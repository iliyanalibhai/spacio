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
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test_do_not_use_in_prod"
os.environ["STRIPE_PAYMENTS_WEBHOOK_SECRET"] = "whsec_payments_test_do_not_use_in_prod"
# A non-empty (dummy) secret key so settings.stripe_configured is True and
# the payment endpoints take their real branch instead of returning 503.
# No real Stripe HTTP call is ever made in tests — every stripe.*.create /
# retrieve / capture / transfer is monkeypatched, and stripe.Webhook.
# construct_event only needs the webhook signing secret above. Tests that
# want the "Stripe not configured" path monkeypatch settings.stripe_secret_key
# to "".
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_dummy_not_a_real_key")
# Keep the sentence-transformers model out of the default test run (no
# ~90 MB download, no ~1 s load, no torch import). Only test_matching.py's
# real-model cases opt back in — its `real_embeddings` fixture flips
# settings.embeddings_enabled True for the duration of the test. Everything
# else exercises the non-semantic fallback path in /matching/recommend.
os.environ.setdefault("EMBEDDINGS_ENABLED", "false")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db import ensure_indexes, get_db
from app.deps.auth import ACCESS_TOKEN_COOKIE


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

    # slowapi's Limiter keeps its hit counts in an in-memory store that
    # lives for the whole pytest process (it's attached to the app, which is
    # a module-level singleton), not per-request or per-test. Without this
    # reset, tests that log in more than a handful of times across the whole
    # suite start tripping the real /auth/login rate limit and fail with
    # unrelated-looking errors.
    app.state.limiter.reset()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _register_and_get_token(client, payload: dict) -> str:
    """Register, log in, and return the raw JWT — pulled off the Set-Cookie
    header (`login.cookies`), not a JSON body field, since /auth/login no
    longer returns the token in the body (it's httpOnly-cookie-only now, see
    docs/DOCUMENTATION.md §7). Tests still use it as a Bearer header (rather
    than relying on the shared client's cookie jar) because several tests
    need two authenticated identities live at once on one `client` instance
    — a single cookie jar can only hold one session at a time, but headers
    can carry as many identities as a test needs.
    """
    await client.post("/auth/register", json=payload)
    login = await client.post(
        "/auth/login",
        data={"username": payload["email"], "password": payload["password"]},
    )
    token = login.cookies[ACCESS_TOKEN_COOKIE]
    # Drop the cookie the login above just set on the shared client so it
    # doesn't leak into later requests in the same test that forget to pass
    # an explicit Authorization header — auth in these tests should always
    # be explicit about which identity is acting.
    client.cookies.clear()
    return token


@pytest_asyncio.fixture
async def registered_host(client):
    payload = {
        "name": "Test Host",
        "email": "host@test.spacio.dev",
        "password": "password123",
        "zipCode": "78705",
        "isHost": True,
    }
    token = await _register_and_get_token(client, payload)
    return {"email": payload["email"], "token": token}


@pytest_asyncio.fixture
async def verified_host(registered_host):
    """A host who has cleared both gates the create-listing endpoint checks:
    Stripe Identity verification and Stripe Connect payout onboarding. Both
    are set directly in Mongo (same shortcut seed.py uses) so listing/booking
    tests don't have to drive the real Stripe redirect flows."""
    from app.db import get_db

    db = get_db()
    await db.users.update_one(
        {"email": registered_host["email"]},
        {
            "$set": {
                "verificationStatus": "verified",
                "stripeConnectAccountId": "acct_test_verified_host",
                "stripeConnectOnboarded": True,
            }
        },
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
    token = await _register_and_get_token(client, payload)
    return {"email": payload["email"], "token": token}
