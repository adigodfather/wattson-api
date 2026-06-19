"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { createClient } from "@/lib/supabase";

const LABEL = { display: "block", fontSize: 12, fontWeight: 600, color: "#8B8FA8", marginBottom: 6, letterSpacing: "0.05em", fontFamily: "'DM Sans', sans-serif" } as const;
const INPUT = {
  width: "100%", padding: "10px 14px", borderRadius: 10, fontSize: 14,
  background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)",
  color: "#E2E4E9", outline: "none", fontFamily: "'DM Sans', sans-serif", boxSizing: "border-box",
} as const;

export default function UpdatePasswordPage() {
  // null = inca verificam sesiunea; true/false = are/nu are sesiune de recovery
  const [hasSession, setHasSession] = useState<boolean | null>(null);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  // La intrarea din link, /auth/callback a facut deja exchangeCodeForSession -> sesiune in cookie.
  // Verificam ca exista un user (sesiune de recovery valida). Daca nu -> link expirat/invalid.
  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data: { user } }) => {
      setHasSession(!!user);
    });
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (password.length < 6) {
      setError("Parola trebuie să aibă minim 6 caractere.");
      return;
    }
    if (password !== confirm) {
      setError("Cele două parole nu coincid.");
      return;
    }

    setLoading(true);
    const supabase = createClient();
    const { error } = await supabase.auth.updateUser({ password });
    if (error) {
      setError(error.message);
      setLoading(false);
      return;
    }
    // parola schimbata -> deconectam sesiunea de recovery, ca userul sa intre curat cu parola noua
    await supabase.auth.signOut();
    setDone(true);
  };

  return (
    <div style={{ minHeight: "100vh", background: "#0A0B0E", display: "flex", alignItems: "center", justifyContent: "center", padding: "24px" }}>
      <style>{`
        .zy-input { transition: border-color 0.15s; }
        .zy-input:focus { border-color: rgba(55,138,221,0.4) !important; outline: none; }
        .zy-input::placeholder { color: #555; }
        .zy-input:-webkit-autofill,
        .zy-input:-webkit-autofill:hover,
        .zy-input:-webkit-autofill:focus {
          -webkit-box-shadow: 0 0 0 100px #0d0f12 inset;
          -webkit-text-fill-color: #E2E4E9;
          caret-color: #E2E4E9;
        }
      `}</style>
      <div style={{ width: "100%", maxWidth: 400 }}>
        <Link href="/" aria-label="Zynapse — pagina principală" style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16, marginBottom: 44, justifyContent: "center", textDecoration: "none", maxWidth: "100%" }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo-icon.png" alt="Zynapse" width={200} height={200} style={{
            objectFit: "contain", maxWidth: "62%", height: "auto",
            filter: "brightness(2.2) drop-shadow(0 0 30px rgba(91,184,245,0.5)) drop-shadow(0 0 56px rgba(55,138,221,0.25))",
          }} />
          <span style={{
            fontSize: "clamp(32px, 11vw, 56px)", fontWeight: 700, letterSpacing: "0.14em", lineHeight: 1, fontFamily: "'DM Sans', sans-serif",
            background: "linear-gradient(120deg, #378ADD 0%, #5BB8F5 35%, #CDEBFF 50%, #5BB8F5 65%, #378ADD 100%)",
            WebkitBackgroundClip: "text", backgroundClip: "text", WebkitTextFillColor: "transparent",
            filter: "drop-shadow(0 0 14px rgba(91,184,245,0.45))",
          }}>ZYNAPSE</span>
        </Link>

        <div style={{
          background: "rgba(255,255,255,0.025)",
          border: "1px solid rgba(255,255,255,0.07)",
          borderRadius: 16,
          padding: "32px 28px",
        }}>
          {done ? (
            // ── SUCCES ──
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: 36, marginBottom: 16 }}>✅</div>
              <h2 style={{ margin: "0 0 10px", fontSize: 20, fontWeight: 700, color: "#E2E4E9", fontFamily: "'DM Sans', sans-serif" }}>
                Parolă schimbată
              </h2>
              <p style={{ margin: "0 0 24px", fontSize: 14, color: "#8B8FA8", lineHeight: 1.6, fontFamily: "'DM Sans', sans-serif" }}>
                Parola a fost actualizată. Te poți autentifica cu noua parolă.
              </p>
              <Link href="/login" style={{
                display: "inline-block", padding: "12px 24px", borderRadius: 12, fontSize: 14, fontWeight: 600,
                background: "linear-gradient(135deg, #378ADD, #1D9E75)", color: "#fff", textDecoration: "none",
                fontFamily: "'DM Sans', sans-serif",
              }}>
                Mergi la login
              </Link>
            </div>
          ) : hasSession === null ? (
            // ── VERIFICARE SESIUNE ──
            <p style={{ textAlign: "center", margin: 0, fontSize: 14, color: "#8B8FA8", fontFamily: "'DM Sans', sans-serif" }}>
              Se verifică link-ul...
            </p>
          ) : !hasSession ? (
            // ── LINK EXPIRAT / INVALID ──
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: 36, marginBottom: 16 }}>⚠️</div>
              <h2 style={{ margin: "0 0 10px", fontSize: 20, fontWeight: 700, color: "#E2E4E9", fontFamily: "'DM Sans', sans-serif" }}>
                Link expirat sau invalid
              </h2>
              <p style={{ margin: "0 0 24px", fontSize: 14, color: "#8B8FA8", lineHeight: 1.6, fontFamily: "'DM Sans', sans-serif" }}>
                Link-ul de resetare a expirat sau a fost deja folosit. Cere unul nou.
              </p>
              <Link href="/reset-password" style={{
                display: "inline-block", padding: "12px 24px", borderRadius: 12, fontSize: 14, fontWeight: 600,
                background: "linear-gradient(135deg, #378ADD, #1D9E75)", color: "#fff", textDecoration: "none",
                fontFamily: "'DM Sans', sans-serif",
              }}>
                Cere link nou
              </Link>
            </div>
          ) : (
            // ── FORMULAR PAROLĂ NOUĂ ──
            <>
              <h1 style={{ margin: "0 0 6px", fontSize: 22, fontWeight: 700, color: "#E2E4E9", fontFamily: "'DM Sans', sans-serif" }}>
                Setează o parolă nouă
              </h1>
              <p style={{ margin: "0 0 28px", fontSize: 13, color: "#545870", fontFamily: "'DM Sans', sans-serif" }}>
                Alege o parolă pe care nu ai mai folosit-o
              </p>

              <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                <div>
                  <label style={LABEL}>PAROLĂ NOUĂ</label>
                  <input
                    className="zy-input"
                    type="password" value={password} onChange={e => setPassword(e.target.value)}
                    placeholder="••••••••" required autoComplete="new-password" minLength={6}
                    style={INPUT} />
                </div>

                <div>
                  <label style={LABEL}>CONFIRMĂ PAROLA</label>
                  <input
                    className="zy-input"
                    type="password" value={confirm} onChange={e => setConfirm(e.target.value)}
                    placeholder="••••••••" required autoComplete="new-password" minLength={6}
                    style={INPUT} />
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
                  {loading ? "Se salvează..." : "Schimbă parola"}
                </button>
              </form>

              <div style={{ marginTop: 20, textAlign: "center" }}>
                <Link href="/login" style={{ fontSize: 13, color: "#545870", textDecoration: "none", fontFamily: "'DM Sans', sans-serif" }}
                  onMouseOver={(e) => (e.currentTarget.style.color = "#8B8FA8")}
                  onMouseOut={(e) => (e.currentTarget.style.color = "#545870")}>
                  ← Înapoi la login
                </Link>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
