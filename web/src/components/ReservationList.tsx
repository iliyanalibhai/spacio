import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { Message, Reservation } from "../types";
import * as reservationApi from "../api/reservations";
import * as messageApi from "../api/messages";

export function ReservationList({ asHost }: { asHost: boolean }) {
  const queryClient = useQueryClient();
  const { data: reservations = [], isLoading } = useQuery({
    queryKey: ["reservations"],
    queryFn: reservationApi.listReservations,
  });
  const approve = useMutation({
    mutationFn: (id: string) => reservationApi.approveReservation(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["reservations"] }),
  });
  const decline = useMutation({
    mutationFn: (id: string) => reservationApi.declineReservation(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["reservations"] }),
  });

  if (isLoading) return <p className="text-slate-600">Loading reservations…</p>;
  if (!reservations.length) return <p className="text-slate-600">No reservations yet.</p>;

  return (
    <div className="grid gap-3">
      {reservations.map((r) => (
        <ReservationCard
          key={r._id}
          reservation={r}
          asHost={asHost}
          onApprove={() => approve.mutate(r._id)}
          onDecline={() => decline.mutate(r._id)}
        />
      ))}
    </div>
  );
}

function ReservationCard({
  reservation,
  asHost,
  onApprove,
  onDecline,
}: {
  reservation: Reservation;
  asHost: boolean;
  onApprove: () => void;
  onDecline: () => void;
}) {
  const [showMessages, setShowMessages] = useState(false);
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
  const cancel = useMutation({
    mutationFn: () => reservationApi.deleteReservation(reservation._id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["reservations"] }),
  });

  const addOns: string[] = [];
  if (reservation.boxCost > 0) addOns.push(`${reservation.numBoxes} box${reservation.numBoxes === 1 ? "" : "es"} $${reservation.boxCost}`);
  if (reservation.insuranceCost > 0) addOns.push(`insurance $${reservation.insuranceCost}`);

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-xs uppercase text-slate-500">{reservation._id}</p>
          <p className="text-sm text-slate-600">
            {reservation.startDate} → {reservation.endDate}
          </p>
          <p className="text-sm text-slate-600">Status: {reservation.status}</p>
          <p className="text-sm text-slate-600">
            Total ${reservation.totalPrice} (fee ${reservation.serviceFee}
            {addOns.length > 0 && ` + ${addOns.join(" + ")}`})
          </p>
        </div>
        {asHost && reservation.status === "pending_host_confirmation" && (
          <div className="flex gap-2">
            <button onClick={onApprove} className="rounded-lg bg-emerald-600 px-3 py-1 text-white">
              Approve
            </button>
            <button onClick={onDecline} className="rounded-lg bg-red-600 px-3 py-1 text-white">
              Decline
            </button>
          </div>
        )}
        {!asHost && (
          <button
            className="text-sm text-red-600 underline"
            onClick={() => cancel.mutate()}
            disabled={cancel.isPending}
          >
            {cancel.isPending ? "Cancelling..." : "Cancel reservation"}
          </button>
        )}
        <button className="text-sm text-brand-600 underline" onClick={() => setShowMessages((s) => !s)}>
          {showMessages ? "Hide messages" : "Messages"}
        </button>
      </div>
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
