# -*- coding: utf-8 -*-
"""
Numerotarea SECVENTIALA a planselor (IE.1..IE.N) — SINGURA sursa de adevar.

Ordinea fixa (confirmata Dan):
  1. Plan iluminat parter            (mereu)
  2. Plan iluminat etaj/nivel        (per nivel peste parter)
  3. Plan forta parter               (mereu)
  4. Plan forta etaj/nivel           (per nivel peste parter)
  5. Plan curenti slabi parter       (daca exista sistem de securitate)
  6. Plan curenti slabi etaj/nivel   (per nivel peste parter)
  7. Plan detectie incendiu parter   (daca exista sistem de detectie)
  8. Plan detectie incendiu nivel    (per nivel peste parter)
  9. Schema monofilara TEG           (mereu)
  8. Schema monofilara TES/nivel     (per nivel peste parter)
  9. Schema monofilara TE-CT         (daca exista echipament termic)
 10. Schema sistem curenti slabi    (daca exista echipamente de curenti slabi)
 11. Schema monofilara sistem FV    (MEREU ultima, daca exista FV)

Numerotare CONSECUTIVA fara goluri: se construieste lista planselor care EXISTA
(sar peste cele lipsa, in ordinea de mai sus), apoi IE.1, IE.2, ... pe lista.

Functie PURA (input = ce exista -> output = numerotarea). Zero dependinte, testabila izolat.
Faza 1: IZOLAT, nu se conecteaza la n8n. Faza 2: n8n calculeaza secventa cu asta si cheama
restamp_plansa (cartus_swap) pe fiecare PDF -> numarul TIPARIT = numarul din documente.

Numele contin diacritice (canonic, ca in memoriu_generator); cartusul le transpune la ASCII
la desenare (base14 helv/hebo, via _txt din cartus_swap). Aceeasi mapare serveste si memoriul.
"""

import floors as _fl                     # axa DESCHISA de niveluri (sursa unica; vezi floors.py)

# tipurile de plansa, in ORDINEA fixa de prioritate
TIPURI = ("plan_situatie",
          "plan_iluminat", "plan_forta", "plan_curenti_slabi", "plan_detectie_incendiu",
          "plan_camera_pompe_iluminat", "plan_camera_pompe_forta",
          "schema_distributie", "schema_bmpt_fdcp", "schema_fdcp",
          "schema_teg", "schema_tes", "schema_tect",
          "schema_camera_pompe", "schema_ap", "schema_sp", "schema_tcc", "schema_tecv",
          "schema_cs", "schema_detectie", "schema_fv",
          "schema_distributie_tv", "schema_distributie_date", "schema_distributie_interfon",
          "detaliu_iluminat_siguranta", "detaliu_priza_pamant", "detaliu_montaj_fv")

# eticheta de afisare per nivel (folosita in numele planselor)
_NIVEL_LABEL = {
    "parter": "PARTER", "p": "PARTER",
    "etaj": "ETAJ", "etaj1": "ETAJ", "etaj 1": "ETAJ", "e1": "ETAJ",
    "etaj2": "ETAJ 2", "etaj 2": "ETAJ 2", "e2": "ETAJ 2",
    "mansarda": "MANSARDA", "man": "MANSARDA",
    "demisol": "DEMISOL", "subsol": "SUBSOL",
}


def _nivel_label(nivel):
    """Eticheta de AFISARE a nivelului. Dictionarul ramane autoritatea (ca pana acum, pentru cele
    scrise explicit acolo); ce nu-i in el trece intai prin canonizarea axei, ca „etaj3"/„E3 retras"
    /„plan_etaj 3" sa dea toate „ETAJ 3", nu trei etichete diferite."""
    key = str(nivel or "").strip().lower()
    if key in _NIVEL_LABEL:
        return _NIVEL_LABEL[key]
    if not key:
        return str(nivel or "").strip().upper()        # None/gol -> "" , exact ca inainte
    return _fl.floor_canonic(nivel).upper()


def plansa_nume(tip, nivel=None):
    """Numele complet al planzei (canonic, cu diacritice)."""
    nl = _nivel_label(nivel)
    if tip == "plan_iluminat":
        return "PLAN {} INSTALAȚII ELECTRICE DE ILUMINAT".format(nl)
    if tip == "plan_forta":
        return "PLAN {} INSTALAȚII ELECTRICE DE FORȚĂ".format(nl)
    if tip == "plan_curenti_slabi":
        return "PLAN {} INSTALAȚII CURENȚI SLABI".format(nl)
    if tip == "plan_detectie_incendiu":
        # incape pe UN rand in celula de titlu a cartusului, chiar si cu "MANSARDA" (masurat cu
        # `_wrap2` pe latimea reala a celulei: 299 pt la 9 pt hebo). Peste doua randuri s-ar TAIA.
        return "PLAN {} INSTALAȚII DETECȚIE INCENDIU ȘI DESFUMARE".format(nl)
    if tip == "schema_teg":
        return "SCHEMA ELECTRICĂ MONOFILARĂ TABLOU ELECTRIC GENERAL"
    if tip == "schema_tes":
        return "SCHEMA ELECTRICĂ MONOFILARĂ TABLOU ELECTRIC SECUNDAR {}".format(nl)
    if tip == "schema_tect":
        return "SCHEMA ELECTRICĂ MONOFILARĂ TABLOU ELECTRIC CENTRALĂ TERMICĂ"
    if tip == "schema_cs":
        # = titlul mare desenat pe schema (schema_cs.TITLU). Sistem, nu tablou -> nu-i "monofilara".
        return "SCHEMA SISTEM CURENȚI SLABI"
    if tip == "schema_detectie":
        # = titlul mare desenat pe schema (schema_det.TITLU). Sistem, nu tablou.
        return "SCHEMA MONOBLOC INSTALAȚII DETECȚIE INCENDIU ȘI DESFUMARE"
    if tip == "schema_fv":
        # = titlul mare desenat pe plansa (schema_fv.py); cartusul ei zice "... - SISTEM FOTOVOLTAIC"
        # (formatul comun draw_cartouche, aceeasi relatie ca TEG/TES/TE-CT cu numele lor canonice)
        return "SCHEMA ELECTRICĂ MONOFILARĂ SISTEM FOTOVOLTAIC"
    # ── BLOC (P5) — titlurile urmeaza planşele REALE ale lui Dan, nu formulari inventate.
    # `nivel` poarta aici NUMELE instantei (FDCP-ul, tipul de apartament, spatiul comercial), nu un
    # nivel: tipurile care vin in mai multe exemplare au nevoie sa se distinga intre ele, iar campul
    # exista deja si calatoreste pana in borderou.
    if tip == "plan_situatie":
        return "PLAN DE SITUAȚIE INSTALAȚII ELECTRICE"
    if tip == "plan_camera_pompe_iluminat":
        return "PLAN CAMERA POMPELOR INSTALAȚII ELECTRICE DE ILUMINAT"
    if tip == "plan_camera_pompe_forta":
        return "PLAN CAMERA POMPELOR INSTALAȚII ELECTRICE DE FORȚĂ"
    if tip == "schema_distributie":
        return "SCHEMA ELECTRICĂ DE DISTRIBUȚIE"
    if tip == "schema_bmpt_fdcp":
        return "SCHEMA ELECTRICĂ MONOFILARĂ BMPT ȘI FDCP"
    if tip == "schema_fdcp":
        return "SCHEMA ELECTRICĂ MONOFILARĂ {}".format(_inst(nivel, "FDCP"))
    if tip == "schema_camera_pompe":
        return "SCHEMA ELECTRICĂ MONOFILARĂ CAMERA POMPE"
    if tip == "schema_ap":
        return "SCHEMA ELECTRICĂ MONOFILARĂ TABLOU ELECTRIC {}".format(_inst(nivel, "AP"))
    if tip == "schema_sp":
        return "SCHEMA ELECTRICĂ MONOFILARĂ {}".format(_inst(nivel, "SP"))
    if tip == "schema_tcc":
        return "SCHEMA ELECTRICĂ MONOFILARĂ TCC"
    if tip == "schema_tecv":
        return "SCHEMA ELECTRICĂ MONOFILARĂ CONSUMATORI VITALI"
    if tip == "schema_distributie_tv":
        return "SCHEMA DE DISTRIBUȚIE REȚEA CABLU TV"
    if tip == "schema_distributie_date":
        return "SCHEMA DE DISTRIBUȚIE DATE"
    if tip == "schema_distributie_interfon":
        return "SCHEMA DE DISTRIBUȚIE REȚEA DE INTERFON"
    if tip == "detaliu_iluminat_siguranta":
        return "DETALIU ILUMINAT DE SIGURANȚĂ"
    if tip == "detaliu_priza_pamant":
        return "DETALIU CONECTARE PRIZĂ DE PĂMÂNT"
    if tip == "detaliu_montaj_fv":
        return "DETALIU MONTAJ PANOU FOTOVOLTAIC"
    return "PLANȘĂ"


def _inst(nume, implicit):
    """Numele INSTANTEI pentru tipurile care vin in mai multe exemplare (FDCP-uri, tipuri de
    apartament, spatii comerciale). Gol -> eticheta generica, ca planşa sa nu iasa fara nume."""
    n = str(nume or "").strip()
    return n.upper() if n else implicit


def compute_plansa_numbering(extra_floors=None, has_tect=False, has_tes=None, has_fv=False,
                             has_cs=False, has_schema_cs=None, has_det=False,
                             has_schema_det=None, coborare_floors=None,
                             # ── BLOC (P5). TOATE au implicit ABSENT, si asta e non-regresia:
                             # o casa nu trimite niciunul, deci lista iese exact ca pana acum.
                             # Fiecare e GATED PE PREZENTA, nu pe „e bloc": un numar rezervat
                             # pentru o planşa care nu vine deplaseaza tot restul si promite
                             # clientului ceva ce nu primeste — exact golul inchis la 156a89b.
                             has_situatie=False, has_camera_pompe=False, has_teg=True,
                             has_distributie=False, has_bmpt_fdcp=False,
                             fdcp=None, apartamente=None, spatii=None,
                             has_tcc=False, has_tecv=False,
                             has_tv=False, has_date=False, has_interfon=False,
                             detalii=None):
    """Lista ORDONATA a planselor EXISTENTE, numerotate IE.1..IE.N FARA goluri.

    extra_floors: nivelurile peste parter, in ordine (ex. ["etaj"] sau ["etaj","mansarda"]).
                  Gol/None => casa doar parter.
    has_tect:     exista tablou centrala termica (echipament termic: boiler/pdc/pompe/ventilatie
                  SAU circuite panel=TE-CT).
    has_tes:      override; implicit = exista cel putin un nivel peste parter (o schema TES per nivel).
    has_fv:       sistem fotovoltaic selectat (extra_equipment.solar.enabled) -> schema FV = ULTIMA
                  plansa IE. Absent/False = nicio plansa FV (non-regresie proiecte fara FV).
    has_cs:       sistem de curenti slabi (efractie + supraveghere video) -> cate o plansa per nivel,
                  DUPA planurile de forta si INAINTEA schemelor (gruparea "planuri, apoi scheme").
                  Spre deosebire de FV (mereu ultima), asta DEPLASEAZA schemele cu len(floors)
                  pozitii. Absent/False = nicio plansa CS (non-regresie totala).
    has_det:      sistem de detectie incendiu si desfumare -> cate o plansa per nivel, DUPA cele de
                  curenti slabi si INAINTEA schemelor (aceeasi grupare "planuri, apoi scheme").
                  Ca si CS, DEPLASEAZA schemele cu len(floors) pozitii. Absent/False = nimic.
    coborare_floors: nivelurile care NU au tablou secundar — circuitele lor coboara la TEG printr-un
                  punct plasat de inginer, deci nivelul NU primeste schema TES.
                  E lista EXCEPTIILOR, nu a nivelurilor cu tablou, si asta e deliberat:
                    - oglindeste `enrich_circuits._panel_for_floor` — singurul caz care schimba
                      tabloul e punctul de coborare; „are tablou" si „n-are nimic" duc amandoua la TES;
                    - absenta ei (proiectele de pana acum, si generarea, unde elementele nu exista
                      inca) da AUTOMAT numerotarea de azi — non-regresia e structurala, nu un caz
                      special de intretinut.

    Return: [{"nr": "IE.N", "tip": ..., "nivel": ..., "nume": ...}, ...]
    """
    extra = [f for f in (extra_floors or []) if str(f or "").strip()]
    # ORDINEA PE VERTICALA, nu „parterul intai si restul dupa". Defectul se vedea abia cu subsol:
    # `["parter"] + extra` il aseza DUPA parter, desi e sub el — la Dan subsolul e planşa IE.2, iar
    # parterul IE.3. `sort_floors` asaza dupa indexul axei, deci parter/etaj/mansarda raman EXACT in
    # ordinea de pana acum (0 < 1 < 2) si nimic nu se schimba pe proiectele existente.
    floors = _fl.sort_floors(["parter"] + extra)
    extra = [f for f in floors if f != _fl.PARTER]        # canonizate + ordonate, fara parter
    tes_on = bool(extra) if has_tes is None else bool(has_tes)
    _cob = {str(f or "").strip().lower() for f in (coborare_floors or []) if str(f or "").strip()}

    sheets = []
    # ── BLOC: planul de SITUATIE deschide borderoul (IE.1 la Dan). E singura planşa care arata
    # cladirea in teren, nu in ea insasi — de-aia sta inaintea tuturor.
    if has_situatie:
        sheets.append(("plan_situatie", None))
    # 1-2: TOATE planurile de iluminat (parter, apoi nivelurile) — inaintea fortei (ordinea Dan)
    for fl in floors:
        sheets.append(("plan_iluminat", fl))
    # 3-4: TOATE planurile de forta (parter, apoi nivelurile)
    for fl in floors:
        sheets.append(("plan_forta", fl))
    # 5-6: TOATE planurile de curenti slabi (parter, apoi nivelurile) — dupa forta, inaintea schemelor
    if has_cs:
        for fl in floors:
            sheets.append(("plan_curenti_slabi", fl))
    # 7-8: TOATE planurile de detectie incendiu — dupa curenti slabi, inaintea schemelor
    if has_det:
        for fl in floors:
            sheets.append(("plan_detectie_incendiu", fl))
    # ── BLOC: planşele camerei de pompe. Sunt planşe de INCAPERE, nu de nivel — de-aia n-au
    # eticheta de nivel si nu se multiplica cu `floors`.
    if has_camera_pompe:
        sheets.append(("plan_camera_pompe_iluminat", None))
        sheets.append(("plan_camera_pompe_forta", None))
    # ── BLOC: arborele de distributie si firidele, INAINTEA schemelor de tablou (asa citesti
    # ierarhia: de la bransament in jos).
    if has_distributie:
        sheets.append(("schema_distributie", None))
    if has_bmpt_fdcp:
        sheets.append(("schema_bmpt_fdcp", None))
    for _f in (fdcp or []):
        sheets.append(("schema_fdcp", _f))
    # 9: TEG. `has_teg` e implicit True = comportamentul de pana acum; un bloc il trece pe False,
    # fiindca acolo tabloul general e TEGD si apare in schema de distributie, nu ca TEG.
    if has_teg:
        sheets.append(("schema_teg", "parter"))
    # 6: TES — cate una per nivel peste parter, MAI PUTIN nivelurile cu punct de coborare (acolo
    # nu exista tablou secundar, deci n-are ce schema sa se genereze; un numar rezervat pentru o
    # planşa care nu vine deplaseaza degeaba tot ce urmeaza)
    if tes_on:
        for fl in extra:
            if str(fl or "").strip().lower() in _cob:
                continue
            sheets.append(("schema_tes", fl))
    # 7: TE-CT (daca exista)
    if has_tect:
        sheets.append(("schema_tect", None))
    # ── BLOC: schemele de tablou, in ordinea de pe planşele lui Dan.
    if has_camera_pompe:
        sheets.append(("schema_camera_pompe", None))
    for _a in (apartamente or []):
        sheets.append(("schema_ap", _a))       # una per TIP de apartament (P4 stie care-s identice)
    for _sp in (spatii or []):
        sheets.append(("schema_sp", _sp))      # una per spatiu comercial
    if has_tcc:
        sheets.append(("schema_tcc", None))
    if has_tecv:
        sheets.append(("schema_tecv", None))
    # 8: schema sistemului de curenti slabi — DUPA schemele de tablou, INAINTEA FV (care ramane
    # ultima, decizia Dan). Implicit urmeaza planşa de curenti slabi (has_cs): daca exista planşa,
    # exista si schema. `has_schema_cs` permite decuplarea lor (ex. planşa desenata dar goala).
    if has_cs if has_schema_cs is None else has_schema_cs:
        sheets.append(("schema_cs", None))
    # 9: schema sistemului de detectie incendiu — DUPA schema de curenti slabi, INAINTEA FV.
    # Acelasi tipar ca `has_schema_cs`: implicit urmeaza planşa (has_det), dar se poate decupla.
    if has_det if has_schema_det is None else has_schema_det:
        sheets.append(("schema_detectie", None))
    # 10: schema FV — ultima dintre SCHEMELE DE INSTALATIE, doar cu sistem fotovoltaic selectat.
    # „Mereu ultima" era adevarat cat timp dupa ea nu venea nimic; la bloc vin schemele de
    # distributie a curentilor slabi si detaliile. Pozitia ei RELATIVA fata de tot ce exista azi
    # ramane insa neschimbata — nimic nou nu se strecoara inaintea ei pe o casa.
    if has_fv:
        sheets.append(("schema_fv", None))
    # ── BLOC: distributia curentilor slabi (TV / date / interfon), apoi DETALIILE, la final.
    # Detaliile inchid borderoul fiindca sunt planşe TIPIZATE: nu descriu cladirea, ci cum se
    # executa un lucru. La Dan sunt IE.35-37, ultimele trei.
    if has_tv:
        sheets.append(("schema_distributie_tv", None))
    if has_date:
        sheets.append(("schema_distributie_date", None))
    if has_interfon:
        sheets.append(("schema_distributie_interfon", None))
    for _d in (detalii or []):
        sheets.append(("detaliu_%s" % _d, None))

    out = []
    for i, (tip, nivel) in enumerate(sheets, start=1):
        out.append({
            "nr": "IE.{}".format(i),
            "tip": tip,
            "nivel": nivel,
            "nume": plansa_nume(tip, nivel),
        })
    return out


# floor INTREG din circuite -> nume nivel. Semnal FIABIL: nivel/level sunt NULL in DB,
# plan_elements.floor e "parter" peste tot; floor intreg e singura sursa corecta (verificat pe 715
# circuite: 330 floor=0, 79 floor=1). Delegat la axa: 1 -> „etaj", 2 -> „mansarda" (MOSTENIT,
# neschimbat), iar peste 2 nu mai iese „nivel 3", ci „etaj 3".
def _floor_to_label(f):
    return _fl.floor_canonic(f)


def derive_extra_floors(circuits):
    """Nivelurile ALTELE DECAT PARTERUL, din circuite, ordonate de jos in sus.

    DOUA surse, in ordinea increderii:
      1. `floor_label` — eticheta canonica pusa de enrich de la P0 incoace. Autoritatea, fiindca
         numele nivelului nu mai e deductibil din intreg: 2 a insemnat dintotdeauna „mansarda", dar
         pe axa deschisa poate fi si „etaj 2", iar subsolul (negativ) n-avea cum sa apara deloc.
      2. `floor` INTREG — fallback pentru circuitele de dinaintea pachetului (si pentru apelurile
         directe / teste). Exact regula veche: distinct > 0, sortat crescator, 1 -> „etaj",
         2 -> „mansarda". Circuit fara floor numeric valid -> ignorat (nu presupune parter gresit).

    Fara `floor_label` nicaieri — adica toate proiectele existente — rezultatul e IDENTIC cu cel de
    dinainte. Asta face non-regresia structurala, nu un caz special de intretinut.

    NU keyword-matching pe intreg (nesigur: "etaj" in "1" = False). Sursa PRIMARA ramane explicit
    din n8n (Faza 2B); asta e derivarea de fallback (borderoul memoriului / apeluri directe)."""
    etichete = [str((c or {}).get("floor_label") or "").strip()
                for c in (circuits or []) if (c or {}).get("floor_label")]
    if etichete:
        return [f for f in _fl.sort_floors(etichete) if f != _fl.PARTER]
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


# tipul planului persistat (result_data.planuri[].type) -> eticheta nivelului. Sursa PREFERATA la
# regenerare: levels_string NU se persista in result_data (verificat: NULL peste tot), dar tipul
# planului reflecta numele REAL al nivelului (plan_mansarda pe P+M) — aliniat cu nodul n8n
# "Numerotare Planse" (care deriva din levels_string la generare).
_PLAN_TYPE_LABEL = {
    "plan_etaj": "etaj", "plan_etaj1": "etaj", "plan_etaj2": "etaj 2",
    "plan_mansarda": "mansarda", "plan_demisol": "demisol", "plan_subsol": "subsol",
}


def pick_plan_entry(result_data, plan_type, floor):
    """Intrarea {nr, nume, ...} pentru PLANUL (iluminat/forta) al nivelului `floor` din autoritatea
    compute_plansa_numbering — folosita de /regenerate-plan ca planul regenerat sa primeasca numarul
    FINAL IE.N (forta parter=IE.3 pe model complet), nu numarul mostenit al planului de baza.

    Derivarea nivelurilor: 1) result_data.planuri[].type (persistat, etichete reale — P+M da
    'mansarda'); 2) fallback: floor intreg din circuite (derive_extra_floors). has_tect: flag-ul
    result_data.has_tect SAU panel=TE-CT in circuite.

    `floor` = conventia frontend floorCanonic PE INDEX (parter=0->'parter', 1->'etaj', 2->'mansarda')
    -> match POZITIONAL pe lista nivelurilor (robust la divergenta de eticheta etaj/mansarda pe P+M:
    index 1 = primul nivel peste parter, oricum s-ar numi). None daca nu se poate determina —
    apelantul pastreaza comportamentul vechi (fara stampare)."""
    rd = result_data or {}
    circuits = rd.get("circuits") or []

    # `planuri[1:]` = nivelurile peste parter. Saltul POZITIONAL ramane neatins deliberat: in baza
    # exista 10 proiecte cu `planuri[0].type = "plan_generic"` (masurat), iar orice filtrare pe
    # eticheta l-ar citi ca nivel necunoscut si le-ar inventa un etaj. Ce se schimba e doar
    # DERIVAREA numelui pentru tipurile din afara dictionarului: trece intai prin axa, deci
    # „plan_etaj3" da „etaj 3", nu genericul „etaj".
    # LIMITA CUNOSCUTA: pe o cladire unde parterul NU e planşa [0] (bloc cu subsol) saltul ar sari
    # subsolul. Nu se poate intampla inca — ordinea planselor de bloc se decide la P1/P2, odata cu
    # generarea lor — si o repar acolo, cu ordinea reala in fata, nu ghicind-o acum.
    extra = []
    for p in (rd.get("planuri") or [])[1:]:            # [0] = parter
        t = str((p or {}).get("type") or "").strip().lower()
        if t in _PLAN_TYPE_LABEL:
            extra.append(_PLAN_TYPE_LABEL[t])
            continue
        _c = _fl.floor_canonic(t)                      # „plan_etaj3" -> „etaj 3"
        extra.append(_c if _c != _fl.PARTER else "etaj")   # nerecunoscut la nivel>0 -> ca inainte
    if not extra:
        extra = derive_extra_floors(circuits)

    has_tect = bool(rd.get("has_tect")) or any((c or {}).get("panel") == "TE-CT" for c in circuits)
    _pt = str(plan_type or "").strip().lower()
    tip = {"forta": "plan_forta", "curenti_slabi": "plan_curenti_slabi",
           "detectie_incendiu": "plan_detectie_incendiu"}.get(_pt, "plan_iluminat")
    # CURENTI SLABI: planşele lor stau DUPA forta, deci nu deplaseaza iluminatul/forta -> pentru
    # acelea has_cs e irelevant. Dar cand se cere chiar planşa de curenti slabi, ea trebuie sa
    # existe in lista, altfel n-ar avea numar. Semnalul: fie tipul cerut, fie planse deja salvate.
    has_cs = (tip == "plan_curenti_slabi") or bool(rd.get("planse_curenti_slabi"))
    # DETECTIA sta DUPA curenti slabi, deci trebuie sa existe in lista si cand se cere ea insasi, si
    # cand exista deja planse salvate — altfel n-ar primi numar (acelasi rationament ca la has_cs).
    has_det = (tip == "plan_detectie_incendiu") or bool(rd.get("planse_detectie"))
    entries = [p for p in compute_plansa_numbering(extra, has_tect, has_cs=has_cs, has_det=has_det)
               if p["tip"] == tip]

    fidx = {"parter": 0, "etaj": 1, "etaj1": 1, "etaj 1": 1,
            "mansarda": 2, "etaj2": 2, "etaj 2": 2}.get(str(floor or "parter").strip().lower(), 0)
    if fidx >= len(entries):
        return None
    return entries[fidx]
