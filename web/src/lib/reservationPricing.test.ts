import { describe, expect, it } from "vitest";
import { insuranceMonthlyCost, quoteReservation } from "./reservationPricing";

describe("quoteReservation", () => {
  it("matches the reference unit economics: full space, full month", () => {
    const quote = quoteReservation({
      hostMonthlyPrice: 40,
      totalSqft: 100,
      sqftRequested: 100,
      startDate: "2026-01-01",
      endDate: "2026-01-31",
      numBoxes: 0,
      insuranceDeclaredValue: null,
      hasOwnInsurance: false,
    });
    expect(quote).not.toBeNull();
    expect(quote!.days).toBe(30);
    expect(quote!.base).toBe(40);
    expect(quote!.serviceFee).toBe(8);
    expect(quote!.boxCost).toBe(0);
    expect(quote!.insuranceCost).toBe(0);
    expect(quote!.total).toBe(48);
  });

  it("prorates base price by both space and time", () => {
    const quote = quoteReservation({
      hostMonthlyPrice: 100,
      totalSqft: 200,
      sqftRequested: 100,
      startDate: "2026-01-01",
      endDate: "2026-01-16",
      numBoxes: 0,
      insuranceDeclaredValue: null,
      hasOwnInsurance: false,
    });
    expect(quote!.days).toBe(15);
    expect(quote!.spaceRatioPct).toBe(50);
    expect(quote!.base).toBeCloseTo(100 * 0.5 * (15 / 30), 2);
  });

  it("charges $10/box, prorated for a full month", () => {
    const quote = quoteReservation({
      hostMonthlyPrice: 40,
      totalSqft: 100,
      sqftRequested: 100,
      startDate: "2026-01-01",
      endDate: "2026-01-31",
      numBoxes: 2,
      insuranceDeclaredValue: null,
      hasOwnInsurance: false,
    });
    expect(quote!.boxCost).toBe(20);
    expect(quote!.total).toBe(40 + 8 + 20);
  });

  it("waives the insurance charge when the renter has their own insurance", () => {
    const quote = quoteReservation({
      hostMonthlyPrice: 40,
      totalSqft: 100,
      sqftRequested: 100,
      startDate: "2026-01-01",
      endDate: "2026-01-31",
      numBoxes: 0,
      insuranceDeclaredValue: 2000,
      hasOwnInsurance: true,
    });
    expect(quote!.insuranceCost).toBe(0);
  });

  it("prorates the insurance cost by stay length", () => {
    const quote = quoteReservation({
      hostMonthlyPrice: 40,
      totalSqft: 100,
      sqftRequested: 100,
      startDate: "2026-01-01",
      endDate: "2026-01-16", // 15 days = half a month
      numBoxes: 0,
      insuranceDeclaredValue: 500,
      hasOwnInsurance: false,
    });
    expect(quote!.insuranceCost).toBeCloseTo(12 * 0.5, 2);
  });

  it("returns null when the date range is empty or inverted", () => {
    expect(
      quoteReservation({
        hostMonthlyPrice: 40,
        totalSqft: 100,
        sqftRequested: 100,
        startDate: "2026-01-10",
        endDate: "2026-01-01",
        numBoxes: 0,
        insuranceDeclaredValue: null,
        hasOwnInsurance: false,
      }),
    ).toBeNull();
  });

  it("returns null when no space is requested", () => {
    expect(
      quoteReservation({
        hostMonthlyPrice: 40,
        totalSqft: 100,
        sqftRequested: 0,
        startDate: "2026-01-01",
        endDate: "2026-01-31",
        numBoxes: 0,
        insuranceDeclaredValue: null,
        hasOwnInsurance: false,
      }),
    ).toBeNull();
  });
});

describe("insuranceMonthlyCost", () => {
  it.each([
    [0, 12],
    [1000, 12],
    [1000.01, 20],
    [3000, 20],
    [3000.01, 30],
    [5000, 30],
    [5000.01, 45],
    [10000, 45],
  ])("declared value %d -> $%d/mo", (declaredValue, expected) => {
    expect(insuranceMonthlyCost(declaredValue)).toBe(expected);
  });

  it("returns null above the highest tier, deferring to the server to reject", () => {
    expect(insuranceMonthlyCost(10_000.01)).toBeNull();
  });
});
