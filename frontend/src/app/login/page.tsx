"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { login, seedAdmin } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await login(username, password);
      localStorage.setItem("fte_token", res.access_token);
      router.replace("/dashboard");
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Login failed");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSeed = async () => {
    try {
      const res = await seedAdmin();
      setError("");
      setUsername("admin");
      setPassword("admin123");
      alert(res.message + " — username: admin, password: admin123");
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      }
    }
  };

  return (
    <div className="login-wrapper">
      <div className="login-card glass-card animate-in">
        <h1 className="page-title" style={{ textAlign: "center", fontSize: "1.5rem" }}>
          ⚡ Digital FTE
        </h1>
        <p>Sign in to your AI Employee Dashboard</p>

        {error && <div className="login-error">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="username">Username</label>
            <input
              id="username"
              className="input-field"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="admin"
              autoComplete="username"
              required
            />
          </div>
          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              className="input-field"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              autoComplete="current-password"
              required
            />
          </div>
          <button
            type="submit"
            className="btn-primary"
            style={{ width: "100%", justifyContent: "center", marginTop: 8 }}
            disabled={loading}
          >
            {loading ? "Signing in…" : "Sign In"}
          </button>
        </form>

        <div style={{ textAlign: "center", marginTop: 24 }}>
          <button className="btn-ghost" style={{ fontSize: "0.8rem" }} onClick={handleSeed}>
            First time? Create admin user
          </button>
        </div>
      </div>
    </div>
  );
}
