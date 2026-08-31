"""Stripe Connect (host payouts) + Checkout (renter payments).

Structured exactly like `app/routers/verification.py` (the Stripe Identity
integration): `stripe.api_key` set at import, a redirect-based hosted flow
(`/connect/onboard` returns a URL the frontend navigates to, like the
Identity session), a `/connect/status` poll endpoint, and a single
signature-verified webhook.

PR-A scope: Connect onboarding only. `POST /payments/webhook` handles
`account.updated` here; `checkout.session.*` events are accepted and
ignored until PR-B wires Checkout.
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

router = APIRouter()
logger = logging.getLogger(__name__)

stripe.api_key = settings.stripe_secret_key

# A connected account is only usable for payouts once Stripe reports BOTH
# flags true. `details_submitted` alone goes true while the account is still
# under review / restricted, so it is not sufficient.
_READY_FLAGS = ("charges_enabled", "payouts_enabled")


class ConnectStatusResponse(BaseModel):
    onboarded: bool
    accountId: str | None = None
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

    # checkout.session.completed / checkout.session.expired are wired in PR-B.
    return {"received": True}
