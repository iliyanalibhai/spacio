import { useQuery } from "@tanstack/react-query";
import type { Listing } from "../types";
import * as listingApi from "../api/listings";
import { ListingCard } from "./ListingCard";

const FEATURED_COUNT = 6;

type Props = {
  onSelect: (listing: Listing) => void;
};

// Shown on the landing page before any search — an empty page until you
// type something was the single biggest reason it read as unfinished (see
// docs/DOCUMENTATION.md §10). GET /listings with no params already returns
// everything unfiltered (api/app/routers/listings.py's `origin` stays None
// and `filters` stays empty), so this needed no backend change.
export function FeaturedListings({ onSelect }: Props) {
  const { data: listings = [], isLoading } = useQuery({
    queryKey: ["listings", "featured"],
    queryFn: () => listingApi.fetchListings({}),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600"></div>
      </div>
    );
  }

  if (listings.length === 0) {
    return null;
  }

  const featured = listings.slice(0, FEATURED_COUNT);

  return (
    <section>
      <div className="flex items-end justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Available now</h2>
          <p className="text-slate-600">A few spaces near our host communities.</p>
        </div>
      </div>
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {featured.map((listing, index) => (
          <ListingCard key={listing._id} listing={listing} index={index} onClick={() => onSelect(listing)} />
        ))}
      </div>
    </section>
  );
}
