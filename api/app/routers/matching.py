import logging
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel
from pymongo import UpdateOne

from app.db import get_db
from app.ml.embeddings import EmbeddingsDisabled, embed, embed_one, listing_text
from app.models.schemas import ListingPublic
from app.services.geo import haversine_miles, to_geojson_point, zip_to_coords
from app.services.matching import match_listings

router = APIRouter()
logger = logging.getLogger(__name__)


class MatchRequest(BaseModel):
    query: str
    zipCode: Optional[str] = None
    # Explicit coordinates ("near me") take precedence over zipCode when both
    # are sent.
    lat: Optional[float] = None
    lng: Optional[float] = None
    # Optional: the SmartMatch UI doesn't collect dates yet, but when it
    # does, listings whose availability window covers the stay are nudged up
    # and ones that clearly don't are pushed down.
    availableFrom: Optional[date] = None
    availableTo: Optional[date] = None


class MatchResponse(BaseModel):
    listings: List[ListingPublic]
    explanation: str


async def _ensure_listing_embeddings(
    db: AsyncIOMotorDatabase, rows: List[dict]
) -> None:
    """Backfill embeddings for any listings that don't have one yet
    (created before this feature, or seeded), persisting them so the work
    happens once. Mutates `rows` in place. Raises `EmbeddingsDisabled` if
    embeddings are off (caller falls back to a non-semantic ranking)."""
    missing = [r for r in rows if not r.get("embedding")]
    if not missing:
        return
    vectors = embed([listing_text(r) for r in missing])
    ops = []
    for row, vector in zip(missing, vectors):
        row["embedding"] = vector.tolist()
        ops.append(UpdateOne({"_id": row["_id"]}, {"$set": {"embedding": row["embedding"]}}))
    if ops:
        await db.listings.bulk_write(ops)
    logger.info("backfilled embeddings for %d listing(s)", len(ops))


async def _ensure_listing_locations(
    db: AsyncIOMotorDatabase, rows: List[dict]
) -> None:
    """Backfill the map point for any listing missing one whose ZIP resolves,
    persisting it once. Mutates `rows` in place. Never raises — a ZIP that
    doesn't geocode is just left without a `location`."""
    ops = []
    for row in rows:
        if row.get("location"):
            continue
        coords = zip_to_coords(row.get("zipCode"))
        if coords is None:
            continue
        row["location"] = to_geojson_point(coords)
        ops.append(UpdateOne({"_id": row["_id"]}, {"$set": {"location": row["location"]}}))
    if ops:
        await db.listings.bulk_write(ops)
        logger.info("backfilled locations for %d listing(s)", len(ops))


@router.post("/recommend", response_model=MatchResponse)
async def recommend(payload: MatchRequest, db: AsyncIOMotorDatabase = Depends(get_db)):
    rows = await db.listings.find({}).to_list(length=500)
    await _ensure_listing_locations(db, rows)

    # Explicit coordinates win; otherwise geocode the ZIP if there is one.
    origin: Optional[tuple[float, float]] = None
    if payload.lat is not None and payload.lng is not None:
        origin = (payload.lat, payload.lng)
    elif payload.zipCode:
        origin = zip_to_coords(payload.zipCode)

    query_vector: Optional[list[float]] = None
    try:
        await _ensure_listing_embeddings(db, rows)
        query_vector = embed_one(payload.query)
    except EmbeddingsDisabled:
        pass  # expected under EMBEDDINGS_ENABLED=false; fall through to structured-only ranking
    except Exception:
        # A model load/run failure must degrade to a non-semantic ranking,
        # never 500 the endpoint.
        logger.warning("semantic matching unavailable; falling back", exc_info=True)

    top, explanation = match_listings(
        rows,
        query_vector,
        origin_coords=origin,
        want_from=payload.availableFrom,
        want_to=payload.availableTo,
    )

    listings_out = []
    for listing in top:
        model = ListingPublic.model_validate(listing)
        if origin is not None and model.lat is not None and model.lng is not None:
            model.distanceMiles = round(
                haversine_miles(origin, (model.lat, model.lng)), 1
            )
        listings_out.append(model)
    return MatchResponse(listings=listings_out, explanation=explanation)
