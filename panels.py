# -*- coding: utf-8 -*-
"""REGISTRUL DE TABLOURI si graful lor — sursa unica pentru backend.

Pana aici apartenenta unui circuit la iesire era o LISTA ALBA, scrisa ca o inlantuire de filtre:

    out = teg + redirected_teg + feed_circuits + tes + merged_tect
    #     panel == "TEG"                  panel.startswith("TES")   panel == "TE-CT"

Nu era o lista de nume, ci o FORMA — `startswith("TES")` nu prinde nici macar „TE-SP1". Orice
circuit al carui tablou nu nimerea una din cele trei forme nu aparea in `out` si DISPAREA TACIT:
schema si memoriul se generau normal, doar ca fara el. Masurat la comercial: un tablou numit „TE"
dadea ZERO circuite. Din cele 16 nume de tablou ale unui bloc, DOUASPREZECE cadeau asa.

DOUA SCHIMBARI DE PRINCIPIU:

1. PARTITIE TOTALA, nu filtre. `_bucket` intoarce o galeata pentru ORICE nume, inclusiv unul
   necunoscut. Un circuit nu mai poate cadea in afara tuturor ramurilor, fiindca nu mai exista
   „in afara": ultima galeata prinde tot ce n-a fost revendicat.

2. IMPLICITUL E IZOLAREA, NU PIERDEREA. Un tablou nerecunoscut isi PASTREAZA circuitele si primeste
   o secventa de numerotare proprie; nu e adoptat de TEG si nu e aruncat. Acelasi principiu ca la
   `_PLAN_SPEC` (draw_elements): o planşa neinregistrata iese GOALA si VIZIBIL, nu gresita si tacut.
   Un tablou nerecunoscut iese IZOLAT in graf — se vede ca n-are parinte — nu dispare.

COLIZIUNEA DE NUME, rezolvata explicit: `tablou_tcc` EXISTA DEJA si inseamna T.CC, tabloul de curent
CONTINUU al fotovoltaicului (8 proiecte in baza il folosesc). Blocul cheama TCC „Tablou Consumatori
Comuni" — acelasi acronim, alt aparat. Tipul de element al blocului e deci `tablou_consumatori_comuni`,
scris pe litere: identificatorul intern e neambiguu, iar `tablou_tcc` ramane exact ce era, fara
migrare de randuri existente. Ramane o apropiere de AFISAJ („T.CC" vs „TCC", un punct diferenta):
DECIZIA LUI DAN (20 sept 2026) e ca etichetele raman asa, fiindca separarea o face FORMA — firidele
au contur dublu, iar conturul se vede si pe tiparul alb-negru, care e cum se citesc planurile pe
santier. `_ETICHETE_APROPIATE` pastreaza perechile ca sa nu se redeschida discutia din amintire.
"""

# ── FAMILII DE TABLOU ─────────────────────────────────────────────────────────────────────────
# (familie, element_type, eticheta scurta, ku, e_firida)
#   ku  = coeficientul de simultaneitate al tabloului (I7-2011 cap. 3.2.2.3, tab. 3.5).
#         Valorile de bloc sunt MASURATE pe schemele lui Dan, nu alese: TE-AP 11,31/18,85 = 0,600;
#         TCC 31,90/39,88 = 0,800; TECV 20,80/20,80 = 1,000; TGD 330,40/550,67 = 0,600;
#         TE-SP 0,900 (scris in clar in Nota 1 de pe IE.27 si IE.28).
#   e_firida = dulap/firida de distributie (contur DUBLU pe plan) vs tablou propriu-zis (simbolul
#         clasic, doua triunghiuri). Distinctia e de desen, nu de calcul.
_FAMILII = (
    # numele EXISTENTE — neatinse, aceleasi valori ca pana acum
    ("TE-CT", "tablou_te_ct",  "TE-CT",  0.80, False),
    ("TEGD",  "tablou_tgd",    "TEGD",   0.60, True),    # INAINTEA lui TEG: „TEGD" incepe cu „TEG"
    ("TEG",   "tablou_teg",    "TEG",    0.70, False),
    ("TES",   "tablou_tes",    "TES",    0.70, False),
    # BLOC (P1) — cele zece
    ("BMPT",  "tablou_bmpt",   "BMPT",   1.00, True),
    # Decizia lui Dan (20 sept): eticheta TIPARITA e „TEGD", cum scrie legenda de pe planşele lui.
    # Familia „TGD" ramane ca INTRARE acceptata — schema lui de distributie o scrie asa — dar
    # afiseaza tot „TEGD". Intrarea si iesirea sunt lucruri diferite; doar iesirea e o decizie.
    ("TGD",   "tablou_tgd",    "TEGD",   0.60, True),
    ("FDCP",  "tablou_fdcp",   "FDCP",   0.60, True),
    ("FDCS",  "tablou_fdcs",   "FDCS",   0.80, True),
    ("TE-AP", "tablou_te_ap",  "TE-AP",  0.60, False),
    # 0,90 e MASURAT, nu implicit: IE.27 si IE.28 scriu amandoua, in Nota 1, „Conform NORMATIV
    # I7/2011 Cap.3.2.2.3 Tabel 3.5. Factorul de utilizare pentru acest tip de tablou este egal cu
    # ku= 0.90". Pana la P6b figura aici 0,80 — o valoare pusa la P1 fiindca nu ma uitasem inca pe
    # planşele spatiilor, deci o presupunere, nu o citire.
    ("TE-SP", "tablou_te_sp",  "TE-SP",  0.90, False),
    ("TE-LIFT", "tablou_te_lift", "TE-LIFT", 1.00, False),
    ("TECV",  "tablou_tecv",   "TECV",   1.00, False),
    ("TEP",   "tablou_tep",    "TEP",    1.00, False),
    ("TCC",   "tablou_consumatori_comuni", "TCC", 0.80, False),
)

# Ordinea de potrivire: prefixul CEL MAI LUNG intai. Fara asta „TEGD" ar fi citit ca „TEG" + „D",
# iar „TE-LIFT" ca „TE-" + rest. Regula, nu ordinea din tuplu, e autoritatea.
_MATCH = tuple(sorted(_FAMILII, key=lambda f: -len(f[0])))

KU_IMPLICIT = 0.70          # tablou nerecunoscut: ku-ul implicit de azi (SchemaRequest.ku = 0.70)

ELEMENT_TYPES = tuple(dict.fromkeys(f[1] for f in _FAMILII))   # fara duplicate, ordine stabila

# Tipurile NOI aduse de P1 (cele care cer migratie pe chk_element_type).
ELEMENT_TYPES_BLOC = ("tablou_tgd", "tablou_bmpt", "tablou_fdcp", "tablou_fdcs", "tablou_te_ap",
                      "tablou_te_sp", "tablou_te_lift", "tablou_tecv", "tablou_tep",
                      "tablou_consumatori_comuni")

# Perechi de etichete care se TIPARESC aproape identic. Nu-s bug-uri de cod — sunt capcane de
# CITIRE pe planşa, si se rezolva prin decizie, nu prin cod. Lista exista ca sa nu se piarda.
_ETICHETE_APROPIATE = (
    ("T.CC", "TCC"),        # tabloul de curent continuu al FV vs consumatorii comuni ai blocului
    ("TE-CT", "TECV"),      # camera tehnica vs consumatorii vitali
)   # Dan, 20 sept: raman asa — le separa conturul dublu al firidelor, nu eticheta.


def _norm(name):
    """Normalizare pentru POTRIVIRE. Punctul se PASTREAZA: „TE-AP 1.1" si „TE-AP 11" sunt doua
    tablouri diferite, iar scoaterea punctului le-ar face sa dea acelasi sufix de circuit."""
    return str(name or "").strip().upper().replace("_", "-")


def panel_family(name):
    """Numele unui tablou -> familia lui („TE-AP 1.1" -> „TE-AP", „TES2" -> „TES").
    None daca nu seamana cu nimic cunoscut — si atunci e IZOLAT, nu adoptat de altcineva."""
    n = _norm(name)
    if not n:
        return None
    for fam, _et, _lbl, _ku, _fir in _MATCH:
        f = _norm(fam)
        if n == f or n.startswith(f):
            return fam
    return None


def _fam_row(name):
    fam = panel_family(name)
    if fam is None:
        return None
    for row in _FAMILII:
        if row[0] == fam:
            return row
    return None




def panel_ku(name):
    """Coeficientul de simultaneitate. Nerecunoscut -> implicitul de azi (0.70), nu zero: un ku
    lipsa care ar iesi 0 ar face Pa=0 si ar ascunde tabloul in loc sa-l arate neconfigurat."""
    row = _fam_row(name)
    return row[3] if row else KU_IMPLICIT




_FIRIDE_ET = frozenset(f[1] for f in _FAMILII if f[4])


def element_is_firida(element_type):
    """Tipul de ELEMENT e o firida/dulap de distributie? (desenul le da contur dublu). Intrebarea se
    pune pe tip, nu pe eticheta: eticheta e pentru citit, tipul e pentru decis."""
    return str(element_type or "") in _FIRIDE_ET




# ── GALETILE DE IESIRE ────────────────────────────────────────────────────────────────────────
# Cele trei familii MOSTENITE isi pastreaza galeata (si deci locul in `out` si secventa de
# numerotare). Orice altceva merge in „alt" — inclusiv un nume necunoscut. Functia e TOTALA:
# nu exista intrare pentru care sa nu intoarca nimic, si de-aia nu se mai poate pierde un circuit.
BUCKET_TEG, BUCKET_TES, BUCKET_TECT, BUCKET_ALT = "teg", "tes", "tect", "alt"


def panel_bucket(name):
    n = _norm(name)
    if n == "TEG":
        return BUCKET_TEG
    if n.startswith("TES") and not n.startswith("TE-S"):    # „TES1"/„TES2"/„TESS1" — nu „TE-SP1"
        return BUCKET_TES
    if n == "TE-CT":
        return BUCKET_TECT
    return BUCKET_ALT


def circuit_suffix(name):
    """Sufixul id-ului de circuit al tabloului („C3-TES").

    Familiile mostenite pastreaza MAPAREA MULTI-LA-UNU: TES1 si TES2 dau amandoua „-TES", deci
    impart o singura secventa — exact numerotarea de azi, pe care o vede si `plan_elements.circuit_id`.
    Un tablou NOU primeste un sufix propriu, deci o secventa proprie: blocul are 25 de TE-AP-uri,
    fiecare cu C1..C15 al lui."""
    b = panel_bucket(name)
    if b == BUCKET_TEG:
        return ""
    if b == BUCKET_TES:
        return "-TES"
    if b == BUCKET_TECT:
        return "-TECT"
    n = _norm(name)
    if not n:
        return "-?"                      # circuit fara tablou: id-ul iese „C1-?", vizibil ca nesetat
    if n.startswith("TE-"):
        n = n[3:]
    return "-" + n.replace(" ", "-")


# ── GRAFUL ────────────────────────────────────────────────────────────────────────────────────
_U_TRI = 636.4      # sqrt3 x 400 x 0.92 — ACEEASI constanta ca `enrich_circuits.breaker_and_ia`
_U_MONO = 230.0


def _phase_current(pa_w, phases):
    """Ia din Pa, cu conventia de tensiune a restului codului (nu una inventata aici).

    Verificata pe schemele lui Dan: AP-1 mono 11310/230 = 49,17 A — exact Ia tiparit pe planşa;
    TECV trifazat 20800/636,4 = 32,68 A fata de 32,67 tiparit."""
    if pa_w <= 0:
        return 0.0
    return pa_w / (_U_TRI if phases >= 3 else _U_MONO)


def panel_graph(circuits):
    """Graful tablourilor DEDUS din circuite. Nu inventeaza o structura noua: muchia EXISTA deja —
    un circuit `type='sub_tablou'` care sta pe `panel` si alimenteaza `feeds_panel` E muchia
    parinte -> copil. P1 doar o citeste ca atare, in loc s-o trateze drept caz special.

    Intoarce {nume: {parent, children, ku, pi_w, pa_w, ia_a, phases, circuits, izolat}}.

    Pi URCA BRUT pe graf (suma puterilor instalate, ale circuitelor proprii SI ale copiilor), iar
    ku se aplica la FIECARE nod pe Pi-ul lui. Verificat pe cifrele lui Dan: TE-AP 11,31/18,85 =
    0,600, TCC 31,90/39,88 = 0,800, TECV 20,80/20,80 = 1,000, TGD 330,40/550,67 = 0,600.

    `izolat` = tablou fara parinte care nu-i radacina evidenta: nu-i o eroare, e SEMNALUL ca cineva
    n-a fost legat — vizibil, in loc sa dispara."""
    noduri, parinte = {}, {}
    for c in (circuits or []):
        if not isinstance(c, dict):
            continue
        p = str(c.get("panel") or "").strip()
        if p:
            noduri.setdefault(p, [])
        fp = str(c.get("feeds_panel") or "").strip()
        if fp and str(c.get("type") or "") == "sub_tablou":
            noduri.setdefault(fp, [])
            parinte[fp] = p or None                  # muchia: `panel` alimenteaza `feeds_panel`
        elif p:
            noduri[p].append(c)                      # circuit PROPRIU (nu coloana catre altcineva)

    g = {}
    for nume, cc in noduri.items():
        pi = sum(float((x or {}).get("power_w") or 0) for x in cc)
        ph = max([int((x or {}).get("phases") or 1) for x in cc] or [1])
        g[nume] = {"parent": parinte.get(nume), "children": [], "ku": panel_ku(nume),
                   "pi_w": pi, "pa_w": 0.0, "ia_a": 0.0, "phases": ph,
                   "circuits": [str((x or {}).get("id") or "") for x in cc],
                   "family": panel_family(nume), "izolat": False}
    for nume, nod in g.items():
        par = nod["parent"]
        if par and par in g:
            g[par]["children"].append(nume)
    for nume, nod in g.items():
        # IZOLAT = nici parinte, nici copii, intr-un graf cu mai multe tablouri. Nu-i eroare si nu
        # opreste nimic: e SEMNALUL ca cineva n-a fost legat. Radacina (TEG/TGD) n-are parinte, dar
        # are copii, deci nu intra aici. Calculat DUPA ce s-au construit copiii — altfel ar depinde
        # de ordinea dictionarului.
        nod["izolat"] = bool(len(g) > 1 and nod["parent"] is None and not nod["children"])

    # Pi urca de la frunze spre radacina; ordinea = adancimea, calculata iterativ (fara recursie,
    # si cu o limita: un ciclu introdus de date gresite nu trebuie sa blocheze generarea).
    for _ in range(len(g) + 1):
        schimbat = False
        for nume, nod in g.items():
            tot = sum(float((x or {}).get("power_w") or 0)
                      for x in noduri[nume]) + sum(g[ch]["pi_w"] for ch in nod["children"])
            if abs(tot - nod["pi_w"]) > 1e-9:
                nod["pi_w"] = tot
                schimbat = True
        if not schimbat:
            break
    for nod in g.values():
        nod["pa_w"] = nod["pi_w"] * nod["ku"]
        nod["ia_a"] = _phase_current(nod["pa_w"], nod["phases"])
    return g
