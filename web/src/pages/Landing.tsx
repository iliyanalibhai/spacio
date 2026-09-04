import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { Listing, StorageSize } from "../types";
import * as listingApi from "../api/listings";
import { ListingCard } from "../components/ListingCard";
import { ListingDetailModal } from "../components/ListingDetailModal";
import { ResultsMap } from "../components/ResultsMap";
import { formatDateOnly } from "../lib/formatDate";

type Filters = {
  zipCode?: string;
  startDate?: string;
  endDate?: string;
  priceMin?: number;
  priceMax?: number;
  size?: StorageSize;
  lat?: number;
  lng?: number;
  radiusMiles: number;
};

const RADIUS_OPTIONS = [5, 10, 25, 50];

export function Landing() {
  const [filters, setFilters] = useState<Filters>({ radiusMiles: 25 });
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

  const clearMyLocation = () =>
    setFilters((f) => ({ ...f, lat: undefined, lng: undefined }));

  return (
    <main className="min-h-screen bg-gradient-to-b from-slate-50 to-white">
      {showPaymentSuccess && (
        <div className="bg-emerald-500 text-white py-3 px-4">
          <div className="mx-auto max-w-6xl flex items-center gap-3">
            <span className="font-medium">Payment successful! Your reservation is confirmed.</span>
          </div>
        </div>
      )}

      <div className="relative min-h-[380px]">
        <div
          className="absolute inset-0 h-[380px] bg-cover bg-center"
          style={{
            backgroundImage:
              "url('https://images.unsplash.com/photo-1558618666-fcd25c85cd64?auto=format&fit=crop&w=2000&q=80')",
          }}
        />
        <div className="absolute inset-0 h-[380px] bg-gradient-to-b from-black/50 via-black/30 to-transparent" />

        <div className="relative mx-auto max-w-6xl px-4 pt-10 pb-16">
          <div className="text-center text-white mb-8">
            <h1 className="text-4xl md:text-5xl font-bold mb-4 drop-shadow-lg">Find storage space near you</h1>
            <p className="text-lg md:text-xl text-white/90 drop-shadow">
              Affordable, secure storage from verified local hosts
            </p>
          </div>

          <div className="bg-white rounded-2xl shadow-2xl p-2 max-w-4xl mx-auto">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
              <div className="p-3 md:border-r border-slate-200">
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">
                  Location
                </label>
                <input
                  type="text"
                  placeholder="Enter ZIP code"
                  value={filters.zipCode || ""}
                  onChange={(e) => setFilters((f) => ({ ...f, zipCode: e.target.value }))}
                  className="w-full text-slate-900 font-medium placeholder:text-slate-400 outline-none text-lg"
                />
              </div>

              <div className="p-3 md:border-r border-slate-200">
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">
                  Start Date
                </label>
                <input
                  type="date"
                  value={filters.startDate || ""}
                  onChange={(e) => setFilters((f) => ({ ...f, startDate: e.target.value }))}
                  className="w-full text-slate-900 font-medium outline-none text-lg"
                />
              </div>

              <div className="p-3 md:border-r border-slate-200">
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">
                  End Date
                </label>
                <input
                  type="date"
                  value={filters.endDate || ""}
                  onChange={(e) => setFilters((f) => ({ ...f, endDate: e.target.value }))}
                  className="w-full text-slate-900 font-medium outline-none text-lg"
                />
              </div>

              <div className="p-2 flex items-center">
                <div className="w-full h-full bg-gradient-to-r from-brand-600 to-brand-500 text-white rounded-xl font-semibold text-lg flex items-center justify-center gap-2 min-h-[56px]">
                  {isLoading ? "Searching..." : "Search"}
                </div>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3 border-t border-slate-100 px-3 py-2 text-sm">
              <label className="flex items-center gap-2 text-slate-600">
                Within
                <select
                  value={filters.radiusMiles}
                  onChange={(e) =>
                    setFilters((f) => ({ ...f, radiusMiles: Number(e.target.value) }))
                  }
                  className="rounded-lg border border-slate-200 bg-white px-2 py-1 font-medium text-slate-800"
                >
                  {RADIUS_OPTIONS.map((mi) => (
                    <option key={mi} value={mi}>
                      {mi} miles
                    </option>
                  ))}
                </select>
              </label>
              {usingMyLocation ? (
                <button
                  type="button"
                  onClick={clearMyLocation}
                  className="inline-flex items-center gap-1 rounded-full bg-brand-50 px-3 py-1 font-medium text-brand-700"
                >
                  Near your location <span aria-hidden>×</span>
                </button>
              ) : (
                <button
                  type="button"
                  onClick={useMyLocation}
                  className="font-medium text-brand-600 hover:text-brand-700"
                >
                  Use my location
                </button>
              )}
              {geoError && <span className="text-red-600">{geoError}</span>}
            </div>
          </div>

          <div className="flex flex-wrap justify-center gap-6 mt-8 text-white/90">
            <div className="flex items-center gap-2">
              <span className="font-medium">Verified Hosts</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="font-medium">Secure Storage</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="font-medium">Save up to 50%</span>
            </div>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-6xl px-4 pb-12 pt-8 bg-slate-50">
        {shouldSearch && (
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
                  {filters.startDate && filters.endDate &&
                    ` • ${formatDateOnly(filters.startDate)} - ${formatDateOnly(filters.endDate)}`}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <select
                  value={filters.size || ""}
                  onChange={(e) =>
                    setFilters((f) => ({ ...f, size: (e.target.value as StorageSize) || undefined }))
                  }
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
                    <ListingCard key={listing._id} listing={listing} index={index} onClick={() => setSelected(listing)} />
                  ))}
                </div>
                <div className="order-1 lg:order-2">
                  <div className="h-64 lg:sticky lg:top-24 lg:h-[calc(100vh-8rem)]">
                    <ResultsMap listings={listings} origin={origin} onSelect={setSelected} />
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
        )}
        {!shouldSearch && (
          <section className="pt-8">
            <h2 className="text-2xl font-bold text-slate-900 text-center mb-10">How Spacio Works</h2>
            <div className="grid md:grid-cols-3 gap-8">
              <div className="text-center">
                <div className="mx-auto w-16 h-16 rounded-2xl bg-brand-100 flex items-center justify-center mb-4" />
                <h3 className="font-semibold text-lg text-slate-900">Search</h3>
                <p className="mt-2 text-slate-600">Enter your location and dates to find available storage spaces near you.</p>
              </div>
              <div className="text-center">
                <div className="mx-auto w-16 h-16 rounded-2xl bg-brand-100 flex items-center justify-center mb-4" />
                <h3 className="font-semibold text-lg text-slate-900">Book Securely</h3>
                <p className="mt-2 text-slate-600">Reserve your space instantly with secure payment and optional insurance.</p>
              </div>
              <div className="text-center">
                <div className="mx-auto w-16 h-16 rounded-2xl bg-brand-100 flex items-center justify-center mb-4" />
                <h3 className="font-semibold text-lg text-slate-900">Store & Save</h3>
                <p className="mt-2 text-slate-600">Access your storage anytime. Save up to 50% compared to traditional units.</p>
              </div>
            </div>
          </section>
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
