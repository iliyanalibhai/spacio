"""Stripe PaymentIntent capture/cancel side effects for the reservation
approve/decline/cancel flow (PR-B).

Kept separate from `app/routers/payments.py` (which owns Checkout session
creation and the webhook) so `app/routers/reservations.py` doesn't need to
import another router — but the raw `stripe.PaymentIntent` calls here follow
the same pattern used there.
"""

import logging

import stripe
from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings

logger = logging.getLogger(__name__)

stripe.api_key = settings.stripe_secret_key


async def capture_reservation_payment(db: AsyncIOMotorDatabase, reservation: dict) -> None:
    """Capture the renter's already-authorized PaymentIntent when a host
    approves. Raises so an approval can never silently succeed without the
    renter actually being charged."""
    pi_id = reservation.get("stripePaymentIntentId")
    if not pi_id:
        raise HTTPException(status_code=400, detail="No authorized payment to capture")
    try:
        stripe.PaymentIntent.capture(pi_id)
    except stripe.StripeError as e:
        raise HTTPException(status_code=502, detail=f"Payment capture failed: {e}")
    await db.reservations.update_one(
        {"_id": reservation["_id"]}, {"$set": {"paymentStatus": "captured"}}
    )


async def refund_reservation_payment(
    db: AsyncIOMotorDatabase, reservation: dict, *, amount_cents: int, tier: str
) -> None:
    """Refund a *captured* reservation payment when the renter cancels a
    confirmed booking. ``amount_cents`` / ``tier`` come from
    ``services.refund_policy.decide_refund``.

    Unlike ``cancel_reservation_payment`` this is deliberately NOT
    best-effort: a Stripe failure raises, so the reservation is never marked
    cancelled/refunded while the renter's money is still captured.

    ``refund_application_fee`` + ``reverse_transfer`` make Stripe apply the
    same proportion as ``amount_cents`` to the platform fee and to the
    transfer already sent to the host's connected account — so a 50% refund
    claws back 50% of each automatically."""
    pi_id = reservation.get("stripePaymentIntentId")
    if not pi_id:
        raise HTTPException(status_code=400, detail="No captured payment to refund")

    if amount_cents > 0 and settings.stripe_configured:
        try:
            stripe.Refund.create(
                payment_intent=pi_id,
                amount=amount_cents,
                refund_application_fee=True,
                reverse_transfer=True,
                metadata={"reservation_id": reservation["_id"]},
            )
        except stripe.StripeError as e:
            raise HTTPException(status_code=502, detail=f"Refund failed: {e}")

    payment_status = "refunded" if tier == "full" else "partially_refunded"
    await db.reservations.update_one(
        {"_id": reservation["_id"]},
        {"$set": {"paymentStatus": payment_status, "refundedAmount": amount_cents / 100}},
    )


async def cancel_reservation_payment(db: AsyncIOMotorDatabase, reservation: dict) -> None:
    """Release an authorized hold on decline, hold-expiry, or a renter
    cancelling their own still-pending reservation. Best-effort: a Stripe
    error here (e.g. the hold already lapsed on Stripe's side) must never
    block the decline/cancel itself."""
    pi_id = reservation.get("stripePaymentIntentId")
    if pi_id and settings.stripe_configured:
        try:
            stripe.PaymentIntent.cancel(pi_id)
        except stripe.StripeError:
            logger.warning("Failed to cancel PaymentIntent %s", pi_id, exc_info=True)
    await db.reservations.update_one(
        {"_id": reservation["_id"]}, {"$set": {"paymentStatus": "canceled"}}
    )
