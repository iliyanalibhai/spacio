"""24-hour reservation hold expiry sweep.

Runs as a background asyncio task started from `main.py`'s lifespan — not a
new scheduler dependency, since a single periodic loop is enough for this
single-process deployment (same reasoning as the in-memory rate limiter,
see docs/DOCUMENTATION.md §3). Only started when Stripe is configured
(`Settings.stripe_configured`): without it no host can complete Connect
onboarding, so no listing — and therefore no reservation — can exist yet.

`expire_stale_holds` is the actual sweep logic, kept as a plain async
function (no sleeping, no loop) so it can be unit/integration tested
directly against a real test database; `run_forever` is the thin loop that
schedules it.
"""

import asyncio
import logging
from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.schemas import ReservationStatus
from app.services.reservation_payments import cancel_reservation_payment
from app.services.reservation_state import is_hold_expired

logger = logging.getLogger(__name__)

SWEEP_INTERVAL_SECONDS = 60

# A live authorization hold is only actually outstanding in these
# paymentStatus values — "captured" means the renter was already charged
# (can't happen for a still-pending reservation, but stay defensive) and
# "canceled" means there's nothing left to release.
_RELEASABLE_PAYMENT_STATUSES = {"pending_payment", "authorized", "payment_expired"}


async def expire_stale_holds(db: AsyncIOMotorDatabase, *, now: datetime | None = None) -> int:
    """Expire every still-pending reservation whose 24h hold has elapsed,
    releasing any outstanding payment authorization. Returns the count
    expired."""
    now = now or datetime.utcnow()
    cursor = db.reservations.find(
        {"status": ReservationStatus.pending, "holdExpiresAt": {"$lte": now}}
    )

    expired = 0
    async for reservation in cursor:
        # Defensive re-check through the same tested predicate the state
        # machine uses elsewhere, rather than trusting the Mongo query alone
        # as the one source of truth for "is this actually expired."
        if not is_hold_expired(ReservationStatus(reservation["status"]), reservation["holdExpiresAt"], now):
            continue

        await db.reservations.update_one(
            {"_id": reservation["_id"]}, {"$set": {"status": ReservationStatus.expired}}
        )
        if reservation.get("paymentStatus") in _RELEASABLE_PAYMENT_STATUSES:
            await cancel_reservation_payment(db, reservation)
        expired += 1

    if expired:
        logger.info("Expired %d stale reservation hold(s)", expired)
    return expired


async def run_forever(db: AsyncIOMotorDatabase) -> None:
    while True:
        try:
            await expire_stale_holds(db)
        except Exception:
            logger.exception("Hold-expiry sweep iteration failed")
        await asyncio.sleep(SWEEP_INTERVAL_SECONDS)
