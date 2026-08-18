/**
 * LoginPage — Supabase email/password sign-in screen.
 *
 * Called from App.jsx when there is no active session.
 * On success: saves the JWT to localStorage + calls setAuthToken()
 * so api.js attaches it to every subsequent API request.
 *
 * Supports two modes (toggled by the user):
 *   • Sign In   — supabase.auth.signInWithPassword
 *   • Sign Up   — supabase.auth.signUp (creates a new Supabase user)
 *
 * After sign-up, Supabase sends a confirmation email by default.
 * For hackathon demos, disable email confirmation in:
 *   Supabase Dashboard → Authentication → Settings → "Confirm email" OFF
 */
import { useState } from "react";
import { ShieldCheck, Mail, Lock, Eye, EyeOff, Loader2, AlertCircle } from "lucide-react";
import { supabase } from "../supabaseClient";
import { setAuthToken } from "../api";

export default function LoginPage({ onLogin }) {
  const [mode, setMode] = useState("signin"); // "signin" | "signup"
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setInfo("");
    setLoading(true);

    try {
      let result;
      if (mode === "signin") {
        result = await supabase.auth.signInWithPassword({ email, password });
      } else {
        result = await supabase.auth.signUp({ email, password });
      }

      const { data, error: authErr } = result;

      if (authErr) {
        setError(authErr.message);
        return;
      }

      // Sign-up with email confirmation pending
      if (mode === "signup" && !data.session) {
        setInfo("Account created! Check your email to confirm, then sign in.");
        setMode("signin");
        return;
      }

      if (data.session) {
        const token = data.session.access_token;
        localStorage.setItem("sb_access_token", token);
        setAuthToken(token);
        onLogin(data.session);
      }
    } catch (err) {
      setError(err.message || "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{ background: "#07111f", minHeight: "100vh" }}
      className="flex items-center justify-center p-4"
    >
      <div style={{ width: "100%", maxWidth: 420 }}>
        {/* Logo / header */}
        <div className="text-center mb-8">
          <div
            className="inline-flex items-center justify-center w-14 h-14 rounded-2xl mb-4"
            style={{ background: "linear-gradient(135deg, #00b4d8 0%, #0077b6 100%)" }}
          >
            <ShieldCheck className="w-7 h-7 text-white" />
          </div>
          <h1 className="text-2xl font-extrabold tracking-tight text-white">
            Supply Chain Control Tower
          </h1>
          <p className="text-sm mt-1" style={{ color: "#64748b" }}>
            SIH PSS04 · Secure Sign-In
          </p>
        </div>

        {/* Card */}
        <div
          className="rounded-2xl p-6"
          style={{
            background: "rgba(255,255,255,0.04)",
            border: "1px solid rgba(255,255,255,0.08)",
            backdropFilter: "blur(12px)",
          }}
        >
          {/* Mode toggle */}
          <div
            className="flex rounded-xl p-1 mb-6"
            style={{ background: "rgba(255,255,255,0.05)" }}
          >
            {["signin", "signup"].map((m) => (
              <button
                key={m}
                onClick={() => { setMode(m); setError(""); setInfo(""); }}
                className="flex-1 py-1.5 rounded-lg text-sm font-medium transition-all duration-200"
                style={{
                  background: mode === m ? "rgba(0,180,216,0.2)" : "transparent",
                  color: mode === m ? "#00b4d8" : "#64748b",
                  border: mode === m ? "1px solid rgba(0,180,216,0.3)" : "1px solid transparent",
                }}
              >
                {m === "signin" ? "Sign In" : "Sign Up"}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            {/* Email */}
            <div>
              <label className="text-xs font-medium mb-1.5 block" style={{ color: "#94a3b8" }}>
                Email
              </label>
              <div className="relative">
                <Mail
                  className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4"
                  style={{ color: "#64748b" }}
                />
                <input
                  id="login-email"
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="officer@health.gov.in"
                  className="w-full pl-10 pr-4 py-2.5 rounded-xl text-sm text-white outline-none transition-all"
                  style={{
                    background: "rgba(255,255,255,0.06)",
                    border: "1px solid rgba(255,255,255,0.1)",
                  }}
                  onFocus={(e) => (e.target.style.borderColor = "rgba(0,180,216,0.5)")}
                  onBlur={(e) => (e.target.style.borderColor = "rgba(255,255,255,0.1)")}
                />
              </div>
            </div>

            {/* Password */}
            <div>
              <label className="text-xs font-medium mb-1.5 block" style={{ color: "#94a3b8" }}>
                Password
              </label>
              <div className="relative">
                <Lock
                  className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4"
                  style={{ color: "#64748b" }}
                />
                <input
                  id="login-password"
                  type={showPw ? "text" : "password"}
                  required
                  autoComplete={mode === "signin" ? "current-password" : "new-password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full pl-10 pr-10 py-2.5 rounded-xl text-sm text-white outline-none transition-all"
                  style={{
                    background: "rgba(255,255,255,0.06)",
                    border: "1px solid rgba(255,255,255,0.1)",
                  }}
                  onFocus={(e) => (e.target.style.borderColor = "rgba(0,180,216,0.5)")}
                  onBlur={(e) => (e.target.style.borderColor = "rgba(255,255,255,0.1)")}
                />
                <button
                  type="button"
                  tabIndex={-1}
                  onClick={() => setShowPw((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2"
                  style={{ color: "#64748b" }}
                >
                  {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Error / Info */}
            {error && (
              <div
                className="flex items-center gap-2 rounded-xl p-3 text-sm"
                style={{ background: "rgba(239,68,68,0.12)", color: "#f87171", border: "1px solid rgba(239,68,68,0.2)" }}
              >
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}
            {info && (
              <div
                className="flex items-center gap-2 rounded-xl p-3 text-sm"
                style={{ background: "rgba(34,197,94,0.12)", color: "#4ade80", border: "1px solid rgba(34,197,94,0.2)" }}
              >
                <span>{info}</span>
              </div>
            )}

            {/* Submit */}
            <button
              id="login-submit"
              type="submit"
              disabled={loading}
              className="w-full py-2.5 rounded-xl font-semibold text-sm flex items-center justify-center gap-2 transition-all duration-200"
              style={{
                background: loading
                  ? "rgba(0,180,216,0.4)"
                  : "linear-gradient(135deg, #00b4d8 0%, #0077b6 100%)",
                color: "white",
                opacity: loading ? 0.7 : 1,
              }}
            >
              {loading && <Loader2 className="w-4 h-4 animate-spin" />}
              {loading ? "Please wait…" : mode === "signin" ? "Sign In" : "Create Account"}
            </button>
          </form>
        </div>

        <p className="text-center text-xs mt-4" style={{ color: "#334155" }}>
          Secured by Supabase Auth · JWT-gated API · RLS enforced
        </p>
      </div>
    </div>
  );
}
