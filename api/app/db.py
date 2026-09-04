from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongodb_uri)
    return _client


def get_db() -> AsyncIOMotorDatabase:
    return get_client()[settings.database_name]


async def ensure_indexes() -> None:
    """Create indexes required for correctness (not just performance).

    A full indexing pass with documented rationale for every index is
    scoped to Phase 5. These two exist earlier because they guard against
    real bugs: duplicate accounts via a race in the register endpoint, and
    the capacity/overlap query that every booking depends on.
    """
    db = get_db()
    await db.users.create_index("email", unique=True)
    await db.reservations.create_index(
        [("listingId", 1), ("status", 1), ("startDate", 1), ("endDate", 1)]
    )
    await db.messages.create_index("reservationId")
    # Payments webhooks and the hold-expiry sweep look reservations/users up
    # by their Stripe ids; sparse because only rows that have reached a
    # Stripe flow carry them.
    await db.users.create_index("stripeConnectAccountId", sparse=True)
    # app/services/hold_expiry.py's sweep queries exactly this shape every
    # 60s (status=pending, holdExpiresAt<=now) with no listingId filter, so
    # it can't use the (listingId, status, ...) compound index above.
    await db.reservations.create_index([("status", 1), ("holdExpiresAt", 1)])
    # One review per reservation (not per listing — a renter who books the
    # same listing again gets an independent chance to review that stay
    # too). Enforced here, not just in app/routers/reviews.py, so a race
    # between two concurrent POST /reviews/ for the same reservation can't
    # slip both through.
    await db.reviews.create_index("reservationId", unique=True)
    await db.reviews.create_index("listingId")
    # Radius search (GET /listings?lat=&lng=, and any zipCode search that
    # geocodes) runs a $geoNear aggregation, which requires a 2dsphere index
    # on the GeoJSON point it searches. 2dsphere naturally skips documents
    # with no `location`, so listings whose ZIP didn't geocode are simply
    # absent from geo results rather than erroring. See app/routers/listings.py.
    await db.listings.create_index([("location", "2dsphere")])
