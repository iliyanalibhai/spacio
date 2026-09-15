import type { StorageSize } from "../types";

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
  return (
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
  );
}
