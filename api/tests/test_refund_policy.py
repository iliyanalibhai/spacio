"""Pure unit tests for the tiered renter-cancellation refund policy
(app/services/refund_policy.py)."""

from datetime import datetime, timedelta

import pytest

from app.services.refund_policy import (
    FULL_REFUND_CUTOFF_HOURS,
    CancellationNotAllowedError,
    decide_refund,
)

START = datetime(2026, 6, 1, 0, 0, 0)


def test_full_refund_well_before_start():
    decision = decide_refund(200.0, START, START - timedelta(days=10))
    assert decision.tier == "full"
    assert decision.refund_rate == 1.0
    assert decision.refund_amount == 200.0
    assert decision.refund_cents == 20000


def test_full_refund_exactly_at_the_cutoff():
    now = START - timedelta(hours=FULL_REFUND_CUTOFF_HOURS)
    decision = decide_refund(200.0, START, now)
    assert decision.tier == "full"


def test_partial_refund_just_inside_the_window():
    now = START - timedelta(hours=FULL_REFUND_CUTOFF_HOURS) + timedelta(minutes=1)
    decision = decide_refund(200.0, START, now)
    assert decision.tier == "partial"
    assert decision.refund_rate == 0.5
    assert decision.refund_amount == 100.0
    assert decision.refund_cents == 10000


def test_partial_refund_rounds_to_whole_cents():
    # 149.99 * 0.5 = 74.995 -> 7500 cents
    decision = decide_refund(149.99, START, START - timedelta(hours=1))
    assert decision.refund_cents == 7500
    assert decision.refund_amount == 75.0


def test_no_cancellation_once_started():
    with pytest.raises(CancellationNotAllowedError):
        decide_refund(200.0, START, START)
    with pytest.raises(CancellationNotAllowedError):
        decide_refund(200.0, START, START + timedelta(hours=1))


def test_reason_string_mentions_the_cutoff():
    full = decide_refund(10.0, START, START - timedelta(days=5))
    partial = decide_refund(10.0, START, START - timedelta(hours=2))
    assert str(FULL_REFUND_CUTOFF_HOURS) in full.reason
    assert str(FULL_REFUND_CUTOFF_HOURS) in partial.reason
