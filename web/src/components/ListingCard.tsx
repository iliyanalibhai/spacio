import type { Listing } from "../types";
import { getListingImage, fallbackListingImage } from "../lib/getListingImage";

export function ListingCard({
  listing,
  index,
  onClick,
}: {
  listing: Listing;
  index: number;
  onClick: () => void;
}) {
  const imageUrl = getListingImage(listing, index);
  const availableSqft = listing.availableSqft ?? listing.sizeSqft ?? 100;

  return (
    <div onClick={onClick} className="group cursor-pointer">
      <div className="relative aspect-[4/3] overflow-hidden rounded-2xl bg-slate-100">
        <img
          src={imageUrl}
          alt={listing.title}
          className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
          onError={(e) => {
            (e.target as HTMLImageElement).src = fallbackListingImage();
          }}
        />
        {listing.hostVerified && (
          <span className="absolute top-3 left-3 inline-flex items-center gap-1 rounded-full bg-white/90 backdrop-blur-sm px-2.5 py-1 text-xs font-semibold text-slate-700 shadow-sm">
            <svg className="h-3.5 w-3.5 text-emerald-500" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            Verified
          </span>
        )}
      </div>
      <div className="mt-3">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-slate-900 group-hover:text-brand-600 transition-colors">
            {listing.title}
          </h3>
          {listing.rating != null && (
            <div className="flex items-center gap-1 text-sm">
              <svg className="h-4 w-4 text-amber-500" fill="currentColor" viewBox="0 0 20 20">
                <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
              </svg>
              <span className="font-medium">{listing.rating}</span>
              {!!listing.reviewCount && <span className="text-slate-400">({listing.reviewCount})</span>}
            </div>
          )}
        </div>
        <p className="text-slate-500 text-sm mt-0.5">{listing.addressSummary}</p>
        <p className="text-slate-500 text-sm">
          {listing.sizeSqft ? `${listing.sizeSqft} sqft total` : listing.size} • {listing.zipCode}
        </p>
        <p className="text-sm mt-1">
          <span className={`font-medium ${availableSqft > 0 ? "text-emerald-600" : "text-red-500"}`}>
            {availableSqft} sqft available
          </span>
        </p>
        <p className="mt-2">
          <span className="font-semibold text-slate-900">${listing.pricePerMonth}</span>
          <span className="text-slate-500"> / month (full space)</span>
        </p>
      </div>
    </div>
  );
}
