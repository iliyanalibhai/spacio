from datetime import datetime, timedelta

import pytest

from app.models.schemas import ReservationStatus
from app.services.reservation_state import (
    InvalidTransitionError,
    assert_transition,
    can_transition,
    is_hold_expired,
)

PENDING = ReservationStatus.pending
CONFIRMED = ReservationStatus.confirmed
DECLINED = ReservationStatus.declined
EXPIRED = ReservationStatus.expired
CANCELLED = ReservationStatus.cancelled


@pytest.mark.parametrize(
    "target",
    [CONFIRMED, DECLINED, EXPIRED, CANCELLED],
)
def test_pending_can_transition_to_terminal_states(target):
    assert can_transition(PENDING, target)


def test_confirmed_can_only_transition_to_cancelled():
    """A renter cancelling an approved booking is the one transition out of
    confirmed — it triggers the tiered refund."""
    assert can_transition(CONFIRMED, CANCELLED)
    assert not can_transition(CONFIRMED, DECLINED)
    assert not can_transition(CONFIRMED, EXPIRED)


@pytest.mark.parametrize(
    "current,target",
    [
        (CONFIRMED, DECLINED),
        (CONFIRMED, CONFIRMED),
        (CONFIRMED, EXPIRED),
        (DECLINED, CONFIRMED),
        (DECLINED, DECLINED),
        (EXPIRED, CONFIRMED),
        (PENDING, PENDING),
        (CANCELLED, CONFIRMED),
        (CANCELLED, CANCELLED),
    ],
)
def test_terminal_states_cannot_transition(current, target):
    assert not can_transition(current, target)
    with pytest.raises(InvalidTransitionError):
        assert_transition(current, target)


def test_double_approve_is_rejected():
    """The v1 prototype allowed calling /approve on an already-confirmed
    (or even already-declined) reservation. This must now be rejected."""
    with pytest.raises(InvalidTransitionError):
        assert_transition(CONFIRMED, CONFIRMED)
    with pytest.raises(InvalidTransitionError):
        assert_transition(DECLINED, CONFIRMED)


def test_is_hold_expired_true_when_past_deadline():
    now = datetime(2026, 1, 2, 12, 0, 0)
    hold_expires_at = datetime(2026, 1, 2, 0, 0, 0)
    assert is_hold_expired(PENDING, hold_expires_at, now)


def test_is_hold_expired_false_when_before_deadline():
    now = datetime(2026, 1, 1, 0, 0, 0)
    hold_expires_at = now + timedelta(hours=24)
    assert not is_hold_expired(PENDING, hold_expires_at, now)


def test_is_hold_expired_false_for_non_pending_status():
    now = datetime(2026, 1, 5, 0, 0, 0)
    hold_expires_at = datetime(2026, 1, 1, 0, 0, 0)
    assert not is_hold_expired(CONFIRMED, hold_expires_at, now)
