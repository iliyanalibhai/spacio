import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as listingApi from "../api/listings";
import { useAuth } from "../hooks/useAuth";
import { ReservationList } from "../components/ReservationList";
import { VerificationCard } from "../components/VerificationCard";
import { PayoutOnboardingCard } from "../components/PayoutOnboardingCard";
import { CreateListingForm } from "../components/CreateListingForm";
import { MyListingCard } from "../components/MyListingCard";

export function HostDashboard() {
  const { refreshUser } = useAuth();
  const [onboardingReturn, setOnboardingReturn] = useState(false);
  const { data: myListings = [], isLoading: loadingMy } = useQuery({
    queryKey: ["my-listings"],
    queryFn: listingApi.fetchMyListings,
  });
  const queryClient = useQueryClient();

  // Return leg of the Stripe Connect onboarding redirect (return_url /
  // refresh_url set in POST /payments/connect/onboard). Mirrors Profile's
  // `?verified=` handling. Whether onboarding actually completed is decided
  // by the account.updated webhook, so we just refresh and let
  // PayoutOnboardingCard's poll show the real state.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("onboarding")) {
      setOnboardingReturn(true);
      queryClient.invalidateQueries({ queryKey: ["connect-status"] });
      refreshUser();
      window.history.replaceState({}, "", "/host");
    }
  }, [queryClient, refreshUser]);

  const updateListing = useMutation({
    mutationFn: (vars: { id: string; payload: Parameters<typeof listingApi.updateListing>[1] }) =>
      listingApi.updateListing(vars.id, vars.payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["my-listings"] });
      queryClient.invalidateQueries({ queryKey: ["listings"] });
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
      {onboardingReturn && (
        <div className="mt-4 rounded-lg border border-brand-100 bg-brand-50 px-4 py-3 text-sm text-brand-800">
          Thanks — Stripe is reviewing your payout details. This card updates automatically once
          you're approved.
        </div>
      )}
      <div className="mt-6 grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="space-y-4">
          <VerificationCard />
          <PayoutOnboardingCard />
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
                  <MyListingCard
                    key={listing._id}
                    listing={listing}
                    onSave={(id, payload) => updateListing.mutate({ id, payload })}
                    onDelete={(id) => deleteListing.mutate(id)}
                    saveError={updateListing.isError}
                  />
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
