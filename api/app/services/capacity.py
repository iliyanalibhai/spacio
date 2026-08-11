"""Listing capacity rule.

A single listing can host multiple concurrent renters as long as the sum of
sqftRequested across all overlapping confirmed + pending reservations never
exceeds the listing's totalSqft. This was already correct in the v1
prototype; it's extracted here as a pure function (given already-fetched
reservation dicts) so it can be unit tested without a database, and so the
route handler isn't where the business logic lives.

See docs/DOCUMENTATION.md §5.
"""

from datetime import date, datetime
from typing import Iterable, Union

DateLike = Union[date, datetime]

# Statuses that hold a claim on the listing's capacity. Declined and expired
# reservations release their sqft back to the pool.
CAPACITY_HOLDING_STATUSES = {"pending_host_confirmation", "confirmed"}


def date_ranges_overlap(
    a_start: DateLike, a_end: DateLike, b_start: DateLike, b_end: DateLike
) -> bool:
    """Half-open interval overlap: [a_start, a_end) intersects [b_start, b_end)."""
    return a_start < b_end and b_start < a_end


def reserved_sqft_for_range(
    reservations: Iterable[dict],
    start: DateLike,
    end: DateLike,
) -> float:
    """Sum sqftRequested across reservations that overlap [start, end) and
    are still holding capacity (pending or confirmed)."""
    total = 0.0
    for reservation in reservations:
        if reservation.get("status") not in CAPACITY_HOLDING_STATUSES:
            continue
        r_start = reservation["startDate"]
        r_end = reservation["endDate"]
        if date_ranges_overlap(r_start, r_end, start, end):
            total += reservation.get("sqftRequested", 0)
    return total


def available_sqft_for_range(
    total_sqft: float,
    reservations: Iterable[dict],
    start: DateLike,
    end: DateLike,
) -> float:
    """How much sqft is free for a new booking over [start, end)."""
    reserved = reserved_sqft_for_range(reservations, start, end)
    return total_sqft - reserved


def can_fit(
    sqft_requested: float,
    total_sqft: float,
    reservations: Iterable[dict],
    start: DateLike,
    end: DateLike,
) -> bool:
    return sqft_requested <= available_sqft_for_range(
        total_sqft, reservations, start, end
    )
