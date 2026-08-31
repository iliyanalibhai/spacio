"""Stripe Connect (host payout) onboarding — PR-A.

No real Stripe calls: `stripe.Account.*` / `stripe.AccountLink.*` are
monkeypatched, and the webhook test signs a real payload with the test
signing secret so `stripe.Webhook.construct_event` runs for real (same
approach as test_verification_webhook.py).
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import stripe

from app.core.config import settings
from app.db import get_db
from tests.helpers import sign_stripe_payload

WEBHOOK_PATH = "/payments/webhook"


@pytest.fixture
def stripe_stub(monkeypatch):
    """Patch the Connect calls used by the onboarding endpoints."""
    account_create = MagicMock(return_value=SimpleNamespace(id="acct_test_new"))
    link_create = MagicMock(return_value=SimpleNamespace(url="https://connect.stripe.test/onboard/x"))
    account_retrieve = MagicMock(
        return_value=SimpleNamespace(
            id="acct_test_new", charges_enabled=True, payouts_enabled=True
        )
    )
    monkeypatch.setattr(stripe.Account, "create", account_create)
    monkeypatch.setattr(stripe.AccountLink, "create", link_create)
    monkeypatch.setattr(stripe.Account, "retrieve", account_retrieve)
    return SimpleNamespace(
        account_create=account_create,
        link_create=link_create,
        account_retrieve=account_retrieve,
    )


def _auth(host):
    return {"Authorization": f"Bearer {host['token']}"}


async def test_onboard_creates_account_and_returns_link(client, registered_host, stripe_stub):
    resp = await client.post("/payments/connect/onboard", headers=_auth(registered_host))

    assert resp.status_code == 200
    assert resp.json()["url"].startswith("https://connect.stripe.test/")
    stripe_stub.account_create.assert_called_once()
    assert stripe_stub.account_create.call_args.kwargs["type"] == "express"
    assert "user_id" in stripe_stub.account_create.call_args.kwargs["metadata"]

    db = get_db()
    user = await db.users.find_one({"email": registered_host["email"]})
    assert user["stripeConnectAccountId"] == "acct_test_new"
    assert user["stripeConnectOnboarded"] is False


async def test_onboard_reuses_existing_account(client, registered_host, stripe_stub):
    await client.post("/payments/connect/onboard", headers=_auth(registered_host))
    await client.post("/payments/connect/onboard", headers=_auth(registered_host))

    stripe_stub.account_create.assert_called_once()  # not re-created
    assert stripe_stub.link_create.call_count == 2  # fresh link each time


async def test_onboard_503_when_stripe_not_configured(
    client, registered_host, stripe_stub, monkeypatch
):
    monkeypatch.setattr(settings, "stripe_secret_key", "")

    resp = await client.post("/payments/connect/onboard", headers=_auth(registered_host))

    assert resp.status_code == 503
    stripe_stub.account_create.assert_not_called()


async def test_connect_status_defaults_to_not_onboarded(client, registered_host, stripe_stub):
    resp = await client.get("/payments/connect/status", headers=_auth(registered_host))

    assert resp.status_code == 200
    assert resp.json() == {"onboarded": False, "accountId": None, "error": None}
    stripe_stub.account_retrieve.assert_not_called()


async def test_connect_status_refreshes_from_stripe_and_persists(
    client, registered_host, stripe_stub
):
    await client.post("/payments/connect/onboard", headers=_auth(registered_host))

    resp = await client.get("/payments/connect/status", headers=_auth(registered_host))

    assert resp.status_code == 200
    body = resp.json()
    assert body["onboarded"] is True
    assert body["accountId"] == "acct_test_new"
    stripe_stub.account_retrieve.assert_called_once_with("acct_test_new")

    db = get_db()
    user = await db.users.find_one({"email": registered_host["email"]})
    assert user["stripeConnectOnboarded"] is True


async def test_connect_status_survives_stripe_error(
    client, registered_host, stripe_stub, monkeypatch
):
    await client.post("/payments/connect/onboard", headers=_auth(registered_host))
    monkeypatch.setattr(
        stripe.Account, "retrieve", MagicMock(side_effect=stripe.StripeError("boom"))
    )

    resp = await client.get("/payments/connect/status", headers=_auth(registered_host))

    assert resp.status_code == 200
    body = resp.json()
    assert body["onboarded"] is False
    assert body["error"] == "boom"


async def test_create_listing_blocked_without_connect_onboarding(client, registered_host):
    db = get_db()
    await db.users.update_one(
        {"email": registered_host["email"]}, {"$set": {"verificationStatus": "verified"}}
    )

    resp = await client.post(
        "/listings/",
        headers=_auth(registered_host),
        json={
            "title": "Garage",
            "description": "A garage",
            "size": "M",
            "sizeSqft": 100,
            "pricePerMonth": 40,
            "addressSummary": "Austin, TX",
            "zipCode": "78705",
            "availableFrom": "2026-01-01",
            "availableTo": "2026-12-31",
        },
    )

    assert resp.status_code == 403
    assert "payout account" in resp.json()["detail"]


async def test_create_listing_allowed_once_fully_onboarded(client, verified_host):
    resp = await client.post(
        "/listings/",
        headers=_auth(verified_host),
        json={
            "title": "Garage",
            "description": "A garage",
            "size": "M",
            "sizeSqft": 100,
            "pricePerMonth": 40,
            "addressSummary": "Austin, TX",
            "zipCode": "78705",
            "availableFrom": "2026-01-01",
            "availableTo": "2026-12-31",
        },
    )

    assert resp.status_code == 201


def _account_updated_event(account_id: str, user_id: str, *, charges: bool, payouts: bool) -> bytes:
    return json.dumps(
        {
            "id": "evt_test",
            "object": "event",
            "type": "account.updated",
            "data": {
                "object": {
                    "id": account_id,
                    "charges_enabled": charges,
                    "payouts_enabled": payouts,
                    "metadata": {"user_id": user_id},
                }
            },
        }
    ).encode()


async def test_webhook_rejects_forged_signature(client, registered_host):
    db = get_db()
    user = await db.users.find_one({"email": registered_host["email"]})
    payload = _account_updated_event("acct_x", user["_id"], charges=True, payouts=True)

    resp = await client.post(
        WEBHOOK_PATH,
        content=payload,
        headers={
            "stripe-signature": sign_stripe_payload(payload, "not-the-real-secret"),
            "content-type": "application/json",
        },
    )

    assert resp.status_code == 400


async def test_webhook_account_updated_marks_onboarded(client, registered_host):
    db = get_db()
    user = await db.users.find_one({"email": registered_host["email"]})
    payload = _account_updated_event("acct_x", user["_id"], charges=True, payouts=True)

    resp = await client.post(
        WEBHOOK_PATH,
        content=payload,
        headers={
            "stripe-signature": sign_stripe_payload(
                payload, settings.stripe_payments_webhook_secret
            ),
            "content-type": "application/json",
        },
    )

    assert resp.status_code == 200
    updated = await db.users.find_one({"_id": user["_id"]})
    assert updated["stripeConnectOnboarded"] is True


async def test_webhook_account_updated_incomplete_stays_false(client, registered_host):
    db = get_db()
    user = await db.users.find_one({"email": registered_host["email"]})
    payload = _account_updated_event("acct_x", user["_id"], charges=True, payouts=False)

    resp = await client.post(
        WEBHOOK_PATH,
        content=payload,
        headers={
            "stripe-signature": sign_stripe_payload(
                payload, settings.stripe_payments_webhook_secret
            ),
            "content-type": "application/json",
        },
    )

    assert resp.status_code == 200
    updated = await db.users.find_one({"_id": user["_id"]})
    assert updated.get("stripeConnectOnboarded") is False
