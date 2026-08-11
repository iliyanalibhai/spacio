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
  // Genuinely null until Phase 4's review system exists — the backend
  // deliberately removed v1's hardcoded 4.7 default. Do not fall back to a
  // fake number in the UI.
  rating?: number | null;
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
  paymentStatus: string;
  holdExpiresAt: string;
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
};
