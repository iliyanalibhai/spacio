import { useEffect, useRef } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useAuth } from "../hooks/useAuth";
import * as verificationApi from "../api/verification";

type Props = {
  // Fires once, the moment a poll resolves to verified — not on every
  // refetch. GET /verification/status already syncs Mongo from the live
  // Stripe session on its own (see api/tests/test_verification.py), but
  // that doesn't update the app-wide `user` object from useAuth, which
  // still reflects whatever /auth/me last returned. Rendering this card
  // wherever a host might land right after Stripe's redirect (the Profile
  // page) and wiring this callback to refreshUser is what actually closes
  // the verification deadlock — see docs/DOCUMENTATION.md §10.
  onVerified?: () => void;
};

export function VerificationCard({ onVerified }: Props = {}) {
  const { user } = useAuth();
  const { data: status, isLoading, refetch } = useQuery({
    queryKey: ["verification-status"],
    queryFn: verificationApi.getVerificationStatus,
    refetchInterval: 5000,
  });

  const notifiedRef = useRef(false);
  useEffect(() => {
    if (status?.verified && !notifiedRef.current) {
      notifiedRef.current = true;
      onVerified?.();
    }
  }, [status?.verified, onVerified]);

  const createSession = useMutation({
    mutationFn: verificationApi.createVerificationSession,
    onSuccess: (data) => {
      window.location.href = data.url;
    },
  });

  const isVerified = status?.verified || user?.verificationStatus === "verified";
  const isPending = status?.status === "pending" || status?.status === "processing";

  const createSessionError = createSession.error as
    | { response?: { status?: number; data?: { detail?: string } } }
    | undefined;
  const isDisabled = createSessionError?.response?.status === 503;

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-slate-900">Identity Verification</h3>
          <p className="text-sm text-slate-600">Verify your ID to build trust with renters.</p>
        </div>
        {isVerified && (
          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-3 py-1 text-sm font-semibold text-emerald-700">
            Verified
          </span>
        )}
      </div>

      {isLoading ? (
        <p className="mt-3 text-sm text-slate-500">Checking status...</p>
      ) : isVerified ? (
        <div className="mt-3 rounded-lg bg-emerald-50 p-3">
          <p className="text-sm text-emerald-700">
            Your identity has been verified. Renters will see a "Verified Host" badge on your listings.
          </p>
        </div>
      ) : isPending ? (
        <div className="mt-3 rounded-lg bg-amber-50 p-3">
          <p className="text-sm text-amber-700">Verification in progress. This usually takes a few minutes.</p>
          <button onClick={() => refetch()} className="mt-2 text-sm font-medium text-amber-700 underline">
            Check status
          </button>
        </div>
      ) : (
        <div className="mt-4">
          <p className="text-sm text-slate-600 mb-3">
            Complete a quick ID verification (driver's license, passport, or ID card) with a selfie match.
          </p>
          <button
            onClick={() => createSession.mutate()}
            disabled={createSession.isPending}
            className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-500 disabled:opacity-60"
          >
            {createSession.isPending ? "Starting verification..." : "Verify My Identity"}
          </button>
          {isDisabled ? (
            <p className="mt-2 text-sm text-slate-500">
              Identity verification is disabled in this environment — no Stripe key configured.
            </p>
          ) : (
            createSession.error && (
              <p className="mt-2 text-sm text-red-600">
                {createSessionError?.response?.data?.detail || "Failed to start verification"}
              </p>
            )
          )}
        </div>
      )}
    </div>
  );
}
