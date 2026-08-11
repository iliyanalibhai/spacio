import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { Listing } from "../types";
import { useAuth } from "../hooks/useAuth";
import * as reservationApi from "../api/reservations";
import { getListingImage } from "../lib/getListingImage";
import { quoteReservation, BOX_PRICE_PER_MONTH } from "../lib/reservationPricing";

export function ListingDetailModal({
  listing,
  onClose,
  searchDates,
}: {
  listing: Listing;
  onClose: () => void;
  searchDates?: { startDate?: string; endDate?: string };
}) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [startDate, setStartDate] = useState(searchDates?.startDate || "");
  const [endDate, setEndDate] = useState(searchDates?.endDate || "");
  const [numBoxes, setNumBoxes] = useState(0);
  const [wantsInsurance, setWantsInsurance] = useState(false);
  const [declaredValue, setDeclaredValue] = useState(1000);
  const [hasOwnInsurance, setHasOwnInsurance] = useState(false);
  const [confirmed, setConfirmed] = useState(false);

  const totalSqft = listing.sizeSqft || 100;
  const availableSqft = listing.availableSqft ?? totalSqft;
  const [sqftRequested, setSqftRequested] = useState(Math.min(50, availableSqft));

  const { mutateAsync, isPending, error } = useMutation({
    mutationFn: reservationApi.createReservation,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reservations"] });
      queryClient.invalidateQueries({ queryKey: ["my-reservations"] });
      queryClient.invalidateQueries({ queryKey: ["listings"] });
      // Payment is `mocked-success` server-side (real Stripe Checkout is
      // Phase 4) — show a local confirmation rather than redirecting to any
      // payment page, mocked or real, so this never implies a charge that
      // didn't happen.
      setConfirmed(true);
    },
  });

  const quote = useMemo(
    () =>
      quoteReservation({
        hostMonthlyPrice: listing.pricePerMonth,
        totalSqft,
        sqftRequested,
        startDate,
        endDate,
        numBoxes,
        insuranceDeclaredValue: wantsInsurance ? declaredValue : null,
        hasOwnInsurance,
      }),
    [listing.pricePerMonth, totalSqft, sqftRequested, startDate, endDate, numBoxes, wantsInsurance, declaredValue, hasOwnInsurance]
  );

  const isOwnListing = user && listing.hostId === user._id;

  const handleReserve = async () => {
    if (!user) {
      alert("Login first");
      return;
    }
    if (isOwnListing) {
      alert("You cannot rent your own listing");
      return;
    }
    if (sqftRequested > availableSqft) {
      alert(`Only ${availableSqft} sqft available`);
      return;
    }
    await mutateAsync({
      listingId: listing._id,
      startDate,
      endDate,
      sqftRequested,
      numBoxes,
      insuranceDeclaredValue: wantsInsurance ? declaredValue : null,
      hasOwnInsurance,
    });
  };

  if (confirmed) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
        <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl text-center">
          <svg className="mx-auto h-12 w-12 text-emerald-500" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
          </svg>
          <h3 className="mt-3 text-lg font-semibold text-slate-900">Reservation requested</h3>
          <p className="mt-1 text-sm text-slate-600">
            The host has 24 hours to approve or decline. You'll see the status in your reservations.
          </p>
          <button
            onClick={onClose}
            className="mt-4 rounded-lg bg-brand-600 px-4 py-2 text-white shadow-sm hover:bg-brand-500 transition-colors"
          >
            Done
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 overflow-y-auto">
      <div className="w-full max-w-2xl rounded-2xl bg-white p-6 shadow-xl my-auto">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs uppercase text-brand-600">
              {listing.sizeSqft ? `${listing.sizeSqft} sqft` : listing.size} • {listing.zipCode}
            </p>
            <h3 className="text-2xl font-semibold text-slate-900">{listing.title}</h3>
            <p className="text-sm text-slate-600">{listing.description}</p>
            <p className="mt-2 text-sm text-slate-500">{listing.addressSummary}</p>
          </div>
          <button
            className="rounded-full p-2 hover:bg-slate-100 transition-colors text-slate-500 hover:text-slate-700"
            onClick={onClose}
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <div className="rounded-xl border border-slate-200 p-4">
            <h4 className="font-semibold text-slate-900">Reserve</h4>
            <div className="mt-3 flex flex-col gap-2">
              <div className="rounded-lg border border-slate-200 p-3 bg-slate-50">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-slate-700">Space needed</span>
                  <span className="text-sm text-emerald-600 font-medium">{availableSqft} sqft available</span>
                </div>
                <div className="flex items-center gap-3">
                  <input
                    type="range"
                    min={10}
                    max={availableSqft}
                    step={5}
                    value={sqftRequested}
                    onChange={(e) => setSqftRequested(Number(e.target.value))}
                    className="flex-1 h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-brand-600"
                  />
                  <div className="flex items-center gap-1">
                    <input
                      type="number"
                      min={10}
                      max={availableSqft}
                      value={sqftRequested}
                      onChange={(e) => setSqftRequested(Math.min(availableSqft, Math.max(10, Number(e.target.value))))}
                      className="w-16 rounded-lg border border-slate-200 px-2 py-1 text-center text-sm"
                    />
                    <span className="text-sm text-slate-500">sqft</span>
                  </div>
                </div>
                <p className="text-xs text-slate-500 mt-2">
                  {Math.round((sqftRequested / totalSqft) * 100)}% of total space ({totalSqft} sqft)
                </p>
              </div>

              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                min={listing.availableFrom ? listing.availableFrom.split("T")[0] : undefined}
                max={listing.availableTo ? listing.availableTo.split("T")[0] : undefined}
                className="rounded-lg border border-slate-200 px-3 py-2"
              />
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                min={startDate || (listing.availableFrom ? listing.availableFrom.split("T")[0] : undefined)}
                max={listing.availableTo ? listing.availableTo.split("T")[0] : undefined}
                className="rounded-lg border border-slate-200 px-3 py-2"
              />

              <div className="rounded-lg border border-slate-200 p-3 bg-slate-50">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-sm font-medium text-slate-700">Secure boxes</span>
                    <p className="text-xs text-slate-500">
                      Lockable, only you hold the key — ${BOX_PRICE_PER_MONTH}/box/month
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setNumBoxes((n) => Math.max(0, n - 1))}
                      className="h-7 w-7 rounded-full border border-slate-300 text-slate-600"
                    >
                      −
                    </button>
                    <span className="w-4 text-center text-sm font-medium">{numBoxes}</span>
                    <button
                      type="button"
                      onClick={() => setNumBoxes((n) => n + 1)}
                      className="h-7 w-7 rounded-full border border-slate-300 text-slate-600"
                    >
                      +
                    </button>
                  </div>
                </div>
              </div>

              <div className="rounded-lg border border-slate-200 p-3 bg-slate-50">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={wantsInsurance}
                    onChange={(e) => {
                      setWantsInsurance(e.target.checked);
                      if (e.target.checked) setHasOwnInsurance(false);
                    }}
                    className="h-4 w-4 rounded border-slate-300 text-brand-600"
                  />
                  <span className="text-sm font-medium text-slate-700">Add insurance (theft, damage, loss)</span>
                </label>
                {wantsInsurance && (
                  <div className="mt-2">
                    <label className="text-xs text-slate-500">Declared value of stored items ($)</label>
                    <input
                      type="number"
                      min={0}
                      max={10000}
                      value={declaredValue}
                      onChange={(e) => setDeclaredValue(Number(e.target.value))}
                      className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                    />
                    {declaredValue > 10000 && (
                      <p className="mt-1 text-xs text-red-600">Max covered declared value is $10,000</p>
                    )}
                  </div>
                )}
                <label className="mt-2 flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={hasOwnInsurance}
                    onChange={(e) => {
                      setHasOwnInsurance(e.target.checked);
                      if (e.target.checked) setWantsInsurance(false);
                    }}
                    className="h-4 w-4 rounded border-slate-300 text-brand-600"
                  />
                  <span className="text-xs text-slate-600">I have my own renter's insurance</span>
                </label>
              </div>

              {quote && (
                <div className="text-sm text-slate-700">
                  <div className="flex justify-between text-slate-500">
                    <span>
                      {sqftRequested} sqft × {quote.days} days ({quote.spaceRatioPct}% of space)
                    </span>
                  </div>
                  <div className="flex justify-between mt-1">
                    <span>Base price</span>
                    <span>${quote.base}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Service fee (20%)</span>
                    <span>${quote.serviceFee}</span>
                  </div>
                  {quote.boxCost > 0 && (
                    <div className="flex justify-between">
                      <span>Boxes ({numBoxes})</span>
                      <span>${quote.boxCost}</span>
                    </div>
                  )}
                  {quote.insuranceCost > 0 && (
                    <div className="flex justify-between text-emerald-600">
                      <span>Insurance</span>
                      <span>${quote.insuranceCost}</span>
                    </div>
                  )}
                  <div className="mt-2 flex justify-between font-semibold border-t border-slate-200 pt-2">
                    <span>Total</span>
                    <span>${quote.total}</span>
                  </div>
                </div>
              )}
              {error && (
                <p className="text-sm text-red-600">
                  {(error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Error"}
                </p>
              )}
              {isOwnListing ? (
                <div className="rounded-lg bg-amber-50 border border-amber-200 px-4 py-3 text-center">
                  <p className="text-sm font-medium text-amber-800">This is your listing</p>
                  <p className="text-xs text-amber-600 mt-1">You cannot rent your own space</p>
                </div>
              ) : (
                <button
                  disabled={!startDate || !endDate || isPending || sqftRequested <= 0 || sqftRequested > availableSqft}
                  onClick={handleReserve}
                  className="rounded-lg bg-brand-600 px-4 py-2 text-white shadow-sm disabled:opacity-60 hover:bg-brand-500 transition-colors"
                >
                  {isPending ? "Reserving..." : "Reserve spot"}
                </button>
              )}
            </div>
          </div>
          <div className="rounded-xl border border-slate-200 p-4">
            <h4 className="font-semibold text-slate-900">Details</h4>
            <p className="mt-2 text-sm text-slate-600">
              {listing.rating != null ? `Rating: ${listing.rating} • ` : ""}
              Availability: {listing.availability ? "Available" : "Unavailable"}
            </p>
            <p className="mt-2 text-sm text-slate-600">Price: ${listing.pricePerMonth}/month (full space)</p>
            <p className="mt-2 text-sm text-slate-600">Size: {listing.sizeSqft || 100} sq ft total</p>
            {listing.availableFrom && listing.availableTo && (
              <p className="mt-2 text-sm text-slate-600">
                <span className="font-medium">Available:</span>{" "}
                {new Date(listing.availableFrom).toLocaleDateString()} - {new Date(listing.availableTo).toLocaleDateString()}
              </p>
            )}
            {listing.bookingDeadline ? (
              <p className="mt-2 text-sm text-amber-600">
                <span className="font-medium">Book by:</span> {new Date(listing.bookingDeadline).toLocaleDateString()}
              </p>
            ) : (
              <p className="mt-2 text-sm text-emerald-600">No booking deadline</p>
            )}
            <img
              src={getListingImage(listing)}
              alt={listing.title}
              className="mt-3 h-32 w-full rounded-lg object-cover"
            />
          </div>
        </div>

        <div className="mt-4 rounded-xl bg-slate-50 border border-slate-200 p-4">
          <div className="flex items-start gap-3">
            <svg className="h-5 w-5 text-emerald-600 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <p className="text-sm font-medium text-slate-900">Free cancellation until 72 hours before your reservation</p>
              <p className="text-xs text-slate-500 mt-1">
                Cancel before check-in for a full refund. After that, you'll be charged 50% of the reservation total to the host for no-shows.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
