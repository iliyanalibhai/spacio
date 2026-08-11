"""Reservation cost calculation.

This is the actual business model, not the "AI" pricing suggestion service
(see ai_pricing.py) — this module answers "what does this specific booking
cost", given a host's monthly rate and what the renter is requesting.

Pure functions only: no database access, so this is fully unit-testable.
See docs/DOCUMENTATION.md §5 for the business rules this implements.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, Union

from app.core.config import settings

DateLike = Union[date, datetime]

# Declared value tiers -> flat monthly cost. Treated as (previous max, this
# max], so a declared value of exactly $1,000 falls in the first tier.
# Replaces the v1 prototype's `sqftRequested * 0.15`, which was not the
# business model.
INSURANCE_TIERS: list[tuple[float, float]] = [
    (1_000.0, 12.0),
    (3_000.0, 20.0),
    (5_000.0, 30.0),
    (10_000.0, 45.0),
]


class DeclaredValueTooHighError(ValueError):
    """Raised when a declared value exceeds the highest insurance tier."""


def insurance_monthly_cost(declared_value: float) -> float:
    if declared_value < 0:
        raise ValueError("declared_value must be non-negative")
    for max_value, cost in INSURANCE_TIERS:
        if declared_value <= max_value:
            return cost
    raise DeclaredValueTooHighError(
        f"No insurance tier covers a declared value of {declared_value}; "
        f"the highest tier covers up to {INSURANCE_TIERS[-1][0]}"
    )


@dataclass(frozen=True)
class ReservationCostBreakdown:
    days: int
    space_ratio: float
    base_price: float
    service_fee: float
    box_cost: float
    insurance_cost: float
    total: float


def _month_fraction(start: DateLike, end: DateLike) -> tuple[int, float]:
    if isinstance(start, datetime):
        start = start.date()
    if isinstance(end, datetime):
        end = end.date()
    days = (end - start).days
    if days <= 0:
        raise ValueError("end date must be after start date")
    return days, days / 30


def calculate_reservation_cost(
    host_monthly_price: float,
    total_sqft: float,
    sqft_requested: float,
    start: DateLike,
    end: DateLike,
    num_boxes: int = 0,
    insurance_declared_value: Optional[float] = None,
    has_own_insurance: bool = False,
) -> ReservationCostBreakdown:
    """Calculate the full cost breakdown for a reservation.

    base = hostMonthlyPrice * (sqftRequested / totalSqft) * (days / 30)
    serviceFee = base * SERVICE_FEE_RATE
    boxCost = numBoxes * BOX_PRICE_PER_MONTH * (days / 30)
    insuranceCost = tier(declaredValue) * (days / 30), unless the renter
        supplies their own insurance, in which case it's 0.
    """
    if total_sqft <= 0:
        raise ValueError("total_sqft must be positive")
    if sqft_requested <= 0:
        raise ValueError("sqft_requested must be positive")
    if sqft_requested > total_sqft:
        raise ValueError("sqft_requested cannot exceed total_sqft")

    days, month_fraction = _month_fraction(start, end)
    space_ratio = sqft_requested / total_sqft

    base_price = round(host_monthly_price * space_ratio * month_fraction, 2)
    service_fee = round(base_price * settings.service_fee_rate, 2)
    box_cost = round(num_boxes * settings.box_price_per_month * month_fraction, 2)

    insurance_cost = 0.0
    if insurance_declared_value is not None and not has_own_insurance:
        insurance_cost = round(
            insurance_monthly_cost(insurance_declared_value) * month_fraction, 2
        )

    total = round(base_price + service_fee + box_cost + insurance_cost, 2)

    return ReservationCostBreakdown(
        days=days,
        space_ratio=space_ratio,
        base_price=base_price,
        service_fee=service_fee,
        box_cost=box_cost,
        insurance_cost=insurance_cost,
        total=total,
    )
