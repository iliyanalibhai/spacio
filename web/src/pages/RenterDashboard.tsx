import { Link } from "react-router-dom";
import { ReservationList } from "../components/ReservationList";

export function RenterDashboard() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="text-2xl font-semibold text-slate-900">Renter dashboard</h1>
      <div className="mt-6 grid gap-4">
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <h3 className="text-lg font-semibold text-slate-900">My reservations</h3>
          <ReservationList asHost={false} />
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <h3 className="text-lg font-semibold text-slate-900">Smart Match</h3>
          <p className="text-sm text-slate-600">Describe what you need to store and get suggested spaces.</p>
          <Link
            to="/match"
            className="mt-3 inline-flex rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white shadow-sm"
          >
            Try Smart Match
          </Link>
        </div>
      </div>
    </div>
  );
}
