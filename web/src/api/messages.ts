import api from "./client";
import type { Message } from "../types";

export async function listMessages(reservationId: string) {
  const { data } = await api.get<Message[]>(`/messages/${reservationId}`);
  return data;
}

export async function sendMessage(payload: {
  reservationId: string;
  content: string;
}) {
  const { data } = await api.post<Message>("/messages", payload);
  return data;
}
