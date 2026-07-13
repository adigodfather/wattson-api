"use client";

import { useState, useRef, useEffect, useMemo } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  BUILDING_CATEGORIES_3, BUILDING_SUBTYPES,
  INSULATION, HEATING_GENERATION, HEATING_DISTRIBUTION,
  EXTRA_EQUIPMENT_DEFAULTS, FV_PACKAGE_OPTIONS, FV_SOIL_OPTIONS, FV_SOIL_DEFAULT, snapFvPackage, FAZA_PROIECT_OPTIONS, isPhasePT, iluminatPlanseToShow, ADMIN_USER_ID,
  plansaNumberingFromResult, mapSchemasToNumbering, sanitizePdfName,
  defaultTechRoom,
  INITIAL_FORM, type FormData, type ProjectResult, type Motor, type ExtraEquipment,
} from "@/lib/constants";
import { useAuth } from "@/components/auth-provider";
import AppHeader from "@/components/AppHeader";
import { createClient } from "@/lib/supabase";
import { floorCanonic, floorIndex } from "@/lib/floors";
import { heatingEquipmentFromCircuits } from "@/lib/heating-equipment";   // T3: echipamentele auto-plasabile   // M2a: un singur sistem de etaje (canonic)
import {
  MetricCard, CircuitTable, RoomsList, MemoriuSection, MemoriuDocxButton,
  SchemasSection, SchemaDownloadButton, AnnotatedPlanSection, ProjectInfoCard, PlanPdfSection,
} from "@/components/result-sections";
import CartusConfirmModal, { type VisionSurfaces } from "./CartusConfirmModal";
import MultiFileDropZone from "./MultiFileDropZone";
import { CREDIT_PRICING } from "@/components/CreditCalculator";

// Editor vizual (react-konva) — client-only (canvas/window). Lazy + ssr:false ca să nu pice next build.
const PlanEditor = dynamic(() => import("./plan-editor"), { ssr: false });

const WEBHOOK_URL = "/api/generate";

/* ─── Cartuș types ─── */
type CartusFirma = {
  firma_nume: string;
  firma_cui: string;
  firma_reg_com: string;
  firma_tel: string;
  firma_email: string;
  firma_adresa: string;
  firma_logo_url: string;
  proiectant_nume: string;
  desenator_nume: string;
};

type CartusProiect = {
  beneficiar: string;
  amplasament: string;
  titlu_proiect: string;
  numar_proiect: string;
  data_proiect: string;
  faza: string;
  sef_proiect: string;
};

const EMPTY_CARTUS_FIRMA: CartusFirma = {
  firma_nume: '', firma_cui: '', firma_reg_com: '', firma_tel: '',
  firma_email: '', firma_adresa: '', firma_logo_url: '',
  proiectant_nume: '', desenator_nume: '',
};

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
      <div className={`relative shrink-0 w-9 h-5 rounded-full transition-all duration-200${checked ? " zy-current" : ""}`}
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

/* ─── Drop zone ─── (înlocuit de MultiFileDropZone în Epic 3.11) */

/* ─── Building category cards (PAS 1) ─── */
/* Epic 3.11: doar "rezidential" e activ; Public + Industrial disabled cu badge "Curând" pentru
   TOȚI (decizia Dan 2026-07-13: Public se testează separat și se deschide când e gata). */
function CategoryCards({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div className="grid grid-cols-3 gap-2 mb-3">
      {BUILDING_CATEGORIES_3.map(c => {
        const selected = value === c.value;
        const enabled = c.value === "rezidential";
        return (
          <button key={c.value} type="button" disabled={!enabled}
            onClick={() => enabled && onChange(c.value)}
            title={enabled ? undefined : "Disponibil curând"}
            className={`rounded-xl p-3 text-center transition-all duration-150 font-[inherit]${selected ? " zy-current" : ""}`}
            style={{
              background: selected ? "rgba(55,138,221,0.08)" : "rgba(255,255,255,0.02)",
              border: selected ? "1.5px solid rgba(55,138,221,0.5)" : "1px solid rgba(255,255,255,0.07)",
              outline: "none",
              cursor: enabled ? "pointer" : "not-allowed",
              opacity: enabled ? 1 : 0.4,
            }}>
            <div style={{ fontSize: 22, marginBottom: 4 }}>{c.icon}</div>
            <div className="text-[12px] font-bold" style={{ color: selected ? "#5BB8F5" : "#C8CAD6" }}>{c.label}</div>
            {enabled ? (
              <div className="text-[10px] mt-1 leading-tight" style={{ color: "#545870" }}>{c.desc}</div>
            ) : (
              <div className="text-[10px] mt-1 font-semibold" style={{ color: "#C9A227" }}>Curând</div>
            )}
          </button>
        );
      })}
    </div>
  );
}

// Cost generare in Z-Coins — ACEEASI regula ca functia DB consume_credits:
// contine 'PT' -> 3/mp (DTAC+PT); altfel (DTAC) -> 1/mp. CEIL pe suprafata.
function genCostZ(surface: number, faza: string): number {
  if (!surface || surface <= 0) return 0;
  const perM2 = isPhasePT(faza)
    ? CREDIT_PRICING.perM2.dtac + CREDIT_PRICING.perM2.pt
    : CREDIT_PRICING.perM2.dtac;
  return Math.ceil(surface * perM2);
}

/* ─── ETAPA 3 Storage: preview + download schema per tablou (citeste-ambele) ───
   base64 (proiecte vechi / schema proaspata in memorie) -> direct; pdf_path (proiecte noi)
   -> signed URL din bucketul privat (iframe: 3600s la randare; download: 60s la click). */
function SchemaFrame({ base64Pdf, storagePath, title }: { base64Pdf?: string | null; storagePath?: string | null; title: string }) {
  const [src, setSrc] = useState<string | null>(base64Pdf ? `data:application/pdf;base64,${base64Pdf}` : null);
  useEffect(() => {
    let cancelled = false;
    if (!base64Pdf && storagePath) {
      (async () => {
        try {
          const supabase = createClient();
          const { data } = await supabase.storage.from("project-files").createSignedUrl(storagePath, 3600);
          if (!cancelled && data?.signedUrl) setSrc(data.signedUrl);
        } catch (e) {
          console.error("[SchemaFrame] signed URL esuat (preview lipseste, download ramane):", e);
        }
      })();
    }
    return () => { cancelled = true; };
  }, [base64Pdf, storagePath]);
  if (!src) return null;
  return <iframe src={src} className="w-full" style={{ height: 600, border: "none" }} title={title} />;
}

async function downloadSchemaEl(
  s: { pdf_base64?: string | null; pdf_path?: string | null },
  fileName: string,
  downloadB64: (b64: string, name: string) => void
) {
  if (s.pdf_base64) { downloadB64(s.pdf_base64, fileName); return; }
  if (s.pdf_path) {
    try {
      const supabase = createClient();
      const { data, error } = await supabase.storage
        .from("project-files")
        .createSignedUrl(s.pdf_path, 60, { download: fileName });
      if (error || !data?.signedUrl) {
        console.error("[downloadSchemaEl] signed URL esuat:", error?.message);
        alert("Nu s-a putut descărca schema. Încearcă din nou.");
        return;
      }
      const a = document.createElement("a");
      a.href = data.signedUrl;
      a.click();
    } catch (e) {
      console.error("[downloadSchemaEl] download din Storage esuat:", e);
      alert("Nu s-a putut descărca schema. Încearcă din nou.");
    }
  }
}

/* ─── Faza proiect chips (Epic 3.11) — DTAC + DTAC+PT live pentru TOȚI (lansare 2026-07-13);
       PT-only rămâne "Curând" (enabled: false în FAZA_PROIECT_OPTIONS). ─── */
function FazaProiectChips({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div className="grid grid-cols-3 gap-2 mb-3.5">
      {FAZA_PROIECT_OPTIONS.map(opt => {
        const enabled = opt.enabled;
        const isSel = value === opt.value;
        return (
          <button key={opt.value} type="button" disabled={!enabled}
            onClick={() => enabled && onChange(opt.value)}
            title={"tooltip" in opt ? opt.tooltip : undefined}
            className={`rounded-lg py-2.5 px-2 text-center transition-all duration-150 font-[inherit]${isSel ? " zy-current" : ""}`}
            style={{
              background: isSel ? "rgba(55,138,221,0.1)" : "rgba(255,255,255,0.02)",
              border: isSel ? "1px solid rgba(55,138,221,0.4)" : "1px solid rgba(255,255,255,0.06)",
              color: isSel ? "#5BB8F5" : "#C8CAD6",
              cursor: enabled ? "pointer" : "not-allowed",
              opacity: enabled ? 1 : 0.4,
            }}>
            <div className="text-[12px] font-bold">{opt.label}</div>
            {!enabled && <div className="text-[10px] mt-0.5 font-semibold" style={{ color: "#C9A227" }}>Curând</div>}
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
          // "Curând" per sub-tip (pattern-ul categoriilor): blocat DOAR daca nu-i deja selectat —
          // un proiect vechi resumed cu sub-tipul Soon ramane vizibil selectat (click nou blocat).
          const blocked = !!s.soon && !sel;
          return (
            <button key={s.value} type="button" disabled={blocked}
              onClick={() => !blocked && onChange(s.value)}
              title={blocked ? "Disponibil curând" : undefined}
              className={`text-left px-3 py-2 rounded-lg text-sm transition-all duration-100 font-[inherit]${blocked ? "" : " cursor-pointer"}`}
              style={{
                background: sel ? "rgba(55,138,221,0.1)" : "rgba(255,255,255,0.02)",
                border: sel ? "1px solid rgba(55,138,221,0.35)" : "1px solid rgba(255,255,255,0.06)",
                color: sel ? "#5BB8F5" : "#C8CAD6",
                cursor: blocked ? "not-allowed" : "pointer",
                opacity: blocked ? 0.4 : 1,
              }}>
              {s.label}
              {blocked && <span className="text-[10px] font-semibold" style={{ color: "#C9A227", marginLeft: 8 }}>Curând</span>}
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
              className={`w-9 h-9 rounded-lg text-[13px] font-semibold cursor-pointer font-[inherit] transition-all duration-100${floors === n ? " zy-current" : ""}`}
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
            className={`rounded-xl p-3 text-center cursor-pointer transition-all duration-150 font-[inherit]${sel ? " zy-current" : ""}`}
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
interface EquipState { enabled: boolean; power_kw: number; phase: string; soil_type?: string; }

function EquipmentCards({
  equipment, setEquipment, customEquipment, setCustomEquipment,
}: {
  equipment: Record<string, EquipState>;
  setEquipment: React.Dispatch<React.SetStateAction<Record<string, EquipState>>>;
  customEquipment: { name: string; room: string; power_kw: number; phase: string }[];
  setCustomEquipment: React.Dispatch<React.SetStateAction<{ name: string; room: string; power_kw: number; phase: string }[]>>;
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
            className={`rounded-xl transition-all duration-150 overflow-hidden${st.enabled ? " zy-current" : ""}`}
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
            {st.enabled && eq.fvPackage && (
              // FV: PACHETE discrete (5/10/15/20 kW), FĂRĂ putere liberă și FĂRĂ mono/tri (mereu trifazat).
              <div className="px-3 pb-3" onClick={e => e.stopPropagation()}>
                <label className="block text-[11px] font-semibold mb-1" style={{ color: "#545870" }}>PACHET (kW)</label>
                <div className="grid grid-cols-4 gap-2">
                  {FV_PACKAGE_OPTIONS.map(kw => {
                    const sel = snapFvPackage(st.power_kw) === kw;
                    return (
                      <button key={kw} type="button"
                        onClick={() => setEquipment(prev => ({ ...prev, [eq.type]: { ...prev[eq.type], power_kw: kw, phase: "tri" } }))}
                        className="px-2 py-2 rounded-lg text-[13px] font-semibold transition-all duration-150"
                        style={{
                          background: sel ? "rgba(55,138,221,0.18)" : "rgba(255,255,255,0.04)",
                          border: sel ? "1.5px solid rgba(55,138,221,0.55)" : "1px solid rgba(255,255,255,0.08)",
                          color: sel ? "#5BB8F5" : "#8B8FA8",
                        }}>
                        {kw} kW
                      </button>
                    );
                  })}
                </div>
                <div className="text-[11px] mt-1.5" style={{ color: "#545870" }}>Sistem trifazat 400V (pachet standard)</div>
                {/* G-UI: tipul de sol (priza de pamant FV) — dropdown sub pachet, conform studiului geo */}
                <label className="block text-[11px] font-semibold mb-1 mt-2.5" style={{ color: "#545870" }}>
                  TIP DE SOL (PENTRU PRIZA DE PĂMÂNT)
                </label>
                <select value={st.soil_type || FV_SOIL_DEFAULT}
                  onChange={e => setEquipment(prev => ({ ...prev, [eq.type]: { ...prev[eq.type], soil_type: e.target.value } }))}
                  className="w-full px-2.5 py-2" style={{ ...inputStyle, paddingRight: 8 }}>
                  {FV_SOIL_OPTIONS.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}
                </select>
              </div>
            )}
            {st.enabled && !eq.fvPackage && eq.default_kw > 0 && (
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
          <input type="text" placeholder="Încăpere / Cameră (ex: bucătărie, living, hol)" value={eq.room}
            onChange={e => setCustomEquipment(prev => prev.map((x, j) => j === i ? { ...x, room: e.target.value } : x))}
            className="w-full px-2.5 py-2 rounded-lg text-[13px] outline-none font-[inherit] mb-2"
            style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", color: "#E2E4E9" }} />
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
        onClick={() => setCustomEquipment(prev => [...prev, { name: "", room: "", power_kw: 0, phase: "mono" }])}
        className="text-[12px] font-semibold px-3 py-2 rounded-lg cursor-pointer font-[inherit] text-left"
        style={{ background: "rgba(255,255,255,0.03)", border: "1px dashed rgba(255,255,255,0.1)", color: "#545870" }}>
        ➕ Adaugă echipament custom
      </button>
    </div>
  );
}

/* ─── Panou drept (b): cip de procesare finală (status === "loading") ─── */
function CipProcesare() {
  return (
    <div className="flex flex-col items-center justify-center text-center min-h-[70vh] md:min-h-[640px] md:self-stretch px-6">
      <div className="w-full" style={{ maxWidth: 680 }}>
        <svg viewBox="-50 -50 420 320" preserveAspectRatio="xMidYMid meet" fill="none" aria-hidden="true" className="block w-full h-auto">
          <defs>
            <filter id="zcGlow" x="-60%" y="-60%" width="220%" height="220%">
              <feGaussianBlur stdDeviation="2.2" result="b" />
              <feMerge>
                <feMergeNode in="b" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
          <style dangerouslySetInnerHTML={{ __html: `
            .zc-gear{transform-box:fill-box;transform-origin:center;animation:zc-rot 6s linear infinite}
            @keyframes zc-rot{to{transform:rotate(360deg)}}
            .zc-pulse{transform-box:fill-box;transform-origin:center;animation:zc-pulse 4.4s ease-out infinite}
            .zc-pulse.b{animation-delay:2.2s}
            @keyframes zc-pulse{0%{transform:scale(.22);opacity:.5}70%{opacity:.12}100%{transform:scale(2.4);opacity:0}}
            .zc-cur{stroke-dasharray:16 260;animation:zc-flow 3.6s linear infinite}
            .zc-cur.d2{animation-delay:.9s}.zc-cur.d3{animation-delay:1.8s}.zc-cur.d4{animation-delay:2.7s}
            @keyframes zc-flow{from{stroke-dashoffset:276}to{stroke-dashoffset:0}}
            .zc-node{animation:zc-node 2.8s ease-in-out infinite}
            @keyframes zc-node{0%,100%{opacity:.3}50%{opacity:1}}
            @media (prefers-reduced-motion: reduce){
              .zc-gear,.zc-cur,.zc-node{animation:none}
              .zc-pulse{animation:none;opacity:0}
            }
          `}} />

          {/* trasee PCB de fundal */}
          <g stroke="#545870" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" opacity="0.55">
            <path d="M160 78 V-40" />
            <path d="M192 110 H360" />
            <path d="M160 142 V260" />
            <path d="M128 110 H-40" />
            <path d="M140 78 V35 H-35" />
            <path d="M180 78 V35 H310" />
            <path d="M180 142 V185 H310" />
            <path d="M140 142 V185 H-35" />
            <path d="M192 96 H270 V35" />
            <path d="M128 124 H50 V185" />
          </g>

          {/* noduri pulsatoare (decalat) */}
          <g fill="#378ADD">
            <circle className="zc-node" cx="160" cy="-40" r="2.8" style={{ animationDelay: "0s" }} />
            <circle className="zc-node" cx="360" cy="110" r="2.8" style={{ animationDelay: ".5s" }} />
            <circle className="zc-node" cx="160" cy="260" r="2.8" style={{ animationDelay: "1s" }} />
            <circle className="zc-node" cx="-40" cy="110" r="2.8" style={{ animationDelay: "1.5s" }} />
            <circle className="zc-node" cx="-35" cy="35" r="2.2" style={{ animationDelay: ".8s" }} />
            <circle className="zc-node" cx="310" cy="35" r="2.2" style={{ animationDelay: "1.3s" }} />
            <circle className="zc-node" cx="310" cy="185" r="2.2" style={{ animationDelay: ".3s" }} />
            <circle className="zc-node" cx="-35" cy="185" r="2.2" style={{ animationDelay: "1.8s" }} />
            <circle className="zc-node" cx="270" cy="35" r="2.2" style={{ animationDelay: "2.1s" }} />
            <circle className="zc-node" cx="50" cy="185" r="2.2" style={{ animationDelay: ".6s" }} />
          </g>

          {/* curent care "curge" pe trasee cardinale */}
          <g stroke="#5BB8F5" strokeWidth="1.6" strokeLinecap="round" fill="none" filter="url(#zcGlow)">
            <path className="zc-cur" d="M160 78 V-40" />
            <path className="zc-cur d2" d="M192 110 H360" />
            <path className="zc-cur d3" d="M160 142 V260" />
            <path className="zc-cur d4" d="M128 110 H-40" />
          </g>

          {/* puls radial din centru */}
          <g fill="none" stroke="#378ADD" strokeWidth="1.1">
            <circle className="zc-pulse" cx="160" cy="110" r="26" />
            <circle className="zc-pulse b" cx="160" cy="110" r="26" />
          </g>

          {/* pini cip */}
          <g fill="#378ADD" opacity="0.7">
            <rect x="142" y="72.5" width="4" height="6" rx="1" />
            <rect x="158" y="72.5" width="4" height="6" rx="1" />
            <rect x="174" y="72.5" width="4" height="6" rx="1" />
            <rect x="142" y="141.5" width="4" height="6" rx="1" />
            <rect x="158" y="141.5" width="4" height="6" rx="1" />
            <rect x="174" y="141.5" width="4" height="6" rx="1" />
            <rect x="121.5" y="90" width="6" height="4" rx="1" />
            <rect x="121.5" y="108" width="6" height="4" rx="1" />
            <rect x="121.5" y="126" width="6" height="4" rx="1" />
            <rect x="192.5" y="90" width="6" height="4" rx="1" />
            <rect x="192.5" y="108" width="6" height="4" rx="1" />
            <rect x="192.5" y="126" width="6" height="4" rx="1" />
          </g>

          {/* corp cip */}
          <rect x="128" y="78" width="64" height="64" rx="11" fill="rgba(55,138,221,0.05)" stroke="#378ADD" strokeWidth="1.4" />

          {/* angrenaj rotativ (focal) */}
          <g className="zc-gear">
            <circle cx="160" cy="110" r="15" fill="none" stroke="#5BB8F5" strokeWidth="5" strokeDasharray="4.5 5.4" filter="url(#zcGlow)" />
            <circle cx="160" cy="110" r="9.5" fill="#0F1115" stroke="#378ADD" strokeWidth="1.4" />
            <circle cx="160" cy="110" r="2.6" fill="#5BB8F5" />
          </g>
        </svg>
      </div>
      <h3 className="text-[19px] font-semibold m-0 mt-6" style={{ color: "#8B8FA8" }}>Se generează proiectul…</h3>
      <p className="text-[14px] m-0 mt-2" style={{ color: "#3A3D50" }}>Calculăm circuitele și pregătim planșele</p>
    </div>
  );
}

/* ─── Panou drept (a): carusel flux (schelet — cadre placeholder) ─── */
function FluxIconBox({ children, size = 76 }: { children: React.ReactNode; size?: number }) {
  return (
    <div className="rounded-2xl flex items-center justify-center shrink-0"
      style={{ width: size, height: size, background: "rgba(55,138,221,0.07)", border: "1px solid rgba(55,138,221,0.14)" }}>
      {children}
    </div>
  );
}

const EQUIPMENT_ART: { label: string; icon: React.ReactNode }[] = [
  {
    label: "Wi-Fi",
    icon: (
      <>
        <path d="M4.5 9.5a11 11 0 0 1 15 0" stroke="#5BB8F5" strokeWidth="1.6" strokeLinecap="round" />
        <path d="M7.5 12.5a7 7 0 0 1 9 0" stroke="#378ADD" strokeWidth="1.6" strokeLinecap="round" />
        <path d="M10 15.4a3 3 0 0 1 4 0" stroke="#378ADD" strokeWidth="1.6" strokeLinecap="round" />
        <circle cx="12" cy="18.4" r="1.3" fill="#5BB8F5" />
      </>
    ),
  },
  {
    label: "PDC",
    icon: (
      <>
        <rect x="2.5" y="6.5" width="19" height="11" rx="2" stroke="#5BB8F5" strokeWidth="1.5" />
        <circle cx="12" cy="12" r="3.3" stroke="#378ADD" strokeWidth="1.4" />
        <path d="M12 8.7v6.6M9.1 10.3l5.8 3.4M9.1 13.7l5.8-3.4" stroke="#378ADD" strokeWidth="1.1" strokeLinecap="round" />
        <path d="M4.7 9.2v5.6" stroke="#5BB8F5" strokeWidth="1.2" strokeLinecap="round" />
      </>
    ),
  },
  {
    label: "Cuptor",
    icon: (
      <>
        <rect x="4" y="4" width="16" height="16" rx="2" stroke="#5BB8F5" strokeWidth="1.5" />
        <path d="M4 9h16" stroke="#378ADD" strokeWidth="1.3" />
        <path d="M7 6.6h3.5" stroke="#378ADD" strokeWidth="1.2" strokeLinecap="round" />
        <rect x="7.5" y="11.5" width="9" height="6" rx="1" stroke="#378ADD" strokeWidth="1.2" />
      </>
    ),
  },
  {
    label: "Boiler",
    icon: (
      <>
        <rect x="7" y="3.5" width="10" height="17" rx="4.5" stroke="#5BB8F5" strokeWidth="1.5" />
        <path d="M9.5 11h5M9.5 14h5" stroke="#378ADD" strokeWidth="1.2" strokeLinecap="round" />
        <path d="M12 3.5V1.6M10 20.5v1.9M14 20.5v1.9" stroke="#5BB8F5" strokeWidth="1.2" strokeLinecap="round" />
      </>
    ),
  },
  {
    label: "Aer condiționat",
    icon: (
      <>
        <rect x="2.5" y="6" width="19" height="7" rx="2" stroke="#5BB8F5" strokeWidth="1.5" />
        <path d="M5 10.5h14" stroke="#378ADD" strokeWidth="1.2" strokeLinecap="round" />
        <path d="M7 16c0 1 .8 1.5 1.6 2M12 16c0 1 .8 1.5 1.6 2M17 16c-.2 1 .4 1.6 1.1 2.2" stroke="#378ADD" strokeWidth="1.1" strokeLinecap="round" />
      </>
    ),
  },
  {
    label: "Fotovoltaice",
    icon: (
      <>
        <rect x="3" y="5.5" width="18" height="9" rx="1" stroke="#5BB8F5" strokeWidth="1.5" />
        <path d="M9 5.5v9M15 5.5v9M3 8.5h18M3 11.5h18" stroke="#378ADD" strokeWidth="1" strokeLinecap="round" />
        <path d="M12 14.5v4M8 18.5h8" stroke="#5BB8F5" strokeWidth="1.3" strokeLinecap="round" />
      </>
    ),
  },
];

const FLUX_FRAMES: { n: number; title: string; subtitle: string; icon: React.ReactNode; durationMs: number; art?: React.ReactNode }[] = [
  {
    n: 1, durationMs: 15000, title: "Încarcă arhitectura", subtitle: "Planșele clădirii — PDF sau imagine",
    icon: (
      <svg width="34" height="34" viewBox="0 0 24 24" fill="none">
        <rect x="3.5" y="3.5" width="17" height="17" rx="1.5" stroke="#5BB8F5" strokeWidth="1.6" />
        <path d="M12 3.5V13M12 13H20.5M3.5 13H8" stroke="#378ADD" strokeWidth="1.4" strokeLinecap="round" />
      </svg>
    ),
    art: (
      <div className="w-full flex flex-col items-center" style={{ maxWidth: 640 }}>
        <svg viewBox="0 0 420 290" preserveAspectRatio="xMidYMid meet" fill="none" aria-hidden="true" className="block w-full h-auto">
          <defs>
            <filter id="bpGlow" x="-30%" y="-30%" width="160%" height="160%">
              <feGaussianBlur stdDeviation="3.4" />
            </filter>
          </defs>
          <style dangerouslySetInnerHTML={{ __html: `
            .bp{animation:bp-fade 15s ease-in-out infinite}
            @keyframes bp-fade{0%{opacity:0}2.5%{opacity:1}93%{opacity:1}100%{opacity:0}}
            .bp-line{stroke-dasharray:1}
            .bp-1{animation:bp-d1 15s ease-in-out infinite}
            .bp-2{animation:bp-d2 15s ease-in-out infinite}
            .bp-3{animation:bp-d3 15s ease-in-out infinite}
            .bp-4{animation:bp-d4 15s ease-in-out infinite}
            .bp-5{animation:bp-d5 15s ease-in-out infinite}
            @keyframes bp-d1{0%,2%{stroke-dashoffset:1}25%,100%{stroke-dashoffset:0}}
            @keyframes bp-d2{0%,25%{stroke-dashoffset:1}45%,100%{stroke-dashoffset:0}}
            @keyframes bp-d3{0%,45%{stroke-dashoffset:1}63%,100%{stroke-dashoffset:0}}
            @keyframes bp-d4{0%,63%{stroke-dashoffset:1}74%,100%{stroke-dashoffset:0}}
            @keyframes bp-d5{0%,74%{stroke-dashoffset:1}85%,100%{stroke-dashoffset:0}}
            .bp-glow-el{animation:bp-glow 15s ease-in-out infinite}
            @keyframes bp-glow{0%,86%{opacity:0}90%{opacity:.5}94%,100%{opacity:0}}
            @media (prefers-reduced-motion: reduce){
              .bp{animation:none!important;opacity:1!important}
              .bp-line{animation:none!important;stroke-dashoffset:0!important}
              .bp-glow-el{animation:none!important;opacity:0!important}
            }
          `}} />
          <g className="bp" fill="none" strokeLinecap="round" strokeLinejoin="round">
            {/* halo puls pe contur (după desenarea completă) */}
            <path className="bp-glow-el" d="M30 30 H390 V260 H30 Z" stroke="#5BB8F5" strokeWidth="2.8" filter="url(#bpGlow)" />
            {/* contur exterior (pereți casă) */}
            <path className="bp-line bp-1" pathLength="1" d="M30 30 H390 V260 H30 Z" stroke="#5BB8F5" strokeWidth="2.4" />
            {/* pereți interiori principali */}
            <path className="bp-line bp-2" pathLength="1" d="M180 30 V180 M30 180 H390 M290 30 V180" stroke="#378ADD" strokeWidth="1.8" />
            {/* pereți interiori secundari (camere) */}
            <path className="bp-line bp-3" pathLength="1" d="M120 180 V260 M230 180 V260 M320 180 V260 M180 110 H290" stroke="#378ADD" strokeWidth="1.7" />
            {/* uși (arce de deschidere) */}
            <path className="bp-line bp-4" pathLength="1" d="M180 130 A22 22 0 0 0 158 152 M250 180 A20 20 0 0 1 270 200 M290 90 A18 18 0 0 0 272 108" stroke="#5BB8F5" strokeWidth="1.6" />
            {/* ferestre (straddle pe pereți) */}
            <path className="bp-line bp-5" pathLength="1" d="M80 26 H120 M80 34 H120 M320 26 H360 M320 34 H360 M26 95 V135 M34 95 V135 M160 256 H200 M160 264 H200" stroke="#5BB8F5" strokeWidth="1.6" />
          </g>
        </svg>

        {/* Reguli planșe — ies în evidență / strălucesc */}
        <div className="mt-5 w-full text-left rounded-xl px-4 py-3.5"
          style={{ background: "rgba(55,138,221,0.06)", border: "1px solid rgba(91,184,245,0.28)", boxShadow: "0 0 22px rgba(55,138,221,0.12)" }}>
          <ul className="m-0 p-0 list-none flex flex-col gap-2">
            {[
              "Planșele să nu fie semnate sau ștampilate",
              "Planșele să nu fie semnate electronic",
              "Planșele să nu fie scanate (preferabil format vectorial / PDF nativ)",
            ].map(r => (
              <li key={r} className="flex items-start gap-2.5 text-[13px] md:text-[13.5px] font-medium"
                style={{ color: "#9FD2FA", textShadow: "0 0 10px rgba(91,184,245,0.4)" }}>
                <span style={{ color: "#5BB8F5" }}>▸</span><span>{r}</span>
              </li>
            ))}
          </ul>
          <p className="m-0 mt-3 text-[12.5px] italic leading-relaxed" style={{ color: "#7FB4E0" }}>
            Vă mulțumim că respectați aceste cerințe — ne ajută să vă oferim un rezultat de calitate
          </p>
        </div>
      </div>
    ),
  },
  {
    n: 2, durationMs: 15000, title: "Selectează datele", subtitle: "Tip clădire, regim, putere, echipamente",
    icon: (
      <svg width="34" height="34" viewBox="0 0 24 24" fill="none">
        <path d="M4 7h16M4 12h16M4 17h16" stroke="#378ADD" strokeWidth="1.6" strokeLinecap="round" />
        <circle cx="9" cy="7" r="2.4" fill="#0F1115" stroke="#5BB8F5" strokeWidth="1.6" />
        <circle cx="15" cy="12" r="2.4" fill="#0F1115" stroke="#5BB8F5" strokeWidth="1.6" />
        <circle cx="8" cy="17" r="2.4" fill="#0F1115" stroke="#5BB8F5" strokeWidth="1.6" />
      </svg>
    ),
    art: (
      <div className="w-full flex flex-col items-center" style={{ maxWidth: 560 }}>
        <svg viewBox="0 0 440 280" preserveAspectRatio="xMidYMid meet" fill="none" aria-hidden="true" className="block w-full h-auto">
          <defs>
            <filter id="eqGlow" x="-40%" y="-40%" width="180%" height="180%"><feGaussianBlur stdDeviation="2.4" /></filter>
          </defs>
          <style dangerouslySetInnerHTML={{ __html: `
            .eqs{animation:eqs-fade 15s ease-in-out infinite}
            @keyframes eqs-fade{0%{opacity:0}3%{opacity:1}94%{opacity:1}100%{opacity:0}}
            .eq-app{transform-box:fill-box;transform-origin:center;opacity:0}
            .ea1{animation:ea1 15s ease-in-out infinite}
            .ea2{animation:ea2 15s ease-in-out infinite}
            .ea3{animation:ea3 15s ease-in-out infinite}
            .ea4{animation:ea4 15s ease-in-out infinite}
            .ea5{animation:ea5 15s ease-in-out infinite}
            .ea6{animation:ea6 15s ease-in-out infinite}
            @keyframes ea1{0%,2%{opacity:0;transform:scale(.82)}7%{opacity:1;transform:scale(1)}100%{opacity:1;transform:scale(1)}}
            @keyframes ea2{0%,5%{opacity:0;transform:scale(.82)}10%{opacity:1;transform:scale(1)}100%{opacity:1;transform:scale(1)}}
            @keyframes ea3{0%,8%{opacity:0;transform:scale(.82)}13%{opacity:1;transform:scale(1)}100%{opacity:1;transform:scale(1)}}
            @keyframes ea4{0%,11%{opacity:0;transform:scale(.82)}16%{opacity:1;transform:scale(1)}100%{opacity:1;transform:scale(1)}}
            @keyframes ea5{0%,14%{opacity:0;transform:scale(.82)}19%{opacity:1;transform:scale(1)}100%{opacity:1;transform:scale(1)}}
            @keyframes ea6{0%,17%{opacity:0;transform:scale(.82)}22%{opacity:1;transform:scale(1)}100%{opacity:1;transform:scale(1)}}
            .eq-panel{stroke-dasharray:1;animation:eq-panel 15s ease-in-out infinite}
            @keyframes eq-panel{0%,3%{stroke-dashoffset:1}16%,100%{stroke-dashoffset:0}}
            .eq-mod{opacity:0;animation:eq-mod 15s ease-in-out infinite}
            @keyframes eq-mod{0%,40%{opacity:0}52%,100%{opacity:1}}
            .eq-cable{stroke-dasharray:1}
            .ec1{animation:ec1 15s ease-in-out infinite}
            .ec2{animation:ec2 15s ease-in-out infinite}
            .ec3{animation:ec3 15s ease-in-out infinite}
            .ec4{animation:ec4 15s ease-in-out infinite}
            .ec5{animation:ec5 15s ease-in-out infinite}
            .ec6{animation:ec6 15s ease-in-out infinite}
            @keyframes ec1{0%,24%{stroke-dashoffset:1}36%,100%{stroke-dashoffset:0}}
            @keyframes ec2{0%,29%{stroke-dashoffset:1}41%,100%{stroke-dashoffset:0}}
            @keyframes ec3{0%,34%{stroke-dashoffset:1}46%,100%{stroke-dashoffset:0}}
            @keyframes ec4{0%,39%{stroke-dashoffset:1}51%,100%{stroke-dashoffset:0}}
            @keyframes ec5{0%,44%{stroke-dashoffset:1}56%,100%{stroke-dashoffset:0}}
            @keyframes ec6{0%,49%{stroke-dashoffset:1}61%,100%{stroke-dashoffset:0}}
            .eq-cur{stroke-dasharray:9 80;animation:eq-flow 2.2s linear infinite, eq-curfade 15s ease-in-out infinite}
            @keyframes eq-flow{from{stroke-dashoffset:89}to{stroke-dashoffset:0}}
            @keyframes eq-curfade{0%,58%{opacity:0}64%{opacity:.85}90%{opacity:.85}95%,100%{opacity:0}}
            .eq-dot{animation:eq-dot 2.6s ease-in-out infinite}
            @keyframes eq-dot{0%,100%{opacity:.3}50%{opacity:1}}
            @media (prefers-reduced-motion: reduce){
              .eqs{animation:none!important;opacity:1!important}
              .eq-app{animation:none!important;opacity:1!important;transform:none!important}
              .eq-panel,.eq-cable{animation:none!important;stroke-dashoffset:0!important}
              .eq-mod{animation:none!important;opacity:1!important}
              .eq-cur{animation:none!important;opacity:0!important}
              .eq-dot{animation:none!important;opacity:.8!important}
            }
          `}} />
          <g className="eqs">
            {/* cabluri (se conectează pe rând spre tablou) */}
            {EQUIPMENT_ART.map((eq, i) => {
              const rowY = 34 + i * 40, midx = 220 + i * 8, py = 70 + i * 28;
              return <path key={`c${i}`} className={`eq-cable ec${i + 1}`} pathLength="1" d={`M150 ${rowY} H${midx} V${py} H330`} stroke="#4A5E86" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />;
            })}
            {/* curent care curge spre tablou */}
            {EQUIPMENT_ART.map((eq, i) => {
              const rowY = 34 + i * 40, midx = 220 + i * 8, py = 70 + i * 28;
              return <path key={`f${i}`} className="eq-cur" d={`M150 ${rowY} H${midx} V${py} H330`} stroke="#5BB8F5" strokeWidth="1.8" fill="none" strokeLinecap="round" filter="url(#eqGlow)" />;
            })}
            {/* tablou electric */}
            <rect className="eq-panel" pathLength="1" x="330" y="54" width="86" height="172" rx="6" stroke="#5BB8F5" strokeWidth="2" fill="rgba(55,138,221,0.04)" />
            <path className="eq-panel" pathLength="1" d="M340 76 H406" stroke="#378ADD" strokeWidth="1.4" />
            {EQUIPMENT_ART.map((eq, i) => {
              const py = 70 + i * 28;
              return (
                <g key={`m${i}`} className="eq-mod" fill="none">
                  <rect x="342" y={py - 8} width="62" height="16" rx="2" stroke="#378ADD" strokeWidth="1.2" />
                  <path d={`M351 ${py} h7`} stroke="#5BB8F5" strokeWidth="1.4" strokeLinecap="round" />
                </g>
              );
            })}
            {/* echipamente etichetate (apar pe rând) */}
            {EQUIPMENT_ART.map((eq, i) => {
              const rowY = 34 + i * 40;
              return (
                <g key={`e${i}`} className={`eq-app ea${i + 1}`}>
                  <svg x="8" y={rowY - 16} width="32" height="32" viewBox="0 0 24 24" fill="none">{eq.icon}</svg>
                  <text x="46" y={rowY + 4} fontSize="12.5" fontWeight="500" fill="#9AA0B5">{eq.label}</text>
                </g>
              );
            })}
            {/* noduri pulsatoare (echipament + intrare tablou) */}
            {EQUIPMENT_ART.map((eq, i) => {
              const rowY = 34 + i * 40, py = 70 + i * 28;
              return (
                <g key={`n${i}`} fill="#5BB8F5">
                  <circle className="eq-dot" cx="150" cy={rowY} r="2.6" style={{ animationDelay: `${i * 0.25}s` }} />
                  <circle className="eq-dot" cx="330" cy={py} r="2.6" style={{ animationDelay: `${i * 0.25 + 0.4}s` }} />
                </g>
              );
            })}
          </g>
        </svg>

        {/* Reguli echipamente — ies în evidență / strălucesc */}
        <div className="mt-5 w-full text-left rounded-xl px-4 py-3.5"
          style={{ background: "rgba(55,138,221,0.06)", border: "1px solid rgba(91,184,245,0.28)", boxShadow: "0 0 22px rgba(55,138,221,0.12)" }}>
          <ul className="m-0 p-0 list-none flex flex-col gap-2">
            {[
              "Selectați opțiunile dorite pentru imobilul dumneavoastră",
              "Pentru echipamente nespecificate de noi, adăugați și încăperea în care doriți montarea, precum și puterea acestora",
              "Pentru cele mai bune rezultate, selectați toate echipamentele dorite din proiect",
            ].map(r => (
              <li key={r} className="flex items-start gap-2.5 text-[13px] md:text-[13.5px] font-medium"
                style={{ color: "#9FD2FA", textShadow: "0 0 10px rgba(91,184,245,0.4)" }}>
                <span style={{ color: "#5BB8F5" }}>▸</span><span>{r}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    ),
  },
];

function CarouselFlux() {
  const [idx, setIdx] = useState(0);
  const [reduced, setReduced] = useState(false);

  // Detectare prefers-reduced-motion (pur vizual, izolat de fluxul de generare)
  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const onChange = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  // Ciclare automată: fiecare cadru așteaptă propria durată, apoi trece la următorul.
  // setTimeout re-armat la fiecare schimbare de index (oprit la reduced-motion); curățat la unmount.
  useEffect(() => {
    if (reduced) return;
    const dur = FLUX_FRAMES[idx]?.durationMs ?? 4000;
    const id = setTimeout(() => setIdx(i => (i + 1) % FLUX_FRAMES.length), dur);
    return () => clearTimeout(id);
  }, [reduced, idx]);

  // Reduced-motion: toate cadrele static, fără mișcare
  if (reduced) {
    return (
      <div className="flex flex-col justify-center gap-3 min-h-[40vh] md:min-h-[480px]" style={{ padding: "8px 20px" }}>
        {FLUX_FRAMES.map(f => (
          <div key={f.n} className="flex items-center gap-3.5 text-left">
            <FluxIconBox size={52}>{f.icon}</FluxIconBox>
            <div>
              <div className="text-sm font-semibold" style={{ color: "#8B8FA8" }}>{f.n}. {f.title}</div>
              <div className="text-[12px]" style={{ color: "#3A3D50" }}>{f.subtitle}</div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  const active = FLUX_FRAMES[idx] ?? FLUX_FRAMES[0];
  return (
    <div className="flex flex-col items-center justify-center text-center min-h-[40vh] md:min-h-[480px]" style={{ padding: "12px 24px 36px" }}>
      <div key={active.n} className="w-full flex flex-col items-center" style={{ animation: "zy-fade-in 480ms ease both" }}>
        {active.art ?? <FluxIconBox>{active.icon}</FluxIconBox>}
        <h3 className="text-[17px] font-semibold m-0 mt-5 mb-1.5" style={{ color: "#8B8FA8" }}>{active.n}. {active.title}</h3>
        <p className="text-sm m-0 leading-relaxed" style={{ color: "#3A3D50", maxWidth: 320 }}>{active.subtitle}</p>
      </div>
      <div className="mt-6 flex justify-center gap-2">
        {FLUX_FRAMES.map((f, i) => (
          <span key={f.n} className="rounded-full transition-all duration-300"
            style={{ width: i === idx ? 18 : 6, height: 6, background: i === idx ? "#378ADD" : "rgba(255,255,255,0.14)" }} />
        ))}
      </div>
    </div>
  );
}

/* ─── Main configurator ─── */
export function ZynapseConfigurator() {
  const router = useRouter();
  const { user, profile, refreshProfile } = useAuth();
  const [files, setFiles] = useState<File[]>([]);
  const [form, setForm] = useState<FormData>(INITIAL_FORM);
  const [status, setStatus] = useState("idle");
  const [result, setResult] = useState<ProjectResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stepIndex, setStepIndex] = useState(0);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [finalizeLoading, setFinalizeLoading] = useState(false);   // Faza 2b: "Finalizeaza" genereaza docs
  const [finalizeErr, setFinalizeErr] = useState<string | null>(null);
  const [motors, setMotors] = useState<Motor[]>([]);

  // Height regime (manual controls)
  const [manualFloors, setManualFloors] = useState(0);

  // Extra equipment state
  const [equipment, setEquipment] = useState<Record<string, EquipState>>(
    Object.fromEntries(EXTRA_EQUIPMENT_DEFAULTS.map(e => [e.type, { enabled: false, power_kw: e.default_kw, phase: e.default_phase }]))
  );
  const [customEquipment, setCustomEquipment] = useState<{ name: string; room: string; power_kw: number; phase: string }[]>([]);

  // Auto-detect badge (populated from response)
  const [autoDetected, setAutoDetected] = useState<{ climate_zone: string; climate_source?: string; levels_string?: string } | null>(null);
  const [activeTab, setActiveTab] = useState<string>('circuits');
  const [modeEditor, setModeEditor] = useState<"iluminat" | "forta">("iluminat");   // F3: comutator Iluminat/Forta in tab Editor
  // Fundal editor FORTA = baza CURATA (randata prin /api/render-base-png), NU PNG-ul iluminat (becuri invechite).
  const [fortaBg, setFortaBg] = useState<{ png_base64: string; png_meta: { dpi?: number; scale?: number;
    pdf_width_pt?: number; pdf_height_pt?: number; png_width_px?: number; png_height_px?: number } } | null>(null);
  const [fortaBgErr, setFortaBgErr] = useState(false);   // /render-base-png a esuat definitiv -> fallback pe fundalul iluminat (fara eroare in UI)
  // M2b: etajul SELECTAT în editor (index în planse_iluminat = index etaj). Selectabil prin selector multi-etaj.
  const [editorPlansaIdx, setEditorPlansaIdx] = useState(0);
  const [savedProjectId, setSavedProjectId] = useState<string | null>(null);  // uuid proiect salvat -> editor citește plan_elements
  const [pageFormat, setPageFormat] = useState<string>('');
  const [cartusProiectInput, setCartusProiectInput] = useState<CartusProiect>({
    beneficiar: '',
    amplasament: '',
    titlu_proiect: '',
    numar_proiect: '',
    faza: 'DTAC',       // default ieftin (1/mp); DTAC+PT = opt-in constient (3/mp, cost in preview)
    sef_proiect: '',
    data_proiect: '',
  });

  // Vision cartuș flow state
  const [visionCartusLoading, setVisionCartusLoading] = useState(false);
  // Suprafețe detectate de Vision din cartuș (Pas 2) — pt. rândul de cost real în modal (Pas 3)
  const [visionSurfaces, setVisionSurfaces] = useState<VisionSurfaces | null>(null);
  const [showCartusModal, setShowCartusModal] = useState(false);
  const [cartusConfirmed, setCartusConfirmed] = useState(false);
  const visionAnalyzedRef = useRef<string | null>(null);

  const update = (key: keyof FormData, val: string | boolean | number) =>
    setForm(prev => ({ ...prev, [key]: val }));

  const isAdmin = profile?.is_admin === true;

  // LANSARE (Dan, 2026-07-13): plasa de siguranta care reseta faza PT la DTAC pentru non-admin
  // (al 3-lea gate) a fost STEARSA — DTAC+PT e live pentru toti; default-ul fazei e 'DTAC'
  // (ieftin, 1/mp), PT-ul e opt-in constient (costul 3x e afisat in preview inainte de generare).

  // Tab-urile Planșă + Materiale apar DOAR pe faza PT (DTAC+PT). isPhasePT robust la format.
  const showPlanBom = isPhasePT(result?.output_phase ?? result?.project_info?.faza ?? "");
  // Editor vizual (PASUL 3.1): planșa de iluminat SELECTATĂ (M2b: editorPlansaIdx selectabil, nu fix [0]).
  const planseIluminat = result?.planse_iluminat || [];
  const editorPlansa = planseIluminat[editorPlansaIdx] || null;
  // Baza CURATĂ a planșei curente (arhitectural + cartuș, FĂRĂ becuri) = sursă pt. fundalul forței + prop backend.
  const fortaCleanBase = (result?.planuri || []).find(p => p.plansa_nr === editorPlansa?.source_plansa_nr)?.pdf_base64 || null;
  // CONSECVENȚĂ nume (Dan): numerotarea REALĂ din mirror (compute_plansa_numbering) — schemele din
  // result_data au plansa_nr STALE (numerotate în universul lor: prima schemă = IE.1, coliziune cu
  // planurile). Afișajul + numele fișierului se derivă local, universal (și pe proiectele vechi).
  const plansaNum = useMemo(() => (result ? plansaNumberingFromResult(result) : []), [result]);
  const schemasMapped = useMemo(
    () => (result?.schemas?.length ? mapSchemasToNumbering(result.schemas, plansaNum) : []),
    [result, plansaNum]
  );
  // Mod FORȚĂ: cere PNG-ul bazei CURATE (o dată per planșă/bază) -> fundal fără iluminatul învechit.
  // Iluminat / lipsă bază -> fără fetch. Cleanup pe schimbare mod/planșă (evită fundal stale).
  // PREINCARCA fundalul curat de forta de indata ce avem baza (independent de mod) -> cand utilizatorul
  // trece pe forta, PNG-ul e deja gata (timp mort ~ZERO). Bulletproof: r.ok + success verificate; esec ->
  // NICIODATA dump JSON in UI (doar console.error) + fallback pe fundalul iluminat (calculat mai jos).
  useEffect(() => {
    if (!fortaCleanBase) { setFortaBg(null); setFortaBgErr(false); return; }
    let cancelled = false;
    setFortaBg(null); setFortaBgErr(false);
    fetch("/api/render-base-png", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pdf_base64: fortaCleanBase }),
    })
      .then(async r => {
        if (!r.ok) throw new Error(`render-base-png HTTP ${r.status}`);
        return r.json();
      })
      .then(d => {
        if (cancelled) return;
        if (d?.success && d.png_base64) setFortaBg({ png_base64: d.png_base64, png_meta: d.png_meta || {} });
        else throw new Error(d?.error || "render-base-png: raspuns fara png");
      })
      .catch(err => { if (!cancelled) { console.error("[render-base-png]", err); setFortaBgErr(true); } });
    return () => { cancelled = true; };
  }, [fortaCleanBase, editorPlansaIdx]);
  // Etajele EDITABILE (cu PNG) = opțiunile selectorului de etaj. >1 -> multi-etaj (selector vizibil).
  const editablePlanse = planseIluminat
    .map((p, idx) => ({ idx, p }))
    .filter((x) => !!x.p.png_base64);
  const multiFloor = editablePlanse.length > 1;
  // M3: forța per etaj PERSISTATĂ în planse_forta[idx].regenerated (înlocuiește fortaDoneIdxs din sesiune).
  const planseForta = result?.planse_forta || [];
  const fortaDone = (idx: number) => planseForta[idx]?.regenerated === true;
  const floorName = (idx: number) => {
    const c = floorCanonic(idx);
    return c.charAt(0).toUpperCase() + c.slice(1);   // "Parter"/"Etaj"/"Mansarda"
  };
  // M1: camere scopate pe etajul SELECTAT (floorIndex robust la cele 3 codificări).
  // Proiecte vechi/single-floor cu floor=null -> parter (index 0) = zero regresie.
  const roomsScoped = (result?.rooms ?? []).filter(
    (r) => floorIndex((r as { floor?: string | number | null }).floor) === editorPlansaIdx
  );
  // Editor full-width (PASUL 3.5): tab Editor -> ascunde formularul + lateste planul pe tot ecranul.
  const editorFull = activeTab === "editor" && !!result;

  // ── R2 (resume): /configurator?resume=<uuid> -> REHIDRATEAZA proiectul salvat (form + echipamente +
  // result + editor) si intra DIRECT pe etapa corecta, fara re-generare. Datele exista integral in DB:
  // input_data = formularul complet, result_data = planse (PNG editor + PDF) + documente, plan_elements
  // = elementele editorului (PlanEditor le citeste pe savedProjectId). Ruleaza O DATA, dupa login. ──
  const resumeTriedRef = useRef(false);
  const resumeModeRef = useRef<"iluminat" | "forta" | null>(null);
  // FIX 4 (prize automat): proiect FINALIZAT re-deschis (resume) -> editorul NU auto-genereaza
  // prize (zero scrieri automate pe proiecte inchise). Sesiunile noi raman false (finalized se
  // seteaza abia la "Finalizeaza", care navigheaza afara din configurator).
  const [resumedFinalized, setResumedFinalized] = useState(false);
  useEffect(() => {
    if (!user || resumeTriedRef.current) return;
    const rid = typeof window !== "undefined"
      ? new URLSearchParams(window.location.search).get("resume") : null;
    if (!rid) return;
    resumeTriedRef.current = true;
    const supabase = createClient();
    supabase.from("projects").select("id, input_data, result_data, finalized")
      .eq("id", rid).eq("user_id", user.id).single()
      .then(({ data, error }) => {
        if (error || !data?.result_data) {
          console.error("[resume] proiect negasit / fara result_data:", error?.message);
          return;                                        // ramane formularul gol (comportamentul normal)
        }
        setResumedFinalized(!!(data as { finalized?: boolean | null }).finalized);
        const inp = (data.input_data || {}) as Record<string, unknown>;
        const rd = data.result_data as ProjectResult;
        // formularul: DOAR cheile FormData (input_data contine si extra: planuri base64, user_id, climate...)
        const patch: Partial<FormData> = {};
        for (const k of Object.keys(INITIAL_FORM) as (keyof FormData)[]) {
          if (k in inp) (patch as Record<string, unknown>)[k] = inp[k];
        }
        setForm(prev => ({ ...prev, ...patch }));
        // echipamentele BIFATE la generare (gating-ul H5/H6 al paletei functioneaza pe starea rehidratata)
        const extra = Array.isArray(inp.extra_equipment) ? (inp.extra_equipment as ExtraEquipment[]) : [];
        setEquipment(prev => {
          const next = { ...prev };
          for (const e of extra) {
            if (e?.type && e.type !== "custom" && next[e.type]) {
              if (e.type === "solar") {
                // FV backward-compat: proiecte vechi cu power_kw liber (10.3) -> snap la pachet + tri;
                // soil_type absent (pre-G-UI) -> agricol
                next[e.type] = { enabled: true, power_kw: snapFvPackage(e.package_kw ?? e.power_kw),
                                 phase: "tri", soil_type: String(e.soil_type || FV_SOIL_DEFAULT) };
              } else {
                next[e.type] = { enabled: true, power_kw: Number(e.power_kw) || next[e.type].power_kw,
                                 phase: String(e.phase || next[e.type].phase) };
              }
            }
          }
          return next;
        });
        setCustomEquipment(extra.filter(e => e?.type === "custom").map(e => ({
          name: String(e.name || ""), room: String((e as { room?: string }).room || ""),
          power_kw: Number(e.power_kw) || 0, phase: String(e.phase || "mono"),
        })));
        const mf = parseInt(String(inp.floors_above_ground ?? ""), 10);
        if (Number.isFinite(mf)) setManualFloors(mf);
        // ETAPA: vreo plansa de iluminat (editabila, cu PNG) fara "Obtine plan iluminat" -> ILUMINAT;
        // iluminat complet + proiect PT -> FORTA (gating-ul existent fazaFlux ramane autoritar la randare).
        const il = (rd.planse_iluminat || []).filter(p => (p as { png_base64?: string })?.png_base64);
        const ilDone = il.length > 0 && il.every(p => (p as { regenerated?: boolean })?.regenerated === true);
        resumeModeRef.current = (ilDone && isPhasePT((rd as { phase?: string }).phase)) ? "forta" : "iluminat";
        setResult(rd);
        setSavedProjectId(String(data.id));               // PlanEditor citeste plan_elements pe acest uuid
        setStatus("success");                             // UI-ul post-generare (tab-uri + documente)
        setActiveTab("editor");                           // direct pe editor (etapa din resumeModeRef)
      });
  }, [user]);

  // M2b: la schimbarea proiectului -> resetează etajul selectat (parter) + tracking forță + mod iluminat.
  // R2: la RESUME, modul vine din resumeModeRef (etapa detectata) — altfel reset pe iluminat, ca inainte.
  useEffect(() => {
    setEditorPlansaIdx(0);
    setModeEditor(resumeModeRef.current || "iluminat");
    resumeModeRef.current = null;
  }, [savedProjectId]);

  // ── FLUX FORTA (S1): starea fazei din semnale EXISTENTE (zero migratie). ──
  // editorAvailable = tab-ul Editor e disponibil (PT + plansa cu PNG + proiect salvat) — aceeasi conditie ca filtrul de tab.
  const editorAvailable = showPlanBom && !!editorPlansa && !!savedProjectId;
  // iluminatFinalizat = IE.1 generat ("Obtine plan iluminat" -> regenerated=true, semnal persistent in result_data).
  const iluminatFinalizat = editorPlansa?.regenerated === true;
  // faza fluxului: iluminat fara IE.1 -> "iluminat-nedefinitivat"; cu IE.1 -> "iluminat-gata"; pe forta -> "forta".
  const fazaFlux: "iluminat-nedefinitivat" | "iluminat-gata" | "forta" =
    !iluminatFinalizat ? "iluminat-nedefinitivat" : modeEditor === "forta" ? "forta" : "iluminat-gata";

  // "Obține plan" (1d): PDF regenerat (cabluri + editări) INLOCUIESTE ciorna Vision in result + se persista.
  async function handleRegenerated(pdfBase64: string, mode: "iluminat" | "forta", plansaNr?: string) {
    if (!result || !editorPlansa || !savedProjectId) return;
    // M3: construiește result_data pe mod, apoi PERSISTĂ o singură dată în Supabase.
    let updated: ProjectResult;
    if (mode === "forta") {
      // planse_forta = oglindă planse_iluminat (per etaj). Lazy-init la prima forță; marchează etajul curent.
      // PAS 2: metadata de FORȚĂ (nu clonată de la iluminat): type=plan_forta + name „— FORȚĂ";
      // source_plansa_nr = numărul FINAL IE.N stampat de backend (fallback: cel moștenit).
      const base = (result.planse_forta && result.planse_forta.length === planseIluminat.length)
        ? result.planse_forta
        : planseIluminat.map(p => ({ type: "plan_forta",
                                     name: `${(p.name || "PLAN").replace(/\s*—\s*ILUMINAT\s*$/, "")} — FORȚĂ`,
                                     source_plansa_nr: p.source_plansa_nr,
                                     pdf_base64: "", regenerated: false }));
      updated = {
        ...result,
        planse_forta: base.map((f, i) => i === editorPlansaIdx
          ? { ...f, pdf_base64: pdfBase64, regenerated: true, type: "plan_forta",
              name: `${(f.name || "PLAN").replace(/\s*—\s*(ILUMINAT|FORȚĂ)\s*$/, "")} — FORȚĂ`,
              ...(plansaNr ? { source_plansa_nr: plansaNr } : {}),
              filename: `Plan_forta_${floorCanonic(editorPlansaIdx)}.pdf` }
          : f),
      };
    } else {
      updated = {
        ...result,
        planse_iluminat: (result.planse_iluminat || []).map(p =>
          p === editorPlansa ? { ...p, pdf_base64: pdfBase64, regenerated: true } : p),
      };
    }
    setResult(updated);
    try {
      const supabase = createClient();
      const { error } = await supabase.from("projects").update({ result_data: updated }).eq("id", savedProjectId);
      if (error) console.error("[regenerate] persist result_data esuat:", error.message);
    } catch (e) {
      console.error("[regenerate] persist exception:", e);
    }
  }
  useEffect(() => {
    if (!showPlanBom && (activeTab === "plan" || activeTab === "bom")) setActiveTab("circuits");
  }, [showPlanBom, activeTab]);

  // S5: dupa generare PORNESTE in tab-ul Editor (iluminat), nu pe Circuite — ca inginerul sa intre
  // in flux (iluminat -> forta), nu sa vada direct "Finalizare". O SINGURA data per proiect (apoi
  // navigheaza liber). Editor indisponibil (DTAC / fara plansa) -> ramane pe circuits (zero regresie).
  const autoEditorRef = useRef(false);
  useEffect(() => {
    if (status !== "success") { autoEditorRef.current = false; return; }   // reset pt. urmatorul proiect
    if (editorAvailable && !autoEditorRef.current) {
      autoEditorRef.current = true;
      setActiveTab("editor");
    }
  }, [status, editorAvailable]);

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
    Number(form.surface_mp) > 0 &&   // FIX billing (P0-1): suprafata OBLIGATORIE (serverul respinge surface<=0)
    files.length > 0
  );
  // Epic 3.11: butonul Generează e activ când formularul de bază e complet (fără cartuș —
  // cartușul se confirmă în popup-ul declanșat de Generează). canSubmit (cu cartuș confirmat)
  // gateează rularea efectivă a backend-ului.
  const canSubmitBasic = formReady;   // limita de 3 proiecte eliminata (trecem pe credite)
  const canSubmit = canSubmitBasic && cartusConfirmed;

  useEffect(() => {
    if (!saveMessage) return;
    const t = setTimeout(() => setSaveMessage(null), 4000);
    return () => clearTimeout(t);
  }, [saveMessage]);

  // Epic 3.11: Vision NU mai rulează la upload. Rulează doar la click pe "Generează"
  // (vezi handleGenerate). Aici doar resetăm confirmarea cartușului dacă se schimbă planurile.
  useEffect(() => {
    const key = files.map(f => `${f.name}:${f.size}:${f.lastModified}`).join("|");
    if (visionAnalyzedRef.current !== key) {
      visionAnalyzedRef.current = key;
      setCartusConfirmed(false);
    }
  }, [files]);

  // Reset subtype when category changes
  const handleCategoryChange = (v: string) => {
    update("building_category", v);
    update("building_type", "");
  };

  async function fetchCartusFirma(): Promise<CartusFirma> {
    const supabase = createClient();
    const { data: { user: u } } = await supabase.auth.getUser();
    if (!u) return EMPTY_CARTUS_FIRMA;
    const { data, error } = await supabase
      .from('profiles')
      .select('firma_nume,firma_cui,firma_reg_com,firma_tel,firma_email,firma_adresa,firma_logo_url,proiectant_nume,desenator_nume')
      .eq('id', u.id)
      .single();
    if (error || !data) {
      console.warn('[Zynapse] Nu s-a putut citi profile pentru cartuș:', error?.message);
      return EMPTY_CARTUS_FIRMA;
    }
    return {
      firma_nume:       data.firma_nume       ?? '',
      firma_cui:        data.firma_cui        ?? '',
      firma_reg_com:    data.firma_reg_com    ?? '',
      firma_tel:        data.firma_tel        ?? '',
      firma_email:      data.firma_email      ?? '',
      firma_adresa:     data.firma_adresa     ?? '',
      firma_logo_url:   data.firma_logo_url   ?? '',
      proiectant_nume:  data.proiectant_nume  ?? '',
      desenator_nume:   data.desenator_nume   ?? '',
    };
  }

  function buildCartusProiect(override?: CartusProiect): CartusProiect {
    // Fallback data_proiect ca MM.YYYY (format cartuș) dacă userul nu a completat.
    // override = datele confirmate in modal (evita stale closure cand runBackend e
    // apelat imediat dupa setCartusProiectInput, inainte ca state-ul sa se actualizeze).
    const now = new Date();
    const mmYyyy = `${String(now.getMonth() + 1).padStart(2, '0')}.${now.getFullYear()}`;
    const src = override ?? cartusProiectInput;
    return {
      ...src,
      data_proiect: src.data_proiect || mmYyyy,
    };
  }

  // Epic 3.11: pas 1 — la click pe "Generează", rulează Vision pe primul plan (parter),
  // apoi deschide modalul de confirmare cartuș. Dacă cartușul e deja confirmat, sare direct
  // la backend (permite re-generare fără a re-rula Vision).
  const handleGenerate = async () => {
    if (!canSubmitBasic || status === "loading" || visionCartusLoading) return;

    // HOLD SIMPLU (verificare sold, informativ): blocheaza ÎNAINTE de generare daca soldul
    // nu acopera costul. Consumul real + verificarea autoritara se fac in DB la succes.
    const holdCost = genCostZ(form.surface_mp, cartusProiectInput.faza);
    const holdBal = profile?.credits_balance ?? 0;
    if (user && holdCost > 0 && holdBal < holdCost) {
      setError(`Sold insuficient: ai nevoie de ${holdCost} Z-Coins, ai ${holdBal}. Cumpara credite din pagina principala (Acasa).`);
      setStatus("error");
      return;
    }

    // ── POARTA DE VALIDARE (determinista, FARA AI) — INAINTE de vision-cartus (primul consum
    // Anthropic), de lock si de credite. Raster (PDF scanat) = BLOCARE HARD; "nu pare plan de
    // arhitectura" (0 camere cu arie + <20 pereti) = WARNING cu override (faza 1). Imaginile
    // (JPG/PNG) NU trec prin poarta (comportament neschimbat). Poarta e DEFENSIVA: orice eroare
    // a ei (retea/backend) -> permite generarea (nu blocam useri pe bug-urile portii).
    setVisionCartusLoading(true);
    try {
      for (const f of files) {
        if ((f.type || "") !== "application/pdf") continue;
        const b64 = await fileToBase64(f);
        const vres = await fetch("/api/validate-plan", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ pdf_base64: b64 }),
        });
        const v = await vres.json().catch(() => null);
        if (v?.status === "rejected") {
          setVisionCartusLoading(false);
          setError(`„${f.name}": ${v.message || "PDF invalid."}`);
          setStatus("error");
          return;                                   // HARD: 0 Anthropic, 0 lock, 0 credite
        }
        if (v?.status === "warning") {
          const go = window.confirm(`„${f.name}": ${v.message}\n\nContinuă oricum?`);
          if (!go) { setVisionCartusLoading(false); return; }   // userul a anulat: 0 consum
        }
      }
    } catch (e) {
      console.warn("[validate-plan] poarta a esuat, continuam defensiv:", e);
    }

    if (cartusConfirmed) { setVisionCartusLoading(false); void runBackend(); return; }

    setVisionSurfaces(null);   // reset la fiecare incercare; setat din raspuns daca exista
    try {
      const fd = new FormData();
      fd.append("plan", files[0]); // primul plan = parter
      const res = await fetch("/api/vision-cartus", { method: "POST", body: fd });
      if (res.ok) {
        const cartus = await res.json();
        // FIX faza: selectia UI (FazaProiectChips -> prev.faza) CASTIGA ca default in modal.
        // Vision-cartus extrage titlu/beneficiar/etc., dar NU suprascrie faza aleasa de user
        // (altfel DTAC din UI ajungea DTAC+PT in modal -> cost 3x gresit). Userul o poate
        // schimba in modal daca vrea (select editabil).
        setCartusProiectInput(prev => ({
          titlu_proiect: cartus.titlu_proiect || "",
          beneficiar:    cartus.beneficiar    || "",
          amplasament:   cartus.amplasament   || "",
          sef_proiect:   cartus.sef_proiect   || "",
          numar_proiect: cartus.numar_proiect || "",
          data_proiect:  cartus.data_proiect  || "",
          faza:          prev.faza,
        }));
        // Pas 2: capturam surfaces (poate fi null daca Vision nu le-a gasit) — null -> fallback manual la Pas 3
        setVisionSurfaces((cartus.surfaces && typeof cartus.surfaces === "object") ? cartus.surfaces : null);
      }
      // Dacă Vision eșuează → câmpurile rămân goale; userul le completează în modal.
    } catch (e) {
      console.error("[Vision Cartus] Failed:", e);
    } finally {
      setVisionCartusLoading(false);
      setShowCartusModal(true); // modal apare automat (succes sau eșec)
    }
  };

  // Epic 3.11: pas 2 — după confirmarea cartușului, rulează efectiv backend-ul.
  // cartusOverride = datele confirmate in modal, pasate direct (nu prin state) ca sa
  // evite stale closure (setCartusProiectInput e asincron).
  const runBackend = async (cartusOverride?: CartusProiect) => {
    if (status === "loading") return;
    setStatus("loading"); setError(null); setResult(null); setStepIndex(0);

    try {
      setStepIndex(0);
      const base64 = await fileToBase64(files[0]);
      // Faza B.1: encodează TOATE planurile (parter/etaj/mansardă) pentru backend multi-etaj.
      // Non-breaking: plan_base64 (parter) rămâne pentru flow-ul JSON existent; backend-ul
      // actual ignoră plan_floors_base64 până la Faza B.2.
      const planFloorsBase64 = await Promise.all(
        files.map(async (f) => ({
          base64: await fileToBase64(f),
          plan_type: f.type || "image/jpeg",
          filename: f.name,
        }))
      );

      setStepIndex(1);
      const extra_equipment: ExtraEquipment[] = [
        ...EXTRA_EQUIPMENT_DEFAULTS
          .filter(e => equipment[e.type]?.enabled)
          .map(e => e.fvPackage ? {
            // FV: pachet discret + mereu trifazat (power_kw = pachetul, compat n8n; package_kw = sursa schemei FV)
            type: e.type,
            name: e.label,
            power_kw: snapFvPackage(equipment[e.type].power_kw),
            package_kw: snapFvPackage(equipment[e.type].power_kw),
            phase: "tri",
            phases: 3,
            // G-UI: solul prizei de pamant FV (BOM + breviar); absent -> agricol (fallback backend)
            soil_type: equipment[e.type].soil_type || FV_SOIL_DEFAULT,
          } : {
            type: e.type,
            name: e.label,
            power_kw: equipment[e.type].power_kw,
            phase: equipment[e.type].phase,
            // numeric phases pentru backend (mono/none → 1, tri → 3)
            phases: equipment[e.type].phase === "tri" ? 3 : 1,
          }),
        ...customEquipment
          .filter(e => e.name.trim())
          .map(e => ({ type: "custom", ...e, phases: e.phase === "tri" ? 3 : 1 })),
      ];

      // Mapare heating_type frontend → heating_system pentru backend n8n.
      // Backend-ul citește wb.heating_system.enabled + source_category (heating_type e ignorat).
      // Cheile = valorile REALE din HEATING_GENERATION (lib/constants.ts).
      // Doar pdc_aer / pdc_geo / centrala_electrica activează TE-CT (vezi TECT_CATEGORIES în n8n);
      // centrala_gaz / termoficare → circuit dedicat în TEG, fără TE-CT; "existing" → fără sistem nou.
      const HEATING_TYPE_TO_CATEGORY: Record<string, string> = {
        pdc_air_water: "pdc_aer",            // Pompă de căldură aer-apă
        pdc_ground_water: "pdc_geo",         // Pompă de căldură sol-apă (geotermală)
        electric_boiler: "centrala_electrica", // Centrală electrică
        gas_boiler: "centrala_gaz",          // Centrală pe gaz
        district_heating: "termoficare",     // Termoficare (rețea urbană)
      };

      const heatingCategory = HEATING_TYPE_TO_CATEGORY[form.heating_type] || null;
      const heatingSystem = heatingCategory ? {
        enabled: true,
        source_category: heatingCategory,
        phases: form.power_phase === "tri" ? 3 : 1,
        rezistenta_backup: false,
      } : null;

      const payload: Record<string, unknown> = {
        // Faza B.1/B.2: multi-etaj — index 0 = parter, 1 = etaj, 2 = mansardă (ordinea din UI)
        plan_floors_base64: planFloorsBase64,
        floors_count: files.length,
        has_etaj: files.length >= 2,
        has_mansarda: files.length >= 3,
        // plan_base64 (legacy) — trimis DOAR pentru 1 plan (ramura Vision veche).
        // La multi-plan e redundant (parter e deja în plan_floors_base64[0]) → evită duplicarea.
        ...(files.length === 1 ? { plan_base64: base64, plan_type: files[0].type || "image/jpeg" } : {}),
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
        heating_system: heatingSystem,
        heating_distribution: form.heating_distribution,
        extra_equipment,
        ...(form.building_type === "bloc_locuinte" && form.floors ? { floors: parseInt(form.floors) } : {}),
        ...(form.building_type === "bloc_locuinte" && form.apartments_per_floor ? { apartments_per_floor: parseInt(form.apartments_per_floor) } : {}),
        ...(form.building_category === "industrial" && motors.length > 0 ? { motors } : {}),
      };

      console.log("PAYLOAD TRIMIS:", JSON.stringify({
        building_category: form.building_category,
        building_type: form.building_type,
      }, null, 2));

      const cartus_firma = await fetchCartusFirma();
      const cartus_proiect = buildCartusProiect(cartusOverride);

      setStepIndex(2);
      const res = await fetch(WEBHOOK_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...payload,
          cartus_firma,
          cartus_proiect,
          ...(pageFormat ? { page_format: pageFormat } : {}),
        }),
      });

      setStepIndex(3);

      // Citim ca text mai întâi (proxy-ul poate întoarce non-JSON la 504)
      const rawText = await res.text();
      let data: ProjectResult;
      try {
        data = JSON.parse(rawText);
      } catch {
        throw new Error("Răspuns invalid de la server (posibil timeout). Încearcă din nou sau cu mai puține planuri.");
      }
      console.log("WEBHOOK RESPONSE:", data);

      // Verificăm statusul HTTP: proxy-ul /api/generate întoarce 502 la timeout/eroare upstream
      if (!res.ok) {
        const msg = (data as any)?.details
          || (data as any)?.error
          || `Eroare de procesare (HTTP ${res.status}). Încearcă din nou.`;
        throw new Error(msg);
      }

      // n8n poate întoarce 200 cu shape {status:"error"}
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
        // SERVER-FIRST: /api/generate persistă + debitează pe succes, server-side (nu depinde de client),
        // și întoarce `saved_project_id`. PREZENT -> folosim id-ul lui (NU mai inserăm -> fără dublu proiect);
        // refacem DOAR consume_credits (idempotent pe project_id) ca plasă de siguranță dacă consume-ul
        // server a eșuat; NU increment (server l-a făcut, e NEidempotent -> dublă-numărare). ABSENT (INSERT
        // server eșuat) -> calea VECHE completă (insert+consume+increment) -> degradare grațioasă.
        const serverProjectId = (data as { saved_project_id?: string }).saved_project_id;
        const consumeFaza = cartusOverride?.faza ?? cartusProiectInput.faza;
        let projectUuid: string | null = serverProjectId ?? null;
        let insertError: unknown = null;
        let msg = "Proiect salvat cu succes";

        if (!projectUuid) {
          const { data: inserted, error } = await supabase.from("projects").insert({
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
          }).select("id").single();
          insertError = error;
          projectUuid = inserted?.id ?? null;
        }

        if (insertError || !projectUuid) {
          console.error("[save project] insert error:", insertError);
          setSaveMessage("Proiectul a fost generat, dar salvarea în istoric a eșuat. Descarcă-l acum din rezultate.");
        } else {
          setSavedProjectId(projectUuid);   // pt. tab-ul Editor (citește plan_elements pe acest uuid)
          // CONSUME idempotent pe project_id (id-ul REAL, server sau fallback): no-op dacă serverul a
          // debitat deja; debitează dacă serverul a eșuat. NICIODATĂ dublă-debitare (același project_id).
          try {
            const { data: consumeRes, error: consumeErr } = await supabase.rpc("consume_credits", {
              p_surface_mp: form.surface_mp,
              p_phase: consumeFaza,
              p_project_id: projectUuid,
            });
            if (consumeErr) {
              console.error("[consume_credits] error:", consumeErr);
            } else if (consumeRes && (consumeRes as { success?: boolean }).success === false) {
              console.warn("[consume_credits] insuficient la consum:", consumeRes);
              msg = "Proiect generat. Atenție: soldul de Z-Coins nu a putut fi debitat (sold insuficient la finalizare).";
            }
          } catch (e) {
            console.error("[consume_credits] exception:", e);
          }
          // INCREMENT doar dacă serverul NU a persistat (NEidempotent -> evită dubla-numărare).
          if (!serverProjectId) {
            const { error: rpcError } = await supabase.rpc("increment_projects_used");
            if (rpcError) console.error("[save project] increment error:", rpcError);
          }

          // ADITIV + NON-BLOCANT: populează plan_elements (becuri) pentru editorul interactiv.
          // RLS permite owner-ului autenticat INSERT (plan_elements_insert_own). ORICE eroare aici
          // NU afectează proiectul/planul (deja salvate + afișate) — doar log. Proiect nou la fiecare
          // generare (uuid nou) -> fără duplicate. Faza DTAC (fără planse_iluminat/centers) -> 0 elemente.
          try {
            if (projectUuid) {
              const planElements: Array<Record<string, unknown>> = [];
              for (const [idx, plansa] of (data.planse_iluminat || []).entries()) {
                // M2a: floor CANONIC din INDEXUL planșei (0=parter/1=etaj/2=mansarda) — robust,
                // aliniat cu rooms[].floor + plan_elements. Elimină vechiul "etaj1".
                const floor = floorCanonic(idx);
                for (const c of (plansa.centers || [])) {
                  planElements.push({
                    project_id: projectUuid,
                    floor,
                    // tip + putere din REGULA backend (_bulb_rule_for_room, prin detected.centers) —
                    // aceeasi sursa ca desenul PDF; fallback pe default-urile vechi (raspuns fara campuri).
                    element_type: c.element_type || "aplica_tavan",
                    plan_type: "iluminat",          // becurile apar DOAR pe planșa de iluminat
                    label: null,
                    room: c.label || null,
                    x: c.x,
                    y: c.y,
                    wall_mounted: false,
                    rotation: 0,
                    power_w: c.power_w ?? 25,       // editabil in meniu; apare si in eticheta "Lustra LED 40W"
                  });
                }
                for (const sw of (plansa.switches || [])) {
                  planElements.push({
                    project_id: projectUuid,
                    floor,
                    element_type: "intrerupator_simplu",
                    plan_type: "iluminat",          // întrerupătoarele apar DOAR pe planșa de iluminat
                    label: null,
                    // sw.room = NUMELE camerei, rezolvat în backend din index (sau null). Nu mai ghicim.
                    room: sw.room || null,
                    x: sw.x,
                    y: sw.y,
                    wall_mounted: true,             // întrerupătoarele sunt pe perete
                    rotation: sw.angle || 0,
                  });
                }
              }
              if (planElements.length > 0) {
                const { error: peError } = await supabase.from("plan_elements").insert(planElements);
                if (peError) console.error("[plan_elements] insert failed:", peError);
                else console.log(`[plan_elements] inserted ${planElements.length} elements`);
              }
            }
          } catch (e) {
            console.error("[plan_elements] insert exception:", e);
          }

          await refreshProfile();   // re-fetch -> soldul nou apare imediat in UI
          setSaveMessage(msg);
        }
      }

      setResult(data);
      setStatus("success");
    } catch (err: any) {
      setError(err.message || "Eroare de conexiune la n8n");
      setStatus("error");
      // FIX 1: pe eroare DEBLOCHEAZA panoul (reset cartusConfirmed -> blocked devine false).
      // Userul poate corecta datele si reincerca (re-ruleaza Vision + modal).
      setCartusConfirmed(false);
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
  // Blocheaza panoul stang din momentul CONFIRMARII modalului de cartus (cand incepe generarea
  // reala), prin loading, pana la success. Asa userul nu poate modifica date care nu se mai
  // reflecta in proiectul ce se genereaza, nici re-apasa Genereaza -> alt project_id -> consum dublu.
  // cartusConfirmed = confirmat in modal; loading = generare in curs; success = gata.
  // 'error' NU e inclus si cartusConfirmed se reseteaza pe error -> panoul se deblocheaza (retry).
  const blocked = cartusConfirmed || status === "loading" || status === "success";

  // "Proiect nou": curata COMPLET starea -> re-activeaza panoul pentru un proiect nou.
  const resetForNewProject = () => {
    setStatus("idle");
    setResult(null);
    setError(null);
    setSaveMessage(null);
    setStepIndex(0);
    setForm(INITIAL_FORM);
    setFiles([]);
    setMotors([]);
    setManualFloors(0);
    setEquipment(Object.fromEntries(EXTRA_EQUIPMENT_DEFAULTS.map(e => [e.type, { enabled: false, power_kw: e.default_kw, phase: e.default_phase }])));
    setCustomEquipment([]);
    setAutoDetected(null);
    setActiveTab("circuits");
    setPageFormat("");
    setCartusProiectInput({ beneficiar: "", amplasament: "", titlu_proiect: "", numar_proiect: "", faza: "DTAC", sef_proiect: "", data_proiect: "" });
    setVisionSurfaces(null);
    setShowCartusModal(false);
    setCartusConfirmed(false);
    setVisionCartusLoading(false);
    visionAnalyzedRef.current = null;
    if (typeof window !== "undefined") window.scrollTo({ top: 0, behavior: "smooth" });
  };

  // "Finalizare Proiect": calea principala de incheiere -> /projects (proiectul e deja salvat
  // la succes). Handler (nu Link direct) ca sa fie usor de extins: aici se va insera ulterior
  // un modal de feedback (nota 1-10 + nemultumiri daca <5) INAINTE de redirect. Acum doar navigheaza.
  const handleFinalize = () => {
    router.push("/projects");
  };

  // Faza 2b — "Finalizeaza documentele": genereaza schema monofilara + memoriu + BOM din datele
  // FINALE ale proiectului (via /api/finalize -> webhook n8n zynapse-finalize), le stocheaza in
  // result_data si marcheaza finalized=true. Model de UI: handleRegenerated. Proiect fara editor
  // (non-PT, fara aceste documente) -> cade pe iesirea clasica.
  async function handleFinalizeDocs() {
    if (!result || !savedProjectId) { handleFinalize(); return; }
    setFinalizeLoading(true);
    setFinalizeErr(null);
    try {
      const res = await fetch("/api/finalize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_id: savedProjectId }),
      });
      const data = await res.json();
      if (!res.ok || data?.success === false || data?.error) {
        setFinalizeErr(data?.error || "Finalizare esuata.");
        setFinalizeLoading(false);
        return;
      }
      // Merge documentele proaspete in result + persista result_data + finalized=true (o singura scriere).
      const updated: ProjectResult = {
        ...result,
        schemas: data.schemas ?? result.schemas,
        schema_monofilara_pdf: data.schema_monofilara_pdf ?? result.schema_monofilara_pdf,
        memoriu_docx_base64: data.memoriu_docx_base64 ?? result.memoriu_docx_base64,
        bom: data.bom ?? result.bom,
        bom_source: data.bom_source ?? result.bom_source,   // "plan (unified)" | "n8n (fallback)"
        // UNIFICARE: circuitele enrich (plan) -> tabelul UI (circuits_te_ct/teg) = documentele.
        circuits: data.circuits ?? result.circuits,
        circuits_te_ct: data.circuits_te_ct ?? result.circuits_te_ct,
        circuits_teg: data.circuits_teg ?? result.circuits_teg,
        circuits_all: data.circuits_all ?? result.circuits_all,
        circuits_source: data.circuits_source ?? result.circuits_source,
      };
      const supabase = createClient();
      // ETAPA 1 Storage (fix 03.07): memoriul PROASPAT de la finalize -> Storage pe ACELASI path
      // (upsert suprascrie versiunea de la generare), base64 STERS din result_data -> volumul nu
      // se dubleaza (inainte: finalize re-adauga base64 langa path -> result_data nu scadea).
      // Fallback: orice esec la upload -> base64 ramane (download-ul merge, nimic pierdut).
      try {
        const freshB64 = typeof updated.memoriu_docx_base64 === "string" ? updated.memoriu_docx_base64 : "";
        if (freshB64.length > 100 && user && savedProjectId) {
          const storagePath = `${user.id}/${savedProjectId}/memoriu.docx`;
          const raw = freshB64.includes(",") ? freshB64.split(",")[1] : freshB64;
          const byteStr = atob(raw);
          const bytes = new Uint8Array(byteStr.length);
          for (let i = 0; i < byteStr.length; i++) bytes[i] = byteStr.charCodeAt(i);
          const { error: upErr } = await supabase.storage
            .from("project-files")
            .upload(storagePath, new Blob([bytes], {
              type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            }), { upsert: true });
          if (!upErr) {
            updated.memoriu_docx_path = storagePath;
            delete updated.memoriu_docx_base64;   // ramane DOAR referinta (citirea cade pe Storage)
          } else {
            console.error("[finalize] upload memoriu in Storage esuat (fallback base64):", upErr.message);
          }
        }
      } catch (e) {
        console.error("[finalize] bloc Storage memoriu esuat (fallback base64):", e);
      }
      // ETAPA 2 Storage: schema monofilara PROASPATA de la finalize -> Storage pe acelasi path
      // (upsert suprascrie versiunea de la generare) + sterge scalarul base64. Duplicatul VECHI
      // schema_monofilara_pdf_base64 (adus de spread ...result, necitit nicaieri) se sterge MEREU.
      try {
        delete (updated as unknown as Record<string, unknown>).schema_monofilara_pdf_base64;   // duplicat mort
        const freshSch = typeof updated.schema_monofilara_pdf === "string" ? updated.schema_monofilara_pdf : "";
        if (freshSch.length > 100 && user && savedProjectId) {
          const schPath = `${user.id}/${savedProjectId}/schema_monofilara.pdf`;
          const rawSch = freshSch.includes(",") ? freshSch.split(",")[1] : freshSch;
          const schStr = atob(rawSch);
          const schBytes = new Uint8Array(schStr.length);
          for (let i = 0; i < schStr.length; i++) schBytes[i] = schStr.charCodeAt(i);
          const { error: schUpErr } = await supabase.storage
            .from("project-files")
            .upload(schPath, new Blob([schBytes], { type: "application/pdf" }), { upsert: true });
          if (!schUpErr) {
            updated.schema_monofilara_path = schPath;
            delete updated.schema_monofilara_pdf;
          } else {
            console.error("[finalize] upload schema in Storage esuat (fallback base64):", schUpErr.message);
          }
        }
      } catch (e) {
        console.error("[finalize] bloc Storage schema esuat (fallback base64):", e);
      }
      // ETAPA 3 Storage: schemas[] PROASPETE de la finalize -> Storage pe ACELEASI path-uri per
      // element (upsert suprascrie versiunile de la generare) + sterge base64 per element.
      // Bucla clasica; fallback per element (upload esuat -> acel element ramane pe base64).
      try {
        const schemasArr = Array.isArray(updated.schemas) ? updated.schemas : [];
        if (schemasArr.length > 0 && user && savedProjectId) {
          const newSchemas: NonNullable<ProjectResult["schemas"]> = [];
          for (let i = 0; i < schemasArr.length; i++) {
            const el = { ...(schemasArr[i] || {}) } as NonNullable<ProjectResult["schemas"]>[number];
            const elB64 = typeof el.pdf_base64 === "string" ? el.pdf_base64 : "";
            if (elB64.length > 100) {
              const elPath = `${user.id}/${savedProjectId}/schema_tablou_${i}.pdf`;
              const rawEl = elB64.includes(",") ? elB64.split(",")[1] : elB64;
              const bStr = atob(rawEl);
              const bArr = new Uint8Array(bStr.length);
              for (let k = 0; k < bStr.length; k++) bArr[k] = bStr.charCodeAt(k);
              const { error: elUpErr } = await supabase.storage
                .from("project-files")
                .upload(elPath, new Blob([bArr], { type: "application/pdf" }), { upsert: true });
              if (!elUpErr) {
                el.pdf_path = elPath;
                delete el.pdf_base64;
              } else {
                console.error(`[finalize] upload schemas[${i}] esuat (fallback base64):`, elUpErr.message);
              }
            }
            newSchemas.push(el);
          }
          updated.schemas = newSchemas;
        }
      } catch (e) {
        console.error("[finalize] bloc Storage schemas[] esuat (fallback base64):", e);
      }
      setResult(updated);
      const { error } = await supabase.from("projects")
        .update({ result_data: updated, finalized: true }).eq("id", savedProjectId);
      if (error) {
        setFinalizeErr("Documente generate, dar salvarea a esuat: " + error.message);
        setFinalizeLoading(false);
        return;
      }
      router.push("/projects");
    } catch (e) {
      setFinalizeErr(e instanceof Error ? e.message : "Eroare de retea.");
      setFinalizeLoading(false);
    }
  }

  // "Editor Plan Forta" (S2): iluminatul e DEJA salvat (plan_elements persistat + IE.1/regenerated).
  // Comuta editorul pe forta -> load useEffect din PlanEditor (dep mode) reincarca elementele forta.
  // Ramai in tab-ul Editor; scroll sus la editor.
  const handleGoForta = () => {
    setModeEditor("forta");
    if (typeof window !== "undefined") window.scrollTo({ top: 0, behavior: "smooth" });
  };

  // M2b: navighează la (etaj, fază) în stepper-ul multi-etaj.
  const goEditorStep = (idx: number, mode: "iluminat" | "forta") => {
    setEditorPlansaIdx(idx);
    setModeEditor(mode);
    if (typeof window !== "undefined") window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <div style={{ minHeight: "100vh", background: "#0A0B0E" }}>

      {/* ── Vision cartuș: loading overlay global ── */}
      {visionCartusLoading && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md">
          <div className="text-center">
            <div className="inline-block animate-spin rounded-full h-16 w-16 border-4 border-blue-500 border-t-transparent mb-4"></div>
            <h2 className="text-2xl font-bold text-white mb-2">Se analizează planurile...</h2>
            <p className="text-gray-400">Vision AI extrage datele din cartuș…</p>
          </div>
        </div>
      )}

      {/* ── Vision cartuș: modal confirmare → la confirm rulează backend-ul ── */}
      <CartusConfirmModal
        isOpen={showCartusModal}
        initialData={cartusProiectInput}
        surfaces={visionSurfaces}
        manualSurfaceMp={form.surface_mp}
        balance={profile?.credits_balance ?? 0}
        onConfirm={(data) => {
          setCartusProiectInput(data);
          setCartusConfirmed(true);
          setShowCartusModal(false);
          void runBackend(data); // pasează datele EDITATE direct (evită stale closure)
        }}
        onCancel={() => setShowCartusModal(false)}
      />

      {/* ── Header ── */}
      <AppHeader rightExtra={<span className="hidden sm:inline-flex"><StatusBadge status={status} /></span>} />

      {/* ── Layout ── */}
      {/* Tab Editor: o singură coloană pe toată lățimea (formularul se ascunde) ca planul să fie mare.
          Restul taburilor: layout neschimbat (formular 420px stânga + rezultat 1fr dreapta). */}
      <div className={`p-4 mx-auto grid grid-cols-1 gap-6 items-start ${editorFull ? "md:px-6 md:py-6 max-w-[1760px]" : "md:p-8 max-w-[1280px] md:grid-cols-[420px_1fr]"}`}>

        {/* ── Form panel ── (ascuns în tab Editor: display:none, fără remount -> state-ul formularului rămâne) */}
        <div className={`rounded-2xl p-6 md:sticky md:top-[58px] md:max-h-[calc(100vh-82px)] md:overflow-y-auto ${editorFull ? "hidden" : ""}`}
          style={{ background: "rgba(255,255,255,0.025)", border: "1px solid rgba(255,255,255,0.07)" }}>

          <div className="mb-5">
            <h1 className="text-lg font-bold tracking-tight m-0" style={{ color: "#E2E4E9" }}>Configurator proiect</h1>
            <p className="text-[13px] mt-1 m-0" style={{ color: "#545870" }}>Încarcă planșele și completează datele clădirii</p>
          </div>

          {/* Dupa succes: panoul de inputuri e blocat (pointer-events:none) ca sa nu se poata
              modifica/re-trimite datele unui proiect deja generat. Butonul de reset e in afara. */}
          <div aria-disabled={blocked}
            style={{ pointerEvents: blocked ? "none" : undefined, opacity: blocked ? 0.45 : 1, transition: "opacity 0.2s ease" }}>

          {/* limita de 3 proiecte ELIMINATA — trecem pe credite (Z-Coins, pasul 3) */}

          {/* 1. Upload (Epic 3.11: multi-plan cu etichete Parter/Etaj/Mansardă) */}
          <MultiFileDropZone files={files} onChange={setFiles} maxFiles={3} />

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

          {/* Faza proiect (Epic 3.11) — bound la cartusProiectInput.faza */}
          <SectionLabel>Faza proiect</SectionLabel>
          <FazaProiectChips value={cartusProiectInput.faza}
            onChange={v => setCartusProiectInput(p => ({ ...p, faza: v }))} />

          {/* Suprafață construită + cost estimat Z-Coins — DOAR afișare (consumul real: task A5) */}
          <SectionLabel>Suprafață construită</SectionLabel>
          <div className="mb-3.5">
            <label className="block text-[12px] font-semibold tracking-wide mb-1.5" style={{ color: "#8B8FA8" }}>
              SUPRAFAȚĂ TOTALĂ (mp) <span style={{ color: "#E24B4A" }}>*</span>
            </label>
            <input type="number" min={1} step={1} value={form.surface_mp || ""}
              onChange={(e) => update("surface_mp", parseFloat(e.target.value) || 0)}
              placeholder="ex: 160"
              className="w-full rounded-lg px-3 py-2.5 text-[14px] font-[inherit] outline-none"
              style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)", color: "#E2E4E9" }} />
          </div>

          {form.surface_mp > 0 && (() => {
            const faza = cartusProiectInput.faza;
            const perM2 = isPhasePT(faza)
              ? CREDIT_PRICING.perM2.dtac + CREDIT_PRICING.perM2.pt
              : CREDIT_PRICING.perM2.dtac;
            const zcoins = Math.ceil(form.surface_mp * perM2);
            const lei = zcoins * CREDIT_PRICING.pricePerCredit;
            const fmt = (n: number) => n.toLocaleString("ro-RO", { maximumFractionDigits: 2 });
            const pretZ = CREDIT_PRICING.pricePerCredit.toFixed(2).replace(".", ",");
            return (
              <div className="mb-3.5 rounded-xl p-4" style={{ background: "rgba(55,138,221,0.06)", border: "1px solid rgba(55,138,221,0.18)" }}>
                <div className="text-[12px]" style={{ color: "#8B8FA8" }}>Cost estimat proiect</div>
                <div className="mt-1" style={{ fontSize: 20, fontWeight: 700 }}>
                  <span style={{ color: "#5BB8F5" }}>{fmt(zcoins)} Z-Coins</span>
                  <span style={{ color: "#8B8FA8", fontWeight: 500, fontSize: 15 }}> · {fmt(lei)} lei</span>
                </div>
                <div className="mt-1 text-[11px]" style={{ color: "#545870" }}>
                  {faza} · {form.surface_mp} mp × {perM2} Z-Coin/mp · {pretZ} lei/Z-Coin
                </div>
                {user && (() => {
                  const bal = profile?.credits_balance ?? 0;
                  const enough = bal >= zcoins;
                  return (
                    <>
                      {/* Sold curent (gri, discret) + sold ramas dupa scaderea costului (verde / eroare rosie) */}
                      <div className="mt-2 text-[11px]" style={{ color: "#8B8FA8" }}>
                        Sold curent: {fmt(bal)} Z-Coins
                      </div>
                      {enough ? (
                        <div className="mt-0.5 text-[11px]" style={{ color: "#3ECFA0" }}>
                          Sold după consum: {fmt(bal - zcoins)} Z-Coins
                        </div>
                      ) : (
                        <div className="mt-0.5 text-[11px]" style={{ color: "#F09595" }}>
                          Sold insuficient: ai {fmt(bal)}, ai nevoie de {fmt(zcoins)}.{" "}
                          <Link href="/home" style={{ color: "#F09595", textDecoration: "underline" }}>Cumpără credite</Link>
                        </div>
                      )}
                    </>
                  );
                })()}
              </div>
            );
          })()}

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
            onChange={v => {
              update("heating_type", v);
              // Faza 2 TE-CT: la schimbarea SURSEI, checkbox-ul revine la default-ul ei
              // (bifat pe PDC/centrala electrica, nebifat pe gaz/termoficare/existing)
              update("has_tech_room", defaultTechRoom(v));
            }} options={HEATING_GENERATION} required />
          {form.heating_type && form.heating_type !== "existing" && (
            <SelectField label="Tip distribuție căldură" value={form.heating_distribution}
              onChange={v => update("heating_distribution", v)} options={HEATING_DISTRIBUTION} />
          )}
          {/* Faza 2 TE-CT: camera tehnica e OPTIONALA pe ORICE sursa — decide DOAR destinatia
              echipamentelor de incalzire: bifat -> tablou TE-CT; nebifat -> TEG (alta incapere). */}
          {form.heating_type && (
            <Toggle label="Am cameră tehnică" checked={form.has_tech_room}
              onChange={v => update("has_tech_room", v)}
              description={form.has_tech_room
                ? "Echipamentele de încălzire pe tablou separat TE-CT (cameră tehnică)"
                : "Echipamentele de încălzire pe TEG (debara / cămară / altă încăpere)"} />
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

          {/* Cartuș: confirmat automat din Vision (vezi modalul). Rezumat compact + re-editare */}
          {cartusConfirmed && (
            <div style={{ marginTop: 8, marginBottom: 4, padding: "12px 14px", borderRadius: 12,
              background: "rgba(29,158,117,0.08)", border: "1px solid rgba(29,158,117,0.25)" }}>
              <div className="flex items-center justify-between gap-2">
                <div style={{ fontSize: 13, color: "#E2E4E9" }}>
                  <strong>{cartusProiectInput.titlu_proiect || "Proiect"}</strong>
                  <span style={{ color: "#8B8FA8" }}>
                    {" "}· {cartusProiectInput.faza}{cartusProiectInput.numar_proiect ? ` · ${cartusProiectInput.numar_proiect}` : ""}
                  </span>
                </div>
                <button type="button" onClick={() => setShowCartusModal(true)}
                  className="text-[12px] font-semibold"
                  style={{ color: "#5BB8F5", background: "none", border: "none", cursor: "pointer" }}>
                  Editează
                </button>
              </div>
            </div>
          )}

          </div>{/* /panou inputuri blocabil */}

          {/* 10. Submit — Epic 3.11: declanșează Vision pe primul plan, apoi modal cartuș.
              Pe success butonul devine "Proiect nou" (reset complet) -> re-activeaza panoul.
              In loading ramane butonul normal ("Se procesează...", disabled) — NU resetul. */}
          {status === "success" ? (
            <button type="button" onClick={resetForNewProject}
              className="w-full mt-5 py-3.5 px-6 rounded-xl text-[14px] font-semibold font-[inherit] tracking-wide transition-all duration-200"
              style={{ background: "rgba(29,158,117,0.12)", border: "1px solid rgba(29,158,117,0.3)", color: "#3ECFA0", cursor: "pointer" }}>
              ✓ Proiect generat · Începe proiect nou
            </button>
          ) : (
            <button onClick={handleGenerate} disabled={!canSubmitBasic || isLoading || visionCartusLoading}
              className="w-full mt-5 py-3.5 px-6 rounded-xl text-[14px] font-semibold font-[inherit] tracking-wide transition-all duration-200"
              style={{
                background: canSubmitBasic && !isLoading ? "linear-gradient(135deg, #378ADD 0%, #1D9E75 100%)" : "rgba(255,255,255,0.05)",
                border: "none",
                color: canSubmitBasic ? "#fff" : "#545870",
                cursor: canSubmitBasic && !isLoading && !visionCartusLoading ? "pointer" : "not-allowed",
                opacity: isLoading ? 0.75 : 1,
                boxShadow: canSubmitBasic && !isLoading ? "0 0 24px rgba(55,138,221,0.25)" : "none",
              }}>
              {visionCartusLoading ? "Se analizează planurile..." : isLoading ? "Se procesează..." : "Generează proiect electric"}
            </button>
          )}

          {isLoading && (
            <div className="mt-3">
              <div className="h-0.5 rounded-full mb-2 overflow-hidden" style={{ background: "rgba(255,255,255,0.07)" }}>
                <div className="h-full rounded-full transition-all duration-700"
                  style={{ width: `${((stepIndex + 1) / PROGRESS_STEPS.length) * 100}%`, background: "linear-gradient(90deg, #378ADD, #1D9E75)" }} />
              </div>
              <div className="flex items-center justify-center gap-2 text-[12px]" style={{ color: "#5BB8F5" }}>
                <span className="inline-block w-3.5 h-3.5 border-2 rounded-full"
                  style={{ borderColor: "#5BB8F5", borderTopColor: "transparent", animation: "zy-spin 0.7s linear infinite" }} />
                Se generează proiectul…
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
              {/* Export JSON = dump-ul brut result_data (debug) — DOAR admin (Dan), ca toggle-ul
                  de pereți din editor; clienții nu au ce face cu el (structura interna + base64). */}
              {user?.id === ADMIN_USER_ID && (
                <button onClick={exportJSON}
                  className="px-4 py-2 rounded-lg text-[13px] font-semibold font-[inherit] cursor-pointer transition-colors duration-150"
                  style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", color: "#8B8FA8" }}
                  onMouseOver={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.08)")}
                  onMouseOut={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.04)")}>
                  Export JSON
                </button>
              )}
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

            {/* ── Tab bar ── */}
            <div className="flex gap-1 mb-4 p-1 rounded-xl" style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
              {[
                { id: 'circuits', label: 'Circuite' },
                { id: 'bom',      label: 'Materiale' },
                { id: 'schemas',  label: 'Scheme' },
                { id: 'plan',     label: 'Planșă' },
                { id: 'editor',   label: 'Editor' },
                { id: 'memoriu',  label: 'Memoriu' },
              ].filter(tab => {
                if (tab.id === 'bom' || tab.id === 'plan') return showPlanBom;
                if (tab.id === 'editor') return showPlanBom && !!editorPlansa && !!savedProjectId;  // PT + PNG + proiect salvat
                return true;
              }).map(tab => (
                <button key={tab.id} onClick={() => setActiveTab(tab.id)}
                  className="flex-1 py-2 px-3 rounded-lg text-[12px] font-semibold font-[inherit] cursor-pointer transition-all duration-150"
                  style={{
                    background: activeTab === tab.id ? "rgba(55,138,221,0.18)" : "transparent",
                    border: activeTab === tab.id ? "1px solid rgba(55,138,221,0.35)" : "1px solid transparent",
                    color: activeTab === tab.id ? "#5BB8F5" : "#545870",
                  }}>
                  {tab.label}
                </button>
              ))}
            </div>

            {/* ── Tab: Circuite ── */}
            {activeTab === 'circuits' && (
              <div>
                {result!.project_info && <ProjectInfoCard info={result!.project_info} />}

                {(() => {
                  const allCircuits = result!.circuits?.length
                    ? result!.circuits
                    : [...(result!.circuits_te_ct || []), ...(result!.circuits_teg || [])];
                  return allCircuits.length > 0 ? (
                    <div className="rounded-xl mb-3 overflow-hidden"
                      style={{ background: "rgba(255,255,255,0.025)", border: "1px solid rgba(255,255,255,0.06)" }}>
                      <div className="px-5 py-3.5 flex items-center gap-2 text-sm font-semibold border-b"
                        style={{ color: "#C8CAD6", borderColor: "rgba(255,255,255,0.04)" }}>
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
                      </div>
                      <div className="overflow-x-auto px-5 pb-4">
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
                    </div>
                  ) : (
                    <p className="text-sm text-center py-8" style={{ color: "#545870" }}>Niciun circuit în răspuns.</p>
                  );
                })()}

                <RoomsList rooms={result!.rooms} />
              </div>
            )}

            {/* ── Tab: Materiale (BOM) — DOAR pe DTAC+PT ── */}
            {showPlanBom && activeTab === 'bom' && (
              <div>
                {result!.bom?.length ? (
                  <div className="rounded-xl mb-3 overflow-hidden"
                    style={{ background: "rgba(255,255,255,0.025)", border: "1px solid rgba(255,255,255,0.06)" }}>
                    <div className="px-5 py-3.5 flex items-center gap-2 text-sm font-semibold border-b"
                      style={{ color: "#C8CAD6", borderColor: "rgba(255,255,255,0.04)" }}>
                      Listă materiale
                      <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full"
                        style={{ background: "rgba(255,255,255,0.07)", color: "#8B8FA8" }}>
                        {result!.bom.length}
                      </span>
                    </div>
                    <div className="overflow-x-auto px-5 pb-4">
                      <table className="w-full border-collapse text-sm mt-3">
                        <thead>
                          <tr>
                            {["Categorie", "Articol", "Cant.", "UM", "Observații"].map(h => (
                              <th key={h} className="text-left px-2 py-2 text-[10px] font-semibold tracking-widest uppercase"
                                style={{ color: "#545870", borderBottom: "1px solid rgba(255,255,255,0.06)" }}>{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {result!.bom.map((b, i) => (
                            <tr key={i} style={{ background: i % 2 ? "rgba(255,255,255,0.015)" : "transparent" }}>
                              <td className="px-2 py-2 text-[11px]" style={{ color: "#545870" }}>{b.category || ""}</td>
                              <td className="px-2 py-2 text-sm" style={{ color: "#C8CAD6" }}>{b.item || (b as any).articol}</td>
                              <td className="px-2 py-2 text-sm font-semibold" style={{ color: "#8B8FA8" }}>{b.quantity ?? (b as any).cant}</td>
                              <td className="px-2 py-2 text-[11px]" style={{ color: "#545870" }}>{b.unit || (b as any).um}</td>
                              <td className="px-2 py-2 text-[11px]" style={{ color: "#545870" }}>{b.notes || (b as any).obs || ""}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-center py-8" style={{ color: "#545870" }}>Nicio listă de materiale în răspuns.</p>
                )}
              </div>
            )}

            {/* ── Tab: Scheme monofilare ── */}
            {activeTab === 'schemas' && (
              <div>
                {result!.schemas?.length ? (
                  <div className="flex flex-col gap-4">
                    {result!.schemas.map((s, i) => (
                      <div key={i} className="rounded-xl overflow-hidden"
                        style={{ background: "rgba(255,255,255,0.025)", border: "1px solid rgba(255,255,255,0.06)" }}>
                        <div className="px-5 py-3 flex items-center justify-between border-b"
                          style={{ borderColor: "rgba(255,255,255,0.04)" }}>
                          <span className="text-sm font-semibold" style={{ color: "#C8CAD6" }}>
                            {/* numele = LITERAL titlul din cartus (mirror numerotare); fallback = metadata veche */}
                            {schemasMapped[i]
                              ? `${schemasMapped[i]!.nr} ${schemasMapped[i]!.titlu}`
                              : `${s.name}${s.plansa_nr ? ` — Planșa ${s.plansa_nr}` : ""}`}{s.page_format ? ` (${s.page_format})` : ""}
                          </span>
                          <button
                            onClick={() => downloadSchemaEl(
                              s,
                              schemasMapped[i]
                                ? `${sanitizePdfName(`${schemasMapped[i]!.nr} ${schemasMapped[i]!.titlu}`)}.pdf`
                                : `Schema-${s.name}-${result!.project_info?.proiect_nr || result!.project_id || "zynapse"}.pdf`,
                              downloadPDF
                            )}
                            className="px-3 py-1.5 rounded-lg text-[12px] font-semibold font-[inherit] cursor-pointer"
                            style={{ background: "rgba(21,128,61,0.12)", border: "1px solid rgba(21,128,61,0.28)", color: "#4ADE80" }}>
                            ⬇ Descarcă PDF
                          </button>
                        </div>
                        {/* citeste-ambele: base64 direct (vechi) sau signed URL din Storage (nou) */}
                        <SchemaFrame base64Pdf={s.pdf_base64} storagePath={s.pdf_path} title={s.name} />
                      </div>
                    ))}
                  </div>
                ) : (result!.schema_monofilara_pdf || result!.schema_monofilara_path) ? (
                  <div className="rounded-xl overflow-hidden"
                    style={{ background: "rgba(255,255,255,0.025)", border: "1px solid rgba(255,255,255,0.06)" }}>
                    <div className="px-5 py-3 border-b flex justify-end" style={{ borderColor: "rgba(255,255,255,0.04)" }}>
                      <SchemaDownloadButton base64Pdf={result!.schema_monofilara_pdf} storagePath={result!.schema_monofilara_path} />
                    </div>
                    {/* preview inline DOAR pe base64 (proiecte vechi / schema proaspata in memorie);
                        cu doar path (Storage) ramane butonul de download — schemas[] acopera oricum afisajul */}
                    {result!.schema_monofilara_pdf ? (
                      <iframe
                        src={`data:application/pdf;base64,${result!.schema_monofilara_pdf}`}
                        className="w-full"
                        style={{ height: 600, border: "none" }}
                        title="Schema monofilară"
                      />
                    ) : null}
                  </div>
                ) : (
                  <p className="text-sm text-center py-8" style={{ color: "#545870" }}>Nicio schemă monofilară în răspuns.</p>
                )}
              </div>
            )}

            {/* ── Tab: Planșe (arhitectură cu cartuș Zynapse) — DOAR pe DTAC+PT ── */}
            {showPlanBom && activeTab === 'plan' && (() => {
              // 1d: arata DOAR planul REGENERAT (dupa "Obtine plan"); ciorna Vision se ascunde (placeholder).
              const { planse, draftPending } = iluminatPlanseToShow(result!);
              if (draftPending) {
                return (
                  <div className="text-center py-10">
                    <p className="text-sm m-0" style={{ color: "#8B8FA8" }}>Planul de iluminat e încă ciornă.</p>
                    <p className="text-[13px] mt-1 m-0" style={{ color: "#545870" }}>
                      Mergi la tab-ul <b style={{ color: "#8B8FA8" }}>Editor</b>, ajustează elementele și apasă <b style={{ color: "#5BB8F5" }}>„Obține plan iluminat"</b> ca să generezi planul final (cu cabluri).
                    </p>
                  </div>
                );
              }
              return planse.length
                ? <PlanPdfSection planse={planse} />
                : <p className="text-sm text-center py-8" style={{ color: "#545870" }}>Nu există planuri.</p>;
            })()}

            {/* ── Tab: Editor vizual (PASUL 3.1, read-only) — PNG plan + overlay plan_elements ── */}
            {activeTab === 'editor' && editorPlansa && savedProjectId && (
              <div>
                {/* F3: comutator Iluminat | Forță (segmented control — accent app #378ADD/#5BB8F5, dark) */}
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12, flexWrap: "wrap" }}>
                  {/* M2b: selector de etaj (DOAR multi-etaj) — comută planșa/etajul editat (verde). */}
                  {multiFloor && (
                    <div style={{ display: "inline-flex", padding: 3, gap: 3, borderRadius: 10,
                      background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)" }}>
                      {editablePlanse.map(({ idx }) => {
                        const on = editorPlansaIdx === idx;
                        return (
                          <button key={idx} type="button"
                            onClick={() => { setEditorPlansaIdx(idx); if (planseIluminat[idx]?.regenerated !== true) setModeEditor("iluminat"); }}
                            style={{ padding: "6px 16px", borderRadius: 7, cursor: "pointer", fontFamily: "inherit",
                              fontSize: 12.5, fontWeight: 600, letterSpacing: 0.2,
                              background: on ? "rgba(29,158,117,0.18)" : "transparent",
                              border: on ? "1px solid rgba(29,158,117,0.45)" : "1px solid transparent",
                              color: on ? "#37C58A" : "#8B8FA8",
                              transition: "background-color .15s ease, color .15s ease, border-color .15s ease" }}>
                            {floorName(idx)}
                          </button>
                        );
                      })}
                    </div>
                  )}
                  <div style={{ display: "inline-flex", padding: 3, gap: 3, borderRadius: 10,
                    background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)" }}>
                    {([["iluminat", "Iluminat"], ["forta", "Forță"]] as const).map(([m, label]) => {
                      const on = modeEditor === m;
                      const locked = m === "forta" && !iluminatFinalizat;   // forta blocata pana la IE.1 (coerent cu CTA)
                      return (
                        <button key={m} type="button" disabled={locked}
                          onClick={() => !locked && setModeEditor(m)}
                          title={locked ? "Obtine planul de iluminat intai" : undefined}
                          style={{
                            padding: "6px 18px", borderRadius: 7, cursor: locked ? "not-allowed" : "pointer", fontFamily: "inherit",
                            fontSize: 12.5, fontWeight: 600, letterSpacing: 0.2, opacity: locked ? 0.45 : 1,
                            background: on ? "rgba(55,138,221,0.18)" : "transparent",
                            border: on ? "1px solid rgba(55,138,221,0.45)" : "1px solid transparent",
                            color: on ? "#5BB8F5" : "#8B8FA8",
                            transition: "background-color .15s ease, color .15s ease, border-color .15s ease",
                          }}>
                          {label}
                        </button>
                      );
                    })}
                  </div>
                  <span style={{ fontSize: 11, color: "#545870" }}>
                    {modeEditor === "iluminat"
                      ? "Becuri, întrerupătoare, tablouri"
                      : "Prize / alimentări · tablouri moștenite (read-only)"}
                  </span>
                </div>
                <PlanEditor
                  projectId={savedProjectId}
                  mode={modeEditor}
                  // Forta: fundalul CURAT (fortaBg); daca a esuat definitiv SAU lipseste baza -> fallback pe
                  // PNG-ul iluminat (valid, scale corect) ca sa nu ramana gol/eroare; cat se incarca efectiv
                  // (baza exista, fetch in curs) -> null + spinner (bgLoading). Spinner DOAR cand chiar se incarca.
                  pngBase64={modeEditor === "forta" ? (fortaBg?.png_base64 ?? ((fortaBgErr || !fortaCleanBase) ? editorPlansa.png_base64 : null)) : editorPlansa.png_base64}
                  pngMeta={modeEditor === "forta" ? (fortaBg?.png_meta ?? ((fortaBgErr || !fortaCleanBase) ? editorPlansa.png_meta : null)) : editorPlansa.png_meta}
                  bgLoading={modeEditor === "forta" && !!fortaCleanBase && !fortaBg && !fortaBgErr}
                  cleanBasePdf={fortaCleanBase}
                  floor={floorCanonic(editorPlansaIdx)}
                  onRegenerated={handleRegenerated}
                  rooms={roomsScoped}
                  heatingDistribution={form.heating_distribution}
                  heatingType={form.heating_type}
                  enabledEquipment={Object.keys(equipment).filter(t => equipment[t]?.enabled)}
                  isAdmin={user?.id === ADMIN_USER_ID}
                  heatingEquipment={heatingEquipmentFromCircuits(result?.circuits as never[] | undefined)}
                  hasTechRoom={form.has_tech_room}
                  hasFv={!!equipment.solar?.enabled}
                  fvKw={snapFvPackage(equipment.solar?.power_kw)}
                  finalized={resumedFinalized}
                />
              </div>
            )}

            {/* ── Tab: Memoriu tehnic ── */}
            {activeTab === 'memoriu' && (
              <div>
                {(result!.memoriu_docx_base64 || result!.memoriu_docx_path) ? (
                  <div className="mb-4">
                    <MemoriuDocxButton
                      base64Docx={result!.memoriu_docx_base64}
                      storagePath={result!.memoriu_docx_path}
                      fileName={result!.memoriu_filename || `Memoriu_Tehnic_${(result!.project_id || "proiect")}.docx`}
                    />
                  </div>
                ) : (
                  <p className="text-sm text-center py-8" style={{ color: "#545870" }}>
                    Memoriul tehnic nu a fost generat pentru acest proiect.
                  </p>
                )}
                <MemoriuSection text={result!.memoriu_tehnic} />
                <details className="mt-4">
                  <summary className="text-[11px] cursor-pointer select-none"
                    style={{ color: "#3A3D50" }}>Debug: JSON complet</summary>
                  <pre className="mt-2 p-3 rounded-lg text-[10px] overflow-auto max-h-72 m-0"
                    style={{ background: "rgba(0,0,0,0.4)", color: "#545870", fontFamily: "'JetBrains Mono', monospace", lineHeight: 1.5 }}>
                    {JSON.stringify(result, null, 2)}
                  </pre>
                </details>
              </div>
            )}

            {/* ── CTA flux (S2/S4): STEPPER faze-aware. BUG REPARAT: "Finalizare" NU mai e CTA global pe
                orice tab (asta scurtcircuita forta) — apare DOAR in faza forta, in tab-ul Editor.
                Iluminat-in-editor -> "Editor Plan Forta" (gated pe IE.1). Alte tab-uri -> "Continua in
                Editor". Proiect fara editor (DTAC) -> "Finalizare Proiect" clasic (zero regresie). ── */}
            {status === "success" && (() => {
              let label = "Finalizare Proiect →";
              let onClick: (() => void) | undefined = handleFinalize;
              let variant: "green" | "blue" = "green";
              let disabled = false;
              let hint: string | null = null;
              if (!editorAvailable) {
                // proiect fara editor (non-PT / fara plansa editabila) -> iesire clasica (zero regresie)
              } else if (activeTab !== "editor") {
                label = "Continuă în Editor →"; onClick = () => setActiveTab("editor"); variant = "blue";
              } else if (!multiFloor) {
                // ── SINGLE-FLOOR: logica EXISTENTĂ (byte-for-byte) — zero regresie ──
                if (fazaFlux === "iluminat-nedefinitivat") {
                  label = "Editor Plan Forță →"; onClick = undefined; variant = "blue"; disabled = true;
                  hint = "Obține planul de iluminat întâi (butonul 'Obține plan iluminat').";
                } else if (fazaFlux === "iluminat-gata") {
                  label = "Editor Plan Forță →"; onClick = handleGoForta; variant = "blue";
                } else {   // fazaFlux === "forta"
                  label = "Finalizare proiect →"; onClick = handleFinalizeDocs; variant = "green";
                }
              } else if (modeEditor === "iluminat") {
                // ── MULTI-ETAJ · faza ILUMINAT: toate etajele întâi (ordinea Dan) ──
                const nextIdx = editablePlanse.map(x => x.idx).find(i => planseIluminat[i]?.regenerated !== true);
                if (planseIluminat[editorPlansaIdx]?.regenerated !== true) {
                  label = "Continuă →"; onClick = undefined; variant = "blue"; disabled = true;
                  hint = `Obține planul de iluminat (${floorName(editorPlansaIdx)}) — butonul din editor.`;
                } else if (nextIdx !== undefined) {
                  label = `Iluminat ${floorName(nextIdx)} →`; onClick = () => goEditorStep(nextIdx, "iluminat"); variant = "blue";
                } else {
                  label = "Editor Plan Forță →"; onClick = () => goEditorStep(editablePlanse[0].idx, "forta"); variant = "blue";
                }
              } else {
                // ── MULTI-ETAJ · faza FORȚĂ: după ce TOATE etajele au iluminat ──
                const nextIdx = editablePlanse.map(x => x.idx).find(i => !fortaDone(i));
                if (!fortaDone(editorPlansaIdx)) {
                  label = "Continuă →"; onClick = undefined; variant = "blue"; disabled = true;
                  hint = `Obține planul de forță (${floorName(editorPlansaIdx)}) — butonul din editor.`;
                } else if (nextIdx !== undefined) {
                  label = `Forță ${floorName(nextIdx)} →`; onClick = () => goEditorStep(nextIdx, "forta"); variant = "blue";
                } else {
                  label = "Finalizare proiect →"; onClick = handleFinalizeDocs; variant = "green";
                }
              }
              // Faza 2b: cat timp genereaza documentele la finalizare -> buton dezactivat + eticheta de progres.
              if (onClick === handleFinalizeDocs && finalizeLoading) {
                label = "Se generează documentele…"; disabled = true; onClick = undefined;
              }
              const grad = variant === "blue"
                ? { background: "linear-gradient(135deg, #2870C2 0%, #378ADD 100%)", boxShadow: "0 0 24px rgba(55,138,221,0.30)" }
                : { background: "linear-gradient(135deg, #1D9E75 0%, #37C58A 100%)", boxShadow: "0 0 24px rgba(29,158,117,0.30)" };
              return (
                <div className="mt-6 pt-5" style={{ borderTop: "1px solid rgba(255,255,255,0.07)" }}>
                  <div className="flex justify-end">
                    <button type="button" disabled={disabled} onClick={onClick}
                      className="py-3 px-7 rounded-xl text-[14px] font-semibold font-[inherit] tracking-wide transition-all duration-200"
                      style={{ ...grad, border: "none", color: "#fff",
                        cursor: disabled ? "not-allowed" : "pointer", opacity: disabled ? 0.5 : 1,
                        ...(disabled ? { boxShadow: "none" } : {}) }}>
                      {label}
                    </button>
                  </div>
                  {hint && <div className="text-right text-[11px] mt-2" style={{ color: "#C8A04D" }}>{hint}</div>}
                  {finalizeErr && <div className="text-right text-[11px] mt-2" style={{ color: "#F09595" }}>{finalizeErr}</div>}
                </div>
              );
            })()}

          </div>
        ) : isLoading ? (
          <CipProcesare />
        ) : (
          <CarouselFlux />
        )}
      </div>
    </div>
  );
}
