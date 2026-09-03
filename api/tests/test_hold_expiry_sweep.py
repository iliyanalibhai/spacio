"""24-hour reservation hold expiry sweep (app/services/hold_expiry.py).

Calls expire_stale_holds directly against the test database rather than
through the FastAPI app/lifespan: the ASGI test client's transport never
triggers lifespan events (see conftest.py's clean_database fixture, which
has to call ensure_indexes() itself for the same reason), so the
background task started there never actually runs during tests anyway.
That's fine — the sweep logic itself is a plain async function precisely so
it can be tested this way, independent of the scheduling loop around it.
"""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import stripe

from app.db import get_db
from app.services.hold_expiry import expire_stale_holds


def _auth(user):
    return {"Authorization": f"Bearer {user['token']}"}


@pytest.fixture
def stripe_payment_intent_stub(monkeypatch):
    cancel = MagicMock()
    monkeypatch.setattr(stripe.PaymentIntent, "cancel", cancel)
    return SimpleNamespace(cancel=cancel)


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


async def _backdate_hold(reservation_id: str, *, hours_ago: int) -> None:
    db = get_db()
    await db.reservations.update_one(
        {"_id": reservation_id},
        {"$set": {"holdExpiresAt": datetime.utcnow() - timedelta(hours=hours_ago)}},
    )


async def test_expires_a_stale_pending_hold(client, reservation):
    await _backdate_hold(reservation["_id"], hours_ago=1)

    db = get_db()
    count = await expire_stale_holds(db)

    assert count == 1
    stored = await db.reservations.find_one({"_id": reservation["_id"]})
    assert stored["status"] == "expired"
    # No payment was ever authorized — releasing it is a no-op that still
    # marks paymentStatus canceled, same semantics as declining unpaid.
    assert stored["paymentStatus"] == "canceled"


async def test_leaves_a_fresh_hold_alone(client, reservation):
    db = get_db()
    count = await expire_stale_holds(db)

    assert count == 0
    stored = await db.reservations.find_one({"_id": reservation["_id"]})
    assert stored["status"] == "pending_host_confirmation"


async def test_releases_an_authorized_payment(client, reservation, stripe_payment_intent_stub):
    db = get_db()
    await db.reservations.update_one(
        {"_id": reservation["_id"]},
        {"$set": {"paymentStatus": "authorized", "stripePaymentIntentId": "pi_test_fake"}},
    )
    await _backdate_hold(reservation["_id"], hours_ago=1)

    count = await expire_stale_holds(db)

    assert count == 1
    stripe_payment_intent_stub.cancel.assert_called_once_with("pi_test_fake")
    stored = await db.reservations.find_one({"_id": reservation["_id"]})
    assert stored["paymentStatus"] == "canceled"


async def test_does_not_touch_confirmed_reservations(client, reservation):
    db = get_db()
    await db.reservations.update_one(
        {"_id": reservation["_id"]}, {"$set": {"status": "confirmed", "paymentStatus": "captured"}}
    )
    await _backdate_hold(reservation["_id"], hours_ago=1)

    count = await expire_stale_holds(db)

    assert count == 0
    stored = await db.reservations.find_one({"_id": reservation["_id"]})
    assert stored["status"] == "confirmed"


async def test_expires_multiple_stale_holds_in_one_pass(client, registered_renter, listing):
    ids = []
    for start, end in [("2026-02-01", "2026-02-05"), ("2026-03-01", "2026-03-05")]:
        resp = await client.post(
            "/reservations/",
            headers=_auth(registered_renter),
            json={"listingId": listing["_id"], "startDate": start, "endDate": end, "sqftRequested": 20},
        )
        ids.append(resp.json()["_id"])
        await _backdate_hold(resp.json()["_id"], hours_ago=1)

    db = get_db()
    count = await expire_stale_holds(db)

    assert count == 2
    for reservation_id in ids:
        stored = await db.reservations.find_one({"_id": reservation_id})
        assert stored["status"] == "expired"
