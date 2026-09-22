# -*- coding: utf-8 -*-
"""Holul ca SPATIU RAMAS intre camerele cunoscute, impartit in BRATE.

DE CE. Holul si accesul nu au pereti proprii si nu au usi — sunt golul dintre celelalte camere.
Cautarea de contur nu are ce inchide acolo, deci camera cade pe dreptunghiul Vision si becul ajunge
unde nimereste. Aici nu se mai cauta camera, ci golul: se marcheaza peretii si camerele care AU
contur, iar ce ramane liber se imparte in brate drepte. Fiecare brat isi primeste becul pe mijlocul
latimii, iar cei doi pereti laterali ies pe gratis — sunt marginile bratului pe directia subtire.

UNDE SE APLICA, STRICT: doar camerele de circulatie care AZI cad pe dreptunghiul Vision sau pe
ancora etichetei. Camerele normale si cele patru holuri care au deja contur propriu nu se ating —
au ceva mai bun decat ce poate da metoda asta.

PRAGUL DE ACCEPTARE (decizia lui Dan): latime <= 3 m, aria <= aria declarata dupa taiere, si
bratul trebuie sa contina eticheta camerei. Daca nu trece, camera ramane cum e azi: MAI BINE NIMIC
DECAT UN BEC IN LOC GRESIT.

ORICE PRAG IN METRI SE IA DIN SCARA REALA a planului (`bom.derive_scale`), nu din conversia fixa:
pe `casa testt` cele doua difera cu 49% (0,0249 vs 0,0167 m/pt), adica orice latime ar iesi cu
jumatate mai mare decat e.
"""
import re
from collections import deque

# Circulatie: familia pentru care metoda asta are sens. Terasele si balcoanele se scot EXPLICIT,
# fiindca „acces" le prinde altfel („Terasa acces") — aceeasi capcana ca „logie" in „radioLOGIE".
RX_CIRCULATIE = re.compile(
    # `casa scarii` are nevoie de \w* la coada: cu `\b` dupa „scar" nu s-ar potrivi niciodata,
    # fiindca urmeaza „ii". Prins de test, nu de citit.
    r"\b(hol|vestibul|sas|palier|windfang|degajament|culoar|coridor|acces)\b|\bcasa\s*sc[aă]r\w*",
    re.I)
RX_NU_E_CIRCULATIE = re.compile(r"\b(terasa|terase|balcon|curte|logie|pod|garaj)\b", re.I)

PAS = 5.0                  # pt per celula de grila
GROSIME_PERETE = 1         # celule de ingrosare (un perete trebuie sa desparta, nu sa se scurga)
LATIME_MAX_M = 3.0         # decizia lui Dan: peste 3 m nu mai e hol
LUNGIME_MIN_M = 1.2        # sub atat nu e brat, e colt
ARIE_MIN_M2 = 0.8          # sub atat nu merita un bec propriu
LIBER, PERETE, CAMERA, EXTERIOR = 0, 1, 2, 3


def e_circulatie(nume):
    n = (nume or "").strip()
    return bool(RX_CIRCULATIE.search(n)) and not RX_NU_E_CIRCULATIE.search(n)


class _Harta:
    """Grila de ocupare a planului: pereti, camere cunoscute, exterior, si ce ramane."""

    def __init__(self, W, H, pas=PAS):
        self.pas = pas
        self.nx = int(W / pas) + 2
        self.ny = int(H / pas) + 2
        self.g = bytearray(self.nx * self.ny)

    def _i(self, ix, iy):
        return iy * self.nx + ix

    def cel(self, x, y):
        return int(x / self.pas), int(y / self.pas)

    def segment(self, x0, y0, x1, y1):
        ix0, iy0 = self.cel(min(x0, x1), min(y0, y1))
        ix1, iy1 = self.cel(max(x0, x1), max(y0, y1))
        for iy in range(max(0, iy0 - GROSIME_PERETE), min(self.ny, iy1 + GROSIME_PERETE + 1)):
            baza = iy * self.nx
            for ix in range(max(0, ix0 - GROSIME_PERETE), min(self.nx, ix1 + GROSIME_PERETE + 1)):
                self.g[baza + ix] = PERETE

    def dreptunghi(self, l, t, r, b):
        ix0, iy0 = self.cel(l, t)
        ix1, iy1 = self.cel(r, b)
        for iy in range(max(0, iy0), min(self.ny, iy1 + 1)):
            baza = iy * self.nx
            for ix in range(max(0, ix0), min(self.nx, ix1 + 1)):
                if self.g[baza + ix] == LIBER:
                    self.g[baza + ix] = CAMERA

    def _blocat_ingrosat(self, k):
        """Masca de blocare cu peretii INGROSATI cu k celule, pentru inundarea exteriorului.

        Anvelopa unei case nu e inchisa in desen: usa de intrare, iesirea spre terasa si racordurile
        lasa goluri, iar inundarea din marginea paginii intra prin ele si marcheaza jumatate de casa
        drept „exterior" — masurat, asa cadeau 21 din 33 de camere de circulatie. Ingrosarea astupa
        golurile cat o usa. E folosita NUMAI la inundare, deci nu poate decat sa RESTRANGA exteriorul:
        o celula interioara nu are cum sa devina exterioara din cauza ei.
        """
        nx, ny, g = self.nx, self.ny, self.g
        b = bytearray(nx * ny)
        for iy in range(ny):
            baza = iy * nx
            ultim = -10 ** 9
            for ix in range(nx):                         # o trecere la dreapta
                if g[baza + ix] != LIBER:
                    ultim = ix
                if ix - ultim <= k:
                    b[baza + ix] = 1
            ultim = 10 ** 9
            for ix in range(nx - 1, -1, -1):             # si una la stanga
                if g[baza + ix] != LIBER:
                    ultim = ix
                if ultim - ix <= k:
                    b[baza + ix] = 1
        for ix in range(nx):                             # apoi acelasi lucru pe verticala
            ultim = -10 ** 9
            for iy in range(ny):
                if b[iy * nx + ix]:
                    ultim = iy
                if iy - ultim <= k:
                    b[iy * nx + ix] = 1
            ultim = 10 ** 9
            for iy in range(ny - 1, -1, -1):
                if b[iy * nx + ix]:
                    ultim = iy
                if ultim - iy <= k:
                    b[iy * nx + ix] = 1
        return b

    def scoate_exteriorul(self, k_inchidere=0):
        """Inunda din marginea paginii: ce se atinge de afara nu e spatiu interior."""
        blocat = self._blocat_ingrosat(k_inchidere) if k_inchidere else None

        def liber(ix, iy):
            i = self._i(ix, iy)
            if self.g[i] != LIBER:
                return False
            return not (blocat and blocat[i])

        q = deque()
        for ix in range(self.nx):
            for iy in (0, self.ny - 1):
                if liber(ix, iy):
                    q.append((ix, iy))
        for iy in range(self.ny):
            for ix in (0, self.nx - 1):
                if liber(ix, iy):
                    q.append((ix, iy))
        vaz = set(q)
        while q:
            ix, iy = q.popleft()
            self.g[self._i(ix, iy)] = EXTERIOR
            for jx, jy in ((ix + 1, iy), (ix - 1, iy), (ix, iy + 1), (ix, iy - 1)):
                if (jx, jy) in vaz or not (0 <= jx < self.nx and 0 <= jy < self.ny):
                    continue
                if liber(jx, jy):
                    vaz.add((jx, jy))
                    q.append((jx, jy))

    def gol_din(self, ix, iy, max_celule=60000):
        """Componenta conexa de spatiu liber care contine celula data (sau None)."""
        if not (0 <= ix < self.nx and 0 <= iy < self.ny) or self.g[self._i(ix, iy)] != LIBER:
            return None
        vaz = {(ix, iy)}
        q = deque([(ix, iy)])
        while q:
            ax, ay = q.popleft()
            if len(vaz) > max_celule:
                break
            for jx, jy in ((ax + 1, ay), (ax - 1, ay), (ax, ay + 1), (ax, ay - 1)):
                if (jx, jy) in vaz or not (0 <= jx < self.nx and 0 <= jy < self.ny):
                    continue
                if self.g[self._i(jx, jy)] == LIBER:
                    vaz.add((jx, jy))
                    q.append((jx, jy))
        return vaz


def _grosimi(celule):
    """(gx, gy) per celula: lungimea sirului liber prin ea, pe orizontala si pe verticala."""
    gx, gy = {}, {}
    rand, col = {}, {}
    for (ix, iy) in celule:
        rand.setdefault(iy, []).append(ix)
        col.setdefault(ix, []).append(iy)
    for iy, xs in rand.items():
        xs.sort()
        i = 0
        while i < len(xs):
            j = i
            while j + 1 < len(xs) and xs[j + 1] == xs[j] + 1:
                j += 1
            for k in range(i, j + 1):
                gx[(xs[k], iy)] = xs[j] - xs[i] + 1
            i = j + 1
    for ix, ys in col.items():
        ys.sort()
        i = 0
        while i < len(ys):
            j = i
            while j + 1 < len(ys) and ys[j + 1] == ys[j] + 1:
                j += 1
            for k in range(i, j + 1):
                gy[(ix, ys[k])] = ys[j] - ys[i] + 1
            i = j + 1
    return gx, gy


def _brate(celule, pas, scara):
    """Golul, impartit in brate drepte: [{o, celule, gros_med_m}].

    O celula e „de coridor" daca grosimea ei MICA e sub latimea maxima; gruparea se face pe
    ORIENTARE si apoi pe conexitate. Un hol drept da un brat, unul in L doua, unul in T trei —
    fara nicio regula in plus, doar din forma golului.
    """
    gx, gy = _grosimi(celule)
    lat_max = LATIME_MAX_M / scara / pas          # in celule
    orient = {}
    for c in celule:
        a, b = gx.get(c, 0), gy.get(c, 0)
        # La COLTUL unui L, grosimea pe x e egala cu cea pe y (patratul de intoarcere). Cu
        # inegalitate stricta, coltul nu intra in niciun brat si le DESPARTE pe cele doua, iar un
        # hol in L iesea cu un singur bec. Egalitatea merge la brazul orizontal, determinist.
        if b <= lat_max and b <= a:
            orient[c] = "H"
        elif a <= lat_max and a < b:
            orient[c] = "V"
    out, vaz = [], set()
    for c0 in orient:
        if c0 in vaz:
            continue
        o = orient[c0]
        q = deque([c0])
        vaz.add(c0)
        grup = []
        while q:
            c = q.popleft()
            grup.append(c)
            ix, iy = c
            for j in ((ix + 1, iy), (ix - 1, iy), (ix, iy + 1), (ix, iy - 1)):
                if j in orient and j not in vaz and orient[j] == o:
                    vaz.add(j)
                    q.append(j)
        gros = sorted((gy if o == "H" else gx).get(c, 0) for c in grup)
        out.append({"o": o, "celule": grup,
                    "gros_med_m": (gros[len(gros) // 2] * pas * scara) if gros else 0.0})
    return out


def _taie_la_buget(brat, ancora_cel, pas, scara, buget_m2):
    """Bratul, taiat la aria declarata, pastrand partea dinspre eticheta camerei.

    Celulele se iau in ordinea distantei fata de eticheta PE AXA LUNGA a bratului (deci de la
    eticheta spre capete), pana se atinge bugetul. Simetric, nu intr-o singura directie: eticheta
    sta de obicei la mijlocul holului, iar o taiere intr-o singura parte ar muta becul spre un capat.
    """
    if not buget_m2 or buget_m2 <= 0:
        return None                                # fara arie declarata -> nu inventam buget
    arie_cel = (pas * scara) ** 2
    n_max = int(buget_m2 / arie_cel)
    if n_max <= 0:
        return None
    if len(brat["celule"]) <= n_max:
        return brat["celule"]
    axa = 0 if brat["o"] == "H" else 1             # H -> lungimea e pe x
    a0 = ancora_cel[axa]
    return sorted(brat["celule"], key=lambda c: abs(c[axa] - a0))[:n_max]


def _dreptunghi_celule(celule, pas):
    xs = [c[0] for c in celule]
    ys = [c[1] for c in celule]
    return (min(xs) * pas, min(ys) * pas, (max(xs) + 1) * pas, (max(ys) + 1) * pas)


def _vecine(a, b):
    """Doua brate se ating? (o celula a unuia e lipita de o celula a celuilalt)"""
    cb = set(b["celule"])
    for (ix, iy) in a["celule"]:
        if ((ix + 1, iy) in cb or (ix - 1, iy) in cb or (ix, iy + 1) in cb or (ix, iy - 1) in cb):
            return True
    return False


def brate_camerei(hm, ancora_pt, decl_m2, scara):
    """Bratele acceptate pentru o camera, pornind de la eticheta ei. [] daca niciunul nu trece.

    Se pleaca de la bratul care CONTINE eticheta si se creste in bratele vecine cat incape in aria
    declarata. De-aici ies de la sine cele trei cazuri: un hol drept da un brat, unul in L doua
    (bratul orizontal si cel vertical se ating), unul in T trei. Bugetul e cel care opreste
    cresterea inainte sa intre in camera deschisa de alaturi.
    """
    respinse = {"latime": 0, "lungime": 0, "fara_eticheta": 0, "arie": 0,
                "fara_buget": 0, "fara_gol": 0}
    if not decl_m2 or decl_m2 <= 0:
        respinse["fara_buget"] = 1                 # decizia 2: fara arie declarata, nu se aplica
        return [{"respinse": respinse}]
    ac = hm.cel(*ancora_pt)
    gol = hm.gol_din(*ac)
    if not gol:
        # ancora nu cade in spatiu liber: e pe un perete, intr-o camera cunoscuta, sau afara —
        # adica planul nu are un gol acolo unde Vision crede ca e camera
        respinse["fara_gol"] = 1
        return [{"respinse": respinse}]
    toate = _brate(gol, hm.pas, scara)
    seminte = [b for b in toate if ac in set(b["celule"])]
    if not seminte:
        respinse["fara_eticheta"] = 1              # eticheta nu cade in niciun brat
        return [{"respinse": respinse}]
    arie_cel = (hm.pas * scara) ** 2
    pastrate = []
    buget = decl_m2
    of = [b for b in seminte if b["gros_med_m"] <= LATIME_MAX_M]
    if not of:
        respinse["latime"] = 1
        return [{"respinse": respinse}]
    coada = [of[0]]
    ramase = [b for b in toate if b is not of[0]]
    while coada:
        br = coada.pop(0)
        if br["gros_med_m"] > LATIME_MAX_M:
            respinse["latime"] += 1
            continue
        cel = br["celule"]
        if len(cel) * arie_cel > buget:            # bratul depaseste bugetul -> se taie
            cel = _taie_la_buget(br, ac, hm.pas, scara, buget)
            if not cel:
                respinse["arie"] += 1
                continue
        l, t, r, b = _dreptunghi_celule(cel, hm.pas)
        lung_m = max(r - l, b - t) * scara
        arie = len(cel) * arie_cel
        if lung_m < LUNGIME_MIN_M or arie < ARIE_MIN_M2:
            respinse["lungime"] += 1
            continue
        pastrate.append({"rect": (l, t, r, b), "o": br["o"], "lung_m": lung_m,
                         "lat_m": min(r - l, b - t) * scara, "arie_m2": arie,
                         "pereti": ((t, b) if br["o"] == "H" else (l, r))})
        buget -= arie
        if buget <= ARIE_MIN_M2:
            break
        for alt in list(ramase):                   # creste in bratele lipite de cel pastrat
            if _vecine(br, alt):
                ramase.remove(alt)
                coada.append(alt)
    if not pastrate:
        return [{"respinse": respinse}]
    pastrate[0]["respinse"] = respinse
    return pastrate


# Cat se ingroasa peretii la inundarea exteriorului: cat o usa (~0,9 m), exprimat in celule prin
# scara reala a planului. Sub atat, exteriorul intra pe usa de intrare; peste, n-ar strica nimic
# (masca e folosita DOAR la inundare), dar costa timp degeaba.
INCHIDERE_M = 0.9


def harta_plan(h_segs, v_segs, rects_cunoscute, W, H, scara=None):
    """Grila unui plan: pereti + camerele cu contur propriu, cu exteriorul scos."""
    hm = _Harta(W, H)
    for (x0, x1, y) in (h_segs or []):
        hm.segment(x0, y, x1, y)
    for (y0, y1, x) in (v_segs or []):
        hm.segment(x, y0, x, y1)
    for (l, t, r, b) in (rects_cunoscute or []):
        hm.dreptunghi(l, t, r, b)
    k = int(INCHIDERE_M / (scara * hm.pas)) if (scara and scara > 0) else 0
    hm.scoate_exteriorul(k_inchidere=k)
    return hm
