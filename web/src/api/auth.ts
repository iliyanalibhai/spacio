import api from "./client";
import type { User } from "../types";

export type RegisterPayload = {
  name: string;
  email: string;
  password: string;
  zipCode: string;
  isHost: boolean;
  phone?: string;
  backgroundCheckAccepted?: boolean;
};

export async function register(payload: RegisterPayload): Promise<User> {
  const { data } = await api.post<User>("/auth/register", payload);
  return data;
}

export async function login(email: string, password: string) {
  const body = new URLSearchParams();
  body.append("username", email);
  body.append("password", password);
  const { data } = await api.post("/auth/login", body, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  return data as { access_token: string; token_type: string };
}

export async function me(): Promise<User> {
  const { data } = await api.get<User>("/auth/me");
  return data;
}
