"""Synthetic training data for the pricing model.

**This dataset is entirely synthetic.** Spacio has no real booking or
listing-price history to train on yet, and generating fabricated "real"
comps would be dishonest — so this module generates rows from an explicit,
documented formula plus noise, and every doc/comment describing the
resulting model says plainly that it was trained on synthetic data. See
`docs/DOCUMENTATION.md` §6.

The generative formula here is deliberately *not* the same as the old
heuristic in `ai_pricing.py` (now retired) — it's continuous in sqft with
diminishing per-sqft cost at larger sizes, has a demand-tier x indoor
interaction, and includes noisy/outlier rows, so a model actually has to
learn structure rather than just memorizing the old heuristic's formula.
That also makes the baseline-vs-model MAE comparison in
`train_pricing_model.py` meaningful instead of circular.
"""

import numpy as np
import pandas as pd

from app.ml.features import (
    HIGH_DEMAND_ZIP3,
    MID_DEMAND_ZIP3,
    SIZE_SQFT_RANGE,
    zip_demand_tier,
)

# $/sqft/month by demand tier, before the sqft-scaling and indoor effects
# below are applied. Chosen so the *median* generated price for a mid-size
# (~100 sqft) low-tier outdoor unit lands close to the old heuristic's ~$28
# floor and a high-tier indoor large unit lands near its ~$70 ceiling — the
# synthetic market is calibrated to the same business range documented in
# `docs/DOCUMENTATION.md` §5, it just isn't the same formula.
BASE_RATE_PER_SQFT = {"low": 0.30, "mid": 0.37, "high": 0.46}
INDOOR_MULTIPLIER = 1.18
SQFT_SCALING_EXPONENT = 0.88  # < 1: bulk discount, larger units cost less per sqft
FLAT_ACCESS_FEE = 6.0  # fixed monthly overhead independent of size
NOISE_SIGMA = 0.08  # multiplicative log-normal noise (per-listing variance)
OUTLIER_PROBABILITY = 0.05
OUTLIER_SPREAD = 0.25

_LOW_DEMAND_ZIP3 = ["733", "780", "790", "791", "797", "798", "700", "710"]


def _sample_zip_code(rng: np.random.Generator) -> str:
    tier = rng.choice(["high", "mid", "low"], p=[0.25, 0.35, 0.40])
    prefix_pool = {
        "high": sorted(HIGH_DEMAND_ZIP3),
        "mid": sorted(MID_DEMAND_ZIP3),
        "low": _LOW_DEMAND_ZIP3,
    }[tier]
    prefix = rng.choice(prefix_pool)
    suffix = rng.integers(0, 100)
    return f"{prefix}{suffix:02d}"


def _sample_row(rng: np.random.Generator) -> dict:
    size = rng.choice(["S", "M", "L"], p=[0.35, 0.4, 0.25])
    lo, hi = SIZE_SQFT_RANGE[size]
    sqft = rng.uniform(lo, hi)
    zip_code = _sample_zip_code(rng)
    tier = zip_demand_tier(zip_code)
    indoor = bool(rng.random() < 0.65)

    rate = BASE_RATE_PER_SQFT[tier]
    price = rate * (sqft**SQFT_SCALING_EXPONENT) + FLAT_ACCESS_FEE
    if indoor:
        price *= INDOOR_MULTIPLIER

    noise = np.exp(rng.normal(0.0, NOISE_SIGMA))
    price *= noise
    if rng.random() < OUTLIER_PROBABILITY:
        price *= 1 + rng.uniform(-OUTLIER_SPREAD, OUTLIER_SPREAD)

    return {
        "size": size,
        "sizeSqft": round(sqft, 1),
        "zipCode": zip_code,
        "zip_demand_tier": tier,
        "indoor": indoor,
        "price": round(max(price, 8.0), 2),
    }


def generate_synthetic_comps(n: int = 8000, seed: int = 42) -> pd.DataFrame:
    """Generate `n` synthetic comp rows, fully reproducible given `seed`."""
    rng = np.random.default_rng(seed)
    rows = [_sample_row(rng) for _ in range(n)]
    return pd.DataFrame(rows)
