import api from "./client";

export interface ConnectStatus {
  onboarded: boolean;
  accountId?: string | null;
  error?: string | null;
}

/**
 * Start (or resume) Stripe Connect payout onboarding for the current host.
 * Returns a Stripe-hosted URL to navigate to, same shape as the Identity
 * verification flow (`window.location.href = url`).
 */
export async function startConnectOnboarding(): Promise<{ url: string }> {
  const { data } = await api.post<{ url: string }>("/payments/connect/onboard");
  return data;
}

/** Poll the host's payout-onboarding state. */
export async function getConnectStatus(): Promise<ConnectStatus> {
  const { data } = await api.get<ConnectStatus>("/payments/connect/status");
  return data;
}
