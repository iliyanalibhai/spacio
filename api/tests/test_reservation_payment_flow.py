"""Reservation approve/decline/cancel payment-lifecycle gating (PR-B):
capture-on-approve, cancel-on-decline/cancel, and the "not paid yet" gate on
approve. Stripe PaymentIntent capture/cancel calls are monkeypatched here;
Checkout Session creation + the webhook are covered in
test_payments_checkout.py."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import stripe

from app.db import get_db


def _auth(user):
    return {"Authorization": f"Bearer {user['token']}"}


@pytest.fixture
def stripe_payment_intent_stub(monkeypatch):
    capture = MagicMock()
    cancel = MagicMock()
    monkeypatch.setattr(stripe.PaymentIntent, "capture", capture)
    monkeypatch.setattr(stripe.PaymentIntent, "cancel", cancel)
    return SimpleNamespace(capture=capture, cancel=cancel)


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


async def _mark_authorized(reservation_id: str) -> None:
    db = get_db()
    await db.reservations.update_one(
        {"_id": reservation_id},
        {"$set": {"paymentStatus": "authorized", "stripePaymentIntentId": "pi_test_fake"}},
    )


async def test_approve_blocked_until_payment_authorized(client, verified_host, reservation):
    assert reservation["paymentStatus"] == "pending_payment"

    resp = await client.post(f"/reservations/{reservation['_id']}/approve", headers=_auth(verified_host))

    assert resp.status_code == 400
    assert "payment" in resp.json()["detail"].lower()


async def test_approve_captures_payment(client, verified_host, reservation, stripe_payment_intent_stub):
    await _mark_authorized(reservation["_id"])

    resp = await client.post(f"/reservations/{reservation['_id']}/approve", headers=_auth(verified_host))

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "confirmed"
    assert body["paymentStatus"] == "captured"
    stripe_payment_intent_stub.capture.assert_called_once_with("pi_test_fake")

    db = get_db()
    stored = await db.reservations.find_one({"_id": reservation["_id"]})
    assert stored["paymentStatus"] == "captured"
    assert stored["status"] == "confirmed"


async def test_approve_fails_if_capture_rejected(client, verified_host, reservation, stripe_payment_intent_stub):
    await _mark_authorized(reservation["_id"])
    stripe_payment_intent_stub.capture.side_effect = stripe.StripeError("card issuer declined")

    resp = await client.post(f"/reservations/{reservation['_id']}/approve", headers=_auth(verified_host))

    assert resp.status_code == 502

    db = get_db()
    stored = await db.reservations.find_one({"_id": reservation["_id"]})
    # A rejected capture must not leave the reservation looking confirmed.
    assert stored["status"] == "pending_host_confirmation"
    assert stored["paymentStatus"] == "authorized"


async def test_decline_before_payment_needs_no_stripe_call(
    client, verified_host, reservation, stripe_payment_intent_stub
):
    resp = await client.post(f"/reservations/{reservation['_id']}/decline", headers=_auth(verified_host))

    assert resp.status_code == 200
    assert resp.json()["paymentStatus"] == "canceled"
    stripe_payment_intent_stub.cancel.assert_not_called()


async def test_decline_after_authorization_cancels_the_hold(
    client, verified_host, reservation, stripe_payment_intent_stub
):
    await _mark_authorized(reservation["_id"])

    resp = await client.post(f"/reservations/{reservation['_id']}/decline", headers=_auth(verified_host))

    assert resp.status_code == 200
    assert resp.json()["paymentStatus"] == "canceled"
    stripe_payment_intent_stub.cancel.assert_called_once_with("pi_test_fake")


async def test_delete_pending_reservation_releases_authorization(
    client, registered_renter, reservation, stripe_payment_intent_stub
):
    await _mark_authorized(reservation["_id"])

    resp = await client.delete(f"/reservations/{reservation['_id']}", headers=_auth(registered_renter))

    assert resp.status_code == 204
    stripe_payment_intent_stub.cancel.assert_called_once_with("pi_test_fake")


async def test_delete_confirmed_reservation_is_refused(
    client, verified_host, registered_renter, reservation, stripe_payment_intent_stub
):
    """A confirmed booking has captured money behind it — DELETE now 409s
    and points at POST /{id}/cancel (the refund path). Covered end-to-end in
    test_reservation_cancel.py."""
    await _mark_authorized(reservation["_id"])
    approve = await client.post(f"/reservations/{reservation['_id']}/approve", headers=_auth(verified_host))
    assert approve.status_code == 200
    stripe_payment_intent_stub.capture.assert_called_once()

    resp = await client.delete(f"/reservations/{reservation['_id']}", headers=_auth(registered_renter))

    assert resp.status_code == 409
    stripe_payment_intent_stub.cancel.assert_not_called()
    db = get_db()
    assert await db.reservations.find_one({"_id": reservation["_id"]}) is not None
