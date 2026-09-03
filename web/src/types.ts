export type StorageSize = "S" | "M" | "L";

export type Listing = {
  _id: string;
  hostId: string;
  title: string;
  description: string;
  size: StorageSize;
  sizeSqft?: number;
  availableSqft?: number;
  pricePerMonth: number;
  addressSummary: string;
  zipCode: string;
  images: string[];
  availability: boolean;
  availableFrom?: string;
  availableTo?: string;
  bookingDeadline?: string | null;
  // Genuinely null until the listing has at least one real review — the
  // backend deliberately removed v1's hardcoded 4.7 default. Do not fall
  // back to a fake number in the UI.
  rating?: number | null;
  // Real from the moment a listing exists (0, not null) — see Review below.
  reviewCount?: number;
  createdAt: string;
  hostVerified?: boolean;
};

export type Reservation = {
  _id: string;
  listingId: string;
  renterId: string;
  startDate: string;
  endDate: string;
  sqftRequested: number;
  numBoxes: number;
  insuranceDeclaredValue?: number | null;
  hasOwnInsurance: boolean;
  status: "pending_host_confirmation" | "confirmed" | "declined" | "expired";
  basePrice: number;
  serviceFee: number;
  boxCost: number;
  insuranceCost: number;
  totalPrice: number;
  // "pending_payment" until the renter completes Stripe Checkout,
  // "authorized" once the card hold is placed (manual capture), "captured"
  // once the host approves, "canceled"/"payment_expired" otherwise.
  paymentStatus: "pending_payment" | "authorized" | "captured" | "canceled" | "payment_expired";
  holdExpiresAt: string;
  createdAt: string;
};

export type Review = {
  _id: string;
  listingId: string;
  reservationId: string;
  renterId: string;
  rating: number;
  comment?: string | null;
  createdAt: string;
};

export type Message = {
  _id: string;
  reservationId: string;
  senderId: string;
  content: string;
  createdAt: string;
};

export type User = {
  _id: string;
  name: string;
  email: string;
  zipCode: string;
  isHost: boolean;
  phone?: string;
  verificationStatus?: string;
  // Stripe Connect payout onboarding. `stripeConnectOnboarded` gates
  // listing creation alongside `verificationStatus === "verified"`.
  stripeConnectAccountId?: string | null;
  stripeConnectOnboarded?: boolean;
};
