import { describe, expect, it } from "vitest";
import { boundsFromPoints, formatDistance, metersToMiles } from "./geo";

describe("metersToMiles", () => {
  it("converts a mile of meters back to ~1", () => {
    expect(metersToMiles(1609.344)).toBeCloseTo(1, 6);
  });
});

describe("formatDistance", () => {
  it("keeps one decimal under 10 miles", () => {
    expect(formatDistance(0.42)).toBe("0.4 mi away");
    expect(formatDistance(3.55)).toBe("3.6 mi away");
  });

  it("rounds to whole miles past 10", () => {
    expect(formatDistance(12.4)).toBe("12 mi away");
    expect(formatDistance(180.9)).toBe("181 mi away");
  });

  it("has a floor label for effectively-zero distance", () => {
    expect(formatDistance(0)).toBe("less than 0.1 mi away");
  });

  it("returns null for missing/invalid input", () => {
    expect(formatDistance(null)).toBeNull();
    expect(formatDistance(undefined)).toBeNull();
    expect(formatDistance(NaN)).toBeNull();
  });
});

describe("boundsFromPoints", () => {
  it("returns null when there are no valid points", () => {
    expect(boundsFromPoints([])).toBeNull();
    expect(boundsFromPoints([null, undefined])).toBeNull();
    expect(boundsFromPoints([{ lat: NaN, lng: 0 }])).toBeNull();
  });

  it("returns a degenerate box for a single point", () => {
    expect(boundsFromPoints([{ lat: 30.3, lng: -97.7 }])).toEqual([
      [30.3, -97.7],
      [30.3, -97.7],
    ]);
  });

  it("spans [[south, west], [north, east]] across many points", () => {
    const bounds = boundsFromPoints([
      { lat: 30.29, lng: -97.74 },
      { lat: 32.78, lng: -96.8 },
      { lat: 29.42, lng: -98.49 },
    ]);
    expect(bounds).toEqual([
      [29.42, -98.49],
      [32.78, -96.8],
    ]);
  });

  it("ignores nulls mixed in with real points", () => {
    const bounds = boundsFromPoints([
      { lat: 30, lng: -97 },
      null,
      { lat: 31, lng: -96 },
    ]);
    expect(bounds).toEqual([
      [30, -97],
      [31, -96],
    ]);
  });
});
