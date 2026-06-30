"use client";

import { useState } from "react";
import Link from "next/link";
import { createClient } from "@/lib/supabase";

export default function ResetPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    const supabase = createClient();
    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: "https://www.zynapse.org/auth/callback?next=/update-password",
    });

    if (error) {
      setError(error.message);
      setLoading(false);
    } else {
      setDone(true);
    }
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
          <img src="/bgbgbun.png" alt="Zynapse" width={169} height={92} style={{
            objectFit: "contain", height: "clamp(74px, 16vw, 92px)", width: "auto", maxWidth: "80%",
            filter: "drop-shadow(0 0 30px rgba(91,184,245,0.5)) drop-shadow(0 0 56px rgba(55,138,221,0.25))",
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
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: 36, marginBottom: 16 }}>📨</div>
              <h2 style={{ margin: "0 0 10px", fontSize: 20, fontWeight: 700, color: "#E2E4E9", fontFamily: "'DM Sans', sans-serif" }}>
                Link trimis
              </h2>
              <p style={{ margin: "0 0 24px", fontSize: 14, color: "#8B8FA8", lineHeight: 1.6, fontFamily: "'DM Sans', sans-serif" }}>
                Link-ul de resetare a fost trimis la <strong style={{ color: "#E2E4E9" }}>{email}</strong>.
              </p>
              <Link href="/login" style={{ fontSize: 13, color: "#5BB8F5", textDecoration: "none", fontFamily: "'DM Sans', sans-serif" }}>
                ← Înapoi la login
              </Link>
            </div>
          ) : (
            <>
              <h1 style={{ margin: "0 0 6px", fontSize: 22, fontWeight: 700, color: "#E2E4E9", fontFamily: "'DM Sans', sans-serif" }}>
                Resetează parola
              </h1>
              <p style={{ margin: "0 0 28px", fontSize: 13, color: "#545870", fontFamily: "'DM Sans', sans-serif" }}>
                Trimitem un link de resetare pe email-ul tău
              </p>

              <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                <div>
                  <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#8B8FA8", marginBottom: 6, letterSpacing: "0.05em", fontFamily: "'DM Sans', sans-serif" }}>
                    EMAIL
                  </label>
                  <input
                    className="zy-input"
                    type="email" value={email} onChange={e => setEmail(e.target.value)}
                    placeholder="adresa@email.com" required autoComplete="email"
                    style={{
                      width: "100%", padding: "10px 14px", borderRadius: 10, fontSize: 14,
                      background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)",
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
                  {loading ? "Se trimite..." : "Trimite link de resetare"}
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
