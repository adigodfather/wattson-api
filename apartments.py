# -*- coding: utf-8 -*-
"""APARTAMENTUL ca entitate de grupare — conturul desenat si apartenenta la el.

Pana aici sistemul lucra pe CAMERA si grupa pe NIVEL. Nimic din `plan_elements` nu exprima „aceste
sase camere sunt apartamentul P1.5", iar la bloc circuitele se calculeaza per apartament, nu per
etaj. E aceeasi clasa de schimbare ca „gruparea e pe NIVEL, nu pe tablou" (P0): se schimba CHEIA DE
GRUPARE, nu o regula.

DE CE CONTEAZA ATAT: `compute_circuits` face bin-packing peste TOT ce primeste, fara nicio notiune
de apartament — exact cum n-avea notiune de etaj. Doua apartamente intrate in acelasi apel ies pe
ACELEASI circuite. Deci apartamentul trebuie sa fie un APEL SEPARAT, cum e azi fiecare nivel.

DECIZIA LUI DAN (20 sept 2026): conturul se deseneaza MANUAL, pe FIECARE NIVEL care are
apartamente. Nu o data, proiectat in sus. Motivul e masurat pe planşele lui: parterul are 4
apartamente cu alt layout decat etajele 1-2 (noua fiecare), iar E3 retras are cinci cu al treilea
layout — un singur set de contururi proiectat in sus n-ar putea descrie toate trei. In plus,
bbox-urile Vision sunt normalizate PER NIVEL, deci proiectia ar presupune o aliniere pe care
modelul de date n-o garanteaza. P4 copiaza CONTINUTUL intre apartamente identice, nu conturul —
si asta il face mai sigur: compara doua contururi care exista amandoua, in loc sa inventeze unul.
"""
import re

CONTUR = "contur_apartament"        # element_type: poligon, ca `ground_electrode_path`

# Eticheta de apartament, conventia de pe planşele lui Dan:
#   parter  -> „P1".."P4"      (marcaj „Ap P1"),   tablou „TE-AP 1"
#   etaj 1  -> „P1_1".."P1_9"  (marcaj „Ap P1_5"), tablou „TE-AP 1.5"
# Cratima si punctul difera intre marcajul de pe plan si numele tabloului chiar in documentele lui —
# pastram ambele forme exact cum le scrie el, fiecare acolo unde apare.
_RX_ET = re.compile(r"^P(\d+)_(\d+)$")
_RX_P = re.compile(r"^P(\d+)$")


def _pts(el):
    """Punctele conturului (x, y) in PUNCTE PDF. Forma e `cable_path`, ca la priza de pamant si la
    lantul FV — un element nou n-are nevoie de o a doua conventie de poligon."""
    cp = (el or {}).get("cable_path")
    if not isinstance(cp, (list, tuple)) or len(cp) < 3:
        return None                              # sub 3 varfuri nu inchide o suprafata
    out = []
    for p in cp:
        try:
            out.append((float(p[0]), float(p[1])))
        except (TypeError, ValueError, IndexError):
            return None
    return out


def _in_poligon(x, y, pts):
    """Punct in poligon, prin numararea intersectiilor (ray casting spre dreapta).

    NU dreptunghi: apartamentele sunt in L, in U, cu balcon iesit in afara — un bbox ar inghiti
    camere ale vecinului. Poligonul e desenat de inginer tocmai ca sa fie exact."""
    if not pts:
        return False
    inside = False
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xin = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < xin:
                inside = not inside
    return inside


def _aria(pts):
    """Aria poligonului (formula lui Gauss), in puncte^2. Serveste la departajare cand contururile
    se suprapun: castiga cel mai MIC, adica cel mai specific — aceeasi regula ca la `_room_of_point`
    pentru bbox-uri imbricate."""
    s = 0.0
    n = len(pts or [])
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def eticheta_auto(floor_idx, ordine):
    """Eticheta propusa la creare: nivelul + ordinea. Parterul n-are prefix de etaj, ca la Dan.

    AUTOMATA, dar EDITABILA — se scrie in `label`, campul care exista deja. Numerotarea automata e
    singura care ramane consecventa cand inginerul sterge al treilea apartament din cinci; scrisul
    de mana ar lasa o gaura pe care n-o vede nimeni pana la schema."""
    if floor_idx <= 0:
        return "P%d" % ordine
    return "P%d_%d" % (floor_idx, ordine)


def panel_apartament(eticheta):
    """Numele TABLOULUI apartamentului, din eticheta lui: „P1_5" -> „TE-AP 1.5"; „P3" -> „TE-AP 3".
    Necunoscut -> „TE-AP <eticheta>", ca sa ramana lizibil in loc sa dispara."""
    e = str(eticheta or "").strip()
    m = _RX_ET.match(e)
    if m:
        return "TE-AP %s.%s" % (m.group(1), m.group(2))
    m = _RX_P.match(e)
    if m:
        return "TE-AP %s" % m.group(1)
    return "TE-AP %s" % e if e else "TE-AP"


def eticheta_din_panel(panel):
    """„TE-AP 1.5" -> „P1_5"; „TE-AP 3" -> „P3". None daca nu-i tablou de apartament.
    Drumul invers al lui `panel_apartament`, ca descrierea circuitului sa poata numi APARTAMENTUL
    in loc de nivel: noua circuite „Iluminat etaj" pe acelasi etaj nu spun nimic."""
    e = str(panel or "").strip()
    if not e.upper().startswith("TE-AP"):
        return None
    rest = e[5:].strip()
    if not rest:
        return None
    m = re.match(r"^(\d+)\.(\d+)$", rest)
    if m:
        return "P%s_%s" % (m.group(1), m.group(2))
    m = re.match(r"^(\d+)$", rest)
    return ("P%s" % m.group(1)) if m else rest


def conturi_nivel(plan_elements, floor_key, floor_canonic):
    """Contururile de apartament de pe UN nivel, in ordine determinista (de sus in jos, apoi de la
    stanga la dreapta — ordinea in care le-ar numerota un om). Fiecare: {eticheta, pts, aria, el}.

    `floor_canonic` se primeste ca functie ca sa nu duplicam axa aici: apartenenta la nivel trece
    prin ACEEASI canonizare ca restul codului."""
    br = []
    for el in (plan_elements or []):
        if ((el or {}).get("element_type") or "") != CONTUR:
            continue
        if floor_canonic((el or {}).get("floor")) != floor_key:
            continue
        pts = _pts(el)
        if not pts:
            continue                             # poligon malformat -> ignorat, nu o exceptie
        br.append({"pts": pts, "aria": _aria(pts), "el": el,
                   "_y": min(p[1] for p in pts), "_x": min(p[0] for p in pts)})
    br.sort(key=lambda b: (round(b["_y"] / 40.0), b["_x"]))   # randuri de ~40 pt, apoi stanga->dreapta
    for i, b in enumerate(br, start=1):
        lbl = str((b["el"].get("label") or "")).strip()
        b["eticheta"] = lbl or eticheta_auto(_idx_din(floor_key, floor_canonic), i)
    return br


def _idx_din(floor_key, floor_canonic):
    """Indexul de nivel, doar pentru eticheta automata. Import tarziu ca sa nu legam modulul de
    axa la incarcare (si ca sa ramana testabil izolat)."""
    try:
        import floors as _fl
        return max(0, _fl.floor_index(floor_key))
    except Exception:
        return 0


def apartament_al_punctului(x, y, conturi):
    """Apartamentul care CONTINE punctul, sau None. Suprapunere -> cel mai mic contur."""
    hits = [c for c in (conturi or []) if _in_poligon(x, y, c["pts"])]
    if not hits:
        return None
    return min(hits, key=lambda c: c["aria"])["eticheta"]


def apartament_al_elementului(el, conturi):
    """Apartamentul unui element de plan: cel al carui contur ii contine PUNCTUL. None altfel.

    UN SINGUR criteriu, si nu din lene. Prima varianta avea si o plasa pe CAMERA — un element cazut
    cu un punct in afara liniei ar fi fost recuperat prin camera lui. La bloc regula aia e NESIGURA:
    numele de camera nu sunt unice pe nivel („Dormitor" apare de 29 de ori pe planşele lui Dan, cate
    unul in fiecare apartament), deci „camera Dormitor apartine apartamentului X" n-are inteles.
    O plasa care ghiceste intre noua apartamente ar muta un circuit la vecin — tacut si plauzibil,
    exact defectul pe care incercam sa-l evitam.

    Elementele ramase in afara oricarui contur cad in grupul COMUN al nivelului (corect pentru casa
    scarii si holul de palier). Ca sa nu fie tacut cand NU e corect, `orfani` le numara —
    vezi `elemente_orfane`."""
    try:
        return apartament_al_punctului(float(el["x"]), float(el["y"]), conturi)
    except (TypeError, ValueError, KeyError):
        return None


def elemente_orfane(els, conturi):
    """Cate elemente de pe un nivel CU contururi n-au nimerit in niciunul.

    Zero e normal pe un nivel fara apartamente. Pe unul cu apartamente, un numar mai mare decat
    cele cateva elemente comune (casa scarii, holul) inseamna ca un contur e prost desenat — si
    atunci circuitele au plecat la tabloul de nivel in loc sa plece la TE-AP. Numarul e SEMNALUL;
    fara el, greseala ar arata pe schema exact ca o alegere."""
    if not conturi:
        return 0
    return sum(1 for e in (els or []) if apartament_al_elementului(e, conturi) is None)


def camere_ale_apartamentelor(rooms, conturi, W, H):
    """{nume camera (lowercase) -> eticheta apartament}. O camera apartine apartamentului al carui
    contur ii contine CENTRUL bbox-ului.

    Bbox-urile Vision sunt fractii 0..1 normalizate PER NIVEL, deci se inmultesc cu (W, H) ale
    planşei nivelului — acelasi calcul ca `_room_of_point`. Camerele COMUNE (casa scarii, holul de
    palier) nu cad in niciun contur si raman pe nivel, ca azi."""
    out = {}
    for r in (rooms or []):
        bb = (r or {}).get("bbox") or {}
        try:
            cx = (float(bb["x"]) + float(bb["w"]) / 2.0) * W
            cy = (float(bb["y"]) + float(bb["h"]) / 2.0) * H
        except (TypeError, ValueError, KeyError):
            continue
        ap = apartament_al_punctului(cx, cy, conturi)
        if ap:
            out[str((r or {}).get("name") or "").strip().lower()] = ap
    return out
