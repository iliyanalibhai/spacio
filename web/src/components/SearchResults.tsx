import type { Listing, StorageSize } from "../types";
import { ListingCard } from "./ListingCard";
import { ResultsMap } from "./ResultsMap";
import { formatDateOnly } from "../lib/formatDate";
import type { SearchFilters } from "./SearchHero";

type Props = {
  listings: Listing[];
  isLoading: boolean;
  filters: SearchFilters;
  setFilters: (update: (f: SearchFilters) => SearchFilters) => void;
  usingMyLocation: boolean;
  origin: { lat: number; lng: number } | null;
  onSelect: (listing: Listing) => void;
};

export function SearchResults({
  listings,
  isLoading,
  filters,
  setFilters,
  usingMyLocation,
  origin,
  onSelect,
}: Props) {
  return (
    <section>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">
            {isLoading ? "Searching..." : `${listings.length} ${listings.length === 1 ? "space" : "spaces"} available`}
          </h2>
          <p className="text-slate-600">
            {usingMyLocation
              ? `within ${filters.radiusMiles} miles of you`
              : filters.zipCode && `within ${filters.radiusMiles} miles of ${filters.zipCode}`}
            {filters.startDate &&
              filters.endDate &&
              ` • ${formatDateOnly(filters.startDate)} - ${formatDateOnly(filters.endDate)}`}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={filters.size || ""}
            onChange={(e) => setFilters((f) => ({ ...f, size: (e.target.value as StorageSize) || undefined }))}
            className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium shadow-sm hover:shadow transition"
          >
            <option value="">Any size</option>
            <option value="S">Small</option>
            <option value="M">Medium</option>
            <option value="L">Large</option>
          </select>
        </div>
      </div>
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600"></div>
        </div>
      ) : listings.length > 0 ? (
        <div className="grid gap-6 lg:grid-cols-[1fr_minmax(340px,400px)]">
          <div className="order-2 lg:order-1 grid gap-6 sm:grid-cols-2 lg:grid-cols-1">
            {listings.map((listing, index) => (
              <ListingCard key={listing._id} listing={listing} index={index} onClick={() => onSelect(listing)} />
            ))}
          </div>
          <div className="order-1 lg:order-2">
            <div className="h-64 lg:sticky lg:top-24 lg:h-[calc(100vh-8rem)]">
              <ResultsMap listings={listings} origin={origin} onSelect={onSelect} />
            </div>
          </div>
        </div>
      ) : (
        <div className="text-center py-12">
          <h3 className="mt-4 text-lg font-semibold text-slate-900">No spaces available</h3>
          <p className="mt-1 text-slate-500">Try a wider radius, different dates, or another area.</p>
        </div>
      )}
    </section>
  );
}
