import type { User } from "../types";

type Props = {
  user: User;
  becomingHost: boolean;
  onBecomeHost: () => void;
};

export function ProfileInfoTab({ user, becomingHost, onBecomeHost }: Props) {
  return (
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
                onClick={onBecomeHost}
                disabled={becomingHost}
                className="mt-4 bg-brand-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-brand-500 transition-colors disabled:opacity-50"
              >
                {becomingHost ? "Starting verification..." : "Become a Host"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
