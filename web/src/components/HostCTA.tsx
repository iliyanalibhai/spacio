import { Link } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

export function HostCTA() {
  const { user } = useAuth();
  // Send an already-registered visitor to where "Become a Host" actually
  // lives (ProfileHeader); a first-time visitor goes to registration first.
  const ctaTo = user ? "/profile" : "/register";

  return (
    <section className="rounded-3xl bg-gradient-to-br from-brand-800 to-brand-900 px-6 py-10 text-white sm:px-10">
      <div className="mx-auto max-w-3xl text-center">
        <h2 className="text-2xl font-bold sm:text-3xl">Have unused space?</h2>
        <p className="mt-3 text-brand-100">
          Hosts earn around <span className="font-semibold text-white">$128/month</span> across four
          renters — list a garage, closet, or spare room and start earning from space you're not using.
        </p>
        <Link
          to={ctaTo}
          className="mt-6 inline-flex items-center gap-2 rounded-lg bg-accent-600 px-6 py-3 font-semibold text-white shadow-sm transition hover:bg-accent-500"
        >
          Become a host
        </Link>
      </div>
    </section>
  );
}
