import json

from fastapi import APIRouter, Depends, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorDatabase
import stripe

from app.core.config import settings
from app.db import get_db
from app.deps.auth import get_current_user

router = APIRouter()

stripe.api_key = settings.stripe_secret_key


@router.post("/create-session")
async def create_verification_session(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    if current_user.get("verificationStatus") == "verified":
        raise HTTPException(status_code=400, detail="Already verified")

    if not current_user.get("isHost"):
        await db.users.update_one({"_id": current_user["_id"]}, {"$set": {"isHost": True}})

    try:
        verification_session = stripe.identity.VerificationSession.create(
            type="document",
            metadata={"user_id": current_user["_id"]},
            options={
                "document": {
                    "allowed_types": ["driving_license", "passport", "id_card"],
                    "require_id_number": False,
                    "require_live_capture": True,
                    "require_matching_selfie": True,
                },
            },
            return_url=f"{settings.frontend_url}/profile?verified=pending",
        )

        await db.users.update_one(
            {"_id": current_user["_id"]},
            {
                "$set": {
                    "stripeVerificationSessionId": verification_session.id,
                    "verificationStatus": "pending",
                }
            },
        )

        return {"url": verification_session.url, "sessionId": verification_session.id}

    except stripe.StripeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_verification_status(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    session_id = current_user.get("stripeVerificationSessionId")

    if not session_id:
        return {
            "status": current_user.get("verificationStatus", "unverified"),
            "verified": current_user.get("verificationStatus") == "verified",
        }

    try:
        session = stripe.identity.VerificationSession.retrieve(session_id)

        status_map = {
            "verified": "verified",
            "requires_input": "pending",
            "processing": "processing",
            "canceled": "cancelled",
        }
        new_status = status_map.get(session.status, "pending")

        if new_status != current_user.get("verificationStatus"):
            await db.users.update_one(
                {"_id": current_user["_id"]}, {"$set": {"verificationStatus": new_status}}
            )

        return {"status": new_status, "verified": new_status == "verified", "stripeStatus": session.status}

    except stripe.StripeError as e:
        return {
            "status": current_user.get("verificationStatus", "unverified"),
            "verified": False,
            "error": str(e),
        }


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncIOMotorDatabase = Depends(get_db)):
    # NOTE: this does not verify the Stripe signature yet
    # (stripe.Webhook.construct_event with STRIPE_WEBHOOK_SECRET). As written,
    # anyone on the internet can POST a forged identity.verification_session.verified
    # event with an arbitrary user_id and become a "verified" host. This is a
    # known Tier 2 vulnerability, fixed in Phase 1 — see docs/DOCUMENTATION.md §7.
    # Left unverified here (rather than fixed early) to keep Phase 0 scoped to
    # "the repo runs" and Phase 1 scoped to "the repo is safe to deploy."
    payload = await request.body()

    try:
        event = stripe.Event.construct_from(json.loads(payload), stripe.api_key)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")

    if event.type == "identity.verification_session.verified":
        session = event.data.object
        user_id = session.get("metadata", {}).get("user_id")
        if user_id:
            await db.users.update_one(
                {"_id": user_id}, {"$set": {"verificationStatus": "verified"}}
            )

    elif event.type == "identity.verification_session.requires_input":
        session = event.data.object
        user_id = session.get("metadata", {}).get("user_id")
        if user_id:
            await db.users.update_one(
                {"_id": user_id}, {"$set": {"verificationStatus": "requires_input"}}
            )

    return {"received": True}
