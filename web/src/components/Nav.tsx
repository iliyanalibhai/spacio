import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

export function Nav() {
  const { user, logout } = useAuth();
  const [showUserMenu, setShowUserMenu] = useState(false);

  return (
    <header className="border-b bg-white sticky top-0 z-50">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <Link to="/" className="text-xl font-bold text-brand-600">
          Spacio
        </Link>
        <nav className="flex items-center gap-3 text-sm font-medium text-slate-600">
          {!user && (
            <>
              <Link to="/login" className="hover:text-slate-900 transition-colors">
                Login
              </Link>
              <Link
                to="/register"
                className="bg-brand-600 text-white px-4 py-2 rounded-full hover:bg-brand-500 transition-colors"
              >
                Sign up
              </Link>
            </>
          )}
          {user && (
            <div className="relative">
              <button
                onClick={() => setShowUserMenu(!showUserMenu)}
                className="flex items-center gap-2 rounded-full border border-slate-200 p-1 pl-3 hover:shadow-md transition-shadow"
              >
                <svg className="h-4 w-4 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
                <div className="h-8 w-8 rounded-full bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center text-white font-semibold text-sm">
                  {user.name.charAt(0).toUpperCase()}
                </div>
              </button>

              {showUserMenu && (
                <>
                  <div className="fixed inset-0" onClick={() => setShowUserMenu(false)} />
                  <div className="absolute right-0 mt-2 w-64 rounded-xl bg-white shadow-xl border border-slate-200 py-2 z-50">
                    <div className="px-4 py-3 border-b border-slate-100">
                      <p className="font-semibold text-slate-900">{user.name}</p>
                      <p className="text-sm text-slate-500">{user.email}</p>
                    </div>

                    <Link
                      to="/profile"
                      className="flex items-center gap-3 px-4 py-3 hover:bg-slate-50 transition-colors"
                      onClick={() => setShowUserMenu(false)}
                    >
                      <span className="text-slate-700">My Profile</span>
                    </Link>

                    <Link
                      to="/profile?tab=reservations"
                      className="flex items-center gap-3 px-4 py-3 hover:bg-slate-50 transition-colors"
                      onClick={() => setShowUserMenu(false)}
                    >
                      <span className="text-slate-700">My Reservations</span>
                    </Link>

                    {user.isHost && user.verificationStatus === "verified" && (
                      <Link
                        to="/host"
                        className="flex items-center gap-3 px-4 py-3 hover:bg-slate-50 transition-colors"
                        onClick={() => setShowUserMenu(false)}
                      >
                        <span className="text-slate-700">Host Dashboard</span>
                      </Link>
                    )}

                    <div className="border-t border-slate-100 mt-2 pt-2">
                      <button
                        onClick={() => {
                          logout();
                          setShowUserMenu(false);
                        }}
                        className="flex items-center gap-3 px-4 py-3 hover:bg-slate-50 transition-colors w-full text-left"
                      >
                        <span className="text-slate-700">Log out</span>
                      </button>
                    </div>
                  </div>
                </>
              )}
            </div>
          )}
        </nav>
      </div>
    </header>
  );
}
