import { useState } from "react";
import * as listingApi from "../api/listings";
import type { Listing } from "../types";

type Props = {
  listing: Listing;
  onSave: (id: string, payload: Parameters<typeof listingApi.updateListing>[1]) => void;
  onDelete: (id: string) => void;
  saveError?: boolean;
};

export function MyListingCard({ listing, onSave, onDelete, saveError }: Props) {
  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState<Record<string, unknown>>({});
  const [editFile, setEditFile] = useState<File | null>(null);
  const [editPreview, setEditPreview] = useState<string | null>(null);

  const resetEditState = () => {
    setEditing(false);
    setEditForm({});
    setEditFile(null);
    setEditPreview(null);
  };

  const handleFile = (f: File | undefined) => {
    if (f && (f.type === "image/jpeg" || f.type === "image/png")) {
      setEditFile(f);
      setEditPreview(URL.createObjectURL(f));
    }
  };

  const handleSave = async () => {
    let payload = { ...editForm };
    if (editFile) {
      const uploaded = await listingApi.uploadImage(editFile);
      payload = { ...payload, images: [uploaded.url] };
    }
    onSave(listing._id, payload as Parameters<typeof listingApi.updateListing>[1]);
    resetEditState();
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
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
      {editing ? (
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
                handleFile(e.dataTransfer.files?.[0]);
              }}
            >
              <input
                type="file"
                accept="image/jpeg,image/png"
                className="hidden"
                onChange={(e) => handleFile(e.target.files?.[0])}
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
              onClick={handleSave}
            >
              Save
            </button>
            <button
              className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700"
              onClick={resetEditState}
            >
              Cancel
            </button>
          </div>
          {saveError && <p className="text-sm text-red-600">Error saving changes</p>}
        </div>
      ) : (
        <div className="mt-3 flex gap-2">
          <button
            className="rounded-lg border border-slate-200 px-3 py-1 text-xs font-semibold text-slate-700"
            onClick={() => {
              setEditing(true);
              setEditForm({});
            }}
          >
            Edit
          </button>
          <button
            className="rounded-lg border border-red-200 px-3 py-1 text-xs font-semibold text-red-600"
            onClick={() => onDelete(listing._id)}
          >
            Delete
          </button>
        </div>
      )}
    </div>
  );
}
