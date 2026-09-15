import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { Listing } from "../types";
import * as listingApi from "../api/listings";
import { ListingDetailModal } from "../components/ListingDetailModal";
import { SearchHero, type SearchFilters } from "../components/SearchHero";
import { SearchResults } from "../components/SearchResults";
import { HowItWorks } from "../components/HowItWorks";

export function Landing() {
  const [filters, setFilters] = useState<SearchFilters>({ radiusMiles: 25 });
  const [selected, setSelected] = useState<Listing | null>(null);
  const [showPaymentSuccess, setShowPaymentSuccess] = useState(false);
  const [geoError, setGeoError] = useState<string | null>(null);

  const usingMyLocation = filters.lat != null && filters.lng != null;
  const shouldSearch = (filters.zipCode?.length ?? 0) >= 1 || usingMyLocation;
  const origin = usingMyLocation ? { lat: filters.lat!, lng: filters.lng! } : null;

  const { data: listings = [], isLoading } = useQuery({
    queryKey: ["listings", filters],
    queryFn: () => listingApi.fetchListings(filters),
    enabled: shouldSearch,
  });

  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get("payment") === "success") {
      setShowPaymentSuccess(true);
      window.history.replaceState({}, "", "/");
      setTimeout(() => setShowPaymentSuccess(false), 5000);
    }
  }, []);

  const useMyLocation = () => {
    setGeoError(null);
    if (!navigator.geolocation) {
      setGeoError("Your browser can't share a location.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) =>
        setFilters((f) => ({
          ...f,
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
        })),
      () => setGeoError("Couldn't get your location. Try a ZIP code instead."),
      { timeout: 10000 }
    );
  };

  const clearMyLocation = () => setFilters((f) => ({ ...f, lat: undefined, lng: undefined }));

  return (
    <main className="min-h-screen bg-gradient-to-b from-slate-50 to-white">
      {showPaymentSuccess && (
        <div className="bg-emerald-500 text-white py-3 px-4">
          <div className="mx-auto max-w-6xl flex items-center gap-3">
            <span className="font-medium">Payment successful! Your reservation is confirmed.</span>
          </div>
        </div>
      )}

      <SearchHero
        filters={filters}
        setFilters={setFilters}
        isLoading={isLoading}
        usingMyLocation={usingMyLocation}
        onUseMyLocation={useMyLocation}
        onClearMyLocation={clearMyLocation}
        geoError={geoError}
      />

      <div className="mx-auto max-w-6xl px-4 pb-12 pt-8 bg-slate-50">
        {shouldSearch ? (
          <SearchResults
            listings={listings}
            isLoading={isLoading}
            filters={filters}
            setFilters={setFilters}
            usingMyLocation={usingMyLocation}
            origin={origin}
            onSelect={setSelected}
          />
        ) : (
          <HowItWorks />
        )}

        {selected && (
          <ListingDetailModal
            listing={selected}
            onClose={() => setSelected(null)}
            searchDates={{ startDate: filters.startDate, endDate: filters.endDate }}
          />
        )}
      </div>
    </main>
  );
}
