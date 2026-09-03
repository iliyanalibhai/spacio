"""Review system (Phase 4): POST /reviews/, GET /reviews/listing/{id},
GET /reviews/reservation/{id}, and the listing rating/reviewCount
recompute on write. Eligibility rules themselves (confirmed + stay ended +
own reservation) are unit-tested in test_review_eligibility.py; this file
covers the endpoints end-to-end through the real HTTP API."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import stripe

from app.db import get_db

WEBHOOK_PATH = "/payments/webhook"


def _auth(user):
    return {"Authorization": f"Bearer {user['token']}"}


@pytest.fixture
def stripe_payment_intent_stub(monkeypatch):
    capture = MagicMock()
    monkeypatch.setattr(stripe.PaymentIntent, "capture", capture)
    return SimpleNamespace(capture=capture)


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


async def _book_and_confirm(
    client, verified_host, registered_renter, listing, stripe_payment_intent_stub, *, start, end
) -> str:
    """Book, mark the payment authorized, approve (real capture call is
    mocked), and backdate the stay into the past so it's review-eligible.
    Returns the reservation id."""
    booking = await client.post(
        "/reservations/",
        headers=_auth(registered_renter),
        json={"listingId": listing["_id"], "startDate": start, "endDate": end, "sqftRequested": 20},
    )
    reservation_id = booking.json()["_id"]

    db = get_db()
    await db.reservations.update_one(
        {"_id": reservation_id},
        {"$set": {"paymentStatus": "authorized", "stripePaymentIntentId": "pi_test_fake"}},
    )
    approve = await client.post(f"/reservations/{reservation_id}/approve", headers=_auth(verified_host))
    assert approve.status_code == 200

    await db.reservations.update_one(
        {"_id": reservation_id}, {"$set": {"endDate": datetime.utcnow() - timedelta(days=1)}}
    )
    return reservation_id


@pytest.fixture
async def confirmed_ended_reservation(
    client, verified_host, registered_renter, listing, stripe_payment_intent_stub
):
    return await _book_and_confirm(
        client,
        verified_host,
        registered_renter,
        listing,
        stripe_payment_intent_stub,
        start="2026-02-01",
        end="2026-02-11",
    )


async def test_create_review_sets_listing_rating(
    client, registered_renter, listing, confirmed_ended_reservation
):
    resp = await client.post(
        "/reviews/",
        headers=_auth(registered_renter),
        json={"reservationId": confirmed_ended_reservation, "rating": 5, "comment": "Great space!"},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["rating"] == 5
    assert body["comment"] == "Great space!"
    assert body["listingId"] == listing["_id"]

    listing_resp = await client.get(f"/listings/{listing['_id']}")
    assert listing_resp.status_code == 200
    listing_body = listing_resp.json()
    assert listing_body["rating"] == 5.0
    assert listing_body["reviewCount"] == 1


async def test_rating_is_the_average_across_reviews(
    client, verified_host, registered_renter, listing, stripe_payment_intent_stub
):
    first = await _book_and_confirm(
        client, verified_host, registered_renter, listing, stripe_payment_intent_stub,
        start="2026-02-01", end="2026-02-05",
    )
    second = await _book_and_confirm(
        client, verified_host, registered_renter, listing, stripe_payment_intent_stub,
        start="2026-03-01", end="2026-03-05",
    )

    await client.post("/reviews/", headers=_auth(registered_renter), json={"reservationId": first, "rating": 5})
    await client.post("/reviews/", headers=_auth(registered_renter), json={"reservationId": second, "rating": 3})

    listing_resp = await client.get(f"/listings/{listing['_id']}")
    body = listing_resp.json()
    assert body["rating"] == 4.0
    assert body["reviewCount"] == 2


async def test_cannot_review_the_same_reservation_twice(
    client, registered_renter, confirmed_ended_reservation
):
    first = await client.post(
        "/reviews/", headers=_auth(registered_renter), json={"reservationId": confirmed_ended_reservation, "rating": 4}
    )
    assert first.status_code == 201

    second = await client.post(
        "/reviews/", headers=_auth(registered_renter), json={"reservationId": confirmed_ended_reservation, "rating": 2}
    )
    assert second.status_code == 400


async def test_cannot_review_before_the_stay_ends(
    client, verified_host, registered_renter, listing, stripe_payment_intent_stub
):
    booking = await client.post(
        "/reservations/",
        headers=_auth(registered_renter),
        json={"listingId": listing["_id"], "startDate": "2026-02-01", "endDate": "2026-02-11", "sqftRequested": 20},
    )
    reservation_id = booking.json()["_id"]
    db = get_db()
    await db.reservations.update_one(
        {"_id": reservation_id},
        {"$set": {"paymentStatus": "authorized", "stripePaymentIntentId": "pi_test_fake"}},
    )
    await client.post(f"/reservations/{reservation_id}/approve", headers=_auth(verified_host))
    # endDate left in the future (default reservation_pricing fixture dates
    # are already in the past by wall-clock time in this environment, so
    # push it forward explicitly to actually exercise the "not yet" path).
    await db.reservations.update_one(
        {"_id": reservation_id}, {"$set": {"endDate": datetime.utcnow() + timedelta(days=1)}}
    )

    resp = await client.post("/reviews/", headers=_auth(registered_renter), json={"reservationId": reservation_id, "rating": 5})

    assert resp.status_code == 400


async def test_cannot_review_a_reservation_that_was_never_confirmed(
    client, registered_renter, listing
):
    booking = await client.post(
        "/reservations/",
        headers=_auth(registered_renter),
        json={"listingId": listing["_id"], "startDate": "2026-02-01", "endDate": "2026-02-11", "sqftRequested": 20},
    )
    reservation_id = booking.json()["_id"]

    resp = await client.post("/reviews/", headers=_auth(registered_renter), json={"reservationId": reservation_id, "rating": 5})

    assert resp.status_code == 400


async def test_cannot_review_someone_elses_reservation(client, confirmed_ended_reservation):
    await client.post(
        "/auth/register",
        json={
            "name": "Other Renter",
            "email": "other-review-renter@test.spacio.dev",
            "password": "password123",
            "zipCode": "78705",
            "isHost": False,
        },
    )
    login = await client.post(
        "/auth/login", data={"username": "other-review-renter@test.spacio.dev", "password": "password123"}
    )
    other_headers = {"Authorization": f"Bearer {login.cookies['access_token']}"}

    resp = await client.post(
        "/reviews/", headers=other_headers, json={"reservationId": confirmed_ended_reservation, "rating": 1}
    )

    assert resp.status_code == 400


async def test_get_reservation_review_is_null_until_reviewed(
    client, registered_renter, confirmed_ended_reservation
):
    before = await client.get(
        f"/reviews/reservation/{confirmed_ended_reservation}", headers=_auth(registered_renter)
    )
    assert before.status_code == 200
    assert before.json() is None

    await client.post(
        "/reviews/", headers=_auth(registered_renter), json={"reservationId": confirmed_ended_reservation, "rating": 4}
    )

    after = await client.get(
        f"/reviews/reservation/{confirmed_ended_reservation}", headers=_auth(registered_renter)
    )
    assert after.status_code == 200
    assert after.json()["rating"] == 4


async def test_get_reservation_review_forbidden_for_unrelated_user(client, confirmed_ended_reservation):
    await client.post(
        "/auth/register",
        json={
            "name": "Bystander",
            "email": "bystander@test.spacio.dev",
            "password": "password123",
            "zipCode": "78705",
            "isHost": False,
        },
    )
    login = await client.post("/auth/login", data={"username": "bystander@test.spacio.dev", "password": "password123"})
    headers = {"Authorization": f"Bearer {login.cookies['access_token']}"}

    resp = await client.get(f"/reviews/reservation/{confirmed_ended_reservation}", headers=headers)

    assert resp.status_code == 403


async def test_listing_reviews_endpoint_is_public(client, listing, registered_renter, confirmed_ended_reservation):
    await client.post(
        "/reviews/", headers=_auth(registered_renter), json={"reservationId": confirmed_ended_reservation, "rating": 5}
    )

    resp = await client.get(f"/reviews/listing/{listing['_id']}")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["rating"] == 5
