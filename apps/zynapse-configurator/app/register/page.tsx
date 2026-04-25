"use client";

import { useState } from "react";
import Link from "next/link";
import { createClient } from "@/lib/supabase";

function ZLogo() {
  return (
    <svg width="36" height="36" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="zgr" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#378ADD" />
          <stop offset="100%" stopColor="#1D9E75" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="8" fill="url(#zgr)" />
      <text x="16" y="23" textAnchor="middle" fontFamily="'DM Sans', system-ui, sans-serif"
        fontSize="20" fontWeight="700" fill="white" letterSpacing="-1">Z</text>
    </svg>
  );
}

const inputStyle: React.CSSProperties = {
  width: "100%", padding: "10px 14px", borderRadius: 10, fontSize: 14,
  background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)",
  color: "#E2E4E9", outline: "none", fontFamily: "'DM Sans', sans-serif", boxSizing: "border-box",
};

const labelStyle: React.CSSProperties = {
  display: "block", fontSize: 12, fontWeight: 600, color: "#8B8FA8",
  marginBottom: 6, letterSpacing: "0.05em", fontFamily: "'DM Sans', sans-serif",
};

export default function RegisterPage() {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [loading, setLoading] = useState(false);

  const validate = () => {
    if (!fullName.trim()) return "Introdu numele complet";
    if (password.length < 8) return "Parola trebuie să aibă minim 8 caractere";
    if (password !== confirm) return "Parolele nu coincid";
    return null;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const validationError = validate();
    if (validationError) { setError(validationError); return; }
    setError(null);
    setLoading(true);

    const supabase = createClient();
    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: { full_name: fullName.trim() },
        emailRedirectTo: "https://www.zynapse.org/auth/callback",
      },
    });

    if (error) {
      setError(error.message);
      setLoading(false);
    } else {
      setDone(true);
    }
  };

  if (done) {
    return (
      <div style={{ minHeight: "100vh", background: "#0A0B0E", display: "flex", alignItems: "center", justifyContent: "center", padding: "24px" }}>
        <div style={{ width: "100%", maxWidth: 400, textAlign: "center" }}>
          <div style={{ fontSize: 40, marginBottom: 20 }}>✉️</div>
          <h2 style={{ margin: "0 0 10px", fontSize: 20, fontWeight: 700, color: "#E2E4E9", fontFamily: "'DM Sans', sans-serif" }}>
            Verifică-ți email-ul
          </h2>
          <p style={{ margin: "0 0 24px", fontSize: 14, color: "#8B8FA8", lineHeight: 1.6, fontFamily: "'DM Sans', sans-serif" }}>
            Am trimis un link de confirmare la <strong style={{ color: "#E2E4E9" }}>{email}</strong>.
            Accesează linkul pentru a-ți activa contul.
          </p>
          <Link href="/login" style={{ fontSize: 13, color: "#5BB8F5", textDecoration: "none", fontFamily: "'DM Sans', sans-serif" }}>
            ← Înapoi la login
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100vh", background: "#0A0B0E", display: "flex", alignItems: "center", justifyContent: "center", padding: "24px" }}>
      <div style={{ width: "100%", maxWidth: 400 }}>
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
            Creează cont
          </h1>
          <p style={{ margin: "0 0 28px", fontSize: 13, color: "#545870", fontFamily: "'DM Sans', sans-serif" }}>
            Acces la proiectare electrică automată
          </p>

          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div>
              <label style={labelStyle}>NUME COMPLET</label>
              <input type="text" value={fullName} onChange={e => setFullName(e.target.value)}
                placeholder="Ion Popescu" required autoComplete="name" style={inputStyle} />
            </div>

            <div>
              <label style={labelStyle}>EMAIL</label>
              <input type="email" value={email} onChange={e => setEmail(e.target.value)}
                placeholder="adresa@email.com" required autoComplete="email" style={inputStyle} />
            </div>

            <div>
              <label style={labelStyle}>PAROLĂ</label>
              <input type="password" value={password} onChange={e => setPassword(e.target.value)}
                placeholder="Minim 8 caractere" required autoComplete="new-password" style={inputStyle} />
            </div>

            <div>
              <label style={labelStyle}>CONFIRMĂ PAROLA</label>
              <input type="password" value={confirm} onChange={e => setConfirm(e.target.value)}
                placeholder="Repetă parola" required autoComplete="new-password" style={inputStyle} />
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
              opacity: loading ? 0.7 : 1,
            }}>
              {loading ? "Se creează contul..." : "Creează cont"}
            </button>
          </form>

          <div style={{ marginTop: 20, textAlign: "center" }}>
            <span style={{ fontSize: 13, color: "#545870", fontFamily: "'DM Sans', sans-serif" }}>
              Ai deja cont?{" "}
              <Link href="/login" style={{ color: "#5BB8F5", textDecoration: "none", fontWeight: 500 }}>
                Loghează-te
              </Link>
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
