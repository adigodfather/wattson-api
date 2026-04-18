"use client";

import { useState } from "react";
import type { ProjectPayload, Room } from "@/types/wattson";

const ROOM_FUNCTIONS = [
  { value: "day", label: "Living / Birou / Dining" },
  { value: "night", label: "Dormitor" },
  { value: "circulation", label: "Hol / Casa scării" },
  { value: "bathroom", label: "Baie / WC" },
  { value: "kitchen", label: "Bucătărie" },
  { value: "technical/storage", label: "Cameră tehnică / Depozit" },
  { value: "other", label: "Altele" },
];

const defaultRoom = (): Room => ({
  name: "",
  level: "Parter",
  function: "day",
  area_m2: 0,
  height_m: 2.7,
  has_tv: false,
  has_nightstands: false,
});

interface Props {
  onSubmit: (payload: ProjectPayload) => void;
  loading: boolean;
  error: string | null;
}

export default function WattsonForm({ onSubmit, loading, error }: Props) {
  const [projectId, setProjectId] = useState("");
  const [buildingType, setBuildingType] = useState("casa_unifamiliala");
  const [levels, setLevels] = useState("P");
  const [climateZone, setClimateZone] = useState("II");
  const [insulation, setInsulation] = useState<ProjectPayload["building"]["insulation_level"]>("buna");
  const [heatingType, setHeatingType] = useState<ProjectPayload["heating"]["type"]>("pdc_air_water");
  const [pdcPhase, setPdcPhase] = useState<"mono" | "tri">("tri");
  const [hasAcm, setHasAcm] = useState(false);
  const [hasVentilation, setHasVentilation] = useState(false);
  const [hasHrv, setHasHrv] = useState(false);
  const [hasFloorHeating, setHasFloorHeating] = useState(false);
  const [rooms, setRooms] = useState<Room[]>([defaultRoom()]);

  const addRoom = () => setRooms((r) => [...r, defaultRoom()]);
  const removeRoom = (i: number) => setRooms((r) => r.filter((_, idx) => idx !== i));
  const updateRoom = (i: number, field: keyof Room, value: unknown) =>
    setRooms((r) => r.map((room, idx) => idx === i ? { ...room, [field]: value } : room));

  const totalArea = rooms.reduce((s, r) => s + (r.area_m2 || 0), 0);
  const totalVolume = rooms.reduce((s, r) => s + ((r.area_m2 || 0) * (r.height_m || 0)), 0);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const payload: ProjectPayload = {
      project_id: projectId || "Proiect WATTSON",
      building: {
        type: buildingType,
        levels,
        climate_zone: climateZone,
        insulation_level: insulation,
        total_area_m2: Math.round(totalArea * 10) / 10,
        total_volume_m3: Math.round(totalVolume * 10) / 10,
      },
      heating: {
        type: heatingType,
        pdc_phase: heatingType.startsWith("pdc") ? pdcPhase : undefined,
        has_acm_boiler: hasAcm,
        has_ventilation: hasVentilation,
        has_hrv: hasHrv,
      },
      has_floor_heating: hasFloorHeating,
      rooms,
    };
    onSubmit(payload);
  };

  const card = "rounded-xl border p-5 mb-4";
  const cardStyle = { background: "var(--surface)", borderColor: "var(--border)" };
  const labelCls = "block text-xs font-semibold uppercase tracking-wider mb-1";
  const labelStyle = { color: "var(--muted)" };
  const inputCls = "w-full rounded-lg px-3 py-2 text-sm outline-none focus:ring-1 transition";
  const inputStyle = { background: "#141C2E", border: "1px solid var(--border)", color: "var(--foreground)" };

  return (
    <form onSubmit={handleSubmit}>
      {/* Proiect */}
      <div className={card} style={cardStyle}>
        <h2 className="text-sm font-bold uppercase tracking-widest mb-4" style={{ color: "var(--accent)" }}>
          01 — Proiect
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className={labelCls} style={labelStyle}>Nume proiect</label>
            <input className={inputCls} style={inputStyle} placeholder="Ex: Casa Ionescu P+M"
              value={projectId} onChange={e => setProjectId(e.target.value)} />
          </div>
          <div>
            <label className={labelCls} style={labelStyle}>Tip clădire</label>
            <input className={inputCls} style={inputStyle} placeholder="casa_unifamiliala"
              value={buildingType} onChange={e => setBuildingType(e.target.value)} />
          </div>
          <div>
            <label className={labelCls} style={labelStyle}>Regim înălțime</label>
            <select className={inputCls} style={inputStyle} value={levels} onChange={e => setLevels(e.target.value)}>
              {["P", "P+M", "P+1", "P+1+M", "P+2"].map(l => <option key={l}>{l}</option>)}
            </select>
          </div>
        </div>
      </div>

      {/* Clădire */}
      <div className={card} style={cardStyle}>
        <h2 className="text-sm font-bold uppercase tracking-widest mb-4" style={{ color: "var(--accent)" }}>
          02 — Clădire
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div>
            <label className={labelCls} style={labelStyle}>Zonă climatică</label>
            <select className={inputCls} style={inputStyle} value={climateZone} onChange={e => setClimateZone(e.target.value)}>
              {["I", "II", "III", "IV", "V"].map(z => <option key={z}>{z}</option>)}
            </select>
          </div>
          <div>
            <label className={labelCls} style={labelStyle}>Izolație</label>
            <select className={inputCls} style={inputStyle} value={insulation} onChange={e => setInsulation(e.target.value as ProjectPayload["building"]["insulation_level"])}>
              <option value="slaba">Slabă</option>
              <option value="medie">Medie</option>
              <option value="buna">Bună</option>
              <option value="foarte_buna">Foarte bună</option>
            </select>
          </div>
          <div className="col-span-2">
            <label className={labelCls} style={{ color: "var(--muted)" }}>Suprafață totală calculată</label>
            <div className="rounded-lg px-3 py-2 text-sm font-mono" style={{ background: "#141C2E", border: "1px solid var(--border)", color: "var(--accent)" }}>
              {totalArea.toFixed(1)} m² · {totalVolume.toFixed(1)} m³
            </div>
          </div>
        </div>
      </div>

      {/* Încălzire */}
      <div className={card} style={cardStyle}>
        <h2 className="text-sm font-bold uppercase tracking-widest mb-4" style={{ color: "var(--accent)" }}>
          03 — Sistem de încălzire
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mb-4">
          <div>
            <label className={labelCls} style={labelStyle}>Tip</label>
            <select className={inputCls} style={inputStyle} value={heatingType} onChange={e => setHeatingType(e.target.value as ProjectPayload["heating"]["type"])}>
              <option value="pdc_air_water">PDC aer-apă</option>
              <option value="pdc_air_air">PDC aer-aer</option>
              <option value="gas_boiler">Centrală gaz</option>
              <option value="electric_boiler">Centrală electrică</option>
              <option value="geothermal">Geotermală</option>
              <option value="none">Fără</option>
            </select>
          </div>
          {heatingType.startsWith("pdc") && (
            <div>
              <label className={labelCls} style={labelStyle}>Faze PDC</label>
              <select className={inputCls} style={inputStyle} value={pdcPhase} onChange={e => setPdcPhase(e.target.value as "mono" | "tri")}>
                <option value="tri">Trifazat</option>
                <option value="mono">Monofazat</option>
              </select>
            </div>
          )}
        </div>
        <div className="flex flex-wrap gap-4">
          {[
            { label: "Boiler ACM", value: hasAcm, set: setHasAcm },
            { label: "Ventilație", value: hasVentilation, set: setHasVentilation },
            { label: "Recuperator HRV", value: hasHrv, set: setHasHrv },
            { label: "Încălzire pardoseală", value: hasFloorHeating, set: setHasFloorHeating },
          ].map(({ label, value, set }) => (
            <label key={label} className="flex items-center gap-2 cursor-pointer select-none text-sm">
              <input type="checkbox" checked={value} onChange={e => set(e.target.checked)}
                className="w-4 h-4 rounded accent-emerald-400" />
              <span style={{ color: "var(--text)" }}>{label}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Camere */}
      <div className={card} style={cardStyle}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-bold uppercase tracking-widest" style={{ color: "var(--accent)" }}>
            04 — Camere ({rooms.length})
          </h2>
          <button type="button" onClick={addRoom}
            className="text-xs px-3 py-1.5 rounded-lg font-semibold transition hover:opacity-80"
            style={{ background: "var(--accent)", color: "#000" }}>
            + Adaugă cameră
          </button>
        </div>
        <div className="space-y-3">
          {rooms.map((room, i) => (
            <div key={i} className="rounded-lg p-4" style={{ background: "#141C2E", border: "1px solid var(--border)" }}>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3">
                <div className="col-span-2 sm:col-span-1">
                  <label className={labelCls} style={labelStyle}>Nume cameră</label>
                  <input className={inputCls} style={inputStyle} placeholder="Ex: Living"
                    value={room.name} onChange={e => updateRoom(i, "name", e.target.value)} />
                </div>
                <div>
                  <label className={labelCls} style={labelStyle}>Nivel</label>
                  <input className={inputCls} style={inputStyle} placeholder="Parter"
                    value={room.level} onChange={e => updateRoom(i, "level", e.target.value)} />
                </div>
                <div>
                  <label className={labelCls} style={labelStyle}>Funcție</label>
                  <select className={inputCls} style={inputStyle} value={room.function}
                    onChange={e => updateRoom(i, "function", e.target.value)}>
                    {ROOM_FUNCTIONS.map(f => <option key={f.value} value={f.value}>{f.label}</option>)}
                  </select>
                </div>
                <div>
                  <label className={labelCls} style={labelStyle}>Suprafață (m²)</label>
                  <input type="number" min="1" className={inputCls} style={inputStyle}
                    value={room.area_m2 || ""} onChange={e => updateRoom(i, "area_m2", parseFloat(e.target.value) || 0)} />
                </div>
              </div>
              <div className="grid grid-cols-3 sm:grid-cols-5 gap-3 items-end">
                <div>
                  <label className={labelCls} style={labelStyle}>Înălțime (m)</label>
                  <input type="number" step="0.1" min="2" className={inputCls} style={inputStyle}
                    value={room.height_m} onChange={e => updateRoom(i, "height_m", parseFloat(e.target.value) || 2.7)} />
                </div>
                <label className="flex items-center gap-2 cursor-pointer text-sm">
                  <input type="checkbox" checked={room.has_tv} onChange={e => updateRoom(i, "has_tv", e.target.checked)}
                    className="w-4 h-4 accent-emerald-400" />
                  <span style={{ color: "var(--text)" }}>TV</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer text-sm">
                  <input type="checkbox" checked={room.has_nightstands} onChange={e => updateRoom(i, "has_nightstands", e.target.checked)}
                    className="w-4 h-4 accent-emerald-400" />
                  <span style={{ color: "var(--text)" }}>Noptiere</span>
                </label>
                {rooms.length > 1 && (
                  <button type="button" onClick={() => removeRoom(i)}
                    className="text-xs px-2 py-1 rounded transition hover:opacity-80"
                    style={{ color: "#EF4444", border: "1px solid #EF444444" }}>
                    Șterge
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {error && (
        <div className="rounded-lg px-4 py-3 mb-4 text-sm" style={{ background: "#EF444422", border: "1px solid #EF4444", color: "#FCA5A5" }}>
          {error}
        </div>
      )}

      <button type="submit" disabled={loading}
        className="w-full py-3 rounded-xl font-bold text-sm uppercase tracking-widest transition hover:opacity-90 disabled:opacity-50"
        style={{ background: "linear-gradient(90deg, #00C896, #6366F1)", color: "#fff" }}>
        {loading ? "Se calculează..." : "⚡ Generează proiect electric"}
      </button>
    </form>
  );
}
