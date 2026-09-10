// Client-side mirror of api/app/services/refund_policy.py, used only to
// tell the renter what refund to expect *before* they confirm a
// cancellation. The server recomputes and is the source of truth. Keep the
// two tiers in sync with the backend if the policy changes.

export const FULL_REFUND_CUTOFF_HOURS = 72;
export const PARTIAL_REFUND_RATE = 0.5;

export type RefundEstimate = {
  tier: "full" | "partial" | "none";
  refundAmount: number;
  message: string;
};

// `startDate` is a date-only string ("2026-06-01"); the backend treats it
// as UTC midnight, so parse it the same way rather than in local time.
export function estimateRefund(startDate: string, totalPrice: number, now: Date = new Date()): RefundEstimate {
  const start = new Date(`${startDate}T00:00:00Z`);
  const hoursUntilStart = (start.getTime() - now.getTime()) / 3_600_000;

  if (hoursUntilStart <= 0) {
    return {
      tier: "none",
      refundAmount: 0,
      message: "This reservation has already started — contact support to cancel.",
    };
  }
  if (hoursUntilStart >= FULL_REFUND_CUTOFF_HOURS) {
    return {
      tier: "full",
      refundAmount: totalPrice,
      message: `You'll be refunded the full $${totalPrice.toFixed(2)}.`,
    };
  }
  const refundAmount = Math.round(totalPrice * PARTIAL_REFUND_RATE * 100) / 100;
  return {
    tier: "partial",
    refundAmount,
    message: `It's less than ${FULL_REFUND_CUTOFF_HOURS} hours before your start date, so you'll be refunded 50% ($${refundAmount.toFixed(
      2,
    )}).`,
  };
}
