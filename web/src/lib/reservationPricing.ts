// Client-side mirror of api/app/services/reservation_pricing.py, used only
// for an instant quote in the booking form. The server recomputes and is
// the source of truth — this just avoids a round trip on every keystroke.
// Keep in sync with the backend if the business rules in
// docs/DOCUMENTATION.md §5 change.

export const SERVICE_FEE_RATE = 0.2;
export const BOX_PRICE_PER_MONTH = 10;

// (max declared value, monthly cost], same tiers as the backend.
const INSURANCE_TIERS: Array<[number, number]> = [
  [1_000, 12],
  [3_000, 20],
  [5_000, 30],
  [10_000, 45],
];

export function insuranceMonthlyCost(declaredValue: number): number | null {
  for (const [maxValue, cost] of INSURANCE_TIERS) {
    if (declaredValue <= maxValue) return cost;
  }
  return null; // exceeds the highest tier; server will reject
}

export type ReservationQuote = {
  days: number;
  spaceRatioPct: number;
  base: number;
  serviceFee: number;
  boxCost: number;
  insuranceCost: number;
  total: number;
};

export function quoteReservation(input: {
  hostMonthlyPrice: number;
  totalSqft: number;
  sqftRequested: number;
  startDate: string;
  endDate: string;
  numBoxes: number;
  insuranceDeclaredValue: number | null;
  hasOwnInsurance: boolean;
}): ReservationQuote | null {
  if (!input.startDate || !input.endDate || input.sqftRequested <= 0) return null;
  const start = new Date(input.startDate);
  const end = new Date(input.endDate);
  const days = Math.round((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24));
  if (days <= 0) return null;

  const monthFraction = days / 30;
  const spaceRatio = input.sqftRequested / input.totalSqft;
  const base = round2(input.hostMonthlyPrice * spaceRatio * monthFraction);
  const serviceFee = round2(base * SERVICE_FEE_RATE);
  const boxCost = round2(input.numBoxes * BOX_PRICE_PER_MONTH * monthFraction);

  let insuranceCost = 0;
  if (input.insuranceDeclaredValue != null && !input.hasOwnInsurance) {
    const tierCost = insuranceMonthlyCost(input.insuranceDeclaredValue);
    insuranceCost = tierCost != null ? round2(tierCost * monthFraction) : 0;
  }

  const total = round2(base + serviceFee + boxCost + insuranceCost);

  return {
    days,
    spaceRatioPct: Math.round(spaceRatio * 100),
    base,
    serviceFee,
    boxCost,
    insuranceCost,
    total,
  };
}

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}
