import type { Reservation } from "../types";
import { ProfileReservationCard } from "./ProfileReservationCard";

type CheckoutBanner = { kind: "success" | "cancelled"; text: string };

type Props = {
  checkoutBanner: CheckoutBanner | null;
  onDismissBanner: () => void;
  loading: boolean;
  activeReservations: Reservation[];
  pastReservations: Reservation[];
  onFindSpace: () => void;
};

export function ReservationsTab({
  checkoutBanner,
  onDismissBanner,
  loading,
  activeReservations,
  pastReservations,
  onFindSpace,
}: Props) {
  return (
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
          <button onClick={onDismissBanner} className="font-medium underline flex-shrink-0">
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

        {loading ? (
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
            <button onClick={onFindSpace} className="mt-4 text-brand-600 font-medium hover:text-brand-500">
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
  );
}
