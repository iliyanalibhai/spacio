import { useMutation, useQuery } from "@tanstack/react-query";
import * as paymentsApi from "../api/payments";

// Structural sibling of VerificationCard: poll a status endpoint, and on
// the action button navigate to a Stripe-hosted flow. A host must finish
// this before creating listings (the backend 403s otherwise) — a booking
// can't be approved without somewhere to send the money.
export function PayoutOnboardingCard() {
  const { data: status, isLoading, refetch } = useQuery({
    queryKey: ["connect-status"],
    queryFn: paymentsApi.getConnectStatus,
    refetchInterval: 5000,
  });

  const startOnboarding = useMutation({
    mutationFn: paymentsApi.startConnectOnboarding,
    onSuccess: (data) => {
      window.location.href = data.url;
    },
  });

  const onboarded = status?.onboarded ?? false;
  const inProgress = !onboarded && Boolean(status?.accountId);

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-slate-900">Payouts</h3>
          <p className="text-sm text-slate-600">
            Add your bank details so Spacio can pay you when a booking is approved.
          </p>
        </div>
        {onboarded && (
          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-3 py-1 text-sm font-semibold text-emerald-700">
            Payouts enabled
          </span>
        )}
      </div>

      {isLoading ? (
        <p className="mt-3 text-sm text-slate-500">Checking status...</p>
      ) : onboarded ? (
        <div className="mt-3 rounded-lg bg-emerald-50 p-3">
          <p className="text-sm text-emerald-700">
            Your payout account is set up. Approved bookings pay out to your bank automatically.
          </p>
        </div>
      ) : inProgress ? (
        <div className="mt-3 rounded-lg bg-amber-50 p-3">
          <p className="text-sm text-amber-700">
            Payout setup isn't finished. Stripe may still be reviewing your details.
          </p>
          <div className="mt-2 flex gap-3">
            <button
              onClick={() => startOnboarding.mutate()}
              disabled={startOnboarding.isPending}
              className="text-sm font-medium text-amber-700 underline disabled:opacity-60"
            >
              {startOnboarding.isPending ? "Opening Stripe..." : "Finish setup"}
            </button>
            <button onClick={() => refetch()} className="text-sm font-medium text-amber-700 underline">
              Check status
            </button>
          </div>
        </div>
      ) : (
        <div className="mt-4">
          <p className="mb-3 text-sm text-slate-600">
            Handled securely by Stripe. You'll need your bank account and a government ID.
          </p>
          <button
            onClick={() => startOnboarding.mutate()}
            disabled={startOnboarding.isPending}
            className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-500 disabled:opacity-60"
          >
            {startOnboarding.isPending ? "Opening Stripe..." : "Set up payouts"}
          </button>
        </div>
      )}

      {startOnboarding.error && (
        <p className="mt-2 text-sm text-red-600">
          {(startOnboarding.error as { response?: { data?: { detail?: string } } })?.response?.data
            ?.detail || "Failed to start payout setup"}
        </p>
      )}
    </div>
  );
}
