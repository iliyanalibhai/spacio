"""Renter-initiated cancellation: POST /reservations/{id}/cancel.

Covers the pre-approval path (release the hold, like a decline) and the
post-approval path (tiered Stripe refund on a captured payment), plus the
tightened DELETE that now refuses a confirmed reservation. The refund
*amounts* per tier are unit-tested in test_refund_policy.py; here we check
the endpoint wires the decision to Stripe and the stored status correctly.
"""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import stripe

from app.db import get_db


def _auth(user):
    return {"Authorization": f"Bearer {user['token']}"}


@pytest.fixture
def stripe_stub(monkeypatch):
    capture = MagicMock()
    cancel = MagicMock()
    refund = MagicMock()
    monkeypatch.setattr(stripe.PaymentIntent, "capture", capture)
    monkeypatch.setattr(stripe.PaymentIntent, "cancel", cancel)
    monkeypatch.setattr(stripe.Refund, "create", refund)
    return SimpleNamespace(capture=capture, cancel=cancel, refund=refund)


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
            "availableTo": "2027-12-31",
        },
    )
    return resp.json()


async def _make_reservation(client, renter, listing, *, starts_in_days: int) -> dict:
    # Reservation start/end are stored as UTC midnight, and the refund
    # policy compares against datetime.utcnow() — so anchor on the UTC date,
    # not the local one, or a "2 days out" booking can land in the past.
    start = datetime.utcnow().date() + timedelta(days=starts_in_days)
    end = start + timedelta(days=10)
    resp = await client.post(
        "/reservations/",
        headers=_auth(renter),
        json={
            "listingId": listing["_id"],
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "sqftRequested": 50,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _capture(client, verified_host, renter, listing, *, starts_in_days: int, stub) -> dict:
    """Return a reservation that a host has approved (paymentStatus captured)."""
    reservation = await _make_reservation(client, renter, listing, starts_in_days=starts_in_days)
    db = get_db()
    await db.reservations.update_one(
        {"_id": reservation["_id"]},
        {"$set": {"paymentStatus": "authorized", "stripePaymentIntentId": "pi_test_fake"}},
    )
    approve = await client.post(
        f"/reservations/{reservation['_id']}/approve", headers=_auth(verified_host)
    )
    assert approve.status_code == 200, approve.text
    return approve.json()


async def test_cancel_before_approval_releases_the_hold(
    client, registered_renter, listing, stripe_stub
):
    reservation = await _make_reservation(client, registered_renter, listing, starts_in_days=30)
    db = get_db()
    await db.reservations.update_one(
        {"_id": reservation["_id"]},
        {"$set": {"paymentStatus": "authorized", "stripePaymentIntentId": "pi_test_fake"}},
    )

    resp = await client.post(
        f"/reservations/{reservation['_id']}/cancel", headers=_auth(registered_renter)
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "cancelled"
    assert body["paymentStatus"] == "canceled"
    stripe_stub.cancel.assert_called_once_with("pi_test_fake")
    stripe_stub.refund.assert_not_called()


async def test_cancel_far_ahead_gives_a_full_refund(
    client, verified_host, registered_renter, listing, stripe_stub
):
    reservation = await _capture(
        client, verified_host, registered_renter, listing, starts_in_days=30, stub=stripe_stub
    )
    total_cents = round(reservation["totalPrice"] * 100)

    resp = await client.post(
        f"/reservations/{reservation['_id']}/cancel", headers=_auth(registered_renter)
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "cancelled"
    assert body["paymentStatus"] == "refunded"
    assert body["refundedAmount"] == reservation["totalPrice"]

    _, kwargs = stripe_stub.refund.call_args
    assert kwargs["payment_intent"] == "pi_test_fake"
    assert kwargs["amount"] == total_cents
    assert kwargs["refund_application_fee"] is True
    assert kwargs["reverse_transfer"] is True


async def test_cancel_inside_72h_gives_a_half_refund(
    client, verified_host, registered_renter, listing, stripe_stub
):
    # ~48h out: inside the 72h window, so a half refund.
    reservation = await _capture(
        client, verified_host, registered_renter, listing, starts_in_days=2, stub=stripe_stub
    )
    half_cents = round(reservation["totalPrice"] * 0.5 * 100)

    resp = await client.post(
        f"/reservations/{reservation['_id']}/cancel", headers=_auth(registered_renter)
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["paymentStatus"] == "partially_refunded"
    assert body["refundedAmount"] == half_cents / 100
    _, kwargs = stripe_stub.refund.call_args
    assert kwargs["amount"] == half_cents


async def test_cancel_frees_capacity_for_a_new_booking(
    client, verified_host, registered_renter, listing, stripe_stub
):
    # 50 of 200 sqft taken, then cancelled -> a later 200-sqft booking fits.
    reservation = await _capture(
        client, verified_host, registered_renter, listing, starts_in_days=40, stub=stripe_stub
    )
    await client.post(
        f"/reservations/{reservation['_id']}/cancel", headers=_auth(registered_renter)
    )

    start = datetime.utcnow().date() + timedelta(days=40)
    resp = await client.post(
        "/reservations/",
        headers=_auth(registered_renter),
        json={
            "listingId": listing["_id"],
            "startDate": start.isoformat(),
            "endDate": (start + timedelta(days=10)).isoformat(),
            "sqftRequested": 200,
        },
    )
    assert resp.status_code == 201, resp.text


async def test_only_the_renter_can_cancel(
    client, verified_host, registered_renter, listing, stripe_stub
):
    reservation = await _capture(
        client, verified_host, registered_renter, listing, starts_in_days=30, stub=stripe_stub
    )

    resp = await client.post(
        f"/reservations/{reservation['_id']}/cancel", headers=_auth(verified_host)
    )

    assert resp.status_code == 403
    stripe_stub.refund.assert_not_called()


async def test_cannot_cancel_twice(
    client, verified_host, registered_renter, listing, stripe_stub
):
    reservation = await _capture(
        client, verified_host, registered_renter, listing, starts_in_days=30, stub=stripe_stub
    )
    first = await client.post(
        f"/reservations/{reservation['_id']}/cancel", headers=_auth(registered_renter)
    )
    assert first.status_code == 200

    second = await client.post(
        f"/reservations/{reservation['_id']}/cancel", headers=_auth(registered_renter)
    )
    assert second.status_code == 400
    stripe_stub.refund.assert_called_once()


async def test_refund_failure_leaves_the_reservation_confirmed(
    client, verified_host, registered_renter, listing, stripe_stub
):
    reservation = await _capture(
        client, verified_host, registered_renter, listing, starts_in_days=30, stub=stripe_stub
    )
    stripe_stub.refund.side_effect = stripe.StripeError("refund declined")

    resp = await client.post(
        f"/reservations/{reservation['_id']}/cancel", headers=_auth(registered_renter)
    )

    assert resp.status_code == 502
    db = get_db()
    stored = await db.reservations.find_one({"_id": reservation["_id"]})
    assert stored["status"] == "confirmed"
    assert stored["paymentStatus"] == "captured"


async def test_delete_now_refuses_a_confirmed_reservation(
    client, verified_host, registered_renter, listing, stripe_stub
):
    reservation = await _capture(
        client, verified_host, registered_renter, listing, starts_in_days=30, stub=stripe_stub
    )

    resp = await client.delete(
        f"/reservations/{reservation['_id']}", headers=_auth(registered_renter)
    )

    assert resp.status_code == 409
    assert "cancel" in resp.json()["detail"].lower()
    db = get_db()
    assert await db.reservations.find_one({"_id": reservation["_id"]}) is not None
