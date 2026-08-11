import api from "./client";

export interface VerificationSession {
  url: string;
  sessionId: string;
}

export interface VerificationStatus {
  status: string;
  verified: boolean;
  stripeStatus?: string;
  error?: string;
}

export async function createVerificationSession(): Promise<VerificationSession> {
  const { data } = await api.post<VerificationSession>("/verification/create-session");
  return data;
}

export async function getVerificationStatus(): Promise<VerificationStatus> {
  const { data } = await api.get<VerificationStatus>("/verification/status");
  return data;
}
