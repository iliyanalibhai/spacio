import api from "./client";
import type { Review } from "../types";

export async function createReview(payload: { reservationId: string; rating: number; comment?: string | null }) {
  const { data } = await api.post<Review>("/reviews", payload);
  return data;
}

export async function listListingReviews(listingId: string) {
  const { data } = await api.get<Review[]>(`/reviews/listing/${listingId}`);
  return data;
}

/** Returns null if the reservation hasn't been reviewed yet. */
export async function getReservationReview(reservationId: string) {
  const { data } = await api.get<Review | null>(`/reviews/reservation/${reservationId}`);
  return data;
}
