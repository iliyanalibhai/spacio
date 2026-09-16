import { Link } from "react-router-dom";

export function Footer() {
  return (
    <footer className="border-t border-slate-200 bg-white">
      <div className="mx-auto max-w-6xl px-4 py-10">
        <div className="grid gap-8 sm:grid-cols-3">
          <div>
            <Link to="/" className="flex items-center gap-2">
              <img src="/icon.png" alt="" className="h-8 w-8 rounded-lg" />
              <span className="text-lg font-bold text-brand-800">spacio</span>
            </Link>
            <p className="mt-3 text-sm text-slate-500">
              Storage space from real people near you — pay only for the square footage you use.
            </p>
          </div>

          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400">For renters</h3>
            <ul className="mt-3 space-y-2 text-sm">
              <li>
                <Link to="/" className="text-slate-600 hover:text-brand-700">
                  Find storage
                </Link>
              </li>
              <li>
                <Link to="/match" className="text-slate-600 hover:text-brand-700">
                  Smart Match
                </Link>
              </li>
            </ul>
          </div>

          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400">For hosts</h3>
            <ul className="mt-3 space-y-2 text-sm">
              <li>
                <Link to="/register" className="text-slate-600 hover:text-brand-700">
                  Become a host
                </Link>
              </li>
              <li>
                <Link to="/login" className="text-slate-600 hover:text-brand-700">
                  Host login
                </Link>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-8 border-t border-slate-100 pt-6 text-sm text-slate-400">
          © {new Date().getFullYear()} Spacio.
        </div>
      </div>
    </footer>
  );
}
