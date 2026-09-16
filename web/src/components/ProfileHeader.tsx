import type { User } from "../types";

type Props = {
  user: User;
  becomingHost: boolean;
  onBecomeHost: () => void;
  onGoToHostDashboard: () => void;
};

export function ProfileHeader({ user, becomingHost, onBecomeHost, onGoToHostDashboard }: Props) {
  return (
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
          {/* Navigation is gated only on isHost, never on verification
              status — the dashboard (behind App.tsx's hostOnly route
              guard, which already only checks isHost) is where an
              unverified host actually goes to become verified. Gating
              this button the way the old Nav.tsx link was gated is
              exactly what caused the verification deadlock; see
              docs/DOCUMENTATION.md §10. */}
          {user.isHost ? (
            <button
              onClick={onGoToHostDashboard}
              className="bg-brand-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-brand-500 transition-colors"
            >
              Host Dashboard
            </button>
          ) : (
            <button
              onClick={onBecomeHost}
              disabled={becomingHost}
              className="bg-gradient-to-r from-brand-600 to-brand-500 text-white px-4 py-2 rounded-lg font-medium hover:from-brand-500 hover:to-brand-400 transition-all disabled:opacity-50"
            >
              {becomingHost ? "Starting..." : "Become a Host"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
