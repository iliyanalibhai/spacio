import api from "./client";
import type { Reservation } from "../types";

export async function createReservation(payload: {
  listingId: string;
  startDate: string;
  endDate: string;
  sqftRequested: number;
  numBoxes?: number;
  insuranceDeclaredValue?: number | null;
  hasOwnInsurance?: boolean;
}) {
  const { data } = await api.post<Reservation>("/reservations", payload);
  return data;
}

export async function listReservations() {
  const { data } = await api.get<Reservation[]>("/reservations");
  return data;
}

export async function approveReservation(id: string) {
  const { data } = await api.post<Reservation>(`/reservations/${id}/approve`);
  return data;
}

export async function declineReservation(id: string) {
  const { data } = await api.post<Reservation>(`/reservations/${id}/decline`);
  return data;
}

export async function deleteReservation(id: string) {
  await api.delete(`/reservations/${id}`);
}

// Renter-initiated cancellation. Before host approval this just releases the
// payment hold; after approval it runs the tiered refund (see
// lib/refundPolicy.ts) and the reservation ends in "cancelled".
export async function cancelReservation(id: string) {
  const { data } = await api.post<Reservation>(`/reservations/${id}/cancel`);
  return data;
}
