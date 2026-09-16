import { Lock, ScanFace, ShieldCheck } from "lucide-react";

const PILLARS = [
  {
    icon: ScanFace,
    title: "Verified identity, with a selfie match",
    body: "Every host completes Stripe Identity verification — a government ID plus a live selfie match — before they can publish a listing.",
  },
  {
    icon: ShieldCheck,
    title: "Declared-value insurance",
    body: "Cover your belongings for their real value, in tiers up to $10,000, priced by what you're actually storing.",
  },
  {
    icon: Lock,
    title: "Optional lockable secure box",
    body: "Add a $10/month lockable box for anything you don't want shared space for — only you hold the key.",
  },
];

// Customer research on this product found trust was the top adoption
// barrier for a peer-to-peer storage marketplace — 93.8% named security of
// belongings, 87.5% named trusting strangers (docs/DOCUMENTATION.md §10) —
// so this section is surfacing what's already built, not decoration.
export function TrustSection() {
  return (
    <section>
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold text-slate-900">Built to be trusted with your stuff</h2>
        <p className="mt-2 text-slate-600">
          In our research, 94% of renters worried about the safety of their belongings and 88% worried
          about trusting a stranger. Here's what actually protects you.
        </p>
      </div>
      <div className="grid gap-6 md:grid-cols-3">
        {PILLARS.map(({ icon: Icon, title, body }) => (
          <div key={title} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-100">
              <Icon className="h-6 w-6 text-brand-700" aria-hidden />
            </div>
            <h3 className="mt-4 font-semibold text-slate-900">{title}</h3>
            <p className="mt-1 text-sm text-slate-600">{body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
