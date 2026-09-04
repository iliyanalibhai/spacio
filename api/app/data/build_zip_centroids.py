"""Regenerate `zip_centroids.csv` from the US Census ZCTA gazetteer.

`zip_centroids.csv` is the vendored ZIP-code -> (lat, lng) lookup table that
`app/services/geo.py` loads for "poor man's geocoding": a listing only stores a
5-digit ZIP and a neighbourhood-level `addressSummary` (never a street
address), so its map point is the population-weighted centroid of its ZIP Code
Tabulation Area (ZCTA). Accuracy is therefore ZIP-centroid level (~1-3 miles in
a typical suburban ZIP), which is honest about what the data actually is.

Source: US Census Bureau 2020 Gazetteer Files, "ZIP Code Tabulation Areas"
national file. This is a US Government work and in the public domain (Title 17
U.S.C. Sec. 105) -- no attribution requirement, unlike SimpleMaps or GeoNames.

    https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html

The download is a ~1 MB zip containing one tab-delimited file with columns:
    GEOID  ALAND  AWATER  ALAND_SQMI  AWATER_SQMI  INTPTLAT  INTPTLONG

(The `INTPTLONG` header and every row's final field carry a long run of
trailing spaces in the Census file, so we parse by column position and strip.)

We keep only GEOID (the ZCTA5 code) and the interior-point lat/long, and write
a compact `zip,lat,lng` CSV (~33k rows, ~700 KB). That file is committed to the
repo -- the same way `app/ml/artifacts/pricing_model_v1.joblib` is -- because it
is static reference data and a fresh clone should work with no network.

Run from `api/`:
    python -m app.data.build_zip_centroids
    python -m app.data.build_zip_centroids path/to/2020_Gaz_zcta_national.zip
    python -m app.data.build_zip_centroids path/to/2020_Gaz_zcta_national.txt

The optional path argument skips the download and reads a local copy of the
gazetteer zip (or its extracted .txt) -- useful behind a proxy or when the
machine's Python has no root certificates.
"""

from __future__ import annotations

import csv
import io
import ssl
import sys
import urllib.request
import zipfile
from pathlib import Path

GAZETTEER_URL = (
    "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"
    "2020_Gazetteer/2020_Gaz_zcta_national.zip"
)
OUT_PATH = Path(__file__).resolve().parent / "zip_centroids.csv"


def _load_gazetteer_text(source: str | None) -> str:
    if source is None:
        print(f"downloading {GAZETTEER_URL}")
        try:
            import certifi

            context = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            context = ssl.create_default_context()
        with urllib.request.urlopen(  # noqa: S310 (fixed trusted URL)
            GAZETTEER_URL, context=context
        ) as resp:
            raw = resp.read()
    else:
        path = Path(source)
        raw = path.read_bytes()
        if path.suffix == ".txt":
            return raw.decode("latin-1")

    archive = zipfile.ZipFile(io.BytesIO(raw))
    inner_name = archive.namelist()[0]
    return archive.read(inner_name).decode("latin-1")


def build(source: str | None = None) -> None:
    text = _load_gazetteer_text(source)

    # Columns are fixed: GEOID, ALAND, AWATER, ALAND_SQMI, AWATER_SQMI,
    # INTPTLAT, INTPTLONG. Parse by position and strip -- the header row and
    # the final field of every data row are padded with trailing spaces.
    rows: list[tuple[str, str, str]] = []
    lines = text.splitlines()
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        geoid = parts[0].strip()
        lat = parts[5].strip()
        lng = parts[6].strip()
        if len(geoid) != 5 or not lat or not lng:
            continue
        rows.append((geoid, f"{float(lat):.5f}", f"{float(lng):.5f}"))

    rows.sort()
    with OUT_PATH.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["zip", "lat", "lng"])
        writer.writerows(rows)

    print(f"wrote {len(rows)} rows to {OUT_PATH}")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else None)
