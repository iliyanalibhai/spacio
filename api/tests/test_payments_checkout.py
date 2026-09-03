"""Stripe Checkout for renter payments — PR-B.

Structured like test_payments_connect.py: `stripe.checkout.Session.*` /
`stripe.PaymentIntent.retrieve` are monkeypatched for the create+status
endpoints, and the webhook test signs a real payload with the test signing
secret so `stripe.Webhook.construct_event` runs for real. Capture/cancel on
approve/decline/delete are covered in test_reservation_payment_flow.py.
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


def _auth(user):
    return {"Authorization": f"Bearer {user['token']}"}


@pytest.fixture
def stripe_checkout_stub(monkeypatch):
    session_create = MagicMock(
        return_value=SimpleNamespace(id="cs_test_new", url="https://checkout.stripe.test/pay/x")
    )
    intent_retrieve = MagicMock(
        return_value=SimpleNamespace(id="pi_test_fake", status="requires_capture")
    )
    monkeypatch.setattr(stripe.checkout.Session, "create", session_create)
    monkeypatch.setattr(stripe.PaymentIntent, "retrieve", intent_retrieve)
    return SimpleNamespace(session_create=session_create, intent_retrieve=intent_retrieve)


@pytest.fixture
async def listing(client, verified_host):
    resp = await client.post(
        "/listings/",
        headers=_auth(verified_host),
        json={
            "title": "Test Garage",
            "description": "A garage",
            "size": "L",
            "sizeSqft": 200,
            "pricePerMonth": 60,
            "addressSummary": "Austin, TX",
            "zipCode": "78705",
            "availableFrom": "2026-01-01",
            "availableTo": "2026-12-31",
        },
    )
    return resp.json()


@pytest.fixture
async def reservation(client, registered_renter, listing):
    resp = await client.post(
        "/reservations/",
        headers=_auth(registered_renter),
        json={
            "listingId": listing["_id"],
            "startDate": "2026-02-01",
            "endDate": "2026-02-11",
            "sqftRequested": 50,
        },
    )
    return resp.json()


async def test_create_checkout_session_returns_stripe_url(
    client, registered_renter, reservation, stripe_checkout_stub
):
    resp = await client.post(f"/payments/checkout/{reservation['_id']}", headers=_auth(registered_renter))

    assert resp.status_code == 200
    assert resp.json()["url"].startswith("https://checkout.stripe.test/")

    kwargs = stripe_checkout_stub.session_create.call_args.kwargs
    assert kwargs["payment_intent_data"]["capture_method"] == "manual"
    assert kwargs["payment_intent_data"]["application_fee_amount"] == round(reservation["serviceFee"] * 100)
    assert kwargs["payment_intent_data"]["transfer_data"]["destination"] == "acct_test_verified_host"
    assert kwargs["payment_intent_data"]["metadata"]["reservation_id"] == reservation["_id"]

    db = get_db()
    stored = await db.reservations.find_one({"_id": reservation["_id"]})
    assert stored["stripeCheckoutSessionId"] == "cs_test_new"


async def test_checkout_rejects_non_owner_renter(client, registered_renter, reservation, stripe_checkout_stub):
    await client.post(
        "/auth/register",
        json={
            "name": "Other Renter",
            "email": "other-renter@test.spacio.dev",
            "password": "password123",
            "zipCode": "78705",
            "isHost": False,
        },
    )
    login = await client.post(
        "/auth/login",
        data={"username": "other-renter@test.spacio.dev", "password": "password123"},
    )
    other_headers = {"Authorization": f"Bearer {login.cookies['access_token']}"}

    resp = await client.post(f"/payments/checkout/{reservation['_id']}", headers=other_headers)

    assert resp.status_code == 403
    stripe_checkout_stub.session_create.assert_not_called()


async def test_checkout_503_when_stripe_not_configured(
    client, registered_renter, reservation, stripe_checkout_stub, monkeypatch
):
    monkeypatch.setattr(settings, "stripe_secret_key", "")

    resp = await client.post(f"/payments/checkout/{reservation['_id']}", headers=_auth(registered_renter))

    assert resp.status_code == 503
    stripe_checkout_stub.session_create.assert_not_called()


async def test_checkout_rejects_already_authorized_reservation(
    client, registered_renter, reservation, stripe_checkout_stub
):
    db = get_db()
    await db.reservations.update_one({"_id": reservation["_id"]}, {"$set": {"paymentStatus": "authorized"}})

    resp = await client.post(f"/payments/checkout/{reservation['_id']}", headers=_auth(registered_renter))

    assert resp.status_code == 400
    stripe_checkout_stub.session_create.assert_not_called()


async def test_checkout_status_defaults_to_pending_payment(client, registered_renter, reservation):
    resp = await client.get(
        f"/payments/checkout/status/{reservation['_id']}", headers=_auth(registered_renter)
    )

    assert resp.status_code == 200
    assert resp.json() == {"paymentStatus": "pending_payment", "error": None}


async def test_checkout_status_refreshes_from_stripe_and_persists(
    client, registered_renter, reservation, stripe_checkout_stub
):
    db = get_db()
    await db.reservations.update_one(
        {"_id": reservation["_id"]}, {"$set": {"stripePaymentIntentId": "pi_test_fake"}}
    )

    resp = await client.get(
        f"/payments/checkout/status/{reservation['_id']}", headers=_auth(registered_renter)
    )

    assert resp.status_code == 200
    assert resp.json()["paymentStatus"] == "authorized"
    stripe_checkout_stub.intent_retrieve.assert_called_once_with("pi_test_fake")

    stored = await db.reservations.find_one({"_id": reservation["_id"]})
    assert stored["paymentStatus"] == "authorized"


def _checkout_completed_event(session_id: str, reservation_id: str, payment_intent_id: str) -> bytes:
    return json.dumps(
        {
            "id": "evt_test_checkout",
            "object": "event",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": session_id,
                    "payment_intent": payment_intent_id,
                    "metadata": {"reservation_id": reservation_id},
                }
            },
        }
    ).encode()


def _checkout_expired_event(session_id: str, reservation_id: str) -> bytes:
    return json.dumps(
        {
            "id": "evt_test_checkout_expired",
            "object": "event",
            "type": "checkout.session.expired",
            "data": {"object": {"id": session_id, "metadata": {"reservation_id": reservation_id}}},
        }
    ).encode()


async def test_webhook_checkout_completed_authorizes_reservation(client, reservation):
    payload = _checkout_completed_event("cs_test_x", reservation["_id"], "pi_test_x")

    resp = await client.post(
        WEBHOOK_PATH,
        content=payload,
        headers={
            "stripe-signature": sign_stripe_payload(payload, settings.stripe_payments_webhook_secret),
            "content-type": "application/json",
        },
    )

    assert resp.status_code == 200
    db = get_db()
    updated = await db.reservations.find_one({"_id": reservation["_id"]})
    assert updated["paymentStatus"] == "authorized"
    assert updated["stripePaymentIntentId"] == "pi_test_x"


async def test_webhook_checkout_expired_does_not_clobber_a_later_authorization(client, reservation):
    db = get_db()
    await db.reservations.update_one({"_id": reservation["_id"]}, {"$set": {"paymentStatus": "authorized"}})
    payload = _checkout_expired_event("cs_test_x", reservation["_id"])

    resp = await client.post(
        WEBHOOK_PATH,
        content=payload,
        headers={
            "stripe-signature": sign_stripe_payload(payload, settings.stripe_payments_webhook_secret),
            "content-type": "application/json",
        },
    )

    assert resp.status_code == 200
    updated = await db.reservations.find_one({"_id": reservation["_id"]})
    assert updated["paymentStatus"] == "authorized"


async def test_webhook_checkout_expired_marks_reservation_when_still_pending(client, reservation):
    payload = _checkout_expired_event("cs_test_x", reservation["_id"])

    resp = await client.post(
        WEBHOOK_PATH,
        content=payload,
        headers={
            "stripe-signature": sign_stripe_payload(payload, settings.stripe_payments_webhook_secret),
            "content-type": "application/json",
        },
    )

    assert resp.status_code == 200
    db = get_db()
    updated = await db.reservations.find_one({"_id": reservation["_id"]})
    assert updated["paymentStatus"] == "payment_expired"
