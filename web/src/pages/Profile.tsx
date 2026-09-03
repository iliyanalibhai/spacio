import { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../hooks/useAuth";
import * as reservationApi from "../api/reservations";
import * as verificationApi from "../api/verification";
import * as paymentsApi from "../api/payments";
import { ProfileReservationCard } from "../components/ProfileReservationCard";

export function Profile() {
  const { user, refreshUser } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<"profile" | "reservations">("profile");
  const [checkoutBanner, setCheckoutBanner] = useState<{ kind: "success" | "cancelled"; text: string } | null>(
    null
  );

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("tab") === "reservations") {
      setActiveTab("reservations");
    }
    if (params.get("verified")) {
      refreshUser();
      window.history.replaceState({}, "", "/profile");
    }

    const checkout = params.get("checkout");
    const reservationId = params.get("reservation");
    if (checkout && reservationId) {
      setActiveTab("reservations");
      window.history.replaceState({}, "", "/profile");
      if (checkout === "complete") {
        // Force-sync from Stripe immediately rather than waiting on the
        // webhook, which may not have landed yet in local dev.
        paymentsApi.getCheckoutStatus(reservationId).finally(() => {
          queryClient.invalidateQueries({ queryKey: ["my-reservations"] });
        });
        setCheckoutBanner({
          kind: "success",
          text: "Payment authorized — your card won't be charged until the host approves.",
        });
      } else if (checkout === "cancelled") {
        setCheckoutBanner({
          kind: "cancelled",
          text: "Payment was not completed. You can retry from the reservation below.",
        });
      }
    }
  }, [refreshUser, queryClient]);

  const { data: reservations = [], isLoading: loadingReservations } = useQuery({
    queryKey: ["my-reservations"],
    queryFn: reservationApi.listReservations,
  });

  const myReservations = reservations.filter((r) => r.renterId === user?._id);

  const becomeHostMutation = useMutation({
    mutationFn: () => verificationApi.createVerificationSession(),
    onSuccess: (data) => {
      window.location.href = data.url;
    },
  });

  const activeReservations = myReservations.filter(
    (r) => r.status === "confirmed" || r.status === "pending_host_confirmation"
  );
  const pastReservations = myReservations.filter((r) => r.status === "declined" || r.status === "expired");

  if (!user) {
    return <Navigate to="/login" />;
  }

  return (
    <main className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-4xl px-4 py-8">
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 mb-6">
          <div className="flex items-start gap-6">
            <div className="h-20 w-20 rounded-full bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center text-white font-bold text-3xl flex-shrink-0">
              {user.name.charAt(0).toUpperCase()}
            </div>
            <div className="flex-1">
              <h1 className="text-2xl font-bold text-slate-900">{user.name}</h1>
              <p className="text-slate-500">{user.email}</p>

              <div className="flex flex-wrap gap-2 mt-3">
                {user.isHost && user.verificationStatus === "verified" ? (
                  <span className="inline-flex items-center gap-1 bg-emerald-100 text-emerald-700 px-3 py-1 rounded-full text-sm font-medium">
                    Verified Host
                  </span>
                ) : user.isHost && user.verificationStatus === "pending" ? (
                  <span className="inline-flex items-center gap-1 bg-amber-100 text-amber-700 px-3 py-1 rounded-full text-sm font-medium">
                    Verification Pending
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 bg-brand-100 text-brand-700 px-3 py-1 rounded-full text-sm font-medium">
                    Renter
                  </span>
                )}
              </div>
            </div>

            <div className="flex-shrink-0">
              {user.isHost && user.verificationStatus === "verified" ? (
                <button
                  onClick={() => navigate("/host")}
                  className="bg-brand-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-brand-500 transition-colors"
                >
                  Host Dashboard
                </button>
              ) : !user.isHost ? (
                <button
                  onClick={() => becomeHostMutation.mutate()}
                  disabled={becomeHostMutation.isPending}
                  className="bg-gradient-to-r from-brand-600 to-brand-500 text-white px-4 py-2 rounded-lg font-medium hover:from-brand-500 hover:to-brand-400 transition-all disabled:opacity-50"
                >
                  {becomeHostMutation.isPending ? "Starting..." : "Become a Host"}
                </button>
              ) : user.verificationStatus === "pending" ? (
                <span className="text-sm text-slate-500">Verification in progress</span>
              ) : (
                <button
                  onClick={() => becomeHostMutation.mutate()}
                  disabled={becomeHostMutation.isPending}
                  className="bg-brand-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-brand-500 transition-colors disabled:opacity-50"
                >
                  {becomeHostMutation.isPending ? "Starting..." : "Complete Verification"}
                </button>
              )}
            </div>
          </div>
        </div>

        <div className="flex gap-1 bg-white rounded-xl p-1 shadow-sm border border-slate-200 mb-6">
          <button
            onClick={() => setActiveTab("profile")}
            className={`flex-1 py-2.5 px-4 rounded-lg font-medium transition-colors ${
              activeTab === "profile" ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-100"
            }`}
          >
            Profile
          </button>
          <button
            onClick={() => setActiveTab("reservations")}
            className={`flex-1 py-2.5 px-4 rounded-lg font-medium transition-colors ${
              activeTab === "reservations" ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-100"
            }`}
          >
            My Reservations
            {activeReservations.length > 0 && (
              <span className="ml-2 bg-white/20 text-white px-2 py-0.5 rounded-full text-xs">
                {activeReservations.length}
              </span>
            )}
          </button>
        </div>

        {activeTab === "profile" && (
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
            <h2 className="text-lg font-semibold text-slate-900 mb-4">Account Information</h2>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-500 mb-1">Full Name</label>
                <p className="text-slate-900">{user.name}</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-500 mb-1">Email Address</label>
                <p className="text-slate-900">{user.email}</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-500 mb-1">Account Type</label>
                <p className="text-slate-900">{user.isHost ? "Host & Renter" : "Renter"}</p>
              </div>
              {user.isHost && (
                <div>
                  <label className="block text-sm font-medium text-slate-500 mb-1">Verification Status</label>
                  <p className="text-slate-900 capitalize">{user.verificationStatus || "Not verified"}</p>
                </div>
              )}
            </div>

            {!user.isHost && (
              <div className="mt-8 p-6 bg-gradient-to-r from-brand-50 to-blue-50 rounded-xl border border-brand-100">
                <div className="flex items-start gap-4">
                  <div className="flex-1">
                    <h3 className="font-semibold text-slate-900">Want to earn money with your extra space?</h3>
                    <p className="text-sm text-slate-600 mt-1">
                      Become a verified host and list your garage, closet, or spare room.
                    </p>
                    <button
                      onClick={() => becomeHostMutation.mutate()}
                      disabled={becomeHostMutation.isPending}
                      className="mt-4 bg-brand-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-brand-500 transition-colors disabled:opacity-50"
                    >
                      {becomeHostMutation.isPending ? "Starting verification..." : "Become a Host"}
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === "reservations" && (
          <div className="space-y-6">
            {checkoutBanner && (
              <div
                className={`rounded-xl border p-4 text-sm flex items-start justify-between gap-3 ${
                  checkoutBanner.kind === "success"
                    ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                    : "border-amber-200 bg-amber-50 text-amber-800"
                }`}
              >
                <span>{checkoutBanner.text}</span>
                <button onClick={() => setCheckoutBanner(null)} className="font-medium underline flex-shrink-0">
                  Dismiss
                </button>
              </div>
            )}
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
              <h2 className="text-lg font-semibold text-slate-900 mb-4">
                Active Reservations
                {activeReservations.length > 0 && (
                  <span className="ml-2 text-sm font-normal text-slate-500">({activeReservations.length})</span>
                )}
              </h2>

              {loadingReservations ? (
                <div className="flex items-center justify-center py-8">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600"></div>
                </div>
              ) : activeReservations.length > 0 ? (
                <div className="space-y-4">
                  {activeReservations.map((reservation) => (
                    <ProfileReservationCard key={reservation._id} reservation={reservation} />
                  ))}
                </div>
              ) : (
                <div className="text-center py-8">
                  <p className="text-slate-500">No active reservations</p>
                  <button onClick={() => navigate("/")} className="mt-4 text-brand-600 font-medium hover:text-brand-500">
                    Find storage space →
                  </button>
                </div>
              )}
            </div>

            {pastReservations.length > 0 && (
              <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
                <h2 className="text-lg font-semibold text-slate-900 mb-4">
                  Past Reservations
                  <span className="ml-2 text-sm font-normal text-slate-500">({pastReservations.length})</span>
                </h2>
                <div className="space-y-4">
                  {pastReservations.map((reservation) => (
                    <ProfileReservationCard key={reservation._id} reservation={reservation} />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
