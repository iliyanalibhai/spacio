import { DollarSign, PiggyBank, ShieldCheck, TrendingDown } from "lucide-react";

// Numbers from the real business model (docs/DOCUMENTATION.md §5), not
// invented copy: the pricing formula, the box/insurance add-ons, and the
// $5,000-10,000 declared-value insurance tier ($45/mo) set the ceiling.
const STATS = [
  { icon: DollarSign, label: "$25–70/mo", detail: "typical space price" },
  { icon: TrendingDown, label: "Save up to 50%", detail: "vs. traditional storage units" },
  { icon: ShieldCheck, label: "Up to $10,000", detail: "in declared-value insurance" },
  { icon: PiggyBank, label: "Identity-verified", detail: "hosts, every listing" },
];

export function ValueProps() {
  return (
    <section className="py-2">
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {STATS.map(({ icon: Icon, label, detail }) => (
          <div key={label} className="rounded-2xl border border-slate-200 bg-white p-5 text-center shadow-sm">
            <Icon className="mx-auto h-6 w-6 text-accent-600" aria-hidden />
            <p className="mt-2 text-lg font-bold text-slate-900">{label}</p>
            <p className="text-sm text-slate-500">{detail}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
