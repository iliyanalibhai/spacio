import type { Listing } from "../types";
import { getListingImage } from "../lib/getListingImage";

export function MatchResultCard({ listing }: { listing: Listing }) {
  return (
    <div className="group overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm transition hover:-translate-y-1 hover:shadow-lg">
      <div
        className="h-32 w-full bg-cover bg-center"
        style={{ backgroundImage: `url(${getListingImage(listing)})` }}
      />
      <div className="p-4">
        <div className="flex items-center justify-between text-xs text-slate-500">
          <span className="uppercase tracking-wide text-brand-600">
            {listing.sizeSqft ? `${listing.sizeSqft} sqft` : listing.size} • {listing.zipCode}
          </span>
          {listing.rating != null && <span className="text-amber-600">★ {listing.rating}</span>}
        </div>
        <h3 className="mt-1 text-lg font-semibold text-slate-900">{listing.title}</h3>
        <p className="text-sm text-slate-600 line-clamp-2">{listing.description}</p>
        <p className="mt-2 text-sm text-slate-500">{listing.addressSummary}</p>
        <div className="mt-3 flex items-center justify-between">
          <span className="text-lg font-semibold text-slate-900">${listing.pricePerMonth}/mo</span>
        </div>
      </div>
    </div>
  );
}
