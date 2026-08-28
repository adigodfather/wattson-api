// SPATII COMERCIALE — categorii, sub-tipuri si camere (sursa: spatii_comerciale_camere.md).
//
// PRINCIPIUL CENTRAL: numele generice se rezolva prin SUB-TIP. „Sala" nu inseamna nimic singura;
// pe un plan de fitness e sala de aparate, pe unul de restaurant e sala de servire. Fiecare sub-tip
// declara ce camera preia numele generic — separat pentru „sala" si pentru „spatiu", fiindca la
// spalatorie (C3) sunt DOUA camere diferite: „Spatiu" = primire, „Sala" = masini.
//
// CAMERELE COMUNE (grup sanitar, depozit, birou, vestiar, chicineta, receptie, camera tehnica, hol)
// sunt definite O SINGURA DATA in CAMERE_COMUNE si doar REFERITE de sub-tipuri. Regulile lor sunt
// deja implementate (grup sanitar = IP44 + RCCB 10mA, camera tehnica = TE-CT) si NU se ating aici.
//
// Recunoasterea numelor: regexurile primesc numele NORMALIZAT (lowercase, fara diacritice), deci
// sunt ASCII. Abrevierile scurte („S.", „Sp.") folosesc granite de cuvant si cer punct/spatiu dupa
// litera — tiparul fixului pentru G.S., altfel ar prinde orice inceput de cuvant.

export type CameraDef = { label: string; en: string; rx: RegExp };

// ── CAMERE (dictionar unic; sub-tipurile refera cheile) ──────────────────────────────────────
export const CAMERE_COMERCIALE: Record<string, CameraDef> = {
  // — comune (reguli DEJA implementate; listate ca sa apara in UI, nu ca sa fie redefinite) —
  grup_sanitar:   { label: "Grup sanitar",        en: "Restroom",            rx: /\bg\s*\.?\s*s\.?\b|sanitar|\bwc\b|\bbaie\b|toaleta/ },
  depozit:        { label: "Depozit",             en: "Storage",             rx: /\bdep\.?\b|depoz|depozit|magazie|\bcamara\b/ },
  birou:          { label: "Birou",               en: "Office",              rx: /\bbir\.?\b|\bbirou/ },
  vestiar:        { label: "Vestiar",             en: "Changing room",       rx: /\bvest\.?\b|\bvst\.?\b|vestiar|garderob/ },
  chicineta:      { label: "Chicinetă",           en: "Kitchenette",         rx: /\bchic\.?\b|chicinet|\boficiu\b/ },
  receptie:       { label: "Recepție",            en: "Reception",           rx: /\brec\.?\b|receptie|recept|\bprimire\b/ },
  // „C.T." cerea \b dupa punctul final, care nu se potriveste niciodata -> nu prindea. Acum cerem
  // PUNCTUL intre c si t (asa „ctitor" nu poate prinde) si interzicem litera dupa.
  camera_tehnica: { label: "Cameră tehnică",      en: "Technical room",      rx: /\bcam\.?\s*tehnic|\bc\s*\.\s*t\s*\.?(?!\w)|sp\.?\s*tehnic|\btehnic/ },
  hol:            { label: "Hol / circulație",    en: "Corridor",            rx: /\bh\.?\b|\bhol\b|culoar|coridor/ },

  // — A. COMERT —
  vanzare:        { label: "Spațiu vânzare",      en: "Sales area",          rx: /vanzare|\bmagazin/ },
  casa_marcat:    { label: "Casă de marcat",      en: "Checkout",            rx: /casa\s*(de\s+)?marcat|\bc\.?\s*m\.?\b|zona\s*case/ },
  cam_frigorifica:{ label: "Cameră frigorifică",  en: "Cold room",           rx: /frigorific|camera\s*frig/ },
  receptie_marfa: { label: "Recepție marfă",      en: "Goods receiving",     rx: /rec\.?\s*marfa|receptie\s*marfa|primire\s*marfa/ },
  oficina:        { label: "Oficină",             en: "Pharmacy front",      rx: /oficina|\bfarmacie\b/ },
  receptura:      { label: "Receptură",           en: "Compounding room",    rx: /receptura|prep\.?\s*medicament/ },
  expunere:       { label: "Spațiu expunere",     en: "Showroom",            rx: /expunere|showroom/ },

  // — B. ALIMENTATIE —
  servire:        { label: "Sală servire",        en: "Dining area",         rx: /servire|sala\s*mese|sala\s*restaurant|sala\s*consum|\bcafenea\b/ },
  bucatarie:      { label: "Bucătărie",           en: "Kitchen",             rx: /\bbuc\.?\b|bucatar/ },
  bar:            { label: "Bar",                 en: "Bar",                 rx: /\bbar\b|tejghea|zona\s*bar/ },
  spalator_vase:  { label: "Spălător vase",       en: "Dishwashing",         rx: /spalator|sp\.?\s*vase|spalare\s*vase/ },
  zona_preparare: { label: "Zonă preparare",      en: "Prep area",           rx: /zona\s*prep|preparare/ },
  terasa:         { label: "Terasă",              en: "Terrace",             rx: /\bteras|\bter\.?\b/ },

  // — C. SERVICII PERSONALE —
  sala_lucru:     { label: "Sală lucru",          en: "Work area",           rx: /\blucru\b|coafura|\bsalon\b|frizerie/ },
  zona_spalare:   { label: "Zonă spălare",        en: "Washing area",        rx: /zona\s*spalare|\bscafe\b|sp\.?\s*spalare|\bspalare\b/ },
  sterilizare:    { label: "Sterilizare",         en: "Sterilization",       rx: /steril/ },
  manichiura:     { label: "Sală manichiură",     en: "Manicure area",       rx: /manichiura|salon\s*unghii/ },
  cabina_trat:    { label: "Cabină tratament",    en: "Treatment room",      rx: /cab\.?\s*tratament|\bcabina\b/ },
  primire:        { label: "Spațiu primire",      en: "Reception",           rx: /sp\.?\s*primire|\bprimire\b/ },
  sala_masini:    { label: "Sală mașini",         en: "Machine room",        rx: /\bmasini\b/ },
  zona_calcat:    { label: "Zonă călcat",         en: "Ironing area",        rx: /calcat|calcatorie/ },

  // — D. MEDICAL —
  cabinet:        { label: "Cabinet",             en: "Treatment room",      rx: /\bcab\.?\b|\bcbt\.?\b|cabinet|consultatii|\bunit\b/ },
  radiologie:     { label: "Radiologie",          en: "X-ray room",          rx: /radiolog|\brx\b|\bcbct\b/ },
  asteptare:      { label: "Sală așteptare",      en: "Waiting room",        rx: /asteptare/ },
  sala_tratament: { label: "Sală tratament",      en: "Treatment room",      rx: /tratament|proceduri/ },
  recoltare:      { label: "Sală recoltare",      en: "Sampling room",       rx: /recoltar/ },
  laborator:      { label: "Laborator",           en: "Laboratory",          rx: /\blab\.?\b|laborator|\blabor\.?\b/ },
  dep_reactivi:   { label: "Depozit reactivi",    en: "Reagent storage",     rx: /reactivi/ },
  chirurgie:      { label: "Sală chirurgie",      en: "Surgery room",        rx: /chirurgie|\boperatii\b/ },
  cazare_animale: { label: "Cazare animale",      en: "Animal housing",      rx: /\bcazare\b|\bpadoc\b|\bcusti\b|stationar/ },

  // — E. SPORT / RECREERE —
  sala_aparate:   { label: "Sală aparate",        en: "Gym floor",           rx: /\baparate\b|\bfitness\b|s\.?\s*sport\b/ },
  sala_clase:     { label: "Sală clase",          en: "Group class room",    rx: /\bclase\b|sala\s*grup\b|aerobic|\bstudio\b/ },
  vestiar_b:      { label: "Vestiar bărbați",     en: "Men's changing room", rx: /vest\.?\s*barbati|\bv\.?\s*barbati|vestiar\s*b\b/ },
  vestiar_f:      { label: "Vestiar femei",       en: "Women's changing room", rx: /vest\.?\s*femei|\bv\.?\s*femei|vestiar\s*f\b/ },
  dusuri:         { label: "Dușuri",              en: "Showers",             rx: /\bdusuri\b|\bdus\b|zona\s*dusuri/ },
  sala_principala:{ label: "Sală principală",     en: "Main hall",           rx: /principala|evenimente|sala\s*mare/ },
  zona_joaca:     { label: "Zonă joacă",          en: "Play area",           rx: /joaca/ },

  // — F. BIROURI / ALTELE —
  sala_birouri:   { label: "Sală birouri",        en: "Open office",         rx: /birouri|open\s*-?\s*space/ },
  sala_sedinte:   { label: "Sală ședințe",        en: "Meeting room",        rx: /sedinte/ },
  camera_server:  { label: "Cameră server",       en: "Server room",         rx: /\bserver\b|camera\s*it\b|\brack\b/ },
  arhiva:         { label: "Arhivă",              en: "Archive",             rx: /\barhiva\b|\barh\.?\b/ },
  atelier:        { label: "Atelier",             en: "Workshop",            rx: /\bat\.?\b|\batel\.?\b|atelier/ },
  sala_grupa:     { label: "Sală grupă",          en: "Classroom",           rx: /\bgrupa\b|\bclasa\b/ },
  sala_mese:      { label: "Sală mese",           en: "Dining room",         rx: /\bmese\b/ },
  dormitor_copii: { label: "Dormitor",            en: "Nap room",            rx: /\bdorm\.?\b|dormitor|\bsomn\b/ },
};

// ── SUB-TIPURI: ce camere are fiecare + ce preia numele generic ──────────────────────────────
export type SubtipDef = {
  value: string; label: string;
  camere: string[];                              // chei din CAMERE_COMERCIALE
  generic: { sala?: string; spatiu?: string };    // ce camera preia „Sala" / „Spatiu"
};
export type CategorieDef = { value: string; label: string; icon: string; subtipuri: SubtipDef[] };

// Cele opt din sectiunea „CAMERE COMUNE" a referintei — disponibile in ORICE sub-tip, definite o data.
const COMUNE = ["grup_sanitar", "depozit", "vestiar", "chicineta", "birou", "receptie", "camera_tehnica", "hol"];

export const COMERCIAL_CATEGORII: CategorieDef[] = [
  { value: "comert", label: "Comerț", icon: "🛍️", subtipuri: [
    { value: "a1_magazin_general", label: "Magazin general / spațiu de închiriat",
      camere: ["vanzare", "casa_marcat", ...COMUNE], generic: { sala: "vanzare", spatiu: "vanzare" } },
    { value: "a2_alimentar", label: "Magazin alimentar / mixt",
      camere: ["vanzare", "casa_marcat", "cam_frigorifica", "receptie_marfa", "depozit", "vestiar", "grup_sanitar"],
      generic: { sala: "vanzare", spatiu: "vanzare" } },
    { value: "a3_farmacie", label: "Farmacie",
      camere: ["oficina", "receptura", "depozit", "birou", "vestiar", "grup_sanitar"],
      generic: { sala: "oficina", spatiu: "oficina" } },
    { value: "a4_showroom", label: "Showroom / magazin nealimentar",
      camere: ["expunere", "depozit", "birou", "grup_sanitar"], generic: { sala: "expunere", spatiu: "expunere" } },
  ]},
  { value: "alimentatie", label: "Alimentație publică", icon: "🍽️", subtipuri: [
    { value: "b1_restaurant", label: "Restaurant / fast-food",
      camere: ["servire", "bucatarie", "bar", "spalator_vase", "depozit", "cam_frigorifica", "vestiar", "grup_sanitar", "terasa"],
      generic: { sala: "servire", spatiu: "servire" } },
    { value: "b2_cafenea", label: "Cafenea / bar / cofetărie",
      camere: ["servire", "bar", "zona_preparare", "depozit", "vestiar", "grup_sanitar"],
      generic: { sala: "servire", spatiu: "servire" } },
  ]},
  { value: "servicii", label: "Servicii personale", icon: "💇", subtipuri: [
    { value: "c1_frizerie", label: "Frizerie / salon coafură",
      camere: ["sala_lucru", "zona_spalare", "receptie", "sterilizare", "depozit", "vestiar", "grup_sanitar"],
      generic: { sala: "sala_lucru", spatiu: "sala_lucru" } },
    { value: "c2_unghii", label: "Salon unghii / cosmetică",
      camere: ["manichiura", "cabina_trat", "receptie", "sterilizare", "depozit", "grup_sanitar"],
      generic: { sala: "manichiura", spatiu: "manichiura" } },
    // SINGURUL sub-tip cu DOUA camere generice diferite: „Spatiu" = primire, „Sala" = masini
    { value: "c3_spalatorie", label: "Spălătorie / curățătorie",
      camere: ["primire", "sala_masini", "zona_calcat", "depozit", "grup_sanitar"],
      generic: { sala: "sala_masini", spatiu: "primire" } },
  ]},
  { value: "medical", label: "Medical", icon: "🩺", subtipuri: [
    { value: "d1_stomatologic", label: "Cabinet stomatologic",
      camere: ["cabinet", "sterilizare", "radiologie", "receptie", "asteptare", "camera_tehnica", "vestiar", "grup_sanitar"],
      generic: { sala: "asteptare", spatiu: "asteptare" } },
    { value: "d2_medical", label: "Cabinet medical",
      camere: ["cabinet", "sala_tratament", "receptie", "asteptare", "sterilizare", "vestiar", "grup_sanitar"],
      generic: { sala: "asteptare", spatiu: "asteptare" } },
    { value: "d3_laborator", label: "Laborator analize",
      camere: ["recoltare", "laborator", "receptie", "asteptare", "dep_reactivi", "grup_sanitar"],
      generic: { sala: "asteptare", spatiu: "asteptare" } },
    { value: "d4_veterinar", label: "Cabinet veterinar",
      camere: ["cabinet", "chirurgie", "receptie", "asteptare", "sterilizare", "cazare_animale", "grup_sanitar"],
      generic: { sala: "asteptare", spatiu: "asteptare" } },
  ]},
  { value: "sport", label: "Sport / recreere", icon: "🏋️", subtipuri: [
    { value: "e1_fitness", label: "Sală fitness",
      camere: ["sala_aparate", "sala_clase", "receptie", "vestiar_b", "vestiar_f", "dusuri", "depozit", "grup_sanitar"],
      generic: { sala: "sala_aparate", spatiu: "sala_aparate" } },
    { value: "e2_evenimente", label: "Sală evenimente / loc de joacă",
      camere: ["sala_principala", "zona_joaca", "chicineta", "depozit", "vestiar", "grup_sanitar"],
      generic: { sala: "sala_principala", spatiu: "sala_principala" } },
  ]},
  { value: "birouri", label: "Birouri / altele", icon: "🏢", subtipuri: [
    { value: "f1_birou", label: "Birou / spațiu administrativ",
      camere: ["sala_birouri", "birou", "sala_sedinte", "receptie", "camera_server", "chicineta", "arhiva", "grup_sanitar"],
      generic: { sala: "sala_birouri", spatiu: "sala_birouri" } },
    { value: "f2_atelier", label: "Atelier service",
      camere: ["atelier", "receptie", "depozit", "grup_sanitar"], generic: { sala: "atelier", spatiu: "atelier" } },
    { value: "f3_gradinita", label: "Grădiniță / after-school",
      camere: ["sala_grupa", "sala_mese", "dormitor_copii", "chicineta", "vestiar", "grup_sanitar", "birou", "depozit"],
      generic: { sala: "sala_grupa", spatiu: "sala_grupa" } },
  ]},
];

export const SUBTIP_DEFAULT = "a1_magazin_general";

export function subtipById(value: string | null | undefined): SubtipDef | null {
  if (!value) return null;
  for (const cat of COMERCIAL_CATEGORII) {
    const s = cat.subtipuri.find((x) => x.value === value);
    if (s) return s;
  }
  return null;
}

// ── REGULI PE DESTINATIE (iluminat + prize + zona umeda), pe cheia camerei canonice ──────────
//
// PRINCIPIUL (decizia Dan): propunem MINIMUL NORMAT, inginerul adauga daca vrea. Un proiect
// sub-luminat e neconform; unul cu un panou in plus e doar mai scump.
//
// `lx` e documentar (nivelul minim normat, NP 061-2002 / SR EN 12464-1) — nu intra in niciun calcul;
// e acolo ca sa se vada DE CE are camera corpul si pasul astea, si ca sa poata fi contestat.
// `pas`/`prizePas` = „+1 la X mp" (null = valoare fixa, indiferent de suprafata).
// `prizaTip: "ip44"` + `umed` = zona umeda; vezi rccb_zone / _WET30 din enrich_circuits.py.
//
// CHEILE COMUNE (depozit, birou, receptie, vanzare, casa_marcat, sala_birouri, grup_sanitar...) sunt
// INTENTIONAT absente: au deja reguli din pasii anteriori si trebuie sa ramana neatinse. Cheia lipsa
// de aici -> se cade pe eticheta canonica si pe regulile vechi = exact comportamentul de dinainte.
export type RegulaCamera = {
  lx: number;                 // documentar: nivelul minim normat
  corp: string;               // element_type al corpului de iluminat
  w: number;                  // puterea unui corp
  pas: number | null;         // „+1 corp la X mp"
  prize: number;              // numar fix de prize
  prizePas: number | null;    // „+1 priza la X mp"
  prizaTip?: "ip44";          // zona umeda -> priza etansa
  umed?: "10ma" | "30ma";     // protectie diferentiala ceruta pe circuitul de prize
};

export const REGULI: Record<string, RegulaCamera> = {
  // — A. COMERT —
  cam_frigorifica: { lx: 150, corp: "aplica_tavan", w: 25, pas: null, prize: 2, prizePas: null },
  receptie_marfa:  { lx: 200, corp: "aplica_tavan", w: 25, pas: 12,   prize: 2, prizePas: null },
  oficina:         { lx: 500, corp: "panou_led",    w: 40, pas: 8,    prize: 4, prizePas: 12 },
  receptura:       { lx: 500, corp: "panou_led",    w: 40, pas: 8,    prize: 4, prizePas: null },
  expunere:        { lx: 300, corp: "panou_led",    w: 40, pas: 10,   prize: 4, prizePas: 12 },

  // — B. ALIMENTATIE —
  servire:         { lx: 200, corp: "panou_led",    w: 40, pas: 12,   prize: 4, prizePas: 15 },
  bucatarie:       { lx: 500, corp: "panou_led",    w: 40, pas: 8,    prize: 6, prizePas: 8 },
  bar:             { lx: 300, corp: "panou_led",    w: 40, pas: 10,   prize: 6, prizePas: 8 },
  // decizia Dan: se stropeste, dar NU e zona cu dus/cada -> circuit cu RCCB 30mA, priza NORMALA
  // (pragul de 10mA e rezervat zonelor 0-2 din I7, iar IP44 nu e justificat aici)
  spalator_vase:   { lx: 300, corp: "aplica_tavan", w: 25, pas: null, prize: 4, prizePas: null,
                     umed: "30ma" },
  zona_preparare:  { lx: 500, corp: "panou_led",    w: 40, pas: 8,    prize: 6, prizePas: 8 },
  // acelasi tip+putere ca terasa rezidentiala (aplica_senzor 30W) — se adauga DOAR pasul de suprafata
  terasa:          { lx: 100, corp: "aplica_senzor", w: 30, pas: 15,  prize: 2, prizePas: null },

  // — C. SERVICII PERSONALE —
  sala_lucru:      { lx: 500, corp: "panou_led",    w: 40, pas: 8,    prize: 4, prizePas: 6 },
  // decizia Dan: scafele NU sunt zona cu cada/dus -> priza NORMALA, dar circuit cu RCCB 30mA
  zona_spalare:    { lx: 300, corp: "aplica_tavan", w: 25, pas: null, prize: 2, prizePas: null,
                     umed: "30ma" },
  manichiura:      { lx: 500, corp: "panou_led",    w: 40, pas: 8,    prize: 4, prizePas: 6 },
  cabina_trat:     { lx: 300, corp: "aplica_tavan", w: 25, pas: null, prize: 2, prizePas: null },
  // decizia Dan: ca spalatorul de vase — RCCB 30mA, priza NORMALA (nu e zona cu dus/cada)
  sala_masini:     { lx: 300, corp: "panou_led",    w: 40, pas: 12,   prize: 6, prizePas: 10,
                     umed: "30ma" },
  zona_calcat:     { lx: 300, corp: "panou_led",    w: 40, pas: 12,   prize: 6, prizePas: 10 },
  primire:         { lx: 200, corp: "aplica_tavan", w: 25, pas: 12,   prize: 2, prizePas: null },

  // — D. MEDICAL —
  cabinet:         { lx: 500, corp: "panou_led",    w: 40, pas: 8,    prize: 6, prizePas: null },
  sala_tratament:  { lx: 500, corp: "panou_led",    w: 40, pas: 8,    prize: 4, prizePas: 12 },
  sterilizare:     { lx: 300, corp: "panou_led",    w: 40, pas: null, prize: 4, prizePas: null },
  radiologie:      { lx: 300, corp: "aplica_tavan", w: 25, pas: 8,    prize: 2, prizePas: null },
  laborator:       { lx: 500, corp: "panou_led",    w: 40, pas: 8,    prize: 4, prizePas: null },
  recoltare:       { lx: 500, corp: "panou_led",    w: 40, pas: 8,    prize: 4, prizePas: null },
  dep_reactivi:    { lx: 150, corp: "aplica_tavan", w: 25, pas: null, prize: 2, prizePas: null },
  // PROPUNERE (nu era in tabelul de prize): aliniat la cabinet — tot camera de interventie cu aparate
  chirurgie:       { lx: 500, corp: "panou_led",    w: 40, pas: 8,    prize: 6, prizePas: null },
  cazare_animale:  { lx: 150, corp: "aplica_tavan", w: 25, pas: 12,   prize: 2, prizePas: null },
  asteptare:       { lx: 200, corp: "aplica_tavan", w: 25, pas: 12,   prize: 2, prizePas: null },

  // — E. SPORT / RECREERE —
  sala_aparate:    { lx: 300, corp: "panou_led",    w: 40, pas: 10,   prize: 4, prizePas: 15 },
  sala_clase:      { lx: 300, corp: "panou_led",    w: 40, pas: 10,   prize: 4, prizePas: 12 },
  // zona cu dus = acelasi regim ca baia (I7-2011): IP44 + RCCB 10mA
  dusuri:          { lx: 200, corp: "aplica_tavan", w: 25, pas: 8,    prize: 2, prizePas: null,
                     prizaTip: "ip44", umed: "10ma" },
  sala_principala: { lx: 300, corp: "panou_led",    w: 40, pas: 10,   prize: 4, prizePas: 15 },
  zona_joaca:      { lx: 300, corp: "panou_led",    w: 40, pas: 10,   prize: 4, prizePas: 15 },

  // — F. BIROURI / ALTELE —
  sala_sedinte:    { lx: 500, corp: "panou_led",    w: 40, pas: 8,    prize: 6, prizePas: 12 },
  camera_server:   { lx: 300, corp: "aplica_tavan", w: 25, pas: 8,    prize: 6, prizePas: 12 },
  arhiva:          { lx: 200, corp: "aplica_tavan", w: 25, pas: 12,   prize: 2, prizePas: null },
  atelier:         { lx: 500, corp: "panou_led",    w: 40, pas: 8,    prize: 6, prizePas: 10 },
  sala_grupa:      { lx: 300, corp: "panou_led",    w: 40, pas: 10,   prize: 4, prizePas: 15 },
  sala_mese:       { lx: 300, corp: "panou_led",    w: 40, pas: 10,   prize: 4, prizePas: 15 },
  dormitor_copii:  { lx: 100, corp: "aplica_tavan", w: 25, pas: 12,   prize: 4, prizePas: 15 },
};

// ── RECUNOASTEREA: nume de pe plansa -> cheie de camera canonica ─────────────────────────────
const deDiacritice = (s: string) => s.normalize("NFKD").replace(/[̀-ͯ]/g, "");

// Numele pur generice — DOAR ele se rezolva prin sub-tip. Cer cuvantul singur (eventual cu numar
// sau punct), nu ca prefix: „Sala sedinte" NU e generic, e sala de sedinte.
const RX_GENERIC_SALA   = /^(sala|sal\.?|s\.)\s*\d*$/;
const RX_GENERIC_SPATIU = /^(spatiu|spat\.?|sp\.)\s*\d*$/;

/** Cheia camerei canonice pentru un nume de pe plansa, in contextul unui sub-tip.
 *  ORDINEA: (1) camerele SPECIFICE ale sub-tipului, (2) numele generic -> camera principala,
 *  (3) camerele comune (grup sanitar etc. sunt in lista sub-tipului oricum). null = necunoscut. */
export function cameraCanonica(nume: string | null | undefined, subtip: string | null | undefined): string | null {
  const n = deDiacritice((nume ?? "").toLowerCase().trim());
  if (!n) return null;
  const st = subtipById(subtip) || subtipById(SUBTIP_DEFAULT);
  if (!st) return null;
  // 1. SPECIFIC: camerele sub-tipului, in ordinea declarata (specificele sunt primele in liste)
  for (const key of st.camere) {
    const def = CAMERE_COMERCIALE[key];
    if (def && def.rx.test(n)) return key;
  }
  // 2. GENERIC: „Sala" / „Spatiu" singure -> camera principala a sub-tipului
  if (RX_GENERIC_SALA.test(n) && st.generic.sala) return st.generic.sala;
  if (RX_GENERIC_SPATIU.test(n) && st.generic.spatiu) return st.generic.spatiu;
  return null;
}
