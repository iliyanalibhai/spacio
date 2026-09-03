from datetime import datetime, timedelta

import pytest

from app.services.review_eligibility import ReviewNotAllowedError, assert_can_review

RENTER_ID = "renter-1"
NOW = datetime(2026, 3, 1, 12, 0, 0)


def _reservation(**overrides) -> dict:
    base = {
        "renterId": RENTER_ID,
        "status": "confirmed",
        "endDate": NOW - timedelta(days=1),
    }
    base.update(overrides)
    return base


def test_confirmed_and_ended_reservation_is_reviewable():
    assert_can_review(_reservation(), RENTER_ID, NOW)  # does not raise


def test_someone_elses_reservation_cannot_be_reviewed():
    with pytest.raises(ReviewNotAllowedError):
        assert_can_review(_reservation(renterId="someone-else"), RENTER_ID, NOW)


@pytest.mark.parametrize("status", ["pending_host_confirmation", "declined", "expired"])
def test_only_confirmed_reservations_are_reviewable(status):
    with pytest.raises(ReviewNotAllowedError):
        assert_can_review(_reservation(status=status), RENTER_ID, NOW)


def test_cannot_review_before_the_stay_ends():
    with pytest.raises(ReviewNotAllowedError):
        assert_can_review(_reservation(endDate=NOW + timedelta(days=1)), RENTER_ID, NOW)


def test_can_review_exactly_when_the_stay_ends():
    assert_can_review(_reservation(endDate=NOW), RENTER_ID, NOW)  # does not raise
