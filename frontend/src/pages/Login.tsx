import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { login } from "../services/api";

export default function Login() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("rm_ahmad");
  const [password, setPassword] = useState("warba2025");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await login(username, password);
      localStorage.setItem("token", res.access_token);
      localStorage.setItem("role", res.role);
      localStorage.setItem("user_id", res.user_id);
      navigate("/dashboard");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-frost-navy px-4 py-12">
      <div className="w-full max-w-md">
        <div className="card p-9">
          <div className="mb-8 text-center">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-frost-navy shadow-panel">
              <span className="font-display text-2xl font-bold text-gold">M</span>
            </div>
            <h1 className="font-display text-3xl font-bold text-frost-navy">MemoForge</h1>
            <p className="mt-1.5 text-sm text-frost-slate">
              Warba Bank — Client Documentation Generator
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label htmlFor="username" className="field-label">Username</label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="field"
                autoComplete="username"
                required
              />
            </div>
            <div>
              <label htmlFor="password" className="field-label">Password</label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="field"
                autoComplete="current-password"
                required
              />
            </div>

            {error && (
              <div
                role="alert"
                className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
              >
                {error}
              </div>
            )}

            <button type="submit" disabled={loading} className="btn-navy w-full !py-3">
              {loading ? "Signing in…" : "Sign In"}
            </button>
          </form>

          <p className="mt-7 border-t border-frost-mist pt-5 text-center text-xs leading-relaxed text-frost-steel">
            100% Shariah-Compliant · CBK/IFRS 9 Compliant · SOC 2 Ready
          </p>
        </div>

        <p className="mt-6 text-center text-sm text-frost-light/80">
          New to MemoForge?{" "}
          <Link
            to="/landing"
            className="font-semibold text-gold underline decoration-gold/40 underline-offset-4 transition hover:text-gold-soft"
          >
            Explore the product
          </Link>
        </p>
      </div>
    </div>
  );
}
