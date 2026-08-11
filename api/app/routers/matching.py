from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db import get_db
from app.models.schemas import ListingPublic
from app.services.matching import match_listings

router = APIRouter()


class MatchRequest(BaseModel):
    query: str
    zipCode: Optional[str] = None


class MatchResponse(BaseModel):
    listings: List[ListingPublic]
    explanation: str


@router.post("/recommend", response_model=MatchResponse)
async def recommend(payload: MatchRequest, db: AsyncIOMotorDatabase = Depends(get_db)):
    rows = await db.listings.find({}).to_list(length=500)
    top, explanation = match_listings(rows, payload.query, payload.zipCode)
    return MatchResponse(listings=[ListingPublic.model_validate(listing) for listing in top], explanation=explanation)
