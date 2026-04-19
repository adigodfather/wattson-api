"use client";

import type { CalcResponse, Circuit } from "@/types/wattson";

interface Props {
  result: CalcResponse;
  onReset: () => void;
}

const card: React.CSSProperties = {
  background: "#0D1117", border: "1px solid #1E293B",
  borderRadius: 14, padding: 24, marginBottom: 16,
};
const sectionTitle = (color: string): React.CSSProperties => ({
  fontSize: 10, fontWeight: 800, letterSpacing: 3,
  textTransform: "uppercase", color, marginBottom: 16,
  display: "flex", alignItems: "center", gap: 8,
});
const tag = (color: string): React.CSSProperties => ({
  background: color + "22", color, padding: "2px 8px",
  borderRadius: 6, fontSize: 9,
});

function CircuitRow({ c }: { c: Circuit }) {
  return (
    <div style={{
      display: "flex", alignItems: "flex-start", justifyContent: "space-between",
      padding: "10px 0", borderBottom: "1px solid #1E293B",
    }}>
      <div>
        <span style={{ background: "#1E3A5F", color: "#00C896", fontFamily: "monospace", fontSize: 10, padding: "2px 7px", borderRadius: 5, marginRight: 8 }}>
          {c.id}
        </span>
        <span style={{ color: "#E2E8F0", fontSize: 13 }}>{c.usage || c.device}</span>
        {c.notes && <p style={{ color: "#475569", fontSize: 11, marginTop: 3, marginLeft: 40 }}>{c.notes}</p>}
      </div>
      <div style={{ textAlign: "right", flexShrink: 0, marginLeft: 16 }}>
        {c.breaker_a && <div style={{ color: "#6366F1", fontFamily: "monospace", fontSize: 11 }}>{c.breaker_a} A</div>}
        {c.cable && <div style={{ color: "#475569", fontFamily: "monospace", fontSize: 11 }}>{c.cable}</div>}
      </div>
    </div>
  );
}

export default function WattsonResults({ result, onReset }: Props) {
  const heatingCircuits = Object.values(result.heating_circuits).filter(Boolean) as Circuit[];

  return (
    <div>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 28 }}>
        <div>
          <div style={{ fontSize: 11, color: "#334155", letterSpacing: 3, textTransform: "uppercase", marginBottom: 6 }}>
            Proiect generat
          </div>
          <h2 style={{ fontSize: 22, fontWeight: 800, color: "#00C896", marginBottom: 4 }}>
            ✓ {result.project_id}
          </h2>
          <p style={{ fontSize: 12, color: "#475569" }}>
            Zonă climatică {result.climate_zone} · {result.circuits_all.length} circuite totale
          </p>
        </div>
        <button onClick={onReset} style={{
          padding: "8px 16px", borderRadius: 8,
          background: "transparent", border: "1px solid #1E293B",
          color: "#475569", fontSize: 12, cursor: "pointer",
        }}>
          ← Proiect nou
        </button>
      </div>

      {/* TE-CT */}
      {heatingCircuits.length > 0 && (
        <div style={card}>
          <div style={sectionTitle("#EC4899")}>
            <span style={tag("#EC4899")}>TE-CT</span>
            Circuite cameră tehnică
          </div>
          {result.circuits_te_ct.map((c, i) => <CircuitRow key={i} c={c} />)}
        </div>
      )}

      {/* TEG */}
      <div style={card}>
        <div style={sectionTitle("#6366F1")}>
          <span style={tag("#6366F1")}>TEG</span>
          Tablou electric general
        </div>
        {result.circuits_teg.map((c, i) => <CircuitRow key={i} c={c} />)}
      </div>

      {/* Camere */}
      <div style={card}>
        <div style={sectionTitle("#00C896")}>
          <span style={tag("#00C896")}>CAMERE</span>
          Prize & Iluminat pe cameră
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {result.rooms.map((room, i) => (
            <div key={i} style={{ background: "#141C2E", border: "1px solid #1E293B", borderRadius: 10, padding: "14px 16px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
                <span style={{ fontWeight: 700, fontSize: 13, color: "#E2E8F0" }}>{room.name}</span>
                <span style={{ fontSize: 11, color: "#475569" }}>{room.area_m2} m²</span>
              </div>
              {room.sockets.map((s, j) => (
                <div key={j} style={{ fontSize: 11, color: "#475569", marginBottom: 4, display: "flex", gap: 6 }}>
                  <span style={{ color: "#6366F1" }}>🔌</span>
                  {s.type} ×{s.count} @ {s.height_m}m — {s.notes}
                </div>
              ))}
              {room.lights.map((l, j) => (
                <div key={j} style={{ fontSize: 11, color: "#475569", marginBottom: 4, display: "flex", gap: 6 }}>
                  <span style={{ color: "#F59E0B" }}>💡</span>
                  {l.type} ×{l.count} — {l.notes}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* Memoriu tehnic */}
      <div style={card}>
        <div style={sectionTitle("#00C896")}>
          <span style={tag("#00C896")}>MEMO</span>
          Memoriu tehnic
        </div>
        <pre style={{
          fontSize: 11, lineHeight: 1.7, whiteSpace: "pre-wrap",
          fontFamily: "monospace", color: "#475569",
          maxHeight: 400, overflowY: "auto",
        }}>
          {result.memoriu_tehnic}
        </pre>
      </div>

      <button onClick={onReset} style={{
        width: "100%", padding: 15, borderRadius: 12, border: "none",
        background: "linear-gradient(90deg,#00C896,#6366F1)",
        color: "#fff", fontSize: 14, fontWeight: 800,
        letterSpacing: 1, textTransform: "uppercase", cursor: "pointer",
      }}>
        ⚡ Proiect nou
      </button>
    </div>
  );
}
