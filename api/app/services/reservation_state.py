"""Reservation state machine.

    pending_host_confirmation --> confirmed   (host approves)
    pending_host_confirmation --> declined    (host declines)
    pending_host_confirmation --> expired     (24h hold elapses, no action)
    pending_host_confirmation --> cancelled   (renter backs out before approval)
    confirmed                 --> cancelled   (renter cancels an approved booking)

declined, expired, and cancelled are terminal; confirmed is terminal
*except* for a renter-initiated cancellation, which triggers the tiered
refund in services/refund_policy.py. The v1 prototype didn't enforce
terminality at all — you could call /approve on an already-declined
reservation.

The 24-hour auto-expiry check (is_hold_expired) is pure and tested here and
runs on a schedule via services/hold_expiry.py.
"""

from datetime import datetime

from app.models.schemas import ReservationStatus

VALID_TRANSITIONS: dict[ReservationStatus, frozenset[ReservationStatus]] = {
    ReservationStatus.pending: frozenset(
        {
            ReservationStatus.confirmed,
            ReservationStatus.declined,
            ReservationStatus.expired,
            ReservationStatus.cancelled,
        }
    ),
    ReservationStatus.confirmed: frozenset({ReservationStatus.cancelled}),
    ReservationStatus.declined: frozenset(),
    ReservationStatus.expired: frozenset(),
    ReservationStatus.cancelled: frozenset(),
}


class InvalidTransitionError(ValueError):
    pass


def can_transition(current: ReservationStatus, target: ReservationStatus) -> bool:
    return target in VALID_TRANSITIONS.get(current, frozenset())


def assert_transition(current: ReservationStatus, target: ReservationStatus) -> None:
    if not can_transition(current, target):
        raise InvalidTransitionError(
            f"Cannot transition reservation from {current.value} to {target.value}"
        )


def is_hold_expired(status: ReservationStatus, hold_expires_at: datetime, now: datetime) -> bool:
    return status == ReservationStatus.pending and now >= hold_expires_at
