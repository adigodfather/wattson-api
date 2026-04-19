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

// ─── shared style atoms ────────────────────────────────────────────────────
const card: React.CSSProperties = {
  background: "#0D1117", border: "1px solid #1E293B",
  borderRadius: 14, padding: "24px", marginBottom: 16,
};
const sectionTitle = (color = "#00C896"): React.CSSProperties => ({
  fontSize: 10, fontWeight: 800, letterSpacing: 3,
  textTransform: "uppercase", color, marginBottom: 18,
  display: "flex", alignItems: "center", gap: 8,
});
const label: React.CSSProperties = {
  display: "block", fontSize: 10, fontWeight: 700,
  letterSpacing: 1.5, textTransform: "uppercase",
  color: "#475569", marginBottom: 6,
};
const input: React.CSSProperties = {
  width: "100%", padding: "9px 12px", borderRadius: 8,
  background: "#141C2E", border: "1px solid #1E293B",
  color: "#E2E8F0", fontSize: 13, outline: "none",
  boxSizing: "border-box",
};
const grid = (cols: string): React.CSSProperties => ({
  display: "grid", gridTemplateColumns: cols, gap: 14,
});
const checkRow: React.CSSProperties = {
  display: "flex", alignItems: "center", gap: 8,
  cursor: "pointer", fontSize: 13, color: "#94A3B8",
};

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

  const handleSubmit = (e: React.SyntheticEvent<HTMLFormElement>) => {
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

  return (
    <form onSubmit={handleSubmit}>

      {/* ── 01 Proiect ────────────────────────────────── */}
      <div style={card}>
        <div style={sectionTitle("#00C896")}>
          <span style={{ background: "#00C89622", color: "#00C896", padding: "2px 8px", borderRadius: 6, fontSize: 9 }}>01</span>
          Proiect
        </div>
        <div style={grid("1fr 1fr")}>
          <div>
            <label style={label}>Nume proiect</label>
            <input style={input} placeholder="ex: Casa Ionescu P+M 160m²"
              value={projectId} onChange={e => setProjectId(e.target.value)} />
          </div>
          <div>
            <label style={label}>Tip clădire</label>
            <select style={input} value={buildingType} onChange={e => setBuildingType(e.target.value)}>
              <option value="casa_unifamiliala">Casă unifamilială</option>
              <option value="duplex">Duplex</option>
              <option value="apartament">Apartament</option>
              <option value="spatiu_comercial">Spațiu comercial</option>
            </select>
          </div>
        </div>
      </div>

      {/* ── 02 Clădire ────────────────────────────────── */}
      <div style={card}>
        <div style={sectionTitle("#6366F1")}>
          <span style={{ background: "#6366F122", color: "#6366F1", padding: "2px 8px", borderRadius: 6, fontSize: 9 }}>02</span>
          Clădire
        </div>
        <div style={{ ...grid("1fr 1fr 1fr 1fr"), marginBottom: 14 }}>
          <div>
            <label style={label}>Regim înălțime</label>
            <select style={input} value={levels} onChange={e => setLevels(e.target.value)}>
              {["P", "P+M", "P+1", "P+1+M", "P+2"].map(l => <option key={l}>{l}</option>)}
            </select>
          </div>
          <div>
            <label style={label}>Zonă climatică</label>
            <select style={input} value={climateZone} onChange={e => setClimateZone(e.target.value)}>
              {["I", "II", "III", "IV", "V"].map(z => <option key={z}>{z}</option>)}
            </select>
          </div>
          <div>
            <label style={label}>Izolație</label>
            <select style={input} value={insulation} onChange={e => setInsulation(e.target.value as ProjectPayload["building"]["insulation_level"])}>
              <option value="slaba">Slabă</option>
              <option value="medie">Medie</option>
              <option value="buna">Bună (normativ)</option>
              <option value="foarte_buna">Foarte bună</option>
            </select>
          </div>
          <div>
            <label style={label}>Suprafață calculată</label>
            <div style={{ ...input, color: "#00C896", fontFamily: "monospace", fontSize: 12 }}>
              {totalArea.toFixed(1)} m² · {totalVolume.toFixed(1)} m³
            </div>
          </div>
        </div>
      </div>

      {/* ── 03 Sistem de încălzire ────────────────────── */}
      <div style={card}>
        <div style={sectionTitle("#EC4899")}>
          <span style={{ background: "#EC489922", color: "#EC4899", padding: "2px 8px", borderRadius: 6, fontSize: 9 }}>03</span>
          Sistem de încălzire
        </div>
        <div style={{ ...grid("1fr 1fr"), marginBottom: 18 }}>
          <div>
            <label style={label}>Tip încălzire</label>
            <select style={input} value={heatingType} onChange={e => setHeatingType(e.target.value as ProjectPayload["heating"]["type"])}>
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
              <label style={label}>Faze PDC</label>
              <select style={input} value={pdcPhase} onChange={e => setPdcPhase(e.target.value as "mono" | "tri")}>
                <option value="tri">Trifazat</option>
                <option value="mono">Monofazat</option>
              </select>
            </div>
          )}
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 20 }}>
          {[
            { label: "Boiler ACM electric", value: hasAcm, set: setHasAcm },
            { label: "Ventilație mecanică", value: hasVentilation, set: setHasVentilation },
            { label: "Recuperator HRV", value: hasHrv, set: setHasHrv },
            { label: "Încălzire pardoseală", value: hasFloorHeating, set: setHasFloorHeating },
          ].map(({ label: lbl, value, set }) => (
            <label key={lbl} style={checkRow}>
              <input type="checkbox" checked={value} onChange={e => set(e.target.checked)}
                style={{ accentColor: "#00C896", width: 15, height: 15 }} />
              {lbl}
            </label>
          ))}
        </div>
      </div>

      {/* ── 04 Camere ─────────────────────────────────── */}
      <div style={card}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 18 }}>
          <div style={sectionTitle("#F59E0B")}>
            <span style={{ background: "#F59E0B22", color: "#F59E0B", padding: "2px 8px", borderRadius: 6, fontSize: 9 }}>04</span>
            Camere ({rooms.length})
          </div>
          <button type="button" onClick={addRoom} style={{
            padding: "7px 16px", borderRadius: 8, border: "none",
            background: "#00C896", color: "#000", fontSize: 12,
            fontWeight: 700, cursor: "pointer",
          }}>
            + Adaugă cameră
          </button>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {rooms.map((room, i) => (
            <div key={i} style={{ background: "#141C2E", border: "1px solid #1E293B", borderRadius: 10, padding: "16px" }}>
              <div style={{ ...grid("2fr 1fr 1fr 1fr"), marginBottom: 12 }}>
                <div>
                  <label style={label}>Cameră</label>
                  <input style={input} placeholder="ex: Living"
                    value={room.name} onChange={e => updateRoom(i, "name", e.target.value)} />
                </div>
                <div>
                  <label style={label}>Nivel</label>
                  <input style={input} placeholder="Parter"
                    value={room.level} onChange={e => updateRoom(i, "level", e.target.value)} />
                </div>
                <div>
                  <label style={label}>Funcție</label>
                  <select style={input} value={room.function} onChange={e => updateRoom(i, "function", e.target.value)}>
                    {ROOM_FUNCTIONS.map(f => <option key={f.value} value={f.value}>{f.label}</option>)}
                  </select>
                </div>
                <div>
                  <label style={label}>Suprafață (m²)</label>
                  <input type="number" min="1" style={input}
                    value={room.area_m2 || ""}
                    onChange={e => updateRoom(i, "area_m2", parseFloat(e.target.value) || 0)} />
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 20, flexWrap: "wrap" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <label style={{ ...label, marginBottom: 0 }}>Înălțime (m)</label>
                  <input type="number" step="0.1" min="2" style={{ ...input, width: 80 }}
                    value={room.height_m} onChange={e => updateRoom(i, "height_m", parseFloat(e.target.value) || 2.7)} />
                </div>
                <label style={checkRow}>
                  <input type="checkbox" checked={room.has_tv} onChange={e => updateRoom(i, "has_tv", e.target.checked)}
                    style={{ accentColor: "#00C896", width: 14, height: 14 }} />
                  TV / Prize date
                </label>
                <label style={checkRow}>
                  <input type="checkbox" checked={room.has_nightstands} onChange={e => updateRoom(i, "has_nightstands", e.target.checked)}
                    style={{ accentColor: "#00C896", width: 14, height: 14 }} />
                  Noptiere
                </label>
                {rooms.length > 1 && (
                  <button type="button" onClick={() => removeRoom(i)} style={{
                    marginLeft: "auto", padding: "4px 12px", borderRadius: 6,
                    background: "transparent", border: "1px solid #EF444444",
                    color: "#EF4444", fontSize: 11, cursor: "pointer",
                  }}>
                    Șterge
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div style={{ background: "#EF444415", border: "1px solid #EF444444", borderRadius: 10, padding: "12px 16px", marginBottom: 16, color: "#FCA5A5", fontSize: 13 }}>
          ⚠ {error}
        </div>
      )}

      {/* Submit */}
      <button type="submit" disabled={loading} style={{
        width: "100%", padding: "15px", borderRadius: 12, border: "none",
        background: loading ? "#1E293B" : "linear-gradient(90deg,#00C896,#6366F1)",
        color: loading ? "#475569" : "#fff",
        fontSize: 14, fontWeight: 800, letterSpacing: 1,
        textTransform: "uppercase", cursor: loading ? "not-allowed" : "pointer",
        transition: "opacity .2s",
      }}>
        {loading ? "⚡ Se calculează..." : "⚡ Generează proiect electric"}
      </button>
    </form>
  );
}
