"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import Link from "next/link";
import {
  BUILDING_CATEGORIES_3, BUILDING_SUBTYPES,
  INSULATION, HEATING_GENERATION, HEATING_DISTRIBUTION,
  EXTRA_EQUIPMENT_DEFAULTS,
  INITIAL_FORM, type FormData, type ProjectResult, type Motor, type ExtraEquipment,
} from "@/lib/constants";
import { useAuth } from "@/components/auth-provider";
import { createClient } from "@/lib/supabase";
import {
  MetricCard, CircuitTable, RoomsList, MemoriuSection,
  SchemasSection, SchemaDownloadButton, AnnotatedPlanSection, ProjectInfoCard,
} from "@/components/result-sections";

const WEBHOOK_URL = "/api/generate";

const PROGRESS_STEPS = [
  "Se encodează planșele...",
  "Se trimite la n8n...",
  "Claude Vision analizează planșa...",
  "Se calculează circuitele electrice...",
  "Se generează schema monofilară...",
  "Se salvează proiectul...",
];

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve((reader.result as string).split(",")[1]);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
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
      <span className="text-[11px] font-semibold tracking-widest uppercase" style={{ color: "#545870" }}>{children}</span>
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
      <label className="block text-[12px] font-semibold tracking-wide mb-1.5" style={{ color: "#8B8FA8" }}>
        {label}{required && <span style={{ color: "#E24B4A" }}> *</span>}
      </label>
      <div className="relative">
        <select value={value} onChange={(e) => onChange(e.target.value)}
          className="w-full px-3.5 py-2.5 rounded-lg text-sm outline-none font-[inherit] pr-9"
          style={{
            background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)",
            color: value ? "#E2E4E9" : "#545870", transition: "border-color 0.15s",
          }}>
          <option value="">— Alege —</option>
          {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[10px]" style={{ color: "#545870" }}>▾</span>
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
      <label className="block text-[12px] font-semibold tracking-wide mb-1.5" style={{ color: "#8B8FA8" }}>
        {label}{required && <span style={{ color: "#E24B4A" }}> *</span>}
      </label>
      <input type="text" value={value} onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-3.5 py-2.5 rounded-lg text-sm outline-none font-[inherit]"
        style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", color: "#E2E4E9" }} />
    </div>
  );
}

function Toggle({ label, checked, onChange, description }: {
  label: string; checked: boolean; onChange: (v: boolean) => void; description?: string;
}) {
  return (
    <label className="flex items-center gap-3 mb-3 cursor-pointer select-none">
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
                style={{ background: "none", border: "none", color: "#545870", cursor: "pointer", padding: 0 }}
                className="ml-0.5 text-base leading-none"
                onMouseOver={(e) => (e.currentTarget.style.color = "#E2E4E9")}
                onMouseOut={(e) => (e.currentTarget.style.color = "#545870")}>×</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ─── Building category cards (PAS 1) ─── */
function CategoryCards({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div className="grid grid-cols-3 gap-2 mb-3">
      {BUILDING_CATEGORIES_3.map(c => {
        const selected = value === c.value;
        return (
          <button key={c.value} type="button" onClick={() => onChange(c.value)}
            className="rounded-xl p-3 text-center cursor-pointer transition-all duration-150 font-[inherit]"
            style={{
              background: selected ? "rgba(55,138,221,0.08)" : "rgba(255,255,255,0.02)",
              border: selected ? "1.5px solid rgba(55,138,221,0.5)" : "1px solid rgba(255,255,255,0.07)",
              outline: "none",
            }}>
            <div style={{ fontSize: 22, marginBottom: 4 }}>{c.icon}</div>
            <div className="text-[12px] font-bold" style={{ color: selected ? "#5BB8F5" : "#C8CAD6" }}>{c.label}</div>
            <div className="text-[10px] mt-1 leading-tight" style={{ color: "#545870" }}>{c.desc}</div>
          </button>
        );
      })}
    </div>
  );
}

/* ─── Building subtype list (PAS 2) ─── */
function SubtypeList({ category, value, onChange }: { category: string; value: string; onChange: (v: string) => void }) {
  const subtypes = BUILDING_SUBTYPES[category] || [];
  if (!subtypes.length) return null;
  return (
    <div className="mb-3.5">
      <label className="block text-[12px] font-semibold tracking-wide mb-1.5" style={{ color: "#8B8FA8" }}>
        SUBTIP CLĂDIRE <span style={{ color: "#E24B4A" }}>*</span>
      </label>
      <div className="flex flex-col gap-1">
        {subtypes.map(s => {
          const sel = value === s.value;
          return (
            <button key={s.value} type="button" onClick={() => onChange(s.value)}
              className="text-left px-3 py-2 rounded-lg text-sm cursor-pointer transition-all duration-100 font-[inherit]"
              style={{
                background: sel ? "rgba(55,138,221,0.1)" : "rgba(255,255,255,0.02)",
                border: sel ? "1px solid rgba(55,138,221,0.35)" : "1px solid rgba(255,255,255,0.06)",
                color: sel ? "#5BB8F5" : "#C8CAD6",
              }}>
              {s.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/* ─── Height regime selector ─── */
function HeightRegimeSelector({ hasBasement, setHasBasement, floors, setFloors, hasAttic, setHasAttic }: {
  hasBasement: boolean; setHasBasement: (v: boolean) => void;
  floors: number; setFloors: (v: number) => void;
  hasAttic: boolean; setHasAttic: (v: boolean) => void;
}) {
  const levelsStr = (hasBasement ? "D+" : "") + "P" + (floors > 0 ? "+" + floors : "") + (hasAttic && floors <= 2 ? "+M" : "");
  return (
    <div className="mb-3.5">
      <label className="block text-[12px] font-semibold tracking-wide mb-2" style={{ color: "#8B8FA8" }}>
        REGIM ÎNĂLȚIME
      </label>
      <Toggle label="Subsol?" checked={hasBasement} onChange={setHasBasement} />
      <div className="mb-2.5">
        <div className="text-[11px] mb-1.5" style={{ color: "#545870" }}>Etaje deasupra parterului</div>
        <div className="flex gap-1.5">
          {[0, 1, 2, 3, 4, 5].map(n => (
            <button key={n} type="button" onClick={() => setFloors(n)}
              className="w-9 h-9 rounded-lg text-[13px] font-semibold cursor-pointer font-[inherit] transition-all duration-100"
              style={{
                background: floors === n ? "rgba(55,138,221,0.15)" : "rgba(255,255,255,0.03)",
                border: floors === n ? "1.5px solid #378ADD" : "1px solid rgba(255,255,255,0.08)",
                color: floors === n ? "#5BB8F5" : "#8B8FA8",
              }}>
              {n === 5 ? "5+" : n}
            </button>
          ))}
        </div>
      </div>
      {floors <= 2 && (
        <Toggle label="Mansardă?" checked={hasAttic} onChange={setHasAttic} />
      )}
      <div className="px-3 py-2 rounded-lg mt-1" style={{ background: "rgba(55,138,221,0.05)", border: "1px solid rgba(55,138,221,0.15)" }}>
        <span className="text-[11px]" style={{ color: "#545870" }}>Regim: </span>
        <span className="text-sm font-bold" style={{ color: "#5BB8F5" }}>{levelsStr || "P"}</span>
        <span className="text-[11px] ml-2" style={{ color: "#3A3D50" }}>— se va valida din planșă</span>
      </div>
    </div>
  );
}

/* ─── Power phase selector ─── */
function PowerPhaseSelector({ value, onChange, suggestTri }: {
  value: string; onChange: (v: string) => void; suggestTri?: boolean;
}) {
  const opts = [
    { v: "mono", icon: "⚡", title: "MONOFAZAT", sub: "230V — case mici, apartamente" },
    { v: "tri",  icon: "⚡⚡⚡", title: "TRIFAZAT",  sub: "400V — case mari, hale, blocuri" },
  ];
  return (
    <div className="grid grid-cols-2 gap-2 mb-3.5">
      {opts.map(o => {
        const sel = value === o.v;
        return (
          <button key={o.v} type="button" onClick={() => onChange(o.v)}
            className="rounded-xl p-3 text-center cursor-pointer transition-all duration-150 font-[inherit]"
            style={{
              background: sel ? "rgba(55,138,221,0.08)" : "rgba(255,255,255,0.02)",
              border: sel ? "1.5px solid rgba(55,138,221,0.5)" : "1px solid rgba(255,255,255,0.07)",
            }}>
            <div className="text-lg mb-1">{o.icon}</div>
            <div className="text-[12px] font-bold" style={{ color: sel ? "#5BB8F5" : "#C8CAD6" }}>{o.title}</div>
            <div className="text-[10px] mt-0.5" style={{ color: "#545870" }}>{o.sub}</div>
            {o.v === "tri" && suggestTri && (
              <div className="text-[10px] mt-1 font-semibold" style={{ color: "#3ECFA0" }}>💡 Recomandat</div>
            )}
          </button>
        );
      })}
    </div>
  );
}

/* ─── Equipment toggle cards ─── */
interface EquipState { enabled: boolean; power_kw: number; phase: string; }

function EquipmentCards({
  equipment, setEquipment, customEquipment, setCustomEquipment,
}: {
  equipment: Record<string, EquipState>;
  setEquipment: React.Dispatch<React.SetStateAction<Record<string, EquipState>>>;
  customEquipment: { name: string; power_kw: number; phase: string }[];
  setCustomEquipment: React.Dispatch<React.SetStateAction<{ name: string; power_kw: number; phase: string }[]>>;
}) {
  const inputStyle = {
    background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)",
    color: "#E2E4E9", borderRadius: 8, fontSize: 13, outline: "none", fontFamily: "inherit",
  };
  return (
    <div className="flex flex-col gap-2">
      {EXTRA_EQUIPMENT_DEFAULTS.map(eq => {
        const st = equipment[eq.type];
        return (
          <div key={eq.type}
            className="rounded-xl transition-all duration-150 overflow-hidden"
            style={{
              background: st.enabled ? "rgba(55,138,221,0.06)" : "rgba(255,255,255,0.02)",
              border: st.enabled ? "1.5px solid rgba(55,138,221,0.3)" : "1px solid rgba(255,255,255,0.07)",
            }}>
            <div className="flex items-center gap-2.5 px-3 py-2.5 cursor-pointer select-none"
              onClick={() => setEquipment(prev => ({ ...prev, [eq.type]: { ...prev[eq.type], enabled: !prev[eq.type].enabled } }))}>
              <span className="text-base shrink-0">{eq.icon}</span>
              <span className="text-[13px] flex-1" style={{ color: st.enabled ? "#C8CAD6" : "#8B8FA8" }}>{eq.label}</span>
              <div className="relative shrink-0 w-8 h-4.5 rounded-full transition-all duration-200"
                style={{ background: st.enabled ? "#378ADD" : "rgba(255,255,255,0.1)", width: 32, height: 18 }}>
                <div className="absolute top-0.5 w-3.5 h-3.5 rounded-full bg-white transition-all duration-200"
                  style={{ left: st.enabled ? 14 : 2, width: 14, height: 14 }} />
              </div>
            </div>
            {st.enabled && eq.default_kw > 0 && (
              <div className="px-3 pb-3 grid grid-cols-2 gap-2" onClick={e => e.stopPropagation()}>
                <div>
                  <label className="block text-[11px] font-semibold mb-1" style={{ color: "#545870" }}>PUTERE (kW)</label>
                  <input type="number" min={0.1} step={0.1} value={st.power_kw || ""}
                    onChange={e => setEquipment(prev => ({ ...prev, [eq.type]: { ...prev[eq.type], power_kw: parseFloat(e.target.value) || 0 } }))}
                    className="w-full px-2.5 py-2" style={inputStyle} />
                </div>
                <div>
                  <label className="block text-[11px] font-semibold mb-1" style={{ color: "#545870" }}>ALIMENTARE</label>
                  <select value={st.phase}
                    onChange={e => setEquipment(prev => ({ ...prev, [eq.type]: { ...prev[eq.type], phase: e.target.value } }))}
                    className="w-full px-2.5 py-2" style={{ ...inputStyle, paddingRight: 8 }}>
                    <option value="mono">Monofazat 230V</option>
                    <option value="tri">Trifazat 400V</option>
                    <option value="none">Fără circuit dedicat</option>
                  </select>
                </div>
              </div>
            )}
          </div>
        );
      })}

      {customEquipment.map((eq, i) => (
        <div key={i} className="rounded-xl p-3" style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.07)" }}>
          <div className="flex gap-2 mb-2">
            <input type="text" placeholder="Denumire echipament" value={eq.name}
              onChange={e => setCustomEquipment(prev => prev.map((x, j) => j === i ? { ...x, name: e.target.value } : x))}
              className="flex-1 px-2.5 py-2 rounded-lg text-[13px] outline-none font-[inherit]"
              style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", color: "#E2E4E9" }} />
            <button type="button"
              onClick={() => setCustomEquipment(prev => prev.filter((_, j) => j !== i))}
              className="px-2.5 py-2 rounded-lg text-base leading-none cursor-pointer font-[inherit]"
              style={{ background: "rgba(226,75,74,0.1)", border: "1px solid rgba(226,75,74,0.15)", color: "#F09595" }}>
              ×
            </button>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-[11px] font-semibold mb-1" style={{ color: "#545870" }}>PUTERE (kW)</label>
              <input type="number" min={0} step={0.1} value={eq.power_kw || ""}
                onChange={e => setCustomEquipment(prev => prev.map((x, j) => j === i ? { ...x, power_kw: parseFloat(e.target.value) || 0 } : x))}
                className="w-full px-2.5 py-2 rounded-lg text-[13px] outline-none font-[inherit]"
                style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", color: "#E2E4E9" }} />
            </div>
            <div>
              <label className="block text-[11px] font-semibold mb-1" style={{ color: "#545870" }}>ALIMENTARE</label>
              <select value={eq.phase}
                onChange={e => setCustomEquipment(prev => prev.map((x, j) => j === i ? { ...x, phase: e.target.value } : x))}
                className="w-full px-2.5 py-2 rounded-lg text-[13px] outline-none font-[inherit]"
                style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", color: "#E2E4E9" }}>
                <option value="mono">Monofazat 230V</option>
                <option value="tri">Trifazat 400V</option>
              </select>
            </div>
          </div>
        </div>
      ))}

      <button type="button"
        onClick={() => setCustomEquipment(prev => [...prev, { name: "", power_kw: 0, phase: "mono" }])}
        className="text-[12px] font-semibold px-3 py-2 rounded-lg cursor-pointer font-[inherit] text-left"
        style={{ background: "rgba(255,255,255,0.03)", border: "1px dashed rgba(255,255,255,0.1)", color: "#545870" }}>
        ➕ Adaugă echipament custom
      </button>
    </div>
  );
}

/* ─── Main configurator ─── */
export function ZynapseConfigurator() {
  const { user, profile, signOut, refreshProfile } = useAuth();
  const [files, setFiles] = useState<File[]>([]);
  const [form, setForm] = useState<FormData>(INITIAL_FORM);
  const [status, setStatus] = useState("idle");
  const [result, setResult] = useState<ProjectResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stepIndex, setStepIndex] = useState(0);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [motors, setMotors] = useState<Motor[]>([]);

  // Height regime (manual controls)
  const [manualFloors, setManualFloors] = useState(0);

  // Extra equipment state
  const [equipment, setEquipment] = useState<Record<string, EquipState>>(
    Object.fromEntries(EXTRA_EQUIPMENT_DEFAULTS.map(e => [e.type, { enabled: false, power_kw: e.default_kw, phase: e.default_phase }]))
  );
  const [customEquipment, setCustomEquipment] = useState<{ name: string; power_kw: number; phase: string }[]>([]);

  // Auto-detect badge (populated from response)
  const [autoDetected, setAutoDetected] = useState<{ climate_zone: string; climate_source?: string; levels_string?: string } | null>(null);

  const update = (key: keyof FormData, val: string | boolean | number) =>
    setForm(prev => ({ ...prev, [key]: val }));

  const projectsUsed = profile?.projects_used ?? 0;
  const projectsLimit = profile?.projects_limit ?? 3;
  const isAtLimit = projectsUsed >= projectsLimit;

  // Computed levels string from manual controls
  const levelsString = (form.has_basement ? "D+" : "") + "P" +
    (manualFloors > 0 ? "+" + manualFloors : "") +
    (form.has_attic && manualFloors <= 2 ? "+M" : "");

  // Suggest trifazat for bloc/industrial
  const suggestTri = ["bloc_locuinte", "hala_productie", "statie_tehnologica", "hotel_pensiune", "ferma"].includes(form.building_type);

  const isPDC = form.heating_type?.startsWith("pdc");

  const formReady = !!(
    form.project_id &&
    form.building_category &&
    form.building_type &&
    form.insulation_level &&
    form.heating_type &&
    files.length > 0
  );
  const canSubmit = formReady && !isAtLimit;

  useEffect(() => {
    if (!saveMessage) return;
    const t = setTimeout(() => setSaveMessage(null), 4000);
    return () => clearTimeout(t);
  }, [saveMessage]);

  // Reset subtype when category changes
  const handleCategoryChange = (v: string) => {
    update("building_category", v);
    update("building_type", "");
  };

  const handleSubmit = async () => {
    if (!canSubmit || status === "loading") return;
    setStatus("loading"); setError(null); setResult(null); setStepIndex(0);

    try {
      setStepIndex(0);
      const base64 = await fileToBase64(files[0]);

      setStepIndex(1);
      const extra_equipment: ExtraEquipment[] = [
        ...EXTRA_EQUIPMENT_DEFAULTS
          .filter(e => equipment[e.type]?.enabled)
          .map(e => ({
            type: e.type,
            name: e.label,
            power_kw: equipment[e.type].power_kw,
            phase: equipment[e.type].phase,
          })),
        ...customEquipment
          .filter(e => e.name.trim())
          .map(e => ({ type: "custom", ...e })),
      ];

      const payload: Record<string, unknown> = {
        plan_base64: base64,
        plan_type: files[0].type || "image/jpeg",
        user_id: user?.id || "",
        user_email: user?.email || "",
        ...form,
        // Climate — use Vision-detected values from previous run, or defaults
        climate_zone: autoDetected?.climate_zone || "II",
        climate_auto_detected: !!autoDetected?.climate_zone,
        climate_source: autoDetected?.climate_source || null,
        // Height regime
        levels_string: levelsString,
        levels_auto_detected: !!autoDetected?.levels_string,
        floors_above_ground: manualFloors,
        power_phase: form.power_phase,
        heating_type: form.heating_type,
        heating_distribution: form.heating_distribution,
        extra_equipment,
        ...(form.building_type === "bloc_locuinte" && form.floors ? { floors: parseInt(form.floors) } : {}),
        ...(form.building_type === "bloc_locuinte" && form.apartments_per_floor ? { apartments_per_floor: parseInt(form.apartments_per_floor) } : {}),
        ...(form.building_category === "industrial" && motors.length > 0 ? { motors } : {}),
      };

      setStepIndex(2);
      const res = await fetch(WEBHOOK_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      setStepIndex(3);
      const data: ProjectResult = await res.json();
      if ((data as any).status === "error") throw new Error((data as any).error || "Eroare necunoscută");

      // Extract auto-detected values
      if (data.climate_zone || data.levels_string) {
        setAutoDetected({
          climate_zone: data.climate_zone,
          climate_source: data.climate_source,
          levels_string: data.levels_string,
        });
      }

      setStepIndex(4);
      if (user) {
        const supabase = createClient();
        await supabase.from("projects").insert({
          user_id: user.id,
          project_id: form.project_id,
          building_type: form.building_type,
          levels: levelsString,
          climate_zone: data.climate_zone || "II",
          insulation_level: form.insulation_level,
          heating_type: form.heating_type,
          status: "completed",
          input_data: payload,
          result_data: data,
          memoriu_text: data.memoriu_tehnic,
        });
        await supabase
          .from("profiles")
          .update({ projects_used: projectsUsed + 1 })
          .eq("id", user.id);
        await refreshProfile();
        setSaveMessage("Proiect salvat cu succes");
      }

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

  const handleDownloadPDF = async () => {
    if (!result || pdfLoading) return;
    setPdfLoading(true);
    try {
      const { downloadProjectPDF } = await import("@/components/pdf-export");
      await downloadProjectPDF(result);
    } catch (e) {
      console.error("PDF generation failed:", e);
    } finally {
      setPdfLoading(false);
    }
  };

  const downloadPDF = (base64Data: string, filename: string) => {
    const base64 = base64Data.includes(",") ? base64Data.split(",")[1] : base64Data;
    const byteChars = atob(base64);
    const bytes = new Uint8Array(byteChars.length);
    for (let i = 0; i < byteChars.length; i++) bytes[i] = byteChars.charCodeAt(i);
    const blob = new Blob([bytes], { type: "application/pdf" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click();
    document.body.removeChild(a); URL.revokeObjectURL(url);
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
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-3">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/logo-icon.png" alt="Zynapse" width={30} height={30} style={{
              objectFit: "contain", filter: "brightness(2.2) drop-shadow(0 0 4px rgba(55,138,221,0.3))",
            }} />
            <span className="text-[17px] font-bold tracking-tight" style={{ color: "#E2E4E9" }}>Zynapse</span>
            <span className="text-[10px] font-bold tracking-widest uppercase px-2 py-1 rounded-md"
              style={{ background: "rgba(55,138,221,0.12)", color: "#5BB8F5", border: "1px solid rgba(55,138,221,0.2)" }}>
              Beta
            </span>
          </div>
          <div style={{ width: 1, height: 20, background: "rgba(255,255,255,0.08)" }} />
          <Link href="/projects"
            className="text-sm font-medium transition-colors duration-150"
            style={{ color: "#8B8FA8", textDecoration: "none" }}
            onMouseOver={(e) => (e.currentTarget.style.color = "#E2E4E9")}
            onMouseOut={(e) => (e.currentTarget.style.color = "#8B8FA8")}>
            Proiectele mele
          </Link>
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
                style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", color: "#8B8FA8" }}
                onMouseOver={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.09)")}
                onMouseOut={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.05)")}>
                Deconectare
              </button>
            </>
          )}
        </div>
      </header>

      {/* ── Layout ── */}
      <div className="p-8" style={{ maxWidth: 1280, margin: "0 auto", display: "grid", gridTemplateColumns: "420px 1fr", gap: 24, alignItems: "start" }}>

        {/* ── Form panel ── */}
        <div className="rounded-2xl p-6 sticky top-[73px]"
          style={{ background: "rgba(255,255,255,0.025)", border: "1px solid rgba(255,255,255,0.07)", maxHeight: "calc(100vh - 97px)", overflowY: "auto" }}>

          <div className="mb-5">
            <h1 className="text-lg font-bold tracking-tight m-0" style={{ color: "#E2E4E9" }}>Configurator proiect</h1>
            <p className="text-[13px] mt-1 m-0" style={{ color: "#545870" }}>Încarcă planșele și completează datele clădirii</p>
          </div>

          {isAtLimit && (
            <div className="mb-4 p-4 rounded-xl"
              style={{ background: "rgba(226,75,74,0.08)", border: "1px solid rgba(226,75,74,0.2)" }}>
              <div className="text-sm font-semibold mb-1" style={{ color: "#F09595" }}>
                Limită atinsă — {projectsUsed}/{projectsLimit} proiecte
              </div>
              <div className="text-[12px]" style={{ color: "#8B6060" }}>
                <a href="mailto:contact@zynapse.org" style={{ color: "#F09595", textDecoration: "underline" }}>
                  Contactează-ne pentru upgrade
                </a>
              </div>
            </div>
          )}

          {!isAtLimit && profile && (
            <div className="mb-4 flex items-center justify-between text-[11px]" style={{ color: "#545870" }}>
              <span>Proiecte folosite</span>
              <span style={{ color: "#8B8FA8" }}>{projectsUsed} / {projectsLimit}</span>
            </div>
          )}

          {/* 1. Upload */}
          <DropZone files={files} setFiles={setFiles} />

          {/* Auto-detect badge (shows after successful result) */}
          {autoDetected && (
            <div className="mb-4 px-3 py-2 rounded-lg text-[12px] flex items-center gap-2"
              style={{ background: "rgba(29,158,117,0.08)", border: "1px solid rgba(29,158,117,0.2)", color: "#3ECFA0" }}>
              {autoDetected.climate_source && <span>📍 Zona {autoDetected.climate_zone} ({autoDetected.climate_source})</span>}
              {autoDetected.levels_string && <span>· 📐 {autoDetected.levels_string}</span>}
              <span style={{ color: "#1D9E75" }}>— detectate automat din planșă</span>
            </div>
          )}

          <div style={{ height: 1, background: "rgba(255,255,255,0.05)", margin: "0 0 16px" }} />

          {/* 2. Numele proiectului */}
          <SectionLabel>Identificare proiect</SectionLabel>
          <TextField label="Numele proiectului" value={form.project_id}
            onChange={v => update("project_id", v)} placeholder="ex: Casa Popescu P+M 160mp" required />

          {/* 3. Tip clădire PAS1 + PAS2 */}
          <SectionLabel>Tip clădire</SectionLabel>
          <CategoryCards value={form.building_category} onChange={handleCategoryChange} />
          {form.building_category && (
            <SubtypeList category={form.building_category} value={form.building_type}
              onChange={v => update("building_type", v)} />
          )}

          {/* 4. Regim înălțime */}
          <SectionLabel>Regim înălțime</SectionLabel>
          <HeightRegimeSelector
            hasBasement={form.has_basement} setHasBasement={v => update("has_basement", v)}
            floors={manualFloors} setFloors={setManualFloors}
            hasAttic={form.has_attic} setHasAttic={v => update("has_attic", v)} />

          {/* 5. Alimentare electrică */}
          <SectionLabel>Alimentare electrică</SectionLabel>
          <PowerPhaseSelector value={form.power_phase} onChange={v => update("power_phase", v)} suggestTri={suggestTri} />

          {/* 6. Nivel izolație */}
          <SectionLabel>Izolație termică</SectionLabel>
          <SelectField label="Nivel izolație" value={form.insulation_level}
            onChange={v => update("insulation_level", v)} options={INSULATION} required />

          {/* 7. Sistem termoenergetic */}
          <SectionLabel>Sistem termoenergetic</SectionLabel>
          <SelectField label="Tip generare căldură" value={form.heating_type}
            onChange={v => update("heating_type", v)} options={HEATING_GENERATION} required />
          {form.heating_type && form.heating_type !== "existing" && (
            <SelectField label="Tip distribuție căldură" value={form.heating_distribution}
              onChange={v => update("heating_distribution", v)} options={HEATING_DISTRIBUTION} />
          )}
          {isPDC && (
            <SelectField label="Fază PDC" value={form.power_phase}
              onChange={v => update("power_phase", v)}
              options={[{ value: "mono", label: "Monofazat 1F" }, { value: "tri", label: "Trifazat 3F" }]} />
          )}

          {/* 8. Opțiuni suplimentare */}
          <SectionLabel>Opțiuni suplimentare</SectionLabel>
          <EquipmentCards
            equipment={equipment} setEquipment={setEquipment}
            customEquipment={customEquipment} setCustomEquipment={setCustomEquipment} />

          {/* Câmpuri specifice bloc */}
          {form.building_type === "bloc_locuinte" && (
            <>
              <SectionLabel>Detalii bloc</SectionLabel>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                <div className="mb-3.5">
                  <label className="block text-[12px] font-semibold tracking-wide mb-1.5" style={{ color: "#8B8FA8" }}>NR. ETAJE</label>
                  <input type="number" min={1} max={30} value={form.floors}
                    onChange={e => update("floors", e.target.value)}
                    placeholder="ex: 4"
                    className="w-full px-3.5 py-2.5 rounded-lg text-sm outline-none font-[inherit]"
                    style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", color: "#E2E4E9" }} />
                </div>
                <div className="mb-3.5">
                  <label className="block text-[12px] font-semibold tracking-wide mb-1.5" style={{ color: "#8B8FA8" }}>APARTAMENTE/ETAJ</label>
                  <input type="number" min={1} max={20} value={form.apartments_per_floor}
                    onChange={e => update("apartments_per_floor", e.target.value)}
                    placeholder="ex: 4"
                    className="w-full px-3.5 py-2.5 rounded-lg text-sm outline-none font-[inherit]"
                    style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", color: "#E2E4E9" }} />
                </div>
              </div>
              <Toggle label="Are lift" checked={form.has_elevator} onChange={v => update("has_elevator", v)} />
              <Toggle label="Pompă incendiu" checked={form.has_fire_pump} onChange={v => update("has_fire_pump", v)}
                description="Circuit prioritar trifazat dedicat" />
            </>
          )}

          {/* Câmpuri specifice industrial */}
          {form.building_category === "industrial" && (
            <>
              <SectionLabel>Detalii hală</SectionLabel>
              <SelectField label="Grad protecție (IP)" value={form.ip_zone}
                onChange={v => update("ip_zone", v)}
                options={[{ value: "IP44", label: "IP44" }, { value: "IP65", label: "IP65" }, { value: "IP67", label: "IP67" }]} />
              <Toggle label="Aer comprimat" checked={form.has_compressed_air}
                onChange={v => update("has_compressed_air", v)} description="Circuit trifazat 32A dedicat" />
              <Toggle label="Pod rulant (macara)" checked={form.has_overhead_crane}
                onChange={v => update("has_overhead_crane", v)} description="Circuit trifazat 63A dedicat" />
              <div className="mt-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-[11px] font-semibold tracking-widest uppercase" style={{ color: "#545870" }}>Motoare electrice</span>
                  <button type="button"
                    onClick={() => setMotors(prev => [...prev, { name: "", power_kw: 0, phase: "tri", count: 1 }])}
                    className="text-[12px] font-semibold px-3 py-1.5 rounded-lg font-[inherit] cursor-pointer"
                    style={{ background: "rgba(55,138,221,0.12)", border: "1px solid rgba(55,138,221,0.25)", color: "#5BB8F5" }}>
                    + Adaugă motor
                  </button>
                </div>
                {motors.map((m, i) => (
                  <div key={i} className="mb-3 p-3 rounded-xl" style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)" }}>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 8, marginBottom: 8 }}>
                      <input type="text" placeholder="Nume motor" value={m.name}
                        onChange={e => setMotors(prev => prev.map((x, j) => j === i ? { ...x, name: e.target.value } : x))}
                        className="w-full px-3 py-2 rounded-lg text-sm outline-none font-[inherit]"
                        style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", color: "#E2E4E9" }} />
                      <button type="button" onClick={() => setMotors(prev => prev.filter((_, j) => j !== i))}
                        className="px-2.5 py-2 rounded-lg cursor-pointer font-[inherit]"
                        style={{ background: "rgba(226,75,74,0.1)", border: "1px solid rgba(226,75,74,0.15)", color: "#F09595", fontSize: 16 }}>
                        ×
                      </button>
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
                      <div>
                        <label className="block text-[11px] font-semibold mb-1" style={{ color: "#545870" }}>kW</label>
                        <input type="number" min={0.1} step={0.1} value={m.power_kw || ""}
                          onChange={e => setMotors(prev => prev.map((x, j) => j === i ? { ...x, power_kw: parseFloat(e.target.value) || 0 } : x))}
                          className="w-full px-2.5 py-2 rounded-lg text-sm outline-none font-[inherit]"
                          style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", color: "#E2E4E9" }} />
                      </div>
                      <div>
                        <label className="block text-[11px] font-semibold mb-1" style={{ color: "#545870" }}>FAZE</label>
                        <select value={m.phase}
                          onChange={e => setMotors(prev => prev.map((x, j) => j === i ? { ...x, phase: e.target.value } : x))}
                          className="w-full px-2.5 py-2 rounded-lg text-sm outline-none font-[inherit]"
                          style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", color: "#E2E4E9" }}>
                          <option value="tri">3F</option>
                          <option value="mono">1F</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-[11px] font-semibold mb-1" style={{ color: "#545870" }}>BUC</label>
                        <input type="number" min={1} max={20} value={m.count}
                          onChange={e => setMotors(prev => prev.map((x, j) => j === i ? { ...x, count: parseInt(e.target.value) || 1 } : x))}
                          className="w-full px-2.5 py-2 rounded-lg text-sm outline-none font-[inherit]"
                          style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", color: "#E2E4E9" }} />
                      </div>
                    </div>
                  </div>
                ))}
                {motors.length === 0 && (
                  <p className="text-[12px]" style={{ color: "#3A3D50" }}>Niciun motor adăugat — opțional</p>
                )}
              </div>
            </>
          )}

          {/* 9. Observații */}
          <SectionLabel>Note suplimentare</SectionLabel>
          <textarea value={form.notes} onChange={(e) => update("notes", e.target.value)}
            placeholder="Garaj încălzit, anexe, specificații speciale..." rows={3}
            className="w-full px-3.5 py-2.5 rounded-lg text-sm font-[inherit] outline-none"
            style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", color: "#E2E4E9", resize: "vertical" }} />

          {/* 10. Submit */}
          <button onClick={handleSubmit} disabled={!canSubmit || isLoading}
            className="w-full mt-5 py-3.5 px-6 rounded-xl text-[14px] font-semibold font-[inherit] tracking-wide transition-all duration-200"
            style={{
              background: canSubmit && !isLoading ? "linear-gradient(135deg, #378ADD 0%, #1D9E75 100%)" : "rgba(255,255,255,0.05)",
              border: "none",
              color: canSubmit ? "#fff" : "#545870",
              cursor: canSubmit && !isLoading ? "pointer" : "not-allowed",
              opacity: isLoading ? 0.75 : 1,
              boxShadow: canSubmit && !isLoading ? "0 0 24px rgba(55,138,221,0.25)" : "none",
            }}>
            {isLoading ? "Se procesează..." : "Generează proiect electric"}
          </button>

          {isLoading && (
            <div className="mt-3">
              <div className="h-0.5 rounded-full mb-2 overflow-hidden" style={{ background: "rgba(255,255,255,0.07)" }}>
                <div className="h-full rounded-full transition-all duration-700"
                  style={{ width: `${((stepIndex + 1) / PROGRESS_STEPS.length) * 100}%`, background: "linear-gradient(90deg, #378ADD, #1D9E75)" }} />
              </div>
              <div className="text-center text-[12px]" style={{ color: "#5BB8F5", animation: "zy-pulse 1.6s ease-in-out infinite" }}>
                {PROGRESS_STEPS[stepIndex] || PROGRESS_STEPS[0]}
              </div>
            </div>
          )}

          {saveMessage && (
            <div className="mt-3 p-3 rounded-lg text-sm text-center"
              style={{ background: "rgba(29,158,117,0.12)", border: "1px solid rgba(29,158,117,0.25)", color: "#3ECFA0" }}>
              {saveMessage}
            </div>
          )}

          {error && (
            <div className="mt-3 p-3.5 rounded-lg text-sm"
              style={{ background: "rgba(226,75,74,0.1)", border: "1px solid rgba(226,75,74,0.2)", color: "#F09595" }}>
              {error}
            </div>
          )}
        </div>

        {/* ── Results / Empty state ── */}
        {hasResult ? (
          <div className="zy-slide-in">

            {/* Header */}
            <div className="flex justify-between items-center mb-5">
              <div>
                <h2 className="text-lg font-bold tracking-tight m-0" style={{ color: "#E2E4E9" }}>
                  {result!.project_info?.titlu_proiect || result!.project_name || result!.project_id}
                </h2>
                <p className="text-[12px] mt-0.5 m-0" style={{ color: "#545870" }}>
                  {result!.project_info?.beneficiar || result!.beneficiary || ""}
                  {(result!.climate_zone) && ` · Zona climatică ${result!.climate_zone}`}
                  {result!.levels_string && ` · ${result!.levels_string}`}
                  {result!.output_phase && ` · ${result!.output_phase}`}
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

            {/* Metric cards — use power_summary (n8n) with fallback to heating_circuits (FastAPI) */}
            <div className="grid gap-3 mb-5" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))" }}>
              {result!.power_summary?.installed_kw != null && (
                <MetricCard value={`${result!.power_summary.installed_kw} kW`} label="Putere instalată" color="#EF9F27" />
              )}
              {result!.power_summary?.absorbed_kw != null && (
                <MetricCard value={`${result!.power_summary.absorbed_kw} kW`} label="Putere absorbită" color="#5BB8F5" />
              )}
              {result!.heating_circuits?.pdc && (
                <MetricCard value={`${result!.heating_circuits.pdc.power_kw_thermal} kW`} label="Putere termică PDC" color="#EF9F27" />
              )}
              <MetricCard
                value={(result!.circuits?.length || result!.circuits_all?.length || 0)}
                label="Circuite totale" color="#3ECFA0"
              />
              {result!.rooms?.length != null && result!.rooms.length > 0 && (
                <MetricCard value={result!.rooms.length} label="Camere" color="#ED93B1" />
              )}
            </div>

            {result!.project_info && <ProjectInfoCard info={result!.project_info} />}

            {result!.annotated_plan_base64 && (
              <AnnotatedPlanSection src={result!.annotated_plan_base64} />
            )}

            {/* Schema downloads — works for both n8n and FastAPI responses */}
            {result!.schemas?.length ? (
              <div className="rounded-xl mb-3 overflow-hidden"
                style={{ background: "rgba(255,255,255,0.025)", border: "1px solid rgba(255,255,255,0.06)" }}>
                <div className="px-5 py-3.5 flex items-center gap-2.5 text-sm font-semibold border-b"
                  style={{ color: "#C8CAD6", borderColor: "rgba(255,255,255,0.04)" }}>
                  Scheme monofilare
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full"
                    style={{ background: "rgba(255,255,255,0.07)", color: "#8B8FA8" }}>
                    {result!.schemas.length}
                  </span>
                </div>
                <div className="px-5 pb-4 flex flex-col gap-2 mt-3">
                  {result!.schemas.map((s, i) => (
                    <button key={i}
                      onClick={() => downloadPDF(
                        s.pdf_base64,
                        `Schema-${s.name}-${result!.project_info?.proiect_nr || result!.project_id || "zynapse"}.pdf`
                      )}
                      className="w-full py-2.5 rounded-lg text-[13px] font-semibold font-[inherit] cursor-pointer transition-colors duration-150 flex items-center justify-between gap-2 px-3"
                      style={{ background: "rgba(21,128,61,0.12)", border: "1px solid rgba(21,128,61,0.28)", color: "#4ADE80" }}
                      onMouseOver={(e) => (e.currentTarget.style.background = "rgba(21,128,61,0.22)")}
                      onMouseOut={(e) => (e.currentTarget.style.background = "rgba(21,128,61,0.12)")}>
                      <span>{s.name}{s.plansa_nr ? ` — Planșa ${s.plansa_nr}` : ""}{s.page_format ? ` (${s.page_format})` : ""}</span>
                      <span style={{ fontSize: 15 }}>⬇</span>
                    </button>
                  ))}
                </div>
              </div>
            ) : result!.schema_monofilara_pdf ? (
              <div className="mb-3">
                <SchemaDownloadButton base64Pdf={result!.schema_monofilara_pdf} />
              </div>
            ) : null}

            {/* Circuits — use circuits (n8n) with fallback to circuits_te_ct/teg (FastAPI) */}
            {(() => {
              const allCircuits = result!.circuits?.length
                ? result!.circuits
                : [...(result!.circuits_te_ct || []), ...(result!.circuits_teg || [])];
              return allCircuits.length > 0 ? (
                <div className="rounded-xl mb-3 overflow-hidden"
                  style={{ background: "rgba(255,255,255,0.025)", border: "1px solid rgba(255,255,255,0.06)" }}>
                  <details>
                    <summary className="px-5 py-3.5 flex items-center gap-2 text-sm font-semibold cursor-pointer list-none"
                      style={{ color: "#C8CAD6" }}>
                      Circuite electrice
                      <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full"
                        style={{ background: "rgba(255,255,255,0.07)", color: "#8B8FA8" }}>
                        {allCircuits.length}
                      </span>
                      {result!.power_summary?.installed_kw != null && (
                        <span className="ml-auto text-[11px]" style={{ color: "#545870" }}>
                          Pi={result!.power_summary.installed_kw} kW · Pa={result!.power_summary.absorbed_kw} kW
                        </span>
                      )}
                    </summary>
                    <div className="overflow-x-auto px-5 pb-4 border-t" style={{ borderColor: "rgba(255,255,255,0.04)" }}>
                      <table className="w-full border-collapse text-sm mt-3">
                        <thead>
                          <tr>
                            {["Nr.", "Destinație", "Tip", "Protecție", "Cablu"].map(h => (
                              <th key={h} className="text-left px-2 py-2 text-[10px] font-semibold tracking-widest uppercase"
                                style={{ color: "#545870", borderBottom: "1px solid rgba(255,255,255,0.06)" }}>{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {allCircuits.map((c, i) => {
                            const ctype = String((c as any).type || "");
                            return (
                              <tr key={i} style={{ background: i % 2 ? "rgba(255,255,255,0.015)" : "transparent" }}>
                                <td className="px-2 py-2">
                                  <span className="px-2 py-0.5 rounded text-[10px] font-bold"
                                    style={{
                                      background: ctype === "iluminat" ? "rgba(59,130,246,0.15)"
                                        : ctype === "prize" ? "rgba(245,158,11,0.15)"
                                        : "rgba(34,197,94,0.15)",
                                      color: ctype === "iluminat" ? "#93C5FD"
                                        : ctype === "prize" ? "#FCD34D"
                                        : "#86EFAC",
                                    }}>{c.id}</span>
                                </td>
                                <td className="px-2 py-2 text-sm" style={{ color: "#C8CAD6" }}>{c.usage || String((c as any).description || "")}</td>
                                <td className="px-2 py-2 text-[11px]" style={{ color: "#545870" }}>{ctype}</td>
                                <td className="px-2 py-2 text-sm font-semibold" style={{ color: "#8B8FA8" }}>{c.breaker_a}A</td>
                                <td className="px-2 py-2 text-[11px]" style={{ color: "#8B8FA8", fontFamily: "'JetBrains Mono', monospace" }}>
                                  {c.cable || String((c as any).cable_type || "")}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </details>
                </div>
              ) : null;
            })()}

            {/* BOM */}
            {result!.bom?.length ? (
              <div className="rounded-xl mb-3 overflow-hidden"
                style={{ background: "rgba(255,255,255,0.025)", border: "1px solid rgba(255,255,255,0.06)" }}>
                <details>
                  <summary className="px-5 py-3.5 flex items-center gap-2 text-sm font-semibold cursor-pointer list-none"
                    style={{ color: "#C8CAD6" }}>
                    Listă materiale
                    <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full"
                      style={{ background: "rgba(255,255,255,0.07)", color: "#8B8FA8" }}>
                      {result!.bom.length}
                    </span>
                  </summary>
                  <div className="overflow-x-auto px-5 pb-4 border-t" style={{ borderColor: "rgba(255,255,255,0.04)" }}>
                    <table className="w-full border-collapse text-sm mt-3">
                      <thead>
                        <tr>
                          {["Articol", "Cant.", "UM", "Observații"].map(h => (
                            <th key={h} className="text-left px-2 py-2 text-[10px] font-semibold tracking-widest uppercase"
                              style={{ color: "#545870", borderBottom: "1px solid rgba(255,255,255,0.06)" }}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {result!.bom.map((b, i) => (
                          <tr key={i} style={{ background: i % 2 ? "rgba(255,255,255,0.015)" : "transparent" }}>
                            <td className="px-2 py-2 text-sm" style={{ color: "#C8CAD6" }}>{b.item || (b as any).articol}</td>
                            <td className="px-2 py-2 text-sm font-semibold" style={{ color: "#8B8FA8" }}>{b.quantity ?? (b as any).cant}</td>
                            <td className="px-2 py-2 text-[11px]" style={{ color: "#545870" }}>{b.unit || (b as any).um}</td>
                            <td className="px-2 py-2 text-[11px]" style={{ color: "#545870" }}>{b.notes || (b as any).obs || ""}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </details>
              </div>
            ) : null}

            <RoomsList rooms={result!.rooms} />
            <MemoriuSection text={result!.memoriu_tehnic} />

            {/* Debug JSON */}
            <details className="mt-4">
              <summary className="text-[11px] cursor-pointer select-none"
                style={{ color: "#3A3D50" }}>Debug: JSON complet</summary>
              <pre className="mt-2 p-3 rounded-lg text-[10px] overflow-auto max-h-72 m-0"
                style={{ background: "rgba(0,0,0,0.4)", color: "#545870", fontFamily: "'JetBrains Mono', monospace", lineHeight: 1.5 }}>
                {JSON.stringify(result, null, 2)}
              </pre>
            </details>

          </div>
        ) : (
          <div className="flex flex-col items-center justify-center text-center" style={{ minHeight: 440, padding: "0 40px" }}>
            <div className="mb-5 rounded-2xl flex items-center justify-center"
              style={{ width: 72, height: 72, background: "rgba(55,138,221,0.07)", border: "1px solid rgba(55,138,221,0.12)" }}>
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" style={{ opacity: 0.5 }}>
                <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" stroke="#378ADD" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <h3 className="text-[17px] font-semibold m-0 mb-2" style={{ color: "#545870" }}>Proiectare electrică automată</h3>
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
