from datetime import date

import pytest

from app.services.reservation_pricing import (
    DeclaredValueTooHighError,
    calculate_reservation_cost,
    insurance_monthly_cost,
)


def test_full_space_full_month_matches_reference_unit_economics():
    """From the business brief: $40/mo host price, full space, full month
    -> $40 base, $8 service fee (20%), host nets $32."""
    cost = calculate_reservation_cost(
        host_monthly_price=40.0,
        total_sqft=100,
        sqft_requested=100,
        start=date(2026, 1, 1),
        end=date(2026, 1, 31),
    )
    assert cost.days == 30
    assert cost.base_price == 40.0
    assert cost.service_fee == 8.0
    assert cost.box_cost == 0
    assert cost.insurance_cost == 0
    assert cost.total == 48.0


def test_partial_space_and_partial_time_prorate_together():
    # half the space, half the month
    cost = calculate_reservation_cost(
        host_monthly_price=100.0,
        total_sqft=200,
        sqft_requested=100,
        start=date(2026, 1, 1),
        end=date(2026, 1, 16),
    )
    assert cost.days == 15
    assert cost.space_ratio == 0.5
    assert cost.base_price == pytest.approx(100 * 0.5 * (15 / 30))


def test_box_cost_is_ten_per_box_prorated():
    cost = calculate_reservation_cost(
        host_monthly_price=40.0,
        total_sqft=100,
        sqft_requested=100,
        start=date(2026, 1, 1),
        end=date(2026, 1, 31),
        num_boxes=2,
    )
    assert cost.box_cost == 20.0  # 2 boxes * $10, full month
    assert cost.total == 40.0 + 8.0 + 20.0


@pytest.mark.parametrize(
    "declared_value,expected",
    [
        (0, 12.0),
        (1000, 12.0),
        (1000.01, 20.0),
        (3000, 20.0),
        (3000.01, 30.0),
        (5000, 30.0),
        (5000.01, 45.0),
        (10000, 45.0),
    ],
)
def test_insurance_tiers(declared_value, expected):
    assert insurance_monthly_cost(declared_value) == expected


def test_insurance_declared_value_above_highest_tier_raises():
    with pytest.raises(DeclaredValueTooHighError):
        insurance_monthly_cost(10_000.01)


def test_has_own_insurance_waives_spacio_insurance_charge():
    cost = calculate_reservation_cost(
        host_monthly_price=40.0,
        total_sqft=100,
        sqft_requested=100,
        start=date(2026, 1, 1),
        end=date(2026, 1, 31),
        insurance_declared_value=2000,
        has_own_insurance=True,
    )
    assert cost.insurance_cost == 0


def test_insurance_cost_is_prorated_by_stay_length():
    cost = calculate_reservation_cost(
        host_monthly_price=40.0,
        total_sqft=100,
        sqft_requested=100,
        start=date(2026, 1, 1),
        end=date(2026, 1, 16),  # 15 days = half a month
        insurance_declared_value=500,
    )
    assert cost.insurance_cost == pytest.approx(12.0 * 0.5)


def test_reference_box_scenario_from_business_brief():
    """$40/mo base, +box = $50/mo, per the business brief's reference
    unit economics."""
    cost = calculate_reservation_cost(
        host_monthly_price=40.0,
        total_sqft=100,
        sqft_requested=100,
        start=date(2026, 1, 1),
        end=date(2026, 1, 31),
        num_boxes=1,
    )
    assert cost.base_price + cost.box_cost == 50.0


def test_sqft_requested_cannot_exceed_total_sqft():
    with pytest.raises(ValueError):
        calculate_reservation_cost(
            host_monthly_price=40.0,
            total_sqft=100,
            sqft_requested=150,
            start=date(2026, 1, 1),
            end=date(2026, 1, 31),
        )


def test_end_date_must_be_after_start_date():
    with pytest.raises(ValueError):
        calculate_reservation_cost(
            host_monthly_price=40.0,
            total_sqft=100,
            sqft_requested=50,
            start=date(2026, 1, 10),
            end=date(2026, 1, 1),
        )
