import { describe, expect, it } from "vitest";
import { formatDateOnly } from "./formatDate";

describe("formatDateOnly", () => {
  it("does not shift the date backward regardless of local timezone", () => {
    // new Date("2026-09-01").toLocaleDateString() shifts to 8/31 in any
    // timezone behind UTC — this must stay on the 1st.
    expect(formatDateOnly("2026-09-01")).toBe(new Date(2026, 8, 1).toLocaleDateString());
  });

  it("formats a date near a month boundary correctly", () => {
    expect(formatDateOnly("2026-01-31")).toBe(new Date(2026, 0, 31).toLocaleDateString());
  });
});
