import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./hooks/useAuth";
import { Nav } from "./components/Nav";
import { Landing } from "./pages/Landing";
import { Login } from "./pages/Login";
import { Register } from "./pages/Register";
import { Profile } from "./pages/Profile";
import { HostDashboard } from "./pages/HostDashboard";
import { RenterDashboard } from "./pages/RenterDashboard";
import { SmartMatch } from "./pages/SmartMatch";

function RequireAuth({ children, hostOnly = false }: { children: JSX.Element; hostOnly?: boolean }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (hostOnly && !user.isHost) return <Navigate to="/" replace />;
  return children;
}

export default function App() {
  return (
    <div className="min-h-screen bg-slate-50">
      <Nav />
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
  );
}
