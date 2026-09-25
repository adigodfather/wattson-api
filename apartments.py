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

# SPATIUL COMERCIAL din bloc (P6b). TIP PROPRIU, nu un flag pe conturul de apartament — si nu din
# lene, ci fiindca singurul flag „gratuit" ar fi fost prefixul etichetei („SP1" vs „P1_5"), iar
# eticheta e un camp LIBER, pe care inginerul il editeaza. Tipul dedus dintr-o eticheta editabila
# inseamna ca o redenumire muta tacit circuitele pe alt tablou — greşit si plauzibil, exact clasa de
# defect pe care o evitam peste tot. Un tip de element e o decizie inregistrata o data, are butonul
# lui in editor si simbolul lui in legenda, si costa aceeasi migratie ca o coloana noua.
CONTUR_SP = "contur_spatiu_comercial"
CONTURI = (CONTUR, CONTUR_SP)

# Eticheta de apartament, conventia de pe planşele lui Dan:
#   parter  -> „P1".."P4"      (marcaj „Ap P1"),   tablou „TE-AP 1"
#   etaj 1  -> „P1_1".."P1_9"  (marcaj „Ap P1_5"), tablou „TE-AP 1.5"
# Cratima si punctul difera intre marcajul de pe plan si numele tabloului chiar in documentele lui —
# pastram ambele forme exact cum le scrie el, fiecare acolo unde apare.
# Tiparele „P1_5" / „P3" traiesc acum in `_panel_din`, parametrizate pe prefix, ca sa nu existe o a
# doua copie pentru „SP1_2" / „SP1".


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


# Prefixul etichetei si al tabloului, per tip de contur. Spatiul comercial urmeaza EXACT aceeasi
# regula ca apartamentul („SP1" la parter, „SP1_2" la etajul 1 -> „TE-SP 1" / „TE-SP 1.2"), ca sa nu
# existe doua conventii de citit. Numele „TE-SP <n>" e al lui Dan, luat de pe IE.27 (Nota 2:
# „Tabloul electric TE-SP va fi montat incastrat in perete"), nu inventat.
_PREFIX = {CONTUR: ("P", "TE-AP"), CONTUR_SP: ("SP", "TE-SP")}


def eticheta_auto(floor_idx, ordine, tip=CONTUR):
    """Eticheta propusa la creare: nivelul + ordinea. Parterul n-are prefix de etaj, ca la Dan.

    AUTOMATA, dar EDITABILA — se scrie in `label`, campul care exista deja. Numerotarea automata e
    singura care ramane consecventa cand inginerul sterge al treilea apartament din cinci; scrisul
    de mana ar lasa o gaura pe care n-o vede nimeni pana la schema.

    Ordinea se numara PER TIP: un parter cu doua apartamente si un magazin da „P1", „P2" si „SP1",
    nu „SP3" — altfel numerotarea comerciala ar depinde de cate apartamente sunt langa."""
    pre = _PREFIX.get(tip, _PREFIX[CONTUR])[0]
    if floor_idx <= 0:
        return "%s%d" % (pre, ordine)
    return "%s%d_%d" % (pre, floor_idx, ordine)


def _panel_din(eticheta, pre, tab):
    e = str(eticheta or "").strip()
    if e.upper().startswith(pre.upper()):
        rest = e[len(pre):]
        m = re.match(r"^(\d+)_(\d+)$", rest)
        if m:
            return "%s %s.%s" % (tab, m.group(1), m.group(2))
        m = re.match(r"^(\d+)$", rest)
        if m:
            return "%s %s" % (tab, m.group(1))
    return ("%s %s" % (tab, e)) if e else tab


def panel_contur(eticheta, tip=CONTUR):
    """Numele TABLOULUI unui contur, din eticheta si TIPUL lui.

    Tipul, nu eticheta, decide familia de tablou. O eticheta scrisa de mana care nu se potriveste cu
    tiparul iese „TE-AP <eticheta>" / „TE-SP <eticheta>" — lizibila, in loc sa dispara."""
    pre, tab = _PREFIX.get(tip, _PREFIX[CONTUR])
    return _panel_din(eticheta, pre, tab)




def eticheta_din_panel(panel):
    """„TE-AP 1.5" -> „P1_5"; „TE-SP 2" -> „SP2". None daca nu-i tablou de contur.
    Drumul invers al lui `panel_contur`, ca descrierea circuitului sa poata numi APARTAMENTUL sau
    SPATIUL in loc de nivel: noua circuite „Iluminat etaj" pe acelasi etaj nu spun nimic."""
    e = str(panel or "").strip()
    for tip, (pre, tab) in _PREFIX.items():
        if not e.upper().startswith(tab.upper()):
            continue
        rest = e[len(tab):].strip()
        if not rest:
            return None
        m = re.match(r"^(\d+)\.(\d+)$", rest)
        if m:
            return "%s%s_%s" % (pre, m.group(1), m.group(2))
        m = re.match(r"^(\d+)$", rest)
        return ("%s%s" % (pre, m.group(1))) if m else rest
    return None




def conturi_nivel(plan_elements, floor_key, floor_canonic, tipuri=CONTURI):
    """Contururile de pe UN nivel — apartamente SI spatii comerciale — in ordine determinista (de sus
    in jos, apoi de la stanga la dreapta: ordinea in care le-ar numerota un om).
    Fiecare: {eticheta, tip, pts, aria, el}.

    `floor_canonic` se primeste ca functie ca sa nu duplicam axa aici: apartenenta la nivel trece
    prin ACEEASI canonizare ca restul codului. `tipuri` exista ca sa se poata cere DOAR apartamentele
    acolo unde intrebarea chiar e despre ele."""
    br = []
    for el in (plan_elements or []):
        tip = (el or {}).get("element_type") or ""
        if tip not in tipuri:
            continue
        if floor_canonic((el or {}).get("floor")) != floor_key:
            continue
        pts = _pts(el)
        if not pts:
            continue                             # poligon malformat -> ignorat, nu o exceptie
        br.append({"pts": pts, "aria": _aria(pts), "el": el, "tip": tip,
                   "_y": min(p[1] for p in pts), "_x": min(p[0] for p in pts)})
    br.sort(key=lambda b: (round(b["_y"] / 40.0), b["_x"]))   # randuri de ~40 pt, apoi stanga->dreapta
    _ord = {}                                    # ordinea se numara PER TIP (vezi `eticheta_auto`)
    for b in br:
        _ord[b["tip"]] = _ord.get(b["tip"], 0) + 1
        lbl = str((b["el"].get("label") or "")).strip()
        b["eticheta"] = lbl or eticheta_auto(_idx_din(floor_key, floor_canonic),
                                             _ord[b["tip"]], b["tip"])
    return br


def _idx_din(floor_key, floor_canonic):
    """Indexul de nivel, doar pentru eticheta automata. Import tarziu ca sa nu legam modulul de
    axa la incarcare (si ca sa ramana testabil izolat)."""
    try:
        import floors as _fl
        return max(0, _fl.floor_index(floor_key))
    except Exception:
        return 0


def contur_al_punctului(x, y, conturi):
    """Conturul care CONTINE punctul (dictionarul intreg), sau None.

    SUPRAPUNERE -> castiga cel mai MIC, adica cel mai specific. Aceeasi regula si cand contururile-s
    de TIPURI diferite: un apartament desenat peste un spatiu comercial nu e o situatie legitima, dar
    daca inginerul o deseneaza, raspunsul trebuie sa fie DETERMINIST, nu sa depinda de ordinea din
    lista. La arii egale departajeaza eticheta, tot ca sa nu existe doua raspunsuri pentru acelasi
    plan."""
    hits = [c for c in (conturi or []) if _in_poligon(x, y, c["pts"])]
    if not hits:
        return None
    return min(hits, key=lambda c: (c["aria"], str(c.get("eticheta") or "")))




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
    c = contur_al_elementului(el, conturi)
    return c["eticheta"] if c else None


def contur_al_elementului(el, conturi):
    """Conturul unui element de plan (dictionarul intreg, cu `tip`), sau None.

    Forma generala a lui `apartament_al_elementului`: cine are nevoie sa stie DACA e apartament sau
    spatiu comercial intreaba aici, in loc sa deduca din eticheta."""
    try:
        return contur_al_punctului(float(el["x"]), float(el["y"]), conturi)
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




# ── P4: COPIEREA CONTINUTULUI INTRE APARTAMENTE IDENTICE ──────────────────────────────────────
# Inginerul lucreaza UN apartament complet; cele identice de pe alte niveluri il primesc automat.
#
# DE CE E MAI SIGUR DECAT DETECTIA USII, care a picat pe 7 din 8 planuri:
#   1. apartamentele suprapuse sunt ALINIATE VERTICAL — se compara conturul din ACELASI LOC pe doua
#      planşe, nu se cauta asemanari oriunde;
#   2. esecul e VIZIBIL: daca nu recunoaste, etajul iese GOL si inginerul pune manual. La usa, o
#      detectie gresita producea o planşa care PAREA corecta.
#
# TOLERANTELE SUNT MASURATE PE PLANSELE LUI DAN, nu alese:
#   jitterul intre etaje (camere potrivite pe pozitie, IE.4 -> IE.5): mediana 6,2 pt, p90 19,3,
#     MAXIM 21,5 pt — atata se misca acelasi lucru de la un etaj la altul;
#   pasul intre apartamente vecine (marcajele „Ap Pn_m" de pe IE.4): MINIM 140 pt, mediana 159;
#   cea mai mica distanta intre doua camere GEMENE de pe aceeasi planşa: 76 pt.
# TOL_POZITIE = 30 pt sta intre ele: 1,4x peste jitterul maxim observat (deci accepta suprapunerea
# reala) si de 2,5 ori sub cea mai mica distanta de confuzie (deci nu poate lega doua apartamente
# diferite). La scara 1:50 inseamna 53 cm.
TOL_POZITIE = 30.0

# FORMA confirma, nu discrimineaza — pozitia a facut deja treaba, fiindca la 30 pt niciun alt
# apartament nu incape. De-aia toleranta de forma e RELATIVA si generoasa: contururile-s desenate cu
# mana, iar un prag strict ar refuza perechi bune fara sa castige nimic la siguranta.
TOL_FORMA_FRAC = 0.08          # 8% din diagonala conturului
TOL_FORMA_MIN = 12.0           # ...dar niciodata sub 12 pt


def _dedup(pts, eps=0.5):
    """Colturi consecutive ~identice -> unul singur (cele doua click-uri ale unui dublu-click)."""
    out = []
    for p in pts or []:
        if not out or abs(p[0] - out[-1][0]) > eps or abs(p[1] - out[-1][1]) > eps:
            out.append((float(p[0]), float(p[1])))
    if len(out) > 1 and abs(out[0][0] - out[-1][0]) <= eps and abs(out[0][1] - out[-1][1]) <= eps:
        out.pop()                                # poligonul e inchis implicit
    return out


def _ancora(pts):
    """Coltul din stanga-sus al bbox-ului. Stabil la translatie si INDEPENDENT de ordinea in care
    au fost desenate colturile — spre deosebire de „primul varf", care depinde de unde a inceput
    inginerul sa apese."""
    return (min(p[0] for p in pts), min(p[1] for p in pts))


def _diagonala(pts):
    return ((max(p[0] for p in pts) - min(p[0] for p in pts)) ** 2
            + (max(p[1] for p in pts) - min(p[1] for p in pts)) ** 2) ** 0.5


def acelasi_apartament(a_pts, b_pts, tol_poz=TOL_POZITIE):
    """(identice?, (dx, dy)) — doua contururi descriu acelasi apartament?

    TREI conditii, in ordinea in care elimina cel mai repede:
      1. acelasi numar de colturi (dupa dedup) — o forma cu 6 colturi nu poate fi una cu 4;
      2. POZITIE: ancorele la cel mult `tol_poz` una de alta (suprapunerea verticala);
      3. FORMA: dupa translatia care suprapune ancorele, fiecare colt in dreptul perechii lui.

    Colturile se compara IN ORDINE, dar cu rotatie: acelasi dreptunghi desenat incepand din alt colt
    da aceeasi forma, si ar fi absurd sa-l refuzam pentru asta."""
    A, B = _dedup(a_pts), _dedup(b_pts)
    if len(A) < 3 or len(A) != len(B):
        return False, None
    ax, ay = _ancora(A)
    bx, by = _ancora(B)
    dx, dy = bx - ax, by - ay
    if (dx * dx + dy * dy) ** 0.5 > tol_poz:
        return False, None
    tol_f = max(TOL_FORMA_MIN, TOL_FORMA_FRAC * _diagonala(A))
    n = len(A)
    for start in range(n):                       # rotatie: acelasi contur, alt colt de pornire
        if all(abs((B[(start + i) % n][0] - dx) - A[i][0]) <= tol_f
               and abs((B[(start + i) % n][1] - dy) - A[i][1]) <= tol_f for i in range(n)):
            return True, (dx, dy)
    return False, None


def perechi_identice(conturi_sursa, conturi_tinta, camere_sursa=None, camere_tinta=None):
    """Perechile (contur sursa, contur tinta, (dx, dy)) intre doua niveluri.

    `camere_*` = {eticheta apartament -> set de nume de camere}, cand se stiu. Atunci se cere SI
    acelasi set de camere: doua apartamente suprapuse cu aceeasi forma dar cu alte incaperi (un
    recompartimentat) nu se mai confunda. Fara camere, raman forma si pozitia — si tot se vede,
    fiindca un etaj negrupat iese GOL."""
    out, luate = [], set()
    for s in (conturi_sursa or []):
        for i, t in enumerate(conturi_tinta or []):
            if i in luate:
                continue
            # TIPUL e prima conditie, inaintea formei: un spatiu comercial de la parter si un
            # apartament de deasupra pot avea exact acelasi contur (des la blocuri — peretii
            # structurali sunt aceiasi), iar copierea ar turna prizele magazinului in apartament.
            # Forma si pozitia n-ar fi prins-o niciodata, fiindca sunt IDENTICE prin constructie.
            if s.get("tip") != t.get("tip"):
                continue
            same, d = acelasi_apartament(s["pts"], t["pts"])
            if not same:
                continue
            if camere_sursa is not None and camere_tinta is not None:
                if camere_sursa.get(s["eticheta"]) != camere_tinta.get(t["eticheta"]):
                    continue
            luate.add(i)
            out.append((s, t, d))
            break
    return out


# Campurile care NU se copiaza: identitatea randului, nivelul (se rescrie) si tot ce e DERIVAT din
# circuite. `circuit_id` copiat ar purta numarul de circuit al apartamentului SURSA pe planşa
# tintei — un numar care arata corect si e al altcuiva.
# `comutat_de` e acelasi defect, cu o treapta mai rau: sunt ID-URI de rand, deci becul copiat ar
# arata spre intrerupatoarele apartamentului SURSA — intrerupatoare care exista, dar sunt in alt
# apartament. Se lasa gol; prima regenerare il completeaza din geometria TINTEI.
_NU_SE_COPIAZA = ("id", "created_at", "updated_at", "project_id", "floor", "circuit_id",
                  "comutat_de")


def plan_copiere(elemente_sursa, dx, dy, floor_tinta, project_id):
    """Elementele de copiat, deja translatate. PUR: nu scrie nimic, doar spune CE ar trebui scris.

    `room` se PASTREAZA: intr-un apartament identic „Dormitor" inseamna aceeasi incapere. E singurul
    loc unde coliziunea de nume de camera e inofensiva, fiindca nu se compara intre apartamente.
    `cable_path` (trasee, benzi LED, contururi) se translateaza punct cu punct, cu ACELASI (dx, dy):
    altfel traseul ar ramane in urma elementelor pe care le leaga."""
    out = []
    for el in (elemente_sursa or []):
        nou = {k: v for k, v in (el or {}).items() if k not in _NU_SE_COPIAZA}
        nou["project_id"] = project_id
        nou["floor"] = floor_tinta
        nou["circuit_id"] = None
        try:
            nou["x"] = float(el["x"]) + dx
            nou["y"] = float(el["y"]) + dy
        except (TypeError, ValueError, KeyError):
            continue
        cp = (el or {}).get("cable_path")
        if isinstance(cp, (list, tuple)) and cp:
            try:
                nou["cable_path"] = [[float(p[0]) + dx, float(p[1]) + dy] for p in cp]
            except (TypeError, ValueError, IndexError):
                nou["cable_path"] = None
        out.append(nou)
    return out


# ── P9: TIPUL de apartament ───────────────────────────────────────────────────────────────────
# DECIZIA LUI DAN: tipul e SURSA DE COPIERE. Apartamentele care si-au primit continutul din acelasi
# apartament sunt de acelasi tip; unul desenat de mana, fara copiere, e un tip nou.
#
# Mecanismul exista de la P4 si nu se adauga nimic: `copiat_din` pe conturul TINTA. Tipul e
# RADACINA lantului — daca A s-a copiat in B si B in C, toate trei au aceeasi radacina, deci acelasi
# tip. Fara lant, un apartament e propria lui radacina.
#
# UN SINGUR CRITERIU, si nu din lene. Tentatia era sa cad pe geometrie cand `copiat_din` lipseste
# (P4 stie deja sa spuna daca doua contururi descriu acelasi apartament). Am lasat-o afara: copierea
# e ACTUL EXPLICIT prin care inginerul spune „astea-s la fel", iar desenarea a doua contururi
# identice nu spune asta. Cu doua criterii, tipul ar fi depins de care raspunde primul.
#
# DOUA CONSECINTE, amandoua vizibile si amandoua cu acelasi remediu (ruleaza copierea):
#   - `copiat_din` e ON DELETE SET NULL: daca inginerul sterge conturul SURSA, tinta devine radacina
#     si apare un tip in plus. E corect — dovada ca erau la fel a disparut odata cu sursa, iar a
#     pastra tipul ar insemna sa tinem o afirmatie fara temei. Consecinta se VEDE (o schema in plus),
#     nu se ascunde.
#   - doua apartamente identice desenate AMBELE de mana dau DOUA tipuri. Acceptabil: proiectul iese
#     cu o schema in plus, nu cu una gresita.
_RX_ETICH = re.compile(r"^(?:P|SP)(\d+)(?:_(\d+))?$")


def _ordine_eticheta(e):
    """Cheie de sortare pentru etichete de apartament: „P1" < „P2" < „P1_1" < „P1_10"."""
    m = _RX_ETICH.match(str(e or "").strip())
    if not m:
        return (9999, 9999, str(e or ""))
    return (int(m.group(1)), int(m.group(2) or 0), "")


def tipuri_apartament(plan_elements, floor_canonic, floor_index):
    """Tipurile de apartament ale proiectului: [{nume, radacina_id, membri, domeniu}].

    `membri` = [(nivel, eticheta)], ordonate de jos in sus si apoi dupa eticheta.
    `domeniu` = textul pe care schema si-l declara singura, ca AP-1 de pe IE.25 al lui Dan:
        „PARTER: P1..P4 · ETAJ 1: P1_1..P1_9".

    Numerotarea AP-1, AP-2... urmeaza RADACINILE, in ordinea in care le intalneste inginerul:
    nivelul de jos intai, apoi de sus in jos si de la stanga la dreapta pe nivel — exact ordinea in
    care `conturi_nivel` le numeroteaza. Asa tipul 1 e cel din care s-a copiat prima oara."""
    els = list(plan_elements or [])
    conturi = {}                                    # id contur -> (nivel, eticheta, ordine pe nivel)
    parinte = {}
    for fk in sorted({floor_canonic(e.get("floor")) for e in els}, key=floor_index):
        for i, c in enumerate(conturi_nivel(els, fk, floor_canonic, tipuri=(CONTUR,))):
            cid = (c["el"] or {}).get("id")
            if cid is None:
                continue
            conturi[cid] = (fk, c["eticheta"], i)
            src = (c["el"] or {}).get("copiat_din")
            if src:
                parinte[cid] = src

    def radacina(cid):
        """Capatul lantului. Limita de pasi: un ciclu introdus de date gresite n-are voie sa blocheze
        generarea — se opreste si trateaza nodul curent ca radacina."""
        vazut = set()
        while cid in parinte and parinte[cid] in conturi and cid not in vazut:
            vazut.add(cid)
            cid = parinte[cid]
        return cid

    grupe = {}
    for cid in conturi:
        grupe.setdefault(radacina(cid), []).append(cid)

    def cheie_radacina(r):
        fk, _et, ordine = conturi[r]
        return (floor_index(fk), ordine)

    out = []
    for n, r in enumerate(sorted(grupe, key=cheie_radacina), start=1):
        membri = sorted(((conturi[c][0], conturi[c][1]) for c in grupe[r]),
                        key=lambda m: (floor_index(m[0]), _ordine_eticheta(m[1])))
        pe_nivel = {}
        for niv, et in membri:
            pe_nivel.setdefault(niv, []).append(et)
        bucati = []
        for niv in sorted(pe_nivel, key=floor_index):
            ee = pe_nivel[niv]
            bucati.append("%s: %s" % (niv.upper(),
                                      ee[0] if len(ee) == 1 else "%s..%s" % (ee[0], ee[-1])))
        out.append({"nume": "AP-%d" % n, "radacina_id": r, "membri": membri,
                    "domeniu": " · ".join(bucati)})
    return out




def copieri_pentru_nivel(plan_elements, floor_tinta, project_id, floor_canonic, floor_index):
    """CE ar trebui copiat pe nivelul `floor_tinta`. PUR — nu scrie nimic, nu atinge baza.

    SURSA e cel mai apropiat nivel de DEDESUBT care are un apartament identic CU CONTINUT. „De
    dedesubt" fiindca asa lucreaza inginerul: face parterul, apoi urca. Cel mai apropiat, fiindca
    daca a modificat etajul 1 fata de parter, etajul 2 trebuie sa semene cu etajul 1, nu cu parterul.

    Se sare peste un apartament tinta daca:
      - are deja `copiat_din` setat  -> s-a copiat o data; ce-a facut inginerul dupa ramane al lui;
      - are deja elemente inauntru   -> a lucrat acolo, nu-i turnam peste.
    Amandoua garzile sunt necesare: prima tine minte ca s-a copiat chiar daca inginerul a sters TOT
    ce-a primit; a doua apara un apartament lucrat de mana, care n-a fost niciodata copiat.

    Intoarce {"copieri": [...], "sarite": [...]} — si sarite, ca interfata sa poata SPUNE de ce n-a
    facut nimic. Un etaj care ramane gol fara explicatie arata identic cu unul uitat."""
    els = list(plan_elements or [])
    ft = floor_canonic(floor_tinta)
    conturi_t = conturi_nivel(els, ft, floor_canonic)
    if not conturi_t:
        return {"copieri": [], "sarite": [], "motiv": "nivelul nu are contururi de apartament"}

    # nivelurile de DEDESUBT, de la cel mai apropiat in jos
    niveluri = sorted({floor_canonic(e.get("floor")) for e in els},
                      key=lambda f: floor_index(f), reverse=True)
    mai_jos = [f for f in niveluri if floor_index(f) < floor_index(ft)]

    copieri, sarite = [], []
    for t in conturi_t:
        if (t["el"] or {}).get("copiat_din"):
            sarite.append({"tinta": t["eticheta"], "motiv": "a primit deja continut"})
            continue
        els_t = [e for e in els
                 if floor_canonic(e.get("floor")) == ft
                 and (e.get("element_type") or "") != CONTUR
                 and apartament_al_elementului(e, [t])]
        if els_t:
            sarite.append({"tinta": t["eticheta"], "motiv": "are deja %d elemente" % len(els_t)})
            continue
        gasit = None
        for fs in mai_jos:
            conturi_s = conturi_nivel(els, fs, floor_canonic)
            per = perechi_identice(conturi_s, [t])
            if not per:
                continue
            s, _t, d = per[0]
            els_s = [e for e in els
                     if floor_canonic(e.get("floor")) == fs
                     and (e.get("element_type") or "") != CONTUR
                     and apartament_al_elementului(e, [s])]
            if not els_s:
                continue                         # identic, dar gol — nu-i sursa, cautam mai jos
            gasit = (fs, s, d, els_s)
            break
        if not gasit:
            sarite.append({"tinta": t["eticheta"],
                           "motiv": "niciun apartament identic cu continut pe nivelurile de dedesubt"})
            continue
        fs, s, (dx, dy), els_s = gasit
        copieri.append({
            "tinta": t["eticheta"], "tinta_id": (t["el"] or {}).get("id"),
            "sursa": s["eticheta"], "sursa_id": (s["el"] or {}).get("id"), "sursa_nivel": fs,
            "dx": round(dx, 2), "dy": round(dy, 2),
            "elemente": plan_copiere(els_s, dx, dy, ft, project_id),
        })
    return {"copieri": copieri, "sarite": sarite}
