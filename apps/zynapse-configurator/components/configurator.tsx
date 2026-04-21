"use client";

import { useState, useRef, useCallback } from "react";
import {
  BUILDING_TYPES, LEVELS, CLIMATE_ZONES, INSULATION, HEATING,
  INITIAL_FORM, type FormData, type ProjectResult, type Circuit, type RoomResult,
} from "@/lib/constants";

const WEBHOOK_URL = process.env.NEXT_PUBLIC_N8N_WEBHOOK_URL || "https://www.ai-nord-vest.com/webhook/zynapse-electrical";

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      resolve(result.split(",")[1]);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

/* ── Tiny UI atoms ── */

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { bg: string; text: string; label: string }> = {
    idle:    { bg: "rgba(120,120,120,0.15)", text: "#999",    label: "Așteaptă date" },
    loading: { bg: "rgba(59,139,212,0.15)",  text: "#5BB8F5", label: "Se procesează..." },
    success: { bg: "rgba(99,153,34,0.15)",   text: "#97C459", label: "Finalizat" },
    error:   { bg: "rgba(226,75,74,0.15)",   text: "#F09595", label: "Eroare" },
  };
  const c = map[status] ?? map.idle;
  return (
    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium"
      style={{ background: c.bg, color: c.text }}>
      {status === "loading" && (
        <span className="inline-block w-2.5 h-2.5 border-2 rounded-full animate-spin"
          style={{ borderColor: c.text, borderTopColor: "transparent" }} />
      )}
      {c.label}
    </span>
  );
}

function SelectField({ label, value, onChange, options, required }: {
  label: string; value: string; onChange: (v: string) => void;
  options: { value: string; label: string }[]; required?: boolean;
}) {
  return (
    <div className="mb-4">
      <label className="block text-sm text-[#999] mb-1.5 font-medium">
        {label}{required && <span className="text-red-400"> *</span>}
      </label>
      <select value={value} onChange={(e) => onChange(e.target.value)}
        className="w-full px-3.5 py-2.5 bg-white/5 border border-white/10 rounded-lg text-[#eee] text-sm outline-none font-[inherit] appearance-none">
        <option value="">— Alege —</option>
        {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );
}

function TextField({ label, value, onChange, placeholder, required }: {
  label: string; value: string; onChange: (v: string) => void;
  placeholder?: string; required?: boolean;
}) {
  return (
    <div className="mb-4">
      <label className="block text-sm text-[#999] mb-1.5 font-medium">
        {label}{required && <span className="text-red-400"> *</span>}
      </label>
      <input type="text" value={value} onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-3.5 py-2.5 bg-white/5 border border-white/10 rounded-lg text-[#eee] text-sm outline-none font-[inherit]" />
    </div>
  );
}

function Toggle({ label, checked, onChange, description }: {
  label: string; checked: boolean; onChange: (v: boolean) => void; description?: string;
}) {
  return (
    <label className="flex items-center gap-3 mb-3 cursor-pointer select-none">
      <div className="relative w-10 h-[22px] rounded-full transition-colors"
        style={{ background: checked ? "#378ADD" : "rgba(255,255,255,0.12)" }}>
        <div className="absolute top-0.5 w-[18px] h-[18px] rounded-full bg-white transition-[left]"
          style={{ left: checked ? 20 : 2 }} />
        <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)}
          className="absolute opacity-0 w-full h-full cursor-pointer m-0" />
      </div>
      <div>
        <div className="text-sm text-[#ddd]">{label}</div>
        {description && <div className="text-xs text-[#777]">{description}</div>}
      </div>
    </label>
  );
}

/* ── Drop zone ── */

function DropZone({ files, setFiles }: { files: File[]; setFiles: React.Dispatch<React.SetStateAction<File[]>> }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const dropped = Array.from(e.dataTransfer.files).filter(f =>
      f.type.startsWith("image/") || f.type === "application/pdf"
    );
    if (dropped.length) setFiles(prev => [...prev, ...dropped]);
  }, [setFiles]);

  return (
    <div className="mb-6">
      <label className="block text-sm text-[#999] mb-1.5 font-medium">Planșe arhitectură</label>
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className="border-2 border-dashed rounded-xl py-8 px-5 text-center cursor-pointer transition-all"
        style={{
          borderColor: dragging ? "#5BB8F5" : "rgba(255,255,255,0.12)",
          background: dragging ? "rgba(59,139,212,0.06)" : "rgba(255,255,255,0.02)",
        }}>
        <input ref={inputRef} type="file" multiple accept="image/*,.pdf"
          className="hidden" onChange={(e) => {
            const selected = Array.from(e.target.files || []);
            if (selected.length) setFiles(prev => [...prev, ...selected]);
          }} />
        <div className="text-3xl mb-2 opacity-40">+</div>
        <div className="text-sm text-[#aaa]">Trage planșele aici sau click pentru a selecta</div>
        <div className="text-xs text-[#666] mt-1">PDF, JPG, PNG — parter, etaj, mansardă</div>
      </div>
      {files.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {files.map((f, i) => (
            <div key={i} className="flex items-center gap-2 bg-white/5 rounded-lg px-3 py-1.5 text-sm">
              <span className="text-[#5BB8F5]">{f.type.startsWith("image/") ? "🖼" : "📄"}</span>
              <span className="text-[#ccc] max-w-[160px] overflow-hidden text-ellipsis whitespace-nowrap">{f.name}</span>
              <span className="text-[11px] text-[#666]">{(f.size / 1024).toFixed(0)} KB</span>
              <button onClick={(e) => { e.stopPropagation(); setFiles(prev => prev.filter((_, j) => j !== i)); }}
                className="bg-transparent border-none text-[#666] cursor-pointer text-base p-0 leading-none hover:text-white">×</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Result sections ── */

function ResultSection({ title, children, defaultOpen = true }: {
  title: string; children: React.ReactNode; defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="bg-white/[0.03] rounded-xl border border-white/[0.06] mb-4 overflow-hidden">
      <button onClick={() => setOpen(!open)}
        className="w-full px-5 py-3.5 bg-transparent border-none text-[#ddd] text-[15px] font-semibold cursor-pointer flex justify-between items-center font-[inherit]">
        {title}
        <span className="text-xs text-[#666] transition-transform" style={{ transform: open ? "rotate(180deg)" : "none" }}>▼</span>
      </button>
      {open && <div className="px-5 pb-4">{children}</div>}
    </div>
  );
}

function CircuitTable({ circuits, title }: { circuits: Circuit[]; title: string }) {
  if (!circuits?.length) return null;
  return (
    <ResultSection title={`${title} (${circuits.length} circuite)`}>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-white/10">
              {["ID", "Utilizare", "Protecție", "Cablu"].map(h => (
                <th key={h} className="text-left px-2.5 py-2 text-[#888] font-medium text-[11px] uppercase tracking-wider">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {circuits.map((c, i) => (
              <tr key={i} className="border-b border-white/[0.04]"
                style={{ background: i % 2 === 0 ? "transparent" : "rgba(255,255,255,0.015)" }}>
                <td className="px-2.5 py-2 text-[#999]">
                  <span className="px-2 py-0.5 rounded text-[11px] font-semibold"
                    style={{
                      background: c.panel === "TE-CT" ? "rgba(212,83,126,0.15)" : "rgba(59,139,212,0.15)",
                      color: c.panel === "TE-CT" ? "#ED93B1" : "#85B7EB",
                    }}>{c.id}</span>
                </td>
                <td className="px-2.5 py-2 text-[#ccc]">{c.usage}</td>
                <td className="px-2.5 py-2 text-[#999]">{c.breaker_a}A</td>
                <td className="px-2.5 py-2 text-[#999] font-mono text-xs">{c.cable}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </ResultSection>
  );
}

function RoomsList({ rooms }: { rooms: RoomResult[] }) {
  if (!rooms?.length) return null;
  return (
    <ResultSection title={`Camere — ${rooms.length} identificate`} defaultOpen={false}>
      {rooms.map((r, i) => (
        <div key={i} className="p-3 mb-2 rounded-lg bg-white/[0.03] border border-white/5">
          <div className="flex justify-between mb-1.5">
            <span className="text-[#ddd] font-semibold text-sm">{r.name}</span>
            <span className="text-[#888] text-sm">{r.area_m2} m²</span>
          </div>
          <div className="flex gap-4 text-xs text-[#777]">
            <span>Prize: {r.sockets?.reduce((s, x) => s + (x.count || 0), 0) || 0}</span>
            <span>Iluminat: {r.lights?.reduce((s, x) => s + (x.count || 0), 0) || 0}</span>
            <span className="capitalize">{r.function}</span>
          </div>
        </div>
      ))}
    </ResultSection>
  );
}

function MemoriuSection({ text }: { text: string }) {
  if (!text) return null;
  return (
    <ResultSection title="Memoriu tehnic" defaultOpen={false}>
      <pre className="whitespace-pre-wrap break-words text-[12.5px] leading-relaxed text-[#bbb] font-mono m-0 max-h-[500px] overflow-y-auto p-4 bg-black/20 rounded-lg">
        {text}
      </pre>
      <button onClick={() => {
        const blob = new Blob([text], { type: "text/plain" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url; a.download = "memoriu_tehnic.txt"; a.click();
        URL.revokeObjectURL(url);
      }} className="mt-3 px-5 py-2 bg-[rgba(59,139,212,0.15)] text-[#5BB8F5] border border-[rgba(59,139,212,0.3)] rounded-lg cursor-pointer text-sm font-[inherit] hover:bg-[rgba(59,139,212,0.25)] transition-colors">
        Descarcă memoriu .txt
      </button>
    </ResultSection>
  );
}

/* ── Main configurator ── */

export function ZynapseConfigurator() {
  const [files, setFiles] = useState<File[]>([]);
  const [form, setForm] = useState<FormData>(INITIAL_FORM);
  const [status, setStatus] = useState("idle");
  const [result, setResult] = useState<ProjectResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState("");

  const updateForm = (key: keyof FormData, val: string | boolean) =>
    setForm(prev => ({ ...prev, [key]: val }));

  const canSubmit = form.project_id && form.building_type && form.levels
    && form.insulation_level && form.heating_type && files.length > 0;

  const isPDC = form.heating_type?.startsWith("pdc") || form.heating_type === "geothermal";

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setStatus("loading"); setError(null); setResult(null);
    setProgress("Se encodează planșele...");

    try {
      const base64 = await fileToBase64(files[0]);
      setProgress("Se trimite la n8n...");

      const payload = {
        plan_base64: base64,
        plan_type: files[0].type || "image/jpeg",
        ...form,
      };

      setProgress("Claude analizează planșa...");
      const res = await fetch(WEBHOOK_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data: ProjectResult = await res.json();
      if (data.status === "error") throw new Error((data as any).error || "Eroare necunoscută");

      setResult(data);
      setStatus("success");
    } catch (err: any) {
      setError(err.message || "Eroare de conexiune");
      setStatus("error");
    } finally {
      setProgress("");
    }
  };

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="px-8 py-5 border-b border-white/[0.06] flex justify-between items-center bg-[rgba(10,11,14,0.9)] backdrop-blur-md sticky top-0 z-50">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#378ADD] to-[#1D9E75] flex items-center justify-center text-base font-bold text-white">Z</div>
          <span className="text-lg font-bold tracking-tight">Zynapse</span>
          <span className="text-[11px] text-[#666] bg-white/5 px-2 py-0.5 rounded ml-1">Beta</span>
        </div>
        <StatusBadge status={status} />
      </header>

      <div className="max-w-[1200px] mx-auto p-8 grid gap-8"
        style={{ gridTemplateColumns: result ? "400px 1fr" : "1fr" }}>

        {/* Form panel */}
        <div className="bg-white/[0.02] border border-white/[0.06] rounded-2xl p-6"
          style={{ maxHeight: result ? "calc(100vh - 120px)" : "none", overflowY: result ? "auto" : "visible" }}>
          <h2 className="text-xl font-bold mb-1 text-[#eee] tracking-tight">Configurator proiect</h2>
          <p className="text-sm text-[#666] mt-0 mb-6">Încarcă planșele și completează datele clădirii</p>

          <DropZone files={files} setFiles={setFiles} />
          <div className="h-px bg-white/[0.06] my-6" />

          <TextField label="Numele proiectului" value={form.project_id}
            onChange={v => updateForm("project_id", v)} placeholder="ex: Casa Popescu P+M 160mp" required />

          <div className="grid grid-cols-2 gap-3">
            <SelectField label="Tip clădire" value={form.building_type}
              onChange={v => updateForm("building_type", v)} options={BUILDING_TYPES} required />
            <SelectField label="Regim înălțime" value={form.levels}
              onChange={v => updateForm("levels", v)}
              options={LEVELS.map(l => ({ value: l, label: l }))} required />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <SelectField label="Zona climatică" value={form.climate_zone}
              onChange={v => updateForm("climate_zone", v)} options={CLIMATE_ZONES} />
            <SelectField label="Izolație" value={form.insulation_level}
              onChange={v => updateForm("insulation_level", v)} options={INSULATION} required />
          </div>

          <TextField label="Intrare principală" value={form.main_entrance}
            onChange={v => updateForm("main_entrance", v)} placeholder="ex: Parter, fațada sud" />

          <div className="h-px bg-white/[0.06] my-6" />
          <h3 className="text-[15px] font-semibold text-[#bbb] mb-4">Sistem încălzire</h3>

          <SelectField label="Tip încălzire" value={form.heating_type}
            onChange={v => updateForm("heating_type", v)} options={HEATING} required />

          {isPDC && (
            <SelectField label="Fază PDC" value={form.pdc_phase}
              onChange={v => updateForm("pdc_phase", v)}
              options={[{ value: "mono", label: "Monofazat" }, { value: "tri", label: "Trifazat" }]} />
          )}

          <div className="mt-2">
            <Toggle label="Boiler ACM" checked={form.has_acm_boiler} onChange={v => updateForm("has_acm_boiler", v)} />
            <Toggle label="Ventilație mecanică" checked={form.has_ventilation} onChange={v => updateForm("has_ventilation", v)} />
            <Toggle label="Recuperator căldură (HRV)" checked={form.has_hrv} onChange={v => updateForm("has_hrv", v)} />
            <Toggle label="Încălzire în pardoseală" checked={form.has_floor_heating} onChange={v => updateForm("has_floor_heating", v)} />
          </div>

          <div className="mt-4">
            <label className="block text-sm text-[#999] mb-1.5 font-medium">Observații</label>
            <textarea value={form.notes} onChange={(e) => updateForm("notes", e.target.value)}
              placeholder="Garaj încălzit, anexe, note speciale..." rows={3}
              className="w-full px-3.5 py-2.5 bg-white/5 border border-white/10 rounded-lg text-[#eee] text-sm outline-none font-[inherit] resize-y" />
          </div>

          <button onClick={handleSubmit} disabled={!canSubmit || status === "loading"}
            className="w-full mt-6 py-3.5 px-6 border-none rounded-xl text-[15px] font-semibold font-[inherit] tracking-wide transition-all"
            style={{
              background: canSubmit && status !== "loading" ? "linear-gradient(135deg, #378ADD, #1D9E75)" : "rgba(255,255,255,0.06)",
              color: canSubmit ? "#fff" : "#555",
              cursor: canSubmit && status !== "loading" ? "pointer" : "not-allowed",
              opacity: status === "loading" ? 0.7 : 1,
            }}>
            {status === "loading" ? "Se procesează..." : "Generează proiect electric"}
          </button>

          {status === "loading" && progress && (
            <div className="mt-3 text-center text-sm text-[#5BB8F5]"
              style={{ animation: "zy-pulse 1.5s ease-in-out infinite" }}>{progress}</div>
          )}
          {error && (
            <div className="mt-3 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-[#F09595] text-sm">{error}</div>
          )}
        </div>

        {/* Results panel */}
        {result && (
          <div>
            <div className="flex justify-between items-center mb-5">
              <h2 className="text-xl font-bold text-[#eee]">Rezultate — {result.project_id}</h2>
              <button onClick={() => {
                const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url; a.download = `${result.project_id || "proiect"}.json`; a.click();
                URL.revokeObjectURL(url);
              }} className="px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-[#aaa] text-sm cursor-pointer font-[inherit] hover:bg-white/10 transition-colors">
                Export JSON
              </button>
            </div>

            {/* Metric cards */}
            <div className="grid grid-cols-[repeat(auto-fit,minmax(140px,1fr))] gap-3 mb-5">
              {result.heating_circuits?.pdc && (
                <>
                  <div className="bg-white/[0.03] rounded-xl p-4 text-center border border-white/5">
                    <div className="text-[22px] font-bold text-[#EF9F27]">{result.heating_circuits.pdc.power_kw_thermal} kW</div>
                    <div className="text-[11px] text-[#888]">Putere termică PDC</div>
                  </div>
                  <div className="bg-white/[0.03] rounded-xl p-4 text-center border border-white/5">
                    <div className="text-[22px] font-bold text-[#5BB8F5]">{result.heating_circuits.pdc.breaker_a}A</div>
                    <div className="text-[11px] text-[#888]">Protecție PDC</div>
                  </div>
                </>
              )}
              <div className="bg-white/[0.03] rounded-xl p-4 text-center border border-white/5">
                <div className="text-[22px] font-bold text-[#97C459]">{result.circuits_all?.length || 0}</div>
                <div className="text-[11px] text-[#888]">Circuite totale</div>
              </div>
              <div className="bg-white/[0.03] rounded-xl p-4 text-center border border-white/5">
                <div className="text-[22px] font-bold text-[#ED93B1]">{result.rooms?.length || 0}</div>
                <div className="text-[11px] text-[#888]">Camere</div>
              </div>
            </div>

            <CircuitTable circuits={result.circuits_te_ct} title="Tablou TE-CT (cameră tehnică)" />
            <CircuitTable circuits={result.circuits_teg} title="Tablou TEG (general)" />
            <RoomsList rooms={result.rooms} />
            <MemoriuSection text={result.memoriu_tehnic} />
          </div>
        )}

        {/* Empty state */}
        {!result && (
          <div className="flex flex-col items-center justify-center min-h-[400px] text-center">
            <div className="w-20 h-20 rounded-2xl bg-[rgba(59,139,212,0.08)] flex items-center justify-center text-4xl mb-5 border border-[rgba(59,139,212,0.12)]">⚡</div>
            <h3 className="text-lg text-[#888] font-medium mb-2">Proiectare electrică automată</h3>
            <p className="text-sm text-[#555] max-w-[360px] leading-relaxed">
              Încarcă planșele arhitecturale, completează formularul și primești proiectul electric complet în sub 30 de secunde.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
