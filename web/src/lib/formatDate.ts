// `new Date("2026-09-01").toLocaleDateString()` parses date-only strings as
// UTC midnight, then formats in the browser's local timezone — anywhere
// west of UTC that renders as the previous day. The backend's `startDate`/
// `endDate` fields are calendar dates (Python `date`, no time component),
// so parse the components directly instead of going through UTC.
//
// Some fields (e.g. `ListingPublic.availableFrom`, typed `Optional[datetime]`
// in schemas.py) serialize with a time component instead — "2026-09-01
// T00:00:00" — which would otherwise split into ["2026","09","01T00:00:00"]
// and produce Invalid Date (`Number("01T00:00:00")` is NaN). Strip anything
// from "T" onward first so every caller is covered, not just the ones that
// happen to pass a bare date already.
export function formatDateOnly(isoDate: string): string {
  const [year, month, day] = isoDate.split("T")[0].split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString();
}
