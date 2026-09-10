"""Refund policy for a renter cancelling a *confirmed* reservation.

Tiered, matching the cancellation terms already shown to renters in the
booking UI (`web/src/components/ListingDetailModal.tsx`) and mirrored
client-side in `web/src/lib/refundPolicy.ts`:

    cancel >= 72h before the start date  -> 100% refund
    cancel  < 72h before the start date  ->  50% refund
    cancel on/after the start date       -> no self-serve cancellation

The refund is a fraction of the whole reservation total, Spacio's service
fee included — the fee comes back at the same rate as everything else, so a
50% refund also returns half the fee. On the Stripe side a single partial
`Refund` with `refund_application_fee=True` + `reverse_transfer=True` makes
Stripe apply that same proportion to the platform fee and to the transfer
already sent to the host (see
`services.reservation_payments.refund_reservation_payment`).

Pure and side-effect-free so it can be unit tested directly; the router
(`reservations.cancel_reservation`) turns a `RefundDecision` into the Stripe
call and the status write.
"""

from dataclasses import dataclass
from datetime import datetime

# Hours before the start date up to which a cancellation is still "free"
# (full refund). Inside this window the renter gets PARTIAL_REFUND_RATE.
FULL_REFUND_CUTOFF_HOURS = 72
PARTIAL_REFUND_RATE = 0.5


class CancellationNotAllowedError(Exception):
    """The reservation has already started — no self-serve cancellation."""


@dataclass(frozen=True)
class RefundDecision:
    tier: str  # "full" | "partial"
    refund_rate: float  # 1.0 | 0.5
    refund_amount: float  # dollars, rounded to whole cents
    refund_cents: int  # what to pass to stripe.Refund.create(amount=...)
    reason: str


def decide_refund(total_price: float, start: datetime, now: datetime) -> RefundDecision:
    """Return how much of ``total_price`` to refund for a cancellation at
    ``now`` against a reservation starting at ``start``. Raises
    ``CancellationNotAllowedError`` once the start date has passed."""
    if now >= start:
        raise CancellationNotAllowedError(
            "This reservation has already started. Contact support to cancel."
        )

    hours_until_start = (start - now).total_seconds() / 3600
    if hours_until_start >= FULL_REFUND_CUTOFF_HOURS:
        rate = 1.0
        tier = "full"
        reason = f"Cancelled {FULL_REFUND_CUTOFF_HOURS}+ hours before the start date."
    else:
        rate = PARTIAL_REFUND_RATE
        tier = "partial"
        reason = (
            f"Cancelled less than {FULL_REFUND_CUTOFF_HOURS} hours before the start date."
        )

    cents = round(total_price * rate * 100)
    return RefundDecision(
        tier=tier,
        refund_rate=rate,
        refund_amount=cents / 100,
        refund_cents=cents,
        reason=reason,
    )
