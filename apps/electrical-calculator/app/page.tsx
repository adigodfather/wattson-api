"use client";

import { useState } from "react";
import WattsonForm from "@/components/WattsonForm";
import WattsonResults from "@/components/WattsonResults";
import type { CalcResponse } from "@/types/wattson";

const S = {
  page: { minHeight: "100vh", background: "#080C14", color: "#E2E8F0", fontFamily: "'Inter', 'Segoe UI', Arial, sans-serif" } as React.CSSProperties,
  header: { borderBottom: "1px solid #1E293B", padding: "16px 24px", display: "flex", alignItems: "center", justifyContent: "space-between" } as React.CSSProperties,
  logo: { display: "flex", alignItems: "center", gap: 8, fontWeight: 800, fontSize: 15, color: "#E2E8F0", textDecoration: "none" } as React.CSSProperties,
  badge: { fontSize: 10, padding: "3px 10px", borderRadius: 20, border: "1px solid #00C89633", background: "#00C89611", color: "#00C896", fontFamily: "monospace", letterSpacing: 1 } as React.CSSProperties,
  main: { maxWidth: 820, margin: "0 auto", padding: "40px 20px 80px" } as React.CSSProperties,
  heroTitle: { fontSize: 32, fontWeight: 800, background: "linear-gradient(90deg,#00C896,#6366F1)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", letterSpacing: -0.5 } as React.CSSProperties,
  heroSub: { fontSize: 14, color: "#475569", marginTop: 6 } as React.CSSProperties,
};

export default function Home() {
  const [result, setResult] = useState<CalcResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (payload: unknown) => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch(process.env.NEXT_PUBLIC_N8N_WEBHOOK_URL!, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok || data.status === "error") {
        setError(data.error ?? "Eroare necunoscută");
      } else {
        setResult(data);
      }
    } catch {
      setError("Nu s-a putut conecta la server. Încearcă din nou.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={S.page}>
      <header style={S.header}>
        <a href="https://zynapse.ro" style={S.logo}>
          <span style={{ color: "#00C896" }}>⚡</span> WATTSON
        </a>
        <span style={S.badge}>by ZYNAPSE</span>
      </header>

      <main style={S.main}>
        {!result ? (
          <>
            <div style={{ textAlign: "center", marginBottom: 40 }}>
              <p style={{ fontSize: 11, letterSpacing: 4, color: "#334155", textTransform: "uppercase", marginBottom: 8 }}>
                Automatizare Proiectare Electrică
              </p>
              <h1 style={S.heroTitle}>⚡ Generator Proiect Electric</h1>
              <p style={S.heroSub}>
                Completează formularul — obții instant circuitele, siguranțele și memoriul tehnic.
              </p>
            </div>
            <WattsonForm onSubmit={handleSubmit} loading={loading} error={error} />
          </>
        ) : (
          <WattsonResults result={result} onReset={() => setResult(null)} />
        )}
      </main>
    </div>
  );
}
