import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { StorageSize } from "../types";
import * as listingApi from "../api/listings";
import * as pricingApi from "../api/pricing";

const emptyForm = {
  title: "",
  description: "",
  size: "M" as StorageSize,
  sizeSqft: 100,
  pricePerMonth: 100,
  addressSummary: "",
  zipCode: "",
  availableFrom: "",
  availableTo: "",
  bookingDeadline: "",
};

export function CreateListingForm() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState(emptyForm);
  const [indoor, setIndoor] = useState(true);
  const [noBookingDeadline, setNoBookingDeadline] = useState(true);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [suggested, setSuggested] = useState<{
    price: number;
    min: number;
    max: number;
    reason: string;
  } | null>(null);

  const pricing = useMutation({
    mutationFn: () =>
      pricingApi.suggestPrice({
        size: form.sizeSqft <= 60 ? "S" : form.sizeSqft <= 150 ? "M" : "L",
        zipCode: form.zipCode,
        indoor,
        title: form.title,
        description: form.description,
      }),
    onSuccess: (res) => {
      setSuggested({
        price: res.suggestedPrice,
        min: res.minPrice,
        max: res.maxPrice,
        reason: res.explanation,
      });
      setForm((prev) => ({ ...prev, pricePerMonth: res.suggestedPrice }));
    },
  });

  const { mutateAsync, isPending, error } = useMutation({
    mutationFn: (payload: Parameters<typeof listingApi.createListing>[0]) =>
      listingApi.createListing(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["listings"] });
      queryClient.invalidateQueries({ queryKey: ["my-listings"] });
      alert("Listing created");
      setForm(emptyForm);
      setNoBookingDeadline(true);
      setFile(null);
      setPreview(null);
      setSuggested(null);
    },
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    let images: string[] = [];
    if (file) {
      const uploaded = await listingApi.uploadImage(file);
      images = [uploaded.url];
    }
    await mutateAsync({
      ...form,
      sizeSqft: Number(form.sizeSqft),
      pricePerMonth: Number(form.pricePerMonth),
      bookingDeadline: noBookingDeadline ? null : form.bookingDeadline,
      images,
    });
  };

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <h3 className="text-lg font-semibold text-slate-900">Create listing</h3>
      <form className="mt-3 grid gap-3" onSubmit={handleSubmit}>
        <input
          required
          placeholder="Title"
          className="rounded-lg border border-slate-200 px-3 py-2"
          value={form.title}
          onChange={(e) => setForm({ ...form, title: e.target.value })}
        />
        <textarea
          required
          placeholder="Description"
          className="rounded-lg border border-slate-200 px-3 py-2"
          value={form.description}
          onChange={(e) => setForm({ ...form, description: e.target.value })}
        />
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="flex flex-col gap-1 text-sm font-medium text-slate-700">
            Size (sqft)
            <input
              type="number"
              required
              min={1}
              placeholder="e.g., 80"
              className="rounded-lg border border-slate-200 px-3 py-2"
              value={form.sizeSqft}
              onChange={(e) => setForm({ ...form, sizeSqft: Number(e.target.value) })}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium text-slate-700">
            Price per month ($)
            <input
              type="number"
              required
              min={1}
              placeholder="e.g., 120"
              className="rounded-lg border border-slate-200 px-3 py-2"
              value={form.pricePerMonth}
              onChange={(e) => setForm({ ...form, pricePerMonth: Number(e.target.value) })}
            />
          </label>
        </div>
        {suggested && (
          <div className="flex items-start gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
            <div>
              <div className="font-semibold">
                Suggested price: ${suggested.price} (range ${suggested.min} – ${suggested.max})
              </div>
              <div className="text-slate-600">{suggested.reason}</div>
            </div>
          </div>
        )}
        <input
          required
          placeholder="ZIP code"
          className="rounded-lg border border-slate-200 px-3 py-2"
          value={form.zipCode}
          onChange={(e) => setForm({ ...form, zipCode: e.target.value })}
        />
        <input
          required
          placeholder="Address summary"
          className="rounded-lg border border-slate-200 px-3 py-2"
          value={form.addressSummary}
          onChange={(e) => setForm({ ...form, addressSummary: e.target.value })}
        />

        <div className="rounded-lg border border-slate-200 p-3 bg-slate-50">
          <p className="text-sm font-semibold text-slate-800 mb-2">Availability Period</p>
          <p className="text-xs text-slate-500 mb-3">When is this space available for renters?</p>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="flex flex-col gap-1 text-sm font-medium text-slate-700">
              Available from
              <input
                type="date"
                required
                className="rounded-lg border border-slate-200 px-3 py-2"
                value={form.availableFrom}
                onChange={(e) => setForm({ ...form, availableFrom: e.target.value })}
              />
            </label>
            <label className="flex flex-col gap-1 text-sm font-medium text-slate-700">
              Available until
              <input
                type="date"
                required
                className="rounded-lg border border-slate-200 px-3 py-2"
                value={form.availableTo}
                onChange={(e) => setForm({ ...form, availableTo: e.target.value })}
              />
            </label>
          </div>
        </div>

        <div className="rounded-lg border border-slate-200 p-3 bg-slate-50">
          <p className="text-sm font-semibold text-slate-800 mb-2">Booking Deadline</p>
          <p className="text-xs text-slate-500 mb-3">
            By when must reservations be finalized? (e.g., if you're going on vacation)
          </p>
          <label className="flex items-center gap-2 text-sm font-medium text-slate-700 mb-3">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-slate-300"
              checked={noBookingDeadline}
              onChange={(e) => setNoBookingDeadline(e.target.checked)}
            />
            No deadline - renters can book anytime during availability
          </label>
          {!noBookingDeadline && (
            <label className="flex flex-col gap-1 text-sm font-medium text-slate-700">
              Reservations must be finalized by
              <input
                type="date"
                required={!noBookingDeadline}
                className="rounded-lg border border-slate-200 px-3 py-2"
                value={form.bookingDeadline}
                onChange={(e) => setForm({ ...form, bookingDeadline: e.target.value })}
              />
            </label>
          )}
        </div>

        <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-slate-300"
            checked={indoor}
            onChange={(e) => setIndoor(e.target.checked)}
          />
          Indoor storage (adds premium in suggestion)
        </label>
        <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-4">
          <p className="text-sm font-semibold text-slate-800">Add photo (JPEG or PNG)</p>
          <label
            className="mt-2 flex cursor-pointer items-center justify-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              const f = e.dataTransfer.files?.[0];
              if (f && (f.type === "image/jpeg" || f.type === "image/png")) {
                setFile(f);
                setPreview(URL.createObjectURL(f));
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
                  setFile(f);
                  setPreview(URL.createObjectURL(f));
                }
              }}
            />
            <span>Click or drag an image here</span>
          </label>
          {preview && (
            <div className="mt-3">
              <img src={preview} alt="Preview" className="h-28 w-full rounded-lg object-cover" />
            </div>
          )}
        </div>
        {error && (
          <p className="text-sm text-red-600">
            {(error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
              "Error creating listing"}
          </p>
        )}
        <div className="flex items-center gap-2 text-sm text-slate-700">
          <button
            type="button"
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700"
            onClick={() => pricing.mutate()}
            disabled={pricing.isPending || !form.zipCode || !form.sizeSqft}
          >
            {pricing.isPending ? "Getting price suggestion…" : "Suggest a price"}
          </button>
          {pricing.isError && (
            <span className="text-sm text-red-600">Could not fetch a price suggestion. Please try again.</span>
          )}
        </div>
        <button
          type="submit"
          disabled={isPending}
          className="rounded-lg bg-brand-600 px-4 py-2 text-white shadow-sm disabled:opacity-60"
        >
          {isPending ? "Saving..." : "Create listing"}
        </button>
      </form>
    </div>
  );
}
