"""Covers the Stripe Identity webhook's signature verification.

This closes the Tier 2 vulnerability tracked in docs/DOCUMENTATION.md §7:
before signature verification was wired up, anyone could POST a forged
identity.verification_session.verified event and mark an arbitrary user
"verified". These tests pin that a valid signature is required and that a
correctly signed event still updates the user as expected.
"""

import hmac
import json
import time
from hashlib import sha256

from app.core.config import settings
from app.db import get_db

WEBHOOK_PATH = "/verification/webhook"


def _sign(payload: bytes, secret: str, timestamp: int | None = None) -> str:
    timestamp = timestamp if timestamp is not None else int(time.time())
    signed_payload = f"{timestamp}.".encode() + payload
    signature = hmac.new(secret.encode(), signed_payload, sha256).hexdigest()
    return f"t={timestamp},v1={signature}"


def _event(user_id: str, event_type: str) -> bytes:
    return json.dumps(
        {
            "id": "evt_test",
            "object": "event",
            "type": event_type,
            "data": {"object": {"metadata": {"user_id": user_id}}},
        }
    ).encode()


async def test_webhook_rejects_forged_signature(client, registered_host):
    payload = _event(user_id="whoever-i-want", event_type="identity.verification_session.verified")

    response = await client.post(
        WEBHOOK_PATH,
        content=payload,
        headers={
            "stripe-signature": _sign(payload, "not-the-real-secret"),
            "content-type": "application/json",
        },
    )

    assert response.status_code == 400


async def test_webhook_rejects_missing_signature(client, registered_host):
    payload = _event(user_id="whoever-i-want", event_type="identity.verification_session.verified")

    response = await client.post(
        WEBHOOK_PATH, content=payload, headers={"content-type": "application/json"}
    )

    assert response.status_code == 400


async def test_webhook_accepts_valid_signature_and_updates_status(client, registered_host):
    db = get_db()
    user = await db.users.find_one({"email": registered_host["email"]})
    payload = _event(user_id=user["_id"], event_type="identity.verification_session.verified")

    response = await client.post(
        WEBHOOK_PATH,
        content=payload,
        headers={
            "stripe-signature": _sign(payload, settings.stripe_webhook_secret),
            "content-type": "application/json",
        },
    )

    assert response.status_code == 200
    updated = await db.users.find_one({"_id": user["_id"]})
    assert updated["verificationStatus"] == "verified"
