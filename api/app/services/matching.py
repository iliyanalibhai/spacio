"""Free-text listing matching — semantic search over listing text.

A renter describes what they need to store ("a road bike and a few boxes
over winter") and this ranks listings by how close that description is, in
meaning, to each listing's own title + description — then nudges the order
with the structured signals (distance from the search origin, price,
availability).

The semantic part is done with sentence embeddings (see
`app/ml/embeddings.py`): every listing's text and the query are turned into
384-dimensional unit vectors by `all-MiniLM-L6-v2`, and their cosine
similarity (a dot product, since the vectors are normalized) is the
relevance score. Unlike the keyword dictionary this replaced, "bicycle",
"cycling gear" and "somewhere for my bike" all land near a listing that
says "great for cyclists" even with no shared words.

This module is deliberately pure and model-free: it takes the query vector,
an optional (lat, lng) origin, and listings that already carry an
`embedding` and a `location`, and does nothing but arithmetic — so it
unit-tests with hand-built vectors and never imports torch. Producing the
vectors, geocoding the origin, and lazily backfilling listings that predate
these features are the router's job.

When `query_vector` is None — embeddings disabled, or the model failed to
load — `match_listings` still returns a sane ordering from the structured
signals alone, and its explanation string says the semantic ranking was
unavailable rather than pretending otherwise.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Optional, Sequence, Tuple

import numpy as np

from app.services.geo import haversine_miles

Coords = Tuple[float, float]  # (latitude, longitude)

# Relative weights of the ranking signals. The semantic score is a cosine
# similarity in roughly [0.0, 0.8] for related text; the others are small
# additive nudges so that, among listings of similar relevance, a nearby /
# cheaper / available one wins — without a far-away exact-text match ever
# outranking a close-by near-match. Tune here, not in the router.
SEMANTIC_WEIGHT = 1.0
# Distance term: DISTANCE_WEIGHT at zero miles, decaying exponentially with a
# ~DECAY_MILES scale length (≈0.37 * weight at DECAY_MILES, ≈0.14 at 2×). It
# replaced a flat exact-ZIP / shared-3-digit-prefix bonus, which treated "one
# block away in the next ZIP" and "40 miles away, same prefix" identically.
DISTANCE_WEIGHT = 0.15
DECAY_MILES = 15.0
PRICE_WEIGHT = 0.08  # max contribution, for a nominally free listing
DATE_FIT_BONUS = 0.05
DATE_MISS_PENALTY = -0.5

TOP_N_DEFAULT = 5


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity, safe against zero vectors. Inputs are expected to
    be unit vectors already (embeddings.embed normalizes), so this is
    essentially a dot product; the norm division just guards against a
    stray un-normalized or empty vector."""
    av = np.asarray(a, dtype=np.float32)
    bv = np.asarray(b, dtype=np.float32)
    if av.size == 0 or bv.size == 0 or av.shape != bv.shape:
        return 0.0
    denom = float(np.linalg.norm(av) * np.linalg.norm(bv))
    if denom == 0.0:
        return 0.0
    return float(np.dot(av, bv) / denom)


def _price_score(listing: dict) -> float:
    price = listing.get("pricePerMonth") or 0.0
    if price <= 0:
        return PRICE_WEIGHT
    # Smoothly decreasing: ~half weight around $50/mo, tending to 0 as
    # price grows. Bounded by PRICE_WEIGHT so it can only ever be a nudge.
    return PRICE_WEIGHT * (50.0 / (50.0 + float(price)))


def _as_date(value: object) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).date()
        except ValueError:
            return None
    return None


def _date_fit_score(
    listing: dict, want_from: Optional[date], want_to: Optional[date]
) -> float:
    """Reward listings whose availability window covers the requested dates,
    penalize ones that clearly don't. Neutral (0.0) when the caller gave no
    dates or the listing declares no window."""
    if want_from is None or want_to is None:
        return 0.0
    avail_from = _as_date(listing.get("availableFrom"))
    avail_to = _as_date(listing.get("availableTo"))
    if avail_from is None and avail_to is None:
        return 0.0
    if avail_from is not None and want_from < avail_from:
        return DATE_MISS_PENALTY
    if avail_to is not None and want_to > avail_to:
        return DATE_MISS_PENALTY
    return DATE_FIT_BONUS


def _listing_coords(listing: dict) -> Optional[Coords]:
    """(lat, lng) for a listing, from either a flat lat/lng pair (test
    fixtures) or a stored `location` GeoJSON Point (real Mongo docs)."""
    lat, lng = listing.get("lat"), listing.get("lng")
    if lat is not None and lng is not None:
        return (float(lat), float(lng))
    location = listing.get("location")
    if isinstance(location, dict):
        coordinates = location.get("coordinates")
        if isinstance(coordinates, (list, tuple)) and len(coordinates) == 2:
            return (float(coordinates[1]), float(coordinates[0]))
    return None


def _distance_score(listing: dict, origin_coords: Optional[Coords]) -> float:
    """Exponential distance decay from the search origin. Neutral (0.0) when
    the caller gave no origin or the listing has no coordinates."""
    if origin_coords is None:
        return 0.0
    listing_coords = _listing_coords(listing)
    if listing_coords is None:
        return 0.0
    miles = haversine_miles(origin_coords, listing_coords)
    return DISTANCE_WEIGHT * math.exp(-miles / DECAY_MILES)


def score_listing(
    listing: dict,
    query_vector: Optional[Sequence[float]],
    origin_coords: Optional[Coords] = None,
    want_from: Optional[date] = None,
    want_to: Optional[date] = None,
) -> float:
    """Combined ranking score for one listing. Higher is better.

    `query_vector` None => the semantic term is dropped and the score is
    built from the structured signals only.
    """
    score = 0.0

    listing_vec = listing.get("embedding")
    if query_vector is not None and listing_vec:
        score += SEMANTIC_WEIGHT * _cosine(query_vector, listing_vec)

    score += _distance_score(listing, origin_coords)
    score += _price_score(listing)
    score += _date_fit_score(listing, want_from, want_to)
    return score


def _explanation(
    query_vector: Optional[Sequence[float]],
    has_origin: bool,
    n: int,
) -> str:
    if n == 0:
        return "No available spaces matched your description."
    if query_vector is None:
        base = (
            f"Showing {n} available space{'s' if n != 1 else ''}, ranked by "
            "price and distance. (Semantic matching is unavailable right now, "
            "so this isn't ranked by how well each description matches what "
            "you typed.)"
        )
    else:
        base = (
            f"These {n} space{'s' if n != 1 else ''} have the listing "
            "descriptions closest in meaning to what you described"
        )
        base += ", with nearby spaces moved up" if has_origin else ""
        base += "."
    return base


def match_listings(
    listings: list[dict],
    query_vector: Optional[Sequence[float]],
    origin_coords: Optional[Coords] = None,
    want_from: Optional[date] = None,
    want_to: Optional[date] = None,
    top_n: int = TOP_N_DEFAULT,
) -> tuple[list[dict], str]:
    """Rank `listings` and return the top `top_n` plus a human explanation.

    Listings explicitly marked unavailable (`availability is False`) are
    dropped. Ordering is by `score_listing` descending; `_id` breaks ties
    for a stable result.
    """
    candidates = [lst for lst in listings if lst.get("availability", True) is not False]

    ranked = sorted(
        candidates,
        key=lambda lst: (
            -score_listing(lst, query_vector, origin_coords, want_from, want_to),
            str(lst.get("_id", "")),
        ),
    )
    top = ranked[:top_n]
    return top, _explanation(query_vector, origin_coords is not None, len(top))
