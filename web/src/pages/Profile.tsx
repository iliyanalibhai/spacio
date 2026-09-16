import { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../hooks/useAuth";
import * as reservationApi from "../api/reservations";
import * as verificationApi from "../api/verification";
import * as paymentsApi from "../api/payments";
import { ProfileHeader } from "../components/ProfileHeader";
import { ProfileInfoTab } from "../components/ProfileInfoTab";
import { ReservationsTab } from "../components/ReservationsTab";
import { VerificationCard } from "../components/VerificationCard";

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

  // A confirmed reservation whose stay has already ended is functionally
  // "past" (and reviewable — see ProfileReservationCard), not still active.
  const hasEnded = (r: (typeof myReservations)[number]) => new Date(r.endDate) <= new Date();
  const activeReservations = myReservations.filter(
    (r) => r.status === "pending_host_confirmation" || (r.status === "confirmed" && !hasEnded(r))
  );
  const pastReservations = myReservations.filter(
    (r) => r.status === "declined" || r.status === "expired" || (r.status === "confirmed" && hasEnded(r))
  );

  if (!user) {
    return <Navigate to="/login" />;
  }

  return (
    <main className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-4xl px-4 py-8">
        <ProfileHeader
          user={user}
          becomingHost={becomeHostMutation.isPending}
          onBecomeHost={() => becomeHostMutation.mutate()}
          onGoToHostDashboard={() => navigate("/host")}
        />

        {user.isHost && user.verificationStatus !== "verified" && (
          <div className="mb-6">
            <VerificationCard onVerified={refreshUser} />
          </div>
        )}

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
          <ProfileInfoTab
            user={user}
            becomingHost={becomeHostMutation.isPending}
            onBecomeHost={() => becomeHostMutation.mutate()}
          />
        )}

        {activeTab === "reservations" && (
          <ReservationsTab
            checkoutBanner={checkoutBanner}
            onDismissBanner={() => setCheckoutBanner(null)}
            loading={loadingReservations}
            activeReservations={activeReservations}
            pastReservations={pastReservations}
            onFindSpace={() => navigate("/")}
          />
        )}
      </div>
    </main>
  );
}
