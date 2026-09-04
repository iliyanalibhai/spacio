"""Geographic search over listings — GET /listings with a radius.

Exercises the real $geoNear path against MongoDB: creating a listing geocodes
its ZIP to a point, and a lat/lng (or a geocodable zipCode) turns the search
into a distance-bounded, distance-sorted query.
"""

from __future__ import annotations

import pytest

# ZIP centroids used below (from app/data/zip_centroids.csv):
#   78705 West Campus, Austin       (30.294, -97.739)
#   78751 Hyde Park, Austin         (~2 mi from 78705)
#   75080 Richardson, Dallas metro  (~180 mi from Austin)
AUSTIN_LATLNG = {"lat": 30.2943, "lng": -97.7385}


async def _create_listing(client, token: str, *, zip_code: str, title: str) -> dict:
    resp = await client.post(
        "/listings/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": title,
            "description": "A place to keep things.",
            "size": "M",
            "sizeSqft": 100,
            "pricePerMonth": 100,
            "addressSummary": f"{zip_code} area",
            "zipCode": zip_code,
            "availableFrom": "2026-01-01",
            "availableTo": "2026-12-31",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
async def three_listings(client, verified_host):
    token = verified_host["token"]
    return {
        "campus": await _create_listing(client, token, zip_code="78705", title="Campus"),
        "hyde_park": await _create_listing(client, token, zip_code="78751", title="Hyde Park"),
        "dallas": await _create_listing(client, token, zip_code="75080", title="Dallas"),
    }


async def test_create_listing_geocodes_its_zip(client, verified_host):
    listing = await _create_listing(
        client, verified_host["token"], zip_code="78705", title="Campus"
    )
    assert listing["lat"] == pytest.approx(30.29, abs=0.05)
    assert listing["lng"] == pytest.approx(-97.74, abs=0.05)
    assert listing["distanceMiles"] is None  # only set by a radius search


async def test_radius_search_bounds_and_sorts_by_distance(client, three_listings):
    resp = await client.get(
        "/listings/", params={**AUSTIN_LATLNG, "radiusMiles": 25}
    )
    assert resp.status_code == 200
    results = resp.json()

    titles = [r["title"] for r in results]
    assert "Dallas" not in titles  # ~180 mi out, past the 25 mi radius
    assert titles == ["Campus", "Hyde Park"]  # nearest first

    for r in results:
        assert r["distanceMiles"] is not None
    assert results[0]["distanceMiles"] <= results[1]["distanceMiles"]
    assert results[0]["distanceMiles"] == pytest.approx(0.0, abs=1.0)


async def test_zipcode_search_geocodes_into_a_radius_query(client, three_listings):
    # No explicit lat/lng — the ZIP alone drives the distance search.
    resp = await client.get("/listings/", params={"zipCode": "78705"})
    assert resp.status_code == 200
    titles = [r["title"] for r in resp.json()]
    assert set(titles) == {"Campus", "Hyde Park"}


async def test_widening_the_radius_reaches_dallas(client, three_listings):
    resp = await client.get(
        "/listings/", params={**AUSTIN_LATLNG, "radiusMiles": 300}
    )
    assert resp.status_code == 200
    titles = [r["title"] for r in resp.json()]
    assert titles == ["Campus", "Hyde Park", "Dallas"]


async def test_unknown_zip_falls_back_to_string_match(client, three_listings):
    # 00000 isn't a real ZCTA, so there's no origin to search from — the
    # endpoint drops back to the prefix match rather than erroring.
    resp = await client.get("/listings/", params={"zipCode": "00000"})
    assert resp.status_code == 200
    assert resp.json() == []


async def test_price_filter_still_applies_inside_a_radius_search(client, verified_host):
    token = verified_host["token"]
    await _create_listing(client, token, zip_code="78705", title="Campus")
    pricey = await client.post(
        "/listings/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Pricey",
            "description": "Expensive spot.",
            "size": "M",
            "sizeSqft": 100,
            "pricePerMonth": 900,
            "addressSummary": "78705 area",
            "zipCode": "78705",
            "availableFrom": "2026-01-01",
            "availableTo": "2026-12-31",
        },
    )
    assert pricey.status_code == 201

    resp = await client.get(
        "/listings/", params={**AUSTIN_LATLNG, "radiusMiles": 25, "priceMax": 500}
    )
    assert resp.status_code == 200
    assert [r["title"] for r in resp.json()] == ["Campus"]
