"""Tests for rate limiting on /auth/login and /pricing/suggest — closes the
Tier 2 issue where both endpoints had no limit, leaving login open to
credential-stuffing/brute-force and pricing/suggest open to scraping/abuse.
See docs/DOCUMENTATION.md §7.
"""


async def test_login_is_rate_limited_after_five_attempts_per_minute(client):
    # Deliberately wrong password: the limiter counts requests regardless of
    # outcome, and using a bad password avoids depending on a registered user.
    payload = {"username": "nobody@test.spacio.dev", "password": "wrong"}
    for _ in range(5):
        response = await client.post("/auth/login", data=payload)
        assert response.status_code == 400  # under the limit: normal auth failure

    sixth = await client.post("/auth/login", data=payload)
    assert sixth.status_code == 429


async def test_pricing_suggest_is_rate_limited_after_twenty_per_minute(client):
    payload = {"size": "M", "zipCode": "78705", "indoor": True}
    for _ in range(20):
        response = await client.post("/pricing/suggest", json=payload)
        assert response.status_code == 200

    over_limit = await client.post("/pricing/suggest", json=payload)
    assert over_limit.status_code == 429


async def test_login_rate_limit_is_scoped_separately_from_pricing_suggest(client):
    """Each @limiter.limit(...) is tracked as its own bucket keyed by
    (endpoint, caller) — hitting one endpoint's limit shouldn't affect the
    other's, since they protect against different abuse (brute force vs.
    scraping) and share nothing but the caller's IP."""
    login_payload = {"username": "nobody@test.spacio.dev", "password": "wrong"}
    for _ in range(5):
        await client.post("/auth/login", data=login_payload)
    limited = await client.post("/auth/login", data=login_payload)
    assert limited.status_code == 429

    pricing_payload = {"size": "M", "zipCode": "78705", "indoor": True}
    still_allowed = await client.post("/pricing/suggest", json=pricing_payload)
    assert still_allowed.status_code == 200
