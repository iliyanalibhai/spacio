// Small geo helpers for the results map. Pure functions, no Leaflet import,
// so they unit-test without a DOM.

export type LatLng = { lat: number; lng: number };

export function metersToMiles(meters: number): number {
  return meters / 1609.344;
}

/**
 * Human-friendly distance label. Under 10 miles we keep one decimal ("0.4 mi
 * away"); beyond that the fraction is noise, so round to whole miles.
 */
export function formatDistance(miles: number | null | undefined): string | null {
  if (miles == null || Number.isNaN(miles)) return null;
  if (miles < 0.1) return "less than 0.1 mi away";
  const rounded = miles < 10 ? Math.round(miles * 10) / 10 : Math.round(miles);
  return `${rounded} mi away`;
}

/**
 * Bounding box covering every point, as Leaflet's
 * [[south, west], [north, east]] tuple — or null when there's nothing to fit.
 * A single point yields a degenerate box; callers pad it (fitBounds accepts a
 * padding option, or set a maxZoom).
 */
export function boundsFromPoints(
  points: Array<LatLng | null | undefined>
): [[number, number], [number, number]] | null {
  const valid = points.filter(
    (p): p is LatLng =>
      !!p && Number.isFinite(p.lat) && Number.isFinite(p.lng)
  );
  if (valid.length === 0) return null;

  let south = valid[0].lat;
  let north = valid[0].lat;
  let west = valid[0].lng;
  let east = valid[0].lng;
  for (const p of valid) {
    south = Math.min(south, p.lat);
    north = Math.max(north, p.lat);
    west = Math.min(west, p.lng);
    east = Math.max(east, p.lng);
  }
  return [
    [south, west],
    [north, east],
  ];
}
