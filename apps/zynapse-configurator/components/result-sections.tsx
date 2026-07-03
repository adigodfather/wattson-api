"use client";

import { useState } from "react";
import { isPhasePT, iluminatPlanseToShow } from "@/lib/constants";
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
export function MemoriuSection({ text }: { text: string }) {
  if (!text) return null;
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
    </ResultSection>
  );
}

/* ─── Memoriu tehnic (.docx) download button ───
   CITEȘTE-AMBELE (Problema 5, Etapa 1): base64 ÎNTÂI (proiecte vechi + memoriu proaspăt de la
   "Finalizează" — mereu versiunea mai nouă), altfel storagePath -> signed URL PROASPĂT la click
   (bucket privat project-files, RLS owner-only; URL-ul expiră în 60s, nu se stochează). */
export function MemoriuDocxButton({ base64Docx, storagePath, label = "Descarcă Memoriu tehnic (.docx)", fileName = "Memoriu_Tehnic.docx" }: { base64Docx?: string | null; storagePath?: string | null; label?: string; fileName?: string }) {
  const handleDownload = async () => {
    // 1) BASE64 (vechi / finalizat proaspăt) -> decodează direct (comportamentul dintotdeauna)
    if (base64Docx) {
      const raw = base64Docx.includes(",") ? base64Docx.split(",")[1] : base64Docx;
      const byteStr = atob(raw);
      const ab = new ArrayBuffer(byteStr.length);
      const ia = new Uint8Array(ab);
      for (let i = 0; i < byteStr.length; i++) ia[i] = byteStr.charCodeAt(i);
      const blob = new Blob([ab], {
        type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = fileName;
      a.click();
      URL.revokeObjectURL(url);
      return;
    }
    // 2) REFERINȚĂ Storage (proiect nou) -> signed URL proaspăt, cu download forțat + nume corect
    if (storagePath) {
      try {
        const { createClient } = await import("@/lib/supabase");
        const { data, error } = await createClient().storage
          .from("project-files")
          .createSignedUrl(storagePath, 60, { download: fileName });
        if (error || !data?.signedUrl) {
          console.error("[MemoriuDocx] signed URL esuat:", error?.message);
          alert("Nu s-a putut descărca memoriul. Încearcă din nou.");
          return;
        }
        const a = document.createElement("a");
        a.href = data.signedUrl;
        a.click();
      } catch (e) {
        console.error("[MemoriuDocx] download din Storage esuat:", e);
        alert("Nu s-a putut descărca memoriul. Încearcă din nou.");
      }
    }
  };

  return (
    <button
      onClick={handleDownload}
      className="w-full py-2.5 rounded-lg text-[13px] font-semibold font-[inherit] cursor-pointer transition-colors duration-150 flex items-center justify-center gap-2"
      style={{
        background: "rgba(55,138,221,0.12)",
        border: "1px solid rgba(55,138,221,0.28)",
        color: "#60A5FA",
      }}
      onMouseOver={(e) => (e.currentTarget.style.background = "rgba(55,138,221,0.22)")}
      onMouseOut={(e) => (e.currentTarget.style.background = "rgba(55,138,221,0.12)")}
    >
      <span style={{ fontSize: 15 }}>⬇</span> {label}
    </button>
  );
}

/* ─── Schema monofilară download button ───
   CITEȘTE-AMBELE (Problema 5, Etapa 2): base64 ÎNTÂI (proiecte vechi + schema proaspătă în
   memorie), altfel storagePath -> signed URL PROASPĂT la click (bucket privat, expiră 60s). */
export function SchemaDownloadButton({ base64Pdf, storagePath, label = "Schemă monofilară PDF", fileName = "schema-monofilara.pdf" }: { base64Pdf?: string | null; storagePath?: string | null; label?: string; fileName?: string }) {
  const handleDownload = async () => {
    if (base64Pdf) {
      const raw = base64Pdf.includes(",") ? base64Pdf.split(",")[1] : base64Pdf;
      const byteStr = atob(raw);
      const ab = new ArrayBuffer(byteStr.length);
      const ia = new Uint8Array(ab);
      for (let i = 0; i < byteStr.length; i++) ia[i] = byteStr.charCodeAt(i);
      const blob = new Blob([ab], { type: "application/pdf" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = fileName;
      a.click();
      URL.revokeObjectURL(url);
      return;
    }
    if (storagePath) {
      try {
        const { createClient } = await import("@/lib/supabase");
        const { data, error } = await createClient().storage
          .from("project-files")
          .createSignedUrl(storagePath, 60, { download: fileName });
        if (error || !data?.signedUrl) {
          console.error("[SchemaDownload] signed URL esuat:", error?.message);
          alert("Nu s-a putut descărca schema. Încearcă din nou.");
          return;
        }
        const a = document.createElement("a");
        a.href = data.signedUrl;
        a.click();
      } catch (e) {
        console.error("[SchemaDownload] download din Storage esuat:", e);
        alert("Nu s-a putut descărca schema. Încearcă din nou.");
      }
    }
  };

  return (
    <button
      onClick={handleDownload}
      className="w-full py-2.5 rounded-lg text-[13px] font-semibold font-[inherit] cursor-pointer transition-colors duration-150 flex items-center justify-center gap-2"
      style={{
        background: "rgba(21,128,61,0.12)",
        border: "1px solid rgba(21,128,61,0.28)",
        color: "#4ADE80",
      }}
      onMouseOver={(e) => (e.currentTarget.style.background = "rgba(21,128,61,0.22)")}
      onMouseOut={(e) => (e.currentTarget.style.background = "rgba(21,128,61,0.12)")}
    >
      <span style={{ fontSize: 15 }}>⬇</span> {label}
    </button>
  );
}

/* ─── Multi-schema download cards ─── */
export function SchemasSection({ schemas }: { schemas: NonNullable<ProjectResult["schemas"]> }) {
  if (!schemas?.length) return null;
  return (
    <ResultSection title="Scheme monofilare" count={schemas.length} defaultOpen>
      <div className="flex flex-col gap-2 mt-3">
        {schemas.map((s, i) => (
          <SchemaDownloadButton
            key={i}
            base64Pdf={s.pdf_base64}
            label={`${s.name}${s.plansa_nr ? ` — Planșa ${s.plansa_nr}` : ""} PDF`}
            fileName={`schema-${s.name.toLowerCase().replace(/\s+/g, "-")}.pdf`}
          />
        ))}
      </div>
    </ResultSection>
  );
}

/* ─── Annotated plan ─── */
export function AnnotatedPlanSection({ src }: { src: string }) {
  if (!src) return null;

  const handleDownload = () => {
    const a = document.createElement("a");
    a.href = src;
    a.download = "plansa_adnotata.png";
    a.click();
  };

  return (
    <ResultSection title="Planșă adnotată" defaultOpen>
      <div className="mt-3">
        <img
          src={src}
          alt="Planșă electrică adnotată"
          className="w-full rounded-lg"
          style={{ border: "1px solid rgba(255,255,255,0.08)" }}
        />
        <button
          onClick={handleDownload}
          className="mt-3 w-full py-2.5 rounded-lg text-[13px] font-semibold font-[inherit] cursor-pointer transition-colors duration-150"
          style={{
            background: "rgba(55,138,221,0.12)",
            border: "1px solid rgba(55,138,221,0.25)",
            color: "#85B7EB",
          }}
          onMouseOver={(e) => (e.currentTarget.style.background = "rgba(55,138,221,0.2)")}
          onMouseOut={(e) => (e.currentTarget.style.background = "rgba(55,138,221,0.12)")}
        >
          Descarcă planșă adnotată
        </button>
      </div>
    </ResultSection>
  );
}

/* ─── Planșe PDF cu straturi (iluminat cu becuri, forță... — fiecare planșă separată) ─── */
export function PlanPdfSection({ planse }: {
  planse: Array<{ name: string; pdf_base64: string; filename?: string; plansa_nr?: string; source_plansa_nr?: string; type?: string; ie_label?: string }>;
}) {
  if (!planse?.length) return null;
  return (
    <ResultSection title="Planșe" count={planse.length} defaultOpen>
      <div className="flex flex-col gap-4 mt-3">
        {planse.map((p, i) => {
          const nr = p.ie_label || p.plansa_nr || p.source_plansa_nr || "";   // M3: IE.x prioritar
          return (
            <div key={i} className="rounded-xl overflow-hidden"
              style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)" }}>
              <div className="px-4 py-2.5 border-b" style={{ borderColor: "rgba(255,255,255,0.04)" }}>
                <span className="text-sm font-semibold" style={{ color: "#C8CAD6" }}>
                  {nr ? `${nr} — ` : ""}{p.name}
                </span>
              </div>
              <iframe
                src={`data:application/pdf;base64,${p.pdf_base64}`}
                className="w-full"
                style={{ height: 600, border: "none" }}
                title={p.name}
              />
              <div className="px-4 py-3">
                <SchemaDownloadButton
                  base64Pdf={p.pdf_base64}
                  label={`Descarcă ${p.name} PDF`}
                  fileName={p.filename || `Plan-${p.name.toLowerCase().replace(/\s+/g, "-")}.pdf`}
                />
              </div>
            </div>
          );
        })}
      </div>
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

/* ─── Project info card (cartus data) ─── */
export function ProjectInfoCard({ info }: { info: NonNullable<ProjectResult["project_info"]> }) {
  const rows: { label: string; value: string | undefined }[] = [
    { label: "Titlu proiect", value: info.titlu_proiect },
    { label: "Beneficiar", value: info.beneficiar },
    { label: "Amplasament", value: info.amplasament },
    { label: "Șef proiect", value: info.sef_proiect },
    { label: "Nr. proiect", value: info.proiect_nr },
    { label: "Data", value: info.data },
    { label: "Faza", value: info.faza },
    { label: "Planșă", value: info.plansa_nr },
  ].filter(r => r.value);

  if (!rows.length) return null;

  return (
    <div className="rounded-xl mb-4 px-4 py-3"
      style={{ background: "rgba(255,255,255,0.025)", border: "1px solid rgba(255,255,255,0.06)" }}>
      <p className="text-[10px] font-semibold tracking-widest uppercase mb-2.5 m-0"
        style={{ color: "#545870" }}>Date proiect (cartus)</p>
      <div className="grid gap-y-1.5 gap-x-4" style={{ gridTemplateColumns: "auto 1fr" }}>
        {rows.map(({ label, value }) => (
          <>
            <span key={`l-${label}`} className="text-[11px]" style={{ color: "#545870" }}>{label}</span>
            <span key={`v-${label}`} className="text-[11px] font-medium" style={{ color: "#C8CAD6" }}>{value}</span>
          </>
        ))}
      </div>
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
            {result.project_name || result.project_id || projectName}
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

      {result.project_info && <ProjectInfoCard info={result.project_info} />}

      {/* Planșă (iluminat / plan adnotat) — DOAR pe faza PT (DTAC+PT) */}
      {isPhasePT(result.output_phase ?? result.project_info?.faza ?? "") && (() => {
        // 1d: planul REGENERAT (cabluri+editari) e planul principal; ciorna Vision (neregenerata) se ASCUNDE.
        const { planse, draftPending } = iluminatPlanseToShow(result);
        if (draftPending) {
          return <p className="text-sm text-center py-8" style={{ color: "#545870" }}>Planul de iluminat nu a fost generat din editor (ciornă).</p>;
        }
        if (planse.length) return <PlanPdfSection planse={planse} />;
        if (result.annotated_plan_base64) return <AnnotatedPlanSection src={result.annotated_plan_base64} />;
        return null;
      })()}
      {result.schemas?.length ? (
        <SchemasSection schemas={result.schemas} />
      ) : (result.schema_monofilara_pdf || result.schema_monofilara_path) ? (
        <div className="mb-3">
          <SchemaDownloadButton base64Pdf={result.schema_monofilara_pdf} storagePath={result.schema_monofilara_path} />
        </div>
      ) : null}
      <CircuitTable circuits={result.circuits_te_ct} title="TE-CT — Cameră tehnică" />
      <CircuitTable circuits={result.circuits_teg} title="TEG — Tablou general" />
      <RoomsList rooms={result.rooms} />
      <MemoriuSection text={result.memoriu_tehnic} />
    </div>
  );
}
