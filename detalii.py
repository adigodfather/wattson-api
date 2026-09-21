# -*- coding: utf-8 -*-
"""PLANSELE DE DETALIU, desenate vectorial la noi.

DOUA detalii, amandoua TIPIZATE — verificat pe planşele lui Dan, cuvant cu cuvant: IE.35 si IE.36
n-au NICIUN continut specific proiectului. Tot ce scrie pe ele („Alim. corpuri il.sig.", „Doza
conexiuni", „piesa de separatie montata la h=1.5m") e valabil pe orice santier. De-aia pot fi
generate: nu depind de nimic ce trebuie masurat.

DE CE LE REDESENAM, in loc sa incorporam PDF-ul lui. Planşele lui poarta cartusul si nota de
proprietate a SC INSTAUDITOR SRL — „Ea nu poate fi reprodusa, copiata, imprumutata integral sau
partial". A le livra mai departe ar fi exact ce interzice nota. Continutul unui detaliu tehnic e
practica de meserie si nu se poate revendica; desenul ANUME al cuiva, da. Deci: continutul lui,
desenul nostru, cartusul nostru.

SINGURUL parametru: sectiunea benzii, care vine din `bloc.sectiune_banda` — aceeasi functie pe
care o cheama si BOM-ul, si caietul de sarcini, si eticheta de pe plan. Daca detaliul si-ar scrie
sectiunea de mana, planşa ar putea cere una si lista de materiale alta.
"""
import fitz

MMPT = 72.0 / 25.4

try:
    from cartus_swap import _txt as _ascii
except Exception:                                  # pragma: no cover
    def _ascii(s):
        return str(s or "")

_A4 = (210.0, 297.0)
_PAD_MM = 6.0
_NEGRU = (0.10, 0.10, 0.10)
_GRI = (0.55, 0.55, 0.55)
_GRI_DES = (0.72, 0.72, 0.72)
_CUPRU = (0.72, 0.42, 0.12)          # banda / bara prizei de pamant
_BETON = (0.86, 0.86, 0.84)

TITLU_IL = "DETALIU CONECTARE ILUMINAT DE SIGURANȚĂ"
TITLU_PP = "DETALIU CONECTARE PRIZĂ DE PĂMÂNT"


def _text(page, x, y, s, fs=7.0, bold=False, col=_NEGRU, anchor="left", rot=0):
    """Text, cu diacriticele transpuse prin ACELASI helper ca la cartus si la planşa: fonturile
    base-14 n-au ă/î/ș/ț si fara transpunere ies puncte."""
    t = _ascii(s)
    f = "hebo" if bold else "helv"
    w = fitz.get_text_length(t, fontname=f, fontsize=fs)
    if anchor == "center":
        x -= w / 2.0
    elif anchor == "right":
        x -= w
    page.insert_text((x, y), t, fontname=f, fontsize=fs, color=col, rotate=rot)
    return w


def _linie(page, x0, y0, x1, y1, col=_NEGRU, w=0.8, dash=None):
    page.draw_line(fitz.Point(x0 * MMPT, y0 * MMPT), fitz.Point(x1 * MMPT, y1 * MMPT),
                   color=col, width=w, dashes=dash)


def _drept(page, x0, y0, x1, y1, col=_NEGRU, w=0.8, fill=None):
    page.draw_rect(fitz.Rect(x0 * MMPT, y0 * MMPT, x1 * MMPT, y1 * MMPT),
                   color=col, width=w, fill=fill)


def _cerc(page, x, y, r, col=_NEGRU, w=0.8, fill=None):
    page.draw_circle(fitz.Point(x * MMPT, y * MMPT), r * MMPT, color=col, width=w, fill=fill)


def _txt(page, x, y, s, **kw):
    return _text(page, x * MMPT, y * MMPT, s, **kw)


def _trimitere(page, x0, y0, x1, y1, s, fs=6.2, anchor="left"):
    """Linie de trimitere (leader) + eticheta la capat. Capatul dinspre desen are un punct, ca sa
    se vada CE anume se indica — o sageata ar fi sugerat un sens, si aici nu curge nimic."""
    _linie(page, x0, y0, x1, y1, col=_GRI, w=0.5)
    _cerc(page, x0, y0, 0.5, col=_GRI, fill=_GRI)
    _txt(page, x1 + (1.2 if anchor == "left" else -1.2), y1 + 0.8, s, fs=fs, anchor=anchor,
         col=(0.25, 0.25, 0.25))


# ── DETALIUL 1: ILUMINATUL DE SIGURANTA ───────────────────────────────────────────────────────
# CE ARATA, si de ce asta conteaza: corpul de siguranta AUTONOM are acumulator, si ca sa-l poata
# incarca ii trebuie faza PERMANENTA — luata INAINTE de intrerupator. Daca s-ar lega dupa el, s-ar
# descarca exact cand omul stinge lumina si pleaca, adica fix cand e nevoie de el. Detaliul exista
# ca sa arate derivatia asta, si de-aia „Alim. corpuri il.sig." pleaca din doza, nu de pe circuitul
# comandat.
def _deseneaza_iluminat(page, W, H):
    X0, X1 = 26.0, 184.0
    _txt(page, (X0 + X1) / 2.0, 30.0, "Detaliu conectare iluminat de siguranță",
         fs=11.5, bold=True, anchor="center")
    _txt(page, (X0 + X1) / 2.0, 36.5,
         "corp autonom cu acumulator — alimentare permanentă, înaintea întrerupătorului",
         fs=6.8, col=(0.35, 0.35, 0.35), anchor="center")

    # ── circuitul de alimentare: trei conductoare, etichetate la stanga ──
    YL, YN, YPE = 104.0, 114.0, 124.0
    X_IN, X_DOZA = 34.0, 92.0
    for y, et, col in ((YL, "L", _NEGRU), (YN, "N", (0.15, 0.30, 0.65)), (YPE, "PE", (0.10, 0.50, 0.20))):
        _linie(page, X_IN, y, X_DOZA, y, col=col, w=1.1)
        _txt(page, X_IN - 2.0, y + 1.0, et, fs=7.0, bold=True, anchor="right", col=col)
    _txt(page, X_IN, YL - 6.0, "Alimentare circuit", fs=7.2, bold=True)
    _txt(page, X_IN, YL - 2.2, "(din tabloul de iluminat)", fs=6.0, col=(0.40, 0.40, 0.40))

    # ── doza de conexiuni ──
    DZ = (X_DOZA, 95.0, X_DOZA + 26.0, 133.0)
    _drept(page, DZ[0], DZ[1], DZ[2], DZ[3], col=_NEGRU, w=1.0, fill=(0.97, 0.97, 0.99))
    _txt(page, (DZ[0] + DZ[2]) / 2.0, DZ[3] + 5.0, "Doză conexiuni", fs=6.8, bold=True,
         anchor="center")
    for y in (YL, YN, YPE):
        _cerc(page, DZ[0] + 13.0, y, 1.0, col=_NEGRU, fill=_NEGRU)

    # ── ramura 1: corpurile de iluminat NORMAL, prin intrerupator ──
    X_SW, X_OUT = 140.0, 160.0
    Y_NORM = 124.0
    _linie(page, DZ[2], YL, X_SW - 4.0, YL, col=_NEGRU, w=1.1)
    _linie(page, X_SW - 4.0, YL, X_SW - 4.0, Y_NORM, col=_NEGRU, w=1.1)
    # intrerupatorul: contact oblic deschis
    _linie(page, X_SW - 4.0, Y_NORM, X_SW, Y_NORM, col=_NEGRU, w=1.1)
    _linie(page, X_SW, Y_NORM, X_SW + 5.0, Y_NORM - 4.0, col=_NEGRU, w=1.1)
    _cerc(page, X_SW, Y_NORM, 0.7, col=_NEGRU, fill=(1, 1, 1))
    _cerc(page, X_SW + 6.0, Y_NORM, 0.7, col=_NEGRU, fill=(1, 1, 1))
    _txt(page, X_SW + 1.0, Y_NORM - 6.0, "întrerupător", fs=6.0, col=(0.35, 0.35, 0.35))
    _linie(page, X_SW + 6.0, Y_NORM, X_OUT, Y_NORM, col=_NEGRU, w=1.1)
    _linie(page, DZ[2], YN, X_OUT, YN, col=(0.15, 0.30, 0.65), w=1.1)
    _linie(page, DZ[2], YPE, X_OUT, YPE, col=(0.10, 0.50, 0.20), w=1.1)
    _linie(page, X_OUT, YN, X_OUT, Y_NORM, col=(0.15, 0.30, 0.65), w=1.1)
    _drept(page, X_OUT, Y_NORM - 3.2, X_OUT + 14.0, Y_NORM + 3.2, col=_NEGRU, w=0.9,
           fill=(1.0, 0.98, 0.88))
    _cerc(page, X_OUT + 7.0, Y_NORM, 1.8, col=(0.45, 0.45, 0.45))
    _txt(page, X_OUT + 7.0, Y_NORM + 9.0, "Alim. corpuri", fs=6.4, anchor="center")
    _txt(page, X_OUT + 7.0, Y_NORM + 12.4, "il. normal", fs=6.4, anchor="center")

    # ── ramura 2: corpurile de SIGURANTA, permanent, din doza ──
    Y_SIG = 62.0
    _linie(page, DZ[0] + 13.0, YL, DZ[0] + 13.0, Y_SIG, col=_NEGRU, w=1.3)
    _linie(page, DZ[0] + 13.0, Y_SIG, X_OUT, Y_SIG, col=_NEGRU, w=1.3)
    _linie(page, DZ[0] + 13.0, YN, DZ[0] + 16.5, YN, col=(0.15, 0.30, 0.65), w=1.1)
    _linie(page, DZ[0] + 16.5, YN, DZ[0] + 16.5, Y_SIG + 3.2, col=(0.15, 0.30, 0.65), w=1.1)
    _linie(page, DZ[0] + 16.5, Y_SIG + 3.2, X_OUT, Y_SIG + 3.2, col=(0.15, 0.30, 0.65), w=1.1)
    _linie(page, DZ[0] + 13.0, YPE, DZ[0] + 20.0, YPE, col=(0.10, 0.50, 0.20), w=1.1)
    _linie(page, DZ[0] + 20.0, YPE, DZ[0] + 20.0, Y_SIG + 6.4, col=(0.10, 0.50, 0.20), w=1.1)
    _linie(page, DZ[0] + 20.0, Y_SIG + 6.4, X_OUT, Y_SIG + 6.4, col=(0.10, 0.50, 0.20), w=1.1)
    _drept(page, X_OUT, Y_SIG - 3.2, X_OUT + 14.0, Y_SIG + 8.0, col=_NEGRU, w=1.1,
           fill=(0.90, 0.98, 0.90))
    _txt(page, X_OUT + 7.0, Y_SIG + 3.4, "E", fs=9.0, bold=True, anchor="center",
         col=(0.10, 0.45, 0.20))
    _txt(page, X_OUT + 7.0, Y_SIG - 10.4, "Alim. corpuri", fs=6.4, anchor="center")
    _txt(page, X_OUT + 7.0, Y_SIG - 6.8, "il. siguranță", fs=6.4, bold=True, anchor="center")
    # Leaderul merge spre STANGA. Ancorat la dreapta, textul iesea din pagina (incepea la x=-19);
    # ancorat la stanga, linia trecea peste primele cuvinte. Se aseaza la stanga si leaderul se
    # opreste la MARGINEA DREAPTA a textului — latimea se MASOARA (`_txt` o intoarce), nu se
    # ghiceste, ca sa nu depinda de lungimea sirului.
    _YE = (YL + Y_SIG) / 2.0 - 10.0
    _w1 = _txt(page, X0 + 2.0, _YE, "fază PERMANENTĂ, derivată", fs=6.2, col=(0.25, 0.25, 0.25))
    _w2 = _txt(page, X0 + 2.0, _YE + 4.2, "înaintea întrerupătorului", fs=6.2, col=(0.25, 0.25, 0.25))
    _xe = X0 + 2.0 + max(_w1, _w2) / MMPT + 2.0
    _linie(page, DZ[0] + 13.0, (YL + Y_SIG) / 2.0, _xe, _YE + 2.0, col=_GRI, w=0.5)
    _cerc(page, DZ[0] + 13.0, (YL + Y_SIG) / 2.0, 0.5, col=_GRI, fill=_GRI)

    # ── nota ──
    NY = 168.0
    _drept(page, X0, NY, X1, NY + 30.0, col=_GRI_DES, w=0.6, fill=(0.98, 0.98, 0.98))
    _txt(page, X0 + 4.0, NY + 6.5, "NOTĂ", fs=7.0, bold=True)
    for i, r in enumerate((
            "Corpurile de iluminat de siguranță sunt autonome, cu acumulator propriu.",
            "Faza de alimentare se derivă din doza de conexiuni, ÎNAINTEA întrerupătorului,",
            "astfel încât acumulatorul să rămână în încărcare și cu iluminatul normal stins.",
            "Conductorul de protecție (PE) se leagă la ambele corpuri.")):
        _txt(page, X0 + 4.0, NY + 12.0 + i * 4.6, r, fs=6.4, col=(0.25, 0.25, 0.25))


# ── DETALIUL 2: PRIZA DE PAMANT ───────────────────────────────────────────────────────────────
# CE ARATA: legatura dintre armatura fundatiei unui stalp de beton si electrodul orizontal al prizei
# de pamant. NU DIFERA intre bloc cu subsol si bloc fara: detaliul descrie fundatia unui STALP, iar
# stalpul are aceeasi fundatie indiferent la ce cota incepe cladirea deasupra lui. Ce se schimba cu
# subsolul e PLANSA pe care apare conturul prizei (nivelul cel mai de jos), nu desenul de aici.
def _deseneaza_priza(page, W, H, banda="40x4"):
    X0, X1 = 26.0, 184.0
    _txt(page, (X0 + X1) / 2.0, 30.0, "Detaliu conectare armătură fundație", fs=11.5, bold=True,
         anchor="center")
    _txt(page, (X0 + X1) / 2.0, 36.5, "stâlp de beton la priza de pământ", fs=11.5, bold=True,
         anchor="center")

    XC = 82.0                    # axul stalpului
    Y_SOL = 96.0                 # cota terenului
    Y_CUZ_SUS, Y_CUZ_JOS = 132.0, 150.0
    Y_GROAPA = 162.0

    # ── terenul ──
    _linie(page, X0, Y_SOL, X1, Y_SOL, col=_NEGRU, w=1.0)
    for x in range(int(X0), int(X1), 5):
        _linie(page, x, Y_SOL, x - 2.4, Y_SOL - 2.4, col=_GRI, w=0.4)
    _txt(page, X0, Y_SOL - 4.0, "CTN", fs=6.2, col=(0.35, 0.35, 0.35))

    # ── stalpul de beton ──
    _drept(page, XC - 9.0, 44.0, XC + 9.0, Y_CUZ_SUS, col=_NEGRU, w=0.9, fill=_BETON)
    _txt(page, XC, 52.0, "stâlp", fs=6.4, anchor="center", col=(0.35, 0.35, 0.35))
    # ── cuzinetul / fundatia ──
    page.draw_polyline([fitz.Point(x * MMPT, y * MMPT) for x, y in
                        ((XC - 9.0, Y_CUZ_SUS), (XC - 26.0, Y_CUZ_JOS), (XC + 26.0, Y_CUZ_JOS),
                         (XC + 9.0, Y_CUZ_SUS))],
                       color=_NEGRU, width=0.9, fill=_BETON, closePath=True)
    _drept(page, XC - 26.0, Y_CUZ_JOS, XC + 26.0, Y_GROAPA, col=_NEGRU, w=0.9, fill=_BETON)
    _txt(page, XC, Y_CUZ_JOS - 4.0, "fundație stâlp", fs=6.2, anchor="center",
         col=(0.35, 0.35, 0.35))

    # ── gratarul din fier beton, pe fundul gropii ──
    Y_GRAT = Y_GROAPA - 3.0
    for i in range(9):
        x = XC - 24.0 + i * 6.0
        _linie(page, x, Y_GRAT - 3.0, x, Y_GRAT + 1.0, col=(0.35, 0.35, 0.35), w=0.7)
    for j in range(2):
        _linie(page, XC - 24.0, Y_GRAT - 3.0 + j * 4.0, XC + 24.0, Y_GRAT - 3.0 + j * 4.0,
               col=(0.35, 0.35, 0.35), w=0.7)

    # ── electrodul orizontal: banda, pozata in beton pe fundul gropii ──
    _linie(page, X0 + 2.0, Y_GRAT, X1 - 40.0, Y_GRAT, col=_CUPRU, w=2.2)
    # legaturile la gratar, din 20 in 20 cm
    for i in range(5):
        x = XC - 20.0 + i * 10.0
        _linie(page, x, Y_GRAT, x, Y_GRAT - 3.0, col=_CUPRU, w=1.2)
        _cerc(page, x, Y_GRAT - 3.0, 0.7, col=_CUPRU, fill=_CUPRU)

    # ── bara rotunda de urcare + piesa de separatie ──
    X_BARA = XC + 13.0
    Y_PIESA = Y_SOL - 32.0                     # h = 1,5 m peste cota terenului, la scara desenului
    # SUB piesa = BANDA (mai groasa), PESTE ea = bara rotunda (mai subtire). Ordinea e a lui Dan,
    # citita de pe IE.36 de sus in jos: bara rotunda 25x4 · piesa de separatie · banda.
    # (Pe planşa LUI banda scrie 40x6; noi tiparim `bloc.sectiune_banda` — vezi motivul acolo.
    # Ordinea celor trei e ce se preia de-aici, nu sectiunea.)
    _linie(page, X_BARA, Y_GRAT, X_BARA, Y_PIESA + 4.0, col=_CUPRU, w=2.2)
    _linie(page, X_BARA, Y_PIESA - 4.0, X_BARA, 48.0, col=_CUPRU, w=1.2)
    _drept(page, X_BARA - 3.2, Y_PIESA - 4.0, X_BARA + 3.2, Y_PIESA + 4.0, col=_NEGRU, w=0.9,
           fill=(1.0, 1.0, 1.0))
    _linie(page, X_BARA - 2.0, Y_PIESA, X_BARA + 2.0, Y_PIESA, col=_NEGRU, w=0.7)
    # cota h = 1,5 m
    _linie(page, X_BARA + 10.0, Y_SOL, X_BARA + 10.0, Y_PIESA, col=_GRI, w=0.5)
    _linie(page, X_BARA + 8.0, Y_SOL, X_BARA + 12.0, Y_SOL, col=_GRI, w=0.5)
    _linie(page, X_BARA + 8.0, Y_PIESA, X_BARA + 12.0, Y_PIESA, col=_GRI, w=0.5)
    _txt(page, X_BARA + 13.0, (Y_SOL + Y_PIESA) / 2.0, "h = 1,50 m", fs=6.2,
         col=(0.30, 0.30, 0.30))

    # ── trimiteri ──
    _trimitere(page, X_BARA, 54.0, X1 - 42.0, 52.0, "bară rotundă masivă OL-Zn 25×4 mm")
    _trimitere(page, X_BARA, Y_PIESA, X1 - 42.0, Y_PIESA - 2.0,
               "piesă de separație montată la h = 1,50 m")
    _trimitere(page, X_BARA, Y_SOL + 14.0, X1 - 42.0, Y_SOL + 10.0,
               "bandă OL-Zn %s mm" % banda)
    _trimitere(page, XC + 24.0, Y_GRAT, X1 - 42.0, Y_GRAT - 14.0,
               "electrod orizontal al prizei de pământ,")
    _txt(page, X1 - 40.8, Y_GRAT - 9.6, "bandă OL-Zn %s mm pozată în beton" % banda, fs=6.2,
         col=(0.25, 0.25, 0.25))
    _txt(page, X1 - 40.8, Y_GRAT - 6.0, "pe fundul gropii de fundație", fs=6.2,
         col=(0.25, 0.25, 0.25))
    _trimitere(page, XC - 14.0, Y_GRAT - 1.0, X0 + 2.0, Y_GRAT + 12.0,
               "legată de grătarul de la baza cuzinetului")
    _txt(page, X0 + 3.2, Y_GRAT + 16.4, "din 20 în 20 cm", fs=6.2, col=(0.25, 0.25, 0.25))
    _trimitere(page, XC + 6.0, Y_GRAT + 1.5, X0 + 2.0, Y_GRAT + 26.0,
               "grătar din fier beton montat pe fundul gropii de")
    _txt(page, X0 + 3.2, Y_GRAT + 30.4, "fundație a stâlpului, înglobat cel puțin 5 cm în beton",
         fs=6.2, col=(0.25, 0.25, 0.25))

    # ── nota ──
    NY = 212.0
    _drept(page, X0, NY, X1, NY + 21.0, col=_GRI_DES, w=0.6, fill=(0.98, 0.98, 0.98))
    _txt(page, X0 + 4.0, NY + 6.0, "NOTĂ", fs=7.0, bold=True)
    # Pragul se scrie in SENSUL corect. Prima varianta zicea „sub 1 Ω nu se accepta", adica exact
    # pe dos: valoarea mica e cea buna. Si se scrie „ohm", nu „Ω" — fonturile base-14 n-au simbolul
    # si transpunerea ASCII il face un punct.
    _txt(page, X0 + 4.0, NY + 11.5,
         "Priza de pământ este de fundație (I7-2011). Rezistența de dispersie se măsoară la "
         "recepție: cel mult 1 ohm când", fs=6.4, col=(0.25, 0.25, 0.25))
    _txt(page, X0 + 4.0, NY + 16.0,
         "priza este comună cu instalația de paratrăsnet, cel mult 4 ohm în rest.",
         fs=6.4, col=(0.25, 0.25, 0.25))


_DESENE = {
    "detaliu_iluminat_siguranta": (_deseneaza_iluminat, TITLU_IL),
    "detaliu_priza_pamant": (_deseneaza_priza, TITLU_PP),
}


def build_detaliu(tip, cartus_firma=None, cartus_proiect=None, plansa_nr=None, banda=None):
    """Un detaliu -> bytes PDF (o pagina A4), sau None daca tipul nu-i cunoscut.

    `banda` conteaza doar la priza de pamant. Implicit se cere de la `bloc.sectiune_banda` — sursa
    unica; parametrul ramane ca sa se poata testa desenul cu o sectiune anume, fara sa atinga
    constanta."""
    if tip not in _DESENE:
        return None
    fn, titlu = _DESENE[tip]
    W, H = _A4[0] * MMPT, _A4[1] * MMPT
    doc = fitz.open()
    page = doc.new_page(width=W, height=H)
    PAD = _PAD_MM * MMPT
    page.draw_rect(fitz.Rect(PAD, PAD, W - PAD, H - PAD), color=_NEGRU, width=1.2)
    if tip == "detaliu_priza_pamant":
        import bloc as _blc
        fn(page, W, H, banda=banda or _blc.sectiune_banda())
    else:
        fn(page, W, H)
    raw = doc.tobytes(deflate=True)
    doc.close()
    from schema_cs import _cartus_final           # acelasi lant de cartus ca la CS si FV
    return _cartus_final(raw, W, H, cartus_firma, cartus_proiect, plansa_nr, titlu)
