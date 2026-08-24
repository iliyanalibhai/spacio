import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000",
  // Send the httpOnly session cookie (set by POST /auth/login) on every
  // request, and let the browser store cookies set for us in responses.
  // Without this, the cookie exists but the browser won't attach it to
  // cross-origin requests (the web dev server on :5173 calling the API on
  // :8000 counts as cross-origin even though both are "localhost").
  withCredentials: true,
});

// If a request ever comes back 401, the session cookie is missing, invalid,
// or expired — send the user to /login instead of leaving the UI stuck in a
// half-authenticated state. Skip this for /auth/me: useAuth's initial
// session check calls it expecting a 401 whenever nobody is logged in yet,
// which is normal and handled there, not an error worth a hard redirect.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const isSessionCheck = error.config?.url === "/auth/me";
    const alreadyOnLogin = window.location.pathname === "/login";
    if (error.response?.status === 401 && !isSessionCheck && !alreadyOnLogin) {
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

export default api;
