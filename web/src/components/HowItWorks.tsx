import { PiggyBank, Search, ShieldCheck } from "lucide-react";

const STEPS = [
  {
    icon: Search,
    title: "Search",
    body: "Enter your location and dates to find available storage spaces near you.",
  },
  {
    icon: ShieldCheck,
    title: "Book Securely",
    body: "Reserve your space instantly with secure payment and optional insurance.",
  },
  {
    icon: PiggyBank,
    title: "Store & Save",
    body: "Access your storage anytime. Save up to 50% compared to traditional units.",
  },
];

export function HowItWorks() {
  return (
    <section className="pt-8">
      <h2 className="text-2xl font-bold text-slate-900 text-center mb-10">How Spacio Works</h2>
      <div className="grid md:grid-cols-3 gap-8">
        {STEPS.map(({ icon: Icon, title, body }) => (
          <div key={title} className="text-center">
            <div className="mx-auto w-16 h-16 rounded-2xl bg-brand-100 flex items-center justify-center mb-4">
              <Icon className="h-8 w-8 text-brand-700" aria-hidden />
            </div>
            <h3 className="font-semibold text-lg text-slate-900">{title}</h3>
            <p className="mt-2 text-slate-600">{body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
