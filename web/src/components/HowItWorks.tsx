export function HowItWorks() {
  return (
    <section className="pt-8">
      <h2 className="text-2xl font-bold text-slate-900 text-center mb-10">How Spacio Works</h2>
      <div className="grid md:grid-cols-3 gap-8">
        <div className="text-center">
          <div className="mx-auto w-16 h-16 rounded-2xl bg-brand-100 flex items-center justify-center mb-4" />
          <h3 className="font-semibold text-lg text-slate-900">Search</h3>
          <p className="mt-2 text-slate-600">Enter your location and dates to find available storage spaces near you.</p>
        </div>
        <div className="text-center">
          <div className="mx-auto w-16 h-16 rounded-2xl bg-brand-100 flex items-center justify-center mb-4" />
          <h3 className="font-semibold text-lg text-slate-900">Book Securely</h3>
          <p className="mt-2 text-slate-600">Reserve your space instantly with secure payment and optional insurance.</p>
        </div>
        <div className="text-center">
          <div className="mx-auto w-16 h-16 rounded-2xl bg-brand-100 flex items-center justify-center mb-4" />
          <h3 className="font-semibold text-lg text-slate-900">Store & Save</h3>
          <p className="mt-2 text-slate-600">Access your storage anytime. Save up to 50% compared to traditional units.</p>
        </div>
      </div>
    </section>
  );
}
