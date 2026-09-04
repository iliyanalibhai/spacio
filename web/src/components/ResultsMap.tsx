import { useEffect } from "react";
import L from "leaflet";
import { MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import markerIcon2x from "leaflet/dist/images/marker-icon-2x.png";
import markerIcon from "leaflet/dist/images/marker-icon.png";
import markerShadow from "leaflet/dist/images/marker-shadow.png";
import type { Listing } from "../types";
import { boundsFromPoints, formatDistance } from "../lib/geo";

// Leaflet's default marker icon resolves its PNGs from a CSS-derived
// `imagePath` that points into node_modules and breaks under a bundler. Build
// the icon explicitly from Vite-resolved asset URLs and hand it to every
// Marker, so none of that auto-detection runs.
const markerIconInstance = L.icon({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

type MappableListing = Listing & { lat: number; lng: number };

function hasCoords(listing: Listing): listing is MappableListing {
  return typeof listing.lat === "number" && typeof listing.lng === "number";
}

/** Keeps the viewport framed on the current results (and the search origin). */
function FitBounds({ points }: { points: Array<{ lat: number; lng: number }> }) {
  const map = useMap();
  useEffect(() => {
    const bounds = boundsFromPoints(points);
    if (!bounds) return;
    map.fitBounds(bounds, { padding: [48, 48], maxZoom: 14 });
  }, [map, points]);
  return null;
}

export function ResultsMap({
  listings,
  origin,
  onSelect,
}: {
  listings: Listing[];
  origin?: { lat: number; lng: number } | null;
  onSelect: (listing: Listing) => void;
}) {
  const mappable = listings.filter(hasCoords);
  const points = [
    ...mappable.map((l) => ({ lat: l.lat, lng: l.lng })),
    ...(origin ? [origin] : []),
  ];

  // A sensible first frame before FitBounds runs: the origin, else the first
  // result, else the middle of the continental US.
  const initialCenter: [number, number] = origin
    ? [origin.lat, origin.lng]
    : mappable[0]
    ? [mappable[0].lat, mappable[0].lng]
    : [39.5, -98.35];

  if (mappable.length === 0) {
    return (
      <div className="flex h-full items-center justify-center rounded-2xl border border-slate-200 bg-slate-50 text-sm text-slate-500">
        No mapped locations for these results.
      </div>
    );
  }

  return (
    <MapContainer
      center={initialCenter}
      zoom={11}
      scrollWheelZoom
      className="h-full w-full rounded-2xl"
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <FitBounds points={points} />
      {mappable.map((listing) => (
        <Marker
          key={listing._id}
          position={[listing.lat, listing.lng]}
          icon={markerIconInstance}
        >
          <Popup>
            <button
              type="button"
              onClick={() => onSelect(listing)}
              className="text-left"
            >
              <span className="block font-semibold text-slate-900">{listing.title}</span>
              <span className="block text-slate-600">
                ${listing.pricePerMonth}/mo · {listing.addressSummary}
              </span>
              {formatDistance(listing.distanceMiles) && (
                <span className="block text-slate-500">
                  {formatDistance(listing.distanceMiles)}
                </span>
              )}
              <span className="mt-1 block font-medium text-brand-600">View details</span>
            </button>
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}
