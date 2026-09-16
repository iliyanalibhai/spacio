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
    if not settings.stripe_configured:
        raise HTTPException(status_code=503, detail="Identity verification is not configured in this environment")

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

    # Mirrors `payments.checkout_status`: a poll endpoint never 500s or
    # 503s, it just degrades to the stored value when there's nothing to
    # refresh from (no session yet, or Stripe isn't configured at all).
    if not session_id or not settings.stripe_configured:
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
    if not settings.stripe_configured:
        raise HTTPException(status_code=503, detail="Identity verification is not configured in this environment")

    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, signature, settings.stripe_webhook_secret)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

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
