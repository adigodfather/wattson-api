"use client";

import { useState, useRef, useCallback } from "react";
import {
  BUILDING_TYPES, LEVELS, CLIMATE_ZONES, INSULATION, HEATING,
  INITIAL_FORM, type FormData, type ProjectResult, type Circuit, type RoomResult,
} from "@/lib/constants";
import { useAuth } from "@/components/auth-provider";

const WEBHOOK_URL =
  process.env.NEXT_PUBLIC_N8N_WEBHOOK_URL ||
  "https://www.ai-nord-vest.com/webhook/zynapse-electrical";

const PROGRESS_STEPS = [
  "Se encodează planșele...",
  "Se trimite la n8n...",
  "Claude Vision analizează planșa...",
  "Se calculează circuitele...",
  "Se generează memoriul tehnic...",
];

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve((reader.result as string).split(",")[1]);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

/* ─── Logo ─── */
function ZLogo({ size = 32 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="zg" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#378ADD" />
          <stop offset="100%" stopColor="#1D9E75" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="8" fill="url(#zg)" />
      <text x="16" y="23" textAnchor="middle" fontFamily="'DM Sans', system-ui, sans-serif"
        fontSize="20" fontWeight="700" fill="white" letterSpacing="-1">Z</text>
    </svg>
  );
}

/* ─── Status badge ─── */
function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { bg: string; dot: string; text: string; label: string }> = {
    idle:    { bg: "rgba(139,143,168,0.1)",  dot: "#545870", text: "#8B8FA8", label: "Inactiv" },
    loading: { bg: "rgba(55,138,221,0.12)",  dot: "#378ADD", text: "#5BB8F5", label: "Procesare" },
    success: { bg: "rgba(29,158,117,0.12)",  dot: "#1D9E75", text: "#3ECFA0", label: "Finalizat" },
    error:   { bg: "rgba(226,75,74,0.12)",   dot: "#E24B4A", text: "#F09595", label: "Eroare" },
  };
  const c = map[status] ?? map.idle;
  return (
    <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-[11px] font-semibold tracking-wide uppercase"
      style={{ background: c.bg, color: c.text }}>
      {status === "loading" ? (
        <span className="inline-block w-2 h-2 border-[1.5px] rounded-full"
          style={{ borderColor: c.text, borderTopColor: "transparent", animation: "zy-spin 0.7s linear infinite" }} />
      ) : (
        <span className="inline-block w-1.5 h-1.5 rounded-full" style={{ background: c.dot }} />
      )}
      {c.label}
    </span>
  );
}

/* ─── Form atoms ─── */
function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2 mb-4 mt-6 first:mt-0">
      <span className="text-[11px] font-semibold tracking-widest uppercase"
        style={{ color: "#545870" }}>{children}</span>
      <div className="flex-1 h-px" style={{ background: "rgba(255,255,255,0.05)" }} />
    </div>
  );
}

function SelectField({ label, value, onChange, options, required }: {
  label: string; value: string; onChange: (v: string) => void;
  options: { value: string; label: string }[]; required?: boolean;
}) {
  return (
    <div className="mb-3.5">
      <label className="block text-[12px] font-semibold tracking-wide mb-1.5"
        style={{ color: "#8B8FA8" }}>
        {label}{required && <span style={{ color: "#E24B4A" }}> *</span>}
      </label>
      <div className="relative">
        <select value={value} onChange={(e) => onChange(e.target.value)}
          className="w-full px-3.5 py-2.5 rounded-lg text-sm outline-none font-[inherit] pr-9"
          style={{
            background: "rgba(255,255,255,0.04)",
            border: "1px solid rgba(255,255,255,0.08)",
            color: value ? "#E2E4E9" : "#545870",
            transition: "border-color 0.15s",
          }}>
          <option value="">— Alege —</option>
          {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[10px]"
          style={{ color: "#545870" }}>▾</span>
      </div>
    </div>
  );
}

function TextField({ label, value, onChange, placeholder, required }: {
  label: string; value: string; onChange: (v: string) => void;
  placeholder?: string; required?: boolean;
}) {
  return (
    <div className="mb-3.5">
      <label className="block text-[12px] font-semibold tracking-wide mb-1.5"
        style={{ color: "#8B8FA8" }}>
        {label}{required && <span style={{ color: "#E24B4A" }}> *</span>}
      </label>
      <input type="text" value={value} onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-3.5 py-2.5 rounded-lg text-sm outline-none font-[inherit]"
        style={{
          background: "rgba(255,255,255,0.04)",
          border: "1px solid rgba(255,255,255,0.08)",
          color: "#E2E4E9",
        }} />
    </div>
  );
}

function Toggle({ label, checked, onChange, description }: {
  label: string; checked: boolean; onChange: (v: boolean) => void; description?: string;
}) {
  return (
    <label className="flex items-center gap-3 mb-3 cursor-pointer select-none group">
      <div className="relative shrink-0 w-9 h-5 rounded-full transition-all duration-200"
        style={{ background: checked ? "#378ADD" : "rgba(255,255,255,0.1)" }}>
        <div className="absolute top-0.5 w-4 h-4 rounded-full bg-white shadow-sm transition-all duration-200"
          style={{ left: checked ? 18 : 2 }} />
        <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)}
          className="absolute opacity-0 w-full h-full cursor-pointer m-0 top-0 left-0" />
      </div>
      <div>
        <div className="text-sm" style={{ color: "#C8CAD6" }}>{label}</div>
        {description && <div className="text-[11px] mt-0.5" style={{ color: "#545870" }}>{description}</div>}
      </div>
    </label>
  );
}

/* ─── Drop zone ─── */
function DropZone({ files, setFiles }: { files: File[]; setFiles: React.Dispatch<React.SetStateAction<File[]>> }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const addFiles = useCallback((incoming: File[]) => {
    const valid = incoming.filter(f => f.type.startsWith("image/") || f.type === "application/pdf");
    if (valid.length) setFiles(prev => [...prev, ...valid]);
  }, [setFiles]);

  return (
    <div className="mb-5">
      <label className="block text-[12px] font-semibold tracking-wide mb-1.5" style={{ color: "#8B8FA8" }}>
        Planșe arhitectură
      </label>
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); addFiles(Array.from(e.dataTransfer.files)); }}
        onClick={() => inputRef.current?.click()}
        className="rounded-xl py-7 px-5 text-center cursor-pointer transition-all duration-200"
        style={{
          border: `2px dashed ${dragging ? "#378ADD" : "rgba(255,255,255,0.1)"}`,
          background: dragging ? "rgba(55,138,221,0.05)" : "rgba(255,255,255,0.02)",
        }}>
        <input ref={inputRef} type="file" multiple accept="image/*,.pdf" className="hidden"
          onChange={(e) => addFiles(Array.from(e.target.files || []))} />
        <div className="mb-2.5">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" className="mx-auto opacity-30">
            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            <polyline points="17,8 12,3 7,8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            <line x1="12" y1="3" x2="12" y2="15" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
        </div>
        <div className="text-sm" style={{ color: "#8B8FA8" }}>
          {dragging ? "Eliberează pentru a adăuga" : "Trage planșele sau click pentru selectare"}
        </div>
        <div className="text-[11px] mt-1" style={{ color: "#545870" }}>PDF, JPG, PNG — parter, etaj, mansardă</div>
      </div>

      {files.length > 0 && (
        <div className="mt-2.5 flex flex-wrap gap-2">
          {files.map((f, i) => (
            <div key={i} className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs"
              style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.07)" }}>
              <span style={{ color: f.type.startsWith("image/") ? "#5BB8F5" : "#3ECFA0" }}>
                {f.type.startsWith("image/") ? "IMG" : "PDF"}
              </span>
              <span className="max-w-[140px] truncate" style={{ color: "#C8CAD6" }}>{f.name}</span>
              <span style={{ color: "#545870" }}>{(f.size / 1024).toFixed(0)}KB</span>
              <button
                onClick={(e) => { e.stopPropagation(); setFiles(prev => prev.filter((_, j) => j !== i)); }}
                className="ml-0.5 text-base leading-none transition-colors"
                style={{ background: "none", border: "none", color: "#545870", cursor: "pointer", padding: 0 }}
                onMouseOver={(e) => (e.currentTarget.style.color = "#E2E4E9")}
                onMouseOut={(e) => (e.currentTarget.style.color = "#545870")}>×</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ─── Results: collapsible section ─── */
function ResultSection({ title, children, defaultOpen = true, count }: {
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
        <span className="text-[10px] transition-transform duration-200" style={{
          color: "#545870",
          transform: open ? "rotate(180deg)" : "none",
        }}>▼</span>
      </button>
      {open && <div className="px-5 pb-4 border-t" style={{ borderColor: "rgba(255,255,255,0.04)" }}>{children}</div>}
    </div>
  );
}

/* ─── Circuit table ─── */
function CircuitTable({ circuits, title }: { circuits: Circuit[]; title: string }) {
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
                <td className="px-3 py-2.5 text-[12px] font-mono" style={{ color: "#8B8FA8", fontFamily: "'JetBrains Mono', monospace" }}>{c.cable}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </ResultSection>
  );
}

/* ─── Rooms list ─── */
function RoomsList({ rooms }: { rooms: RoomResult[] }) {
  if (!rooms?.length) return null;
  return (
    <ResultSection title="Camere identificate" count={rooms.length} defaultOpen={false}>
      <div className="grid gap-2 mt-3">
        {rooms.map((r, i) => (
          <div key={i} className="px-4 py-3 rounded-lg"
            style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.05)" }}>
            <div className="flex justify-between items-start mb-1.5">
              <span className="text-sm font-semibold" style={{ color: "#E2E4E9" }}>{r.name}</span>
              <span className="text-[12px] font-mono" style={{ color: "#8B8FA8" }}>{r.area_m2} m²</span>
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
function MemoriuSection({ text }: { text: string }) {
  if (!text) return null;

  const download = () => {
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "memoriu_tehnic.txt"; a.click();
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
        style={{
          background: "rgba(55,138,221,0.1)",
          border: "1px solid rgba(55,138,221,0.25)",
          color: "#5BB8F5",
        }}
        onMouseOver={(e) => (e.currentTarget.style.background = "rgba(55,138,221,0.18)")}
        onMouseOut={(e) => (e.currentTarget.style.background = "rgba(55,138,221,0.1)")}>
        Descarcă memoriu .txt
      </button>
    </ResultSection>
  );
}

/* ─── Metric card ─── */
function MetricCard({ value, label, color }: { value: string | number; label: string; color: string }) {
  return (
    <div className="rounded-xl p-4 text-center"
      style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
      <div className="text-2xl font-bold mb-1 tracking-tight" style={{ color }}>{value}</div>
      <div className="text-[11px] font-medium" style={{ color: "#545870" }}>{label}</div>
    </div>
  );
}

/* ─── Main configurator ─── */
export function ZynapseConfigurator() {
  const { user, profile, signOut } = useAuth();
  const [files, setFiles] = useState<File[]>([]);
  const [form, setForm] = useState<FormData>(INITIAL_FORM);
  const [status, setStatus] = useState("idle");
  const [result, setResult] = useState<ProjectResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stepIndex, setStepIndex] = useState(0);

  const update = (key: keyof FormData, val: string | boolean) =>
    setForm(prev => ({ ...prev, [key]: val }));

  const canSubmit = !!(form.project_id && form.building_type && form.levels &&
    form.insulation_level && form.heating_type && files.length > 0);

  const isPDC = form.heating_type?.startsWith("pdc") || form.heating_type === "geothermal";

  const handleSubmit = async () => {
    if (!canSubmit || status === "loading") return;
    setStatus("loading"); setError(null); setResult(null); setStepIndex(0);

    try {
      setStepIndex(0);
      const base64 = await fileToBase64(files[0]);

      setStepIndex(1);
      const payload = { plan_base64: base64, plan_type: files[0].type || "image/jpeg", ...form };

      setStepIndex(2);
      const res = await fetch(WEBHOOK_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      setStepIndex(3);
      const data: ProjectResult = await res.json();
      if ((data as any).status === "error") throw new Error((data as any).error || "Eroare necunoscută");

      setStepIndex(4);
      setResult(data);
      setStatus("success");
    } catch (err: any) {
      setError(err.message || "Eroare de conexiune la n8n");
      setStatus("error");
    }
  };

  const exportJSON = () => {
    if (!result) return;
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `${result.project_id || "proiect"}.json`; a.click();
    URL.revokeObjectURL(url);
  };

  const isLoading = status === "loading";
  const hasResult = !!result;

  return (
    <div style={{ minHeight: "100vh", background: "#0A0B0E" }}>

      {/* ── Header ── */}
      <header className="px-8 py-4 flex justify-between items-center sticky top-0 z-50"
        style={{
          background: "rgba(10,11,14,0.88)",
          borderBottom: "1px solid rgba(255,255,255,0.06)",
          backdropFilter: "blur(16px)",
          WebkitBackdropFilter: "blur(16px)",
        }}>
        <div className="flex items-center gap-3">
          <ZLogo size={32} />
          <span className="text-[17px] font-bold tracking-tight" style={{ color: "#E2E4E9" }}>Zynapse</span>
          <span className="text-[10px] font-bold tracking-widest uppercase px-2 py-1 rounded-md"
            style={{ background: "rgba(55,138,221,0.12)", color: "#5BB8F5", border: "1px solid rgba(55,138,221,0.2)" }}>
            Beta
          </span>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={status} />
          {user && (
            <>
              <span className="text-sm hidden sm:block" style={{ color: "#8B8FA8" }}>
                {profile?.full_name || user.email}
              </span>
              <button onClick={signOut}
                className="px-3 py-1.5 rounded-lg text-sm font-medium font-[inherit] cursor-pointer transition-colors duration-150"
                style={{
                  background: "rgba(255,255,255,0.05)",
                  border: "1px solid rgba(255,255,255,0.1)",
                  color: "#8B8FA8",
                }}
                onMouseOver={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.09)")}
                onMouseOut={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.05)")}>
                Deconectare
              </button>
            </>
          )}
        </div>
      </header>

      {/* ── Layout ── */}
      <div className="p-8"
        style={{
          maxWidth: 1280,
          margin: "0 auto",
          display: "grid",
          gridTemplateColumns: hasResult ? "400px 1fr" : "400px 1fr",
          gap: 24,
          alignItems: "start",
        }}>

        {/* ── Form panel ── */}
        <div className="rounded-2xl p-6 sticky top-[73px]"
          style={{
            background: "rgba(255,255,255,0.025)",
            border: "1px solid rgba(255,255,255,0.07)",
            maxHeight: "calc(100vh - 97px)",
            overflowY: "auto",
          }}>

          <div className="mb-5">
            <h1 className="text-lg font-bold tracking-tight m-0" style={{ color: "#E2E4E9" }}>
              Configurator proiect
            </h1>
            <p className="text-[13px] mt-1 m-0" style={{ color: "#545870" }}>
              Încarcă planșele și completează datele clădirii
            </p>
          </div>

          <DropZone files={files} setFiles={setFiles} />

          <div style={{ height: 1, background: "rgba(255,255,255,0.05)", margin: "16px 0" }} />

          <SectionLabel>Identificare proiect</SectionLabel>
          <TextField label="Numele proiectului" value={form.project_id}
            onChange={v => update("project_id", v)} placeholder="ex: Casa Popescu P+M 160mp" required />

          <SectionLabel>Parametri clădire</SectionLabel>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <SelectField label="Tip clădire" value={form.building_type}
              onChange={v => update("building_type", v)} options={BUILDING_TYPES} required />
            <SelectField label="Regim înălțime" value={form.levels}
              onChange={v => update("levels", v)}
              options={LEVELS.map(l => ({ value: l, label: l }))} required />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <SelectField label="Zona climatică" value={form.climate_zone}
              onChange={v => update("climate_zone", v)} options={CLIMATE_ZONES} />
            <SelectField label="Nivel izolație" value={form.insulation_level}
              onChange={v => update("insulation_level", v)} options={INSULATION} required />
          </div>
          <TextField label="Intrare principală" value={form.main_entrance}
            onChange={v => update("main_entrance", v)} placeholder="ex: Parter, fațada sud" />

          <SectionLabel>Sistem termoenergetic</SectionLabel>
          <SelectField label="Tip încălzire" value={form.heating_type}
            onChange={v => update("heating_type", v)} options={HEATING} required />
          {isPDC && (
            <SelectField label="Fază PDC" value={form.pdc_phase}
              onChange={v => update("pdc_phase", v)}
              options={[{ value: "mono", label: "Monofazat 1F" }, { value: "tri", label: "Trifazat 3F" }]} />
          )}

          <div className="mt-1">
            <Toggle label="Boiler ACM" checked={form.has_acm_boiler} onChange={v => update("has_acm_boiler", v)}
              description="Preparare apă caldă menajeră" />
            <Toggle label="Ventilație mecanică" checked={form.has_ventilation} onChange={v => update("has_ventilation", v)} />
            <Toggle label="Recuperator de căldură (HRV)" checked={form.has_hrv} onChange={v => update("has_hrv", v)} />
            <Toggle label="Încălzire în pardoseală" checked={form.has_floor_heating} onChange={v => update("has_floor_heating", v)} />
          </div>

          <SectionLabel>Note suplimentare</SectionLabel>
          <textarea value={form.notes} onChange={(e) => update("notes", e.target.value)}
            placeholder="Garaj încălzit, anexe, specificații speciale..." rows={3}
            className="w-full px-3.5 py-2.5 rounded-lg text-sm font-[inherit] outline-none"
            style={{
              background: "rgba(255,255,255,0.04)",
              border: "1px solid rgba(255,255,255,0.08)",
              color: "#E2E4E9",
              resize: "vertical",
            }} />

          {/* Submit button */}
          <button onClick={handleSubmit} disabled={!canSubmit || isLoading}
            className="w-full mt-5 py-3.5 px-6 rounded-xl text-[14px] font-semibold font-[inherit] tracking-wide transition-all duration-200"
            style={{
              background: canSubmit && !isLoading
                ? "linear-gradient(135deg, #378ADD 0%, #1D9E75 100%)"
                : "rgba(255,255,255,0.05)",
              border: "none",
              color: canSubmit ? "#fff" : "#545870",
              cursor: canSubmit && !isLoading ? "pointer" : "not-allowed",
              opacity: isLoading ? 0.75 : 1,
              boxShadow: canSubmit && !isLoading ? "0 0 24px rgba(55,138,221,0.25)" : "none",
            }}>
            {isLoading ? "Se procesează..." : "Generează proiect electric"}
          </button>

          {/* Progress indicator */}
          {isLoading && (
            <div className="mt-3">
              <div className="h-0.5 rounded-full mb-2 overflow-hidden" style={{ background: "rgba(255,255,255,0.07)" }}>
                <div className="h-full rounded-full transition-all duration-700"
                  style={{
                    width: `${((stepIndex + 1) / PROGRESS_STEPS.length) * 100}%`,
                    background: "linear-gradient(90deg, #378ADD, #1D9E75)",
                  }} />
              </div>
              <div className="text-center text-[12px]"
                style={{ color: "#5BB8F5", animation: "zy-pulse 1.6s ease-in-out infinite" }}>
                {PROGRESS_STEPS[stepIndex] || PROGRESS_STEPS[0]}
              </div>
            </div>
          )}

          {error && (
            <div className="mt-3 p-3.5 rounded-lg text-sm"
              style={{
                background: "rgba(226,75,74,0.1)",
                border: "1px solid rgba(226,75,74,0.2)",
                color: "#F09595",
              }}>
              {error}
            </div>
          )}
        </div>

        {/* ── Results / Empty state ── */}
        {hasResult ? (
          <div className="zy-slide-in">
            {/* Results header */}
            <div className="flex justify-between items-center mb-5">
              <div>
                <h2 className="text-lg font-bold tracking-tight m-0" style={{ color: "#E2E4E9" }}>
                  {result!.project_id}
                </h2>
                <p className="text-[12px] mt-0.5 m-0" style={{ color: "#545870" }}>
                  Proiect finalizat · Zona climatică {result!.climate_zone}
                </p>
              </div>
              <button onClick={exportJSON}
                className="px-4 py-2 rounded-lg text-[13px] font-semibold font-[inherit] cursor-pointer transition-colors duration-150"
                style={{
                  background: "rgba(255,255,255,0.04)",
                  border: "1px solid rgba(255,255,255,0.08)",
                  color: "#8B8FA8",
                }}
                onMouseOver={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.08)")}
                onMouseOut={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.04)")}>
                Export JSON
              </button>
            </div>

            {/* Metric cards */}
            <div className="grid gap-3 mb-5"
              style={{ gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))" }}>
              {result!.heating_circuits?.pdc && (
                <>
                  <MetricCard
                    value={`${result!.heating_circuits.pdc.power_kw_thermal} kW`}
                    label="Putere termică PDC" color="#EF9F27" />
                  <MetricCard
                    value={`${result!.heating_circuits.pdc.breaker_a}A`}
                    label="Protecție PDC" color="#5BB8F5" />
                </>
              )}
              <MetricCard
                value={result!.circuits_all?.length || 0}
                label="Circuite totale" color="#3ECFA0" />
              <MetricCard
                value={result!.rooms?.length || 0}
                label="Camere" color="#ED93B1" />
            </div>

            <CircuitTable circuits={result!.circuits_te_ct} title="TE-CT — Cameră tehnică" />
            <CircuitTable circuits={result!.circuits_teg} title="TEG — Tablou general" />
            <RoomsList rooms={result!.rooms} />
            <MemoriuSection text={result!.memoriu_tehnic} />
          </div>
        ) : (
          /* Empty state */
          <div className="flex flex-col items-center justify-center text-center"
            style={{ minHeight: 440, padding: "0 40px" }}>
            <div className="mb-5 rounded-2xl flex items-center justify-center"
              style={{
                width: 72, height: 72,
                background: "rgba(55,138,221,0.07)",
                border: "1px solid rgba(55,138,221,0.12)",
              }}>
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" style={{ opacity: 0.5 }}>
                <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" stroke="#378ADD" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <h3 className="text-[17px] font-semibold m-0 mb-2" style={{ color: "#545870" }}>
              Proiectare electrică automată
            </h3>
            <p className="text-sm m-0 leading-relaxed" style={{ color: "#3A3D50", maxWidth: 340 }}>
              Încarcă planșele arhitecturale, completează formularul și primești proiectul electric complet în sub 30 de secunde.
            </p>
            <div className="mt-8 flex gap-6 text-[11px]" style={{ color: "#3A3D50" }}>
              {["Analiză Claude Vision", "Calcul circuite FastAPI", "Memoriu tehnic automat"].map(s => (
                <span key={s} className="flex items-center gap-1.5">
                  <span style={{ color: "#545870" }}>—</span> {s}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
