"""Reservation state machine.

    pending_host_confirmation --> confirmed   (host approves)
    pending_host_confirmation --> declined    (host declines)
    pending_host_confirmation --> expired     (24h hold elapses, no action)

confirmed, declined, and expired are terminal. The v1 prototype didn't
enforce this — you could call /approve on an already-declined reservation.

The 24-hour auto-expiry check (is_hold_expired) is pure and tested here, but
nothing calls it on a schedule yet; wiring a background job is Phase 4 (see
docs/DOCUMENTATION.md §11).
"""

from datetime import datetime

from app.models.schemas import ReservationStatus

VALID_TRANSITIONS: dict[ReservationStatus, frozenset[ReservationStatus]] = {
    ReservationStatus.pending: frozenset(
        {ReservationStatus.confirmed, ReservationStatus.declined, ReservationStatus.expired}
    ),
    ReservationStatus.confirmed: frozenset(),
    ReservationStatus.declined: frozenset(),
    ReservationStatus.expired: frozenset(),
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
