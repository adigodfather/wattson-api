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


def _sarcina(nume_tablou, plansa, circuits, graf, cartus_firma, cartus_proiect, descriere=None):
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
        "_panel": nume_tablou,
        "tablou_nume": nume_tablou,
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
        "cartus_proiect": dict(cartus_proiect or {}, plansa_nr=plansa.get("nr")),
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
    sarcini, lipsa = [], []

    for p in (planse or []):
        tip = str(p.get("tip") or "")
        fam = _TIP_FAMILIE.get(tip)
        if not fam:
            continue                                   # planuri, detalii, scheme de sistem
        inst = str(p.get("nivel") or "").strip()
        tinta = None
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
            tinta = next((n for n in sorted(nume_panels)
                          if _pn.panel_family(n) == "FDCP"
                          and inst.upper().replace("FDCP", "").strip() in n.upper()), None)
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
        sarcini.append(_sarcina(tinta, p, circuits, graf, cartus_firma, cartus_proiect, descr))

    return {"sarcini": sarcini, "lipsa": lipsa}
