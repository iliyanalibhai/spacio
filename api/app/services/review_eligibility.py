"""Review eligibility rules.

A renter may review a reservation once it actually happened: the host must
have approved it (status == confirmed) and the stay must be over
(endDate has passed) — reviewing before check-out would let a renter rate a
stay that hasn't happened yet. Reviews are scoped to a reservation, not a
listing, so a renter who books the same listing again gets a separate,
independent chance to review that stay too; exactly-one-review-per-stay is
enforced by a unique index on `reviews.reservationId` (see app/db.py), not
here — this module only decides whether attempting one is allowed at all.
"""

from datetime import datetime

from app.models.schemas import ReservationStatus


class ReviewNotAllowedError(ValueError):
    pass


def assert_can_review(reservation: dict, renter_id: str, now: datetime) -> None:
    if reservation.get("renterId") != renter_id:
        raise ReviewNotAllowedError("You can only review your own reservations")
    if reservation.get("status") != ReservationStatus.confirmed:
        raise ReviewNotAllowedError("Only confirmed reservations can be reviewed")
    if reservation["endDate"] > now:
        raise ReviewNotAllowedError("You can review a stay once it has ended")
