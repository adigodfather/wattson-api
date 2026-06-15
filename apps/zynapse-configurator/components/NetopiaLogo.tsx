"use client";

// Sigla oficiala NETOPIA (Visa/Mastercard) — ceruta de Netopia pentru aprobare.
// Pachet oficial ntp-logo-react (author: NETOPIA). `secret` = id PUBLIC de afisare
// a siglei (incarca SVG-ul de la mny.ro), NU are legatura cu NETOPIA_SIGNATURE/chei.
// Wrapper "use client": componenta foloseste onClick (window.open) -> interactiv,
// deci nu poate fi randata direct intr-un Server Component.
import NTPIdentity from "ntp-logo-react";

export default function NetopiaLogo() {
  // version != "vertical" -> logo ORIZONTAL. color = fundalul pe care sta (footer inchis)
  // -> componenta alege automat varianta alba a siglei.
  return (
    <div style={{ width: 220, height: 44, margin: "0 auto" }}>
      <NTPIdentity color="#050709" version="horizontal" secret="165954" />
    </div>
  );
}
