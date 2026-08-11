from datetime import date, datetime, timedelta
from typing import List, Union
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.deps.auth import get_current_user
from app.db import get_db
from app.models.schemas import ReservationCreate, ReservationPublic, ReservationStatus
from app.services.capacity import CAPACITY_HOLDING_STATUSES, available_sqft_for_range
from app.services.reservation_pricing import (
    DeclaredValueTooHighError,
    calculate_reservation_cost,
)
from app.services.reservation_state import assert_transition, InvalidTransitionError

router = APIRouter()

DateLike = Union[date, datetime]


def _as_datetime(value: DateLike) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.combine(value, datetime.min.time())


@router.post("/", response_model=ReservationPublic, status_code=status.HTTP_201_CREATED)
async def create_reservation(
    payload: ReservationCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    listing = await db.listings.find_one({"_id": payload.listingId})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    if listing.get("hostId") == current_user["_id"]:
        raise HTTPException(status_code=400, detail="You cannot rent your own listing")

    start_dt = datetime.combine(payload.startDate, datetime.min.time())
    end_dt = datetime.combine(payload.endDate, datetime.min.time())
    if end_dt <= start_dt:
        raise HTTPException(status_code=400, detail="End date must be after start date")

    # Fixed from v1: `if A and B if isinstance(x, date) else C` parses as
    # `(A and B) if isinstance(...) else C`, evaluating the wrong branch of
    # the availability-window guard. Written explicitly here instead.
    available_from = listing.get("availableFrom")
    if available_from is not None:
        if start_dt < _as_datetime(available_from):
            raise HTTPException(
                status_code=400,
                detail=f"This space is not available until {available_from}",
            )

    available_to = listing.get("availableTo")
    if available_to is not None:
        if end_dt > _as_datetime(available_to):
            raise HTTPException(
                status_code=400,
                detail=f"This space is only available until {available_to}",
            )

    booking_deadline = listing.get("bookingDeadline")
    if booking_deadline is not None:
        if datetime.utcnow() > _as_datetime(booking_deadline):
            raise HTTPException(
                status_code=400,
                detail=f"Booking deadline has passed ({booking_deadline}). No new reservations accepted.",
            )

    total_sqft = listing.get("sizeSqft", 100)
    sqft_requested = payload.sqftRequested

    if sqft_requested <= 0:
        raise HTTPException(status_code=400, detail="Must request at least 1 sqft")
    if sqft_requested > total_sqft:
        raise HTTPException(
            status_code=400, detail=f"Cannot request more than {total_sqft} sqft available"
        )

    overlapping_reservations = await db.reservations.find(
        {
            "listingId": payload.listingId,
            "status": {"$in": list(CAPACITY_HOLDING_STATUSES)},
            "startDate": {"$lt": end_dt},
            "endDate": {"$gt": start_dt},
        }
    ).to_list(length=500)

    available_sqft = available_sqft_for_range(total_sqft, overlapping_reservations, start_dt, end_dt)
    if sqft_requested > available_sqft:
        raise HTTPException(
            status_code=400,
            detail=f"Only {available_sqft} sqft available for these dates.",
        )

    try:
        cost = calculate_reservation_cost(
            host_monthly_price=listing["pricePerMonth"],
            total_sqft=total_sqft,
            sqft_requested=sqft_requested,
            start=start_dt,
            end=end_dt,
            num_boxes=payload.numBoxes,
            insurance_declared_value=payload.insuranceDeclaredValue,
            has_own_insurance=payload.hasOwnInsurance,
        )
    except DeclaredValueTooHighError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    reservation_id = str(uuid4())
    now = datetime.utcnow()
    doc = {
        "_id": reservation_id,
        "listingId": payload.listingId,
        "renterId": current_user["_id"],
        "startDate": start_dt,
        "endDate": end_dt,
        "sqftRequested": sqft_requested,
        "numBoxes": payload.numBoxes,
        "insuranceDeclaredValue": payload.insuranceDeclaredValue,
        "hasOwnInsurance": payload.hasOwnInsurance,
        "status": ReservationStatus.pending,
        "basePrice": cost.base_price,
        "serviceFee": cost.service_fee,
        "boxCost": cost.box_cost,
        "insuranceCost": cost.insurance_cost,
        "totalPrice": cost.total,
        "holdExpiresAt": now + timedelta(hours=24),
        "createdAt": now,
        # Real payment integration (Stripe Checkout) is Phase 4. This status
        # is deliberately never claimed to be a real charge anywhere in the
        # UI copy.
        "paymentStatus": "mocked-success",
    }
    await db.reservations.insert_one(doc)
    return ReservationPublic.model_validate(doc)


async def _load_reservation_and_listing(db: AsyncIOMotorDatabase, reservation_id: str):
    reservation = await db.reservations.find_one({"_id": reservation_id})
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    listing = await db.listings.find_one({"_id": reservation["listingId"]})
    return reservation, listing


async def _transition_reservation(
    db: AsyncIOMotorDatabase,
    reservation_id: str,
    current_user: dict,
    target_status: ReservationStatus,
) -> dict:
    reservation, listing = await _load_reservation_and_listing(db, reservation_id)
    if not listing or listing.get("hostId") != current_user["_id"]:
        raise HTTPException(status_code=403, detail="Not authorized for this listing")

    current_status = ReservationStatus(reservation["status"])
    try:
        assert_transition(current_status, target_status)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await db.reservations.update_one(
        {"_id": reservation_id}, {"$set": {"status": target_status}}
    )
    reservation["status"] = target_status
    return reservation


@router.post("/{reservation_id}/approve", response_model=ReservationPublic)
async def approve_reservation(
    reservation_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    reservation = await _transition_reservation(
        db, reservation_id, current_user, ReservationStatus.confirmed
    )
    return ReservationPublic.model_validate(reservation)


@router.post("/{reservation_id}/decline", response_model=ReservationPublic)
async def decline_reservation(
    reservation_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    reservation = await _transition_reservation(
        db, reservation_id, current_user, ReservationStatus.declined
    )
    return ReservationPublic.model_validate(reservation)


@router.get("/", response_model=List[ReservationPublic])
async def list_my_reservations(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    filters = {"renterId": current_user["_id"]}

    if current_user.get("isHost"):
        host_listings = await db.listings.find({"hostId": current_user["_id"]}).to_list(
            length=200
        )
        host_listing_ids = [listing["_id"] for listing in host_listings]
        filters = {"$or": [{"renterId": current_user["_id"]}, {"listingId": {"$in": host_listing_ids}}]}

    cursor = db.reservations.find(filters)
    reservations = await cursor.to_list(length=200)
    return [ReservationPublic.model_validate(r) for r in reservations]


@router.delete("/{reservation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reservation(
    reservation_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    reservation, listing = await _load_reservation_and_listing(db, reservation_id)

    is_host_owner = bool(listing) and listing.get("hostId") == current_user["_id"]
    is_renter = reservation.get("renterId") == current_user["_id"]

    if not (is_host_owner or is_renter):
        raise HTTPException(status_code=403, detail="Not authorized for this reservation")

    await db.reservations.delete_one({"_id": reservation_id})
    return None
