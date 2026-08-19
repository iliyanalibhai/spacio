// `new Date("2026-09-01").toLocaleDateString()` parses date-only strings as
// UTC midnight, then formats in the browser's local timezone — anywhere
// west of UTC that renders as the previous day. The backend's `startDate`/
// `endDate` fields are calendar dates (Python `date`, no time component),
// so parse the components directly instead of going through UTC.
export function formatDateOnly(isoDate: string): string {
  const [year, month, day] = isoDate.split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString();
}
