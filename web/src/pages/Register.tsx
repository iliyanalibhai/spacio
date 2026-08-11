import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { useAuth } from "../hooks/useAuth";
import * as verificationApi from "../api/verification";

export function Register() {
  const { register, loading, error } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    zipCode: "",
    isHost: false,
    phone: "",
    backgroundCheckAccepted: false,
  });

  const startVerification = useMutation({
    mutationFn: verificationApi.createVerificationSession,
    onSuccess: (data) => {
      window.location.href = data.url;
    },
  });

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    await register(form);

    if (form.isHost) {
      try {
        await startVerification.mutateAsync();
      } catch {
        navigate("/host");
      }
    } else {
      navigate("/");
    }
  };

  return (
    <div className="mx-auto flex min-h-[70vh] max-w-md flex-col justify-center px-4">
      <h1 className="text-2xl font-semibold text-slate-900">Create account</h1>
      <form className="mt-4 flex flex-col gap-3" onSubmit={handleSubmit}>
        <input
          required
          placeholder="Name"
          className="rounded-lg border border-slate-200 px-3 py-2"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
        />
        <input
          required
          type="email"
          placeholder="Email"
          className="rounded-lg border border-slate-200 px-3 py-2"
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
        />
        <input
          required
          type="password"
          placeholder="Password"
          className="rounded-lg border border-slate-200 px-3 py-2"
          value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
        />
        <input
          required
          placeholder="ZIP code"
          className="rounded-lg border border-slate-200 px-3 py-2"
          value={form.zipCode}
          onChange={(e) => setForm({ ...form, zipCode: e.target.value })}
        />
        <input
          placeholder="Phone (optional)"
          className="rounded-lg border border-slate-200 px-3 py-2"
          value={form.phone}
          onChange={(e) => setForm({ ...form, phone: e.target.value })}
        />
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={form.isHost}
            onChange={(e) => setForm({ ...form, isHost: e.target.checked })}
          />
          I want to host spaces
        </label>
        {form.isHost && (
          <div className="rounded-lg bg-blue-50 p-3 text-sm text-blue-700">
            <p className="font-medium">Identity Verification Required</p>
            <p className="mt-1 text-blue-600">
              As a host, you'll be asked to verify your identity (ID + selfie) after registration to build trust with renters.
            </p>
          </div>
        )}
        {error && <p className="text-sm text-red-600">{error}</p>}
        {startVerification.error && (
          <p className="text-sm text-red-600">
            {(startVerification.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
              "Verification setup failed, but your account was created. You can verify later from the Host dashboard."}
          </p>
        )}
        <button
          type="submit"
          className="rounded-lg bg-brand-600 px-4 py-2 text-white shadow-sm disabled:opacity-60"
          disabled={loading || startVerification.isPending}
        >
          {loading
            ? "Creating account..."
            : startVerification.isPending
              ? "Starting verification..."
              : form.isHost
                ? "Register & Verify Identity"
                : "Register"}
        </button>
      </form>
    </div>
  );
}
