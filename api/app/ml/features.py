"""Feature encoding shared by training and inference for the pricing model.

This module is the single source of truth for how raw listing inputs (size
bucket, sqft, ZIP code, indoor flag) become the feature columns the LightGBM
models were trained on. Both `train_pricing_model.py` and
`app/services/ai_pricing.py` import from here rather than each keeping their
own copy — encoding drift between training and inference (e.g. a different
category order, or a different ZIP->tier mapping) would silently corrupt
predictions without raising any error, since LightGBM has no way to know the
input encoding changed.
"""

from typing import Literal, Optional

import pandas as pd

Size = Literal["S", "M", "L"]
DemandTier = Literal["low", "mid", "high"]

# Fixed category orderings. Both training and inference must build pandas
# `category` dtype columns against these exact lists so the categorical
# codes LightGBM sees line up on both sides.
SIZE_CATEGORIES: list[str] = ["S", "M", "L"]
TIER_CATEGORIES: list[str] = ["low", "mid", "high"]

FEATURE_COLUMNS: list[str] = ["size", "sizeSqft", "zip_demand_tier", "indoor"]
CATEGORICAL_COLUMNS: list[str] = ["size", "zip_demand_tier"]

# sqft ranges used to bucket a size letter and, in `synthetic_pricing_data`,
# to sample sqft per bucket. Mirrors the frontend's own bucketing in
# `CreateListingForm.tsx` (`sizeSqft <= 60 -> S`, `<= 150 -> M`, else `L`).
SIZE_SQFT_RANGE: dict[str, tuple[float, float]] = {
    "S": (20.0, 60.0),
    "M": (60.0, 150.0),
    "L": (150.0, 400.0),
}
# Used only as a fallback when a caller doesn't supply sizeSqft (e.g. an
# older API client) — the midpoint of the bucket's range.
SIZE_SQFT_FALLBACK: dict[str, float] = {
    k: (lo + hi) / 2 for k, (lo, hi) in SIZE_SQFT_RANGE.items()
}

# Simplified, hand-labeled go-to-market demand tiers by ZIP3 prefix. Not
# derived from real demand data (Spacio has no booking history yet) — this
# is the same kind of honest placeholder as the old heuristic's
# `HIGH_DEMAND_ZIP_PREFIXES`, just expanded from a binary flag to 3 tiers so
# the model has a less trivial signal to learn from. "high" keeps the
# original launch college towns (Austin, Dallas, San Antonio, College
# Station); "mid" adds a handful of other Texas metros; everything else is
# "low". Extend this table, not the model, if the real go-to-market ZIP list
# changes.
HIGH_DEMAND_ZIP3 = {"787", "750", "782", "778"}
MID_DEMAND_ZIP3 = {"770", "771", "772", "760", "761", "762", "733", "786", "799"}


def zip_demand_tier(zip_code: Optional[str]) -> DemandTier:
    prefix = (zip_code or "")[:3]
    if prefix in HIGH_DEMAND_ZIP3:
        return "high"
    if prefix in MID_DEMAND_ZIP3:
        return "mid"
    return "low"


def size_bucket(size: str) -> Size:
    key = size.upper()
    return key if key in SIZE_CATEGORIES else "M"  # type: ignore[return-value]


def build_feature_frame(
    size: str,
    zip_code: Optional[str],
    indoor: Optional[bool],
    size_sqft: Optional[float] = None,
) -> pd.DataFrame:
    """Build a single-row feature frame for inference, using the exact same
    column names/dtypes/category orderings as training."""
    bucket = size_bucket(size)
    sqft = size_sqft if size_sqft is not None else SIZE_SQFT_FALLBACK[bucket]
    tier = zip_demand_tier(zip_code)
    return pd.DataFrame(
        {
            "size": pd.Categorical([bucket], categories=SIZE_CATEGORIES),
            "sizeSqft": [float(sqft)],
            "zip_demand_tier": pd.Categorical([tier], categories=TIER_CATEGORIES),
            "indoor": [bool(indoor)],
        }
    )
