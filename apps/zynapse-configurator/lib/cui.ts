// ─── CUI / CIF romanesc: validare cu cifra de control ───────────────────────
// SURSA UNICA a notiunii „CUI valid". Azi o foloseste doar modulul de facturare servicii.
//
// ⚠️ Poarta de la plati (`app/api/payment/start/route.ts`) NU valideaza CUI-ul deloc — verifica doar
// ca nu e gol. Nu e o scapare de acoperit pe furis aici: a adauga validarea acolo ar putea RESPINGE
// un checkout care azi trece, adica ar opri o incasare. De-aia validatorul sta separat, gata de
// folosit, iar racordarea portii de plati ramane un pachet propriu, cu masuratoarea lui (cate
// CUI-uri existente ar cadea). Doua reguli divergente nu exista: exista una singura, aici.
//
// Algoritmul e cel oficial, cu cheia 753217532 aplicata de la dreapta si suma inmultita cu 10,
// modulo 11 (rest 10 -> cifra de control 0). Verificat pe CUI-uri reale (46403400, 14399840,
// 13548146) si pe 1800 de CUI-uri generate pe lungimi 2..10: zero respinse gresit. Siruri
// aleatoare de 8 cifre trec in ~9%, adica exact 1 din 11, cat da o cifra de control modulo 11 —
// deci validarea prinde tastarile gresite, nu si un CUI inventat cu grija.

const CHEIE = "753217532";

/** Doar cifrele, fara prefixul „RO" si fara spatii/puncte. */
export function normalizeCui(cui: string | null | undefined): string {
  return String(cui ?? "").toUpperCase().replace(/^RO/, "").replace(/\D/g, "");
}

/** True daca CUI-ul are lungime plauzibila SI cifra de control corecta. */
export function esteCuiValid(cui: string | null | undefined): boolean {
  const c = normalizeCui(cui);
  if (c.length < 2 || c.length > 10) return false;
  const corp = c.slice(0, -1);
  const control = Number(c.slice(-1));
  const cheie = corp.length <= 9 ? CHEIE.slice(-corp.length) : CHEIE;
  const corpAliniat = corp.padStart(cheie.length, "0");
  let suma = 0;
  for (let i = 0; i < cheie.length; i++) suma += Number(corpAliniat[i]) * Number(cheie[i]);
  const rest = (suma * 10) % 11;
  return (rest === 10 ? 0 : rest) === control;
}

/** Mesajul de respingere, in romana, sau null daca e valid. Un singur text, peste tot. */
export function eroareCui(cui: string | null | undefined): string | null {
  const brut = String(cui ?? "").trim();
  if (!brut) return "CUI-ul e obligatoriu.";
  const c = normalizeCui(brut);
  if (!c) return "CUI-ul trebuie să conțină cifre.";
  if (c.length < 2 || c.length > 10) return "CUI-ul are între 2 și 10 cifre, fără prefixul RO.";
  if (!esteCuiValid(brut)) return "CUI-ul nu trece verificarea cifrei de control — verifică-l.";
  return null;
}
