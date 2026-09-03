import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { Message, Reservation } from "../types";
import { useAuth } from "../hooks/useAuth";
import * as listingApi from "../api/listings";
import * as messageApi from "../api/messages";
import * as paymentsApi from "../api/payments";
import { getListingImage } from "../lib/getListingImage";
import { formatDateOnly } from "../lib/formatDate";

const statusConfig = {
  pending_host_confirmation: { bg: "bg-amber-100", text: "text-amber-700", label: "Pending Approval" },
  confirmed: { bg: "bg-emerald-100", text: "text-emerald-700", label: "Confirmed" },
  declined: { bg: "bg-red-100", text: "text-red-700", label: "Declined" },
  expired: { bg: "bg-slate-100", text: "text-slate-600", label: "Expired" },
} as const;

const PAYMENT_STATUS_LABEL: Record<Reservation["paymentStatus"], string> = {
  pending_payment: "Payment needed",
  authorized: "Payment authorized",
  captured: "Payment captured",
  canceled: "Not charged",
  payment_expired: "Payment session expired",
};

export function ProfileReservationCard({ reservation }: { reservation: Reservation }) {
  const { user } = useAuth();
  const [showChat, setShowChat] = useState(false);
  const [message, setMessage] = useState("");
  const queryClient = useQueryClient();

  const { data: listing } = useQuery({
    queryKey: ["listing", reservation.listingId],
    queryFn: () => listingApi.fetchListing(reservation.listingId),
  });

  const { data: messages = [] } = useQuery({
    queryKey: ["messages", reservation._id],
    queryFn: () => messageApi.listMessages(reservation._id),
    enabled: showChat,
    refetchInterval: showChat ? 3000 : false,
  });

  const sendMsg = useMutation({
    mutationFn: (content: string) => messageApi.sendMessage({ reservationId: reservation._id, content }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["messages", reservation._id] });
    },
  });

  const retryPayment = useMutation({
    mutationFn: () => paymentsApi.startReservationCheckout(reservation._id),
    onSuccess: (data) => {
      window.location.href = data.url;
    },
  });

  const status = statusConfig[reservation.status];
  const isHostMessage = (msg: Message) => msg.senderId !== reservation.renterId;
  const needsPayment =
    reservation.status === "pending_host_confirmation" &&
    (reservation.paymentStatus === "pending_payment" || reservation.paymentStatus === "payment_expired");

  return (
    <>
      <div
        className="flex gap-4 p-4 rounded-xl border border-slate-200 hover:border-brand-300 hover:shadow-md transition-all cursor-pointer"
        onClick={() => setShowChat(true)}
      >
        <img
          src={getListingImage(listing)}
          alt={listing?.title || "Storage space"}
          className="h-24 w-24 rounded-lg object-cover flex-shrink-0"
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div>
              <h3 className="font-semibold text-slate-900">{listing?.title || "Loading..."}</h3>
              <p className="text-sm text-slate-500">{listing?.addressSummary}</p>
            </div>
            <span className={`${status.bg} ${status.text} px-2.5 py-1 rounded-full text-xs font-semibold flex-shrink-0`}>
              {status.label}
            </span>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-4 text-sm">
            <div className="flex items-center gap-1 text-slate-600">
              <span>
                {formatDateOnly(reservation.startDate)} - {formatDateOnly(reservation.endDate)}
              </span>
            </div>
            <div className="flex items-center gap-2">
              {reservation.insuranceCost > 0 && (
                <span className="text-xs text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full">Insured</span>
              )}
              {reservation.boxCost > 0 && (
                <span className="text-xs text-brand-600 bg-brand-50 px-2 py-0.5 rounded-full">
                  {reservation.numBoxes} box{reservation.numBoxes === 1 ? "" : "es"}
                </span>
              )}
              <span className="font-bold text-slate-900">${reservation.totalPrice}</span>
            </div>
            <span className={`text-xs ${needsPayment ? "text-amber-600 font-medium" : "text-slate-500"}`}>
              {PAYMENT_STATUS_LABEL[reservation.paymentStatus]}
            </span>
            {needsPayment && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  retryPayment.mutate();
                }}
                disabled={retryPayment.isPending}
                className="text-sm font-medium text-brand-600 underline disabled:opacity-60"
              >
                {retryPayment.isPending ? "Opening Stripe..." : "Complete payment"}
              </button>
            )}
            <div className="flex items-center gap-1 text-brand-600">
              <span className="text-sm font-medium">Chat with Host</span>
            </div>
          </div>
        </div>
      </div>

      {showChat && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-lg rounded-2xl bg-white shadow-xl flex flex-col max-h-[80vh]">
            <div className="flex items-center justify-between p-4 border-b border-slate-200">
              <div>
                <h3 className="font-semibold text-slate-900">{listing?.title || "Reservation"}</h3>
                <p className="text-sm text-slate-500">Chat with your host</p>
              </div>
              <button
                onClick={() => setShowChat(false)}
                className="rounded-full p-2 hover:bg-slate-100 transition-colors"
              >
                <svg className="h-5 w-5 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {messages.length === 0 ? (
                <p className="text-center text-slate-500 py-8">No messages yet. Start the conversation!</p>
              ) : (
                messages.map((msg: Message) => {
                  const fromHost = isHostMessage(msg);
                  const isMe = msg.senderId === user?._id;
                  return (
                    <div key={msg._id} className={`flex flex-col ${isMe ? "items-end" : "items-start"}`}>
                      <span className={`text-xs font-semibold mb-1 ${fromHost ? "text-purple-600" : "text-brand-600"}`}>
                        {fromHost ? "Host" : "You"}
                      </span>
                      <div
                        className={`rounded-2xl px-4 py-2 max-w-[80%] ${
                          isMe ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-900"
                        }`}
                      >
                        <p className="text-sm">{msg.content}</p>
                      </div>
                      <span className="text-xs text-slate-400 mt-1">{new Date(msg.createdAt).toLocaleString()}</span>
                    </div>
                  );
                })
              )}
            </div>

            <div className="p-4 border-t border-slate-200">
              <div className="flex gap-2">
                <input
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && message.trim()) {
                      sendMsg.mutate(message.trim());
                      setMessage("");
                    }
                  }}
                  placeholder="Type a message..."
                  className="flex-1 rounded-full border border-slate-200 px-4 py-2 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                />
                <button
                  onClick={() => {
                    if (message.trim()) {
                      sendMsg.mutate(message.trim());
                      setMessage("");
                    }
                  }}
                  disabled={!message.trim() || sendMsg.isPending}
                  className="rounded-full bg-brand-600 px-4 py-2 text-white hover:bg-brand-500 disabled:opacity-50 transition-colors"
                >
                  {sendMsg.isPending ? "..." : "Send"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
