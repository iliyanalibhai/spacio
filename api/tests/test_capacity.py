from datetime import date

from app.services.capacity import (
    available_sqft_for_range,
    can_fit,
    date_ranges_overlap,
    reserved_sqft_for_range,
)


def test_non_overlapping_ranges():
    assert not date_ranges_overlap(
        date(2026, 1, 1), date(2026, 1, 10), date(2026, 1, 10), date(2026, 1, 20)
    )
    assert not date_ranges_overlap(
        date(2026, 1, 10), date(2026, 1, 20), date(2026, 1, 1), date(2026, 1, 10)
    )


def test_overlapping_ranges():
    assert date_ranges_overlap(
        date(2026, 1, 1), date(2026, 1, 15), date(2026, 1, 10), date(2026, 1, 20)
    )
    assert date_ranges_overlap(
        date(2026, 1, 1), date(2026, 1, 20), date(2026, 1, 5), date(2026, 1, 10)
    )


def test_reserved_sqft_ignores_declined_and_expired():
    reservations = [
        {"status": "declined", "startDate": date(2026, 1, 1), "endDate": date(2026, 1, 31), "sqftRequested": 100},
        {"status": "expired", "startDate": date(2026, 1, 1), "endDate": date(2026, 1, 31), "sqftRequested": 100},
        {"status": "confirmed", "startDate": date(2026, 1, 1), "endDate": date(2026, 1, 31), "sqftRequested": 30},
        {"status": "pending_host_confirmation", "startDate": date(2026, 1, 1), "endDate": date(2026, 1, 31), "sqftRequested": 20},
    ]
    reserved = reserved_sqft_for_range(reservations, date(2026, 1, 5), date(2026, 1, 10))
    assert reserved == 50


def test_reserved_sqft_ignores_non_overlapping_dates():
    reservations = [
        {"status": "confirmed", "startDate": date(2026, 2, 1), "endDate": date(2026, 2, 28), "sqftRequested": 100},
    ]
    reserved = reserved_sqft_for_range(reservations, date(2026, 1, 1), date(2026, 1, 31))
    assert reserved == 0


def test_multiple_concurrent_renters_fit_within_capacity():
    """From the business brief: a single listing can host multiple
    concurrent renters as long as the sum of sqftRequested across
    overlapping confirmed + pending reservations never exceeds totalSqft."""
    total_sqft = 200
    existing = [
        {"status": "confirmed", "startDate": date(2026, 1, 1), "endDate": date(2026, 1, 31), "sqftRequested": 80},
        {"status": "pending_host_confirmation", "startDate": date(2026, 1, 5), "endDate": date(2026, 1, 20), "sqftRequested": 50},
    ]
    # 200 - 80 - 50 = 70 sqft free
    assert available_sqft_for_range(total_sqft, existing, date(2026, 1, 10), date(2026, 1, 15)) == 70
    assert can_fit(70, total_sqft, existing, date(2026, 1, 10), date(2026, 1, 15))
    assert not can_fit(71, total_sqft, existing, date(2026, 1, 10), date(2026, 1, 15))


def test_non_overlapping_renters_do_not_count_against_each_other():
    total_sqft = 100
    existing = [
        {"status": "confirmed", "startDate": date(2026, 1, 1), "endDate": date(2026, 1, 15), "sqftRequested": 100},
    ]
    # A booking entirely after the first one's end date should see full capacity.
    assert available_sqft_for_range(total_sqft, existing, date(2026, 1, 15), date(2026, 1, 31)) == 100


def test_can_fit_exact_boundary():
    total_sqft = 100
    existing = [
        {"status": "confirmed", "startDate": date(2026, 1, 1), "endDate": date(2026, 1, 31), "sqftRequested": 60},
    ]
    assert can_fit(40, total_sqft, existing, date(2026, 1, 1), date(2026, 1, 31))
    assert not can_fit(40.01, total_sqft, existing, date(2026, 1, 1), date(2026, 1, 31))
