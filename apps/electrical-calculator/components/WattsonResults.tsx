"use client";

import type { CalcResponse, Circuit } from "@/types/wattson";

interface Props {
  result: CalcResponse;
  onReset: () => void;
}

function CircuitRow({ c }: { c: Circuit }) {
  return (
    <div className="flex items-start justify-between py-2 text-sm border-b last:border-0"
      style={{ borderColor: "var(--border)" }}>
      <div>
        <span className="font-mono text-xs px-1.5 py-0.5 rounded mr-2"
          style={{ background: "#1E3A5F", color: "#00C896" }}>{c.id}</span>
        <span style={{ color: "var(--text)" }}>{c.usage || c.device}</span>
        {c.notes && <p className="text-xs mt-0.5 ml-8" style={{ color: "var(--muted)" }}>{c.notes}</p>}
      </div>
      <div className="text-right shrink-0 ml-4">
        {c.breaker_a && <div className="font-mono text-xs" style={{ color: "#6366F1" }}>{c.breaker_a} A</div>}
        {c.cable && <div className="font-mono text-xs" style={{ color: "var(--muted)" }}>{c.cable}</div>}
      </div>
    </div>
  );
}

export default function WattsonResults({ result, onReset }: Props) {
  const card = "rounded-xl border p-5 mb-4";
  const cardStyle = { background: "var(--surface)", borderColor: "var(--border)" };
  const sectionTitle = "text-sm font-bold uppercase tracking-widest mb-3";

  const heatingCircuits = Object.values(result.heating_circuits).filter(Boolean) as Circuit[];

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-bold" style={{ color: "var(--accent)" }}>
            ✓ {result.project_id}
          </h2>
          <p className="text-xs mt-0.5" style={{ color: "var(--muted)" }}>
            Zonă climatică {result.climate_zone} · {result.circuits_all.length} circuite totale
          </p>
        </div>
        <button onClick={onReset}
          className="text-xs px-3 py-1.5 rounded-lg font-semibold transition hover:opacity-80"
          style={{ border: "1px solid var(--border)", color: "var(--muted)" }}>
          ← Proiect nou
        </button>
      </div>

      {/* Circuite încălzire */}
      {heatingCircuits.length > 0 && (
        <div className={card} style={cardStyle}>
          <h3 className={sectionTitle} style={{ color: "#EC4899" }}>Circuite TE-CT</h3>
          {result.circuits_te_ct.map((c, i) => <CircuitRow key={i} c={c} />)}
        </div>
      )}

      {/* Circuite TEG */}
      <div className={card} style={cardStyle}>
        <h3 className={sectionTitle} style={{ color: "#6366F1" }}>Tablou General (TEG)</h3>
        {result.circuits_teg.map((c, i) => <CircuitRow key={i} c={c} />)}
      </div>

      {/* Camere */}
      <div className={card} style={cardStyle}>
        <h3 className={sectionTitle} style={{ color: "var(--accent)" }}>Prize & Iluminat pe cameră</h3>
        <div className="space-y-3">
          {result.rooms.map((room, i) => (
            <div key={i} className="rounded-lg p-3" style={{ background: "#141C2E", border: "1px solid var(--border)" }}>
              <div className="flex items-center gap-2 mb-2">
                <span className="font-semibold text-sm" style={{ color: "var(--text)" }}>{room.name}</span>
                <span className="text-xs" style={{ color: "var(--muted)" }}>{room.area_m2} m²</span>
              </div>
              {room.sockets.map((s, j) => (
                <div key={j} className="text-xs mb-1" style={{ color: "var(--muted)" }}>
                  🔌 {s.type} ×{s.count} @ {s.height_m}m — {s.notes}
                </div>
              ))}
              {room.lights.map((l, j) => (
                <div key={j} className="text-xs mb-1" style={{ color: "var(--muted)" }}>
                  💡 {l.type} ×{l.count} — {l.notes}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* Memoriu tehnic */}
      <div className={card} style={cardStyle}>
        <h3 className={sectionTitle} style={{ color: "var(--accent)" }}>Memoriu Tehnic</h3>
        <pre className="text-xs leading-relaxed whitespace-pre-wrap font-mono"
          style={{ color: "var(--muted)", maxHeight: 400, overflowY: "auto" }}>
          {result.memoriu_tehnic}
        </pre>
      </div>

      <button onClick={onReset}
        className="w-full py-3 rounded-xl font-bold text-sm uppercase tracking-widest transition hover:opacity-90"
        style={{ background: "linear-gradient(90deg, #00C896, #6366F1)", color: "#fff" }}>
        ⚡ Proiect nou
      </button>
    </div>
  );
}
