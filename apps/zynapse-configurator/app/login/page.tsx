"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase";

function ZLogo() {
  return (
    <svg width="36" height="36" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="zgl" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#378ADD" />
          <stop offset="100%" stopColor="#1D9E75" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="8" fill="url(#zgl)" />
      <text x="16" y="23" textAnchor="middle" fontFamily="'DM Sans', system-ui, sans-serif"
        fontSize="20" fontWeight="700" fill="white" letterSpacing="-1">Z</text>
    </svg>
  );
}

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const supabase = createClient();
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) {
      setError(error.message === "Invalid login credentials"
        ? "Email sau parolă incorectă"
        : error.message);
      setLoading(false);
    } else {
      router.push("/");
      router.refresh();
    }
  };

  return (
    <div style={{ minHeight: "100vh", background: "#0A0B0E", display: "flex", alignItems: "center", justifyContent: "center", padding: "24px" }}>
      <div style={{ width: "100%", maxWidth: 400 }}>
        {/* Logo */}
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 40, justifyContent: "center" }}>
          <ZLogo />
          <span style={{ fontSize: 20, fontWeight: 700, color: "#E2E4E9", letterSpacing: "-0.5px", fontFamily: "'DM Sans', sans-serif" }}>Zynapse</span>
        </div>

        <div style={{
          background: "rgba(255,255,255,0.025)",
          border: "1px solid rgba(255,255,255,0.07)",
          borderRadius: 16,
          padding: "32px 28px",
        }}>
          <h1 style={{ margin: "0 0 6px", fontSize: 22, fontWeight: 700, color: "#E2E4E9", fontFamily: "'DM Sans', sans-serif" }}>
            Bine ai revenit
          </h1>
          <p style={{ margin: "0 0 28px", fontSize: 13, color: "#545870", fontFamily: "'DM Sans', sans-serif" }}>
            Loghează-te în contul tău Zynapse
          </p>

          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div>
              <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#8B8FA8", marginBottom: 6, letterSpacing: "0.05em", fontFamily: "'DM Sans', sans-serif" }}>
                EMAIL
              </label>
              <input
                type="email" value={email} onChange={e => setEmail(e.target.value)}
                placeholder="adresa@email.com" required autoComplete="email"
                style={{
                  width: "100%", padding: "10px 14px", borderRadius: 10, fontSize: 14,
                  background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)",
                  color: "#E2E4E9", outline: "none", fontFamily: "'DM Sans', sans-serif", boxSizing: "border-box",
                }} />
            </div>

            <div>
              <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#8B8FA8", marginBottom: 6, letterSpacing: "0.05em", fontFamily: "'DM Sans', sans-serif" }}>
                PAROLĂ
              </label>
              <input
                type="password" value={password} onChange={e => setPassword(e.target.value)}
                placeholder="••••••••" required autoComplete="current-password"
                style={{
                  width: "100%", padding: "10px 14px", borderRadius: 10, fontSize: 14,
                  background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)",
                  color: "#E2E4E9", outline: "none", fontFamily: "'DM Sans', sans-serif", boxSizing: "border-box",
                }} />
            </div>

            {error && (
              <div style={{
                padding: "10px 14px", borderRadius: 10, fontSize: 13,
                background: "rgba(226,75,74,0.1)", border: "1px solid rgba(226,75,74,0.2)", color: "#F09595",
                fontFamily: "'DM Sans', sans-serif",
              }}>
                {error}
              </div>
            )}

            <button type="submit" disabled={loading} style={{
              marginTop: 6, padding: "12px 20px", borderRadius: 12, fontSize: 14,
              fontWeight: 600, border: "none", cursor: loading ? "not-allowed" : "pointer",
              background: loading ? "rgba(255,255,255,0.06)" : "linear-gradient(135deg, #378ADD, #1D9E75)",
              color: loading ? "#545870" : "#fff",
              fontFamily: "'DM Sans', sans-serif",
              transition: "opacity 0.15s",
              opacity: loading ? 0.7 : 1,
            }}>
              {loading ? "Se autentifică..." : "Intră în cont"}
            </button>
          </form>

          <div style={{ marginTop: 20, display: "flex", flexDirection: "column", gap: 10, alignItems: "center" }}>
            <Link href="/reset-password" style={{ fontSize: 13, color: "#545870", textDecoration: "none", fontFamily: "'DM Sans', sans-serif" }}
              onMouseOver={(e) => (e.currentTarget.style.color = "#8B8FA8")}
              onMouseOut={(e) => (e.currentTarget.style.color = "#545870")}>
              Am uitat parola
            </Link>
            <span style={{ fontSize: 13, color: "#545870", fontFamily: "'DM Sans', sans-serif" }}>
              Nu ai cont?{" "}
              <Link href="/register" style={{ color: "#5BB8F5", textDecoration: "none", fontWeight: 500 }}
                onMouseOver={(e) => (e.currentTarget.style.color = "#378ADD")}
                onMouseOut={(e) => (e.currentTarget.style.color = "#5BB8F5")}>
                Creează cont
              </Link>
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
