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
