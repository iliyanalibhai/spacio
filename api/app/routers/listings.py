from datetime import datetime
from io import BytesIO
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File
from motor.motor_asyncio import AsyncIOMotorDatabase
from PIL import Image, UnidentifiedImageError

from app.core.paths import UPLOAD_DIR
from app.deps.auth import get_current_user
from app.ml.embeddings import listing_text, safe_embed_one
from app.models.schemas import ListingCreate, ListingPublic, ListingUpdate, StorageSize
from app.db import get_db
from app.services.capacity import CAPACITY_HOLDING_STATUSES

router = APIRouter()

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
# Keyed by what Pillow reports after actually decoding the file, not by
# client-supplied Content-Type or filename extension (both are attacker
# controlled).
ALLOWED_IMAGE_FORMATS = {"JPEG": ".jpg", "PNG": ".png"}


def _size_bucket_for_sqft(sqft: float) -> StorageSize:
    if sqft <= 60:
        return StorageSize.small
    if sqft <= 150:
        return StorageSize.medium
    return StorageSize.large


@router.post("/", response_model=ListingPublic, status_code=status.HTTP_201_CREATED)
async def create_listing(
    payload: ListingCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if not current_user.get("isHost"):
        raise HTTPException(status_code=403, detail="Only hosts can create listings")

    if current_user.get("verificationStatus") != "verified":
        raise HTTPException(
            status_code=403, detail="You must verify your identity before creating listings"
        )

    listing_id = str(uuid4())
    now = datetime.utcnow()

    payload_dict = payload.model_dump()
    for date_field in ("availableFrom", "availableTo", "bookingDeadline"):
        if payload_dict.get(date_field):
            payload_dict[date_field] = datetime.combine(payload_dict[date_field], datetime.min.time())

    doc = {
        "_id": listing_id,
        "hostId": current_user["_id"],
        **payload_dict,
        "size": _size_bucket_for_sqft(payload.sizeSqft),
        # No fabricated default rating (v1 hardcoded 4.7 on every listing
        # with no review system behind it). Real ratings arrive with the
        # Phase 4 review system; until then this is genuinely null.
        "rating": None,
        # Sentence embedding of title + description, used by
        # /matching/recommend for semantic search. None if embeddings are
        # disabled or the model is unavailable — /matching/recommend
        # backfills it lazily in that case. See app/ml/embeddings.py.
        "embedding": None,
        "createdAt": now,
    }
    doc["embedding"] = safe_embed_one(listing_text(doc))
    await db.listings.insert_one(doc)
    return ListingPublic.model_validate(doc)


@router.get("/", response_model=List[ListingPublic])
async def list_listings(
    zipCode: Optional[str] = None,
    startDate: Optional[str] = None,
    endDate: Optional[str] = None,
    priceMin: Optional[float] = Query(default=None, ge=0),
    priceMax: Optional[float] = Query(default=None, ge=0),
    size: Optional[StorageSize] = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    filters: dict = {}
    if zipCode:
        filters["zipCode"] = {"$regex": f"^{zipCode}", "$options": "i"}
    if size:
        filters["size"] = size
    if priceMin is not None or priceMax is not None:
        price_filter: dict = {}
        if priceMin is not None:
            price_filter["$gte"] = priceMin
        if priceMax is not None:
            price_filter["$lte"] = priceMax
        filters["pricePerMonth"] = price_filter

    listings = await db.listings.find(filters).to_list(length=100)

    if startDate and endDate:
        search_start = datetime.fromisoformat(startDate)
        search_end = datetime.fromisoformat(endDate)

        def is_within_availability(listing: dict) -> bool:
            available_from = listing.get("availableFrom")
            available_to = listing.get("availableTo")
            if available_from and search_start < available_from:
                return False
            if available_to and search_end > available_to:
                return False
            return True

        listings = [listing for listing in listings if is_within_availability(listing)]

    host_ids = list({listing.get("hostId") for listing in listings if listing.get("hostId")})
    hosts = {}
    if host_ids:
        host_list = await db.users.find({"_id": {"$in": host_ids}}).to_list(length=100)
        hosts = {h["_id"]: h for h in host_list}

    listing_ids = [listing["_id"] for listing in listings]
    now = datetime.utcnow()
    active_reservations = await db.reservations.find(
        {
            "listingId": {"$in": listing_ids},
            "status": {"$in": list(CAPACITY_HOLDING_STATUSES)},
            "endDate": {"$gt": now},
        }
    ).to_list(length=1000)

    reservations_by_listing: dict[str, list[dict]] = {}
    for reservation in active_reservations:
        reservations_by_listing.setdefault(reservation["listingId"], []).append(reservation)

    for listing in listings:
        host = hosts.get(listing.get("hostId"), {})
        listing["hostVerified"] = host.get("verificationStatus") == "verified"
        total_sqft = listing.get("sizeSqft", 100)
        reserved_sqft = sum(
            r.get("sqftRequested", 0) for r in reservations_by_listing.get(listing["_id"], [])
        )
        listing["availableSqft"] = max(0, total_sqft - reserved_sqft)

    if zipCode:
        listings.sort(
            key=lambda listing: (
                0 if listing.get("zipCode") == zipCode else 1,
                -(listing.get("rating") or 0),
            )
        )
    return [ListingPublic.model_validate(listing) for listing in listings]


@router.get("/mine", response_model=List[ListingPublic])
async def my_listings(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if not current_user.get("isHost"):
        raise HTTPException(status_code=403, detail="Only hosts can view their listings")
    items = await db.listings.find({"hostId": current_user["_id"]}).to_list(length=200)
    return [ListingPublic.model_validate(item) for item in items]


@router.get("/{listing_id}", response_model=ListingPublic)
async def get_listing(listing_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    listing = await db.listings.find_one({"_id": listing_id})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    return ListingPublic.model_validate(listing)


@router.patch("/{listing_id}", response_model=ListingPublic)
async def update_listing(
    listing_id: str,
    payload: ListingUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    listing = await db.listings.find_one({"_id": listing_id})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.get("hostId") != current_user["_id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    updates = payload.model_dump(exclude_unset=True)
    if "sizeSqft" in updates and updates["sizeSqft"] is not None:
        updates["size"] = _size_bucket_for_sqft(updates["sizeSqft"])
    if not updates:
        return ListingPublic.model_validate(listing)

    # The embedding is derived from title + description, so it goes stale
    # whenever either changes. Recompute from the merged document.
    if "title" in updates or "description" in updates:
        updates["embedding"] = safe_embed_one(listing_text({**listing, **updates}))

    await db.listings.update_one({"_id": listing_id}, {"$set": updates})
    listing.update(updates)
    return ListingPublic.model_validate(listing)


@router.delete("/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_listing(
    listing_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    listing = await db.listings.find_one({"_id": listing_id})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.get("hostId") != current_user["_id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    await db.listings.delete_one({"_id": listing_id})
    return None


@router.post("/upload")
async def upload_image(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    # Read at most MAX_UPLOAD_BYTES + 1: if the client sends more, this still
    # only buffers one byte over the cap in memory rather than the whole
    # (potentially huge) upload before we get a chance to reject it.
    contents = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image must be 5MB or smaller")

    try:
        probe = Image.open(BytesIO(contents))
        probe.verify()  # decodes just enough to confirm this isn't corrupt/not-an-image
    except (UnidentifiedImageError, OSError, SyntaxError):
        raise HTTPException(status_code=400, detail="Only JPEG and PNG images are allowed")

    if probe.format not in ALLOWED_IMAGE_FORMATS:
        raise HTTPException(status_code=400, detail="Only JPEG and PNG images are allowed")
    image_format = probe.format
    assert image_format is not None  # narrowed by the `in ALLOWED_IMAGE_FORMATS` check above

    # verify() leaves the Image unusable for further ops, so reopen for the
    # real decode. Pillow also caps decompressed pixel count by default
    # (Image.MAX_IMAGE_PIXELS), guarding against decompression-bomb uploads.
    image: Image.Image = Image.open(BytesIO(contents))
    if image_format == "JPEG" and image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4()}{ALLOWED_IMAGE_FORMATS[image_format]}"
    dest = UPLOAD_DIR / filename

    # Saving the re-decoded pixel data (instead of writing `contents` to disk
    # as-is) strips EXIF metadata and any bytes appended after the image data
    # by the client, since only what Pillow actually decoded gets written.
    image.save(dest, format=image_format)

    return {"url": f"/uploads/{filename}"}
