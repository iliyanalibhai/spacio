import api from "./client";
import type { Listing, StorageSize } from "../types";

export async function fetchListings(params: {
  zipCode?: string;
  startDate?: string;
  endDate?: string;
  priceMin?: number;
  priceMax?: number;
  size?: StorageSize;
  // A ZIP alone geocodes server-side; lat/lng override it ("near me").
  lat?: number;
  lng?: number;
  radiusMiles?: number;
}) {
  const { data } = await api.get<Listing[]>("/listings", { params });
  return data;
}

export async function fetchListing(id: string) {
  const { data } = await api.get<Listing>(`/listings/${id}`);
  return data;
}

export async function createListing(payload: {
  title: string;
  description: string;
  size: StorageSize;
  sizeSqft: number;
  pricePerMonth: number;
  addressSummary: string;
  zipCode: string;
  availableFrom: string;
  availableTo: string;
  bookingDeadline?: string | null;
  images: string[];
}) {
  const { data } = await api.post<Listing>("/listings", payload);
  return data;
}

export async function fetchMyListings() {
  const { data } = await api.get<Listing[]>("/listings/mine");
  return data;
}

export async function updateListing(
  id: string,
  payload: Partial<{
    title: string;
    description: string;
    size: StorageSize;
    pricePerMonth: number;
    addressSummary: string;
    zipCode: string;
    images: string[];
    availability: boolean;
  }>
) {
  const { data } = await api.patch<Listing>(`/listings/${id}`, payload);
  return data;
}

export async function deleteListing(id: string) {
  await api.delete(`/listings/${id}`);
}

export async function uploadImage(file: File) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post<{ url: string }>("/listings/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}
