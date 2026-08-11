import type { Listing } from "../types";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

// v1 hardcoded http://127.0.0.1:8000 in six places here, breaking every
// image on any deployment other than a developer's own machine (defect #5).
// This is the only place that URL gets built now, from VITE_API_URL.
export function getListingImage(listing: Listing | undefined, fallbackIndex = 0): string {
  if (listing?.images?.[0]) {
    return listing.images[0].startsWith("/")
      ? `${API_URL}${listing.images[0]}`
      : listing.images[0];
  }

  const text = `${listing?.title || ""} ${listing?.description || ""}`.toLowerCase();
  if (
    text.includes("closet") ||
    text.includes("room") ||
    text.includes("indoor") ||
    text.includes("nook")
  ) {
    return `${API_URL}/images/closet-img.webp`;
  }
  if (text.includes("garage") || text.includes("parking") || text.includes("outdoor")) {
    return `${API_URL}/images/garage-img.jpg`;
  }

  return fallbackIndex % 2 === 0
    ? `${API_URL}/images/garage-img.jpg`
    : `${API_URL}/images/closet-img.webp`;
}

export function fallbackListingImage(): string {
  return `${API_URL}/images/garage-img.jpg`;
}
