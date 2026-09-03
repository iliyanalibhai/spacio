"""Stripe Connect (host payouts) + Checkout (renter payments).

Structured exactly like `app/routers/verification.py` (the Stripe Identity
integration): `stripe.api_key` set at import, a redirect-based hosted flow
(`/connect/onboard`, `/checkout/{id}` each return a URL the frontend
navigates to, like the Identity session), poll endpoints, and a single
signature-verified webhook.

PR-A scope was Connect onboarding only. PR-B (this file, now) adds Checkout:
`POST /payments/checkout/{reservation_id}` creates a Checkout Session whose
PaymentIntent uses `capture_method="manual"` — the renter's card is
authorized (funds held) at booking time but not actually charged until the
host approves (`reservations.approve_reservation` calls
`services.reservation_payments.capture_reservation_payment`). A decline,
hold-expiry, or renter cancellation instead cancels the authorization
(`cancel_reservation_payment`), releasing the hold with no charge. The
Checkout Session's `transfer_data.destination` sends the money straight to
the host's Connect account, with `application_fee_amount` set to the
reservation's own `serviceFee` — Spacio's cut — so the split is exactly the
number already shown to the renter in the booking quote.
"""

import logging

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from app.core.config import settings
from app.core.rate_limit import limiter
from app.db import get_db
from app.deps.auth import get_current_user
from app.models.schemas import ReservationStatus

router = APIRouter()
logger = logging.getLogger(__name__)

stripe.api_key = settings.stripe_secret_key

# A connected account is only usable for payouts once Stripe reports BOTH
# flags true. `details_submitted` alone goes true while the account is still
# under review / restricted, so it is not sufficient.
_READY_FLAGS = ("charges_enabled", "payouts_enabled")

# Reservation paymentStatus values a Checkout Session may be (re)started
# from — i.e. no successful authorization exists yet.
_PAYABLE_STATUSES = {"pending_payment", "payment_expired"}

# stripe.PaymentIntent.status -> our paymentStatus, used by both the poll
# endpoint and (for capture/cancel) implicitly documented by
# services/reservation_payments.py.
_PAYMENT_INTENT_STATUS_MAP = {
    "requires_payment_method": "pending_payment",
    "requires_confirmation": "pending_payment",
    "requires_action": "pending_payment",
    "processing": "pending_payment",
    "requires_capture": "authorized",
    "succeeded": "captured",
    "canceled": "canceled",
}


class ConnectStatusResponse(BaseModel):
    onboarded: bool
    accountId: str | None = None
    error: str | None = None


class CheckoutSessionResponse(BaseModel):
    url: str


class CheckoutStatusResponse(BaseModel):
    paymentStatus: str
    error: str | None = None


def _account_ready(account: object) -> bool:
    return all(bool(getattr(account, flag, None)) for flag in _READY_FLAGS)


@router.post("/connect/onboard")
@limiter.limit("5/minute")
async def connect_onboard(
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create (or reuse) an Express connected account for the host and
    return a Stripe-hosted onboarding link. Mirrors
    `verification.create_verification_session`."""
    if not settings.stripe_configured:
        raise HTTPException(status_code=503, detail="Payments are not configured in this environment")

    # Same convenience as the Identity flow: starting payout setup makes you
    # a host.
    if not current_user.get("isHost"):
        await db.users.update_one({"_id": current_user["_id"]}, {"$set": {"isHost": True}})

    account_id = current_user.get("stripeConnectAccountId")
    try:
        if not account_id:
            account = stripe.Account.create(
                type="express",
                email=current_user["email"],
                business_type="individual",
                capabilities={
                    "transfers": {"requested": True},
                    "card_payments": {"requested": True},
                },
                metadata={"user_id": current_user["_id"]},
            )
            account_id = account.id
            await db.users.update_one(
                {"_id": current_user["_id"]},
                {"$set": {"stripeConnectAccountId": account_id, "stripeConnectOnboarded": False}},
            )

        link = stripe.AccountLink.create(
            account=account_id,
            type="account_onboarding",
            refresh_url=f"{settings.frontend_url}/host?onboarding=refresh",
            return_url=f"{settings.frontend_url}/host?onboarding=complete",
        )
        return {"url": link.url}

    except stripe.StripeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/connect/status", response_model=ConnectStatusResponse)
async def connect_status(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Return the host's payout-onboarding state. Like
    `verification.get_verification_status`: refreshes from Stripe when an
    account exists, persists any change, and never 500s on a Stripe error —
    it falls back to the stored value."""
    account_id = current_user.get("stripeConnectAccountId")
    stored = bool(current_user.get("stripeConnectOnboarded"))

    if not account_id or not settings.stripe_configured:
        return ConnectStatusResponse(onboarded=stored, accountId=account_id)

    try:
        account = stripe.Account.retrieve(account_id)
    except stripe.StripeError as e:
        return ConnectStatusResponse(onboarded=stored, accountId=account_id, error=str(e))

    ready = _account_ready(account)
    if ready != stored:
        await db.users.update_one(
            {"_id": current_user["_id"]}, {"$set": {"stripeConnectOnboarded": ready}}
        )
    return ConnectStatusResponse(onboarded=ready, accountId=account_id)


@router.post("/checkout/{reservation_id}", response_model=CheckoutSessionResponse)
@limiter.limit("10/minute")
async def create_checkout_session(
    request: Request,
    reservation_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a Stripe Checkout Session that authorizes (does not yet
    capture) the renter's card for a reservation's total. Redirect-based
    hosted flow, same shape as `connect_onboard` /
    `verification.create_verification_session`: returns a URL for the
    frontend to navigate to."""
    if not settings.stripe_configured:
        raise HTTPException(status_code=503, detail="Payments are not configured in this environment")

    reservation = await db.reservations.find_one({"_id": reservation_id})
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    if reservation.get("renterId") != current_user["_id"]:
        raise HTTPException(status_code=403, detail="Not authorized for this reservation")
    if reservation.get("status") != ReservationStatus.pending:
        raise HTTPException(status_code=400, detail="This reservation is no longer awaiting payment")
    if reservation.get("paymentStatus") not in _PAYABLE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Reservation payment is already {reservation.get('paymentStatus')}",
        )

    listing = await db.listings.find_one({"_id": reservation["listingId"]})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    host = await db.users.find_one({"_id": listing["hostId"]})
    host_account_id = host.get("stripeConnectAccountId") if host else None
    if not host_account_id:
        raise HTTPException(status_code=400, detail="Host has not completed payout onboarding")

    amount_cents = round(reservation["totalPrice"] * 100)
    fee_cents = round(reservation["serviceFee"] * 100)

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": f"Spacio reservation: {listing['title']}"},
                        "unit_amount": amount_cents,
                    },
                    "quantity": 1,
                }
            ],
            payment_intent_data={
                "capture_method": "manual",
                "application_fee_amount": fee_cents,
                "transfer_data": {"destination": host_account_id},
                "metadata": {"reservation_id": reservation_id},
            },
            metadata={"reservation_id": reservation_id},
            success_url=f"{settings.frontend_url}/profile?checkout=complete&reservation={reservation_id}",
            cancel_url=f"{settings.frontend_url}/profile?checkout=cancelled&reservation={reservation_id}",
        )
    except stripe.StripeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not session.url:
        raise HTTPException(status_code=500, detail="Stripe did not return a checkout URL")

    await db.reservations.update_one(
        {"_id": reservation_id}, {"$set": {"stripeCheckoutSessionId": session.id}}
    )
    return CheckoutSessionResponse(url=session.url)


@router.get("/checkout/status/{reservation_id}", response_model=CheckoutStatusResponse)
async def checkout_status(
    reservation_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Poll a reservation's payment-authorization state, like
    `connect_status` / `verification.get_verification_status`: refreshes
    from Stripe when a PaymentIntent exists, persists any change, and never
    500s on a Stripe error — it falls back to the stored value. Used right
    after the renter is redirected back from Checkout, since the webhook may
    not have arrived yet."""
    reservation = await db.reservations.find_one({"_id": reservation_id})
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    if reservation.get("renterId") != current_user["_id"]:
        raise HTTPException(status_code=403, detail="Not authorized for this reservation")

    pi_id = reservation.get("stripePaymentIntentId")
    stored = reservation.get("paymentStatus", "pending_payment")
    if not pi_id or not settings.stripe_configured:
        return CheckoutStatusResponse(paymentStatus=stored)

    try:
        intent = stripe.PaymentIntent.retrieve(pi_id)
    except stripe.StripeError as e:
        return CheckoutStatusResponse(paymentStatus=stored, error=str(e))

    mapped = _PAYMENT_INTENT_STATUS_MAP.get(intent.status, stored)
    if mapped != stored:
        await db.reservations.update_one({"_id": reservation_id}, {"$set": {"paymentStatus": mapped}})
    return CheckoutStatusResponse(paymentStatus=mapped)


@router.post("/webhook")
async def payments_webhook(request: Request, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Signature-verified Stripe webhook for payments + Connect events.

    Same `construct_event` guard as `verification.stripe_webhook`, but with
    its own signing secret (`stripe_payments_webhook_secret`). Every branch
    is an idempotent `$set`, so redelivery / out-of-order delivery is safe
    and no processed-events table is needed."""
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload, signature, settings.stripe_payments_webhook_secret
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event.type == "account.updated":
        account = event.data.object
        onboarded = bool(account.get("charges_enabled") and account.get("payouts_enabled"))
        user_id = account.get("metadata", {}).get("user_id")
        query = {"_id": user_id} if user_id else {"stripeConnectAccountId": account["id"]}
        await db.users.update_one(query, {"$set": {"stripeConnectOnboarded": onboarded}})

    elif event.type == "checkout.session.completed":
        session = event.data.object
        reservation_id = session.get("metadata", {}).get("reservation_id")
        payment_intent_id = session.get("payment_intent")
        if reservation_id:
            await db.reservations.update_one(
                {"_id": reservation_id},
                {"$set": {"paymentStatus": "authorized", "stripePaymentIntentId": payment_intent_id}},
            )

    elif event.type == "checkout.session.expired":
        session = event.data.object
        reservation_id = session.get("metadata", {}).get("reservation_id")
        if reservation_id:
            # Guarded on the stored status so a late/out-of-order expiry
            # event can never clobber a reservation that already got
            # authorized (or beyond) through a later Checkout attempt.
            await db.reservations.update_one(
                {"_id": reservation_id, "paymentStatus": "pending_payment"},
                {"$set": {"paymentStatus": "payment_expired"}},
            )

    return {"received": True}
