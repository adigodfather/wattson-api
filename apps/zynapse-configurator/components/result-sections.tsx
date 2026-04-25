"use client";

import { useState } from "react";
import type { Circuit, RoomResult, ProjectResult } from "@/lib/constants";

export { type ProjectResult };

/* ─── Logo ─── */
export function ZLogo({ size = 32, gradientId = "zg-shared" }: { size?: number; gradientId?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#378ADD" />
          <stop offset="100%" stopColor="#1D9E75" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="8" fill={`url(#${gradientId})`} />
      <text x="16" y="23" textAnchor="middle" fontFamily="'DM Sans', system-ui, sans-serif"
        fontSize="20" fontWeight="700" fill="white" letterSpacing="-1">Z</text>
    </svg>
  );
}

/* ─── Collapsible section ─── */
export function ResultSection({ title, children, defaultOpen = true, count }: {
  title: string; children: React.ReactNode; defaultOpen?: boolean; count?: number;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="rounded-xl mb-3 overflow-hidden"
      style={{ background: "rgba(255,255,255,0.025)", border: "1px solid rgba(255,255,255,0.06)" }}>
      <button onClick={() => setOpen(!open)}
        className="w-full px-5 py-3.5 flex justify-between items-center font-[inherit] cursor-pointer"
        style={{ background: "none", border: "none", color: "#C8CAD6" }}>
        <span className="flex items-center gap-2.5 text-sm font-semibold">
          {title}
          {count !== undefined && (
            <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full"
              style={{ background: "rgba(255,255,255,0.07)", color: "#8B8FA8" }}>{count}</span>
          )}
        </span>
        <span className="text-[10px] transition-transform duration-200"
          style={{ color: "#545870", transform: open ? "rotate(180deg)" : "none" }}>▼</span>
      </button>
      {open && (
        <div className="px-5 pb-4 border-t" style={{ borderColor: "rgba(255,255,255,0.04)" }}>
          {children}
        </div>
      )}
    </div>
  );
}

/* ─── Circuit table ─── */
export function CircuitTable({ circuits, title }: { circuits: Circuit[]; title: string }) {
  if (!circuits?.length) return null;
  const isTE = title.includes("TE-CT");
  return (
    <ResultSection title={title} count={circuits.length}>
      <div className="overflow-x-auto -mx-1 mt-3">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr>
              {["ID Circuit", "Utilizare", "Protecție", "Cablu"].map(h => (
                <th key={h} className="text-left px-3 py-2 text-[10px] font-semibold tracking-widest uppercase"
                  style={{ color: "#545870", borderBottom: "1px solid rgba(255,255,255,0.06)" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {circuits.map((c, i) => (
              <tr key={i} style={{ background: i % 2 ? "rgba(255,255,255,0.015)" : "transparent" }}>
                <td className="px-3 py-2.5">
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold tracking-wider"
                    style={{
                      background: isTE ? "rgba(212,83,126,0.14)" : "rgba(55,138,221,0.14)",
                      color: isTE ? "#ED93B1" : "#85B7EB",
                    }}>{c.id}</span>
                </td>
                <td className="px-3 py-2.5 text-sm" style={{ color: "#C8CAD6" }}>{c.usage}</td>
                <td className="px-3 py-2.5 text-sm font-semibold" style={{ color: "#8B8FA8" }}>{c.breaker_a}A</td>
                <td className="px-3 py-2.5 text-[12px]"
                  style={{ color: "#8B8FA8", fontFamily: "'JetBrains Mono', monospace" }}>{c.cable}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </ResultSection>
  );
}

/* ─── Rooms list ─── */
export function RoomsList({ rooms }: { rooms: RoomResult[] }) {
  if (!rooms?.length) return null;
  return (
    <ResultSection title="Camere identificate" count={rooms.length} defaultOpen={false}>
      <div className="grid gap-2 mt-3">
        {rooms.map((r, i) => (
          <div key={i} className="px-4 py-3 rounded-lg"
            style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.05)" }}>
            <div className="flex justify-between items-start mb-1.5">
              <span className="text-sm font-semibold" style={{ color: "#E2E4E9" }}>{r.name}</span>
              <span className="text-[12px]" style={{ color: "#8B8FA8", fontFamily: "'JetBrains Mono', monospace" }}>
                {r.area_m2} m²
              </span>
            </div>
            <div className="flex gap-4 text-[11px]" style={{ color: "#545870" }}>
              <span>Prize: <span style={{ color: "#8B8FA8" }}>{r.sockets?.reduce((s, x) => s + (x.count || 0), 0) || 0}</span></span>
              <span>Iluminat: <span style={{ color: "#8B8FA8" }}>{r.lights?.reduce((s, x) => s + (x.count || 0), 0) || 0}</span></span>
              <span className="capitalize" style={{ color: "#8B8FA8" }}>{r.function}</span>
            </div>
          </div>
        ))}
      </div>
    </ResultSection>
  );
}

/* ─── Memoriu section ─── */
export function MemoriuSection({ text, filename = "memoriu_tehnic.txt" }: { text: string; filename?: string }) {
  if (!text) return null;

  const download = () => {
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <ResultSection title="Memoriu tehnic" defaultOpen={false}>
      <pre className="mt-3 whitespace-pre-wrap break-words leading-relaxed m-0 max-h-[440px] overflow-y-auto p-4 rounded-lg"
        style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: "12px",
          color: "#8B8FA8",
          background: "rgba(0,0,0,0.3)",
          lineHeight: 1.7,
        }}>{text}</pre>
      <button onClick={download}
        className="mt-3 px-5 py-2 rounded-lg text-sm cursor-pointer font-[inherit] transition-colors duration-150"
        style={{ background: "rgba(55,138,221,0.1)", border: "1px solid rgba(55,138,221,0.25)", color: "#5BB8F5" }}
        onMouseOver={(e) => (e.currentTarget.style.background = "rgba(55,138,221,0.18)")}
        onMouseOut={(e) => (e.currentTarget.style.background = "rgba(55,138,221,0.1)")}>
        Descarcă memoriu .txt
      </button>
    </ResultSection>
  );
}

/* ─── Metric card ─── */
export function MetricCard({ value, label, color }: { value: string | number; label: string; color: string }) {
  return (
    <div className="rounded-xl p-4 text-center"
      style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
      <div className="text-2xl font-bold mb-1 tracking-tight" style={{ color }}>{value}</div>
      <div className="text-[11px] font-medium" style={{ color: "#545870" }}>{label}</div>
    </div>
  );
}

/* ─── Full result panel (reused on /projects/[id]) ─── */
export function ProjectResultPanel({ result, projectName }: { result: ProjectResult; projectName?: string }) {
  const exportJSON = () => {
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `${result.project_id || projectName || "proiect"}.json`; a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-5">
        <div>
          <h2 className="text-lg font-bold tracking-tight m-0" style={{ color: "#E2E4E9" }}>
            {result.project_id || projectName}
          </h2>
          <p className="text-[12px] mt-0.5 m-0" style={{ color: "#545870" }}>
            Zona climatică {result.climate_zone}
          </p>
        </div>
        <button onClick={exportJSON}
          className="px-4 py-2 rounded-lg text-[13px] font-semibold font-[inherit] cursor-pointer transition-colors duration-150"
          style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", color: "#8B8FA8" }}
          onMouseOver={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.08)")}
          onMouseOut={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.04)")}>
          Export JSON
        </button>
      </div>

      <div className="grid gap-3 mb-5" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))" }}>
        {result.heating_circuits?.pdc && (
          <>
            <MetricCard value={`${result.heating_circuits.pdc.power_kw_thermal} kW`} label="Putere termică PDC" color="#EF9F27" />
            <MetricCard value={`${result.heating_circuits.pdc.breaker_a}A`} label="Protecție PDC" color="#5BB8F5" />
          </>
        )}
        <MetricCard value={result.circuits_all?.length || 0} label="Circuite totale" color="#3ECFA0" />
        <MetricCard value={result.rooms?.length || 0} label="Camere" color="#ED93B1" />
      </div>

      <CircuitTable circuits={result.circuits_te_ct} title="TE-CT — Cameră tehnică" />
      <CircuitTable circuits={result.circuits_teg} title="TEG — Tablou general" />
      <RoomsList rooms={result.rooms} />
      <MemoriuSection text={result.memoriu_tehnic} filename={`${result.project_id || "memoriu"}.txt`} />
    </div>
  );
}
