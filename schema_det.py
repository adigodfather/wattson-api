# -*- coding: utf-8 -*-
"""SCHEMA FUNCTIONALA a sistemului de detectie incendiu si desfumare.

REFOLOSESTE integral mecanismele schemei de curenti slabi (`schema_cs`): masuratorile si asezarea pe
benzi (`_masoara`, parametrizata), desenul coloanelor si al fasciculelor (`_deseneaza_benzi`),
cablarea in STEA cu laneuri disjuncte (`_leaga_cutie` -> `_stea`), cutiile (`_bloc`), legenda si
cartusul (`_cartus_final`). Aici sta DOAR ce e propriu incendiului: ce intra pe fiecare ramura, ce
scrie in cele doua cutii si nota de subsol.

Doua ramuri, fiecare cu cutia ei — de-aia benzile existente se potrivesc fara caz special:
  SUS  DETECTIE  -> CENTRALA (bucla adresabila, cablu E30)
  JOS  DESFUMARE -> TABLOUL GENERAL (circuite dedicate, cablu de forta)
"""
import math
import fitz

import draw_elements as DE
from draw_elements import (_CS_CABLE, _DET_ABBR, _DET_TYPES, _draw_cs, build_legend_rows,
                           cs_index_map, det_arie, det_are_circuit, det_eticheta, det_loop_map,
                           det_ordine_bucla, det_putere_receptor)
from schema_cs import (MMPT, _A3, _PAD_MM, _NEGRU, _HUB_W, _bloc, _cablu, _cartus_final,
                       _deseneaza_benzi, _gap_hub, _incape_in_cutie, _leaga_cutie, _legenda_dim,
                       _legenda_split, _masoara, _text, _draw_legend, _rezerva_fascicule,
                       _COL_GAP)

# „MONOBLOC" e termenul din practica: ambele scheme de referinta (Technic Jobs, Arhi Act) il
# folosesc. Titlul e mai lung si nu mai incape pe UN rand in celula cartusului (311 pt fata de
# 299) — se rupe pe DOUA, iar celula taie abia la trei. Masurat, nu presupus.
TITLU = "SCHEMA MONOBLOC INSTALAȚII DETECȚIE INCENDIU ȘI DESFUMARE"

# RAMURA 1: ce sta pe bucla adresabila a centralei. ACEEASI lista ca la dimensionare
# (`DE._DET_ADRESABILE`) — daca s-ar scrie a doua oara aici, schema ar putea desena un dispozitiv
# pe care centrala nu-l numara, sau invers.
_BUCLA = DE._DET_ADRESABILE
# RAMURA 2: echipamentele de desfumare. Trapa PNEUMATICA e in lista — apare pe schema, dar FARA
# linie de alimentare (n-are circuit): cine citeste schema trebuie s-o vada, ca sa stie ca exista.
_DESFUMARE = ("trapa_desfumare", "ventilator_desfumare", "clapeta_antifoc", "grila_admisie")

_SCURT = {
    "detector_fum": "detector optic de fum",
    "detector_caldura": "detector termic",
    "buton_incendiu": "declanșator manual",
    "sirena_incendiu": "sirenă de avertizare",
    "panou_repetor": "panou repetor",
    "trapa_desfumare": "trapă de evacuare a fumului",
    "ventilator_desfumare": "ventilator de evacuare a fumului",
    "clapeta_antifoc": "clapetă antifoc",
    "grila_admisie": "grilă motorizată de admisie",
}


# Eticheta vine din `draw_elements.det_eticheta` — SURSA UNICA cu planşa. „D1/3" de pe schema si
# „D1/3" de pe desen sunt acelasi apel, deci nu pot diverge.


def _det_elemente(elements):
    """Elementele de incendiu, grupate pe rol, cu eticheta de pe planşa deja calculata."""
    els = [e for e in (elements or [])
           if ((e or {}).get("element_type") or "") in _DET_TYPES]
    idx = cs_index_map(els)
    lmap = det_loop_map(els)
    # aceeasi sortare ca numerotarea (sus->jos, apoi stanga->dreapta) -> ordinea de pe schema
    # urmeaza ordinea de pe planşa, deci „D1/1" e primul si pe hartie
    els.sort(key=lambda d: (float(d.get("y") or 0), float(d.get("x") or 0)))

    def _grup(tipuri):
        return [(e, det_eticheta(e, lmap, idx)) for e in els
                if (e.get("element_type") or "") in tipuri]

    return {
        "bucla": _grup(_BUCLA),
        "desfumare": _grup(_DESFUMARE),
        "centrala": _grup(("centrala_detectie",)),
        # `toate` merge la legenda: intra si traseele desenate (E30), care nu-s in `_DET_TYPES`
        "toate": [e for e in (elements or [])
                  if ((e or {}).get("element_type") or "") in _DET_TYPES
                  or ((e or {}).get("element_type") or "") == "traseu_cs"],
    }


# SEPARATORUL e „ - ", nu „ · " si nici em-dash: CAPCANA DE MASURARE — `_ascii` transpune em-dash-ul
# in „·", iar `fitz.get_text_length` masoara „·" cu 0,278 em MAI PUTIN decat il deseneaza. Pozitia
# de start a liniei se calculeaza din latimea MASURATA, deci fiecare „·" o aduce cu ~1,8 pt in
# stanga si linia intra peste ultimele litere. Cu doua separatoare, 3,6 pt — mai mult decat marja.
_SEP = " - "


def _descriere(el, cod=None):
    """Textul scurt al randului. La detectoare se adauga ARIA acoperita (informatia care justifica
    numarul lor), la desfumare PUTEREA si codul de circuit (informatia care justifica cablul)."""
    t = (el or {}).get("element_type") or ""
    baza = _SCURT.get(t, t)
    if t in ("detector_fum", "detector_caldura"):
        return "%s%s%d mp" % (baza, _SEP, det_arie(el))
    if t in _DESFUMARE:
        if not det_are_circuit(el):
            return "%s%sacționare pneumatică, fără alimentare" % (baza, _SEP)
        _p = det_putere_receptor(el)
        return "%s%s%s%d W" % (baza, _SEP, ("%s%s" % (cod, _SEP)) if cod else "", _p)
    return baza


def _grupuri(g, coduri=None):
    """Cele doua coloane ale schemei. Grupurile GOALE nu apar — acelasi tipar ca la curenti slabi."""
    coduri = coduri or {}
    # Bucla NU mai e o coloana in stea: e o SERPENTINA (un singur fir prin toate dispozitivele),
    # desenata de `_serpentina`. Aici raman doar coloanele care chiar merg la o cutie.
    out = []
    if g["desfumare"]:
        out.append({"cheie": "desfumare", "titlu": "DESFUMARE", "col": DE._PRIZA_COLOR,
                    "kind": "forta_det", "cutie": "teg",
                    # trapa PNEUMATICA se DESENEAZA, dar nu se leaga: n-are circuit. Fara asta,
                    # schema i-ar trage o linie de alimentare exact langa textul care spune ca
                    # nu se alimenteaza.
                    "fara_linie": {el.get("id") for el, _ in g["desfumare"]
                                   if not det_are_circuit(el)},
                    "randuri": [(el, et, _descriere(el, coduri.get(el.get("id"))))
                                for el, et in g["desfumare"]]})
    return out


# IESIRILE DE COMANDA ale centralei, ca in schemele monobloc de referinta: cate o linie din ECS,
# cu functia scrisa langa ea. Toate cele cinci sunt DERIVABILE din ce stie proiectul — n-am pus
# „deblocare usi cu control acces" sau „panou actionare electroventil" tocmai fiindca ZYNAPSE nu
# modeleaza acele instalatii, iar o iesire desenata pentru un echipament inexistent e o afirmatie
# falsa pe planşa (decizia Dan).
#   `gate`: None = mereu cand exista centrala; "desfumare" = doar cu echipamente de desfumare.
_ECS_COMENZI = (
    # singura conditionata: fara ventilatoare/trape/clapete n-are ce comanda
    ("desfumare", "comandă desfumare la alarmă"),
    # tabloul general e pe planşa de detectie de la pachetul trecut, iar centrala se alimenteaza
    # chiar din el — sageata de 230 V o spune deja pe aceeasi foaie
    # cratima, nu em-dash: `_ascii` NU transpune „—", iar fontul base-14 nu-l are si-l deseneaza
    # ca interpunct — textul de pe foaie ar fi diferit de cel din cod, iar latimea masurata ar fi
    # si ea gresita (aceeasi capcana ca la `_SEP`).
    (None, "comandă TEG - întrerupere alimentare cu energie electrică"),
    # acumulatorul de rezerva e in fiecare centrala (scrie in cutia ei), deci ambele monitorizari
    # de sursa au mereu obiect
    (None, "monitorizare pierdere sursă de bază"),
    (None, "mobilizare sursă de rezervă de energie a ECS"),
    # obligatie P118/3, independenta de ce echipamente s-au plasat
    (None, "semnal la operatorul telefonic - anunțarea serviciului de pompieri"),
)
_CMD_PAS = 13.0         # distanta intre doua iesiri de comanda
_CMD_STUB = 22.0        # lungimea segmentului orizontal dinaintea textului


def _comenzi_ecs(page, r_c, y0, x_hub_mid=None, y_teg=None, cu_desfumare=True):
    """Cele cinci iesiri, ca o magistrala verticala din ECS + cate un braț orizontal per functie.
    Intoarce y-ul de sub ultima. Bratul desfumarii CONTINUA pana la cutia TEG — celelalte se opresc
    la text, fiindca echipamentul lor nu e desenat pe foaia asta."""
    _c = _CS_CABLE["semnal"]
    _xc = r_c.x0 + _S_ECS_W / 2.0
    _lista = [t for gate, t in _ECS_COMENZI if gate is None or cu_desfumare]
    sh = page.new_shape()
    sh.draw_line(fitz.Point(_xc, r_c.y1), fitz.Point(_xc, y0 + (len(_lista) - 1) * _CMD_PAS))
    for i, txt in enumerate(_lista):
        _y = y0 + i * _CMD_PAS
        _x1 = (x_hub_mid if (i == 0 and cu_desfumare and x_hub_mid is not None)
               else _xc + _CMD_STUB)
        sh.draw_line(fitz.Point(_xc, _y), fitz.Point(_x1, _y))
        if i == 0 and cu_desfumare and x_hub_mid is not None and y_teg is not None:
            sh.draw_line(fitz.Point(x_hub_mid, _y), fitz.Point(x_hub_mid, y_teg))
    sh.finish(color=_c["col"], width=1.0, dashes=_c["dash"], closePath=False)
    sh.commit()
    for i, txt in enumerate(_lista):
        _text(page, _xc + _CMD_STUB + 4.0, y0 + i * _CMD_PAS - 2.0, txt, fs=5.6, col=_c["col"])
    return y0 + (len(_lista) - 1) * _CMD_PAS


# ── SERPENTINA BUCLEI ────────────────────────────────────────────────────────────────────────
_S_PAS_X = 118.0        # distanta intre doua dispozitive pe acelasi rand
_S_PAS_Y = 46.0         # distanta intre randurile serpentinei
_S_ZONA_PAD = 10.0      # marginea zonei colorate a unei bucle
_S_ZONA_GAP = 14.0      # spatiul dintre doua zone de bucla
_S_ECS_W = 92.0         # latimea cutiei ECS din stanga
# Fundalul zonei: rosul familiei, foarte diluat. Nu o culoare noua — zona trebuie citita ca fiind
# a aceluiasi sistem, nu ca al cincilea sistem pe foaie.
_S_ZONA_FILL = tuple(1.0 - (1.0 - c) * 0.07 for c in DE._DET_FAMILIE)


# TREPTELE de asezare a serpentinei, de la cea mai aerisita la cea mai stransa: (pas x, pas y,
# scrie si descrierea sub eticheta). O buclă poate avea pana la 127 de dispozitive, iar la pasul
# generos ar iesi de pe foaie — asa ca asezarea se STRANGE pana incape, si abia daca nici cea mai
# stransa nu ajunge se scrie pe planşa ca sistemul depaseste A3. Descrierea cade prima: la pas mic
# n-are unde sa intre, iar textul ei e oricum in legenda. Schemele de referinta scriu si ele doar
# eticheta langa simbol.
_S_TREPTE = ((118.0, 46.0, True), (96.0, 40.0, True), (76.0, 34.0, False), (58.0, 28.0, False))


def _serpentina_spec(n_disp, lat_disp, h_disp):
    """Treapta cu care se aseaza `n_disp` dispozitive in `lat_disp` x `h_disp`, plus inaltimea
    rezultata. Aceeasi functie o folosesc si masuratorile, si desenul — altfel spatiul rezervat si
    cel ocupat ar putea sa nu coincida. Intoarce (h, per, randuri, pas_x, pas_y, cu_descriere, incape)."""
    _ultim = None
    for _px, _py, _desc in _S_TREPTE:
        per = max(1, int(lat_disp // _px))
        randuri = max(1, int(math.ceil(n_disp / float(per))))
        h = 16.0 + randuri * _py + 2 * _S_ZONA_PAD
        _ultim = (h, per, randuri, _px, _py, _desc, h <= h_disp)
        if h <= h_disp:
            return _ultim
    return _ultim


def _serpentina_h(n_disp, lat_disp, h_disp=1e9):
    """Inaltimea de care are nevoie o buclă, ca sa se poata rezerva spatiul INAINTE de a desena."""
    _s = _serpentina_spec(n_disp, lat_disp, h_disp)
    return _s[0], _s[1], _s[2]


def _serpentina(page, els, lmap, bucla, x0, y0, lat_disp, x_ecs=None, y_ecs=None, h_disp=1e9):
    """Un SINGUR fir care trece prin toate dispozitivele buclei, in zigzag.

    Asa arata schemele monobloc de referinta si asa e bucla adresabila in realitate: un cablu care
    intra intr-un dispozitiv si iese spre urmatorul, nu N cabluri individuale la centrala (aia e
    steaua de la efractie si video, corecta acolo). Randul 1 merge STANGA->DREAPTA, randul 2 in sens
    INVERS, si tot asa — de-aia firul nu se intoarce niciodata peste el insusi.

    `x_ecs`/`y_ecs`: punctul din care pleaca firul (iesirea de buclă a centralei). Intoarce
    (y_jos, ultimul_punct) — capatul de unde se poate inchide bucla inapoi in centrala."""
    _h, per, _r, _px, _py, _desc, _ok = _serpentina_spec(len(els), lat_disp, h_disp)
    spec = _CS_CABLE["e30"]
    # ZONA buclei: fundal + eticheta. Cu o singura buclă zona ramane una; cu mai multe, fiecare isi
    # are chenarul si numele ei, ca in exemplul cu „BUCLA 1 / BUCLA 2 / BUCLA 3".
    _zh = _h
    page.draw_rect(fitz.Rect(x0 - _S_ZONA_PAD, y0 - _S_ZONA_PAD,
                             x0 + lat_disp + _S_ZONA_PAD, y0 - _S_ZONA_PAD + _zh),
                   color=spec["col"], fill=_S_ZONA_FILL, width=0.5)
    _text(page, x0, y0 + 4.0, "BUCLA %d — %d dispozitive" % (bucla, len(els)),
          fs=7.5, bold=True, col=spec["col"])

    pct = []
    for i, el in enumerate(els):
        r, c = i // per, i % per
        if r % 2:                       # randul impar merge in sens INVERS (zigzag)
            c = per - 1 - c
        x = x0 + c * _px + 10.0
        y = y0 + 16.0 + r * _py + 12.0
        pct.append((x, y, el))

    # FIRUL: din centrala in primul dispozitiv, apoi din fiecare in urmatorul. Segmentele de trecere
    # intre randuri coboara pe verticala, la capatul randului — exact cotul din exemple.
    sh = page.new_shape()
    _cale = ([(x_ecs, y_ecs)] if x_ecs is not None else []) + [(x, y) for x, y, _ in pct]
    for i in range(len(_cale) - 1):
        (ax, ay), (bx, by) = _cale[i], _cale[i + 1]
        if abs(ay - by) < 0.5:                       # acelasi rand: drept
            sh.draw_line(fitz.Point(ax, ay), fitz.Point(bx, by))
        elif abs(ax - bx) < 0.5:
            # SCHIMBARE DE RAND: capatul randului si inceputul urmatorului sunt pe ACEEASI coloana
            # (asa se intoarce serpentina), deci o coborare dreapta ar trece fix peste eticheta si
            # peste descrierea dispozitivului. Firul iese lateral, coboara pe langa ele si revine.
            # spre STANGA, mereu: eticheta si descrierea se intind la DREAPTA simbolului (pana la
            # ~50 pt), deci un ocol spre dreapta le-ar taia oricum. La stanga, textul incepe abia
            # la x-8, iar dispozitivul dinainte e la cel putin un pas distanta.
            _off = -16.0
            for _a, _b in (((ax, ay), (ax + _off, ay)), ((ax + _off, ay), (ax + _off, by)),
                           ((ax + _off, by), (bx, by))):
                sh.draw_line(fitz.Point(*_a), fitz.Point(*_b))
        else:                            # intrarea din centrala: intai pe verticala, apoi orizontal
            sh.draw_line(fitz.Point(ax, ay), fitz.Point(ax, by))
            sh.draw_line(fitz.Point(ax, by), fitz.Point(bx, by))
    # `closePath=False`: implicit PyMuPDF INCHIDE calea, adica trage un segment de la ultimul
    # dispozitiv inapoi la primul — o diagonala peste toata zona buclei. Bucla e deschisa: pleaca
    # din centrala si se termina la ultimul dispozitiv.
    sh.finish(color=spec["col"], width=1.0, dashes=spec["dash"], closePath=False)
    sh.commit()          # fara `commit` shape-ul e finisat dar NU ajunge pe pagina

    for x, y, el in pct:
        _draw_cs(page, x, y, el.get("element_type") or "doza_cs", scale=0.62)
        _text(page, x - 8, y + 15.0, det_eticheta(el, lmap), fs=7.0, bold=True, col=spec["col"])
        if _desc:
            _text(page, x - 8, y + 23.0, _SCURT.get(el.get("element_type") or "", ""), fs=5.4,
                  col=(0.35, 0.35, 0.35))
    return y0 - _S_ZONA_PAD + _zh, (pct[-1][0], pct[-1][1]) if pct else None


def _coduri_circuite(elements):
    """Codul de circuit al fiecarui echipament de desfumare, din enrich, pe POZITIE — acelasi
    mecanism ca etichetele de pe planşa. Orice esec -> fara coduri (schema iese fara ele, nu crapa)."""
    try:
        import enrich_circuits as EC
        cc = EC.enrich_circuits(list(elements or []), {}, base_circuits=[])
    except Exception:
        return {}
    out = {}
    for c in cc:
        if c.get("type") != "dedicat" or c.get("_plan_x") is None:
            continue
        for el in (elements or []):
            try:
                if (abs(float(el.get("x") or 0) - float(c["_plan_x"])) < 0.01
                        and abs(float(el.get("y") or 0) - float(c["_plan_y"])) < 0.01):
                    out[el.get("id")] = str(c.get("id") or "")
                    break
            except (TypeError, ValueError):
                continue
    return out


def build_det_schema(elements, cartus_firma=None, cartus_proiect=None, plansa_nr=None):
    """Schema sistemului de detectie incendiu -> bytes PDF (o pagina), sau None daca proiectul n-are
    echipamente de incendiu (gate pe PREZENTA, ca la curenti slabi si la FV).

    ASEZAREA urmeaza schemele monobloc de referinta: ECS in STANGA, bucla ca SERPENTINA care pleaca
    din ea, fiecare buclă in zona ei delimitata; desfumarea ramane in STEA, jos, spre tabloul
    general — nu e pe buclă, are circuite proprii."""
    g = _det_elemente(elements)
    if not [e for e in g["toate"] if (e.get("element_type") or "") in _DET_TYPES]:
        return None                       # gate: fara echipamente -> fara schema
    if not g["bucla"] and not g["desfumare"]:
        return None                       # doar centrala plasata, fara nimic pe ramuri

    _coduri = _coduri_circuite(elements)
    grupuri = _grupuri(g, _coduri)        # DOAR desfumarea: bucla se deseneaza ca serpentina
    # LEGENDA: randurile planşei, fara randurile ei de cablu (acolo descriu alimentarea DESENATA pe
    # plan). Fiecare ramura isi declara singura cablul, ca legenda sa acopere exact ce e pe foaie.
    _rows = [r for r in build_legend_rows(g["toate"], "detectie_incendiu")
             if r.get("kind") != "cable"]
    for _k2 in (["e30"] if g["bucla"] else []) + [gr["kind"] for gr in grupuri]:
        _sp = _CS_CABLE[_k2]
        if not any(r.get("text") == _sp["nume"] for r in _rows):
            _rows.append({"kind": "cs_cable", "cable": _k2, "text": _sp["nume"]})

    W, H = _A3[0] * MMPT, _A3[1] * MMPT
    PAD = _PAD_MM * MMPT
    X0 = PAD + 12.0
    X_HUB = W - PAD - 12.0 - _HUB_W
    _leg_w, _leg_h = _legenda_dim(_rows)
    _leg2 = None
    Y_LEG = H - PAD - 12.0 - _leg_h
    _SUS = PAD + 62.0
    _JOS = Y_LEG - 20.0

    # ── cat spatiu ia SERPENTINA (se calculeaza INAINTE, ca desfumarea sa primeasca restul) ──
    _ord = det_ordine_bucla(g["toate"])
    _lmap = det_loop_map(g["toate"])
    _bucle = {}
    for _el in _ord:
        _bucle.setdefault(_lmap[_el["id"]][0], []).append(_el)
    X_ZONA = X0 + _S_ECS_W + 26.0
    _LAT_ZONA = (W - PAD - 12.0) - X_ZONA
    # BUGETUL pe inaltime: zonele de bucla iau cel mult doua treimi din banda utila, ca sa ramana
    # loc si desfumarii. Se imparte egal intre bucle — o buclă plina (127 de dispozitive) trebuie
    # sa se stranga singura pana incape, nu sa iasa de pe foaie.
    _H_ZONE = (_JOS - _SUS) * (1.0 if not g["desfumare"] else 0.62)
    _h_per_bucla = (_H_ZONE - _S_ZONA_GAP * max(0, len(_bucle) - 1)) / max(1, len(_bucle))
    _specs = {b: _serpentina_spec(len(v), _LAT_ZONA, _h_per_bucla) for b, v in _bucle.items()}
    _h_serp = sum(x[0] for x in _specs.values())
    _h_serp += _S_ZONA_GAP * max(0, len(_bucle) - 1)
    _serp_incape = all(x[6] for x in _specs.values())
    # inaltimea blocului de comenzi intra in buget INAINTE de asezarea desfumarii
    _n_cmd = len([1 for gate, _ in _ECS_COMENZI if gate is None or g["desfumare"]])
    _h_cmd = (_n_cmd - 1) * _CMD_PAS + 16.0 if g["bucla"] else 0.0

    # ── DESFUMAREA: aceleasi masuratori ca la curenti slabi, dar pe inaltimea RAMASA ─────────
    m = None
    if grupuri:
        _rest = max(60.0, (_JOS - _SUS) - _h_serp - 26.0)
        m = _masoara(g, grupuri=grupuri, plan_type="detectie_incendiu", cutie_sus="teg",
                     rows=_rows, benzi_fixe=True, buget_h=_rest)
        _leg2 = m["leg2"]
        if _leg2:
            _leg_h, _leg_w = _leg2["h"], _leg2["w"]
            Y_LEG = H - PAD - 12.0 - _leg_h
            _JOS = Y_LEG - 20.0

    doc = fitz.open()
    page = doc.new_page(width=W, height=H)
    page.draw_rect(fitz.Rect(PAD, PAD, W - PAD, H - PAD), color=_NEGRU, width=1.2)
    _text(page, W / 2.0, PAD + 26, TITLU, fs=13.0, bold=True, anchor="center")
    _p = [x for x in (("detecție și semnalizare a incendiului" if g["bucla"] else None),
                      ("evacuare a fumului" if g["desfumare"] else None)) if x]
    _text(page, W / 2.0, PAD + 38, "%s — schemă funcțională" % (" și ".join(_p) or "detecție"),
          fs=7.5, col=(0.35, 0.35, 0.35), anchor="center")

    # ── LEGENDA + NOTA, jos-stanga ───────────────────────────────────────────────────────────
    if _leg2:
        _draw_legend(page, X0, Y_LEG, _leg2["a"])
        _draw_legend(page, X0 + _leg2["w1"] + 14.0, Y_LEG, _leg2["b"])
    else:
        _draw_legend(page, X0, Y_LEG, _rows)
    _n = []
    if g["bucla"]:
        _n.append("Bucla adresabilă este un singur circuit care trece prin toate dispozitivele, în "
                  "ordinea numerotării, executat cu cablu JEH(St)H E30 2x2x0,8 pozat separat de "
                  "restul instalațiilor; centrala are acumulator de rezervă.")
    if g["desfumare"]:
        _n.append("Echipamentele de desfumare se alimentează prin circuite dedicate din tabloul "
                  "electric general.")
    _text(page, X0, Y_LEG - 8.0,
          " ".join(_n) + " Numerele de pe schemă sunt cele de pe planșa de detecție incendiu.",
          fs=6.2, col=(0.35, 0.35, 0.35))

    # ── ECS: in STANGA (asezarea din schemele de referinta) ─────────────────────────────────
    r_c = None
    if g["bucla"]:
        _n_disp = DE.det_dispozitive(g["toate"])
        _n_bucle, _acopera = DE.det_bucle(_n_disp)
        c_lin = ["%d buclă adresabilă" % _n_bucle if _n_bucle == 1
                 else "%d bucle adresabile" % _n_bucle,
                 "%d dispozitiv adresabil" % _n_disp if _n_disp == 1
                 else "%d dispozitive adresabile" % _n_disp,
                 "acumulator de rezervă"]
        if not _acopera:
            c_lin.append("peste capacitate — centrale în rețea")
        c_lin = _incape_in_cutie(c_lin, _S_ECS_W - 10.0)
        c_h = 24.0 + 10.0 * len(c_lin)
        y_c = _SUS + 14.0 + max(0.0, (_h_serp - c_h) / 2.0)
        r_c = fitz.Rect(X0, y_c, X0 + _S_ECS_W, y_c + c_h)
        _et_c = (g["centrala"][0][1] if g["centrala"] else "CSI") or "CSI"
        _bloc(page, r_c, "%s — ECS" % _et_c, c_lin, col=DE._DET_FAMILIE)

    # ── AVERTISMENTUL, UNUL SINGUR, deasupra zonelor ────────────────────────────────────────
    # Doua note separate insemnau si doua locuri de asezat: cea a desfumarii ajungea mereu peste
    # laneurile stelei, care urca deasupra primului rand. Sus, deasupra zonelor, e singura banda
    # in care nu deseneaza nimeni — si oricum cititorului ii trebuie UN avertisment, nu doua.
    _av = [x for x in (("buclele" if not _serp_incape else None),
                       ("desfumarea" if (m is not None and not m["incape"]) else None)) if x]
    if _av:
        _text(page, X_ZONA, _SUS + 8.0,
              "ATENȚIE: %s nu încap pe o planșă A3 — se recomandă planșe separate."
              % (" și ".join(_av)), fs=6.6, col=(0.80, 0.15, 0.15))

    # ── SERPENTINELE: cate una per buclă, sub-una-alta ──────────────────────────────────────
    _y = _SUS + 14.0
    for _b in sorted(_bucle):
        _y = _serpentina(page, _bucle[_b], _lmap, _b, X_ZONA, _y + _S_ZONA_PAD, _LAT_ZONA,
                         x_ecs=(r_c.x1 if r_c is not None else None),
                         y_ecs=((r_c.y0 + r_c.y1) / 2.0 if r_c is not None else None),
                         h_disp=_h_per_bucla)[0]
        _y += _S_ZONA_GAP

    # ── COMENZILE DIN ECS: banda libera de sub zonele de bucla ──────────────────────────────
    # Aici, nu langa ECS: la stanga n-are loc, iar la dreapta ar fi intrat peste zona buclei.
    _y_cmd = _SUS + 14.0 + _h_serp + 14.0
    r_t = None
    if m is not None and m["sus"]:
        _LAT_DISP = X_HUB - _gap_hub() - X0
        _top = _SUS + 14.0 + _h_serp + 34.0 + _h_cmd
        # centrata in spatiul RAMAS sub bucle: lipita de subsol lasa o prapastie alba la mijloc
        Y_JOS = _top + max(0.0, ((_JOS - _top) - m["h_sus"]) / 2.0)
        _fasc = _deseneaza_benzi(page, m, X0, Y_JOS, Y_JOS, _LAT_DISP)[0]
        _alim = [(el, et) for el, et in g["desfumare"] if det_are_circuit(el)]
        t_lin = ["%s%s%s" % (_coduri.get(el.get("id")) or et, _SEP,
                             _SCURT.get(el.get("element_type"), ""))
                 for el, et in _alim] or ["fără echipamente alimentate"]
        t_lin = _incape_in_cutie(t_lin, _HUB_W - 12.0)
        _n_t = sum(len(fa["pct"]) for fa in _fasc)
        t_h = max(24.0 + 10.0 * len(t_lin), 20.0 + _n_t * 3.2)
        y_t = min(_JOS - t_h, max(Y_JOS + m["h_sus"] / 2.0 - t_h / 2.0,
                                  _SUS + 14.0 + _h_serp + 26.0))
        r_t = fitz.Rect(X_HUB, y_t, X_HUB + _HUB_W, y_t + t_h)
        _bloc(page, r_t, "TEG — TABLOU ELECTRIC GENERAL", t_lin, col=DE._PRIZA_COLOR)
        _leaga_cutie(page, r_t, _fasc, X_HUB, _n_t)
        if r_c is not None:
            _comenzi_ecs(page, r_c, _y_cmd, X_HUB + _HUB_W / 2.0, r_t.y0, cu_desfumare=True)

    if r_c is not None and r_t is None:
        # fara desfumare raman cele PATRU neconditionate — centrala tot comanda tabloul si tot
        # isi monitorizeaza sursele
        _comenzi_ecs(page, r_c, _y_cmd, cu_desfumare=False)

    # ── ALIMENTAREA 230 V a centralei ────────────────────────────────────────────────────────
    if r_c is not None:
        _text(page, r_c.x0, r_c.y0 - 8.0, "circuit dedicat 230 V", fs=6.4, col=(0.35, 0.35, 0.35))
        sh = page.new_shape()
        sh.draw_line(fitz.Point(r_c.x0 + _S_ECS_W / 2.0, r_c.y0 - 6.0),
                     fitz.Point(r_c.x0 + _S_ECS_W / 2.0, r_c.y0))
        sh.finish(color=_NEGRU, width=1.2)
        sh.commit()

    raw = doc.tobytes(deflate=True)
    doc.close()
    return _cartus_final(raw, W, H, cartus_firma, cartus_proiect, plansa_nr, TITLU)
