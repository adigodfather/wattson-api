"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase";

type PayState = "loading" | "pending" | "paid" | "failed" | "canceled" | "noorder" | "notfound";

function ReturnInner() {
  const sp = useSearchParams();
  const order = sp.get("order");
  const [state, setState] = useState<PayState>("loading");
  const [credits, setCredits] = useState<number | null>(null);

  useEffect(() => {
    if (!order) { setState("noorder"); return; }
    const supabase = createClient();
    let tries = 0;
    let stop = false;
    // Creditarea reală se face pe IPN (server). Aici doar așteptăm să se reflecte statusul.
    const poll = async () => {
      if (stop) return;
      const { data } = await supabase
        .from("payments")
        .select("status, credits, credited")
        .eq("order_id", order)
        .single();
      if (data) {
        setCredits(data.credits ?? null);
        if (data.status === "paid" || data.status === "failed" || data.status === "canceled") {
          setState(data.status as PayState);
          return;
        }
        setState("pending");
      } else if (tries === 0) {
        setState("notfound");
      }
      tries++;
      if (tries <= 10 && !stop) setTimeout(poll, 2500);
    };
    poll();
    return () => { stop = true; };
  }, [order]);

  const box: React.CSSProperties = {
    maxWidth: 480, margin: "80px auto", padding: "40px 32px", textAlign: "center",
    background: "rgba(255,255,255,0.025)", border: "1px solid rgba(255,255,255,0.08)",
    borderRadius: 18, color: "#C8CAD6", fontFamily: "'DM Sans', system-ui, sans-serif",
  };

  let title = "Verificăm plata ta…";
  let msg = "Te rugăm așteaptă câteva secunde, confirmăm tranzacția.";
  let color = "#5BB8F5";
  if (state === "paid") { title = "Plată confirmată ✓"; msg = `Creditele${credits ? ` (${credits.toLocaleString("ro-RO")})` : ""} au fost adăugate în contul tău.`; color = "#3ECFA0"; }
  else if (state === "failed") { title = "Plata a eșuat"; msg = "Tranzacția nu a fost finalizată. Nu ai fost taxat. Poți reîncerca."; color = "#F09595"; }
  else if (state === "canceled") { title = "Plată anulată"; msg = "Ai anulat tranzacția. Nu ai fost taxat."; color = "#C9A227"; }
  else if (state === "noorder" || state === "notfound") { title = "Comandă negăsită"; msg = "Nu am găsit această comandă. Dacă ai fost taxat, contactează-ne."; color = "#F09595"; }

  return (
    <div style={{ minHeight: "100vh", background: "#0A0B0E" }}>
      <div style={box}>
        <h1 style={{ fontSize: 22, fontWeight: 700, color, margin: "0 0 10px" }}>{title}</h1>
        <p style={{ fontSize: 14, color: "#8B8FA8", lineHeight: 1.6, margin: "0 0 24px" }}>{msg}</p>
        {(state === "loading" || state === "pending") && (
          <span className="inline-block w-6 h-6 border-2 rounded-full" style={{
            display: "inline-block", width: 24, height: 24, borderRadius: "50%",
            border: "2px solid #378ADD", borderTopColor: "transparent",
            animation: "zy-spin 0.7s linear infinite",
          }} />
        )}
        <div style={{ marginTop: 24 }}>
          <Link href="/home" style={{ fontSize: 13, color: "#5BB8F5", textDecoration: "none" }}>
            ← Înapoi la cont
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function PaymentReturnPage() {
  return (
    <Suspense fallback={<div style={{ minHeight: "100vh", background: "#0A0B0E" }} />}>
      <ReturnInner />
    </Suspense>
  );
}
