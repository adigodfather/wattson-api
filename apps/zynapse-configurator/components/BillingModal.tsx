"use client";

// ─── Gate facturare (G5) ─────────────────────────────────────────────────────
// Modal pe „Cumpără": 3 opțiuni de facturare, OBLIGATORIU una validă înainte de plată.
// Datele se trimit la /api/payment/start (re-validate server-side) -> factură corectă din prima.
// NU atinge Configuratorul de planșe.

import { useEffect, useState } from "react";
import Link from "next/link";
import { createClient } from "@/lib/supabase";
import type { BillingChoice } from "@/lib/payment/startCheckout";

type Prof = {
  full_name: string | null;
  firma_nume: string | null;
  firma_cui: string | null;
  firma_adresa: string | null;
  firma_email: string | null;
  last_billing_type: string | null;
  admin_name: string | null;
};

const ACCENT = "#378ADD";
const isType = (s: string | null | undefined): s is BillingChoice["type"] =>
  s === "company_profile" || s === "company_custom" || s === "individual";

// Judeţele (41 + Bucureşti) — valorile se trimit ca atare la SmartBill (câmpul `county`), care le
// mapează în e-Factura (cbc:CountrySubentity). Nume COMPLETE fără diacritice: formatul din exemplele
// SmartBill ("county" => "Galati" / setCounty("Bucharest")); matching-ul lor e pe numele judeţului,
// nu pe abreviere (NU "CJ"/"B").
const JUDETE = [
  "Alba", "Arad", "Arges", "Bacau", "Bihor", "Bistrita-Nasaud", "Botosani", "Braila", "Brasov",
  "Bucuresti", "Buzau", "Calarasi", "Caras-Severin", "Cluj", "Constanta", "Covasna", "Dambovita",
  "Dolj", "Galati", "Giurgiu", "Gorj", "Harghita", "Hunedoara", "Ialomita", "Iasi", "Ilfov",
  "Maramures", "Mehedinti", "Mures", "Neamt", "Olt", "Prahova", "Salaj", "Satu Mare", "Sibiu",
  "Suceava", "Teleorman", "Timis", "Tulcea", "Valcea", "Vaslui", "Vrancea",
];

export default function BillingModal({
  open, submitting, error, onConfirm, onCancel,
}: {
  open: boolean;
  submitting?: boolean;
  error?: string | null;
  onConfirm: (b: BillingChoice) => void;
  onCancel: () => void;
}) {
  const [prof, setProf] = useState<Prof | null>(null);
  const [type, setType] = useState<BillingChoice["type"]>("individual");
  const [adminName, setAdminName] = useState("");
  const [cName, setCName] = useState("");
  const [cVat, setCVat] = useState("");
  const [cAddr, setCAddr] = useState("");
  const [cEmail, setCEmail] = useState("");
  // e-Factura B2C: adresa persoanei fizice (judeţ + localitate OBLIGATORII pt. validarea ANAF)
  const [iCounty, setICounty] = useState("");
  const [iCity, setICity] = useState("");
  const [iAddr, setIAddr] = useState("");
  const [iCnp, setICnp] = useState("");

  useEffect(() => {
    if (!open) return;
    const supabase = createClient();
    let cancelled = false;
    supabase.auth.getUser().then(({ data: { user } }) => {
      if (!user || cancelled) return;
      supabase
        .from("profiles")
        .select("full_name, firma_nume, firma_cui, firma_adresa, firma_email, last_billing_type, admin_name")
        .eq("id", user.id)
        .single()
        .then(({ data }) => {
          if (cancelled || !data) return;
          const p = data as Prof;
          setProf(p);
          setAdminName(p.admin_name || "");
          setType(isType(p.last_billing_type) ? p.last_billing_type : "individual");
        });
      // PRESET B2C: datele din ULTIMA plată ca persoană fizică (RLS payments_select_own).
      // Sursa = ce s-a facturat efectiv -> zero coloane noi în profiles, mereu sincron.
      supabase
        .from("payments")
        .select("billing_data, created_at")
        .eq("user_id", user.id)
        .eq("billing_type", "individual")
        .order("created_at", { ascending: false })
        .limit(1)
        .then(({ data }) => {
          if (cancelled || !data?.length) return;
          const bd = (data[0].billing_data || {}) as Record<string, string>;
          setICounty(bd.county || "");
          setICity(bd.city || "");
          setIAddr(bd.address || "");
          setICnp(bd.cnp || "");
        });
    });
    return () => { cancelled = true; };
  }, [open]);

  if (!open) return null;

  const hasFirma = !!(prof?.firma_cui || "").trim();
  const valid =
    // B2C: numele + judeţul + localitatea sunt obligatorii (fără ele e-Factura e respinsă la SPV)
    type === "individual" ? !!(prof?.full_name || "").trim() && !!iCounty.trim() && !!iCity.trim()
    : type === "company_profile" ? hasFirma && !!adminName.trim()
    : !!cName.trim() && !!cVat.trim() && !!cAddr.trim();

  function confirm() {
    if (!valid || submitting) return;
    if (type === "individual") onConfirm({
      type: "individual",
      county: iCounty.trim(), city: iCity.trim(),
      address: iAddr.trim(), cnp: iCnp.trim(),
    });
    else if (type === "company_profile") onConfirm({ type: "company_profile", adminName: adminName.trim() });
    else onConfirm({ type: "company_custom", name: cName.trim(), vatCode: cVat.trim(), address: cAddr.trim(), email: cEmail.trim(), adminName: adminName.trim() });
  }

  const opt = (val: BillingChoice["type"], title: string, sub: string) => {
    const on = type === val;
    return (
      <button type="button" onClick={() => setType(val)} style={{
        display: "block", width: "100%", textAlign: "left", padding: "12px 14px", borderRadius: 10,
        cursor: "pointer", fontFamily: "inherit", marginBottom: 8,
        background: on ? "rgba(55,138,221,0.12)" : "rgba(255,255,255,0.02)",
        border: `1px solid ${on ? "rgba(55,138,221,0.5)" : "rgba(255,255,255,0.08)"}`,
        transition: "background-color .15s, border-color .15s",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
          <span style={{
            width: 16, height: 16, borderRadius: "50%", flexShrink: 0,
            border: `2px solid ${on ? ACCENT : "#545870"}`,
            boxShadow: on ? `inset 0 0 0 3px ${ACCENT}` : "none",
          }} />
          <span style={{ fontSize: 14, fontWeight: 600, color: on ? "#9FD2FA" : "#C8CAD6" }}>{title}</span>
        </div>
        <div style={{ fontSize: 12, color: "#8B8FA8", marginTop: 3, marginLeft: 25 }}>{sub}</div>
      </button>
    );
  };

  const inputStyle: React.CSSProperties = {
    width: "100%", padding: "9px 12px", borderRadius: 9, fontSize: 13.5, marginTop: 6,
    background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.1)",
    color: "#E2E4E9", outline: "none", fontFamily: "inherit", boxSizing: "border-box",
  };
  const lbl: React.CSSProperties = { fontSize: 11, fontWeight: 600, letterSpacing: ".04em", color: "#8B8FA8", textTransform: "uppercase" };

  return (
    <div onClick={onCancel} style={{
      position: "fixed", inset: 0, zIndex: 60, display: "flex", alignItems: "center", justifyContent: "center",
      background: "rgba(0,0,0,0.78)", backdropFilter: "blur(4px)", padding: 18,
      fontFamily: "'DM Sans', system-ui, sans-serif",
    }}>
      <div onClick={(e) => e.stopPropagation()} style={{
        width: "100%", maxWidth: 460, maxHeight: "90vh", overflowY: "auto", borderRadius: 16,
        background: "#0E1014", border: "1px solid rgba(255,255,255,0.09)", padding: "24px 22px",
        boxShadow: "0 20px 60px rgba(0,0,0,0.6)",
      }}>
        <h2 style={{ margin: "0 0 4px", fontSize: 18, fontWeight: 700, color: "#E2E4E9" }}>Date de facturare</h2>
        <p style={{ margin: "0 0 18px", fontSize: 12.5, color: "#8B8FA8", lineHeight: 1.5 }}>
          Alege cum vrei să primești factura. O completezi o singură dată; rămâne presetată data viitoare.
        </p>

        {opt("company_profile", "Folosesc datele firmei", "Factură pe firma din Setări (CIF, denumire, adresă).")}
        {type === "company_profile" && (
          <div style={{ margin: "-2px 0 10px", padding: "10px 12px", borderRadius: 9, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)" }}>
            {hasFirma ? (
              <>
                <div style={{ fontSize: 12.5, color: "#C8CAD6", lineHeight: 1.6 }}>
                  <strong style={{ color: "#E2E4E9" }}>{prof?.firma_nume || "—"}</strong><br />
                  CUI: {prof?.firma_cui || "—"} · {prof?.firma_adresa || "fără adresă"}
                </div>
                <label style={{ display: "block", marginTop: 10 }}>
                  <span style={lbl}>Nume administrator *</span>
                  <input style={inputStyle} value={adminName} onChange={(e) => setAdminName(e.target.value)} placeholder="Ion Popescu" />
                </label>
              </>
            ) : (
              <div style={{ fontSize: 12.5, color: "#F0B95B", lineHeight: 1.6 }}>
                Nu ai datele firmei completate.{" "}
                <Link href="/settings" style={{ color: "#5BB8F5" }}>Completează-le în Setări</Link>, apoi revino.
              </div>
            )}
          </div>
        )}

        {opt("company_custom", "Date de facturare diferite", "Altă firmă decât cea din Setări.")}
        {type === "company_custom" && (
          <div style={{ margin: "-2px 0 10px", display: "flex", flexDirection: "column", gap: 8 }}>
            <label><span style={lbl}>Denumire firmă *</span><input style={inputStyle} value={cName} onChange={(e) => setCName(e.target.value)} placeholder="S.C. EXEMPLU S.R.L." /></label>
            <label><span style={lbl}>CUI / CIF *</span><input style={inputStyle} value={cVat} onChange={(e) => setCVat(e.target.value)} placeholder="RO12345678" /></label>
            <label><span style={lbl}>Adresă *</span><input style={inputStyle} value={cAddr} onChange={(e) => setCAddr(e.target.value)} placeholder="Str. Exemplu nr. 1, Cluj-Napoca" /></label>
            <label><span style={lbl}>Email facturare</span><input style={inputStyle} value={cEmail} onChange={(e) => setCEmail(e.target.value)} placeholder="contact@firma.ro" /></label>
            <label><span style={lbl}>Nume reprezentant</span><input style={inputStyle} value={adminName} onChange={(e) => setAdminName(e.target.value)} placeholder="Ion Popescu" /></label>
          </div>
        )}

        {opt("individual", "Beneficiar persoană fizică", "Factură pe numele tău.")}
        {type === "individual" && (
          <div style={{ margin: "-2px 0 10px", padding: "10px 12px", borderRadius: 9, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)" }}>
            <div style={{ fontSize: 12.5, color: "#C8CAD6" }}>
              Factură pe: <strong style={{ color: "#E2E4E9" }}>{prof?.full_name || "—"}</strong>
            </div>
            {/* e-Factura: ANAF cere judeţ + localitate şi pentru persoane fizice (altfel SPV respinge factura). */}
            <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 10 }}>
              <label>
                <span style={lbl}>Județ *</span>
                <select style={{ ...inputStyle, appearance: "none", cursor: "pointer" }} value={iCounty} onChange={(e) => setICounty(e.target.value)}>
                  <option value="" style={{ background: "#0E1014" }}>Alege județul…</option>
                  {JUDETE.map(j => <option key={j} value={j} style={{ background: "#0E1014" }}>{j}</option>)}
                </select>
              </label>
              <label><span style={lbl}>Localitate *</span><input style={inputStyle} value={iCity} onChange={(e) => setICity(e.target.value)} placeholder="Cluj-Napoca" /></label>
              <label><span style={lbl}>Adresă</span><input style={inputStyle} value={iAddr} onChange={(e) => setIAddr(e.target.value)} placeholder="Str. Exemplu nr. 1, ap. 2" /></label>
              <label><span style={lbl}>CNP</span><input style={inputStyle} value={iCnp} onChange={(e) => setICnp(e.target.value)} placeholder="opțional" inputMode="numeric" /></label>
              <div style={{ fontSize: 11.5, color: "#8B8FA8", lineHeight: 1.5 }}>
                Județul și localitatea sunt cerute de ANAF pentru e-Factură. Fără CNP, factura se emite cu codul generic de persoană fizică.
              </div>
            </div>
          </div>
        )}

        {error && (
          <div style={{ margin: "6px 0 0", padding: "9px 12px", borderRadius: 9, fontSize: 12.5, background: "rgba(226,75,74,0.1)", border: "1px solid rgba(226,75,74,0.22)", color: "#F09595" }}>{error}</div>
        )}

        <div style={{ display: "flex", gap: 10, marginTop: 18 }}>
          <button type="button" onClick={onCancel} disabled={submitting} style={{
            flex: "0 0 auto", padding: "11px 18px", borderRadius: 10, fontSize: 13.5, fontWeight: 600, fontFamily: "inherit",
            background: "transparent", border: "1px solid rgba(255,255,255,0.12)", color: "#8B8FA8", cursor: "pointer",
          }}>Anulează</button>
          <button type="button" onClick={confirm} disabled={!valid || submitting} style={{
            flex: 1, padding: "11px 18px", borderRadius: 10, fontSize: 13.5, fontWeight: 700, fontFamily: "inherit", color: "#fff",
            border: "none", cursor: !valid || submitting ? "not-allowed" : "pointer", opacity: !valid || submitting ? 0.5 : 1,
            background: "linear-gradient(135deg, #2870C2 0%, #378ADD 100%)",
          }}>{submitting ? "Se redirecționează…" : "Continuă spre plată"}</button>
        </div>
      </div>
    </div>
  );
}
