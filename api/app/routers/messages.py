from datetime import datetime
from typing import List
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.deps.auth import get_current_user
from app.db import get_db
from app.models.schemas import MessageCreate, MessagePublic

router = APIRouter()


async def _assert_participant(
    db: AsyncIOMotorDatabase, reservation_id: str, user_id: str, is_host: bool
) -> dict:
    reservation = await db.reservations.find_one({"_id": reservation_id})
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")

    listing = await db.listings.find_one({"_id": reservation["listingId"]})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    allowed = reservation["renterId"] == user_id or (is_host and listing.get("hostId") == user_id)
    if not allowed:
        raise HTTPException(status_code=403, detail="Not part of this reservation")
    return reservation


@router.post("/", response_model=MessagePublic, status_code=status.HTTP_201_CREATED)
async def send_message(
    payload: MessageCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await _assert_participant(
        db, payload.reservationId, current_user["_id"], current_user.get("isHost", False)
    )

    message_id = str(uuid4())
    now = datetime.utcnow()
    doc = {
        "_id": message_id,
        "reservationId": payload.reservationId,
        "senderId": current_user["_id"],
        "content": payload.content,
        "createdAt": now,
    }
    await db.messages.insert_one(doc)
    return MessagePublic.model_validate(doc)


@router.get("/{reservation_id}", response_model=List[MessagePublic])
async def list_messages(
    reservation_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await _assert_participant(
        db, reservation_id, current_user["_id"], current_user.get("isHost", False)
    )
    messages = await db.messages.find({"reservationId": reservation_id}).sort("createdAt").to_list(
        length=500
    )
    return [MessagePublic.model_validate(m) for m in messages]
