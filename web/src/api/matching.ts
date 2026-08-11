import api from "./client";
import type { Listing } from "../types";

export async function recommend(input: { query: string; zipCode?: string }) {
  const { data } = await api.post<{
    listings: Listing[];
    explanation: string;
  }>("/matching/recommend", input);
  return data;
}
