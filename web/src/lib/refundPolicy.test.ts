import { describe, expect, it } from "vitest";
import { estimateRefund, FULL_REFUND_CUTOFF_HOURS } from "./refundPolicy";

const START = "2026-06-01"; // UTC midnight
const startMs = new Date(`${START}T00:00:00Z`).getTime();

describe("estimateRefund", () => {
  it("full refund well before the start date", () => {
    const now = new Date(startMs - 10 * 24 * 3_600_000);
    const estimate = estimateRefund(START, 200, now);
    expect(estimate.tier).toBe("full");
    expect(estimate.refundAmount).toBe(200);
  });

  it("full refund exactly at the 72h cutoff", () => {
    const now = new Date(startMs - FULL_REFUND_CUTOFF_HOURS * 3_600_000);
    expect(estimateRefund(START, 200, now).tier).toBe("full");
  });

  it("half refund just inside the window", () => {
    const now = new Date(startMs - (FULL_REFUND_CUTOFF_HOURS - 1) * 3_600_000);
    const estimate = estimateRefund(START, 200, now);
    expect(estimate.tier).toBe("partial");
    expect(estimate.refundAmount).toBe(100);
  });

  it("half refund rounds to whole cents", () => {
    const now = new Date(startMs - 3_600_000);
    expect(estimateRefund(START, 149.99, now).refundAmount).toBe(75);
  });

  it("no refund once the start date has passed", () => {
    const now = new Date(startMs + 3_600_000);
    const estimate = estimateRefund(START, 200, now);
    expect(estimate.tier).toBe("none");
    expect(estimate.refundAmount).toBe(0);
  });
});
