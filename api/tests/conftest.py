"""Test configuration.

Sets test-only environment variables *before* app.core.config is ever
imported (settings are read once, at import time, via lru_cache), then
provides fixtures for an isolated test database and an HTTP client wired
directly to the ASGI app (no real network socket needed).

Integration tests require a real MongoDB reachable at MONGODB_URI (default
mongodb://localhost:27017) — see README for how to bring one up locally or
via docker-compose. The pure business-logic tests (pricing, capacity,
reservation state) don't touch the database at all.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_NAME", "spacio_test")
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db import ensure_indexes, get_db


@pytest_asyncio.fixture
async def clean_database():
    """Wipe every collection in the test database before each test.

    Not autouse: only tests that actually need a database (via the
    `client` fixture, which depends on this one) pay the cost of a Mongo
    round trip. Pure business-logic tests never touch this fixture.
    """
    db = get_db()
    for name in await db.list_collection_names():
        await db[name].delete_many({})
    # httpx's ASGITransport doesn't trigger FastAPI's lifespan startup
    # event (which is what normally calls this in production), so tests
    # would otherwise run against a database with no unique index on
    # users.email and silently miss the duplicate-registration bug this
    # index exists to prevent.
    await ensure_indexes()
    yield


@pytest_asyncio.fixture
async def client(clean_database):
    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def registered_host(client):
    payload = {
        "name": "Test Host",
        "email": "host@test.spacio.dev",
        "password": "password123",
        "zipCode": "78705",
        "isHost": True,
    }
    await client.post("/auth/register", json=payload)
    login = await client.post(
        "/auth/login",
        data={"username": payload["email"], "password": payload["password"]},
    )
    token = login.json()["access_token"]
    return {"email": payload["email"], "token": token}


@pytest_asyncio.fixture
async def verified_host(registered_host):
    from app.db import get_db

    db = get_db()
    await db.users.update_one(
        {"email": registered_host["email"]}, {"$set": {"verificationStatus": "verified"}}
    )
    return registered_host


@pytest_asyncio.fixture
async def registered_renter(client):
    payload = {
        "name": "Test Renter",
        "email": "renter@test.spacio.dev",
        "password": "password123",
        "zipCode": "78705",
        "isHost": False,
    }
    await client.post("/auth/register", json=payload)
    login = await client.post(
        "/auth/login",
        data={"username": payload["email"], "password": payload["password"]},
    )
    token = login.json()["access_token"]
    return {"email": payload["email"], "token": token}
