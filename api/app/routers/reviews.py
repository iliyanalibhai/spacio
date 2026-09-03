from datetime import datetime
from typing import List
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.deps.auth import get_current_user
from app.db import get_db
from app.models.schemas import ReviewCreate, ReviewPublic
from app.services.review_eligibility import ReviewNotAllowedError, assert_can_review

router = APIRouter()


async def _recompute_listing_rating(db: AsyncIOMotorDatabase, listing_id: str) -> None:
    """Recompute a listing's rating/reviewCount from the full set of
    reviews, rather than maintaining a running average — simple, always
    correct even under concurrent writes, and cheap at this project's
    scale (see docs/DOCUMENTATION.md §11's "no ANN index / no pagination"
    reasoning for the same tradeoff elsewhere)."""
    pipeline: list[dict[str, object]] = [
        {"$match": {"listingId": listing_id}},
        {"$group": {"_id": None, "avg": {"$avg": "$rating"}, "count": {"$sum": 1}}},
    ]
    result = await db.reviews.aggregate(pipeline).to_list(length=1)
    if not result:
        await db.listings.update_one({"_id": listing_id}, {"$set": {"rating": None, "reviewCount": 0}})
        return
    await db.listings.update_one(
        {"_id": listing_id},
        {"$set": {"rating": round(result[0]["avg"], 2), "reviewCount": result[0]["count"]}},
    )


@router.post("/", response_model=ReviewPublic, status_code=status.HTTP_201_CREATED)
async def create_review(
    payload: ReviewCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    reservation = await db.reservations.find_one({"_id": payload.reservationId})
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")

    try:
        assert_can_review(reservation, current_user["_id"], datetime.utcnow())
    except ReviewNotAllowedError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    review_id = str(uuid4())
    doc = {
        "_id": review_id,
        "listingId": reservation["listingId"],
        "reservationId": payload.reservationId,
        "renterId": current_user["_id"],
        "rating": payload.rating,
        "comment": payload.comment,
        "createdAt": datetime.utcnow(),
    }
    try:
        await db.reviews.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=400, detail="You already reviewed this stay")

    await _recompute_listing_rating(db, reservation["listingId"])
    return ReviewPublic.model_validate(doc)


@router.get("/listing/{listing_id}", response_model=List[ReviewPublic])
async def list_listing_reviews(listing_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    reviews = await db.reviews.find({"listingId": listing_id}).sort("createdAt", -1).to_list(length=200)
    return [ReviewPublic.model_validate(r) for r in reviews]


@router.get("/reservation/{reservation_id}", response_model=ReviewPublic | None)
async def get_reservation_review(
    reservation_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    reservation = await db.reservations.find_one({"_id": reservation_id})
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")

    listing = await db.listings.find_one({"_id": reservation["listingId"]})
    is_renter = reservation.get("renterId") == current_user["_id"]
    is_host = listing is not None and listing.get("hostId") == current_user["_id"]
    if not (is_renter or is_host):
        raise HTTPException(status_code=403, detail="Not part of this reservation")

    review = await db.reviews.find_one({"reservationId": reservation_id})
    return ReviewPublic.model_validate(review) if review else None
