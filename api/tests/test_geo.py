"""Tests for app.services.geo — ZIP centroid lookup and haversine distance.

Pure unit tests: no database, no network. They do read the vendored
`app/data/zip_centroids.csv`, which ships in the repo.
"""

from __future__ import annotations

import math

import pytest

from app.services.geo import (
    _load_centroids,
    haversine_miles,
    normalize_zip,
    to_geojson_point,
    zip_to_coords,
)


class TestCentroidTable:
    def test_table_loads_and_covers_the_country(self):
        table = _load_centroids()
        # ~33k ZCTAs nationally; assert a floor that leaves headroom.
        assert len(table) > 30_000

    def test_known_zip_resolves_to_the_expected_region(self):
        # 78705 = West Campus, Austin TX. Centroid should be near (30.3, -97.7).
        lat, lng = zip_to_coords("78705")
        assert 30.0 < lat < 30.6
        assert -98.0 < lng < -97.5

    def test_zip_plus_four_and_whitespace_are_accepted(self):
        assert zip_to_coords("78705-1234") == zip_to_coords("78705")
        assert zip_to_coords("  78705 ") == zip_to_coords("78705")

    def test_unresolvable_zip_returns_none(self):
        assert zip_to_coords("00000") is None  # not a real ZCTA
        assert zip_to_coords("abcde") is None
        assert zip_to_coords("123") is None
        assert zip_to_coords("") is None
        assert zip_to_coords(None) is None


class TestNormalizeZip:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("78705", "78705"),
            ("78705-1234", "78705"),
            (" 90210 ", "90210"),
            ("9021", None),
            ("", None),
            (None, None),
        ],
    )
    def test_normalize(self, raw, expected):
        assert normalize_zip(raw) == expected


class TestHaversine:
    def test_zero_distance(self):
        p = (30.2943, -97.7385)
        assert haversine_miles(p, p) == pytest.approx(0.0, abs=1e-6)

    def test_la_to_nyc_matches_known_great_circle(self):
        la = (34.0522, -118.2437)
        nyc = (40.7128, -74.0060)
        # Published great-circle distance is ~2451 mi.
        assert haversine_miles(la, nyc) == pytest.approx(2451, abs=15)

    def test_symmetric(self):
        a = (29.7604, -95.3698)  # Houston
        b = (32.7767, -96.7970)  # Dallas
        assert haversine_miles(a, b) == pytest.approx(haversine_miles(b, a), abs=1e-9)

    def test_austin_to_dallas_is_a_couple_hundred_miles(self):
        austin = zip_to_coords("78705")
        dallas = zip_to_coords("75080")
        assert 170 < haversine_miles(austin, dallas) < 210


class TestGeoJson:
    def test_point_is_lng_lat_ordered(self):
        point = to_geojson_point((30.2943, -97.7385))
        assert point == {"type": "Point", "coordinates": [-97.7385, 30.2943]}
        # longitude first, latitude second
        assert point["coordinates"][0] < 0
        assert point["coordinates"][1] > 0

    def test_round_trips_through_haversine(self):
        coords = zip_to_coords("77840")  # College Station
        point = to_geojson_point(coords)
        lng, lat = point["coordinates"]
        assert haversine_miles((lat, lng), coords) == pytest.approx(0.0, abs=1e-9)
        assert not math.isnan(lat)
