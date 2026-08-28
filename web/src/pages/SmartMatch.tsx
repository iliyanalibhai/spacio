import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import * as matchingApi from "../api/matching";
import { getListingImage } from "../lib/getListingImage";

// Named "Smart Match" rather than the v1 prototype's "AI Match". As of
// Phase 2 the backend (services/matching.py) does real semantic search —
// all-MiniLM-L6-v2 sentence embeddings over each listing's text, ranked by
// cosine similarity to the query and nudged by ZIP/price/availability. It's
// still not an LLM, so the copy stays "Smart Match", not "AI".
export function SmartMatch() {
  const [query, setQuery] = useState("");
  const [zip, setZip] = useState("");
  const { data, mutateAsync, isPending, error } = useMutation({
    mutationFn: () => matchingApi.recommend({ query, zipCode: zip || undefined }),
  });

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="text-2xl font-semibold text-slate-900">Smart Match</h1>
      <p className="text-sm text-slate-600">
        Describe what you need to store, and we'll suggest spaces that fit.
      </p>
      <div className="mt-4 grid gap-3">
        <textarea
          className="rounded-lg border border-slate-200 px-3 py-2"
          rows={4}
          placeholder="e.g., I have 6 medium boxes and a bike"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <input
          className="rounded-lg border border-slate-200 px-3 py-2"
          placeholder="ZIP code (optional)"
          value={zip}
          onChange={(e) => setZip(e.target.value)}
        />
        <button
          onClick={() => mutateAsync()}
          disabled={!query || isPending}
          className="inline-flex w-fit rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white shadow-sm disabled:opacity-60"
        >
          {isPending ? "Finding matches..." : "Find matching spaces"}
        </button>
        {error && <p className="text-sm text-red-600">Could not fetch matches. Please try again.</p>}
        {data && (
          <div className="mt-2 space-y-3">
            <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
              <div className="font-semibold">Why these matches?</div>
              <div className="text-slate-600">{data.explanation}</div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {data.listings.map((listing) => (
                <div
                  key={listing._id}
                  className="group overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm transition hover:-translate-y-1 hover:shadow-lg"
                >
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
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
