# -*- coding: utf-8 -*-
"""SCHEMA ELECTRICA DE DISTRIBUTIE: arborele tuturor tablourilor, pe o planşa.

DATELE NU SE RECALCULEAZA. Pi, Pa, Ia, ku, parintele si fazele vin din `panels.panel_graph` —
aceeasi functie care le da memoriului, BOM-ului si schemelor de tablou. Protectia si cablul vin din
circuitul `sub_tablou` care alimenteaza tabloul, exact ca in `schema_payloads._sarcina`. Daca ar fi
recalculate aici, planşa ar putea afirma alte puteri decat memoriul care o insoteste.

CONVENTIA APARTAMENTELOR, masurata pe IE.19 a lui Dan (nu presupusa):
    FDCP  ->  TE-AP 3.1-3.5        FDCP  ->  TE-AP 1-4
    FDCP  ->  TE-AP 2.1-2.9        FDCP  ->  TE-SP 1,2
    FDCP  ->  TE-AP 1.1-1.9
O CUTIE per firida, etichetata cu INTERVALUL apartamentelor pe care le hraneste. Nici pe tipuri
(AP-1 / AP-2 nu apar nicaieri pe IE.19), nici cate una pentru fiecare din cele 27 — arborele ar fi
devenit o perie de nedesenat. Separatorul e al lui: interval cu liniuta de la trei in sus („1.1-1.9",
„1-4"), enumerare cu virgula la doua („1,2").

CE NU INTRA: ramura de curenti slabi (FDCS, DDCS, DTC-AP). La Dan sta pe aceeasi planşa fiindca
si-a desenat-o de mana; la noi curentii slabi au deja planşa lor de sistem, iar a o repeta aici ar
face doua desene care pot diverge.

ASEZAREA difera de a lui intentionat. El are BMPT la mijloc si ramuri in AMANDOUA directiile, ca
sa umple foaia — o alegere care se poate face doar cu mana, uitandu-te la rezultat. Noi mergem pe
coloane de adancime, stanga->dreapta, de la sursa spre consumatori: se citeste la fel, si tine si
cand blocul are alt numar de firide.
"""
import re

import fitz

import panels as _pn
import protectii as _prot

MMPT = 72.0 / 25.4

try:
    from cartus_swap import _txt as _ascii
except Exception:                                  # pragma: no cover
    def _ascii(s):
        return str(s or "")

_A3 = (420.0, 297.0)
_PAD_MM = 6.0
_CARTUS_W_MM, _CARTUS_H_MM = 182.5, 42.5

_NEGRU = (0.10, 0.10, 0.10)
_GRI = (0.55, 0.55, 0.55)
_GRI_DES = (0.78, 0.78, 0.78)

TITLU = "SCHEMA ELECTRICĂ DE DISTRIBUȚIE"

# Familiile care se COMASEAZA intr-o singura cutie sub parintele lor. Doar cele care vin in serii
# mari si identice: un bloc are 27 de apartamente si 2 spatii, dar un singur TCC.
_COMASATE = ("TE-AP", "TE-SP")

_DESCRIERI = {
    "BMPT": "Bloc de măsură și protecție",
    "TEGD": "Tablou general de distribuție",
    "TGD": "Tablou general de distribuție",
    "TEG": "Tablou electric general",
    "TES": "Tablou electric secundar",
    "TE-CT": "Tablou centrală termică",
    "FDCP": "Firidă de distribuție și contorizare de palier",
    "TE-AP": "Tablou electric de apartament",
    "TE-SP": "Tablou electric spațiu comercial",
    "TCC": "Tablou consumatori comuni",
    "TECV": "Tablou consumatori vitali",
    "TEP": "Tablou electric cameră pompe",
}


def _text(page, x, y, s, fs=7.0, bold=False, col=_NEGRU, anchor="left"):
    t = _ascii(s)
    f = "hebo" if bold else "helv"
    w = fitz.get_text_length(t, fontname=f, fontsize=fs)
    if anchor == "center":
        x -= w / 2.0
    elif anchor == "right":
        x -= w
    page.insert_text((x, y), t, fontname=f, fontsize=fs, color=col)
    return w


def _txt(page, x, y, s, **kw):
    return _text(page, x * MMPT, y * MMPT, s, **kw)


def _linie(page, x0, y0, x1, y1, col=_NEGRU, w=0.8):
    page.draw_line(fitz.Point(x0 * MMPT, y0 * MMPT), fitz.Point(x1 * MMPT, y1 * MMPT),
                   color=col, width=w)


def _drept(page, x0, y0, x1, y1, col=_NEGRU, w=0.8, fill=None):
    page.draw_rect(fitz.Rect(x0 * MMPT, y0 * MMPT, x1 * MMPT, y1 * MMPT),
                   color=col, width=w, fill=fill)


# ── ETICHETA DE INTERVAL ──────────────────────────────────────────────────────────────────────
def _sufix(nume, fam):
    s = str(nume or "").strip()
    return s[len(fam):].strip() if s.upper().startswith(fam.upper()) else s


def _eticheta_serie(nume_tablouri, fam):
    """„TE-AP 1.1-1.9" / „TE-SP 1,2" / „TE-AP 1-4" — conventia masurata pe IE.19.

    Interval cu liniuta de la TREI in sus si numai daca ultimul numar e contiguu; la doua, virgula
    (asa scrie el „TE-SP 1,2", desi 1 si 2 sunt contigue — un interval de doi n-ar spune nimic in
    plus). Orice alta forma se enumera, fiindca un interval peste o gaura ar minti."""
    suf = [_sufix(n, fam) for n in nume_tablouri]
    if len(suf) == 1:
        return "%s %s" % (fam, suf[0])
    if len(suf) == 2:
        return "%s %s,%s" % (fam, suf[0], suf[1])
    parti = [re.match(r"^(.*?)(\d+)$", s) for s in suf]
    if all(parti):
        capete = {m.group(1) for m in parti}
        nums = sorted(int(m.group(2)) for m in parti)
        if len(capete) == 1 and nums == list(range(nums[0], nums[-1] + 1)):
            cap = capete.pop()
            return "%s %s%d-%s%d" % (fam, cap, nums[0], cap, nums[-1])
    return "%s %s" % (fam, ",".join(suf))


# ── ARBORELE ──────────────────────────────────────────────────────────────────────────────────
def _feed(circuits, nume):
    return next((c for c in circuits if str(c.get("feeds_panel") or "") == nume), {}) or {}


def construieste_arbore(circuits):
    """[{nume, fam, copii, pi_kw, pa_kw, ia_a, ku, protectie, cablu, membri}] — radacinile.

    `membri` = tablourile REALE din spatele unei cutii comasate (o cutie „TE-AP 1.1-1.9" sta pentru
    noua tablouri). Se pastreaza ca sa se poata verifica ce-a intrat unde, nu se deseneaza."""
    circuits = [c for c in (circuits or []) if isinstance(c, dict)]
    g = _pn.panel_graph(circuits)
    if not g:
        return []

    def nod(nume, membri=None, eticheta=None):
        n = g.get(nume) or {}
        f = _feed(circuits, nume)
        # TRIFAZAT se citeste INTAI de pe coloana care alimenteaza tabloul, nu doar din fazele lui.
        # Un TCC cu un singur circuit de iluminat monofazat are `phases=1`, dar coloana lui de 63 A
        # vine trifazata — si aici se tipareste protectia COLOANEI, nu a plecarilor. Fara asta,
        # planşa scria „1P+N 63A" pe un cablu cu cinci conductoare.
        tri = ("3P" in str(f.get("breaker_type") or "").upper()
               or int(n.get("phases") or 1) >= 3)
        # Cutia comasata poarta SUMA membrilor: altfel planşa ar arata puterea unui apartament
        # acolo unde scrie ca sunt noua.
        mm = membri or [nume]
        pi = sum(float((g.get(x) or {}).get("pi_w") or 0) for x in mm)
        pa = sum(float((g.get(x) or {}).get("pa_w") or 0) for x in mm)
        ia = sum(float((g.get(x) or {}).get("ia_a") or 0) for x in mm)
        return {"nume": eticheta or nume, "fam": _pn.panel_family(nume) or "",
                "copii": [], "membri": mm,
                "pi_kw": round(pi / 1000.0, 2), "pa_kw": round(pa / 1000.0, 2),
                "ia_a": round(ia, 1), "ku": float(n.get("ku") or _pn.KU_IMPLICIT),
                "protectie": _prot.eticheta(int(f.get("breaker_a") or 0) or (40 if tri else 25),
                                            tri=tri, este_tablou=True) if f else "",
                "cablu": str(f.get("cable_type") or "")}

    def copii_de(nume):
        bruti = [x for x in (g.get(nume) or {}).get("children") or []]
        out, serii = [], {}
        for c in bruti:
            fam = _pn.panel_family(c) or ""
            if fam in _COMASATE:
                serii.setdefault(fam, []).append(c)
            else:
                k = nod(c)
                k["copii"] = copii_de(c)
                out.append(k)
        for fam in sorted(serii):
            mem = sorted(serii[fam])
            k = nod(mem[0], membri=mem, eticheta=_eticheta_serie(mem, fam))
            # Protectia si cablul sunt ale UNEI coloane: la o serie de tablouri identice sunt
            # aceleasi, iar cand nu sunt, se scrie ca variaza in loc sa se aleaga una la intamplare.
            cbl = {str(_feed(circuits, x).get("cable_type") or "") for x in mem}
            k["cablu"] = cbl.pop() if len(cbl) == 1 else "variabil"
            k["copii"] = []
            out.append(k)
        return out

    radacini = [n for n, v in g.items() if not v.get("parent")]
    arb = []
    for r in sorted(radacini):
        k = nod(r)
        k["copii"] = copii_de(r)
        arb.append(k)
    return arb


# ── ASEZAREA ──────────────────────────────────────────────────────────────────────────────────
_BOX_W, _BOX_H = 34.0, 15.0
_GAP_X, _GAP_Y = 30.0, 6.0


def _aseaza(noduri, x, y, out, col=0):
    """Coloane de adancime, stanga->dreapta. Intoarce inaltimea ocupata."""
    h = 0.0
    for n in noduri:
        y0 = y + h
        if n["copii"]:
            hc = _aseaza(n["copii"], x + _BOX_W + _GAP_X, y0, out, col + 1)
        else:
            hc = _BOX_H + _GAP_Y
        # cutia se CENTREAZA pe blocul copiilor ei, ca liniile sa plece din mijloc
        out.append(dict(n, _x=x, _y=y0 + (hc - _BOX_H - _GAP_Y) / 2.0, _col=col))
        h += hc
    return h


def masoara(arbore):
    poz = []
    h = _aseaza(arbore, 0.0, 0.0, poz)
    w = max([p["_x"] + _BOX_W for p in poz] or [0.0])
    return {"poz": poz, "w": w, "h": max(h - _GAP_Y, 0.0)}


# ── DESENUL ───────────────────────────────────────────────────────────────────────────────────
def _cutie(page, p, sx, sy, fs):
    x0, y0 = p["_x"], p["_y"]
    x1, y1 = x0 + _BOX_W, y0 + _BOX_H
    _drept(page, x0, y0, x1, y1, col=_NEGRU, w=1.0, fill=(0.975, 0.975, 0.985))
    _txt(page, (x0 + x1) / 2.0, y0 + 4.6, p["nume"], fs=fs + 0.8, bold=True, anchor="center")
    _linie(page, x0, y0 + 6.2, x1, y0 + 6.2, col=_GRI_DES, w=0.5)
    _txt(page, x0 + 1.6, y0 + 9.6, "Pi %.2f kW" % p["pi_kw"], fs=fs - 0.6, col=(0.25, 0.25, 0.25))
    _txt(page, x0 + 1.6, y0 + 12.6, "Pa %.2f kW" % p["pa_kw"], fs=fs - 0.6, col=(0.25, 0.25, 0.25))
    _txt(page, x1 - 1.6, y0 + 9.6, "ku %.2f" % p["ku"], fs=fs - 0.6, anchor="right",
         col=(0.42, 0.42, 0.42))
    _txt(page, x1 - 1.6, y0 + 12.6, "Ia %.1f A" % p["ia_a"], fs=fs - 0.6, anchor="right",
         col=(0.25, 0.25, 0.25))


def build_schema_distributie(circuits, cartus_firma=None, cartus_proiect=None, plansa_nr=None):
    """Schema de distributie -> bytes PDF (o pagina A3), sau None daca nu exista arbore de desenat.

    Gate pe PREZENTA, ca peste tot: fara tablouri in circuite nu se naste planşa."""
    arb = construieste_arbore(circuits)
    if not arb or sum(len(a["copii"]) for a in arb) == 0:
        return None                     # un singur tablou nu e o schema de distributie

    m = masoara(arb)
    W, H = _A3[0] * MMPT, _A3[1] * MMPT
    doc = fitz.open()
    page = doc.new_page(width=W, height=H)
    PAD = _PAD_MM * MMPT
    page.draw_rect(fitz.Rect(PAD, PAD, W - PAD, H - PAD), color=_NEGRU, width=1.2)
    _text(page, W / 2.0, PAD + 26, TITLU, fs=13.0, bold=True, anchor="center")

    # Zona utila: sub titlu, deasupra legendei. Cartusul sta dreapta-jos, deci legenda merge
    # stanga-jos — acelasi aranjament ca la schema de curenti slabi.
    X_MIN, X_MAX = _PAD_MM + 8.0, _A3[0] - _PAD_MM - 8.0
    Y_MIN, Y_MAX = 34.0, _A3[1] - _PAD_MM - _CARTUS_H_MM - 10.0
    lat, inalt = X_MAX - X_MIN, Y_MAX - Y_MIN
    # Scara: se micsoreaza pana intra, dar nu sub pragul la care textul devine ilizibil. Sub el se
    # scrie pe planşa ca arborele depaseste formatul — nu se lasa niciodata suprapunere tacuta,
    # aceeasi regula ca la schema de curenti slabi.
    s = min(1.0, lat / max(m["w"], 1.0), inalt / max(m["h"], 1.0))
    incape = s >= 0.62
    s = max(s, 0.62)
    fs = 7.0 * (1.0 if s > 0.85 else 0.88)
    dx = X_MIN + max(0.0, (lat - m["w"] * s) / 2.0)
    dy = Y_MIN + max(0.0, (inalt - m["h"] * s) / 2.0)

    poz = {}
    for p in m["poz"]:
        q = dict(p, _x=dx + p["_x"] * s, _y=dy + p["_y"] * s)
        poz[p["nume"]] = q

    def desen(noduri):
        for n in noduri:
            p = poz[n["nume"]]
            _cutie(page, p, s, s, fs)
            for c in n["copii"]:
                q = poz[c["nume"]]
                xa, ya = p["_x"] + _BOX_W, p["_y"] + _BOX_H / 2.0
                xb, yb = q["_x"], q["_y"] + _BOX_H / 2.0
                xm = (xa + xb) / 2.0
                _linie(page, xa, ya, xm, ya, col=_NEGRU, w=0.9)
                _linie(page, xm, ya, xm, yb, col=_NEGRU, w=0.9)
                _linie(page, xm, yb, xb, yb, col=_NEGRU, w=0.9)
                # Eticheta coloanei: protectia DEASUPRA segmentului, cablul DEDESUBT, amandoua
                # terminate la marginea din stanga a cutiei-copil. Pe un singur rand, lipit de
                # mijloc, textul intra PESTE cutia urmatoare si se taie — masurat la prima rulare.
                # Daca protectia tot nu incape in golul dintre coloane, se renunta la capacitatea
                # de rupere: e informatia cel mai putin purtatoare de pe o schema de distributie.
                # GARDA: nicio eticheta nu are voie sa treaca peste linia verticala de la `xm`.
                # Se incearca, in ordine: textul intreg · fara capacitatea de rupere (informatia
                # cel mai putin purtatoare de pe o distributie) · font mai mic. Prima varianta
                # verifica doar protectia si doar o data, si atunci cablul lung tot trecea peste.
                _gol = (xb - xm - 1.5) * MMPT

                def _incape(txt, f):
                    return fitz.get_text_length(_ascii(txt), fontname="helv", fontsize=f) <= _gol

                for _s, _dy in ((c.get("protectie") or "", -1.6), (c.get("cablu") or "", 3.4)):
                    if not _s:
                        continue
                    f = fs - 1.4
                    if not _incape(_s, f) and len(_s.split()) > 2:
                        _s = " ".join(_s.split()[:-1])
                    while not _incape(_s, f) and f > 3.6:
                        f -= 0.3
                    _txt(page, xb - 1.0, yb + _dy, _s, fs=f, anchor="right",
                         col=(0.30, 0.30, 0.30))
            desen(n["copii"])

    desen(arb)

    # ── legenda: doar abrevierile CHIAR folosite ──
    fams = []
    for p in m["poz"]:
        f = p["fam"]
        if f and f in _DESCRIERI and f not in fams:
            fams.append(f)
    YL = _A3[1] - _PAD_MM - 10.0 - 4.2 * len(fams)
    _txt(page, X_MIN, YL - 4.0, "LEGENDĂ", fs=7.0, bold=True)
    for i, f in enumerate(fams):
        _txt(page, X_MIN, YL + i * 4.2, "%-7s %s" % (f, _DESCRIERI[f]), fs=6.2,
             col=(0.25, 0.25, 0.25))

    if not incape:
        _txt(page, _A3[0] / 2.0, Y_MAX + 6.0,
             "ATENȚIE: arborele depășește ce încape lizibil pe o planșă A3 — se recomandă "
             "împărțirea pe două planșe.", fs=7.5, bold=True, anchor="center", col=(0.70, 0.15, 0.10))

    raw = doc.tobytes(deflate=True)
    doc.close()
    from schema_cs import _cartus_final
    return _cartus_final(raw, W, H, cartus_firma, cartus_proiect, plansa_nr, TITLU)
