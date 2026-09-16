"""Covers app/routers/verification.py's create-session/status endpoints —
previously untested (only the webhook had coverage, in
test_verification_webhook.py).

Two things pinned here, both from Phase 6's "front door" audit:
  - The create-session and webhook endpoints 503 when Stripe isn't
    configured, instead of calling the SDK with an empty key and raising a
    raw 500 (docs/DOCUMENTATION.md §10/§11). The status endpoint instead
    degrades to the stored value, matching payments.checkout_status's
    established convention for a poll endpoint.
  - GET /verification/status resolves a "processing" session straight to
    "verified" on its own, with no webhook involved — this already worked
    before Phase 6, it just had no regression test. This is what makes the
    Profile-page poll (wired up in this phase) actually self-healing.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import stripe

from app.core.config import settings
from app.db import get_db


def _auth(user):
    return {"Authorization": f"Bearer {user['token']}"}


@pytest.fixture
def stripe_stub(monkeypatch):
    session_create = MagicMock(
        return_value=SimpleNamespace(id="vs_test_new", url="https://verify.stripe.test/vs_test_new")
    )
    monkeypatch.setattr(stripe.identity.VerificationSession, "create", session_create)
    return SimpleNamespace(session_create=session_create)


async def test_create_session_503_when_stripe_not_configured(
    client, registered_host, stripe_stub, monkeypatch
):
    monkeypatch.setattr(settings, "stripe_secret_key", "")

    resp = await client.post("/verification/create-session", headers=_auth(registered_host))

    assert resp.status_code == 503
    stripe_stub.session_create.assert_not_called()


async def test_status_degrades_to_stored_value_when_stripe_not_configured(
    client, registered_host, monkeypatch
):
    # Simulate a session that was created before the key got removed: a
    # session_id is stored, but Stripe is unconfigured now.
    db = get_db()
    await db.users.update_one(
        {"email": registered_host["email"]},
        {"$set": {"stripeVerificationSessionId": "vs_test_stale", "verificationStatus": "pending"}},
    )
    monkeypatch.setattr(settings, "stripe_secret_key", "")

    resp = await client.get("/verification/status", headers=_auth(registered_host))

    assert resp.status_code == 200
    assert resp.json() == {"status": "pending", "verified": False}


async def test_status_resolves_processing_to_verified_without_a_webhook(
    client, registered_host, monkeypatch
):
    """The exact deadlock scenario: Stripe has already verified the host,
    but no webhook has landed. Polling /verification/status must resolve
    this on its own from the live Stripe session — the mechanism the
    Profile-page poll (Phase 6) relies on to be self-healing."""
    db = get_db()
    await db.users.update_one(
        {"email": registered_host["email"]},
        {"$set": {"stripeVerificationSessionId": "vs_test_live", "verificationStatus": "processing"}},
    )
    monkeypatch.setattr(
        stripe.identity.VerificationSession,
        "retrieve",
        MagicMock(return_value=SimpleNamespace(status="verified")),
    )

    resp = await client.get("/verification/status", headers=_auth(registered_host))

    assert resp.status_code == 200
    assert resp.json() == {"status": "verified", "verified": True, "stripeStatus": "verified"}

    user = await db.users.find_one({"email": registered_host["email"]})
    assert user["verificationStatus"] == "verified"
