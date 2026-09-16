import { useMemo, useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import type { StorageSize } from "../types";
import * as listingApi from "../api/listings";

export type SearchFilters = {
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

type Props = {
  filters: SearchFilters;
  setFilters: (update: (f: SearchFilters) => SearchFilters) => void;
  isLoading: boolean;
  usingMyLocation: boolean;
  onUseMyLocation: () => void;
  onClearMyLocation: () => void;
  geoError: string | null;
};

export function SearchHero({
  filters,
  setFilters,
  isLoading,
  usingMyLocation,
  onUseMyLocation,
  onClearMyLocation,
  geoError,
}: Props) {
  // Uncommitted until the form submits — typing here used to write straight
  // into `filters`, which is the query key, so a search fired on every
  // keystroke (including a single, meaningless first digit). Radius and the
  // date pickers stay wired directly to `filters` below: they're discrete
  // selections, not free-text typing, so there's no thrash risk in letting
  // them re-query immediately. See docs/DOCUMENTATION.md §10.
  const [zipInput, setZipInput] = useState(filters.zipCode ?? "");
  const [showSuggestions, setShowSuggestions] = useState(false);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    setShowSuggestions(false);
    setFilters((f) => ({ ...f, zipCode: zipInput }));
  };

  // City/neighborhood typeahead, scoped down from "geocode a typed city
  // name" per the brief's addendum: zip_centroids.csv is zip/lat/lng only,
  // with no city column, and its Census provenance was deliberately chosen
  // over GeoNames/SimpleMaps specifically to avoid an attribution
  // obligation (see api/app/data/build_zip_centroids.py) — adding a second
  // vendored dataset just for city names would quietly reverse that. This
  // instead matches against the addressSummary/zipCode of listings that
  // already exist, which is free, needs no new data, and doesn't suggest
  // cities with zero inventory. Shares its query cache with
  // FeaturedListings (same queryKey) so this doesn't cost a second network
  // request on the landing page. See docs/DOCUMENTATION.md §10.
  const { data: allListings = [] } = useQuery({
    queryKey: ["listings", "featured"],
    queryFn: () => listingApi.fetchListings({}),
  });

  const suggestions = useMemo(() => {
    const query = zipInput.trim().toLowerCase();
    if (query.length < 2 || /^\d+$/.test(query)) return [];
    const seen = new Set<string>();
    const matches: { label: string; zipCode: string }[] = [];
    for (const listing of allListings) {
      if (!listing.addressSummary.toLowerCase().includes(query)) continue;
      if (seen.has(listing.addressSummary)) continue;
      seen.add(listing.addressSummary);
      matches.push({ label: listing.addressSummary, zipCode: listing.zipCode });
      if (matches.length >= 5) break;
    }
    return matches;
  }, [zipInput, allListings]);

  const selectSuggestion = (s: { label: string; zipCode: string }) => {
    setZipInput(s.label);
    setShowSuggestions(false);
    setFilters((f) => ({ ...f, zipCode: s.zipCode }));
  };

  return (
    <div className="relative min-h-[380px]">
      <div
        className="absolute inset-0 h-[380px] bg-cover bg-center"
        style={{
          // A bright yellow three-door garage (Sijmen van Hooff, Unsplash,
          // free license) — the previous photo was an ambiguous close-up of
          // a hand and a piece of wood, which read as "person," not
          // "storage." See docs/DOCUMENTATION.md §10.
          backgroundImage:
            "url('https://images.unsplash.com/photo-1766503494749-0806c2a0aab4?auto=format&fit=crop&w=2000&q=80')",
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

        <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-2xl p-2 max-w-4xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
            <div className="relative p-3 md:border-r border-slate-200">
              <label htmlFor="search-zip" className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">
                Location
              </label>
              <input
                id="search-zip"
                type="text"
                placeholder="ZIP or city"
                autoComplete="off"
                value={zipInput}
                onChange={(e) => {
                  setZipInput(e.target.value);
                  setShowSuggestions(true);
                }}
                onFocus={() => setShowSuggestions(true)}
                onBlur={() => setShowSuggestions(false)}
                className="w-full text-slate-900 font-medium placeholder:text-slate-400 outline-none text-lg"
              />
              {showSuggestions && suggestions.length > 0 && (
                <ul className="absolute left-0 right-0 top-full z-10 mt-1 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg">
                  {suggestions.map((s) => (
                    <li key={s.label}>
                      <button
                        type="button"
                        // onMouseDown (not onClick) fires before the input's
                        // onBlur closes the dropdown, so the click actually
                        // registers.
                        onMouseDown={() => selectSuggestion(s)}
                        className="block w-full px-4 py-2 text-left text-sm text-slate-700 hover:bg-slate-50"
                      >
                        {s.label}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
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
              <button
                type="submit"
                disabled={isLoading}
                className="w-full h-full bg-gradient-to-r from-accent-600 to-accent-500 text-white rounded-xl font-semibold text-lg flex items-center justify-center gap-2 min-h-[56px] transition hover:from-accent-700 hover:to-accent-600 disabled:opacity-70"
              >
                {isLoading ? "Searching..." : "Search"}
              </button>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3 border-t border-slate-100 px-3 py-2 text-sm">
            <label className="flex items-center gap-2 text-slate-600">
              Within
              <select
                value={filters.radiusMiles}
                onChange={(e) => setFilters((f) => ({ ...f, radiusMiles: Number(e.target.value) }))}
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
                onClick={onClearMyLocation}
                className="inline-flex items-center gap-1 rounded-full bg-brand-50 px-3 py-1 font-medium text-brand-700"
              >
                Near your location <span aria-hidden>×</span>
              </button>
            ) : (
              <button
                type="button"
                onClick={onUseMyLocation}
                className="font-medium text-brand-600 hover:text-brand-700"
              >
                Use my location
              </button>
            )}
            {geoError && <span className="text-red-600">{geoError}</span>}
          </div>
        </form>

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
  );
}
