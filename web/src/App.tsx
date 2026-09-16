import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./hooks/useAuth";
import { Nav } from "./components/Nav";
import { Footer } from "./components/Footer";
import { Landing } from "./pages/Landing";
import { Login } from "./pages/Login";
import { Register } from "./pages/Register";
import { Profile } from "./pages/Profile";
import { HostDashboard } from "./pages/HostDashboard";
import { RenterDashboard } from "./pages/RenterDashboard";
import { SmartMatch } from "./pages/SmartMatch";

function RequireAuth({ children, hostOnly = false }: { children: JSX.Element; hostOnly?: boolean }) {
  const { user, initializing } = useAuth();
  // Wait for the initial /auth/me check to resolve before deciding to
  // redirect — otherwise a hard refresh or deep link to a protected route
  // always bounces to /login first, even with a valid token in storage,
  // since `user` starts null until that async check completes.
  if (initializing) return null;
  if (!user) return <Navigate to="/login" replace />;
  if (hostOnly && !user.isHost) return <Navigate to="/" replace />;
  return children;
}

export default function App() {
  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      <Nav />
      <div className="flex-1">
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route
            path="/profile"
            element={
              <RequireAuth>
                <Profile />
              </RequireAuth>
            }
          />
          <Route
            path="/host"
            element={
              <RequireAuth hostOnly>
                <HostDashboard />
              </RequireAuth>
            }
          />
          <Route
            path="/renter"
            element={
              <RequireAuth>
                <RenterDashboard />
              </RequireAuth>
            }
          />
          <Route
            path="/match"
            element={
              <RequireAuth>
                <SmartMatch />
              </RequireAuth>
            }
          />
        </Routes>
      </div>
      <Footer />
    </div>
  );
}
