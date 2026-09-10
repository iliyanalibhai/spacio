import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { Message, Reservation } from "../types";
import * as reservationApi from "../api/reservations";
import * as paymentsApi from "../api/payments";
import * as messageApi from "../api/messages";
import { estimateRefund } from "../lib/refundPolicy";

const PAYMENT_STATUS_LABEL: Record<Reservation["paymentStatus"], string> = {
  pending_payment: "Awaiting renter payment",
  authorized: "Payment authorized",
  captured: "Payment captured",
  canceled: "Payment canceled",
  payment_expired: "Payment session expired",
  refunded: "Refunded in full",
  partially_refunded: "Partially refunded",
};

export function ReservationList({ asHost }: { asHost: boolean }) {
  const { data: reservations = [], isLoading } = useQuery({
    queryKey: ["reservations"],
    queryFn: reservationApi.listReservations,
  });

  if (isLoading) return <p className="text-slate-600">Loading reservations…</p>;
  if (!reservations.length) return <p className="text-slate-600">No reservations yet.</p>;

  return (
    <div className="grid gap-3">
      {reservations.map((r) => (
        <ReservationCard key={r._id} reservation={r} asHost={asHost} />
      ))}
    </div>
  );
}

function ReservationCard({ reservation, asHost }: { reservation: Reservation; asHost: boolean }) {
  const [showMessages, setShowMessages] = useState(false);
  const [confirmingCancel, setConfirmingCancel] = useState(false);
  const { data: messages = [], refetch } = useQuery({
    queryKey: ["messages", reservation._id],
    queryFn: () => messageApi.listMessages(reservation._id),
    enabled: showMessages,
  });
  const send = useMutation({
    mutationFn: (content: string) => messageApi.sendMessage({ reservationId: reservation._id, content }),
    onSuccess: () => refetch(),
  });
  const [message, setMessage] = useState("");
  const queryClient = useQueryClient();
  const invalidateReservations = () => queryClient.invalidateQueries({ queryKey: ["reservations"] });

  const approve = useMutation({
    mutationFn: () => reservationApi.approveReservation(reservation._id),
    onSuccess: invalidateReservations,
  });
  const decline = useMutation({
    mutationFn: () => reservationApi.declineReservation(reservation._id),
    onSuccess: invalidateReservations,
  });
  const cancel = useMutation({
    mutationFn: () => reservationApi.cancelReservation(reservation._id),
    onSuccess: () => {
      setConfirmingCancel(false);
      invalidateReservations();
    },
  });
  const retryPayment = useMutation({
    mutationFn: () => paymentsApi.startReservationCheckout(reservation._id),
    onSuccess: (data) => {
      window.location.href = data.url;
    },
  });

  const addOns: string[] = [];
  if (reservation.boxCost > 0) addOns.push(`${reservation.numBoxes} box${reservation.numBoxes === 1 ? "" : "es"} $${reservation.boxCost}`);
  if (reservation.insuranceCost > 0) addOns.push(`insurance $${reservation.insuranceCost}`);

  const canRetryPayment =
    !asHost &&
    reservation.status === "pending_host_confirmation" &&
    (reservation.paymentStatus === "pending_payment" || reservation.paymentStatus === "payment_expired");
  const canApprove = reservation.paymentStatus === "authorized";

  const canCancel =
    !asHost &&
    (reservation.status === "pending_host_confirmation" || reservation.status === "confirmed");
  // Only a confirmed booking has money to refund; before approval a cancel
  // just releases the hold.
  const refund =
    reservation.status === "confirmed"
      ? estimateRefund(reservation.startDate, reservation.totalPrice)
      : null;
  const cancelError = (cancel.error as { response?: { data?: { detail?: string } } })?.response?.data
    ?.detail;

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-xs uppercase text-slate-500">{reservation._id}</p>
          <p className="text-sm text-slate-600">
            {reservation.startDate} → {reservation.endDate}
          </p>
          <p className="text-sm text-slate-600">Status: {reservation.status}</p>
          <p className="text-sm text-slate-600">{PAYMENT_STATUS_LABEL[reservation.paymentStatus]}</p>
          <p className="text-sm text-slate-600">
            Total ${reservation.totalPrice} (fee ${reservation.serviceFee}
            {addOns.length > 0 && ` + ${addOns.join(" + ")}`})
          </p>
        </div>
        {asHost && reservation.status === "pending_host_confirmation" && (
          <div className="flex flex-col items-end gap-1">
            <div className="flex gap-2">
              <button
                onClick={() => approve.mutate()}
                disabled={!canApprove || approve.isPending}
                title={canApprove ? undefined : "Waiting for the renter to complete payment"}
                className="rounded-lg bg-emerald-600 px-3 py-1 text-white disabled:opacity-50"
              >
                {approve.isPending ? "Approving..." : "Approve"}
              </button>
              <button
                onClick={() => decline.mutate()}
                disabled={decline.isPending}
                className="rounded-lg bg-red-600 px-3 py-1 text-white disabled:opacity-50"
              >
                {decline.isPending ? "Declining..." : "Decline"}
              </button>
            </div>
            {approve.isError && (
              <p className="text-xs text-red-600">
                {(approve.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
                  "Approval failed"}
              </p>
            )}
          </div>
        )}
        {!asHost && canRetryPayment && (
          <button
            className="text-sm text-brand-600 underline"
            onClick={() => retryPayment.mutate()}
            disabled={retryPayment.isPending}
          >
            {retryPayment.isPending ? "Opening Stripe..." : "Complete payment"}
          </button>
        )}
        {canCancel && !confirmingCancel && (
          <button
            className="text-sm text-red-600 underline"
            onClick={() => setConfirmingCancel(true)}
          >
            Cancel reservation
          </button>
        )}
        <button className="text-sm text-brand-600 underline" onClick={() => setShowMessages((s) => !s)}>
          {showMessages ? "Hide messages" : "Messages"}
        </button>
      </div>
      {confirmingCancel && (
        <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3">
          <p className="text-sm text-slate-700">
            {refund
              ? refund.message
              : "You haven't been charged yet — cancelling just releases the payment hold."}
          </p>
          {refund?.tier === "none" ? (
            <button
              className="mt-2 text-sm text-slate-500 underline"
              onClick={() => setConfirmingCancel(false)}
            >
              Close
            </button>
          ) : (
            <div className="mt-2 flex gap-2">
              <button
                onClick={() => cancel.mutate()}
                disabled={cancel.isPending}
                className="rounded-lg bg-red-600 px-3 py-1 text-sm text-white disabled:opacity-50"
              >
                {cancel.isPending ? "Cancelling..." : "Yes, cancel"}
              </button>
              <button
                onClick={() => setConfirmingCancel(false)}
                disabled={cancel.isPending}
                className="text-sm text-slate-500 underline"
              >
                Keep reservation
              </button>
            </div>
          )}
          {cancel.isError && (
            <p className="mt-1 text-xs text-red-600">{cancelError || "Cancellation failed"}</p>
          )}
        </div>
      )}
      {showMessages && (
        <div className="mt-3 rounded-lg border border-slate-200 p-3">
          {!messages.length && <p className="text-sm text-slate-500">No messages yet.</p>}
          <div className="flex flex-col gap-3">
            {messages.map((m: Message) => {
              const isFromHost = m.senderId !== reservation.renterId;
              return (
                <div
                  key={m._id}
                  className={`rounded-lg p-3 text-sm ${isFromHost ? "bg-purple-50 border border-purple-100" : "bg-blue-50 border border-blue-100"}`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className={`text-xs font-semibold ${isFromHost ? "text-purple-600" : "text-blue-600"}`}>
                      {isFromHost ? "Host (You)" : "Renter"}
                    </span>
                    <span className="text-xs text-slate-400">{new Date(m.createdAt).toLocaleString()}</span>
                  </div>
                  <p className="text-slate-700">{m.content}</p>
                </div>
              );
            })}
          </div>
          <div className="mt-3 flex gap-2">
            <input
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && message.trim()) {
                  send.mutateAsync(message.trim());
                  setMessage("");
                }
              }}
              placeholder="Type a message"
              className="flex-1 rounded-lg border border-slate-200 px-3 py-2"
            />
            <button
              className="rounded-lg bg-brand-600 px-3 py-2 text-white"
              onClick={async () => {
                if (!message.trim()) return;
                await send.mutateAsync(message.trim());
                setMessage("");
              }}
            >
              Send
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
