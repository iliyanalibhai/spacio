"""Tests for the real (Phase 2) pricing model in `app/services/ai_pricing.py`.

Pure business-logic tests — no database needed, same category as
`test_reservation_pricing.py` and `test_capacity.py`. These exercise the
committed model artifact directly (not a freshly trained one), so a
regression here means either the artifact or the inference code drifted.
"""

from app.ml.features import zip_demand_tier
from app.services.ai_pricing import MAX_PRICE, MIN_PRICE, _load_bundle, suggest_price

HIGH_DEMAND_ZIP = "78701"  # Austin
LOW_DEMAND_ZIP = "90210"  # not in any demand tier table


def test_zip_fixtures_are_actually_different_tiers():
    """Sanity-check the fixtures above before trusting comparisons that rely on them."""
    assert zip_demand_tier(HIGH_DEMAND_ZIP) == "high"
    assert zip_demand_tier(LOW_DEMAND_ZIP) == "low"


def test_suggest_price_is_deterministic():
    first = suggest_price(size="M", zip_code=HIGH_DEMAND_ZIP, indoor=True, size_sqft=100)
    second = suggest_price(size="M", zip_code=HIGH_DEMAND_ZIP, indoor=True, size_sqft=100)
    assert first == second


def test_quantiles_are_ordered_low_mid_high():
    suggested, min_price, max_price, _ = suggest_price(
        size="L", zip_code=LOW_DEMAND_ZIP, indoor=False, size_sqft=200
    )
    assert min_price <= suggested <= max_price


def test_larger_space_costs_more_within_the_same_size_bucket():
    small_sqft = suggest_price(size="L", zip_code=HIGH_DEMAND_ZIP, indoor=True, size_sqft=160)
    large_sqft = suggest_price(size="L", zip_code=HIGH_DEMAND_ZIP, indoor=True, size_sqft=380)
    assert large_sqft[0] > small_sqft[0]


def test_high_demand_zip_costs_more_than_low_demand_zip():
    low = suggest_price(size="M", zip_code=LOW_DEMAND_ZIP, indoor=True, size_sqft=100)
    high = suggest_price(size="M", zip_code=HIGH_DEMAND_ZIP, indoor=True, size_sqft=100)
    assert high[0] > low[0]


def test_indoor_costs_more_than_outdoor_all_else_equal():
    outdoor = suggest_price(size="M", zip_code=HIGH_DEMAND_ZIP, indoor=False, size_sqft=100)
    indoor = suggest_price(size="M", zip_code=HIGH_DEMAND_ZIP, indoor=True, size_sqft=100)
    assert indoor[0] > outdoor[0]


def test_missing_sqft_falls_back_to_bucket_midpoint_without_erroring():
    suggested, min_price, max_price, explanation = suggest_price(
        size="S", zip_code=LOW_DEMAND_ZIP, indoor=False, size_sqft=None
    )
    assert min_price <= suggested <= max_price
    assert "synthetic" in explanation.lower()


def test_prices_stay_within_safety_bounds():
    for size in ("S", "M", "L"):
        for zip_code in (HIGH_DEMAND_ZIP, LOW_DEMAND_ZIP):
            suggested, min_price, max_price, _ = suggest_price(
                size=size, zip_code=zip_code, indoor=True, size_sqft=None
            )
            assert MIN_PRICE <= min_price <= suggested <= max_price <= MAX_PRICE


def test_committed_artifact_beats_the_naive_baseline_on_held_out_data():
    """Guards against ever shipping a model that isn't actually better than
    the naive per-ZIP-tier-per-sqft baseline it's supposed to improve on."""
    metrics = _load_bundle()["metrics"]
    assert metrics["model_mae"] < metrics["naive_zip_tier_per_sqft_baseline_mae"]
