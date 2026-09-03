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

export interface CheckoutStatus {
  paymentStatus: string;
  error?: string | null;
}

/**
 * Start (or resume) Stripe Checkout to authorize the renter's card for a
 * reservation's total. Same redirect shape as `startConnectOnboarding` —
 * navigate to the returned URL. The card is authorized, not charged; the
 * host's approval is what captures it (`PaymentIntent.capture`).
 */
export async function startReservationCheckout(reservationId: string): Promise<{ url: string }> {
  const { data } = await api.post<{ url: string }>(`/payments/checkout/${reservationId}`);
  return data;
}

/** Poll a reservation's payment-authorization state — used right after the
 * renter is redirected back from Checkout, since the webhook may not have
 * landed yet. */
export async function getCheckoutStatus(reservationId: string): Promise<CheckoutStatus> {
  const { data } = await api.get<CheckoutStatus>(`/payments/checkout/status/${reservationId}`);
  return data;
}
