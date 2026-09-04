"""ZIP-code geocoding and great-circle distance.

Spacio listings store a 5-digit ZIP and a neighbourhood-level `addressSummary`
(deliberately never a street address, for host privacy), so the only geocoding
we can do is ZIP -> centroid. `zip_centroids.csv` (vendored from the US Census
2020 ZCTA gazetteer -- see `app/data/build_zip_centroids.py`) maps each ZIP
Code Tabulation Area to its interior point.

That point becomes the listing's map marker and the origin of a radius search.
Accuracy is ZIP-centroid level -- fine for "storage within ~15 miles", not for
turn-by-turn. Callers that can't resolve a ZIP (a made-up code, a PO-box-only
ZIP the gazetteer omits) get `None` and are expected to degrade gracefully
rather than error.

Pure standard library on purpose: no numpy, no network, no external geocoder.
`_load_centroids` reads the ~33k-row CSV once and caches it (~3 MB of dict).
"""

from __future__ import annotations

import csv
import math
from functools import lru_cache
from pathlib import Path
from typing import Optional, Tuple

Coords = Tuple[float, float]  # (latitude, longitude), degrees

_CENTROIDS_PATH = Path(__file__).resolve().parent.parent / "data" / "zip_centroids.csv"

# Mean Earth radius (miles). Spacio only needs distances good to a fraction of
# a mile, so the spherical-Earth approximation is more than enough.
EARTH_RADIUS_MI = 3958.7613
METERS_PER_MILE = 1609.344
MILES_PER_METER = 1.0 / METERS_PER_MILE


@lru_cache(maxsize=1)
def _load_centroids() -> dict[str, Coords]:
    out: dict[str, Coords] = {}
    with _CENTROIDS_PATH.open(newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                out[row["zip"]] = (float(row["lat"]), float(row["lng"]))
            except (KeyError, ValueError):
                continue
    return out


def normalize_zip(zip_code: Optional[str]) -> Optional[str]:
    """Reduce a user-supplied ZIP to the bare 5-digit code, or None.

    Accepts "78705", "78705-1234", " 78705 "; rejects anything that isn't
    5 leading digits.
    """
    if not zip_code:
        return None
    digits = "".join(ch for ch in zip_code if ch.isdigit())
    return digits[:5] if len(digits) >= 5 else None


def zip_to_coords(zip_code: Optional[str]) -> Optional[Coords]:
    """(lat, lng) for a ZIP's centroid, or None if it can't be resolved."""
    normalized = normalize_zip(zip_code)
    if normalized is None:
        return None
    return _load_centroids().get(normalized)


def haversine_miles(a: Coords, b: Coords) -> float:
    """Great-circle distance between two (lat, lng) points, in miles."""
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_MI * math.asin(math.sqrt(h))


def to_geojson_point(coords: Coords) -> dict:
    """(lat, lng) -> a GeoJSON Point.

    GeoJSON orders coordinates [longitude, latitude] -- the opposite of how
    they're spoken and of every other tuple in this module. MongoDB's 2dsphere
    index and `$geoNear` both expect this order.
    """
    lat, lng = coords
    return {"type": "Point", "coordinates": [lng, lat]}
