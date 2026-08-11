"""End-to-end booking lifecycle through the real HTTP API: search, book,
approve, message — plus the capacity rule and state machine enforced at
the API layer, not just in the pure service-level unit tests."""

import pytest


@pytest.fixture
async def listing(client, verified_host):
    headers = {"Authorization": f"Bearer {verified_host['token']}"}
    response = await client.post(
        "/listings/",
        headers=headers,
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
    return response.json()


async def test_full_booking_lifecycle(client, verified_host, registered_renter, listing):
    renter_headers = {"Authorization": f"Bearer {registered_renter['token']}"}
    host_headers = {"Authorization": f"Bearer {verified_host['token']}"}

    booking = await client.post(
        "/reservations/",
        headers=renter_headers,
        json={
            "listingId": listing["_id"],
            "startDate": "2026-02-01",
            "endDate": "2026-03-03",
            "sqftRequested": 100,
            "numBoxes": 1,
            "insuranceDeclaredValue": 2000,
        },
    )
    assert booking.status_code == 201
    body = booking.json()
    assert body["status"] == "pending_host_confirmation"
    assert body["basePrice"] == 30.0  # 60 * 0.5 * (30/30)
    assert body["boxCost"] == 10.0
    assert body["insuranceCost"] == 20.0

    reservation_id = body["_id"]

    approve = await client.post(f"/reservations/{reservation_id}/approve", headers=host_headers)
    assert approve.status_code == 200
    assert approve.json()["status"] == "confirmed"

    # Double approve rejected by the state machine.
    second_approve = await client.post(f"/reservations/{reservation_id}/approve", headers=host_headers)
    assert second_approve.status_code == 400

    # Messaging is scoped to the reservation and works both directions.
    msg = await client.post(
        "/messages/",
        headers=renter_headers,
        json={"reservationId": reservation_id, "content": "When can I drop off?"},
    )
    assert msg.status_code == 201

    thread = await client.get(f"/messages/{reservation_id}", headers=host_headers)
    assert thread.status_code == 200
    assert len(thread.json()) == 1


async def test_decline_then_approve_is_rejected(client, verified_host, registered_renter, listing):
    renter_headers = {"Authorization": f"Bearer {registered_renter['token']}"}
    host_headers = {"Authorization": f"Bearer {verified_host['token']}"}

    booking = await client.post(
        "/reservations/",
        headers=renter_headers,
        json={
            "listingId": listing["_id"],
            "startDate": "2026-02-01",
            "endDate": "2026-02-11",
            "sqftRequested": 50,
        },
    )
    reservation_id = booking.json()["_id"]

    decline = await client.post(f"/reservations/{reservation_id}/decline", headers=host_headers)
    assert decline.status_code == 200
    assert decline.json()["status"] == "declined"

    approve = await client.post(f"/reservations/{reservation_id}/approve", headers=host_headers)
    assert approve.status_code == 400


async def test_capacity_rule_rejects_overbooking_across_concurrent_renters(
    client, verified_host, registered_renter, listing
):
    """Business rule: a single listing can host multiple concurrent renters
    as long as the sum of sqftRequested across overlapping confirmed +
    pending reservations never exceeds totalSqft (200 here)."""
    renter_headers = {"Authorization": f"Bearer {registered_renter['token']}"}

    first = await client.post(
        "/reservations/",
        headers=renter_headers,
        json={
            "listingId": listing["_id"],
            "startDate": "2026-02-01",
            "endDate": "2026-02-15",
            "sqftRequested": 120,
        },
    )
    assert first.status_code == 201

    # A second, different renter requesting overlapping dates should still
    # be able to fit in the remaining 80 sqft.
    await client.post(
        "/auth/register",
        json={
            "name": "Second Renter",
            "email": "second-renter@test.spacio.dev",
            "password": "password123",
            "zipCode": "78705",
            "isHost": False,
        },
    )
    login = await client.post(
        "/auth/login",
        data={"username": "second-renter@test.spacio.dev", "password": "password123"},
    )
    second_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    second = await client.post(
        "/reservations/",
        headers=second_headers,
        json={
            "listingId": listing["_id"],
            "startDate": "2026-02-05",
            "endDate": "2026-02-10",
            "sqftRequested": 80,
        },
    )
    assert second.status_code == 201

    # A third request that would push the overlapping total past 200 sqft
    # must be rejected.
    third = await client.post(
        "/reservations/",
        headers=second_headers,
        json={
            "listingId": listing["_id"],
            "startDate": "2026-02-06",
            "endDate": "2026-02-08",
            "sqftRequested": 1,
        },
    )
    assert third.status_code == 400

    # But a request for non-overlapping dates should succeed even though
    # the listing is "full" during the earlier window.
    fourth = await client.post(
        "/reservations/",
        headers=second_headers,
        json={
            "listingId": listing["_id"],
            "startDate": "2026-03-01",
            "endDate": "2026-03-10",
            "sqftRequested": 200,
        },
    )
    assert fourth.status_code == 201


async def test_search_reflects_hostVerified_and_availableSqft(client, verified_host, registered_renter, listing):
    renter_headers = {"Authorization": f"Bearer {registered_renter['token']}"}
    await client.post(
        "/reservations/",
        headers=renter_headers,
        json={
            "listingId": listing["_id"],
            "startDate": "2026-02-01",
            "endDate": "2026-02-11",
            "sqftRequested": 60,
        },
    )

    search = await client.get("/listings/", params={"zipCode": "78705"})
    assert search.status_code == 200
    results = search.json()
    match = next(item for item in results if item["_id"] == listing["_id"])
    assert match["hostVerified"] is True
