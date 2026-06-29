"use client";
import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { access_token } = await api.login(username, password);
      localStorage.setItem("pead_token", access_token);
      router.push("/dashboard");
    } catch {
      setError("Invalid credentials.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{
      minHeight: "100vh",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      background: "var(--color-bg-base)",
    }}>
      <div style={{
        width: 360,
        background: "var(--color-bg-panel)",
        border: "1px solid var(--color-border)",
        borderRadius: 8,
        padding: "32px 28px",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 28 }}>
          <div style={{
            width: 8, height: 8, borderRadius: "50%",
            background: "var(--color-positive)",
          }} />
          <span style={{
            fontSize: 13,
            fontWeight: 600,
            letterSpacing: "0.1em",
            textTransform: "uppercase",
            color: "var(--color-text-primary)",
          }}>PEAD System</span>
        </div>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div>
            <label style={{ fontSize: 11, color: "var(--color-text-muted)", letterSpacing: "0.06em", textTransform: "uppercase" }}>
              Username
            </label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              required
              autoFocus
              style={{
                display: "block",
                width: "100%",
                marginTop: 4,
                padding: "8px 10px",
                background: "var(--color-bg-base)",
                border: "1px solid var(--color-border-strong)",
                borderRadius: 4,
                color: "var(--color-text-primary)",
                fontSize: 13,
                fontFamily: "var(--font-family-mono)",
                outline: "none",
              }}
            />
          </div>
          <div>
            <label style={{ fontSize: 11, color: "var(--color-text-muted)", letterSpacing: "0.06em", textTransform: "uppercase" }}>
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              style={{
                display: "block",
                width: "100%",
                marginTop: 4,
                padding: "8px 10px",
                background: "var(--color-bg-base)",
                border: "1px solid var(--color-border-strong)",
                borderRadius: 4,
                color: "var(--color-text-primary)",
                fontSize: 13,
                fontFamily: "var(--font-family-mono)",
                outline: "none",
              }}
            />
          </div>

          {error && (
            <p style={{ fontSize: 12, color: "var(--color-negative)", margin: 0 }}>{error}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              marginTop: 8,
              padding: "9px",
              background: "var(--color-accent)",
              border: "none",
              borderRadius: 4,
              color: "#fff",
              fontSize: 13,
              fontWeight: 500,
              cursor: loading ? "not-allowed" : "pointer",
              opacity: loading ? 0.7 : 1,
              letterSpacing: "0.04em",
            }}
          >
            {loading ? "Authenticating..." : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}
