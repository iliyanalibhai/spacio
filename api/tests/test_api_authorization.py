"""Authorization checks on protected routes, exercised through real HTTP
requests against the ASGI app with a real (test) MongoDB behind it."""

import pytest


async def test_protected_route_requires_token(client):
    response = await client.get("/auth/me")
    assert response.status_code == 401


async def test_invalid_token_is_rejected(client):
    response = await client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


async def test_register_then_me_roundtrip(client):
    payload = {
        "name": "Jane",
        "email": "jane@test.spacio.dev",
        "password": "password123",
        "zipCode": "78705",
        "isHost": False,
    }
    register = await client.post("/auth/register", json=payload)
    assert register.status_code == 201

    login = await client.post(
        "/auth/login", data={"username": payload["email"], "password": payload["password"]}
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == payload["email"]


async def test_duplicate_email_registration_rejected(client):
    payload = {
        "name": "Jane",
        "email": "dupe@test.spacio.dev",
        "password": "password123",
        "zipCode": "78705",
        "isHost": False,
    }
    first = await client.post("/auth/register", json=payload)
    assert first.status_code == 201
    second = await client.post("/auth/register", json=payload)
    assert second.status_code == 400


async def test_non_host_cannot_create_listing(client, registered_renter):
    headers = {"Authorization": f"Bearer {registered_renter['token']}"}
    response = await client.post(
        "/listings/",
        headers=headers,
        json={
            "title": "Test",
            "description": "Test",
            "size": "M",
            "sizeSqft": 100,
            "pricePerMonth": 40,
            "addressSummary": "Austin, TX",
            "zipCode": "78705",
            "availableFrom": "2026-01-01",
            "availableTo": "2026-12-31",
        },
    )
    assert response.status_code == 403


async def test_unverified_host_cannot_create_listing(client, registered_host):
    """The Stripe Identity gate: hosts must be verified before publishing."""
    headers = {"Authorization": f"Bearer {registered_host['token']}"}
    response = await client.post(
        "/listings/",
        headers=headers,
        json={
            "title": "Test",
            "description": "Test",
            "size": "M",
            "sizeSqft": 100,
            "pricePerMonth": 40,
            "addressSummary": "Austin, TX",
            "zipCode": "78705",
            "availableFrom": "2026-01-01",
            "availableTo": "2026-12-31",
        },
    )
    assert response.status_code == 403
    assert "verify your identity" in response.json()["detail"]


async def test_verified_host_can_create_listing(client, verified_host):
    headers = {"Authorization": f"Bearer {verified_host['token']}"}
    response = await client.post(
        "/listings/",
        headers=headers,
        json={
            "title": "Test",
            "description": "Test",
            "size": "M",
            "sizeSqft": 100,
            "pricePerMonth": 40,
            "addressSummary": "Austin, TX",
            "zipCode": "78705",
            "availableFrom": "2026-01-01",
            "availableTo": "2026-12-31",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["rating"] is None  # no fabricated default rating


async def test_new_listing_has_no_fabricated_rating(client, verified_host):
    headers = {"Authorization": f"Bearer {verified_host['token']}"}
    response = await client.post(
        "/listings/",
        headers=headers,
        json={
            "title": "Test",
            "description": "Test",
            "size": "S",
            "sizeSqft": 40,
            "pricePerMonth": 28,
            "addressSummary": "Austin, TX",
            "zipCode": "78705",
            "availableFrom": "2026-01-01",
            "availableTo": "2026-12-31",
        },
    )
    assert response.json()["rating"] is None


@pytest.fixture
async def other_hosts_listing(client, verified_host):
    headers = {"Authorization": f"Bearer {verified_host['token']}"}
    response = await client.post(
        "/listings/",
        headers=headers,
        json={
            "title": "Garage",
            "description": "Garage",
            "size": "M",
            "sizeSqft": 100,
            "pricePerMonth": 40,
            "addressSummary": "Austin, TX",
            "zipCode": "78705",
            "availableFrom": "2026-01-01",
            "availableTo": "2026-12-31",
        },
    )
    return response.json()


async def test_host_cannot_edit_another_hosts_listing(client, verified_host, registered_renter, other_hosts_listing):
    # Make the renter a second (unrelated) verified host and try to edit
    # the first host's listing.
    from app.db import get_db

    db = get_db()
    await db.users.update_one(
        {"email": registered_renter["email"]},
        {"$set": {"isHost": True, "verificationStatus": "verified"}},
    )
    headers = {"Authorization": f"Bearer {registered_renter['token']}"}
    response = await client.patch(
        f"/listings/{other_hosts_listing['_id']}", headers=headers, json={"pricePerMonth": 999}
    )
    assert response.status_code == 403


async def test_cannot_rent_own_listing(client, verified_host, other_hosts_listing):
    headers = {"Authorization": f"Bearer {verified_host['token']}"}
    response = await client.post(
        "/reservations/",
        headers=headers,
        json={
            "listingId": other_hosts_listing["_id"],
            "startDate": "2026-02-01",
            "endDate": "2026-02-11",
            "sqftRequested": 50,
        },
    )
    assert response.status_code == 400


async def test_cannot_message_reservation_you_are_not_part_of(client, verified_host, registered_renter, other_hosts_listing):
    renter_headers = {"Authorization": f"Bearer {registered_renter['token']}"}
    booking = await client.post(
        "/reservations/",
        headers=renter_headers,
        json={
            "listingId": other_hosts_listing["_id"],
            "startDate": "2026-02-01",
            "endDate": "2026-02-11",
            "sqftRequested": 50,
        },
    )
    reservation_id = booking.json()["_id"]

    # A third, unrelated user should not be able to read or send messages.
    await client.post(
        "/auth/register",
        json={
            "name": "Stranger",
            "email": "stranger@test.spacio.dev",
            "password": "password123",
            "zipCode": "78705",
            "isHost": False,
        },
    )
    login = await client.post(
        "/auth/login",
        data={"username": "stranger@test.spacio.dev", "password": "password123"},
    )
    stranger_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    read = await client.get(f"/messages/{reservation_id}", headers=stranger_headers)
    assert read.status_code == 403

    send = await client.post(
        "/messages/",
        headers=stranger_headers,
        json={"reservationId": reservation_id, "content": "hi"},
    )
    assert send.status_code == 403


async def test_only_listing_host_can_approve_reservation(client, verified_host, registered_renter, other_hosts_listing):
    renter_headers = {"Authorization": f"Bearer {registered_renter['token']}"}
    booking = await client.post(
        "/reservations/",
        headers=renter_headers,
        json={
            "listingId": other_hosts_listing["_id"],
            "startDate": "2026-02-01",
            "endDate": "2026-02-11",
            "sqftRequested": 50,
        },
    )
    reservation_id = booking.json()["_id"]

    # Renter (not the host) tries to approve their own reservation.
    response = await client.post(f"/reservations/{reservation_id}/approve", headers=renter_headers)
    assert response.status_code == 403
