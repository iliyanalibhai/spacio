import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../hooks/useAuth";
import * as reservationApi from "../api/reservations";
import { ReservationsTab } from "../components/ReservationsTab";

export function RenterDashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const { data: reservations = [], isLoading } = useQuery({
    queryKey: ["my-reservations"],
    queryFn: reservationApi.listReservations,
  });

  const myReservations = reservations.filter((r) => r.renterId === user?._id);

  // Same split as Profile.tsx's reservations tab: a confirmed reservation
  // whose stay already ended is functionally "past" (and reviewable), not
  // still active.
  const hasEnded = (r: (typeof myReservations)[number]) => new Date(r.endDate) <= new Date();
  const activeReservations = myReservations.filter(
    (r) => r.status === "pending_host_confirmation" || (r.status === "confirmed" && !hasEnded(r))
  );
  const pastReservations = myReservations.filter(
    (r) => r.status === "declined" || r.status === "expired" || (r.status === "confirmed" && hasEnded(r))
  );

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="text-2xl font-semibold text-slate-900">
        Welcome back{user ? `, ${user.name}` : ""}
      </h1>
      <p className="text-sm text-slate-600">Your reservations, messages with hosts, and reviews, all in one place.</p>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_320px]">
        <ReservationsTab
          checkoutBanner={null}
          onDismissBanner={() => {}}
          loading={isLoading}
          activeReservations={activeReservations}
          pastReservations={pastReservations}
          onFindSpace={() => navigate("/")}
        />

        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm h-fit">
          <h3 className="text-lg font-semibold text-slate-900">Smart Match</h3>
          <p className="text-sm text-slate-600">Describe what you need to store and get suggested spaces.</p>
          <Link
            to="/match"
            className="mt-3 inline-flex rounded-lg bg-accent-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-accent-500"
          >
            Try Smart Match
          </Link>
        </div>
      </div>
    </div>
  );
}
