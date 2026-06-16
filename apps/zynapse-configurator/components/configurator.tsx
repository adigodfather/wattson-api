"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import {
  BUILDING_CATEGORIES_3, BUILDING_SUBTYPES,
  INSULATION, HEATING_GENERATION, HEATING_DISTRIBUTION,
  EXTRA_EQUIPMENT_DEFAULTS, FAZA_PROIECT_OPTIONS, isPhasePT,
  INITIAL_FORM, type FormData, type ProjectResult, type Motor, type ExtraEquipment,
} from "@/lib/constants";
import { useAuth } from "@/components/auth-provider";
import { createClient } from "@/lib/supabase";
import {
  MetricCard, CircuitTable, RoomsList, MemoriuSection, MemoriuDocxButton,
  SchemasSection, SchemaDownloadButton, AnnotatedPlanSection, ProjectInfoCard, PlanPdfSection,
} from "@/components/result-sections";
import CartusConfirmModal, { type VisionSurfaces } from "./CartusConfirmModal";
import MultiFileDropZone from "./MultiFileDropZone";
import { CREDIT_PRICING } from "@/components/CreditCalculator";

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
/* Epic 3.11: doar "rezidential" e activ; restul disabled cu badge "Curând". */
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

/* ─── Faza proiect chips (Epic 3.11) — DTAC+PT temporar DOAR pentru admin ─── */
function FazaProiectChips({ value, onChange, isAdmin }: { value: string; onChange: (v: string) => void; isAdmin: boolean }) {
  return (
    <div className="grid grid-cols-3 gap-2 mb-3.5">
      {FAZA_PROIECT_OPTIONS.map(opt => {
        // DTAC+PT activ doar pentru admin (la lansare); restul vad doar DTAC.
        const enabled = opt.enabled && (opt.value !== "DTAC+PT" || isAdmin);
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
interface EquipState { enabled: boolean; power_kw: number; phase: string; }

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
    <div className="flex flex-col items-center justify-center text-center min-h-[70vh] md:min-h-[640px] md:self-stretch px-6 md:pl-[12%]">
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
  const { user, profile, loading: authLoading, signOut, refreshProfile } = useAuth();
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
  const [customEquipment, setCustomEquipment] = useState<{ name: string; room: string; power_kw: number; phase: string }[]>([]);

  // Auto-detect badge (populated from response)
  const [autoDetected, setAutoDetected] = useState<{ climate_zone: string; climate_source?: string; levels_string?: string } | null>(null);
  const [activeTab, setActiveTab] = useState<string>('circuits');
  const [pageFormat, setPageFormat] = useState<string>('');
  const [cartusProiectInput, setCartusProiectInput] = useState<CartusProiect>({
    beneficiar: '',
    amplasament: '',
    titlu_proiect: '',
    numar_proiect: '',
    faza: 'DTAC+PT',
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

  // Poarta DTAC+PT (temporar, la lansare): non-admin -> faza fortata la DTAC.
  // UI ascunde optiunea; aici garantam si starea (default-ul e DTAC+PT).
  useEffect(() => {
    if (!isAdmin && isPhasePT(cartusProiectInput.faza)) {
      setCartusProiectInput(p => ({ ...p, faza: "DTAC" }));
    }
  }, [isAdmin, cartusProiectInput.faza]);

  // Tab-urile Planșă + Materiale apar DOAR pe faza PT (DTAC+PT). isPhasePT robust la format.
  const showPlanBom = isPhasePT(result?.output_phase ?? result?.project_info?.faza ?? "");
  useEffect(() => {
    if (!showPlanBom && (activeTab === "plan" || activeTab === "bom")) setActiveTab("circuits");
  }, [showPlanBom, activeTab]);

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

    if (cartusConfirmed) { void runBackend(); return; }

    setVisionCartusLoading(true);
    setVisionSurfaces(null);   // reset la fiecare incercare; setat din raspuns daca exista
    try {
      const fd = new FormData();
      fd.append("plan", files[0]); // primul plan = parter
      const res = await fetch("/api/vision-cartus", { method: "POST", body: fd });
      if (res.ok) {
        const cartus = await res.json();
        setCartusProiectInput({
          titlu_proiect: cartus.titlu_proiect || "",
          beneficiar:    cartus.beneficiar    || "",
          amplasament:   cartus.amplasament   || "",
          sef_proiect:   cartus.sef_proiect   || "",
          numar_proiect: cartus.numar_proiect || "",
          data_proiect:  cartus.data_proiect  || "",
          faza:          cartus.faza          || "DTAC+PT",
        });
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
          .map(e => ({
            type: e.type,
            name: e.label,
            power_kw: equipment[e.type].power_kw,
            phase: equipment[e.type].phase,
            // numeric phases pentru backend (mono/none → 1, tri → 3)
            phases: equipment[e.type].phase === "tri" ? 3 : 1,
          })),
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
        const { data: inserted, error: insertError } = await supabase.from("projects").insert({
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
        if (insertError) {
          console.error("[save project] insert error:", insertError);
          setSaveMessage("Proiectul a fost generat, dar salvarea în istoric a eșuat. Descarcă-l acum din rezultate.");
        } else {
          // HARD CONSUME — scade creditele real DOAR la succes, idempotent pe uuid-ul proiectului.
          // Costul se calculeaza SERVER-SIDE in functie din surface_mp + faza (clientul nu trimite cost).
          const consumeFaza = cartusOverride?.faza ?? cartusProiectInput.faza;
          let msg = "Proiect salvat cu succes";
          try {
            const { data: consumeRes, error: consumeErr } = await supabase.rpc("consume_credits", {
              p_surface_mp: form.surface_mp,
              p_phase: consumeFaza,
              p_project_id: inserted?.id ?? null,
            });
            if (consumeErr) {
              // eroare tehnica (retea) -> proiectul DEJA e salvat; NU blocam afisarea, doar logam
              console.error("[consume_credits] error:", consumeErr);
            } else if (consumeRes && (consumeRes as { success?: boolean }).success === false) {
              // sold insuficient la finalizare (rar) -> lasam proiectul salvat, avertizam, NU stergem munca
              console.warn("[consume_credits] insuficient la consum:", consumeRes);
              msg = "Proiect generat. Atenție: soldul de Z-Coins nu a putut fi debitat (sold insuficient la finalizare).";
            }
          } catch (e) {
            console.error("[consume_credits] exception:", e);
          }
          const { error: rpcError } = await supabase.rpc("increment_projects_used");
          if (rpcError) console.error("[save project] increment error:", rpcError);
          await refreshProfile();   // re-fetch -> soldul nou apare imediat in UI
          setSaveMessage(msg);
        }
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
      <header className="px-4 md:px-8 py-4 flex justify-between items-center gap-2 sticky top-0 z-50"
        style={{
          background: "rgba(10,11,14,0.88)",
          borderBottom: "1px solid rgba(255,255,255,0.06)",
          backdropFilter: "blur(16px)",
          WebkitBackdropFilter: "blur(16px)",
        }}>
        <div className="flex items-center gap-3 md:gap-4 min-w-0">
          <div className="flex items-center gap-3 shrink-0">
            <Link href="/home" aria-label="Zynapse — acasă" className="flex items-center gap-2 shrink-0" style={{ textDecoration: "none" }}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/logo-icon.png" alt="" width={30} height={30} style={{ objectFit: "contain", filter: "brightness(2.2) drop-shadow(0 0 5px rgba(91,184,245,0.4))" }} />
              <span className="text-[19px] font-bold tracking-wide" style={{
                background: "linear-gradient(120deg, #378ADD 0%, #5BB8F5 35%, #CDEBFF 50%, #5BB8F5 65%, #378ADD 100%)",
                WebkitBackgroundClip: "text", backgroundClip: "text", WebkitTextFillColor: "transparent",
                filter: "drop-shadow(0 0 8px rgba(91,184,245,0.4))",
              }}>ZYNAPSE</span>
            </Link>
            <span className="hidden sm:inline-flex text-[10px] font-bold tracking-widest uppercase px-2 py-1 rounded-md"
              style={{ background: "rgba(55,138,221,0.12)", color: "#5BB8F5", border: "1px solid rgba(55,138,221,0.2)" }}>
              Beta
            </span>
          </div>

          {/* Desktop nav links */}
          <div className="hidden md:flex items-center gap-4">
            <div style={{ width: 1, height: 20, background: "rgba(255,255,255,0.08)" }} />
            <Link href="/home"
              className="text-sm font-medium transition-colors duration-150"
              style={{ color: "#8B8FA8", textDecoration: "none" }}
              onMouseOver={(e) => (e.currentTarget.style.color = "#E2E4E9")}
              onMouseOut={(e) => (e.currentTarget.style.color = "#8B8FA8")}>
              Home
            </Link>
            <div style={{ width: 1, height: 20, background: "rgba(255,255,255,0.08)" }} />
            <Link href="/projects"
              className="text-sm font-medium transition-colors duration-150"
              style={{ color: "#8B8FA8", textDecoration: "none" }}
              onMouseOver={(e) => (e.currentTarget.style.color = "#E2E4E9")}
              onMouseOut={(e) => (e.currentTarget.style.color = "#8B8FA8")}>
              Proiectele mele
            </Link>
            <div style={{ width: 1, height: 20, background: "rgba(255,255,255,0.08)" }} />
            <Link href="/settings"
              className="text-sm font-medium transition-colors duration-150"
              style={{ color: "#8B8FA8", textDecoration: "none" }}
              onMouseOver={(e) => (e.currentTarget.style.color = "#E2E4E9")}
              onMouseOut={(e) => (e.currentTarget.style.color = "#8B8FA8")}>
              Setări firmă
            </Link>
          </div>

          {/* Mobile hamburger — CSS-only (<details>), fara state */}
          <details className="md:hidden relative shrink-0">
            <summary className="list-none cursor-pointer w-9 h-9 flex items-center justify-center rounded-lg text-base select-none"
              style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", color: "#8B8FA8" }}>
              ☰
            </summary>
            <div className="absolute left-0 top-full mt-2 z-50 flex flex-col py-1 rounded-lg min-w-[170px]"
              style={{ background: "#14161C", border: "1px solid rgba(255,255,255,0.1)", boxShadow: "0 8px 28px rgba(0,0,0,0.5)" }}>
              <Link href="/home" className="px-4 py-2.5 text-sm font-medium" style={{ color: "#5BB8F5", textDecoration: "none" }}>
                Home
              </Link>
              <Link href="/projects" className="px-4 py-2.5 text-sm font-medium" style={{ color: "#C8CAD6", textDecoration: "none" }}>
                Proiectele mele
              </Link>
              <Link href="/settings" className="px-4 py-2.5 text-sm font-medium" style={{ color: "#C8CAD6", textDecoration: "none" }}>
                Setări firmă
              </Link>
            </div>
          </details>
        </div>

        <div className="flex items-center gap-2 md:gap-3 min-w-0">
          <span className="hidden sm:inline-flex"><StatusBadge status={status} /></span>
          {user && (
            <>
              <span className="text-sm truncate min-w-0 max-w-[140px] sm:max-w-none" style={{ color: "#8B8FA8" }}>
                {profile?.full_name || user.email}
              </span>
              <span
                className="text-sm flex items-center gap-1.5 px-2.5 md:px-3 py-1.5 rounded-lg font-medium shrink-0"
                style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", color: "#8B8FA8" }}
                title="Z-Coins disponibile">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src="/z-coin.svg" alt="" width={18} height={18} style={{ display: "block" }} />
                {authLoading || !profile
                  ? <>—<span className="hidden sm:inline"> Z-Coins</span></>
                  : <>{profile.credits_balance ?? 0}<span className="hidden sm:inline"> Z-Coins</span></>}
              </span>
              <button onClick={signOut}
                className="px-2.5 md:px-3 py-1.5 rounded-lg text-sm font-medium font-[inherit] cursor-pointer transition-colors duration-150 shrink-0"
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
      <div className="p-4 md:p-8 mx-auto max-w-[1280px] grid grid-cols-1 md:grid-cols-[420px_1fr] gap-6 items-start">

        {/* ── Form panel ── */}
        <div className="rounded-2xl p-6 md:sticky md:top-[73px] md:max-h-[calc(100vh-97px)] md:overflow-y-auto"
          style={{ background: "rgba(255,255,255,0.025)", border: "1px solid rgba(255,255,255,0.07)" }}>

          <div className="mb-5">
            <h1 className="text-lg font-bold tracking-tight m-0" style={{ color: "#E2E4E9" }}>Configurator proiect</h1>
            <p className="text-[13px] mt-1 m-0" style={{ color: "#545870" }}>Încarcă planșele și completează datele clădirii</p>
          </div>

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
          <FazaProiectChips value={cartusProiectInput.faza} isAdmin={isAdmin}
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
                  return bal >= zcoins ? (
                    <div className="mt-2 text-[11px]" style={{ color: "#3ECFA0" }}>
                      Se vor consuma {fmt(zcoins)} Z-Coins · sold: {fmt(bal)}
                    </div>
                  ) : (
                    <div className="mt-2 text-[11px]" style={{ color: "#F09595" }}>
                      Sold insuficient: ai {fmt(bal)}, ai nevoie de {fmt(zcoins)}.{" "}
                      <Link href="/home" style={{ color: "#F09595", textDecoration: "underline" }}>Cumpără credite</Link>
                    </div>
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

          {/* 10. Submit — Epic 3.11: declanșează Vision pe primul plan, apoi modal cartuș */}
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

            {/* ── Tab bar ── */}
            <div className="flex gap-1 mb-4 p-1 rounded-xl" style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
              {[
                { id: 'circuits', label: 'Circuite' },
                { id: 'bom',      label: 'Materiale' },
                { id: 'schemas',  label: 'Scheme' },
                { id: 'plan',     label: 'Planșă' },
                { id: 'memoriu',  label: 'Memoriu' },
              ].filter(tab => showPlanBom || (tab.id !== 'bom' && tab.id !== 'plan')).map(tab => (
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
                            {s.name}{s.plansa_nr ? ` — Planșa ${s.plansa_nr}` : ""}{s.page_format ? ` (${s.page_format})` : ""}
                          </span>
                          <button
                            onClick={() => downloadPDF(
                              s.pdf_base64,
                              `Schema-${s.name}-${result!.project_info?.proiect_nr || result!.project_id || "zynapse"}.pdf`
                            )}
                            className="px-3 py-1.5 rounded-lg text-[12px] font-semibold font-[inherit] cursor-pointer"
                            style={{ background: "rgba(21,128,61,0.12)", border: "1px solid rgba(21,128,61,0.28)", color: "#4ADE80" }}>
                            ⬇ Descarcă PDF
                          </button>
                        </div>
                        <iframe
                          src={`data:application/pdf;base64,${s.pdf_base64}`}
                          className="w-full"
                          style={{ height: 600, border: "none" }}
                          title={s.name}
                        />
                      </div>
                    ))}
                  </div>
                ) : result!.schema_monofilara_pdf ? (
                  <div className="rounded-xl overflow-hidden"
                    style={{ background: "rgba(255,255,255,0.025)", border: "1px solid rgba(255,255,255,0.06)" }}>
                    <div className="px-5 py-3 border-b flex justify-end" style={{ borderColor: "rgba(255,255,255,0.04)" }}>
                      <SchemaDownloadButton base64Pdf={result!.schema_monofilara_pdf} />
                    </div>
                    <iframe
                      src={`data:application/pdf;base64,${result!.schema_monofilara_pdf}`}
                      className="w-full"
                      style={{ height: 600, border: "none" }}
                      title="Schema monofilară"
                    />
                  </div>
                ) : (
                  <p className="text-sm text-center py-8" style={{ color: "#545870" }}>Nicio schemă monofilară în răspuns.</p>
                )}
              </div>
            )}

            {/* ── Tab: Planșe (arhitectură cu cartuș Zynapse) — DOAR pe DTAC+PT ── */}
            {showPlanBom && activeTab === 'plan' && (() => {
              // DTAC+PT: planul cu becuri (planse_iluminat) INLOCUIESTE planul de baza (planuri).
              // DTAC: planse_iluminat lipseste -> afiseaza planuri ca inainte.
              const planseSursa: Array<{ name: string; pdf_base64: string; filename?: string; plansa_nr?: string; source_plansa_nr?: string; type?: string }> =
                (result!.planse_iluminat && result!.planse_iluminat.length)
                  ? result!.planse_iluminat
                  : (result!.planuri || []);
              return planseSursa.length
                ? <PlanPdfSection planse={planseSursa} />
                : <p className="text-sm text-center py-8" style={{ color: "#545870" }}>Nu există planuri.</p>;
            })()}

            {/* ── Tab: Memoriu tehnic ── */}
            {activeTab === 'memoriu' && (
              <div>
                {result!.memoriu_docx_base64 ? (
                  <div className="mb-4">
                    <MemoriuDocxButton
                      base64Docx={result!.memoriu_docx_base64}
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
