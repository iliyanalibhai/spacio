import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as listingApi from "../api/listings";
import { ReservationList } from "../components/ReservationList";
import { VerificationCard } from "../components/VerificationCard";
import { CreateListingForm } from "../components/CreateListingForm";

export function HostDashboard() {
  const { data: myListings = [], isLoading: loadingMy } = useQuery({
    queryKey: ["my-listings"],
    queryFn: listingApi.fetchMyListings,
  });
  const queryClient = useQueryClient();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<Record<string, unknown>>({});
  const [editFile, setEditFile] = useState<File | null>(null);
  const [editPreview, setEditPreview] = useState<string | null>(null);

  const updateListing = useMutation({
    mutationFn: (vars: { id: string; payload: Parameters<typeof listingApi.updateListing>[1] }) =>
      listingApi.updateListing(vars.id, vars.payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["my-listings"] });
      queryClient.invalidateQueries({ queryKey: ["listings"] });
      setEditingId(null);
      setEditFile(null);
      setEditPreview(null);
    },
  });

  const deleteListing = useMutation({
    mutationFn: (id: string) => listingApi.deleteListing(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["my-listings"] });
      queryClient.invalidateQueries({ queryKey: ["listings"] });
    },
  });

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="text-2xl font-semibold text-slate-900">Host workspace</h1>
      <div className="mt-6 grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="space-y-4">
          <VerificationCard />
          <CreateListingForm />
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <h3 className="text-lg font-semibold text-slate-900">Reservations</h3>
          <p className="text-sm text-slate-600">Approve or decline pending requests.</p>
          <div className="mt-3">
            <ReservationList asHost />
          </div>
        </div>
        <div className="lg:col-span-2">
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-slate-900">My listings</h3>
                <p className="text-sm text-slate-600">All listings you host.</p>
              </div>
              <span className="text-sm text-slate-500">{myListings.length} total</span>
            </div>
            <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {loadingMy ? (
                <p className="text-slate-600">Loading…</p>
              ) : myListings.length ? (
                myListings.map((listing) => (
                  <div key={listing._id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                    <div className="flex items-center justify-between text-xs text-slate-500">
                      <span className="uppercase tracking-wide text-brand-600">
                        {listing.size} • {listing.zipCode}
                      </span>
                      {listing.rating != null && <span className="text-amber-600">★ {listing.rating}</span>}
                    </div>
                    <h4 className="mt-1 text-base font-semibold text-slate-900">{listing.title}</h4>
                    <p className="text-sm text-slate-600 line-clamp-2">{listing.description}</p>
                    <p className="mt-2 text-sm text-slate-500">
                      ${listing.pricePerMonth}/mo • {listing.availability ? "Available" : "Unavailable"}
                    </p>
                    <div className="mt-3 flex justify-between text-sm text-slate-600">
                      <span>{listing.addressSummary}</span>
                      <span className="text-slate-500">{new Date(listing.createdAt).toLocaleDateString()}</span>
                    </div>
                    <p className="mt-1 text-sm text-slate-500">
                      {listing.sizeSqft ? `${listing.sizeSqft} sqft` : listing.size}
                    </p>
                    {editingId === listing._id ? (
                      <div className="mt-3 space-y-2">
                        <input
                          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                          defaultValue={listing.title}
                          onChange={(e) => setEditForm((p) => ({ ...p, title: e.target.value }))}
                        />
                        <input
                          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                          defaultValue={listing.pricePerMonth}
                          type="number"
                          onChange={(e) => setEditForm((p) => ({ ...p, pricePerMonth: Number(e.target.value) }))}
                        />
                        <select
                          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                          defaultValue={listing.size}
                          onChange={(e) => setEditForm((p) => ({ ...p, size: e.target.value }))}
                        >
                          <option value="S">S</option>
                          <option value="M">M</option>
                          <option value="L">L</option>
                        </select>
                        <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-3 py-3">
                          <p className="text-xs font-semibold text-slate-800">Replace photo (optional)</p>
                          <label
                            className="mt-2 flex cursor-pointer items-center justify-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50"
                            onDragOver={(e) => e.preventDefault()}
                            onDrop={(e) => {
                              e.preventDefault();
                              const f = e.dataTransfer.files?.[0];
                              if (f && (f.type === "image/jpeg" || f.type === "image/png")) {
                                setEditFile(f);
                                setEditPreview(URL.createObjectURL(f));
                              }
                            }}
                          >
                            <input
                              type="file"
                              accept="image/jpeg,image/png"
                              className="hidden"
                              onChange={(e) => {
                                const f = e.target.files?.[0];
                                if (f && (f.type === "image/jpeg" || f.type === "image/png")) {
                                  setEditFile(f);
                                  setEditPreview(URL.createObjectURL(f));
                                }
                              }}
                            />
                            <span>Click or drag an image here</span>
                          </label>
                          {editPreview || listing.images?.[0] ? (
                            <div className="mt-2">
                              <img
                                src={editPreview || listing.images?.[0]}
                                alt="Preview"
                                className="h-20 w-full rounded-lg object-cover"
                              />
                            </div>
                          ) : null}
                        </div>
                        <div className="flex gap-2">
                          <button
                            className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white"
                            onClick={async () => {
                              let payload = { ...editForm };
                              if (editFile) {
                                const uploaded = await listingApi.uploadImage(editFile);
                                payload = { ...payload, images: [uploaded.url] };
                              }
                              updateListing.mutate({
                                id: listing._id,
                                payload: payload as Parameters<typeof listingApi.updateListing>[1],
                              });
                            }}
                          >
                            Save
                          </button>
                          <button
                            className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700"
                            onClick={() => {
                              setEditingId(null);
                              setEditForm({});
                              setEditFile(null);
                              setEditPreview(null);
                            }}
                          >
                            Cancel
                          </button>
                        </div>
                        {updateListing.error && <p className="text-sm text-red-600">Error saving changes</p>}
                      </div>
                    ) : (
                      <div className="mt-3 flex gap-2">
                        <button
                          className="rounded-lg border border-slate-200 px-3 py-1 text-xs font-semibold text-slate-700"
                          onClick={() => {
                            setEditingId(listing._id);
                            setEditForm({});
                          }}
                        >
                          Edit
                        </button>
                        <button
                          className="rounded-lg border border-red-200 px-3 py-1 text-xs font-semibold text-red-600"
                          onClick={() => deleteListing.mutate(listing._id)}
                        >
                          Delete
                        </button>
                      </div>
                    )}
                  </div>
                ))
              ) : (
                <p className="text-slate-600">You have no listings yet. Create one to get started.</p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
