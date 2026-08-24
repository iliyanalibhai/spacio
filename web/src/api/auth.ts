import api from "./client";
import type { User } from "../types";

export type RegisterPayload = {
  name: string;
  email: string;
  password: string;
  zipCode: string;
  isHost: boolean;
  phone?: string;
};

export async function register(payload: RegisterPayload): Promise<User> {
  const { data } = await api.post<User>("/auth/register", payload);
  return data;
}

export async function login(email: string, password: string): Promise<User> {
  const body = new URLSearchParams();
  body.append("username", email);
  body.append("password", password);
  // The backend sets the session as an httpOnly cookie on this response
  // (JS can't read it, which is the whole point); the body just carries the
  // logged-in user's profile so the UI has something to render immediately.
  const { data } = await api.post<User>("/auth/login", body, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  return data;
}

export async function logout(): Promise<void> {
  // Only the server can clear an httpOnly cookie — there's no client-side
  // equivalent of localStorage.removeItem() for it.
  await api.post("/auth/logout");
}

export async function me(): Promise<User> {
  const { data } = await api.get<User>("/auth/me");
  return data;
}
