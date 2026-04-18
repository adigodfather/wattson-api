"use client";

import { useState } from "react";
import WattsonForm from "@/components/WattsonForm";
import WattsonResults from "@/components/WattsonResults";
import type { CalcResponse } from "@/types/wattson";

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
    <main className="min-h-screen px-4 py-10" style={{ background: "var(--background)" }}>
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="text-center mb-10">
          <div className="text-xs tracking-[4px] uppercase mb-2" style={{ color: "var(--muted)" }}>
            Automatizare Proiectare Electrică
          </div>
          <h1 className="text-3xl font-bold tracking-tight mb-1" style={{
            background: "linear-gradient(90deg, #00C896, #6366F1)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
          }}>
            ⚡ WATTSON
          </h1>
          <p style={{ color: "var(--muted)", fontSize: 14 }}>
            Completează formularul — obții instant circuitele, siguranțele și memoriul tehnic.
          </p>
        </div>

        {!result ? (
          <WattsonForm onSubmit={handleSubmit} loading={loading} error={error} />
        ) : (
          <WattsonResults result={result} onReset={() => setResult(null)} />
        )}
      </div>
    </main>
  );
}
