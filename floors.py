# -*- coding: utf-8 -*-
"""Axa de NIVELURI — deschisa (N niveluri), sursa unica pentru backend.

Pana aici axa era un enum INCHIS de trei — parter / etaj / mansarda — replicat in TREI locuri
(`enrich_circuits._floor_panel`, `draw_elements._floor_idx`, `plansa_numbering._FLOOR_INT_LABEL`),
plus oglinda din `lib/floors.ts`. Pe un bloc S+P+2E+E3 retras cele CINCI niveluri reale cadeau pe
DOUA: `"etaj" in f` prindea etajele 1, 2 si 3 deopotriva, iar subsolul cadea pe ramura implicita,
adica parter.

Nu se PIERDEA nimic — se AMESTECA, si asta e mai rau. `compute_circuits` face bin-packing peste tot
ce primeste, fara nicio notiune de etaj (masurat deja: 6 becuri parter + 1 mansarda -> un singur C1),
deci becurile a trei etaje ar fi iesit pe ACELASI circuit. Rezultatul n-ar fi fost gol, ci gresit si
perfect plauzibil — genul de defect care trece de o verificare vizuala.

DOUA NOTIUNI, DELIBERAT SEPARATE:

    eticheta canonica  -> IDENTITATEA nivelului. Unica prin constructie. Cheia de grupare.
    indexul (int cu semn) -> ORDINEA pe verticala, numele tabloului, campul persistat `floor`.

Identitatea NU mai trece prin index tocmai fiindca indexul are coliziuni legitime: mansarda unei
case P+M sta la 2 (ca proiectele livrate sa ramana byte-identice), iar un „etaj 2" sta tot la 2.
Cat timp identitatea e eticheta, coliziunea de index afecteaza doar ordinea a doua niveluri care
oricum nu coexista — nu mai poate contopi doua niveluri intr-unul.

NON-REGRESIE (criteriul pachetului): parter -> ("TEG", 0), etaj -> ("TES1", 1),
mansarda -> ("TES2", 2). Neschimbate, si testate ca atare.

NUMELE DE TABLOU de aici sunt provizorii pentru nivelurile NOI (subsol -> "TESS1"): P0 doar deschide
axa. Graful real de tablouri — TEGD / FDCP / TE-AP / TCC / TECV — e P1. Pana atunci orice nivel non-
parter primeste un nume care incepe cu „TES", ca sa treaca prin filtrul din `enrich_circuits`
(`panel.startswith("TES")`) exact ca etajele de azi; P0 nu atinge acel filtru.
"""
import re

# ── etichete canonice ─────────────────────────────────────────────────────────────────────────
PARTER = "parter"
MANSARDA = "mansarda"
DEMISOL = "demisol"

_DIACR = {"ă": "a", "â": "a", "î": "i", "ș": "s", "ş": "s", "ț": "t", "ţ": "t",
          "Ă": "a", "Â": "a", "Î": "i", "Ș": "s", "Ş": "s", "Ț": "t", "Ţ": "t"}

# indexul MOSTENIT al mansardei. Nu-i o alegere estetica: `_enrich_group` persista indexul in
# `circuits[].floor`, iar `derive_extra_floors` il citeste inapoi ca „mansarda". Schimbarea lui ar
# rescrie tacit borderoul proiectelor P+M deja livrate.
MANSARDA_LEGACY_IDX = 2

_RX_ETAJ = re.compile(r"^etaj\s*(\d*)$")
_RX_E = re.compile(r"^e\s*(\d+)$")                 # „E3" / „E3 retras" (notatia din planurile de bloc)
_RX_SUBSOL = re.compile(r"^subsol\s*(\d*)$")
_RX_INT = re.compile(r"^-?\d+$")


def _norm(s):
    """Normalizeaza orice forma de scriere la un sir comparabil: fara diacritice, fara prefixul
    „plan_", fara separatori, fara sufixul „retras" (un etaj retras e tot etajul lui)."""
    t = str(s).strip().lower()
    t = "".join(_DIACR.get(c, c) for c in t)
    t = t.replace("_", " ").replace("-", " ")
    t = " ".join(t.split())
    if t.startswith("plan "):
        t = t[5:].strip()
    if t.endswith(" retras"):
        t = t[:-7].strip()
    return t


def _parse(value):
    """Parsarea propriu-zisa: eticheta canonica, sau None daca sirul NU numeste un nivel.

    Distinctia conteaza: `floor_canonic` intoarce „parter" si pentru un parter real, si pentru gunoi
    — iar pe o cladire cu subsol parterul nu mai e nivelul de la pozitia 0, deci „nerecunoscut" nu
    mai poate fi tratat ca „parter" fara sa strice lista nivelurilor."""
    if value is None or value == "" or isinstance(value, bool):   # bool e subclasa de int
        return None
    if isinstance(value, (int, float)):
        return _from_int(int(value))
    t = _norm(value)
    if not t:
        return None
    if _RX_INT.match(t):
        return _from_int(int(t))
    if t.startswith("mansard"):
        return MANSARDA
    if t.startswith("demisol"):
        return DEMISOL
    if t.startswith("parter"):
        return PARTER
    m = _RX_SUBSOL.match(t)
    if m:
        n = int(m.group(1) or 1)
        return "subsol" if n <= 1 else "subsol %d" % n
    m = _RX_ETAJ.match(t) or _RX_E.match(t)
    if m:
        n = int(m.group(1) or 1)
        return "etaj" if n <= 1 else "etaj %d" % n
    return None


def floor_canonic(value):
    """ORICE codificare de nivel -> eticheta canonica. Necunoscut/lipsa -> „parter" (zero regresie
    pe proiectele single-floor, unde `floor` e NULL). Oglinda exacta a `floorCanonic` din floors.ts.

    Intregii pastreaza conventia MOSTENITA (0=parter, 1=etaj, 2=mansarda) — asa sunt persistati in
    `circuits[].floor` de la inceput. Peste 2 sunt etaje (3 -> „etaj 3"), sub 0 sunt subsoluri.
    Ambiguitatea lui 2 („mansarda" sau „etaj 2"?) e motivul pentru care circuitele poarta de acum si
    `floor_label`: eticheta e autoritatea, intregul e doar ordinea."""
    c = _parse(value)
    return PARTER if c is None else c




def _from_int(i):
    if i == 0:
        return PARTER
    if i == 1:
        return "etaj"
    if i == MANSARDA_LEGACY_IDX:
        return MANSARDA                            # MOSTENIT: 2 a insemnat mereu mansarda
    if i > 0:
        return "etaj %d" % i
    return "subsol" if i == -1 else "subsol %d" % (-i)


def floor_index(value, floors=None):
    """Pozitia pe verticala. parter = 0; etajele = numarul lor; subsolurile = negativ (adancimea);
    demisolul = -1. Serveste la ORDONARE, la numele tabloului si la campul persistat `floor`.

    `floors` (nivelurile PREZENTE in proiect) conteaza doar pentru MANSARDA: singura ca nu-si poarta
    numarul in nume. Fara context ramane la 2 (mostenit, si corect pentru P+M si P+E+M — exact
    formele existente); cu doua sau mai multe etaje urca deasupra lor, ca sa nu se ciocneasca de
    „etaj 2". Cazul nu poate aparea pe proiectele de azi: etajul 2 nici nu exista ca nivel distinct
    inainte de pachetul asta."""
    c = floor_canonic(value)
    if c == PARTER:
        return 0
    if c == DEMISOL:
        return -1
    if c == MANSARDA:
        top = 0
        for f in (floors or []):
            fc = floor_canonic(f)
            if fc == "etaj" or fc.startswith("etaj "):
                top = max(top, _num_suffix(fc, 1))
        return max(MANSARDA_LEGACY_IDX, top + 1)
    if c.startswith("subsol"):
        return -_num_suffix(c, 1)
    return _num_suffix(c, 1)                       # etaj / etaj N


def _num_suffix(canonic, default):
    parts = canonic.split()
    return int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else default


def floor_panel(value, floors=None):
    """(nume tablou, index) — regula de AZI, extinsa la axa deschisa.

      index 0   -> „TEG"           (parterul are mereu tabloul general)
      index > 0 -> „TES<index>"    (etaj -> TES1, mansarda -> TES2 — neschimbate)
      index < 0 -> „TESS<adancime>" (subsol -> TESS1)

    Prefixul „TES" e deliberat pastrat pe TOATE: filtrul din `enrich_circuits` selecteaza
    `panel.startswith("TES")`, iar P0 nu are voie sa-l atinga (e P1). Numele reale de tablou de bloc
    vin cu graful, nu de aici."""
    i = floor_index(value, floors)
    if i == 0:
        return "TEG", 0
    if i > 0:
        return "TES%d" % i, i
    return "TESS%d" % (-i), i


def sort_floors(values):
    """Nivelurile CANONICE ordonate de jos in sus (subsol -> demisol -> parter -> etaje -> mansarda),
    fara duplicate. Ordinea e a INDEXULUI, nu alfabetica: „etaj 10" vine dupa „etaj 9", iar subsolul
    INAINTEA parterului — exact defectul din numerotarea planselor, unde parterul era pus mereu
    primul si subsolul aterizase dupa el."""
    labels = [floor_canonic(v) for v in (values or [])]
    seen, out = set(), []
    for c in labels:
        if c in seen:
            continue
        seen.add(c)
        # departajare la index egal: subsolul e sub demisol (amandoua stau la -1, fiindca in
        # practica o cladire are ori una, ori alta). Fara ea ordinea ar depinde de ordinea intrarii.
        out.append((floor_index(c, labels), 0 if c.startswith("subsol") else 1, c))
    return [c for _, _, c in sorted(out, key=lambda t: (t[0], t[1]))]
