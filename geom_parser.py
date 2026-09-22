# -*- coding: utf-8 -*-
"""Citirea desenului direct din content stream, fara `page.get_drawings()`.

DE CE. `get_drawings()` materializeaza FIECARE primitiva ca dict Python cu obiecte Point/Rect:
masurat, ~1,85 KB de RAM bucata. Un plan de bloc de rola are intre 138 000 si 925 000 — la 925 000
varful a fost 1726 MB pe o instanta de 512, iar instanta a murit luand cu ea toti utilizatorii.
Parserul asta citeste aceleasi trasee direct din stream: 59 MB si 3,3 s in loc de 1726 MB si 16 s.

CE PRODUCE — exact subsetul pe care-l foloseste `geometry`, nici mai mult, nici mai putin
(inventariat pe toti cei opt apelanti ai lui get_drawings inainte de a scrie un rand):
    {"layer": <numele OCG sau None>, "items": [("l", P, P) | ("c", P, P, P, P)], "rect": Rect,
     "pictat": <operatorul care a incheiat traseul: b"S", b"f*", ...>}
Nimeni nu citeste grosimea, culoarea, umplerea sau tipul; zona de decupare nu se foloseste nicaieri
(singurul `clip` din geometry e la randare, `get_pixmap`). Daca vreodata va fi nevoie de ele, se
adauga aici — dar nu se emit degeaba, fiindca fiecare camp costa memorie inmultita cu 925 000.

FILTRUL DE STRAT E MOTIVUL PENTRU CARE MERITA. `_collect` are nevoie doar de peretii si usile de
pe cateva straturi din douazeci. Cu `filtru_strat`, traseele de pe celelalte se ARUNCA inainte sa
devina obiecte Python — deci consumul creste cu ce se pastreaza, nu cu ce e pe pagina.

CE TRATEAZA, fiindca fara ele coordonatele ies gresite si peretii cad alaturi:
  q/Q       stiva de stare grafica
  cm        concatenarea matricei; punctele se transforma CAND SUNT CITITE
  Do        XObject-urile de formular, recursiv, fiecare cu `/Matrix` si resursele LUI
            (parterul blocului are 25; fara expandarea lor raporta 281k in loc de 925k primitive)
  /OC BDC   marked content -> numele stratului, prin Resources/Properties -> xref OCG -> /Name
  re        dreptunghi -> patru linii + inchidere, ca in get_drawings
  c/v/y     curbe Bezier (v si y isi repeta un punct de control, ca in spec)
  h         inchiderea caii
CE SARE: textul (BT..ET), imaginile si imaginile inline (BI..ID..EI — datele lor binare contin
orice, inclusiv secvente care arata a operatori).
"""
import re

import fitz

# ── Tokenizer ────────────────────────────────────────────────────────────────────────────────
# Un singur regex peste tot stream-ul: in Python pur, orice bucla caracter-cu-caracter e de zeci de
# ori mai lenta. Ordinea alternativelor conteaza — sirurile si comentariile trebuie recunoscute
# INAINTE de nume/numere, altfel un „(" dintr-un text rupe restul.
# Sirurile literale `(...)` NU se pot recunoaste cu `re`: ar cere recursie pentru parantezele
# imbricate, pe care doar modulul `regex` o are — iar el nu e o dependenta. Se sare peste ele
# manual, cu `_sfarsit_sir`: corect si fara dependente noi.
_TOK = re.compile(rb"""
      (?P<com>%[^\r\n]*)                      # comentariu
    | (?P<sir>\()                             # inceput de sir literal (se sare manual)
    | (?P<hex><[0-9A-Fa-f\s]*>)               # sir hex
    | (?P<dict_desch><<)
    | (?P<dict_inch>>>)
    | (?P<arr_desch>\[)
    | (?P<arr_inch>\])
    | (?P<nume>/[^\s/\[\]<>(){}%]*)           # nume: /Nume
    | (?P<num>[+-]?(?:\d+\.?\d*|\.\d+))       # numar
    | (?P<op>[A-Za-z'"*][A-Za-z0-9'"*]*)      # operator
""", re.X)


def _sfarsit_sir(date, i):
    """Pozitia de dupa `)`-ul care inchide sirul inceput la `i-1`. Trateaza imbricarea si `\\`."""
    adanc = 1
    n = len(date)
    while i < n:
        c = date[i]
        if c == 0x5C:            # backslash: urmatorul caracter e scapat
            i += 2
            continue
        if c == 0x28:            # (
            adanc += 1
        elif c == 0x29:          # )
            adanc -= 1
            if adanc == 0:
                return i + 1
        i += 1
    return n

# `n` NU e aici: inseamna „incheie traseul FARA sa-l desenezi". Tiparul standard `W n` seteaza
# zona de decupare, iar get_drawings nu raporteaza traseele alea — nu se vede nimic din ele.
# Cu `n` tratat ca pictare, parserul gasea 1606 segmente de perete acolo unde get_drawings
# gaseste 1219: 387 de „pereti" care erau de fapt limite de clip.
_PICTEAZA = frozenset([b"S", b"s", b"f", b"F", b"B", b"b", b"f*", b"B*", b"b*"])
_INCHEIE_FARA_DESEN = frozenset([b"n"])               # traseu abandonat (de obicei dupa `W`)
_FARA_TRASEU = frozenset([b"W", b"W*"])               # clip: nu picteaza, nu incheie traseul


def _inmulteste(a, b):
    """a × b, matrice PDF [a b c d e f]. Fara fitz.Matrix: se cheama de milioane de ori."""
    return (a[0] * b[0] + a[1] * b[2],
            a[0] * b[1] + a[1] * b[3],
            a[2] * b[0] + a[3] * b[2],
            a[2] * b[1] + a[3] * b[3],
            a[4] * b[0] + a[5] * b[2] + b[4],
            a[4] * b[1] + a[5] * b[3] + b[5])


def _aplica(m, x, y):
    return (m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5])


def _nums(operanzi, k):
    """Ultimii k operanzi, doar daca sunt TOTI numere; altfel None.

    Fara verificarea asta, un operator de desen precedat de un nume sau de un sir (se intampla in
    stream-uri reale) trecea un `bytes` in aritmetica matricei si ridica TypeError in mijlocul
    unui plan de 900 000 de primitive.
    """
    if len(operanzi) < k:
        return None
    u = operanzi[-k:]
    for z in u:
        if type(z) is not float:
            return None
    return u


def _straturi(doc, xref_res):
    """Numele stratului pentru fiecare /Nume din Resources/Properties al unei resurse."""
    out = {}
    try:
        tip, val = doc.xref_get_key(xref_res, "Resources/Properties")
    except Exception:
        return out
    if tip != "dict" or not val:
        return out
    ocg = doc.get_ocgs() or {}
    for nume, xr in re.findall(r"/([^\s/]+)\s+(\d+)\s+0\s+R", val):
        info = ocg.get(int(xr))
        if info and info.get("name"):
            out[nume.encode()] = info["name"]
    return out


def _xobiecte(doc, xref_res):
    """{/Nume: xref} pentru XObject-urile unei resurse."""
    out = {}
    try:
        tip, val = doc.xref_get_key(xref_res, "Resources/XObject")
    except Exception:
        return out
    if tip != "dict" or not val:
        return out
    for nume, xr in re.findall(r"/([^\s/]+)\s+(\d+)\s+0\s+R", val):
        out[nume.encode()] = int(xr)
    return out


def deseneaza(page, filtru_strat=None, _max_adancime=12):
    """Generator de desene, in forma pe care o asteapta `geometry`.

    `filtru_strat(nume) -> bool` decide, ÎNAINTE de construirea obiectelor, daca traseele de pe
    stratul curent intereseaza. Fara el se emit toate — si atunci memoria e ca la get_drawings.
    """
    doc = page.parent
    baza = tuple(page.transformation_matrix)          # spatiul PDF -> spatiul fitz (flip pe y)

    def _rec(date, xref_res, ctm, adancime, strat_mostenit):
        if adancime > _max_adancime:
            return
        harta_strat = _straturi(doc, xref_res)
        harta_xobj = _xobiecte(doc, xref_res)

        stiva = []                                    # q/Q: (ctm,)
        stiva_strat = []                              # BDC/EMC
        strat = strat_mostenit
        operanzi = []
        cale = []                                     # itemii traseului curent
        x0 = y0 = xc = yc = 0.0                       # start de subtraseu / punct curent
        in_text = False
        i = 0
        n = len(date)
        while i < n:
            m = _TOK.search(date, i)
            if not m:
                break
            i = m.end()
            g = m.lastgroup
            if g == "num":
                operanzi.append(float(m.group()))
                continue
            if g == "sir":
                i = _sfarsit_sir(date, i)
                operanzi.append(b"()")
                continue
            if g in ("nume", "hex", "arr_desch", "arr_inch", "dict_desch", "dict_inch"):
                operanzi.append(m.group())
                continue
            if g == "com":
                continue
            op = m.group()

            # ── text si imagini inline: se sare peste tot blocul ──
            if op == b"BT":
                in_text = True
                operanzi = []
                continue
            if op == b"ET":
                in_text = False
                operanzi = []
                continue
            if op == b"BI":
                # datele binare de dupa `ID` pot contine orice — se sare pana la `EI` izolat
                j = date.find(b"EI", i)
                i = (j + 2) if j >= 0 else n
                operanzi = []
                continue
            if in_text:
                operanzi = []
                continue

            # ── stare grafica ──
            if op == b"q":
                stiva.append(ctm)
            elif op == b"Q":
                if stiva:
                    ctm = stiva.pop()
            elif op == b"cm":
                _u = _nums(operanzi, 6)
                if _u:
                    ctm = _inmulteste(tuple(_u), ctm)

            # ── straturi (marked content) ──
            elif op == b"BDC":
                stiva_strat.append(strat)
                if len(operanzi) >= 2 and operanzi[-2] == b"/OC":
                    et = operanzi[-1]
                    if isinstance(et, bytes) and et.startswith(b"/"):
                        strat = harta_strat.get(et[1:], strat)
            elif op in (b"BMC",):
                stiva_strat.append(strat)
            elif op == b"EMC":
                if stiva_strat:
                    strat = stiva_strat.pop()

            # ── construirea traseului ──
            elif op == b"m":
                _u = _nums(operanzi, 2)
                if _u:
                    xc, yc = _u
                    x0, y0 = xc, yc
            elif op == b"l":
                _u = _nums(operanzi, 2)
                if _u:
                    cale.append(("l", (xc, yc), (_u[0], _u[1])))
                    xc, yc = _u[0], _u[1]
            elif op == b"c":
                a = _nums(operanzi, 6)
                if a:
                    cale.append(("c", (xc, yc), (a[0], a[1]), (a[2], a[3]), (a[4], a[5])))
                    xc, yc = a[4], a[5]
            elif op == b"v":
                a = _nums(operanzi, 4)
                if a:
                    # primul punct de control = punctul curent (spec PDF)
                    cale.append(("c", (xc, yc), (xc, yc), (a[0], a[1]), (a[2], a[3])))
                    xc, yc = a[2], a[3]
            elif op == b"y":
                a = _nums(operanzi, 4)
                if a:
                    # al doilea punct de control = punctul final
                    cale.append(("c", (xc, yc), (a[0], a[1]), (a[2], a[3]), (a[2], a[3])))
                    xc, yc = a[2], a[3]
            elif op == b"re":
                _u = _nums(operanzi, 4)
                if _u:
                    rx, ry, rw, rh = _u
                    # Item de tip "re", NU patru linii. get_drawings asa il da, iar `_collect`
                    # citeste doar "l" si "c" — deci pentru geometrie un dreptunghi e INVIZIBIL.
                    # Daca l-as desface in laturi, as adauga pereti pe care produsul nu i-a vazut
                    # niciodata, si filtrele ar decide altfel. Echivalenta bate corectitudinea
                    # geometrica: scopul e sa nu se schimbe nimic la case.
                    cale.append(("re", (rx, ry), (rx + rw, ry + rh)))
                    xc, yc = rx, ry
                    x0, y0 = rx, ry
            elif op == b"h":
                # Fara item: get_drawings marcheaza inchiderea cu `closePath` pe desen, nu cu o
                # linie in plus — verificat, `closePath` e fals pe toate cele 138 317 de desene ale
                # planului de referinta. O linie aici ar fi un segment pe care geometria nu-l vede.
                xc, yc = x0, y0

            # ── XObject ──
            elif op == b"Do" and operanzi:
                et = operanzi[-1]
                xr = harta_xobj.get(et[1:]) if isinstance(et, bytes) and et.startswith(b"/") else None
                if xr:
                    try:
                        sub = doc.xref_stream(xr)
                    except Exception:
                        sub = None
                    if sub:
                        mt = ctm
                        try:
                            t, v = doc.xref_get_key(xr, "Matrix")
                            if t == "array":
                                nums = [float(z) for z in re.findall(r"[-+]?[\d.]+", v)][:6]
                                if len(nums) == 6:
                                    mt = _inmulteste(tuple(nums), ctm)
                        except Exception:
                            pass
                        for dd in _rec(sub, xr, mt, adancime + 1, strat):
                            yield dd

            # ── pictare: se incheie traseul ──
            elif op in _PICTEAZA:
                if cale and (filtru_strat is None or filtru_strat(strat)):
                    itemi = []
                    xs = []
                    ys = []
                    for it in cale:
                        pct = [fitz.Point(*_aplica(ctm, px, py)) for px, py in it[1:]]
                        if it[0] == "re":
                            # get_drawings da ("re", Rect, orientare); `_collect` il ignora, dar
                            # `extract_columns` citeste `rect`-ul desenului, care se calculeaza
                            # oricum din toate punctele de mai jos.
                            itemi.append(("re", fitz.Rect(min(p.x for p in pct), min(p.y for p in pct),
                                                          max(p.x for p in pct), max(p.y for p in pct)), 1))
                            for pp in pct:
                                xs.append(pp.x)
                                ys.append(pp.y)
                            continue
                        for pp in pct:
                            xs.append(pp.x)
                            ys.append(pp.y)
                        itemi.append((it[0],) + tuple(pct))
                    # `pictat` = operatorul care a incheiat traseul. Parserul NU decide nimic pe
                    # baza lui — il livreaza, fiindca e singurul lucru care deosebeste un patrulater
                    # CONTURAT (simbol) de unul UMPLUT (perete in sectiune), iar regula care se
                    # foloseste de distinctia asta sta in `geometry`, nu aici. Vezi acolo de ce.
                    yield {"layer": strat, "items": itemi, "pictat": op,
                           "rect": fitz.Rect(min(xs), min(ys), max(xs), max(ys))}
                cale = []
            elif op in _INCHEIE_FARA_DESEN:
                cale = []                              # `n`: traseul se arunca, nu se emite nimic
            elif op in _FARA_TRASEU:
                pass                                   # `W`/`W*` nu incheie traseul
            operanzi = []

    # CTM initial = transformarea paginii; asa punctele ies direct in spatiul fitz, ca la get_drawings
    for d in _rec(page.read_contents(), page.xref, baza, 0, None):
        yield d
