# -*- coding: utf-8 -*-
"""
Numerotarea SECVENTIALA a planselor (IE.1..IE.N) — SINGURA sursa de adevar.

Ordinea fixa (confirmata Dan):
  1. Plan iluminat parter            (mereu)
  2. Plan iluminat etaj/nivel        (per nivel peste parter)
  3. Plan forta parter               (mereu)
  4. Plan forta etaj/nivel           (per nivel peste parter)
  5. Schema monofilara TEG           (mereu)
  6. Schema monofilara TES/nivel     (per nivel peste parter)
  7. Schema monofilara TE-CT         (daca exista echipament termic)

Numerotare CONSECUTIVA fara goluri: se construieste lista planselor care EXISTA
(sar peste cele lipsa, in ordinea de mai sus), apoi IE.1, IE.2, ... pe lista.

Functie PURA (input = ce exista -> output = numerotarea). Zero dependinte, testabila izolat.
Faza 1: IZOLAT, nu se conecteaza la n8n. Faza 2: n8n calculeaza secventa cu asta si cheama
restamp_plansa (cartus_swap) pe fiecare PDF -> numarul TIPARIT = numarul din documente.

Numele contin diacritice (canonic, ca in memoriu_generator); cartusul le transpune la ASCII
la desenare (base14 helv/hebo, via _txt din cartus_swap). Aceeasi mapare serveste si memoriul.
"""

# tipurile de plansa, in ORDINEA fixa de prioritate
TIPURI = ("plan_iluminat", "plan_forta", "schema_teg", "schema_tes", "schema_tect")

# eticheta de afisare per nivel (folosita in numele planselor)
_NIVEL_LABEL = {
    "parter": "PARTER", "p": "PARTER",
    "etaj": "ETAJ", "etaj1": "ETAJ", "etaj 1": "ETAJ", "e1": "ETAJ",
    "etaj2": "ETAJ 2", "etaj 2": "ETAJ 2", "e2": "ETAJ 2",
    "mansarda": "MANSARDA", "man": "MANSARDA",
    "demisol": "DEMISOL", "subsol": "SUBSOL",
}


def _nivel_label(nivel):
    key = str(nivel or "").strip().lower()
    return _NIVEL_LABEL.get(key, str(nivel or "").strip().upper())


def plansa_nume(tip, nivel=None):
    """Numele complet al planzei (canonic, cu diacritice)."""
    nl = _nivel_label(nivel)
    if tip == "plan_iluminat":
        return "PLAN {} INSTALAȚII ELECTRICE DE ILUMINAT".format(nl)
    if tip == "plan_forta":
        return "PLAN {} INSTALAȚII ELECTRICE DE FORȚĂ".format(nl)
    if tip == "schema_teg":
        return "SCHEMA ELECTRICĂ MONOFILARĂ TABLOU ELECTRIC GENERAL"
    if tip == "schema_tes":
        return "SCHEMA ELECTRICĂ MONOFILARĂ TABLOU ELECTRIC SECUNDAR {}".format(nl)
    if tip == "schema_tect":
        return "SCHEMA ELECTRICĂ MONOFILARĂ TABLOU ELECTRIC CENTRALĂ TERMICĂ"
    return "PLANȘĂ"


def compute_plansa_numbering(extra_floors=None, has_tect=False, has_tes=None):
    """Lista ORDONATA a planselor EXISTENTE, numerotate IE.1..IE.N FARA goluri.

    extra_floors: nivelurile peste parter, in ordine (ex. ["etaj"] sau ["etaj","mansarda"]).
                  Gol/None => casa doar parter.
    has_tect:     exista tablou centrala termica (echipament termic: boiler/pdc/pompe/ventilatie
                  SAU circuite panel=TE-CT). TE-CT e mereu ULTIMA.
    has_tes:      override; implicit = exista cel putin un nivel peste parter (o schema TES per nivel).

    Return: [{"nr": "IE.N", "tip": ..., "nivel": ..., "nume": ...}, ...]
    """
    extra = [f for f in (extra_floors or []) if str(f or "").strip()]
    floors = ["parter"] + extra
    tes_on = bool(extra) if has_tes is None else bool(has_tes)

    sheets = []
    # 1-2: TOATE planurile de iluminat (parter, apoi nivelurile) — inaintea fortei (ordinea Dan)
    for fl in floors:
        sheets.append(("plan_iluminat", fl))
    # 3-4: TOATE planurile de forta (parter, apoi nivelurile)
    for fl in floors:
        sheets.append(("plan_forta", fl))
    # 5: TEG (mereu)
    sheets.append(("schema_teg", "parter"))
    # 6: TES — cate una per nivel peste parter
    if tes_on:
        for fl in extra:
            sheets.append(("schema_tes", fl))
    # 7: TE-CT (ultima, daca exista)
    if has_tect:
        sheets.append(("schema_tect", None))

    out = []
    for i, (tip, nivel) in enumerate(sheets, start=1):
        out.append({
            "nr": "IE.{}".format(i),
            "tip": tip,
            "nivel": nivel,
            "nume": plansa_nume(tip, nivel),
        })
    return out


# floor INTREG din circuite (0=parter, 1=etaj, 2=mansarda — conventia lib/floors.ts / planLabel)
# -> nume nivel. Semnal FIABIL: nivel/level sunt NULL in DB, plan_elements.floor e "parter" peste tot;
# floor intreg e singura sursa corecta (verificat pe 715 circuite: 330 floor=0, 79 floor=1).
_FLOOR_INT_LABEL = {1: "etaj", 2: "mansarda"}


def _floor_to_label(f):
    return _FLOOR_INT_LABEL.get(f, "nivel {}".format(f))


def derive_extra_floors(circuits):
    """Deduce nivelurile PESTE parter din campul INTREG `floor` al circuitelor (0=parter, 1=etaj,
    2=mansarda). Distinct floor>0, sortat crescator -> nume nivel.

    NU keyword-matching (nesigur: floor e INTREG, "etaj" in "1" = False -> rata etajul; nivel/level-s
    NULL in DB). Circuit fara floor numeric valid -> ignorat (nu presupune parter gresit). Toate lipsa
    -> [] (doar parter). Sursa PRIMARA ramane explicit din n8n (Faza 2B); asta e derivarea CORECTA pt.
    fallback (borderoul memoriului / apeluri directe / teste)."""
    floors = set()
    for c in (circuits or []):
        f = (c or {}).get("floor")
        try:
            fi = int(f)                       # accepta int, "1", 1.0; respinge None / "etaj"
        except (TypeError, ValueError):
            continue                          # floor lipsa/nenumeric -> ignora circuitul (NU = parter)
        if fi > 0:
            floors.add(fi)
    return [_floor_to_label(f) for f in sorted(floors)]
