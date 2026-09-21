# -*- coding: utf-8 -*-
"""SARCINILE UTILE ale schemelor monofilare, construite in AUTORITATE (P9).

Pana aici n8n decidea singur ce scheme se genereaza, printr-o lista alba scrisa ca regex:

    const tesPanels = panels.filter(p => /^TES\\d+$/.test(p.name || ''));

E exact forma reparata la P1 in `enrich_circuits`, mutata cu un etaj mai sus: un tablou al carui
nume nu nimereste tiparul nu dispare cu eroare, pur si simplu nu primeste schema. Din cele 16 nume
ale unui bloc trecea UNUL. Si, in sens invers, un TES ramas in `panels` de la generare primea schema
chiar cand numerotarea spunea ca nu exista — cu un numar de rezerva care cadea peste al unui PLAN.

CE SCHIMBA MODULUL ASTA: lista ANUNTATA de `compute_plansa_numbering` devine sursa. Se genereaza
exact planşele anuntate, in ordinea lor, cu numarul lor. Doua consecinte, amandoua dorite:
  o schema NEANUNTATA nu se mai poate naste (defectul de la P8 dispare structural);
  o schema ANUNTATA fara continut iese in `lipsa`, deci se VEDE — nu se pierde tacut.

Sarcinile se construiesc AICI, nu in nod: datele de tablou (Pi, Pa, Ia, ku, faze, parinte) vin din
`panels.panel_graph`, care le calculeaza deja pentru memoriu si BOM. Construite in JS ar fi fost a
doua sursa pentru aceleasi numere.
"""
import apartments as _apm
import floors as _fl
import panels as _pn
import protectii as _prot

# tip de planşa -> familia de tablou careia ii corespunde. Tipurile care NU descriu un tablou
# (planuri, detalii, scheme de sistem) nu apar aici si nu produc sarcini.
_TIP_FAMILIE = {
    "schema_teg": "TEG",
    "schema_tes": "TES",
    "schema_tect": "TE-CT",
    "schema_ap": "TE-AP",
    "schema_sp": "TE-SP",
    "schema_tcc": "TCC",
    "schema_tecv": "TECV",
    "schema_camera_pompe": "TEP",
    "schema_fdcp": "FDCP",
    "schema_bmpt_fdcp": "BMPT",
}

_DESCRIERI = {
    "TEG": "TABLOU ELECTRIC GENERAL",
    "TES": "TABLOU ELECTRIC SECUNDAR",
    "TE-CT": "TABLOU ELECTRIC CENTRALA TERMICA",
    "TE-AP": "TABLOU ELECTRIC APARTAMENT",
    "TE-SP": "TABLOU ELECTRIC SPATIU COMERCIAL",
    "TCC": "TABLOU CONSUMATORI COMUNI",
    "TECV": "TABLOU CONSUMATORI VITALI",
    "TEP": "TABLOU ELECTRIC CAMERA POMPE",
    "FDCP": "FIRIDA DE DISTRIBUTIE CURENTI TARI",
    "BMPT": "BLOC DE MASURA SI PROTECTIE",
}


# ── GRUPAREA FIRIDELOR DE PALIER ──────────────────────────────────────────────────────────────
# DECIZIA LUI DAN: doua firide IDENTICE impart o singura planşa de schema. La el, FDCP E1 si FDCP E2
# sunt doua firide FIZICE (200 A fiecare, amandoua pe IE.20), dar o singura schema — IE.22,
# „FDCP ETAJ 1-2". PE PLAN raman amandoua, cu etichetele lor: sunt doua cutii in doua case de scara,
# iar a desena una singura ar fi o minciuna despre cladire. Se comaseaza DOCUMENTUL, nu obiectul.
#
# CRITERIUL DE IDENTITATE, in ordinea in care elimina:
#   1. acelasi set de copii, pe TIPURI — nu pe etichete. P1_1..P1_9 de pe etajul 1 si P2_1..P2_9 de
#      pe etajul 2 au etichete diferite si acelasi TIP (AP-1), deci firidele lor sunt identice.
#      Tiparea vine de la P9 si nu se rescrie aici: `tip_al_apartamentului`.
#   2. aceleasi spatii comerciale — acolo nu exista tipare, fiecare spatiu isi are schema lui, deci
#      doua firide care hranesc SP1 si respectiv SP2 NU sunt identice.
#   3. aceeasi protectie a firidei si acelasi cablu de coloana (din circuitul care o alimenteaza).
#
# O SINGURA SURSA: functia asta e chemata si de endpointul care construieste lista de porti (deci de
# numerotare), si de constructorul de sarcini. Daca numerotarea ar grupa si generatorul nu — sau
# invers — ar reveni exact dezechilibrul „anuntate != livrate" inchis la P9.


def _descriptor_copil(nume_copil, tipuri_ap, membri_ap):
    """Cum se vede un tablou-copil in semnatura firidei: prin TIPUL lui, nu prin eticheta."""
    fam = _pn.panel_family(nume_copil) or "?"
    if fam == "TE-AP":
        et = _apm.eticheta_din_panel(nume_copil)
        tip = membri_ap.get(et)
        # FARA TIP, NU SE COMASEAZA. `/api/finalize` isi inveleste apelul la /tipuri-apartament
        # intr-un try/catch, deci lista de tipuri POATE sa iasa goala. Daca in cazul ala toate
        # apartamentele ar primi acelasi descriptor („necunoscut"), doua firide cu acelasi NUMAR de
        # apartamente ar parea identice si ar primi o singura schema — un rezultat gresit si
        # plauzibil, adica exact felul de greseala care nu se prinde la citit. Cazand pe eticheta,
        # firidele raman distincte: mai multe planşe decat trebuie e o pierdere; o schema care
        # descrie un tablou ce nu exista asa e o minciuna in dosar.
        return "AP:%s" % tip if tip else "AP!%s" % (et or nume_copil)
    if fam == "TE-SP":
        # Spatiile comerciale n-au tipare: fiecare isi are schema lui, deci intra cu identitatea lui.
        return "SP:%s" % (_apm.eticheta_din_panel(nume_copil) or nume_copil)
    return fam


def _sufix_fdcp(nume):
    """„FDCP ETAJ 1" -> „ETAJ 1". Numele poarta nivelul (vezi `_fdcp_pe_nivel`)."""
    n = str(nume or "").strip()
    return n[4:].strip() if n.upper().startswith("FDCP") else n


def _eticheta_grup(sufixe):
    """Eticheta unei planşe comasate, in conventia lui Dan: „FDCP ETAJ 1-2".

    Cand nivelurile sunt NEADIACENTE (E1 si E3, cu E2 diferit) nu se poate scrie un interval fara
    sa minta — atunci se enumera: „FDCP ETAJ 1, 3". Un interval „1-3" ar include E2, care are ALTA
    schema, si cititorul ar cauta pe planşa asta ceva ce nu-i acolo."""
    if len(sufixe) == 1:
        return "FDCP %s" % sufixe[0]
    parti = [s.rsplit(" ", 1) for s in sufixe]
    capete = {p[0] for p in parti if len(p) == 2}
    numere = [p[1] for p in parti if len(p) == 2 and p[1].isdigit()]
    if len(capete) == 1 and len(numere) == len(sufixe):
        n = sorted(int(x) for x in numere)
        cap = capete.pop()
        if n == list(range(n[0], n[-1] + 1)):          # adiacente -> interval
            return "FDCP %s %d-%d" % (cap, n[0], n[-1])
        return "FDCP %s %s" % (cap, ", ".join(str(x) for x in n))
    return "FDCP %s" % " · ".join(sufixe)


def grupuri_fdcp(circuits, tipuri_ap=None):
    """[{eticheta, membri, domeniu}] — firidele de palier, comasate cand sunt identice.

    `membri` = numele tablourilor FDCP reale, in ordinea nivelurilor. Primul e REPREZENTANTUL:
    schema se deseneaza din circuitele lui."""
    circuits = [c for c in (circuits or []) if isinstance(c, dict)]
    membri_ap = {}
    for t in (tipuri_ap or []):
        for m in (t.get("membri") or []):
            if isinstance(m, (list, tuple)) and len(m) == 2:
                membri_ap[m[1]] = t.get("nume")

    firide, feed = {}, {}
    for c in circuits:
        p = str(c.get("panel") or "").strip()
        if _pn.panel_family(p) == "FDCP":
            firide.setdefault(p, [])
            fp = str(c.get("feeds_panel") or "").strip()
            if fp:
                firide[p].append(fp)
        fp2 = str(c.get("feeds_panel") or "").strip()
        if _pn.panel_family(fp2) == "FDCP":
            feed[fp2] = c

    def semnatura(nume):
        copii = sorted(_descriptor_copil(x, tipuri_ap, membri_ap) for x in firide.get(nume, []))
        f = feed.get(nume) or {}
        return (tuple(copii), str(f.get("breaker_type") or ""), int(f.get("breaker_a") or 0),
                str(f.get("cable_type") or ""))

    grupe = {}
    for nume in firide:
        grupe.setdefault(semnatura(nume), []).append(nume)

    def cheie_nivel(n):
        return _fl.floor_index(_sufix_fdcp(n).lower())

    out = []
    for g in sorted(grupe.values(), key=lambda g: min(cheie_nivel(x) for x in g)):
        membri = sorted(g, key=cheie_nivel)
        sufixe = [_sufix_fdcp(x) for x in membri]
        out.append({"eticheta": _eticheta_grup(sufixe), "membri": membri,
                    "domeniu": " · ".join(sufixe)})
    return out


def _cheie_tes(nume):
    """„TES2" < „TES10": sortare pe NUMAR, nu pe sir. Alfabetic, al zecelea etaj ar veni al doilea."""
    n = "".join(ch for ch in str(nume or "") if ch.isdigit())
    return (int(n) if n else 0, str(nume or ""))


def _circ_payload(c):
    """Un circuit, in forma pe care o citeste `schema_generator.Circuit`."""
    tri = "3P" in str(c.get("breaker_type") or "")
    amp = int(c.get("breaker_a") or 0)
    tip = str(c.get("type") or "")
    return {
        "nr": str(c.get("id") or ""),
        "fasa": str(c.get("fasa") or "R"),
        "destinatie": str(c.get("description") or "")[:60],
        "pi_kw": round(float(c.get("power_w") or 0) / 1000.0, 3),
        "ia_a": float(c.get("ia_calculated_a") or 0),
        # Eticheta se construieste din `breaker_type`, care poarta deja curba decisa de `protectii`
        # (inclusiv exceptia motorului de desfumare). `normalizeaza` adauga kA-ul dupa pozitia in
        # ierarhie si lasa neatins ce are deja.
        "protectie": _prot.normalizeaza(
            "MCB %s %dA %s" % ("3P+N" if tri else "1P+N", amp,
                               str(c.get("breaker_type") or "").split("-")[-1].split()[0]
                               if c.get("breaker_type") else ""),
            tri=tri, tip=tip, este_tablou=(tip == "sub_tablou")),
        "cablu": str(c.get("cable_type") or ""),
        "tub": str(c.get("pozare") or ""),
        "tip_consumator": tip or "priza",
        "cantitate": int(c.get("outlets") or c.get("lighting_points") or 1) or 1,
        "rccb_ma": c.get("rccb_ma"),
        "has_rccb_individual": bool(c.get("has_rccb_individual")),
        "has_afdd": bool(c.get("has_afdd")),
        "kit_panica": int(c.get("kit_panica") or 0),
    }


# `project_info` si cartusul schemei numesc DOUA lucruri la fel cu nume diferite. Divergenta e
# veche si documentata in `app/api/generate/route.ts` (CARTUS_MAP), unde se face maparea inversa,
# modal -> project_info. Aici e nevoie de ea in sensul celalalt.
def _cartus_proiect(brut, plansa_nr):
    """`project_info` -> cartusul planşei. Un singur rand: normalizarea sta in `cartus_swap`,
    fiindca o cere ORICE producator de planşa, nu doar schemele de tablou (vezi motivul acolo)."""
    from cartus_swap import normalizeaza_cartus_proiect
    return normalizeaza_cartus_proiect(brut, plansa_nr)


def _sarcina(nume_tablou, plansa, circuits, graf, cartus_firma, cartus_proiect, descriere=None,
             nume_afisat=None):
    """`nume_tablou` = tabloul din care se CITESC circuitele; `nume_afisat` = ce SCRIE pe planşa.

    Cele doua difera exact intr-un caz: schema comasata a mai multor firide identice. Antetul
    tipareste „<nume> — <descriere>", deci cu reprezentantul ar fi iesit „FDCP ETAJ 1 — … ETAJ 1 ·
    ETAJ 2" — o planşa care se contrazice singura, in timp ce borderoul o anunta „FDCP ETAJ 1-2"."""
    # Circuitele tabloului = tot ce sta pe el, INCLUSIV coloanele care pleaca spre alte tablouri.
    # Prima varianta le excludea si firidele (FDCP, BMPT) ieseau cu ZERO circuite — la ele coloanele
    # SUNT continutul schemei, n-au consumatori proprii. Si pe un TEG coloana catre TES apare pe
    # schema de azi, deci excluderea ar fi schimbat si casele.
    cc = [c for c in circuits if str(c.get("panel") or "") == nume_tablou]
    nod = (graf or {}).get(nume_tablou) or {}
    # Coloana care ALIMENTEAZA tabloul: circuitul `sub_tablou` care-l hraneste. De-acolo vin si
    # sectiunea cablului de alimentare, si numele sursei — aceleasi date pe care le vede memoriul.
    feed = next((c for c in circuits
                 if str(c.get("feeds_panel") or "") == nume_tablou), {}) or {}
    tri = int(nod.get("phases") or 1) >= 3
    fam = _pn.panel_family(nume_tablou) or ""
    return {
        "_plansa_nr": plansa.get("nr"),
        "_plansa_tip": plansa.get("tip"),
        "_panel": nume_afisat or nume_tablou,
        "tablou_nume": nume_afisat or nume_tablou,
        "tablou_descriere": descriere or _DESCRIERI.get(fam, "TABLOU ELECTRIC"),
        "pi_total_kw": round(float(nod.get("pi_w") or 0) / 1000.0, 2),
        "pa_total_kw": round(float(nod.get("pa_w") or 0) / 1000.0, 2),
        "ia_total_a": round(float(nod.get("ia_a") or 0), 2),
        "ku": float(nod.get("ku") or _pn.KU_IMPLICIT),
        "racord": "Trifazat" if tri else "Monofazat",
        "main_breaker": {
            "cod": "C0",
            "tip": _prot.eticheta(int(feed.get("breaker_a") or 0) or (40 if tri else 25),
                                  tri=tri, este_tablou=True,
                                  din_general=str(nod.get("parent") or "").upper()
                                  .startswith(("BMPT", "TEGD", "TGD"))),
            "cablu_alim": str(feed.get("cable_type") or ""),
            "sursa": ("De la %s" % nod["parent"]) if nod.get("parent") else "",
        },
        "circuits": [_circ_payload(c) for c in cc],
        "cartus_firma": cartus_firma or {},
        "cartus_proiect": _cartus_proiect(cartus_proiect, plansa.get("nr")),
    }


def sarcini_scheme(planse, circuits, cartus_firma=None, cartus_proiect=None, tipuri_ap=None):
    """{sarcini, lipsa} pentru planşele ANUNTATE care sunt scheme de tablou.

    `planse` = iesirea lui `compute_plansa_numbering` (autoritatea). Ordinea si numerele ei se
    pastreaza intocmai — nodul n8n doar itereaza si trimite.

    `lipsa` = planşele anuntate carora nu li s-a gasit tabloul. E CAMPUL CARE CONTEAZA: pana aici o
    schema promisa si negenerata disparea fara urma, iar clientul primea un borderou cu o planşa in
    plus. Acum se numara."""
    circuits = [c for c in (circuits or []) if isinstance(c, dict)]
    graf = _pn.panel_graph(circuits)
    nume_panels = {str(c.get("panel") or "") for c in circuits} | set(graf)
    # ACEEASI functie pe care o cheama si endpointul care construieste lista de porti. Nu se
    # recalculeaza altfel aici: gruparea e o singura sursa, altfel „anuntate != livrate".
    grupe_fd = grupuri_fdcp(circuits, tipuri_ap)
    sarcini, lipsa = [], []

    for p in (planse or []):
        tip = str(p.get("tip") or "")
        fam = _TIP_FAMILIE.get(tip)
        if not fam:
            continue                                   # planuri, detalii, scheme de sistem
        inst = str(p.get("nivel") or "").strip()
        tinta, afisat = None, None
        if tip == "schema_tes":
            # TES-urile se consuma IN ORDINE: si planşele, si tablourile vin din aceeasi lista de
            # niveluri (`extra_floors`), deci al n-lea TES anuntat e al n-lea tablou TES. Potrivirea
            # pe nume („TES2" <-> „etaj 2") ar fi fost o a doua conventie, si una care se rupe de
            # indata ce indexul nu mai e identitate — exact ce-a reparat P0.
            _luate = {s["_panel"] for s in sarcini}
            tinta = next((n for n in sorted(nume_panels, key=_cheie_tes)
                          if _pn.panel_family(n) == "TES" and n not in _luate), None)
        elif tip == "schema_ap":
            # O schema per TIP de apartament: tabloul REPREZENTATIV e al primului membru.
            t = next((t for t in (tipuri_ap or []) if t.get("nume") == inst), None)
            if t and t.get("membri"):
                tinta = _apm.panel_contur(t["membri"][0][1], _apm.CONTUR)
        elif tip == "schema_sp":
            tinta = _apm.panel_contur(inst, _apm.CONTUR_SP)
        elif tip == "schema_fdcp":
            # Numele anuntat e al GRUPULUI („FDCP ETAJ 1-2"), nu al unei firide. Reprezentantul e
            # primul membru; schema lui e schema tuturor, fiindca de-aia s-au grupat.
            g = next((g for g in grupe_fd if g["eticheta"] == inst), None)
            tinta = g["membri"][0] if g else None
            # Circuitele se citesc din reprezentant, dar pe planşa scrie GRUPUL — acelasi nume pe
            # care-l tipareste si borderoul.
            afisat = inst
        else:
            tinta = next((n for n in sorted(nume_panels) if _pn.panel_family(n) == fam), None)

        if not tinta or tinta not in nume_panels:
            lipsa.append({"nr": p.get("nr"), "tip": tip, "nume": p.get("nume"),
                          "motiv": "niciun tablou %s in circuite" % fam})
            continue
        descr = None
        if tip == "schema_ap":
            t = next((t for t in (tipuri_ap or []) if t.get("nume") == inst), None)
            # Schema de TIP isi declara singura domeniul, ca AP-1 de pe IE.25.
            descr = "%s (%s) — %s" % (_DESCRIERI["TE-AP"], inst, t.get("domeniu", "")) if t else None
        elif tip == "schema_fdcp":
            # Ca AP-1: o schema care vorbeste pentru mai multe obiecte isi declara domeniul, ca sa
            # se vada de pe planşa CARE firide se citesc aici. Una singura nu declara nimic.
            g = next((g for g in grupe_fd if g["eticheta"] == inst), None)
            if g and len(g["membri"]) > 1:
                descr = "%s — %s" % (_DESCRIERI["FDCP"], g["domeniu"])
        sarcini.append(_sarcina(tinta, p, circuits, graf, cartus_firma, cartus_proiect, descr,
                                nume_afisat=afisat))

    return {"sarcini": sarcini, "lipsa": lipsa}
