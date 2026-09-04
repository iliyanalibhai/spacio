from datetime import datetime
from io import BytesIO
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File
from motor.motor_asyncio import AsyncIOMotorDatabase
from PIL import Image, UnidentifiedImageError
from pymongo import UpdateOne

from app.core.paths import UPLOAD_DIR
from app.deps.auth import get_current_user
from app.ml.embeddings import listing_text, safe_embed_one
from app.models.schemas import ListingCreate, ListingPublic, ListingUpdate, StorageSize
from app.db import get_db
from app.services.capacity import CAPACITY_HOLDING_STATUSES
from app.services.geo import (
    METERS_PER_MILE,
    MILES_PER_METER,
    to_geojson_point,
    zip_to_coords,
)

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


def _location_for_zip(zip_code: str | None) -> dict | None:
    """GeoJSON Point for a ZIP's centroid, or None if it can't be resolved
    (a typo, or a PO-box-only ZIP the gazetteer omits). A None location just
    means the listing won't appear in radius search until its ZIP is fixed."""
    coords = zip_to_coords(zip_code)
    return to_geojson_point(coords) if coords else None


async def _backfill_missing_locations(db: AsyncIOMotorDatabase) -> None:
    """Give a `location` to any listing created before geocoding existed (or
    seeded without one). Runs only on the radius-search path, and only touches
    rows that are actually missing the field, so it's a no-op once warm."""
    missing = await db.listings.find(
        {"location": {"$exists": False}}, {"zipCode": 1}
    ).to_list(length=1000)
    ops = [
        UpdateOne({"_id": row["_id"]}, {"$set": {"location": location}})
        for row in missing
        if (location := _location_for_zip(row.get("zipCode"))) is not None
    ]
    if ops:
        await db.listings.bulk_write(ops)


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

    if not current_user.get("stripeConnectOnboarded"):
        raise HTTPException(
            status_code=403,
            detail="Set up your payout account before creating listings",
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
        # with no review system behind it) — genuinely null/0 until real
        # reviews exist. app/routers/reviews.py recomputes both on write.
        "rating": None,
        "reviewCount": 0,
        # Sentence embedding of title + description, used by
        # /matching/recommend for semantic search. None if embeddings are
        # disabled or the model is unavailable — /matching/recommend
        # backfills it lazily in that case. See app/ml/embeddings.py.
        "embedding": None,
        # GeoJSON Point (ZIP centroid) for the 2dsphere index / radius search.
        # None when the ZIP can't be geocoded — _backfill_missing_locations
        # retries it later. See app/services/geo.py.
        "location": _location_for_zip(payload.zipCode),
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
    lat: Optional[float] = Query(default=None, ge=-90, le=90),
    lng: Optional[float] = Query(default=None, ge=-180, le=180),
    radiusMiles: float = Query(default=25, gt=0, le=500),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    filters: dict = {}
    if size:
        filters["size"] = size
    if priceMin is not None or priceMax is not None:
        price_filter: dict = {}
        if priceMin is not None:
            price_filter["$gte"] = priceMin
        if priceMax is not None:
            price_filter["$lte"] = priceMax
        filters["pricePerMonth"] = price_filter

    # A search has a geographic origin when the caller passes explicit
    # coordinates ("near me"), or when its ZIP geocodes to a centroid.
    origin: Optional[tuple[float, float]] = None
    if lat is not None and lng is not None:
        origin = (lat, lng)
    elif zipCode:
        origin = zip_to_coords(zipCode)

    distance_miles_by_id: dict[str, float] = {}
    if origin is not None:
        await _backfill_missing_locations(db)
        # $geoNear must be the first pipeline stage; it filters by distance,
        # sorts nearest-first, and reports the distance — all in one pass over
        # the 2dsphere index. `query` applies the price/size filters before
        # the distance sort.
        geo_near: dict = {
            "near": {"type": "Point", "coordinates": [origin[1], origin[0]]},
            "distanceField": "distanceMeters",
            "maxDistance": radiusMiles * METERS_PER_MILE,
            "spherical": True,
        }
        if filters:
            geo_near["query"] = filters
        listings = await db.listings.aggregate(
            [{"$geoNear": geo_near}, {"$limit": 100}]
        ).to_list(length=100)
        distance_miles_by_id = {
            listing["_id"]: round(listing["distanceMeters"] * MILES_PER_METER, 1)
            for listing in listings
        }
    else:
        # No usable origin (no geo params, or a ZIP the gazetteer doesn't
        # have): fall back to the original prefix match on the ZIP string.
        if zipCode:
            filters["zipCode"] = {"$regex": f"^{zipCode}", "$options": "i"}
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
        if listing["_id"] in distance_miles_by_id:
            listing["distanceMiles"] = distance_miles_by_id[listing["_id"]]

    if origin is not None:
        # $geoNear already returned rows nearest-first.
        pass
    elif zipCode:
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

    # Same story for the map point when the ZIP changes.
    if "zipCode" in updates:
        updates["location"] = _location_for_zip(updates["zipCode"])

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
