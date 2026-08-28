"""Host-facing price suggestion service.

Backed by a real trained model: three LightGBM quantile regressors
(p15/p50/p85) trained on a synthetic comps dataset, loaded from the
versioned artifact in `app/ml/artifacts/`. See
`app/ml/train_pricing_model.py` for how it was trained and
`docs/DOCUMENTATION.md` §6 for the full write-up (features, training data
provenance, evaluation against a naive baseline, known limitations).

**The training data is synthetic, not real bookings** — Spacio has no
booking history yet to train on. Every user-facing explanation string below
says so plainly. This replaces the deterministic heuristic that shipped in
Phase 0/1 (see git history for `BASE_PRICES_BY_SIZE` etc. if you need the
old version); the v1 prototype before *that* was worse still — it multiplied
its output by `random.uniform(0.95, 1.05)` and called it "AI," which this
codebase treats as a defect, not a feature, regardless of which pricing
implementation is live.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

import joblib  # type: ignore[import-untyped]

from app.ml.features import build_feature_frame, size_bucket, zip_demand_tier

ARTIFACT_PATH = Path(__file__).resolve().parents[1] / "ml" / "artifacts" / "pricing_model_v1.joblib"

# Safety-net bounds on model output, not a business price band — the old
# heuristic's $25-70 was an intentional fixed band; a real model should be
# allowed to reflect genuine variation across size/ZIP/indoor, so this only
# guards against pathological extrapolation on out-of-distribution inputs.
MIN_PRICE = 10.0
MAX_PRICE = 500.0


@lru_cache(maxsize=1)
def _load_bundle() -> dict:
    if not ARTIFACT_PATH.exists():
        raise RuntimeError(
            f"Pricing model artifact not found at {ARTIFACT_PATH}. "
            "Run `python -m app.ml.train_pricing_model` from `api/` to generate it "
            "(it's committed to the repo, so this should only happen on a broken checkout)."
        )
    return joblib.load(ARTIFACT_PATH)


def suggest_price(
    size: Literal["S", "M", "L"],
    zip_code: str,
    indoor: Optional[bool] = None,
    size_sqft: Optional[float] = None,
) -> tuple[float, float, float, str]:
    bundle = _load_bundle()
    models = bundle["models"]

    features = build_feature_frame(size=size, zip_code=zip_code, indoor=indoor, size_sqft=size_sqft)
    raw = {name: float(model.predict(features)[0]) for name, model in models.items()}

    # LightGBM's quantile models are trained independently and can
    # occasionally cross on out-of-distribution inputs (e.g. p15 > p50) —
    # sorting guarantees a sane low <= mid <= high ordering regardless.
    low, mid, high = sorted((raw["p15"], raw["p50"], raw["p85"]))

    def clip(v: float) -> float:
        return round(min(MAX_PRICE, max(MIN_PRICE, v)), 2)

    suggested, min_price, max_price = clip(mid), clip(low), clip(high)

    tier = zip_demand_tier(zip_code)
    bucket = size_bucket(size)
    explanation = (
        f"Estimate from a LightGBM quantile-regression model ({bundle['version']}) trained on "
        f"Spacio's synthetic comps dataset, for a {bucket}-size ({size_sqft or 'estimated'} sqft) "
        f"space in a '{tier}'-demand ZIP{' (indoor)' if indoor else ''}. "
        "This model is trained on synthetic data, not real booking history — Spacio doesn't have "
        "bookings to train on yet. See docs/DOCUMENTATION.md §6 for methodology and evaluation."
    )
    return suggested, min_price, max_price, explanation
