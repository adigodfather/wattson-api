import base64
import gc
import math
import re
import unicodedata

import fitz  # PyMuPDF

# Roșu pentru planșa de iluminat (RGB 0-1)
RED = (0.86, 0.16, 0.16)
_BULB_YELLOW = (0.980, 0.780, 0.459)   # #FAC775 — umplutură DOAR la aplica_senzor

# Pattern suprafață cameră: "A: 20.41 mp" / "A:20.41mp" / "S = 12.3 mp" etc.
AREA_RE = re.compile(r'\b(?:A|S)\s*[:=]?\s*\d{1,3}[.,]\d{1,2}\s*mp\b', re.IGNORECASE)


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _group_words_by_line(words):
    """Grupează word-urile fitz pe aceeași linie logică (block, line).
    words = listă de tuple (x0,y0,x1,y1,text,block,line,word_no)."""
    lines = {}
    for w in words:
        x0, y0, x1, y1, text = w[0], w[1], w[2], w[3], w[4]
        block, line = w[5], w[6]
        key = (block, line)
        if key not in lines:
            lines[key] = {"words": [], "x0": x0, "y0": y0, "x1": x1, "y1": y1}
        g = lines[key]
        g["words"].append((x0, text))
        g["x0"] = min(g["x0"], x0)
        g["y0"] = min(g["y0"], y0)
        g["x1"] = max(g["x1"], x1)
        g["y1"] = max(g["y1"], y1)
    # reconstituie textul liniei în ordinea x
    out = []
    for key, g in lines.items():
        g["words"].sort(key=lambda t: t[0])
        g["text"] = " ".join(t[1] for t in g["words"])
        out.append(g)
    return out


def _find_room_centers(page, W, H):
    """Returnează centrele camerelor pe baza ancorei de suprafață 'A: NN mp'.
    Exclude zona cartușului (convenție relativă identică cu cartus_swap)."""
    words = page.get_text("words")
    lines = _group_words_by_line(words)
    centers = []
    for g in lines:
        # exclude top 10% (titlu) și zona cartuș (jos-stânga jumătate SAU treime-dreapta)
        if g["y0"] < 0.10 * H:
            continue
        if (g["y0"] > 0.50 * H) or (g["x0"] > 0.66 * W):
            continue
        if AREA_RE.search(g["text"]):
            cx = (g["x0"] + g["x1"]) / 2.0
            cy = (g["y0"] + g["y1"]) / 2.0
            centers.append({"x": cx, "y": cy, "label": g["text"]})
    return centers


def _draw_bulb(page, cx, cy, element_type="aplica_tavan", r=9.0, y_offset=-22, scale=1.0):
    """Simbol corp de iluminat PE TIP (contur roșu; senzor cu umplutură galbenă), portat din Konva:
      aplica_tavan: cerc + X | aplica_perete: semicerc + punct | lustra_led: cerc+X + 2 inele |
      banda_led: dreptunghi alungit + liniuțe | aplica_senzor: cerc + X cu fill galben.
    y_offset: deplasare verticală (cale text_regex -22; vision_bbox/regenerare 0). aplica_tavan = aspectul vechi.
    scale: factor pe TOATE razele/offset-urile (forma identica, mai mica) — pt. legenda (L3). scale=1.0 = neschimbat."""
    s = scale
    cx0 = cx; cy0 = cy + y_offset   # centrul simbolului

    def X(rr):  # X = două diagonale la 45° pe rază rr
        d = rr * math.cos(math.radians(45))
        page.draw_line(fitz.Point(cx0 - d, cy0 - d), fitz.Point(cx0 + d, cy0 + d), color=RED, width=1.2)
        page.draw_line(fitz.Point(cx0 - d, cy0 + d), fitz.Point(cx0 + d, cy0 - d), color=RED, width=1.2)

    center = fitz.Point(cx0, cy0)
    et = element_type or "aplica_tavan"
    if et == "aplica_perete":
        page.draw_sector(center, fitz.Point(cx0 + 9 * s, cy0), 180, color=RED, width=1.2, fullSector=True)
        page.draw_circle(fitz.Point(cx0, cy0 + 4 * s), 1.8 * s, color=RED, fill=RED, width=0.8)
    elif et == "lustra_led":
        page.draw_circle(center, 24 * s, color=RED, width=1.2)
        page.draw_circle(center, 18 * s, color=RED, width=1.2)
        page.draw_circle(center, 12 * s, color=RED, width=1.2)
        X(12 * s)
    elif et == "banda_led":
        page.draw_rect(fitz.Rect(cx0 - 30 * s, cy0 - 7 * s, cx0 + 30 * s, cy0 + 7 * s), color=RED, width=1.2)
        for tx in (-18, -6, 6, 18):
            page.draw_line(fitz.Point(cx0 + tx * s, cy0 - 3 * s), fitz.Point(cx0 + tx * s, cy0 + 3 * s), color=RED, width=1.0)
    elif et == "aplica_senzor":
        page.draw_circle(center, 9 * s, color=RED, fill=_BULB_YELLOW, width=1.2)
        X(9 * s)
    else:  # aplica_tavan (default) — NESCHIMBAT: cerc + X la raza r
        page.draw_circle(center, r * s, color=RED, width=1.2)
        X(r * s)


# eticheta becului: "{Nume} LED[ SP] {power}W" — power_w gol/None -> fara watt (NU inventa default)
_BULB_NAME = {"aplica_tavan": "Aplica", "aplica_perete": "Aplica", "lustra_led": "Lustra",
              "aplica_senzor": "Aplica", "banda_led": "Banda"}
_BULB_TOP = {"lustra_led": 25, "banda_led": 8}   # extinderea simbolului in sus (pt. pozitia etichetei)


def _norm_name_ro(s):
    """Nume normalizat pt. matching pe camera (lowercase, fara diacritice, fara sufixe de etaj)."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    for suf in (" (parter)", " (etaj)", " (mansarda)"):
        s = s.replace(suf, "")
    return " ".join(s.split())


def _bulb_rule_for_room(name):
    """Regula TIP + PUTERE corp de iluminat pe camera (oglinda prizeRuleForRoom; valori BASIC,
    inginerul le schimba in editor). Decide DOAR tip+putere — CATE corpuri decide _vision_centers.
      terase (acces + acoperita)     -> aplica_senzor 30W  (SP: FARA intrerupator + direct TEG,
                                        regula existenta din compute_cables/_switch_centers)
      living / camera de zi / bucatarie -> lustra_led 40W
      dormitoare / birouri              -> lustra_led 30W
      restul (bai, holuri, camara, dressing, spalator, depozitare, spatiu tehnic) -> aplica_tavan 25W
    Ordine specific->generic (ca la prize). Returneaza (element_type, power_w)."""
    n = _norm_name_ro(name)
    if "teras" in n:
        return ("aplica_senzor", 30)
    if "living" in n or "camera de zi" in n or " zi" in n or n == "zi" or "bucatar" in n:
        return ("lustra_led", 40)
    if "dormitor" in n or "birou" in n:
        return ("lustra_led", 30)
    return ("aplica_tavan", 25)


def _bulb_label(element_type, power_w, circuit_id=None):
    name = _BULB_NAME.get(element_type, "Corp")
    suffix = " SP" if element_type == "aplica_senzor" else ""
    txt = "{} LED{}".format(name, suffix)
    if power_w is not None and power_w != "":
        try:
            txt += " {}W".format(int(power_w))
        except (TypeError, ValueError):
            pass
    cid = (circuit_id or "").strip()                 # prefix circuit: "C1 - Aplica LED 25W" (TE-CT: "C1-TECT - ...")
    return "{} - {}".format(cid, txt) if cid else txt   # fara circuit_id -> eticheta veche (backward-compat)


def _bulb_label_spec(cx, cy, element_type, power_w, circuit_id=None):
    """Spec eticheta bec (pozitia DE BAZA, identica cu desenul vechi): text centrat pe cx, DEASUPRA
    simbolului (top din _BULB_TOP). None daca nu e nimic de scris. Desenul efectiv = _draw_label_spec."""
    txt = _bulb_label(element_type, power_w, circuit_id)
    if not txt:
        return None
    fs = 9.0                                      # putin mai mare (era 7.5)
    w = len(txt) * fs * 0.50                      # latime aproximativa (centrare; bold = chars mai late)
    top = _BULB_TOP.get(element_type, 10)
    return {"text": txt, "x0": cx - w / 2.0, "y": cy - top - 5.0, "w": w, "fs": fs,
            "font": "hebo", "color": RED}         # hebo = Helvetica BOLD


_LBL_LINE_H = 10.0   # inaltimea unui rand suplimentar de eticheta (O2: wrap pe 2 randuri)


def _wrap_label_25(text, width=25):
    """O2: rupe textul PE CUVINTE la <=width caractere per rand, MAX 2 randuri; ce depaseste randul 2
    se trunchiaza cu '...'. Un cuvant mai lung decat width ramane singur pe rand (nu se sparge)."""
    words = str(text or "").split()
    l1, rest = "", None
    for i, w in enumerate(words):
        cand = (l1 + " " + w).strip()
        if len(cand) <= width or not l1:
            l1 = cand
        else:
            rest = words[i:]
            break
    if not rest:
        return [l1] if l1 else []
    l2 = " ".join(rest)
    if len(l2) > width:
        l2 = l2[:width - 3].rstrip() + "..."
    return [l1, l2]


def _draw_label_spec(page, sp):
    """Deseneaza un spec de eticheta (x0 = stanga, y = baseline). O2: spec-ul poate avea `lines`
    (max 2 randuri, echipamente de incalzire) -> fiecare rand la +_LBL_LINE_H sub precedentul."""
    lines = sp.get("lines") or [sp["text"]]
    for i, ln in enumerate(lines):
        page.insert_text(fitz.Point(sp["x0"], sp["y"] + i * _LBL_LINE_H), ln,
                         fontsize=sp["fs"], fontname=sp["font"], color=sp["color"])


def _resolve_label_overlaps(specs, pad=1.0, max_steps=40):
    """ANTI-COLIZIUNE etichete (becuri + prize, comuna): etichetele care s-ar suprapune se STIVUIESC
    IN SUS (in sus = departe de simbol, care e mereu SUB eticheta lui — in jos ar intra peste simbol).
    Ordine determinista (y, x0): cea mai de sus/stanga ramane PE LOC, urmatoarea urca cate un rand
    (fs+2) pana nu mai atinge nimic. Etichetele fara suprapunere NU se misca deloc (pozitia de baza
    ramane identica cu desenul vechi). Muta DOAR pozitia etichetelor — simboluri/text neatinse.
    O2: spec-urile cu `lines` (2 randuri) au UN SINGUR dreptunghi cu inaltime dubla (nu 2 spec-uri —
    resolverul le-ar stivui separat si randurile s-ar desparti)."""
    def bb(sp):
        extra = (len(sp.get("lines") or [1]) - 1) * _LBL_LINE_H
        return (sp["x0"] - pad, sp["y"] - sp["fs"] - pad, sp["x0"] + sp["w"] + pad, sp["y"] + extra + pad)

    def hit(a, b):
        return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]

    placed = []
    for i in sorted(range(len(specs)), key=lambda k: (round(specs[k]["y"], 1), round(specs[k]["x0"], 1))):
        sp = specs[i]
        step = sp["fs"] + 2.0
        for _ in range(max_steps):
            b = bb(sp)
            if not any(hit(b, p) for p in placed):
                break
            sp["y"] -= step
        placed.append(bb(sp))
    return specs


def _draw_bulb_label(page, cx, cy, element_type, power_w, circuit_id=None):
    """Eticheta DEASUPRA becului, centrata orizontal pe cx (rosu, lizibil). Prefix circuit (C1/C2/C1-TECT).
    Desen IMEDIAT (fara anti-coliziune) — redraw_from_plan_elements foloseste spec+resolve in loc."""
    sp = _bulb_label_spec(cx, cy, element_type, power_w, circuit_id)
    if sp:
        _draw_label_spec(page, sp)


# ── C4: simbol PRIZA pe PDF (semicerc curba SUS + 2 contacte) + eticheta "C{circuit} - h={h}m". ──
_PRIZA_COLOR = (0.082, 0.396, 0.753)   # ALBASTRU #1565C0 (forta) — coerent cu cablurile, distinct de iluminat (rosu)


_PRIZA_TURQ = (0.247, 0.816, 0.788)    # #3fd0c9 — umplutura prizelor interioare
_PRIZA_TEAL = (0.059, 0.463, 0.431)    # #0f766e — contur IP44 (teal inchis, distinct de interior)
_PRIZA_DARK = (0.051, 0.235, 0.478)    # #0d3c7a — contur alimentare directa (albastru inchis)

# ── Receptor RETEA INTERNET (RJ45): simbol propriu (VIOLET + router alb + 3 unde WiFi). ──
_NET_FILL  = (0.729, 0.408, 0.784)     # #BA68C8 — dreptunghi VIOLET plin (distinct de albastrul prizei)
_NET_EDGE  = (0.557, 0.141, 0.667)     # #8E24AA — contur violet inchis
_NET_WHITE = (1.0, 1.0, 1.0)           # router + unde WiFi (alb)


def _draw_priza(page, cx, cy, element_type="priza_simpla", scale=1.0, rotation=0.0, wall_inward=None, wall_along=None):
    """Simbol priza (portat din Konva): semicerc (SPATELE, curba JOS in local) + 2 contacte
    DEASUPRA diametrului (DESCHIDEREA prizei). Dimensiune = editorul UI (scale*0.96, nu 1.6:
    PDF era ~png_scale=1.667x mai mare ca UI); IP44 caseta turcoaz + semicerc ALB (contur teal),
    alimentare directa albastru inchis plin.
    rotation (radiani, sens orar): 0=contacte/deschidere SUS, pi=JOS, +pi/2=DREAPTA, -pi/2=STANGA —
    baza (diametrul) sta pe perete, CONTACTELE spre interiorul camerei (ca la _draw_switch).
    PUNCTUL 3: daca wall_inward (versor spre interior) e dat, deseneaza in schimb BARA DE MONTAJ pe
    perete (paralela cu el, along) + semicercul sprijinit pe bara, bulbuc spre INTERIOR (nu ingropat).
    Orientarea vine din bbox (inward/along), NU din rotation. wall_inward=None -> desenul vechi."""
    s = scale * 0.96                    # dimensiune = editorul UI (era 1.6 -> PDF ~1.667x prea mare)
    C = _PRIZA_COLOR

    if wall_inward is not None:
        ix, iy = float(wall_inward[0]), float(wall_inward[1])
        _n = math.hypot(ix, iy) or 1.0; ix, iy = ix / _n, iy / _n            # versor interior
        if wall_along is not None:
            ax, ay = float(wall_along[0]), float(wall_along[1])
        else:
            ax, ay = -iy, ix                                                 # perpendicular pe inward
        _na = math.hypot(ax, ay) or 1.0; ax, ay = ax / _na, ay / _na         # versor paralel cu peretele
        r = 8.0 * s
        et = element_type or "priza_simpla"

        def bar(bx, by, half):          # BARA DE MONTAJ pe perete (segment paralel cu peretele)
            page.draw_line(fitz.Point(bx - ax * half, by - ay * half),
                           fitz.Point(bx + ax * half, by + ay * half), color=C, width=1.7)

        def halfdisc(bx, by, rr, fill=_PRIZA_TURQ, edge=C):   # semicerc sprijinit pe bara, bulbuc spre inward
            pts = [fitz.Point(bx - rr * math.cos(math.pi * k / 16.0) * ax + rr * math.sin(math.pi * k / 16.0) * ix,
                              by - rr * math.cos(math.pi * k / 16.0) * ay + rr * math.sin(math.pi * k / 16.0) * iy)
                   for k in range(17)]
            page.draw_polyline(pts, color=edge, fill=fill, width=1.4, closePath=True)   # inchide pe bara (diametru)

        if et == "priza_dubla":
            bar(cx, cy, 2.0 * r)
            for sgn in (-1.0, 1.0):     # 2 semicercuri de-a lungul barei
                halfdisc(cx + sgn * r * ax, cy + sgn * r * ay, r * 0.85)
        elif et == "priza_16a":         # ALIMENTARE DIRECTA = cerc plin, sprijinit pe bara (offset spre interior)
            bar(cx, cy, r * 0.9)
            page.draw_circle(fitz.Point(cx + ix * r, cy + iy * r), r * 0.9,
                             color=_PRIZA_DARK, fill=_PRIZA_COLOR, width=1.4)
        elif et == "priza_exterior_ip44":
            bar(cx, cy, r * 1.15)
            bxc, byc = cx + ix * r * 0.55, cy + iy * r * 0.55                 # caseta offset spre interior
            hw, hh = r * 1.25, r * 1.1
            corners = [fitz.Point(bxc - ax * hw - ix * hh, byc - ay * hw - iy * hh),
                       fitz.Point(bxc + ax * hw - ix * hh, byc + ay * hw - iy * hh),
                       fitz.Point(bxc + ax * hw + ix * hh, byc + ay * hw + iy * hh),
                       fitz.Point(bxc - ax * hw + ix * hh, byc - ay * hw + iy * hh)]
            page.draw_polyline(corners, color=_PRIZA_TEAL, fill=_PRIZA_TURQ, width=1.0, closePath=True)
            halfdisc(cx, cy, r, fill=(1, 1, 1), edge=_PRIZA_TEAL)
            page.insert_text(fitz.Point(cx + ix * (r * 2.2) - ax * 10 * s, cy + iy * (r * 2.2) - ay * 10 * s + 6),
                             "IP44", fontsize=6.0 * s, fontname="hebo", color=_PRIZA_TEAL)
        else:                           # priza_simpla
            bar(cx, cy, r)
            halfdisc(cx, cy, r)
            for off in (-0.34, 0.34):   # 2 contacte (fante) in interiorul discului, spre inward
                page.draw_line(fitz.Point(cx + off * r * ax + 0.28 * r * ix, cy + off * r * ay + 0.28 * r * iy),
                               fitz.Point(cx + off * r * ax + 0.72 * r * ix, cy + off * r * ay + 0.72 * r * iy),
                               color=C, width=1.0)
        return

    cosr, sinr = math.cos(rotation or 0.0), math.sin(rotation or 0.0)

    def P(dx, dy):                      # punct local rotit in jurul ancorei (y-down => sens orar)
        return fitz.Point(cx + dx * cosr - dy * sinr, cy + dx * sinr + dy * cosr)

    def disc(dx, r, fill=_PRIZA_TURQ, edge=C):   # semicerc (curba JOS in local = spre perete): sector rotit
        page.draw_sector(P(dx, 0), P(dx - r, 0), 180, color=edge, fill=fill, width=1.4, fullSector=True)

    def contacts(dx, col=C):            # 2 contacte DEASUPRA diametrului (local -y = spre camera dupa rotatie)
        for off in (-3.0 * s, 3.0 * s):
            page.draw_line(P(dx + off, -2.0 * s), P(dx + off, -6.0 * s), color=col, width=1.1)

    et = element_type or "priza_simpla"
    if et == "priza_dubla":
        disc(-8 * s, 7 * s); contacts(-8 * s)
        disc(8 * s, 7 * s);  contacts(8 * s)
    elif et == "priza_16a":   # ALIMENTARE DIRECTA = cerc PLIN albastru inchis (iese in evidenta)
        page.draw_circle(fitz.Point(cx, cy), 8 * s, color=_PRIZA_DARK, fill=_PRIZA_COLOR, width=1.4)
    elif et == "priza_exterior_ip44":
        # caseta turcoaz cu contur teal (rotita ca polilinie), semicerc ALB cu contur teal
        corners = [P(-11 * s, -10 * s), P(11 * s, -10 * s), P(11 * s, 11 * s), P(-11 * s, 11 * s)]
        page.draw_polyline(corners, color=_PRIZA_TEAL, fill=_PRIZA_TURQ, width=1.0, closePath=True)
        disc(0, 8 * s, fill=(1, 1, 1), edge=_PRIZA_TEAL); contacts(0, col=_PRIZA_TEAL)
        page.insert_text(fitz.Point(cx - 10 * s, cy + 18 * s + 6), "IP44",
                         fontsize=6.0 * s, fontname="hebo", color=_PRIZA_TEAL)
    else:  # priza_simpla
        disc(0, 8 * s); contacts(0)


def _draw_internet(page, cx, cy, scale=1.0):
    """Simbol RETEA INTERNET (RJ45): dreptunghi VIOLET plin + router alb (contur + 2 LED-uri albe
    + o liniuta alba) in jumatatea de jos + 3 unde WiFi albe arcuite deasupra (tot mai late in sus).
    Geometrie IDENTICA cu internetSymbol din plan-editor.tsx (UI=PDF). Dimensiune = editorul UI * u
    (px-PNG -> pt-PDF, ~1/png_scale 1.667), ca la prize. scale<1 -> mai mic (pt. celula legendei)."""
    u = 0.6 * scale
    def P(dx, dy):
        return fitz.Point(cx + dx * u, cy + dy * u)
    def wifi(r):                                     # unda WiFi = arc alb centrat la (0,5), deschis in SUS
        pts = [fitz.Point(cx + (r * u) * math.cos(math.radians(210 + 12 * i)),
                          cy + 5 * u + (r * u) * math.sin(math.radians(210 + 12 * i))) for i in range(11)]
        page.draw_polyline(pts, color=_NET_WHITE, width=1.0)
    # caseta turcoaz plina (contur teal)
    page.draw_rect(fitz.Rect(P(-15, -15), P(15, 15)), color=_NET_EDGE, fill=_NET_FILL, width=1.2, radius=0.16)
    # router: contur alb (fara fill) + 2 LED-uri (stanga) + liniuta (dreapta)
    page.draw_rect(fitz.Rect(P(-9, 4), P(9, 12)), color=_NET_WHITE, width=1.1)
    page.draw_circle(P(-5.5, 8), 1.3 * u, color=_NET_WHITE, fill=_NET_WHITE)
    page.draw_circle(P(-2.5, 8), 1.3 * u, color=_NET_WHITE, fill=_NET_WHITE)
    page.draw_line(P(2, 8), P(7, 8), color=_NET_WHITE, width=1.1)
    # 3 unde WiFi deasupra routerului (tot mai late)
    wifi(4.0); wifi(7.5); wifi(11.0)


def _fmt_height(h):
    """Inaltime curata (trim zerouri): 0.6 -> '0.6', 1.1 -> '1.1', 1.0 -> '1'. None/gol -> None."""
    if h is None or h == "":
        return None
    try:
        return ("%.2f" % float(h)).rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return None


def _priza_label(el):
    """Eticheta priza: 'C{circuit_id} - h={mount_height_m}m'. Circuit lipsa -> doar inaltime;
    ambele lipsa -> ''. Ex: circuit_id='C4', mount_height_m=0.6 -> 'C4 - h=0.6m'."""
    parts = []
    cid = ((el or {}).get("circuit_id") or "").strip()
    if cid:
        parts.append(cid)
    h = _fmt_height((el or {}).get("mount_height_m"))
    if h is not None:
        parts.append("h=%sm" % h)
    return " - ".join(parts)


def _priza_label_spec(cx, cy, el, inward=None):
    """Spec eticheta priza 'C{circuit} - h={h}m': BOLD (hebo, ca becurile) + fs 9.0 (era helv 7.5) +
    plasata IN FATA prizei, pe directia `inward` (spre INTERIORUL camerei, aceeasi orientare ca
    simbolul) -> in spatiul liber, NU peste hasura peretelui (priza sta PE perete). Perete vertical
    (inward orizontal) -> eticheta LATERAL de priza, centrata vertical; perete orizontal -> eticheta
    SUB/DEASUPRA prizei, in camera. Fara inward -> deasupra (ca inainte), doar font/marime noi."""
    txt = _priza_label(el)
    if not txt:
        return None
    fs = 9.0                                       # o treapta+ (era 7.5); = becurile (consistent)
    w = len(txt) * fs * 0.50                       # bold -> caractere mai late (ca la becuri)
    if inward is not None:
        ix, iy = float(inward[0]), float(inward[1])
        if abs(ix) >= abs(iy):                     # perete VERTICAL -> text lateral, in camera
            x0 = (cx + 22.0) if ix > 0 else (cx - 22.0 - w)
            y = cy + fs * 0.35                     # ~centrat vertical pe priza
        else:                                      # perete ORIZONTAL -> text sub/deasupra, in camera
            x0 = cx - w / 2.0
            y = (cy + 30.0 + fs * 0.8) if iy > 0 else (cy - 30.0)
        return {"text": txt, "x0": x0, "y": y, "w": w, "fs": fs,
                "font": "hebo", "color": _PRIZA_COLOR}
    return {"text": txt, "x0": cx - w / 2.0, "y": cy - 26.0, "w": w, "fs": fs,
            "font": "hebo", "color": _PRIZA_COLOR}


def _draw_priza_label(page, cx, cy, el, inward=None):
    """Eticheta prizei, desen IMEDIAT (fara anti-coliziune) — redraw foloseste spec+resolve in loc."""
    sp = _priza_label_spec(cx, cy, el, inward=inward)
    if sp:
        _draw_label_spec(page, sp)


# ── LEGENDA (L2/L3): randuri din plan_elements + text DESCRIPTIV (separat de etichetele de pe plan) ──
# Nume de baza becuri in legenda. Tablouri/intrerupatoare = text descriptiv. FARA diacritice (ca restul planului).
_LEGEND_BULB_NAME = {"aplica_tavan": "Aplica", "aplica_perete": "Aplica", "lustra_led": "Lustra",
                     "banda_led": "Banda", "aplica_senzor": "Aplica"}
_PANEL_LEGEND_NAME = {
    "tablou_teg":    "TEG: Tablou electric general (montaj h=1.5m)",
    "tablou_te_ct":  "TE-CT: Tablou electric camera-tehnica (montaj h=1.5m)",
    "tablou_tes":    "TES: Tablou electric secundar (montaj h=1.5m)",
    "transformator": "Transformator",
}
_SWITCH_LEGEND_TEXT = {
    "intrerupator_simplu":    "Intrerupator simplu montat la h=1.10 m",
    "intrerupator_dublu":     "Intrerupator dublu montat la h=1.10 m",
    "intrerupator_triplu":    "Intrerupator triplu montat la h=1.10 m",
    "intrerupator_cap_scara": "Intrerupator cap-scara montat la h=1.10 m",
}
# Nume prize in legenda forta (citibile). Alimentari (receptor) = "Alimentare {label}"; internet = text fix.
_LEGEND_PRIZA_NAME = {
    "priza_simpla":        "Priza simpla",
    "priza_dubla":         "Priza dubla",
    "priza_16a":           "Alimentare directa (consumator)",
    "priza_exterior_ip44": "Priza exterior IP44",
}
# Ordini deterministice in legenda (seturile _PANEL_TYPES/_SWITCH_TYPES/_PRIZA_TYPES sunt neordonate).
_PANEL_ORDER = ("tablou_teg", "tablou_te_ct", "tablou_tes", "transformator")
_SWITCH_ORDER = ("intrerupator_simplu", "intrerupator_dublu", "intrerupator_triplu", "intrerupator_cap_scara")
_PRIZA_ORDER = ("priza_simpla", "priza_dubla", "priza_16a", "priza_exterior_ip44")
# Cablu pe plan_type: iluminat 1.5, forta (prize) 2.5. Dedicatele (forta) adauga sectiunile lor.
_LEGEND_CABLE_ILUMINAT = "Cablu / Manunchi cablu CYY-F 3x1.5 mmp"
_LEGEND_CABLE_FORTA    = "Cablu / Manunchi cablu CYY-F 3x2.5 mmp"


def _legend_pw(pw):
    """Normalizeaza puterea pt. grupare/sortare: int daca se poate, altfel None (gol/None/nenumeric)."""
    if pw is None or pw == "":
        return None
    try:
        return int(float(pw))
    except (TypeError, ValueError):
        return None


def _legend_label(kind, element_type, power_w=None, label=None):
    """Text DESCRIPTIV pt. LEGENDA (separat de _bulb_label, care ramane SCURT pt. etichetele de pe plan):
      - bulb / switch / panel (iluminat); prize / receptor(alimentare) / internet (forta).
      - cablul e construit direct in build_legend_rows (plan_type-aware). Putere None -> fara segment W."""
    if kind == "switch":
        return _SWITCH_LEGEND_TEXT.get(element_type, element_type)
    if kind == "panel":
        return _PANEL_LEGEND_NAME.get(element_type, element_type)
    if kind == "prize":
        return _LEGEND_PRIZA_NAME.get(element_type, "Priza")
    if kind == "receptor":
        return "Alimentare " + (str(label).strip() if label else "receptor")
    if kind == "internet":
        return "Priza date / internet (RJ45)"
    # bulb (default)
    name = _LEGEND_BULB_NAME.get(element_type, "Corp")
    base = "{} LED cu senzor de prezenta".format(name) if element_type == "aplica_senzor" else "{} LED".format(name)
    pw = _legend_pw(power_w)
    if pw is not None:
        base += " cu puterea de {}W".format(pw)
    return base


def _norm_cable_display(cbl):
    """Format UNIC 'CYY-F NxM' din formatele variate din DB ('5x4 mm2 CYYF', 'CYY-F 3x2.5',
    'CYY-F 5x6mmp'). None/neparsabil -> textul brut trimmat."""
    m = re.search(r"(\d+)\s*[xX]\s*([\d.]+)", str(cbl or ""))
    if not m:
        return str(cbl or "").strip()
    sec = ("%s" % m.group(2)).rstrip("0").rstrip(".") or m.group(2)
    return "CYY-F %sx%s" % (m.group(1), sec)


def _legend_cable_rows(elements, plan_type, present, feeds=None, circuits=None, cross_floor=None):
    """Randuri de cablu pt. legenda, din CIRCUITELE REALE (sursa unica), pe plan_type:
    iluminat -> 3x1.5; forta -> 3x2.5 (prize) + sectiunile DEDICATELOR (din circuits, NU re-derivate
    din puteri default) daca difera de 2.5 + COLOANE (feed sub_tablou TEG->TE-CT/TES, teal).
    circuits lipsa (proiect vechi) -> FALLBACK la re-derivarea din puteri default (comportamentul vechi)."""
    if plan_type != "forta":
        return [{"kind": "cable", "text": _LEGEND_CABLE_ILUMINAT}]
    texts = []
    if present & _PRIZA_TYPES:
        texts.append(_LEGEND_CABLE_FORTA)                           # 2.5 prize (normativ fix)
    recs = [el for el in (elements or [])
            if ((el or {}).get("element_type") or "") in ("alimentare_receptor", "receptor_internet")]
    if recs:
        try:                                                        # lazy (evita import circular)
            import enrich_circuits as _ec
            # SURSA UNICA: tip echipament -> cable_type REAL din circuits (dimensionat de enrich,
            # inclusiv puterile custom din formular). Fallback: re-derivare din default daca circuits lipsa.
            eqmap = {}
            for c in (circuits or []):
                if isinstance(c, dict) and c.get("type") == "dedicat":
                    k = _ec._equip_key(c.get("description") or c.get("usage"))
                    if k and k not in eqmap:
                        eqmap[k] = c.get("cable_type")
            for el in recs:
                is_net = (el.get("element_type") or "") == "receptor_internet"
                lbl = "internet" if is_net else el.get("label")
                cbl = eqmap.get(_ec._equip_key(lbl))                # sectiunea REALA din circuits
                if not cbl:                                         # FALLBACK: proiect vechi fara circuits
                    pw, _tip, ph, _src = _ec.receptor_power(lbl, {})
                    pw = pw or (_ec._NET_RECEPTOR_W if is_net else 0)
                    if not pw:
                        continue
                    tri = str(ph).lower() in ("tri", "trifazat", "3")
                    cbl, _sec = _ec.cable_type("dedicat", _ec.breaker_and_ia(pw, tri=tri, minimum=16)[0], False, tri=tri)
                if _ec._section_of(cbl) not in (0.0, 2.5):          # != prize (2.5 = deja in randul generic)
                    texts.append("Cablu alimentare dedicata %s mmp" % _norm_cable_display(cbl))
        except Exception:
            pass
    if not texts:
        texts = [_LEGEND_CABLE_FORTA]
    out, seen = [], set()
    for t in texts:
        if t not in seen:
            seen.add(t)
            out.append({"kind": "cable", "text": t})
    # COLOANE (feed sub_tablou TEG->TE-CT/TES): un rand TEAL per feed, cu sectiunea din schema
    for f in (feeds or []):
        if not isinstance(f, dict) or f.get("type") != "sub_tablou":
            continue
        tgt = f.get("feeds_panel") or "sub-tablou"
        cbl = (f.get("cable_type") or "").strip()
        txt = ("Coloana alimentare %s %s" % (tgt, cbl)).strip()
        if txt not in seen:
            seen.add(txt)
            # feeds_panel pastrat -> _draw_legend coloreaza randul TES cu verdele coloanei cross-plansa
            out.append({"kind": "column", "text": txt, "feeds_panel": tgt})
    # TRAVERSARE INTRE NIVELURI (cross-plansa): simbolul cerc+sageata in legenda cand plansa il are
    if cross_floor and isinstance(cross_floor, dict) and cross_floor.get("mode") in ("up", "down"):
        _up = cross_floor["mode"] == "up"
        out.append({"kind": "crossing", "up": _up,
                    "text": ("Traversare nivel: coloana urca la etajul urmator" if _up
                             else "Traversare nivel: alimentare venita de la nivelul inferior")})
    return out


def build_legend_rows(elements, plan_type="iluminat", feeds=None, circuits=None, cross_floor=None):
    """LOGICA PURA (fara desen): randurile legendei din plan_elements, pe plan_type.
    Returneaza [{kind, element_type?/label?, power_w?, text}] cu text DESCRIPTIV (_legend_label):
      ILUMINAT: becuri (pe tip+putere) + intrerupatoare (prezente) + tablouri + cablu 3x1.5.
      FORTA:    prize (prezente) + alimentari (receptor, pe label) + internet + tablouri + cablu 3x2.5(+dedicate).
    Ordine determinista. Doar tipurile PREZENTE pe plan. Pura: nu deseneaza, nu modifica `elements`."""
    elements = elements or []
    present = {((el or {}).get("element_type") or "") for el in elements}

    # a) BECURI (iluminat): combinatii unice (element_type, power_w normalizat)
    seen = set()
    bulbs = []
    for el in elements:
        et = (el or {}).get("element_type") or ""
        if et not in _BULB_TYPES:
            continue
        pw = _legend_pw(el.get("power_w"))
        key = (et, pw)
        if key in seen:
            continue
        seen.add(key)
        bulbs.append({"kind": "bulb", "element_type": et, "power_w": pw,
                      "text": _legend_label("bulb", et, pw)})
    bulbs.sort(key=lambda r: (r["element_type"], r["power_w"] is None, r["power_w"] or 0))

    # b) INTRERUPATOARE (iluminat): doar tipurile prezente, ordine determinista
    switches = [{"kind": "switch", "element_type": et, "text": _legend_label("switch", et)}
                for et in _SWITCH_ORDER if et in present and et in _SWITCH_TYPES]

    # c) PRIZE (forta): doar tipurile prezente
    prizes_rows = [{"kind": "prize", "element_type": et, "text": _legend_label("prize", et)}
                   for et in _PRIZA_ORDER if et in present and et in _PRIZA_TYPES]

    # d) ALIMENTARI (forta): alimentare_receptor grupat pe label (distinct, in ordinea aparitiei)
    rec_labels, seen_lbl = [], set()
    for el in elements:
        if ((el or {}).get("element_type") or "") == "alimentare_receptor":
            lbl = ((el.get("label") or "").strip() or "receptor")
            if lbl not in seen_lbl:
                seen_lbl.add(lbl)
                rec_labels.append(lbl)
    receptor_rows = [{"kind": "receptor", "label": lbl, "text": _legend_label("receptor", None, label=lbl)}
                     for lbl in rec_labels]

    # e) RETEA INTERNET (forta): daca prezenta
    internet_rows = ([{"kind": "internet", "text": _legend_label("internet", None)}]
                     if "receptor_internet" in present else [])

    # f) TABLOURI (ambele): doar tipurile prezente
    panels = [{"kind": "panel", "element_type": et, "text": _legend_label("panel", et)}
              for et in _PANEL_ORDER if et in present and et in _PANEL_TYPES]

    # f2) TABLOURILE FV (FV-P2, DINAMICE): descrierea Dan + montajul din LABEL ("fatada"/"spatiu
    # tehnic") + kW-ul invertorului din POWER_W. Texte ~100 caractere -> wrap pe 2 randuri (`lines`,
    # mecanismul O2 cu latimea legendei). Ordinea = lantul T.CC -> INV -> T.CA.
    fv_rows = []
    for et in _FV_PANEL_ORDER:
        el = next((e for e in elements if ((e or {}).get("element_type") or "") == et), None)
        if el is None:
            continue
        loc = ("in spatiul tehnic" if (el.get("label") or "").strip().lower() == "spatiu tehnic"
               else "pe fatada")
        if et == "tablou_inv":
            kw = _fmt_height((el.get("power_w") or 0) / 1000.0) or "0"
            txt = ("INV: Invertor solar trifazat cu puterea de %s kW, montat %s, "
                   "la inaltimea h=1.5m fata de cota terenului" % (kw, loc))
        else:
            fel = "alternativ" if et == "tablou_tca" else "continuu"
            short = "T.CA" if et == "tablou_tca" else "T.CC"
            txt = ("%s: Tablou electric de interfata si protectie in curent %s, montat %s, "
                   "la inaltimea h=1.5m fata de pardoseala" % (short, fel, loc))
        fv_rows.append({"kind": "panel", "element_type": et, "text": txt,
                        "lines": _wrap_label_25(txt, 72)})   # 72: ambele randuri incap FARA trunchiere
    # FV-P3: randul lantului FV in legenda (doar pe FORTA si doar daca exista cel putin 2 tablouri
    # consecutive din lant -> exista segmente desenate pe plan)
    if plan_type == "forta" and fv_rows:
        _fvp = [et for et in ("tablou_tcc", "tablou_inv", "tablou_tca", "tablou_teg") if et in present]
        _has_seg = any(a in present and b in present for a, b in
                       zip(("tablou_tcc", "tablou_inv", "tablou_tca"), ("tablou_inv", "tablou_tca", "tablou_teg")))
        if _has_seg and _fvp:
            fv_rows.append({"kind": "fv_link",
                            "text": "Legatura sistem fotovoltaic (%s)" % " - ".join(
                                _PANEL_INFO.get(et, (None, None, et))[2] for et in _fvp)})

    # g) CABLU pe plan_type (din circuits reale + COLOANE feed sub_tablou)
    cable_rows = _legend_cable_rows(elements, plan_type, present, feeds, circuits, cross_floor=cross_floor)

    return bulbs + switches + prizes_rows + receptor_rows + internet_rows + panels + fv_rows + cable_rows


# Prag suprafață "cameră mare" -> 2 becuri (pe axa lungă). Ușor de ajustat.
ROOM_LARGE_M2 = 25.0
# Factor pt² -> m² la scara planului (~1:71); folosit ca proxy când lipsește area_m2.
_PT2_TO_M2 = 6.205e-4


def _sanitize_bbox(x, y, w, h, label=""):
    """C — validare/clamp bbox Vision. Aduce coordonatele în domeniul valid FĂRĂ a elimina
    camera (toate primesc bec). x,y -> [0,1]; w,h -> (0,1]; x+w, y+h <= 1; latură ~0 -> minim
    vizibil. Loghează aberațiile (latură >0.9 sau ~0). Întoarce (x,y,w,h, fixed)."""
    ox, oy, ow, oh = x, y, w, h
    x = min(max(x, 0.0), 1.0); y = min(max(y, 0.0), 1.0)
    w = min(max(w, 0.0), 1.0); h = min(max(h, 0.0), 1.0)
    if x + w > 1.0: w = 1.0 - x
    if y + h > 1.0: h = 1.0 - y
    if w < 0.01: w = 0.01      # latură degenerată -> minim (nu eliminăm camera)
    if h < 0.01: h = 0.01
    fixed = (abs(ox - x) > 1e-6 or abs(oy - y) > 1e-6 or abs(ow - w) > 1e-6 or abs(oh - h) > 1e-6)
    if fixed or ow > 0.9 or oh > 0.9 or ow < 0.01 or oh < 0.01:
        print("[draw_elements] bbox suspect '%s': (%.3f,%.3f,%.3f,%.3f)->(%.3f,%.3f,%.3f,%.3f)"
              % (label, ox, oy, ow, oh, x, y, w, h))
    return x, y, w, h, fixed


def _clip_region(bx, by, bw, bh, h_segs, v_segs):
    """CLIP bbox∩pereți: taie bbox-ul Vision (px) la pereții detectați din jur -> centrul REGIUNII
    REALE a camerei. Pentru fiecare latură, dacă un perete cade ÎNTRE centrul bbox și marginea bbox
    (revărsare), regiunea se taie la perete -> becul nu mai cade pe zid (ex. Baie 1 cu bbox revărsat).
    Dacă tăierea degenerează (pereți lipsă) -> centrul bbox (degradare grațioasă). -> (cx, cy)."""
    if h_segs is None or v_segs is None:
        return bx + bw / 2.0, by + bh / 2.0
    cx = bx + bw / 2.0; cy = by + bh / 2.0
    L, R, T, B = bx, bx + bw, by, by + bh
    for (y0, y1, x) in v_segs:               # pereți verticali care acoperă cy
        if min(y0, y1) - 6 <= cy <= max(y0, y1) + 6:
            if bx - 6 <= x < cx:
                L = max(L, x)
            elif cx < x <= bx + bw + 6:
                R = min(R, x)
    for (x0, x1, y) in h_segs:               # pereți orizontali care acoperă cx
        if min(x0, x1) - 6 <= cx <= max(x0, x1) + 6:
            if by - 6 <= y < cy:
                T = max(T, y)
            elif cy < y <= by + bh + 6:
                B = min(B, y)
    if R - L < 8 or B - T < 8:                # tăiere degenerată -> centru bbox
        return cx, cy
    return (L + R) / 2.0, (T + B) / 2.0


# ── Acoperire iluminat: holuri (R2) + dedup global ──
_PX_TO_M = _PT2_TO_M2 ** 0.5   # ~0.0249 m/px (scara planului)
HALL_ASPECT = 2.0              # bbox alungit (max/min latura) -> candidat hol
HALL_2BULB_M = 3.0             # hol mai lung de 3m -> 2 becuri pe lungime
DEDUP_D = 85.0                 # px (~2.1m): becuri din camere DIFERITE mai apropiate = duplicat


def _wall_coord_near(target, span_lo, span_hi, segs, kind, tol=30.0):
    """Coordonata celei mai apropiate linii de perete de 'target' (axa perpendiculară holului)
    care acoperă mijlocul span-ului. kind='H': segs=(x0,x1,y)->y; 'V': (y0,y1,x)->x.
    None dacă nu se găsește -> hol 'neclar' (ex. în L) => caller rămâne conservator (1 bec)."""
    mid = (span_lo + span_hi) / 2.0
    best = None; bestd = tol
    if kind == "H":
        for (x0, x1, y) in segs:
            if min(x0, x1) <= mid <= max(x0, x1) and abs(y - target) < bestd:
                bestd = abs(y - target); best = y
    else:
        for (y0, y1, x) in segs:
            if min(y0, y1) <= mid <= max(y0, y1) and abs(x - target) < bestd:
                bestd = abs(x - target); best = x
    return best


def _wall_dist(px, py, h_segs, v_segs):
    """Distanta minima de la (px,py) la o linie de perete care il acopera pe axa relevanta."""
    d = 1e9
    for (x0, x1, y) in h_segs:
        if min(x0, x1) - 4 <= px <= max(x0, x1) + 4:
            d = min(d, abs(y - py))
    for (y0, y1, x) in v_segs:
        if min(y0, y1) - 4 <= py <= max(y0, y1) + 4:
            d = min(d, abs(x - px))
    return d


def _nudge_offwall_long(px, py, horizontal, lo, hi, h_segs, v_segs, tol=16.0, step=12.0):
    """Plasa de siguranta pentru becul de hol: daca punctul cade pe/langa un perete (sau o partitie
    transversala pe axa lunga), il aluneca de-a lungul axei LUNGI in [lo,hi] pana la primul punct la
    >tol de orice perete. Pastreaza coordonata perpendiculara (mijlocul holului). Intoarce cel mai bun
    punct (max distanta) daca niciunul nu atinge tol. -> (x, y)."""
    if _wall_dist(px, py, h_segs, v_segs) >= tol:
        return px, py
    best = (px, py); bestd = _wall_dist(px, py, h_segs, v_segs)
    k = 1
    while k * step <= (hi - lo):
        cands = ((px + k*step, py), (px - k*step, py)) if horizontal else ((px, py + k*step), (px, py - k*step))
        for (qx, qy) in cands:
            q = qx if horizontal else qy
            if lo <= q <= hi:
                dd = _wall_dist(qx, qy, h_segs, v_segs)
                if dd > bestd:
                    bestd, best = dd, (qx, qy)
                if dd >= tol:
                    return qx, qy
        k += 1
    return best


def _dedup_centers(centers, boxes, W, H, D=DEDUP_D):
    """Elimină becuri DUPLICATE între camere DIFERITE (bbox-uri Vision suprapuse) sub D px.
    Candidat la eliminare = bec NON-geometric (becurile geometrice pe pereți reali NU se ating),
    a cărui cameră rămâne cu >=1 bec, ȘI care e fie NEPROTEJAT (fallback cameră mică), fie INTRUS
    (cade în bbox-ul celeilalte camere — ex. bec de Terasă căzut în Living). Preferă să elimine
    INTRUSUL. NU lasă nicio cameră fără bec. Cross-cameră (perechi din aceeași cameră neatinse). -> (centers, n)."""
    counts = {}
    for c in centers:
        counts[c["room"]] = counts.get(c["room"], 0) + 1

    def in_room_bbox(k, room):
        b = boxes[room] if (0 <= room < len(boxes)) else None
        if not b:
            return False
        return b[0]*W <= centers[k]["x"] <= (b[0]+b[2])*W and b[1]*H <= centers[k]["y"] <= (b[1]+b[3])*H

    pairs = []
    for i in range(len(centers)):
        for j in range(i + 1, len(centers)):
            if centers[i]["room"] == centers[j]["room"]:
                continue
            d = math.hypot(centers[i]["x"] - centers[j]["x"], centers[i]["y"] - centers[j]["y"])
            if d < D:
                pairs.append((d, i, j))
    pairs.sort()
    removed = [False] * len(centers); n = 0
    for d, i, j in pairs:
        if removed[i] or removed[j]:
            continue
        cand = []   # (idx, e_intrus)
        for k, other in ((i, j), (j, i)):
            if centers[k].get("geometric"):
                continue                                  # becurile geometrice — niciodată
            if counts[centers[k]["room"]] <= 1:
                continue                                  # nu goli camera
            intruder = in_room_bbox(k, centers[other]["room"])
            if (not centers[k].get("protected")) or intruder:
                cand.append((k, intruder))
        if not cand:
            continue
        # victimă: preferă INTRUSUL; apoi din camera cu mai multe becuri
        victim = min(cand, key=lambda t: (0 if t[1] else 1, -counts[centers[t[0]]["room"]]))[0]
        removed[victim] = True; counts[centers[victim]["room"]] -= 1; n += 1
    return [c for k, c in enumerate(centers) if not removed[k]], n


def _wall_clear(px, py, h_segs, v_segs):
    """Distanța la cel mai apropiat perete care acoperă punctul (sau 1e9 dacă niciunul)."""
    best = 1e9
    for (x0, x1, y) in h_segs:
        if min(x0, x1) - 4 <= px <= max(x0, x1) + 4:
            best = min(best, abs(y - py))
    for (y0, y1, x) in v_segs:
        if min(y0, y1) - 4 <= py <= max(y0, y1) + 4:
            best = min(best, abs(x - px))
    return best


def _resolve_overlaps(centers, boxes, h_segs, v_segs, W, H):
    """Niciun bec nu trebuie să cadă în bbox-ul ALTEI camere (Vision dă bbox-uri DEPLASATE/suprapuse ->
    becul unei camere ajunge vizual în zona vecinei = a 2-a 'lumină' acolo). Pentru fiecare astfel de bec,
    îl mută în propriul bbox la un punct care: NU e în bbox-ul altei camere, e off-wall, și departe de alte
    becuri. GUARD c: becul GEOMETRIC corect (în propriul bbox) rămâne pe loc chiar dacă un bbox vecin se
    suprapune; DAR dacă a DRIFTAT în afara bbox-ului camerei lui ȘI cade la vecin -> îl clampăm înapoi în al
    lui (paliativ pt. bbox Vision deplasat; înainte geometricele erau sărite necondiționat -> rămâneau la
    vecin). Propriul bbox complet înghițit (niciun loc liber) -> lasă (limită open-plan). -> nr. mutate."""
    def in_other(px, py, ri):
        for k, b in enumerate(boxes):
            if k == ri or b is None:
                continue
            if b[0]*W <= px <= (b[0]+b[2])*W and b[1]*H <= py <= (b[1]+b[3])*H:
                return True
        return False

    moved = 0
    for c in centers:
        ri = c["room"]
        if ri is None or ri >= len(boxes) or boxes[ri] is None:
            continue
        if not in_other(c["x"], c["y"], ri):
            continue   # becul nu cade în bbox-ul niciunei ALTE camere -> ok
        bx, by, bw, bh = boxes[ri]
        bx0, by0, bx1, by1 = bx*W, by*H, (bx+bw)*W, (by+bh)*H
        # GUARD c: becul GEOMETRIC corect (în propriul bbox) rămâne pe loc chiar dacă un bbox vecin se
        # suprapune; relochează DOAR dacă a driftat AFARA din bbox-ul lui (atunci e flagrant la vecin).
        # Becurile non-geometrice (clip/hall) se reloca ca înainte (cad în bbox-ul altei camere).
        if c.get("geometric") and (bx0 <= c["x"] <= bx1 and by0 <= c["y"] <= by1):
            continue
        best = None; bestscore = -1e9
        for gi in range(1, 12):
            for gj in range(1, 12):
                px = bx0 + (bx1 - bx0) * gi / 12.0
                py = by0 + (by1 - by0) * gj / 12.0
                if in_other(px, py, ri):
                    continue                       # tot în vecin -> sare
                wc = _wall_clear(px, py, h_segs, v_segs)
                if wc < 10.0:
                    continue                       # pe perete -> sare
                dmin = min((math.hypot(px - o["x"], py - o["y"]) for o in centers if o is not c), default=1e9)
                score = min(wc, 120.0) + 0.4 * min(dmin, 120.0)
                if score > bestscore:
                    bestscore = score; best = (px, py)
        if best:
            c["x"], c["y"] = best; moved += 1
    return moved


def _vision_centers(rooms, W, H, geoms=None, walls=None):
    """PASĂ AUTORITARĂ de plasare becuri (consolidează gărzile-plasture anterioare).
    rooms = [{ name, area_m2, bbox:{x,y,w,h} }] (fracții 0-1). geoms = PARALEL cu rooms (geometry).
    Per cameră cu bbox valid -> ANCORĂ:
      1) centroid geometric (wall-bounded) dacă geometric=True — SURSĂ DE ADEVĂR, prioritate 1;
      2) altfel CLIP bbox∩pereți -> centrul regiunii reale (taie revărsarea -> bec niciodată pe zid).
    Cameră mare (area>=ROOM_LARGE_M2) -> 2 becuri pe axa lungă; hol alungit fallback cu 2 pereți (R2)
    -> 1/2 becuri pe lungime; altfel 1 bec la ancoră. INVARIANT: fiecare cameră validă primește becul
    ei ÎN interior (nimic nu-l mută/șterge în afară). Apoi O SINGURĂ dedup (open-plan).
    LIMITĂ: terase/open-plan fără pereți -> clip degenerează -> centru bbox (nefixabil geometric)."""
    centers = []
    h_segs, v_segs = (walls if walls else (None, None))   # R2 holuri: necesită liniile de perete
    # C — bbox-uri SANITIZATE (clamp la domeniul valid), aliniate cu rooms; None = invalid.
    # Aceleași boxe le folosește și garda anti-intruziune (verificare cross-cameră).
    boxes = []
    bbox_fixed = 0
    for r in (rooms or []):
        bb = (r or {}).get("bbox") or {}
        try:
            x = float(bb["x"]); y = float(bb["y"]); w = float(bb["w"]); h = float(bb["h"])
        except (TypeError, ValueError, KeyError):
            boxes.append(None)
            continue
        sx, sy, sw, sh, fixed = _sanitize_bbox(x, y, w, h, str((r or {}).get("name") or ""))
        if fixed:
            bbox_fixed += 1
        boxes.append((sx, sy, sw, sh))

    # V4: autoritatea "camerei proprii" pentru garzile downstream (dedup, anti-intruziune,
    # invariant) devine geom_bbox DOAR pentru camerele FARA centroid geometric — exact camerele
    # ale caror ancore le mutam pe geom_bbox. Fara asta, garzile "reloca" becul ancorat corect
    # inapoi in bbox-ul Vision DECALAT (in afara cladirii). Camerele CU centroid isi pastreaza
    # bbox-ul Vision sanitizat ca "acasa" (comportamentul de azi, bit-identic — zero regresie).
    if geoms:
        for _i in range(min(len(boxes), len(geoms))):
            _g = geoms[_i] or {}
            if _g.get("geometric") and _g.get("centroid"):
                continue                          # camera cu centroid: autoritatea ramane Vision (ca azi)
            _gb = _g.get("geom_bbox")
            if boxes[_i] is not None and _gb:
                try:
                    boxes[_i] = (float(_gb["x"]), float(_gb["y"]), float(_gb["w"]), float(_gb["h"]))
                except (TypeError, ValueError, KeyError):
                    pass

    rooms_geometric = 0
    rooms_fallback = 0
    for idx, r in enumerate(rooms or []):
        box = boxes[idx] if idx < len(boxes) else None
        if box is None:
            continue
        x, y, w, h = box
        label = str((r or {}).get("name") or "")
        # mărimea camerei: area_m2 din Vision; fallback la aria bbox (proxy la ~1:71)
        try:
            area = float((r or {}).get("area_m2") or 0)
        except (TypeError, ValueError):
            area = 0.0
        if area <= 0:
            area = (w * h) * (W * H) * _PT2_TO_M2

        # ANCORĂ becului: 1) centroid geometric (wall-bounded) — SURSĂ DE ADEVĂR, prioritate 1;
        #                  2) altfel CLIP bbox∩pereți -> centrul REGIUNII REALE (taie revărsarea
        #                     bbox-ului peste pereți -> becul nu mai cade pe zid, la sursă).
        cxc = (x + w / 2.0) * W
        cyc = (y + h / 2.0) * H
        g = geoms[idx] if (geoms and idx < len(geoms)) else None
        used_geometric = bool(g and g.get("geometric") and g.get("centroid"))
        if used_geometric:
            try:
                cxc = float(g["centroid"]["x"]); cyc = float(g["centroid"]["y"])
                rooms_geometric += 1
            except (TypeError, ValueError, KeyError):
                used_geometric = False
        # V4 (oglinda fixului de prize): fara centroid -> ancora = centrul geom_bbox (populat acum
        # pentru toate camerele: 'wall' SAU 'label_anchor' din ancora etichetei). Repara becurile
        # care cadeau pe bbox-ul Vision decalat (terase, Spatiu tehnic, Depozitare, Camera de zi).
        used_geom_bbox = False
        if not used_geometric:
            _gb = (g or {}).get("geom_bbox") if g else None
            if _gb:
                try:
                    cxc = (float(_gb["x"]) + float(_gb["w"]) / 2.0) * W
                    cyc = (float(_gb["y"]) + float(_gb["h"]) / 2.0) * H
                    used_geom_bbox = True
                    rooms_geometric += 1
                except (TypeError, ValueError, KeyError):
                    used_geom_bbox = False
        if not used_geometric and not used_geom_bbox:
            cxc, cyc = _clip_region(x * W, y * H, w * W, h * H, h_segs, v_segs)
            rooms_fallback += 1
        _anchored = used_geometric or used_geom_bbox   # ancora de incredere -> protejata la dedup

        # COUNT (1 vs 2 becuri) pe ARIA DIN CARTUȘ (area_m2, citită din textul bilanțului):
        # ~0% variație între generări ȘI exactă (= aria reală). NU pe aria GEOMETRICĂ — poligonul
        # poate over-merge (ex. Camera de zi geom 49.7 vs cartuș 35.75 -> ar putea umfla gresit count-ul).
        # `area` = area_m2 cartuș când există; fallback la aria bbox doar dacă lipsește din cartuș.
        if area >= ROOM_LARGE_M2:
            # 2 becuri pe axa LUNGĂ a bbox-ului, re-centrate pe (cxc, cyc). PROTEJATE (coverage intentionat).
            if w * W >= h * H:
                dx = (w / 6.0) * W   # jumătatea distanței dintre pozițiile 1/3 și 2/3
                centers.append({"x": cxc - dx, "y": cyc, "label": label, "room": idx, "geometric": _anchored, "protected": True})
                centers.append({"x": cxc + dx, "y": cyc, "label": label, "room": idx, "geometric": _anchored, "protected": True})
            else:
                dy = (h / 6.0) * H
                centers.append({"x": cxc, "y": cyc - dy, "label": label, "room": idx, "geometric": _anchored, "protected": True})
                centers.append({"x": cxc, "y": cyc + dy, "label": label, "room": idx, "geometric": _anchored, "protected": True})
        else:
            # R2 — HOL alungit (bbox aspect>2, fallback): 1 bec in MIJLOCUL holului, garantat off-wall.
            # Axa SCURTA (perp) = mijloc intre cei 2 pereti lungi; daca DOAR UNUL se gaseste -> mijloc
            # intre el si marginea bbox (holul deschis pe o latura, ex. Hol central spre living). Axa
            # LUNGA = centru, apoi NUDGE off-wall daca o partitie transversala cade acolo. Astfel becul
            # nu cade pe perete nici pe zid transversal. 1 bec (consistent cu count-ul pe aria cartus).
            hall_done = False
            if (not _anchored) and h_segs is not None and v_segs is not None:
                bx, by, bw, bh = x * W, y * H, w * W, h * H
                if max(bw, bh) / max(min(bw, bh), 1.0) > HALL_ASPECT:
                    horizontal = bw >= bh
                    if horizontal:   # hol orizontal -> pereti lungi sus/jos (H), bec pe axa X
                        c1 = _wall_coord_near(by, bx, bx + bw, h_segs, "H")
                        c2 = _wall_coord_near(by + bh, bx, bx + bw, h_segs, "H")
                        lo_e, hi_e = by, by + bh
                        lo_l, hi_l = bx, bx + bw
                    else:            # hol vertical -> pereti lungi stanga/dreapta (V), bec pe axa Y
                        c1 = _wall_coord_near(bx, by, by + bh, v_segs, "V")
                        c2 = _wall_coord_near(bx + bw, by, by + bh, v_segs, "V")
                        lo_e, hi_e = bx, bx + bw
                        lo_l, hi_l = by, by + bh
                    if c1 is not None and c2 is not None:
                        perp = (c1 + c2) / 2.0
                    elif c1 is not None:
                        perp = (c1 + hi_e) / 2.0
                    elif c2 is not None:
                        perp = (lo_e + c2) / 2.0
                    else:
                        perp = None
                    if perp is not None:   # macar un perete lung gasit -> hol plauzibil
                        lp = (lo_l + hi_l) / 2.0
                        px0, py0 = (lp, perp) if horizontal else (perp, lp)
                        px1, py1 = _nudge_offwall_long(px0, py0, horizontal, lo_l, hi_l, h_segs, v_segs)
                        centers.append({"x": px1, "y": py1, "label": label, "room": idx, "geometric": False, "protected": False})
                        hall_done = True
            if not hall_done:
                # 1 bec la ANCORĂ (centroid geometric / centrul geom_bbox / centrul regiunii clipate).
                centers.append({"x": cxc, "y": cyc, "label": label, "room": idx, "geometric": _anchored, "protected": _anchored})

    # DEDUP (O SINGURĂ trecere, finală): open-plan / bbox-uri suprapuse -> elimină duplicatul
    # NON-geometric, păstrează geometricul, min 1 bec/cameră. INVARIANT: fiecare cameră cu bbox valid
    # și-a primit becul(urile) în buclă; dedup nu golește nicio cameră -> nicio cameră fără bec.
    centers, bulbs_dedup = _dedup_centers(centers, boxes, W, H)

    # INVARIANT FINAL (garanție absolută): fiecare cameră cu bbox valid are >=1 bec ÎN interior.
    # Structural deja garantat (bucla dă fiecăreia un bec, dedup păstrează min 1); verificare explicită
    # de siguranță — dacă vreo cameră a rămas fără bec, îl re-adaugă la ancoră (centroid sau clip).
    present = {c["room"] for c in centers}
    bulbs_guaranteed = 0
    for idx, box in enumerate(boxes):
        if box is None or idx in present:
            continue
        x, y, w, h = box
        g = geoms[idx] if (geoms and idx < len(geoms)) else None
        _gb = (g or {}).get("geom_bbox") if g else None
        if g and g.get("geometric") and g.get("centroid"):
            try:
                ax, ay = float(g["centroid"]["x"]), float(g["centroid"]["y"])
            except (TypeError, ValueError, KeyError):
                ax, ay = _clip_region(x*W, y*H, w*W, h*H, h_segs, v_segs)
        elif _gb:   # V4: ancora din geom_bbox (aceeasi prioritate 2 ca in bucla principala)
            try:
                ax = (float(_gb["x"]) + float(_gb["w"]) / 2.0) * W
                ay = (float(_gb["y"]) + float(_gb["h"]) / 2.0) * H
            except (TypeError, ValueError, KeyError):
                ax, ay = _clip_region(x*W, y*H, w*W, h*H, h_segs, v_segs)
        else:
            ax, ay = _clip_region(x*W, y*H, w*W, h*H, h_segs, v_segs)
        centers.append({"x": ax, "y": ay, "room": idx, "geometric": False, "protected": True,
                        "label": str(((rooms or [])[idx] or {}).get("name") or "")})
        bulbs_guaranteed += 1

    # ANTI-INTRUZIUNE (completează reconcilierea): niciun bec fallback nu rămâne în bbox-ul altei
    # camere (bbox-uri Vision suprapuse -> dublare vizuală în vecină). Geometricul rămâne pe loc.
    bulbs_separated = 0
    if h_segs is not None:
        bulbs_separated = _resolve_overlaps(centers, boxes, h_segs, v_segs, W, H)

    stats = {
        "rooms_geometric": rooms_geometric,   # câte camere au folosit centroid CAD
        "rooms_fallback": rooms_fallback,      # câte au căzut pe clip bbox∩pereți
        "bbox_fixed": bbox_fixed,              # câte bbox-uri Vision corectate
        "bulbs_dedup": bulbs_dedup,            # câte becuri duplicate (open-plan) eliminate
        "bulbs_guaranteed": bulbs_guaranteed,  # câte becuri re-adăugate de invariantul final
        "bulbs_separated": bulbs_separated,    # câte becuri coincidente separate
    }
    return centers, stats


# ── APARATAJ: întrerupătoare (MVP) — funcții PARALELE cu becurile, nu le ating ──
SWITCH_R = 3.5           # raza punctului plin (px)
SWITCH_STEM = 14.0       # lungimea tijei oblice VIZIBILE, in afara punctului (px)
SWITCH_FROM_JAMB = 11.0  # cat de departe pe perete, dincolo de toc (~27cm)
SWITCH_COL_CLEAR = 30.0  # distanta minima fata de un sambure (px)
SWITCH_SNAP_TOL = 32.0   # cat de departe caut o linie de perete pe care sa lipesc


def _draw_switch(page, x, y, angle, element_type="intrerupator_simplu", scale=1.0):
    """Simbol întrerupător (Varianta B), de la PERETE spre INTERIORUL camerei:
    cerc PLIN (bază, lipit de perete, la ancora x,y) -> linie -> cerc GOL (contur) -> linie -> cârlig(e).
    BAZA (cerc plin + cerc gol + tijă) e IDENTICĂ pentru toate tipurile; diferă DOAR cârligele:
      - intrerupator_simplu      -> 1 cârlig (oblic, +HKA);
      - intrerupator_dublu       -> 2 cârlige din vârful tijei (+HKA și -HKA), "V";
      - intrerupator_triplu      -> 3 cârlige din vârful tijei (+HKA, 0, -HKA);
      - intrerupator_cap_scara   -> 2 cârlige PARALELE (aceeași înclinare), offset ±p -> aspect "scară".
    Orientat după `angle`: u=(cos,sin)=spre interior, p=(-sin,cos)=perpendicular. Ancora (x,y)=cerc plin."""
    ux, uy = math.cos(angle), math.sin(angle)      # direcția spre interiorul camerei
    px, py = -uy, ux                               # perpendiculara (pentru cârlig)
    s = scale          # factor pe geometrie (forma identica, mai mica) — pt. legenda. scale=1.0 = neschimbat
    R1 = 2.5 * s        # cerc PLIN (bază, la perete)
    L1 = 4.0 * s       # linie: bază -> cerc gol
    R2 = 4.0 * s       # cerc GOL (contur)
    L2 = 5.0 * s       # linie: cerc gol -> cârlig
    HK, HKA = 6.0 * s, 0.7  # cârlig: lungime (*scale) + unghi (~40°, NEscalat)

    def P(d):  # punct la distanța d pe axa u (spre interior), de la ancoră
        return fitz.Point(x + d * ux, y + d * uy)

    def hook(start, theta):  # cârlig de lungime HK din `start`, pe u rotit cu theta în baza (u,p)
        dx = ux * math.cos(theta) + px * math.sin(theta)
        dy = uy * math.cos(theta) + py * math.sin(theta)
        page.draw_line(start, fitz.Point(start.x + HK * dx, start.y + HK * dy), color=RED, width=2.0)

    # BAZA (identică pentru toate tipurile)
    page.draw_circle(fitz.Point(x, y), R1, color=RED, fill=RED, width=0.8)  # cerc PLIN (la perete)
    page.draw_line(P(R1), P(R1 + L1), color=RED, width=1.2)                 # linie -> cerc gol
    oc = R1 + L1 + R2                                                       # centrul cercului gol
    page.draw_circle(P(oc), R2, color=RED, width=1.2)                      # cerc GOL (contur)
    base = oc + R2
    page.draw_line(P(base), P(base + L2), color=RED, width=1.2)            # tijă -> cârlig(e)
    hb = P(base + L2)                                                       # vârful tijei (baza cârligelor)

    # CÂRLIGE pe tip (simplul rămâne IDENTIC cu varianta anterioară: 1 cârlig la +HKA)
    if element_type == "intrerupator_dublu":
        hook(hb, +HKA); hook(hb, -HKA)
    elif element_type == "intrerupator_triplu":
        hook(hb, +HKA); hook(hb, 0.0); hook(hb, -HKA)
    elif element_type == "intrerupator_cap_scara":
        off = R2 * 0.7   # 2 cârlige PARALELE (aceeași înclinare), offset ±p -> distinct de "dublu"
        a1 = fitz.Point(hb.x + off * px, hb.y + off * py)
        a2 = fitz.Point(hb.x - off * px, hb.y - off * py)
        hook(a1, +HKA); hook(a2, +HKA)
    else:  # intrerupator_simplu (default) — NESCHIMBAT
        hook(hb, +HKA)


def _nearest_wall_coord(px, py, h_segs, v_segs, axis, tol=SWITCH_SNAP_TOL):
    """Coordonata EXACTĂ a celei mai apropiate linii de perete pe axa cerută, care acoperă punctul.
    axis='H' -> y-ul liniei orizontale (lipim pe verticală); axis='V' -> x-ul liniei verticale.
    None dacă nicio linie sub tol. Așa lipim întrerupătorul pe linia zidului, nu lângă arc."""
    best = None; bestd = tol
    if axis == "H":
        for (x0, x1, y) in h_segs:
            if min(x0, x1) - 8 <= px <= max(x0, x1) + 8 and abs(y - py) < bestd:
                bestd = abs(y - py); best = y
    else:
        for (y0, y1, x) in v_segs:
            if min(y0, y1) - 8 <= py <= max(y0, y1) + 8 and abs(x - px) < bestd:
                bestd = abs(x - px); best = x
    return best


def _switch_pos_at_door(d, columns, h_segs, v_segs):
    """Poziția+unghiul întrerupătorului lângă o ușă: latura de deschidere (mâner), LIPIT pe linia
    peretelui lângă toc, spre interiorul camerei; evită sâmburii. Extras din vechea logică per-ușă
    (neschimbată), refolosit acum per-bec. -> (sx, sy, angle)."""
    hinge = d["hinge"]; strike = d["strike"]; ux, uy = d["swing"]
    if d["certain"]:
        # directia peretelui = de la balama spre strike (strike e pe perete)
        wx, wy = strike[0]-hinge[0], strike[1]-hinge[1]
        wl = math.hypot(wx, wy) or 1.0; wx, wy = wx/wl, wy/wl
        sx = strike[0] + wx * SWITCH_FROM_JAMB
        sy = strike[1] + wy * SWITCH_FROM_JAMB
        wall_h = abs(wx) >= abs(wy)          # peretele e orizontal?
    else:
        # incert (usa la colt): plasa de siguranta — langa toc, spre interiorul camerei
        sx = d["x"] + ux * 12.0
        sy = d["y"] + uy * 12.0
        wall_h = abs(ux) < abs(uy)           # deschidere ⟂ perete -> peretele e pe axa opusa

    # SNAP pe linia EXACTĂ a peretelui, pe axa corectă (lipit pe zid, nu pe arc)
    if wall_h:
        wyc = _nearest_wall_coord(sx, sy, h_segs, v_segs, "H")
        if wyc is not None: sy = wyc
    else:
        wxc = _nearest_wall_coord(sx, sy, h_segs, v_segs, "V")
        if wxc is not None: sx = wxc

    # coliziune sambure -> aluneca DE-A LUNGUL peretelui, departe de sambure, apoi re-snap
    for _ in range(3):
        hit = next(((cx, cy) for (cx, cy) in columns if math.hypot(cx-sx, cy-sy) < SWITCH_COL_CLEAR), None)
        if hit is None:
            break
        if wall_h:
            sx += 18.0 if sx >= hit[0] else -18.0
            wyc = _nearest_wall_coord(sx, sy, h_segs, v_segs, "H")
            if wyc is not None: sy = wyc
        else:
            sy += 18.0 if sy >= hit[1] else -18.0
            wxc = _nearest_wall_coord(sx, sy, h_segs, v_segs, "V")
            if wxc is not None: sx = wxc

    return sx, sy, math.atan2(uy, ux)


def _door_room_index(d, room_boxes):
    """Indexul camerei pe care o SERVEȘTE ușa (punct 55pt în față, pe direcția de deschidere swing).
    None dacă nu cade în nicio cameră. (Aceeași logică ca vechiul served_room.)"""
    if not room_boxes:
        return None
    ux, uy = d["swing"]
    px = d["x"] + ux * 55.0; py = d["y"] + uy * 55.0
    for k, b in enumerate(room_boxes):
        if b and b[0] <= px <= b[0]+b[2] and b[1] <= py <= b[1]+b[3]:
            return k
    return None


def _switch_centers(centers, doors, columns, h_segs, v_segs, W, H, room_boxes=None):
    """REGULĂ NOUĂ — paritate 1:1: UN întrerupător per BEC.
    Pentru fiecare bec: dacă camera lui (bec.room = index) are o ușă NECONSUMATĂ -> întrerupător
    lângă acea ușă (refolosește plasarea lângă-ușă); o ușă consumată de un bec nu se reia pentru
    alt bec din aceeași cameră. Altfel -> lângă bec (35pt lateral). `room` = NUMELE camerei becului
    (bec.label), MEREU (niciodată null). GARANTAT: len(rezultat) == len(centers).
    -> [{x,y,angle,certain,room}]."""
    # uși grupate pe camera servită (index) — pentru a le potrivi cu becul din aceeași cameră
    doors_by_room = {}
    for d in doors:
        ri = _door_room_index(d, room_boxes)
        if ri is not None:
            doors_by_room.setdefault(ri, []).append(d)

    used = set()   # id(ușă) deja folosită -> nu se reia pentru alt bec
    out = []
    for c in centers:
        idx = c.get("room")            # index cameră (pt. potrivirea ușii)
        name = c.get("label")          # numele camerei becului (pt. expunere) — MEREU camera becului
        bx, by = c["x"], c["y"]
        free = [d for d in doors_by_room.get(idx, []) if id(d) not in used]
        if free:
            # cea mai apropiată ușă neconsumată de bec
            d = min(free, key=lambda dd: math.hypot(dd["x"]-bx, dd["y"]-by))
            used.add(id(d))
            sx, sy, angle = _switch_pos_at_door(d, columns, h_segs, v_segs)
            certain = d["certain"]
        else:
            # fără ușă disponibilă în cameră -> lângă bec (35pt lateral, cârlig orientat spre bec)
            sx, sy = bx + 35.0, by
            angle = math.pi
            certain = False
        out.append({"x": sx, "y": sy, "angle": angle, "certain": certain, "room": name})
    return out


# Seturi de tip (categorisire la redraw din plan_elements editat) — aceleasi valori ca CHECK + frontend.
_BULB_TYPES = {"lustra_led", "aplica_tavan", "aplica_perete", "aplica_senzor", "banda_led"}
_SWITCH_TYPES = {"intrerupator_simplu", "intrerupator_dublu", "intrerupator_triplu", "intrerupator_cap_scara"}
_PANEL_TYPES = {"tablou_teg", "tablou_tes", "tablou_te_ct", "transformator",
                "tablou_tcc", "tablou_inv", "tablou_tca"}   # FV-P2: tablourile FV si pe PDF
_FV_PANEL_ORDER = ("tablou_tcc", "tablou_inv", "tablou_tca")   # ordinea lantului (T.CC -> INV -> T.CA)
_PRIZA_TYPES = {"priza_simpla", "priza_dubla", "priza_16a", "priza_exterior_ip44"}
_RECEPTOR_TYPES = {"alimentare_receptor", "receptor_internet"}   # NIVEL 2: receptoare -> room geometric (pt. detectie tech in enrich)

# Culori tablou (RGB 0-1) + eticheta scurta — portate din Konva (PANEL_INFO).
# (colA = triunghi sus-dreapta, colB = triunghi jos-stanga).
_PANEL_DARK = (0.122, 0.141, 0.200)   # #1F2433 contur + conector + eticheta
_PANEL_INFO = {
    "tablou_teg":    ((0.941, 0.941, 0.941), (0.133, 0.773, 0.369), "TEG"),    # alb + verde
    "tablou_te_ct":  ((0.937, 0.267, 0.267), (0.231, 0.510, 0.965), "TE-CT"),  # rosu + albastru
    "tablou_tes":    ((0.941, 0.941, 0.941), (0.082, 0.396, 0.753), "TES"),    # alb + albastru #1565C0 (ca TEG, triunghi verde->albastru)
    "transformator": ((0.820, 0.835, 0.859), (0.420, 0.447, 0.502), "TR"),     # gri
    # FV-P2 (portate din Konva): T.CC/T.CA = tablou diagonal alb+negru; INV are branch propriu in
    # _draw_panel (patrat contur ROSU + diagonala + ~/=), colA/colB nefolosite acolo.
    "tablou_tcc":    ((0.941, 0.941, 0.941), (0.102, 0.102, 0.102), "T.CC"),
    "tablou_inv":    ((1.0, 1.0, 1.0),       (0.863, 0.149, 0.149), "INV"),
    "tablou_tca":    ((0.941, 0.941, 0.941), (0.102, 0.102, 0.102), "T.CA"),
}
_INV_RED = (0.863, 0.149, 0.149)   # #DC2626 — conturul/diagonala invertorului (= Konva)


def _draw_panel(page, x, y, element_type, scale=1.0, with_label=True):
    """Simbol tablou (analog Konva): dreptunghi 24x16 impartit DIAGONAL in 2 triunghiuri
    (TEG alb+verde, TE-CT rosu+albastru) + conector vertical scurt deasupra + eticheta (TEG/TE-CT).
    Centrat la (x,y) in PUNCTE PDF (direct, ca _draw_bulb/_draw_switch).
    scale: factor pe geometrie (forma identica, mai mica) — pt. legenda (L3).
    with_label=False -> NU deseneaza eticheta scurta (in legenda textul randului o spune). Default = neschimbat."""
    colA, colB, short = _PANEL_INFO.get(element_type, ((0.820, 0.835, 0.859), (0.420, 0.447, 0.502), "TAB"))
    s = scale

    def P(dx, dy):
        return fitz.Point(x + dx * s, y + dy * s)

    if element_type == "tablou_inv":
        # FV-P2: INVERTORUL — patrat ALB cu contur ROSU + diagonala + "~" (AC, sus-stanga) si
        # "=" (DC, jos-dreapta). IDENTIC cu simbolul Konva din editor (lectia O1: editor = PDF).
        page.draw_rect(fitz.Rect(x - 12 * s, y - 8 * s, x + 12 * s, y + 8 * s),
                       color=_INV_RED, fill=(1, 1, 1), width=1.4)
        page.draw_line(P(-12, 8), P(12, -8), color=_INV_RED, width=1.2)
        page.insert_text(P(-10, 1.5), "~", fontsize=10 * s, fontname="hebo", color=_PANEL_DARK)
        page.insert_text(P(3.5, 7), "=", fontsize=9 * s, fontname="hebo", color=_PANEL_DARK)
    else:
        # 2 triunghiuri pline (diagonala stanga-sus -> dreapta-jos): A sus-dreapta, B jos-stanga
        page.draw_polyline([P(-12, -8), P(12, -8), P(12, 8)], color=colA, fill=colA, width=0.3, closePath=True)
        page.draw_polyline([P(-12, -8), P(-12, 8), P(12, 8)], color=colB, fill=colB, width=0.3, closePath=True)
        # contur dreptunghi
        page.draw_rect(fitz.Rect(x - 12 * s, y - 8 * s, x + 12 * s, y + 8 * s), color=_PANEL_DARK, width=1.0)
    # conector vertical deasupra (comun)
    page.draw_line(P(0, -8), P(0, -16), color=_PANEL_DARK, width=1.4)
    # eticheta scurta sub dreptunghi (omisa in legenda)
    if with_label:
        page.insert_text(P(-12, 18), short, fontsize=8, fontname="hebo", color=_PANEL_DARK)


def _cable_l_path(a, b):
    """Traseu L (3 puncte) intre a=(x,y) si b=(x,y). Orientare dupa Δ mai mare:
    |Δx|>=|Δy| -> orizontal intai [a,(b.x,a.y),b]; altfel vertical intai [a,(a.x,b.y),b]."""
    ax, ay = a
    bx, by = b
    mid = (bx, ay) if abs(bx - ax) >= abs(by - ay) else (ax, by)
    return [a, mid, b]


# ── SOL B: routing pe "dunga" (traseu) trasa de inginer pe hol. ──
def _extract_stripe(elements):
    """Punctele dungii 'traseu' (cable_path) din elements, ca lista de (x,y) tuple (>=2 puncte).
    None daca nu exista dunga sau e malformata -> consumatorul cade pe L direct (fallback)."""
    for el in (elements or []):
        if (el.get("element_type") or "") != "traseu":
            continue
        cp = el.get("cable_path")
        if not isinstance(cp, (list, tuple)) or len(cp) < 2:
            return None
        pts = []
        for p in cp:
            try:
                pts.append((float(p[0]), float(p[1])))
            except (TypeError, ValueError, IndexError):
                return None
        return pts if len(pts) >= 2 else None
    return None


def _extract_stripes(elements):
    """FAZA B — TOATE dungile 'traseu' (cable_path) din elements, ca lista de polilinii
    [(x,y),...] (fiecare >=2 puncte). Sare peste cele malformate. Lista goala -> consumatorul
    cade pe L direct (exact ca fara dunga in faza A). elements sunt deja filtrate pe
    plansa/floor/plan_type in amonte -> corect din start."""
    out = []
    for el in (elements or []):
        if (el.get("element_type") or "") != "traseu":
            continue
        cp = el.get("cable_path")
        if not isinstance(cp, (list, tuple)) or len(cp) < 2:
            continue
        pts, ok = [], True
        for p in cp:
            try:
                pts.append((float(p[0]), float(p[1])))
            except (TypeError, ValueError, IndexError):
                ok = False
                break
        if ok and len(pts) >= 2:
            out.append(pts)
    return out


def _nearest_stripe_idx(a, stripes):
    """Indexul dungii CELEI MAI APROPIATE de punctul a (proiectie punct-pe-polilinie, distanta
    minima). Reutilizeaza _project_point_on_polyline (fara algoritm nou). stripes gol -> None.
    Determinist la egalitate: indexul mai mic castiga (cablu ~egal intre 2 trasee -> cosmetic)."""
    if not stripes:
        return None
    best_i, best_d = 0, None
    for i, s in enumerate(stripes):
        proj, _, _ = _project_point_on_polyline(a, s)
        d = math.hypot(a[0] - proj[0], a[1] - proj[1])
        if best_d is None or d < best_d:
            best_d, best_i = d, i
    return best_i


def _project_point_on_polyline(p, pts):
    """Proiectia lui p=(x,y) pe polilinia pts=[(x,y),...]: pe fiecare segment, proiectie
    punct-pe-segment cu t clampat in [0,1]; pastreaza cea mai apropiata. Returneaza
    (proj=(x,y), seg_idx, t). pts cu <2 puncte -> (p, 0, 0.0)."""
    if not pts or len(pts) < 2:
        return p, 0, 0.0
    px, py = p
    best = None   # (dist2, proj, seg_idx, t)
    for i in range(len(pts) - 1):
        ax, ay = pts[i]; bx, by = pts[i + 1]
        dx, dy = bx - ax, by - ay
        seg2 = dx * dx + dy * dy
        if seg2 <= 1e-9:
            t = 0.0
        else:
            t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg2))
        qx, qy = ax + t * dx, ay + t * dy
        d2 = (px - qx) ** 2 + (py - qy) ** 2
        if best is None or d2 < best[0]:
            best = (d2, (qx, qy), i, t)
    return best[1], best[2], best[3]


# ── Priza de pamant (grounding): platbanda 40x4 OL-Zn pe conturul fundatiei + legatura 20x2 la TEG. ──
_GROUND_COLOR = (0.95, 0.45, 0.05)     # PORTOCALIU — distinct de rosu (iluminat) si albastru (_PRIZA_COLOR forta)
_GROUND_PLATBANDA_WIDTH = 1.8          # priza 40x4 = cea mai groasa (40x4 > 20x2 > cabluri normale 0.8)
_GROUND_LEGATURA_WIDTH = 1.2           # legatura TEG->priza 20x2 (mai subtire ca platbanda, mai groasa ca cablurile)


def _draw_ground_electrode(page, el_ground, teg_xy=None):
    """Deseneaza priza de pamant trasata manual de inginer (element ground_electrode_path):
      - platbanda 40x4 = poligon INCHIS solid portocaliu pe punctele cable_path (conturul fundatiei);
      - (optional) legatura 20x2 = segment perpendicular TEG -> cel mai apropiat punct de pe contur.
    cable_path = puncte PDF (>=2). teg_xy=(x,y) sau None (TEG lipsa pe plansa -> DOAR platbanda).
    Defensiv: cable_path lipsa/malformat -> nu deseneaza nimic (return False, nu crapa).
    Returneaza True daca a desenat platbanda."""
    cp = el_ground.get("cable_path")
    if not isinstance(cp, (list, tuple)) or len(cp) < 2:
        return False
    pts = []
    for p in cp:
        try:
            pts.append(fitz.Point(float(p[0]), float(p[1])))
        except (TypeError, ValueError, IndexError):
            return False
    if len(pts) < 2:
        return False
    # Platbanda: poligon INCHIS solid (closePath adauga latura ultimul->primul). Fara fill (e o linie, nu suprafata).
    page.draw_polyline(pts, color=_GROUND_COLOR, width=_GROUND_PLATBANDA_WIDTH, closePath=True)
    # Legatura TEG->priza: perpendiculara pe cel mai apropiat segment al conturului INCHIS.
    if teg_xy is not None:
        try:
            tx, ty = float(teg_xy[0]), float(teg_xy[1])
        except (TypeError, ValueError, IndexError):
            return True
        ring = [(pt.x, pt.y) for pt in pts] + [(pts[0].x, pts[0].y)]   # inchide inelul pt. proiectie
        proj, _seg, _t = _project_point_on_polyline((tx, ty), ring)
        page.draw_line(fitz.Point(tx, ty), fitz.Point(proj[0], proj[1]),
                       color=_GROUND_COLOR, width=_GROUND_LEGATURA_WIDTH)
    return True


_BUNDLE_GAP = 3.0   # MANUNCHI: offset lateral (pt) intre cabluri care converg pe ACEEASI dunga (paralele, nu suprapuse)


def _offset_polyline(pts, offset):
    """Deplaseaza polilinia pts LATERAL cu `offset` pt (perpendicular pe directie). Pt. MANUNCHI:
    fiecare cablu ruteaza pe o COPIE deplasata a dungii -> apar PARALELE pe portiunea comuna.
    Normala per-varf = media normalelor segmentelor adiacente (miter). offset 0 / <2 puncte -> neschimbat."""
    n = len(pts)
    if n < 2 or abs(offset) < 1e-9:
        return list(pts)

    def _perp(p, q):
        dx, dy = q[0] - p[0], q[1] - p[1]
        L = math.hypot(dx, dy) or 1.0
        return (-dy / L, dx / L)                 # normala stanga (unitara)

    out = []
    for i in range(n):
        if i == 0:
            nx, ny = _perp(pts[0], pts[1])
        elif i == n - 1:
            nx, ny = _perp(pts[n - 2], pts[n - 1])
        else:
            a1 = _perp(pts[i - 1], pts[i]); a2 = _perp(pts[i], pts[i + 1])
            nx, ny = a1[0] + a2[0], a1[1] + a2[1]
            L = math.hypot(nx, ny) or 1.0
            nx, ny = nx / L, ny / L
        out.append((pts[i][0] + nx * offset, pts[i][1] + ny * offset))
    return out


def _orthogonalize(guide):
    """Transforma o polilinie OARECARE (posibil diagonala/stramba) intr-una ORTOGONALA (Manhattan TOTAL):
    fiecare segment p->q devine un L (H+V) prin coltul din _cable_l_path. Astfel, oricat de STRAMBA
    e dunga-ghid, cablul iese in TREPTE DREPTE pe langa ea. Elimina duplicate consecutive."""
    g = []
    for q in guide:                              # dedupe intrare (proiectie == varf etc.)
        if not g or abs(g[-1][0] - q[0]) > 1e-6 or abs(g[-1][1] - q[1]) > 1e-6:
            g.append((q[0], q[1]))
    if len(g) < 2:
        return g
    out = [g[0]]
    for i in range(len(g) - 1):
        corner = _cable_l_path(g[i], g[i + 1])[1]
        for pt in (corner, g[i + 1]):
            if abs(out[-1][0] - pt[0]) > 1e-6 or abs(out[-1][1] - pt[1]) > 1e-6:
                out.append(pt)
    return out


def _stripe_path(a, b, pts, offset=0.0):
    """Traseu prin dunga, ORTOGONAL TOTAL: a -> proiectie_a -> (varfuri dungii intre proiectii) ->
    proiectie_b -> b, apoi TOT traseul ortogonalizat (trepte drepte). Dunga = doar GHID de directie,
    NU trebuie sa fie dreapta: oricat de stramba, cablul iese drept. `offset` (MANUNCHI) deplaseaza
    dunga lateral -> cabluri PARALELE pe portiunea comuna. pts lipsa/<2 -> L direct."""
    if not pts or len(pts) < 2:
        return _cable_l_path(a, b)
    spts = _offset_polyline(pts, offset)         # MANUNCHI: copie deplasata a dungii (offset 0 -> identica)
    pa, ia, ta = _project_point_on_polyline(a, spts)
    pb, ib, tb = _project_point_on_polyline(b, spts)
    if ia + ta <= ib + tb:                       # inainte pe dunga
        mids = [spts[j] for j in range(ia + 1, ib + 1)]
    else:                                        # inapoi pe dunga -> varfuri in ordine inversa
        mids = [spts[j] for j in range(ib + 1, ia + 1)][::-1]
    out = _orthogonalize([a, pa] + mids + [pb, b])
    return out if len(out) >= 2 else _cable_l_path(a, b)


_CABLE_COLOR = RED   # ROSU #DB2929 — ca becurile (circuit iluminat coerent + lizibil; albastrul dungat nu se citea). Prizele forta = _PRIZA_COLOR (raman albastre)


def _draw_cable(page, path, color=None, width=0.8):
    """Cablu = polilinie SUBTIRE INTRERUPTA (dashed) pe traseu (path = [(x,y),...]).
    Defensiv: path lipsa / <2 puncte -> skip."""
    if not path or len(path) < 2:
        return
    col = color or _CABLE_COLOR
    for i in range(len(path) - 1):
        page.draw_line(fitz.Point(path[i][0], path[i][1]), fitz.Point(path[i + 1][0], path[i + 1][1]),
                       color=col, width=width, dashes="[3 2] 0")


# ── GROSIME cabluri pe TREPTE (manunchi): 1 -> subtire, 2-3 -> mediu, 4+ -> gros. Valori AJUSTABILE. ──
_CABLE_W_THIN, _CABLE_W_MED, _CABLE_W_THICK = 0.8, 1.8, 2.8

def _cable_width_for(count):
    """Grosimea liniei pe TREPTE dupa cate cabluri sunt in manunchi (count)."""
    try:
        n = int(count or 1)
    except (TypeError, ValueError):
        n = 1
    if n >= 4: return _CABLE_W_THICK
    if n >= 2: return _CABLE_W_MED
    return _CABLE_W_THIN


# ── CUMSUM pe dunga: cablurile de la camere se ADUNA -> grosimea creste spre tablou. ──
def _arc_lengths(pts):
    arcs = [0.0]
    for i in range(1, len(pts)):
        arcs.append(arcs[-1] + math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]))
    return arcs

def _arc_of_proj(xy, pts, arcs):
    """(arc_pozitie, punct_proiectat) al proiectiei lui xy pe polilinia pts."""
    proj, seg_i, t = _project_point_on_polyline(xy, pts)
    seg_len = (arcs[seg_i + 1] - arcs[seg_i]) if seg_i + 1 < len(arcs) else 0.0
    return arcs[seg_i] + t * seg_len, proj

def _point_at_arc(pts, arcs, target):
    if target <= 0: return pts[0]
    if target >= arcs[-1]: return pts[-1]
    for i in range(1, len(arcs)):
        if arcs[i] >= target:
            seg = arcs[i] - arcs[i - 1]
            t = (target - arcs[i - 1]) / seg if seg > 1e-9 else 0.0
            return (pts[i - 1][0] + t * (pts[i][0] - pts[i - 1][0]),
                    pts[i - 1][1] + t * (pts[i][1] - pts[i - 1][1]))
    return pts[-1]

def _subpath_between(pts, arcs, a0, a1):
    lo, hi = (a0, a1) if a0 <= a1 else (a1, a0)
    out = [_point_at_arc(pts, arcs, lo)]
    for i in range(len(pts)):
        if lo < arcs[i] < hi:
            out.append(pts[i])
    out.append(_point_at_arc(pts, arcs, hi))
    return out

def _mk_cable(path, kind, room, count):
    length = sum(math.hypot(path[i + 1][0] - path[i][0], path[i + 1][1] - path[i][1])
                 for i in range(len(path) - 1)) if path and len(path) >= 2 else 0.0
    return {"from_type": None, "from_xy": path[0] if path else None, "to_type": None,
            "to_xy": path[-1] if path else None, "path": path, "kind": kind,
            "length": round(length, 1), "room": room, "via_stripe": True, "stripe_idx": None,
            "count": count}

def _stripe_thickness(grp, spts):
    """Inlocuieste manunchiul de pe o dunga cu: (1) cozile priza->punct de intrare pe dunga (grosime =
    count-ul circuitului) + (2) coloana comuna de pe dunga, SPARTA pe segmente cu count CUMULAT (toate
    ies la tablou -> segmentul de langa tablou = suma tuturor -> cel mai gros). spts <2 -> grup neschimbat."""
    if not spts or len(spts) < 2 or not grp:
        return grp
    arcs = _arc_lengths(spts)
    drain_xy = grp[0].get("to_xy")                        # tabloul (comun pe dunga)
    drain_arc, drain_proj = _arc_of_proj(drain_xy, spts, arcs)
    kind0, room0 = grp[0].get("kind"), grp[0].get("room")
    entries = []                                          # (entry_arc, weight, from_xy, entry_pt)
    for c in grp:
        ea, ep = _arc_of_proj(c.get("from_xy"), spts, arcs)
        entries.append((ea, int(c.get("count") or 1), c.get("from_xy"), ep))
    out = []
    for ea, w, fxy, ep in entries:                        # coada: priza(cap lant) -> intrare pe dunga
        out.append(_mk_cable(_cable_l_path(fxy, ep), kind0, room0, w))
    bps = sorted(set([e[0] for e in entries] + [drain_arc]))
    for i in range(len(bps) - 1):                         # coloana comuna, cumsum pe segmente
        lo, hi = bps[i], bps[i + 1]
        mid = (lo + hi) / 2.0
        cum = sum(w for ea, w, _, _ in entries if min(ea, drain_arc) <= mid <= max(ea, drain_arc))
        if cum <= 0:
            continue
        out.append(_mk_cable(_subpath_between(spts, arcs, lo, hi), kind0, room0, cum))
    total = sum(w for _, w, _, _ in entries)
    out.append(_mk_cable(_cable_l_path(drain_proj, drain_xy), kind0, room0, total))   # dunga -> tablou
    return out


_BUNDLE_CAP = 5   # cate manunchiuri PARALELE distincte incap pe o dunga (surplusul se cumuleaza in slotul exterior)
# coloana TE-CT (teal) = slot LATERAL fix, dincolo de manunchiurile de prize (centrate pe ±(cap-1)/2*gap=±6pt)
_COLUMN_STRIPE_OFFSET = ((_BUNDLE_CAP - 1) / 2.0 + 1.0) * _BUNDLE_GAP   # = 9pt


def _stripe_parallel(grp, spts, cap=_BUNDLE_CAP, gap=_BUNDLE_GAP):
    """BUG 4: manunchiurile care urmeaza ACEEASI dunga se deseneaza PARALEL (offset lateral simetric),
    NU cumulate intr-o linie groasa. Fiecare cablu re-rutat via _stripe_path cu offset-ul slotului lui:
      - ALOCARE GEOGRAFICA: sortare dupa latura de intrare (proiectia perpendiculara a from_xy pe dunga)
        -> cel din stanga primeste slotul din stanga (fara incrucisari la intrare).
      - offset(slot i din n) = (i - (n-1)/2) * gap, simetric fata de centru.
      - CAPACITATE cap: primele cap sloturi distincte; surplusul (cap+1..) -> slotul exterior (cumulat).
    Endpoint-urile (from_xy/to_xy) raman FIXE (doar portiunea comuna de pe dunga e paralela). spts<2 -> neschimbat."""
    if not spts or len(spts) < 2 or not grp:
        return grp
    arcs = _arc_lengths(spts)
    dx, dy = spts[-1][0] - spts[0][0], spts[-1][1] - spts[0][1]
    L = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / L, dx / L                              # normala unitara a dungii (axa perpendiculara)

    def _side(c):                                         # latura de intrare = proiectia perpendiculara a from_xy
        fxy = c.get("from_xy")
        if not fxy:
            return 0.0
        _ea, ep = _arc_of_proj(fxy, spts, arcs)
        return (fxy[0] - ep[0]) * nx + (fxy[1] - ep[1]) * ny

    ordered = sorted(grp, key=_side)                      # geografic: stanga->dreapta pe axa perpendiculara
    nslots = min(len(ordered), cap)
    out = []
    for i, c in enumerate(ordered):
        slot = min(i, cap - 1)                            # surplus -> slotul exterior
        off = (slot - (nslots - 1) / 2.0) * gap           # simetric fata de centrul dungii
        a, b = c.get("from_xy"), c.get("to_xy")
        c2 = dict(c)
        if a and b:
            c2["path"] = _stripe_path(a, b, spts, offset=off)   # re-rutare PARALELA (endpoint-uri fixe)
        out.append(c2)
    return out


_HEATING_KW = ("boiler", "pdc", "pompa", "bms", "automatizare", "distribuitor", "aer-apa", "sol-apa",
               "centrala")   # T3: "centrala electrica/pe gaz/termica" = clasa 1 (era doar "centrala termic")


def _norm_lbl(label):
    return (label or "").strip().lower().replace("ă", "a").replace("â", "a").replace("î", "i").replace("ș", "s").replace("ț", "t")


# ── REGULA 10: receptoare termice (VCV + radiatoare GRUPATE + distribuitor de ZONA) ──
# VCV/radiator = grupate pe (etaj, faza), plafon 2kW, putere REALA insumata (grupate in
# compute_circuits = sursa unica pt. circuit_id). Distribuitorul de ZONA = dedicat 1:1 (ca boiler)
# DAR pe TEG/TES (NU clasa 1) — distinct de "Distribuitor principal incalzire" (TE-CT). Detectia pe
# LABEL (element_type ramane alimentare_receptor -> fara migratie de tip).
_GROUPED_HEATING_DEFAULT_W = {"vcv": 100, "radiator": 1500}   # fallback cand power_w lipseste (H2 il seteaza la inserare)


def _is_zone_distributor(label):
    """Distribuitor de ZONA/NIVEL (dedicat, TEG/TES) — distinct de 'Distribuitor principal incalzire'
    (TE-CT, clasa 1). CAPCANA 1: fara asta, cuvantul 'distribuitor' l-ar trimite la clasa 1 + l-ar
    contopi prin dedup cu cel principal."""
    t = _norm_lbl(label)
    return "distribuitor" in t and ("zona" in t or "nivel" in t)


def _grouped_heating_kind(label):
    """'vcv' | 'radiator' | None — tipurile GRUPATE (putere reala insumata). Distribuitorul de zona NU
    e grupat (e dedicat 1:1); boiler/cuptor/etc. NU sunt aici (dedicate)."""
    t = _norm_lbl(label)
    if "ventiloconvector" in t or "vcv" in t:
        return "vcv"
    if "radiator" in t:
        return "radiator"
    return None


def _is_heating_receptor(label):
    """Receptor din CLASA 1 (echipament de incalzire, legat de TE-CT indiferent de pozitie):
    boiler/pdc/pompe/bms/distribuitor. Clasa 2 (cuptor/AC/internet/EV) -> panel dupa camera.
    EXCEPTIE (Regula 10): distribuitorul de ZONA/NIVEL NU e clasa 1 (merge pe TEG/TES, nu TE-CT)."""
    if _is_zone_distributor(label):
        return False                                   # CAPCANA 1: distribuitor zona != cel principal
    return any(k in _norm_lbl(label) for k in _HEATING_KW)


# ── COLOANE de legatura intre tablouri (feed sub-tablou): TEG<->TE-CT/TES. Culoare TEAL distincta. ──
_COLUMN_COLOR = (0.0, 0.514, 0.561)   # #00838F TEAL (distinct de rosu cabluri / violet retea / albastru prize)
# FV-P3: lantul fotovoltaic T.CC->INV->T.CA->TEG — GALBEN AURIU #F9A825 (decizia Dan: se vede
# clar pe alb si se distinge COMPLET de priza de pamant portocalie). Constanta e folosita si de
# linia de pe plan, si de randul legendei -> consistent automat.
_FV_LINK_COLOR = (0.976, 0.659, 0.145)
# Coloana TEG->TES (cross-plansa) + simbolurile ei de traversare: VERDE INCHIS #1B5E20 (decizia Dan) —
# DISTINCTA de teal-ul coloanei TE-CT, vizibila pe planul gri/negru + fundal alb. SURSA UNICA.
_TES_COLUMN_COLOR = (0.106, 0.369, 0.125)

def _draw_column(page, a, b, width=2.6, path=None, color=None):
    """Coloana de legatura = linie SOLIDA groasa de la a=(x,y) la b=(x,y). Ex. TE-CT -> TEG.
    `path` (polilinie) dat -> coloana URMEAZA TRASEUL desenat de inginer (patul de cabluri comun,
    ca in realitate), nu taie prin incaperi. Fara path -> L ortogonal direct (fallback, ca inainte).
    `color` None -> TEAL (coloana TE-CT, neschimbata); coloana TES paseaza verdele ei.
    a/b lipsa -> skip."""
    if not a or not b:
        return
    col = color or _COLUMN_COLOR
    if path and len(path) >= 2:
        for i in range(len(path) - 1):
            page.draw_line(fitz.Point(path[i][0], path[i][1]), fitz.Point(path[i + 1][0], path[i + 1][1]),
                           color=col, width=width)
        return
    mid = (b[0], a[1]) if abs(b[0] - a[0]) >= abs(b[1] - a[1]) else (a[0], b[1])
    for p, q in ((a, mid), (mid, b)):
        page.draw_line(fitz.Point(p[0], p[1]), fitz.Point(q[0], q[1]), color=col, width=width)


# ── CROSS-PLANSA (TEG parter <-> TES etaj): transformarea intre plansele etajelor + simbolul de
# traversare. R&D (masurat pe 9926+701b): plansele-s SUPRAPUSE — translatie PURA (spread 0.02pt),
# offset ~2.6pt. Cascada obligatorie: (a) axele CAD (grid, ~0.1pt) -> (b) pereti (mediana deltelor)
# -> (c) IDENTITATE (etaje desenate suprapus in CAD = practica standard; eroare ~3pt, sub simbol).
# Niciodata "nu desena". ──
def _grid_rects(page):
    """Dreptunghiurile itemelor de pe layerele de AXE structurale (grid/axe/axis), sortate —
    amprenta axelor e identica intre etaje (aceleasi axe) => diferentele dau translatia."""
    return sorted((round(d["rect"].x0, 2), round(d["rect"].y0, 2), round(d["rect"].x1, 2), round(d["rect"].y1, 2))
                  for d in page.get_drawings()
                  if any(k in (d.get("layer") or "").lower() for k in ("grid", "axe", "axis")))


def floor_offset(pdf_from_b64, pdf_to_b64):
    """Translatia care duce coordonatele plansei FROM in plansa TO: p_to = p_from + (dx, dy).
    Returneaza (dx, dy, sursa) cu sursa in {'grid','walls','identity'}. Defensiv: orice esec -> identitate."""
    try:
        a_raw = (pdf_from_b64 or "").split(",", 1)[-1]
        b_raw = (pdf_to_b64 or "").split(",", 1)[-1]
        if not a_raw or not b_raw:
            return 0.0, 0.0, "identity"
        A = fitz.open(stream=base64.b64decode(a_raw), filetype="pdf")
        B = fitz.open(stream=base64.b64decode(b_raw), filetype="pdf")
        try:
            pa, pb = A[0], B[0]
            ga, gb = _grid_rects(pa), _grid_rects(pb)
            if ga and len(ga) == len(gb) and len(ga) >= 4:
                dx = sorted([b[0] - a[0] for a, b in zip(ga, gb)] + [b[2] - a[2] for a, b in zip(ga, gb)])
                dy = sorted([b[1] - a[1] for a, b in zip(ga, gb)] + [b[3] - a[3] for a, b in zip(ga, gb)])
                if max(dx[-1] - dx[0], dy[-1] - dy[0]) <= 1.0:      # translatie PURA (nu forme diferite)
                    return dx[len(dx) // 2], dy[len(dy) // 2], "grid"
            # (b) peretii: pozitiile fetelor (x verticali / y orizontali), mediana deltelor nearest
            import geometry as _g
            hA, vA, _ = _g._collect(pa)
            hB, vB, _ = _g._collect(pb)

            def _pos(segs):
                vals = sorted(p[2] for p in segs if abs(p[1] - p[0]) > 15)
                out = []
                for v in vals:
                    if not out or v - out[-1] > 1.5:
                        out.append(v)
                return out
            xa, xb, ya, yb = _pos(vA), _pos(vB), _pos(hA), _pos(hB)
            if xa and xb and ya and yb:
                # registration 1D robust: MODUL diferentelor pereche-la-pereche (nu nearest-median —
                # fetele de perete dese fac nearest-ul degenerat, mediana trage spre 0). Peretii
                # OMOLOGI (multi) voteaza toti aceeasi translatie; zgomotul se imprastie in binuri.
                def _mode_delta(av, bv, win=12.0, binw=0.5):
                    votes = {}
                    for a in av:
                        for b in bv:
                            d = b - a
                            if abs(d) <= win:
                                votes.setdefault(round(d / binw) * binw, []).append(d)
                    if not votes:
                        return 0.0
                    best = max(votes.values(), key=len)
                    best.sort()
                    return best[len(best) // 2]
                return _mode_delta(xa, xb), _mode_delta(ya, yb), "walls"
        finally:
            A.close()
            B.close()
    except Exception:
        pass
    return 0.0, 0.0, "identity"


def _draw_floor_crossing(page, x, y, up=True, label=None):
    """Simbol conventional de traversare intre niveluri (varianta A, decizia Dan): cerc VERDE INCHIS
    (_TES_COLUMN_COLOR, ca si coloana TES — distinct de teal-ul TE-CT) cu sageata verticala (SUS =
    coloana urca la etaj; JOS = alimentarea vine de jos) + eticheta bold.
    Plasat la POZITIA (proiectata a) tabloului de pe celalalt nivel."""
    r = 8.0
    page.draw_circle(fitz.Point(x, y), r, color=_TES_COLUMN_COLOR, fill=(1, 1, 1), width=1.8)
    tip_y = y - 4.5 if up else y + 4.5                     # varful sagetii spre directia de mers
    tail_y = y + 4.5 if up else y - 4.5
    page.draw_line(fitz.Point(x, tail_y), fitz.Point(x, tip_y), color=_TES_COLUMN_COLOR, width=1.6)
    wing_y = tip_y + (3.2 if up else -3.2)                 # aripile varfului, inapoi spre coada
    for dx in (-2.6, 2.6):
        page.draw_line(fitz.Point(x, tip_y), fitz.Point(x + dx, wing_y), color=_TES_COLUMN_COLOR, width=1.6)
    if label:
        # eticheta DEASUPRA simbolului (sub el pica de regula pe numele camerei — text negru bold)
        fs = 7.5
        w = fitz.get_text_length(label, fontname="hebo", fontsize=fs)
        page.insert_text(fitz.Point(x - w / 2.0, y - r - 4.0), label,
                         fontsize=fs, fontname="hebo", color=_TES_COLUMN_COLOR)


# ── LEGENDA (L3): deseneaza caseta legendei pe PDF (chenar + titlu + randuri simbol+text). ──
# Ancora (x,y) = COLT STANGA-SUS (consistent cu caseta Konva din editor). Fundal ALB OPAC (acopera
# planul dedesubt). Simbolurile se redeseneaza MIC prin `scale` (o singura sursa de forme — regula Dan).
_LEGEND_BORDER = (0.20, 0.22, 0.28)   # chenar gri inchis
_LEGEND_TITLE = (0.07, 0.09, 0.14)    # titlu


def _draw_legend(page, x, y, rows):
    """Caseta legenda la (x,y)=colt stanga-sus. rows = build_legend_rows(...) [{kind, element_type?, text}].
    Fiecare rand: simbol mic (stanga, prin scale) + text (dreapta). Chenar + fundal alb opac."""
    rows = rows or []
    PAD = 7.0
    TITLE_FS = 9.5
    TITLE_H = 15.0
    ROW_H = 17.0
    SYM_W = 30.0          # latimea celulei de simbol (stanga)
    ROW_FS = 8.0
    GAP = 5.0             # spatiu simbol -> text
    WHITE = (1, 1, 1)

    # dimensiuni casetei: latime = celula simbol + cea mai lata LINIE + padding (randurile FV au
    # `lines` — wrap pe 2 randuri, O2 — ca sa nu lateasca toata caseta cu texte de ~100 caractere).
    # latimea textului EXACTA via fitz.get_text_length (nu estimare) -> textul lung NU e taiat/depasit.
    LINE_H = 9.5   # inaltimea unei linii suplimentare intr-un rand multi-line
    def _row_lines(r):
        return r.get("lines") or [r.get("text") or ""]
    def _row_h(r):
        return ROW_H + (len(_row_lines(r)) - 1) * LINE_H
    txt_w = max([fitz.get_text_length(ln, fontname="helv", fontsize=ROW_FS)
                 for r in rows for ln in _row_lines(r)] + [0.0])
    title_w = fitz.get_text_length("LEGENDA", fontname="hebo", fontsize=TITLE_FS)
    box_w = max(PAD + SYM_W + GAP + txt_w + PAD, PAD + title_w + PAD)
    box_h = PAD + TITLE_H + sum(_row_h(r) for r in rows) + PAD

    # 1) chenar + fundal alb opac (acopera planul dedesubt)
    page.draw_rect(fitz.Rect(x, y, x + box_w, y + box_h), color=_LEGEND_BORDER, fill=WHITE, width=1.0)
    # 2) titlu + linie subtire sub el
    page.insert_text(fitz.Point(x + PAD, y + PAD + TITLE_FS), "LEGENDA",
                     fontsize=TITLE_FS, fontname="hebo", color=_LEGEND_TITLE)
    ty = y + PAD + TITLE_H - 2.0
    page.draw_line(fitz.Point(x + PAD, ty), fitz.Point(x + box_w - PAD, ty), color=_LEGEND_BORDER, width=0.6)

    # 3) randuri: simbol mic (stanga) + text (dreapta); inaltimi CUMULATE (randurile FV au 2 linii)
    text_x = x + PAD + SYM_W + GAP
    row_top = y + PAD + TITLE_H
    for i, r in enumerate(rows):
        rh = _row_h(r)
        cy = row_top + rh / 2.0
        cx = x + PAD + SYM_W / 2.0
        kind = r.get("kind")
        if kind == "bulb":
            _draw_bulb(page, cx, cy, r.get("element_type") or "aplica_tavan", y_offset=0, scale=0.42)
        elif kind == "panel":
            # +2 vertical: conectorul tabloului urca ~8pt -> centreaza simbolul in celula
            _draw_panel(page, cx, cy + 2.0, r.get("element_type") or "", scale=0.5, with_label=False)
        elif kind == "switch":
            # intrerupatorul porneste din ancora si se intinde pe directia angle (0=spre dreapta);
            # centram orizontal in celula (extent ~25.5pt la scale 1 -> offset jumatate)
            _sw_s = 0.5
            _draw_switch(page, cx - 12.75 * _sw_s, cy, 0.0,
                         r.get("element_type") or "intrerupator_simplu", scale=_sw_s)
        elif kind == "prize":
            _draw_priza(page, cx, cy, r.get("element_type") or "priza_simpla", scale=0.5)
        elif kind == "receptor":
            _draw_priza(page, cx, cy, "priza_16a", scale=0.5)          # simbolul de alimentare
        elif kind == "internet":
            _draw_internet(page, cx, cy, scale=0.5)                     # caseta violet mica
        elif kind == "cable":
            # MANUNCHI: 3 linii paralele scurte (ilustreaza manunchiul de cabluri)
            for _dy in (-2.3, 0.0, 2.3):
                _draw_cable(page, [(x + PAD + 3.0, cy + _dy), (x + PAD + SYM_W - 3.0, cy + _dy)], width=0.7)
        elif kind == "column":
            # COLOANA: linie SOLIDA groasa — TEAL pt. TE-CT, VERDE INCHIS pt. TES (cross-plansa)
            _ccol = _TES_COLUMN_COLOR if (r.get("feeds_panel") or "").startswith("TES") else _COLUMN_COLOR
            page.draw_line(fitz.Point(x + PAD + 3.0, cy), fitz.Point(x + PAD + SYM_W - 3.0, cy),
                           color=_ccol, width=2.2)
        elif kind == "fv_link":
            # FV-P3: lantul fotovoltaic — linie intrerupta PORTOCALIE (ca pe plan)
            _draw_cable(page, [(x + PAD + 3.0, cy), (x + PAD + SYM_W - 3.0, cy)],
                        color=_FV_LINK_COLOR, width=1.2)
        elif kind == "crossing":
            # TRAVERSARE NIVEL: cercul cu sageata (sus/jos), micsorat pt. celula legendei
            _draw_floor_crossing(page, cx, cy, up=bool(r.get("up", True)), label=None)
        # textul randului (baseline ~ cy + fs*0.35 -> centrat vertical aprox); multi-line (FV):
        # liniile centrate ca bloc pe cy, la LINE_H una sub alta
        _lines = _row_lines(r)
        ty0 = cy + ROW_FS * 0.35 - (len(_lines) - 1) * LINE_H / 2.0
        for j, ln in enumerate(_lines):
            page.insert_text(fitz.Point(text_x, ty0 + j * LINE_H), ln,
                             fontsize=ROW_FS, fontname="helv", color=(0, 0, 0))
        row_top += rh


# ── FAZA 2a: rutare prize pe PERIMETRUL bbox (nu L direct prin interior). ──
def _rect_perim(R):
    x0, y0, x1, y1 = R
    return (x1 - x0), (y1 - y0), 2 * ((x1 - x0) + (y1 - y0))

def _point_at_t(t, R):
    """Punctul de pe conturul dreptunghiului R la pozitia t (perimetru, sens orar de la coltul stanga-sus)."""
    x0, y0, x1, y1 = R
    w, h, P = _rect_perim(R)
    if P <= 0:
        return (x0, y0)
    t %= P
    if t <= w: return (x0 + t, y0)
    t -= w
    if t <= h: return (x1, y0 + t)
    t -= h
    if t <= w: return (x1 - t, y1)
    t -= w
    return (x0, y1 - t)

def _project_to_rect(px, py, R):
    """Proiectia (px,py) pe latura CEA MAI APROPIATA a lui R -> (punct_contur, t_perimetru)."""
    x0, y0, x1, y1 = R
    w, h, P = _rect_perim(R)
    cx = min(max(px, x0), x1); cy = min(max(py, y0), y1)
    cands = [
        (abs(py - y0), (cx, y0), cx - x0),                  # sus
        (abs(px - x1), (x1, cy), w + (cy - y0)),            # dreapta
        (abs(py - y1), (cx, y1), w + h + (x1 - cx)),        # jos
        (abs(px - x0), (x0, cy), 2 * w + h + (y1 - cy)),    # stanga
    ]
    _, bp, t = min(cands, key=lambda c: c[0])
    return bp, t

# ── PUNCTUL 3: orientarea prizei din bbox-ul camerei (NU din campul `rotation`) ──
def _wall_orient(px, py, R):
    """Latura CORECTA a camerei pt. priza (px,py) -> (bp, inward, along):
      bp     = punct pe perete (proiectie pe latura aleasa);
      inward = versor spre INTERIORUL camerei;  along = versor PARALEL cu peretele.
    IN INTERIOR: latura cea mai apropiata (ca la _project_to_rect).
    IN AFARA bbox-ului (bug confirmat pe randarea reala 770c8edd: bbox-ul Vision != peretele real,
    priza snap-uita pe peretele real cade dincolo de latura): latura = DIRECTIA DEPASIRII (axa cu
    violarea mai mare), NU min-distanta pe toate 4 — altfel se alegea o latura perpendiculara /
    un colt (ex. priza la 31pt sub bbox dar la 13pt de latura din dreapta -> 'dreapta') si
    semicercul iesea INTORS / ancorat pe colt. Prizele exact PE muchie (violare 0) = interior -> stabil."""
    x0, y0, x1, y1 = R
    cx = min(max(px, x0), x1); cy = min(max(py, y0), y1)
    SIDES = {
        "sus":     ((cx, y0), (0.0, 1.0), (1.0, 0.0)),      # interior = JOS
        "dreapta": ((x1, cy), (-1.0, 0.0), (0.0, 1.0)),     # interior = STANGA
        "jos":     ((cx, y1), (0.0, -1.0), (1.0, 0.0)),     # interior = SUS
        "stanga":  ((x0, cy), (1.0, 0.0), (0.0, 1.0)),      # interior = DREAPTA
    }
    vx = (x0 - px) if px < x0 else ((px - x1) if px > x1 else 0.0)   # violarea pe x (>0 = in afara)
    vy = (y0 - py) if py < y0 else ((py - y1) if py > y1 else 0.0)
    if vx > 0.0 or vy > 0.0:               # IN AFARA -> latura din directia depasirii
        if vy >= vx:
            side = "sus" if py < y0 else "jos"
        else:
            side = "stanga" if px < x0 else "dreapta"
    else:                                   # IN INTERIOR -> latura cea mai apropiata
        d = {"sus": abs(py - y0), "dreapta": abs(px - x1), "jos": abs(py - y1), "stanga": abs(px - x0)}
        side = min(d, key=d.get)
    bp, inward, along = SIDES[side]
    return bp, inward, along

_PRIZA_BAR_HALF = 7.7   # jumatatea barei de montaj (pt) — capatul barei = startul stub-ului de cablu

def _room_centroids(elements):
    """{room: (cx,cy)} = centroidul GEOMETRIC REAL al elementelor plasate in camera (becuri,
    intrerupatoare, prize, receptoare — orice element cu room). Sursa de ORIENTARE a prizelor:
    bbox-ul Vision e mai mic/nealiniat fata de camera reala, dar elementele sunt puse de inginer
    pe geometria REALA -> centroidul lor e in interiorul camerei reale."""
    pts = {}
    for el in (elements or []):
        room = ((el or {}).get("room") or "").strip()
        et = (el or {}).get("element_type") or ""
        if not room or et in ("traseu", "legenda"):
            continue
        try:
            x, y = float(el["x"]), float(el["y"])
        except (TypeError, ValueError, KeyError):
            continue
        pts.setdefault(room, []).append((x, y))
    return {r: (sum(p[0] for p in v) / len(v), sum(p[1] for p in v) / len(v)) for r, v in pts.items()}


def _orient_axial(px, py, cen):
    """(inward, along) pt. priza (px,py) din centroidul REAL al camerei: inward = AXA DOMINANTA a
    vectorului priza->centroid (cvantizat axial: peretii planului sunt ortogonali -> bara de montaj
    ramane paralela cu peretele; un inward oblic ar desena bara/semicercul strambe). along = perpendicular.
    None daca degenerat (priza ~pe centroid, ex. camera cu 1 element) -> apelantul cade pe fallback."""
    if not cen:
        return None
    dx, dy = float(cen[0]) - px, float(cen[1]) - py
    if abs(dx) < 4.0 and abs(dy) < 4.0:
        return None                                      # degenerat -> fallback (bbox / desen vechi)
    if abs(dx) >= abs(dy):
        inw = (1.0 if dx > 0 else -1.0, 0.0)
    else:
        inw = (0.0, 1.0 if dy > 0 else -1.0)
    return inw, (-inw[1], inw[0])


def _priza_inward(rotation, px, py, cen):
    """O1: orientarea prizei (inward, along) — SURSA = EDITORUL. `rotation` persistat de editor vine
    din SNAP-ul pe peretii REALI (/extract-geometry): auto-generare (plan-editor:663) + drag (:956),
    conventia comuna '0=deschidere SUS (interior sus), pi=jos, +pi/2=dreapta, -pi/2=stanga' (aceeasi
    ca _draw_priza doc) -> inward = (sin r, -cos r), cvantizat axial (peretii-s ortogonali).
    VERIFICAT pe toate 4 cazurile editorului: 0->(0,-1), pi->(0,1), +pi/2->(1,0), -pi/2->(-1,0).
    rotation LIPSA (null — prize vechi/pre-editor) -> fallback CENTROID (_orient_axial, comportamentul
    de azi; conservator — bbox-ul a fost sursa istorica de regresii, ramane doar fallback-ul lui).
    Centroid-ul NU mai decide cand rotation exista -> prizele excentrice pe perete nu se mai intorc."""
    if rotation is not None:
        try:
            r = float(rotation)
            ix, iy = math.sin(r), -math.cos(r)
            if abs(ix) >= abs(iy):
                inw = (1.0 if ix > 0 else -1.0, 0.0)
            else:
                inw = (0.0, 1.0 if iy > 0 else -1.0)
            return inw, (-inw[1], inw[0])
        except (TypeError, ValueError):
            pass                                         # rotation neparsabil -> fallback centroid
    return _orient_axial(px, py, cen)


def _inset_rect(R, m):
    """R micsorat cu marja m pe toate laturile (contur INTERIOR, in camera) -> cablul ruleaza in
    fata peretilor, nu pe ei. Camera prea mica -> R neschimbat (fara inversare)."""
    x0, y0, x1, y1 = R
    if (x1 - x0) <= 2 * m or (y1 - y0) <= 2 * m:
        return R
    return (x0 + m, y0 + m, x1 - m, y1 - m)

def _rooms_to_px(rooms, W, H):
    """rooms (bbox fractii 0-1) -> {nume: (x0,y0,x1,y1) puncte PDF}. Identic cu room_px din compute_cables."""
    out = {}
    if rooms and W and H:
        for r in (rooms or []):
            bb = (r or {}).get("bbox") or {}
            nm = str((r or {}).get("name") or "").strip()
            try:
                x, y, w, h = float(bb["x"]), float(bb["y"]), float(bb["w"]), float(bb["h"])
            except (TypeError, ValueError, KeyError):
                continue
            if nm and w > 0 and h > 0:
                out[nm] = (x * W, y * H, (x + w) * W, (y + h) * H)
    return out

_PRIZA_INSET = 14.0   # marja (pt) a conturului interior pt. rutarea cablului prizelor in fata peretilor

def _perimeter_path(t1, t2, R):
    """Puncte pe LATURILE lui R intre t1 si t2, pe directia MAI SCURTA (prin colturile intermediare)."""
    w, h, P = _rect_perim(R)
    out = [_point_at_t(t1, R)]
    if P > 0:
        corners = [0.0, w, w + h, 2 * w + h]
        fwd = (t2 - t1) % P
        if fwd <= P - fwd:                                  # inainte (t creste)
            seq = sorted((c for c in corners if 1e-6 < (c - t1) % P < fwd - 1e-6), key=lambda c: (c - t1) % P)
        else:                                               # inapoi (t scade)
            back = (t1 - t2) % P
            seq = sorted((c for c in corners if 1e-6 < (t1 - c) % P < back - 1e-6), key=lambda c: (t1 - c) % P)
        out.extend(_point_at_t(c, R) for c in seq)
    out.append(_point_at_t(t2, R))
    return out

def _perim_dist(t1, t2, P):
    if P <= 0:
        return 0.0
    d = (t2 - t1) % P
    return min(d, P - d)


def compute_cables(elements, rooms=None, W=None, H=None, room_centroids=None):
    """PAS 3 (LOGICA pura, FARA desen): asociaza becuri->intrerupatoare (pe room + tip) si
    intrerupatoare->tablou, cu trasee L. PRIZE (regula de aur, ca in realitate): DAISY-CHAIN —
    prizele aceluiasi circuit se leaga IN LANT (capat de bara -> capat de bara), apoi O SINGURA
    iesire din capul lantului spre TRASEUL desenat de inginer (element 'traseu', AUTORITAR) sau
    direct spre tablou. Orientarea barelor = centroidul REAL al elementelor camerei
    (room_centroids; se calculeaza din elements daca lipseste), bbox-ul Vision doar fallback. Reguli:
      - intrerupator_simplu + N becuri -> LANT in serie (switch -> bec nearest -> next nearest ...);
      - dublu/triplu/cap_scara -> fiecare bec -> switch (PARALEL);
      - aplica_senzor -> direct TEG (NU la intrerupator);
      - intrerupator -> TEG, EXCEPTIE room contine 'tehnic' -> TE-CT.
    Skip sigure: intrerupator cu room null (legacy), bec non-senzor fara switch in camera, tablou lipsa.
    Returneaza (cables, stats). cable = {from_type, from_xy, to_type, to_xy, path:[(x,y)..], kind, length, room}."""
    bulbs, switches, panels, prizes, receptors = [], [], {}, [], []
    for el in (elements or []):
        try:
            et = el.get("element_type") or ""
            x = float(el["x"]); y = float(el["y"])
        except (TypeError, ValueError, KeyError):
            continue
        room = el.get("room")
        if et in _BULB_TYPES:
            bulbs.append({"et": et, "x": x, "y": y, "room": room})
        elif et in _SWITCH_TYPES:
            if room:                       # skip intrerupator cu room null (legacy)
                switches.append({"et": et, "x": x, "y": y, "room": room})
        elif et in _PANEL_TYPES:
            panels[et] = (x, y)            # de obicei 1 per tip
        elif et in _PRIZA_TYPES:           # FORTA: prize -> lant pe circuit + coborare la tablou (mai jos)
            prizes.append({"et": et, "x": x, "y": y, "room": room, "cid": el.get("circuit_id"),
                           "rot": el.get("rotation")})   # O1: orientarea barei = rotation persistat (ca desenul)
        elif et in _RECEPTOR_TYPES:        # FORTA: receptor -> linie proprie (dedicat) SAU daisy-chain (grupate, Regula 10)
            receptors.append({"et": et, "x": x, "y": y, "room": room, "label": el.get("label"), "cid": el.get("circuit_id")})
    teg = panels.get("tablou_teg")
    tect = panels.get("tablou_te_ct")

    # FAZA 2a: bbox px per camera (nume -> (x0,y0,x1,y1)) pt. rutarea prizelor pe perimetru.
    # Fara rooms/W/H -> gol -> fallback L direct (backward-compatible cu apelantii care nu paseaza rooms).
    room_px = {}
    if rooms and W and H:
        for r in rooms:
            bb = (r or {}).get("bbox") or {}
            nm = str((r or {}).get("name") or "").strip()
            try:
                x, y, w, h = float(bb["x"]), float(bb["y"]), float(bb["w"]), float(bb["h"])
            except (TypeError, ValueError, KeyError):
                continue
            if nm and w > 0 and h > 0:
                room_px[nm] = (x * W, y * H, (x + w) * W, (y + h) * H)

    cables = []
    stats = {"bec_sw": 0, "senzor_teg": 0, "sw_tablou": 0, "cap_scara": 0,
             "skip_sw_room_null": sum(1 for el in (elements or [])
                                      if (el.get("element_type") in _SWITCH_TYPES) and not el.get("room")),
             "skip_bec_fara_sw": 0, "skip_tablou_lipsa": 0}

    stripes = _extract_stripes(elements)   # FAZA B: TOATE dungile 'traseu'; [] -> fallback L direct
    # ORIENTARE prize: centroidul REAL al elementelor per camera. redraw paseaza centroids din TOATE
    # elementele planului (inainte de filtrarea pe plan_type) -> glyph si cablu identic orientate.
    cen_map = room_centroids if room_centroids is not None else _room_centroids(elements)

    def add(ft, a, tt, b, kind, room, via_stripe=False, count=1, path=None):
        # traseele ...->tablou trec prin dunga CEA MAI APROPIATA de origine (SOL B, faza B); bec->switch local = L direct.
        # count = cate cabluri sunt in manunchiul segmentului (GROSIME pe trepte): prize -> nr. prize/circuit; iluminat -> 1.
        # path dat explicit (FAZA 2a: lant pe perimetru) -> se foloseste ca atare (via_stripe ignorat).
        si = _nearest_stripe_idx(a, stripes) if (via_stripe and path is None) else None
        use = via_stripe and si is not None and path is None
        if path is None:
            path = _stripe_path(a, b, stripes[si]) if use else _cable_l_path(a, b)
        length = sum(math.hypot(path[i + 1][0] - path[i][0], path[i + 1][1] - path[i][1])
                     for i in range(len(path) - 1))
        cables.append({"from_type": ft, "from_xy": a, "to_type": tt, "to_xy": b,
                       "path": path, "kind": kind, "length": round(length, 1), "room": room,
                       "via_stripe": use, "stripe_idx": (si if use else None), "count": count})

    def nearest(p, items):
        return min(items, key=lambda q: math.hypot(q["x"] - p[0], q["y"] - p[1]))

    bulbs_by_room, sw_by_room = {}, {}
    for b in bulbs:
        bulbs_by_room.setdefault(b["room"], []).append(b)
    for s in switches:
        sw_by_room.setdefault(s["room"], []).append(s)

    # BEC -> INTRERUPATOR (pe tip) + SENZOR -> TEG
    for room, rb in bulbs_by_room.items():
        senzori = [b for b in rb if b["et"] == "aplica_senzor"]
        normale = [b for b in rb if b["et"] != "aplica_senzor"]
        for b in senzori:                  # senzor -> TEG (prin dunga daca exista)
            if teg:
                add("aplica_senzor", (b["x"], b["y"]), "tablou_teg", teg, "senzor_teg", room, via_stripe=True)
                stats["senzor_teg"] += 1
            else:
                stats["skip_tablou_lipsa"] += 1
        if not normale:
            continue
        rsw = sw_by_room.get(room, [])
        if not rsw:                        # bec non-senzor fara intrerupator -> skip v1
            stats["skip_bec_fara_sw"] += len(normale)
            continue

        # CAP-SCARA: EXACT 2 intrerupatoare cap_scara in camera -> comanda ACELASI bec: sw1 -> bec -> sw2.
        # (Ambele cap_scara se alimenteaza din tablou -> bucla switch->tablou de mai jos le include automat.)
        cap = [s for s in rsw if s["et"] == "intrerupator_cap_scara"]
        if len(cap) == 2:
            mx = (cap[0]["x"] + cap[1]["x"]) / 2.0
            my = (cap[0]["y"] + cap[1]["y"]) / 2.0
            bec = nearest((mx, my), normale)                                                      # becul comandat
            bxy = (bec["x"], bec["y"])
            add(cap[0]["et"], (cap[0]["x"], cap[0]["y"]), bec["et"], bxy, "cap_scara", room)       # sw1 -> bec
            add(bec["et"], bxy, cap[1]["et"], (cap[1]["x"], cap[1]["y"]), "cap_scara", room)       # bec -> sw2
            stats["cap_scara"] += 1
            normale = [b for b in normale if b is not bec]                                         # bec CONSUMAT
            rsw = [s for s in rsw if s["et"] != "intrerupator_cap_scara"]                          # cap-scara consumate
            if not normale:
                continue
            if not rsw:                    # becuri ramase fara alt switch -> skip
                stats["skip_bec_fara_sw"] += len(normale)
                continue

        cx = sum(b["x"] for b in normale) / len(normale)
        cy = sum(b["y"] for b in normale) / len(normale)
        sw = nearest((cx, cy), rsw)        # intrerupatorul cel mai apropiat de centroidul becurilor
        swxy = (sw["x"], sw["y"])
        # simplu SAU 1/3+ cap_scara ramas -> LANT in serie (fallback simplu); dublu/triplu -> PARALEL
        if sw["et"] in ("intrerupator_simplu", "intrerupator_cap_scara"):
            rem = list(normale); prev_xy = swxy; prev_type = sw["et"]; cur = swxy
            while rem:                     # LANT: switch -> nearest -> next nearest -> ...
                nb = nearest(cur, rem); rem.remove(nb)
                bxy = (nb["x"], nb["y"])
                add(prev_type, prev_xy, nb["et"], bxy, "bec_lant", room)
                stats["bec_sw"] += 1
                prev_xy = bxy; prev_type = nb["et"]; cur = bxy
        else:                              # dublu/triplu -> PARALEL
            for b in normale:
                add(b["et"], (b["x"], b["y"]), sw["et"], swxy, "bec_paralel", room)
                stats["bec_sw"] += 1

    # INTRERUPATOR -> TABLOU (TEG; TE-CT daca room contine 'tehnic')
    for s in switches:
        is_tech = "tehnic" in (s["room"] or "").lower()
        if is_tech and tect:
            add(s["et"], (s["x"], s["y"]), "tablou_te_ct", tect, "sw_tablou", s["room"], via_stripe=True)
            stats["sw_tablou"] += 1
        elif teg:
            add(s["et"], (s["x"], s["y"]), "tablou_teg", teg, "sw_tablou", s["room"], via_stripe=True)
            stats["sw_tablou"] += 1
        else:
            stats["skip_tablou_lipsa"] += 1

    # ── PRIZE -> TABLOU (FORTA): lant pe circuit_id + O coborare la tabloul GENERAL al plansei ──
    # (TEG parter / TES etaj). ADITIV: NU atinge becuri/intrerupatoare/senzori. Realist electric:
    # un circuit = o singura plecare din tablou (capul lantului, priza cea mai apropiata de tablou).
    gen_type = "tablou_teg" if panels.get("tablou_teg") else ("tablou_tes" if panels.get("tablou_tes") else None)
    general_xy = panels.get(gen_type) if gen_type else None
    def _route_chain(prz, room, n, R=None):
        """REGULA DE AUR (Dan): DAISY-CHAIN — prizele circuitului in LANT (capat de bara -> capat de
        bara, nearest-neighbor pornind de la priza cea mai apropiata de IESIRE), apoi O SINGURA iesire
        din capul lantului spre TRASEUL desenat de inginer (autoritar, via_stripe) sau spre tablou.
        NU mai ruteaza pe conturul bbox-ului Vision (mai mic decat camera reala -> cabluri prin mijloc).
        Grosime: segmentul k alimenteaza prizele din aval -> count cumulativ spre iesire (trepte)."""
        cen_room = cen_map.get((room or "").strip())

        def _bar_ends(p):                                  # capetele barei de montaj (orientarea = glyph)
            # O1: ACEEASI sursa ca desenul prizei (_priza_inward: rotation persistat -> centroid fallback)
            # -> bara + cablul lantului raman rotite IMPREUNA cu simbolul.
            o = _priza_inward(p.get("rot"), p["x"], p["y"], cen_room)
            if o is None and R is not None:
                _bp, _inw, _alo = _wall_orient(p["x"], p["y"], R)
                o = (_inw, _alo)
            if o is None:
                return None                                # fara orientare -> lantul intra in centrul prizei
            _inw, alo = o
            return ((p["x"] - alo[0] * _PRIZA_BAR_HALF, p["y"] - alo[1] * _PRIZA_BAR_HALF),
                    (p["x"] + alo[0] * _PRIZA_BAR_HALF, p["y"] + alo[1] * _PRIZA_BAR_HALF))

        def _end_toward(p, t):                             # capatul barei ORIENTAT spre tinta t
            es = _bar_ends(p)
            if not es:
                return (p["x"], p["y"])
            return min(es, key=lambda e: (e[0] - t[0]) ** 2 + (e[1] - t[1]) ** 2)

        # IESIREA intai: traseul desenat de inginer (cel mai apropiat de grup) sau tabloul
        gcen = (sum(p["x"] for p in prz) / len(prz), sum(p["y"] for p in prz) / len(prz))
        if stripes:
            si = _nearest_stripe_idx(gcen, stripes)
            target = _project_point_on_polyline(gcen, stripes[si])[0] if si is not None else general_xy
        else:
            target = general_xy
        # LANT nearest-neighbor de la priza cea mai apropiata de iesire
        rem = list(prz)
        start = min(rem, key=lambda p: (p["x"] - target[0]) ** 2 + (p["y"] - target[1]) ** 2)
        chain = [start]; rem.remove(start)
        cur = (start["x"], start["y"])
        while rem:
            nb = nearest(cur, rem); rem.remove(nb)
            chain.append(nb); cur = (nb["x"], nb["y"])
        for i in range(len(chain) - 1):                    # segmente capat-bara -> capat-bara (L simplu)
            a = _end_toward(chain[i], (chain[i + 1]["x"], chain[i + 1]["y"]))
            b = _end_toward(chain[i + 1], (chain[i]["x"], chain[i]["y"]))
            add(chain[i]["et"], a, chain[i + 1]["et"], b, "priza_lant", room, count=len(chain) - 1 - i)
            stats["priza_lant"] = stats.get("priza_lant", 0) + 1
        # O SINGURA IESIRE: capatul barei capului de lant -> dunga (autoritara) -> tablou
        add(start["et"], _end_toward(start, target), gen_type, general_xy, "priza_tablou", room,
            via_stripe=True, count=n)
        stats["priza_tablou"] = stats.get("priza_tablou", 0) + 1

    if general_xy and prizes:
        by_circuit = {}
        for pz in prizes:
            by_circuit.setdefault(pz.get("cid") or "", []).append(pz)
        for _cid, group in by_circuit.items():
            by_room = {}                                   # rutare PER (circuit, camera): lantul nu sare intre camere
            for pz in group:
                by_room.setdefault(pz.get("room") or "", []).append(pz)
            for _room, prz in by_room.items():
                _n = len(prz)                              # GROSIME: mananchi de N prize -> count=N
                _route_chain(prz, _room, _n, R=room_px.get((_room or "").strip()))

    # RECEPTOARE (FORTA): 2 clase de rutare.
    #  (1) GRUPATE (Regula 10 / H3: VCV+radiatoare cu circuit_id PARTAJAT) -> DAISY-CHAIN pe circuit_id,
    #      ACROSS-ROOM (grupate pe ETAJ, nu pe camera ca prizele), ca prizele dar CENTRU-CENTRU (receptoarele
    #      n-au bara de montaj). O SINGURA iesire spre tabloul general (TEG/TES) pe traseu.
    #  (2) DEDICATE (boiler/cuptor/internet/EV/distribuitor zona) -> O LINIE PROPRIE la tabloul lor (B1, BUG 3b).
    #      Panel dupa CAMERA: camera tehnica SAU echipament clasa 1 (boiler/pdc/pompe/bms/distribuitor PRINCIPAL)
    #      -> TE-CT; altfel (cuptor/AC/internet/EV/distribuitor ZONA) -> general (TEG/TES).
    def _is_grouped_rc(rc):
        return bool(_grouped_heating_kind(rc.get("label")) and rc.get("cid"))
    grouped = [rc for rc in receptors if _is_grouped_rc(rc)]
    dedicated = [rc for rc in receptors if not _is_grouped_rc(rc)]

    def _route_heating_chain(grp, n):
        """Un circuit de incalzire grupat (ACELASI cid, camere diferite): lant nearest-neighbor de la
        elementul cel mai apropiat de IESIRE + O SINGURA iesire spre tabloul general pe traseu. Centru-centru."""
        gcen = (sum(p["x"] for p in grp) / len(grp), sum(p["y"] for p in grp) / len(grp))
        if stripes:
            si = _nearest_stripe_idx(gcen, stripes)
            target = _project_point_on_polyline(gcen, stripes[si])[0] if si is not None else general_xy
        else:
            target = general_xy
        if target is None:
            return
        rem = list(grp)
        start = min(rem, key=lambda p: (p["x"] - target[0]) ** 2 + (p["y"] - target[1]) ** 2)
        chain = [start]; rem.remove(start); cur = (start["x"], start["y"])
        while rem:                                          # lant nearest-neighbor (ca prizele)
            nb = nearest(cur, rem); rem.remove(nb); chain.append(nb); cur = (nb["x"], nb["y"])
        for i in range(len(chain) - 1):                     # segmente CENTRU-CENTRU (fara bara de montaj)
            add(chain[i]["et"], (chain[i]["x"], chain[i]["y"]), chain[i + 1]["et"],
                (chain[i + 1]["x"], chain[i + 1]["y"]), "incalzire_lant", None, count=len(chain) - 1 - i)
            stats["incalzire_lant"] = stats.get("incalzire_lant", 0) + 1
        add(start["et"], (start["x"], start["y"]), gen_type, general_xy, "incalzire_tablou", None,
            via_stripe=True, count=n)                        # O IESIRE: capul lantului -> traseu -> tablou general
        stats["incalzire_tablou"] = stats.get("incalzire_tablou", 0) + 1

    if grouped and general_xy:
        by_cid = {}
        for rc in grouped:
            by_cid.setdefault(rc["cid"], []).append(rc)     # lant pe circuit_id (NU pe camera -> across-floor)
        for _cid, grp in by_cid.items():
            _route_heating_chain(grp, len(grp))

    if dedicated and (general_xy or tect):
        tech_l = (tech_room_from_elements(elements) or "").strip().lower()
        # O3: cablurile ECHIPAMENTELOR DE INCALZIRE din CAMERA TEHNICA merg PE LANGA PERETE (nu prin
        # mijloc): perpendicular la peretele apropiat -> pe margine (prin colturi) -> TE-CT. Refoloseste
        # EXACT geometria prizelor din Faza 2a (_project_to_rect + _perimeter_path + _inset_rect), cu
        # inset CONCENTRIC per echipament (m = 4 + idx*2.5) -> paralele pe acelasi perete, nu suprapuse.
        # DOAR subsetul: clasa 1 + tinta TE-CT + echipamentul si TE-CT in bbox-ul camerei tehnice
        # (toleranta 25pt — bbox-ul Vision poate fi mai mic decat camera reala). Restul: ca inainte.
        _tech_R = None
        if tech_l and tect is not None:
            for _nm, _R in room_px.items():
                if _nm.strip().lower() == tech_l:
                    _tech_R = _R
                    break

        def _in_tech(px, py, tol=25.0):
            return (_tech_R is not None
                    and _tech_R[0] - tol <= px <= _tech_R[2] + tol
                    and _tech_R[1] - tol <= py <= _tech_R[3] + tol)

        def _on_wall_route(rc):
            return (_tech_R is not None and _is_heating_receptor(rc.get("label"))
                    and _in_tech(rc["x"], rc["y"]) and _in_tech(tect[0], tect[1]))

        heat_wall = sorted((rc for rc in dedicated if _on_wall_route(rc)),
                           key=lambda rc: (rc["y"], rc["x"]))          # idx determinist (y,x)
        _wall_ids = {id(rc) for rc in heat_wall}
        for _idx, rc in enumerate(heat_wall):
            _Ri = _inset_rect(_tech_R, 4.0 + _idx * 2.5)               # contur concentric per echipament
            _bp1, _t1 = _project_to_rect(rc["x"], rc["y"], _Ri)        # perpendicular pe peretele apropiat
            _bp2, _t2 = _project_to_rect(tect[0], tect[1], _Ri)        # in dreptul TE-CT
            _wpath = [(rc["x"], rc["y"])] + _perimeter_path(_t1, _t2, _Ri) + [(tect[0], tect[1])]
            add(rc["et"], (rc["x"], rc["y"]), "tablou_te_ct", tect, "receptor_dedicat", rc.get("room"),
                count=1, path=_wpath)                                  # ruta explicita pe margine
            stats["receptor_dedicat"] = stats.get("receptor_dedicat", 0) + 1

        for rc in dedicated:
            if id(rc) in _wall_ids:
                continue                                   # rutat pe perete mai sus
            rroom = (rc.get("room") or "").strip().lower()
            to_tect = (tect is not None) and (_is_heating_receptor(rc.get("label"))
                                              or (bool(tech_l) and rroom == tech_l))
            tgt_xy = tect if to_tect else general_xy
            tgt_ty = "tablou_te_ct" if to_tect else gen_type
            if tgt_xy is None:
                continue
            add(rc["et"], (rc["x"], rc["y"]), tgt_ty, tgt_xy, "receptor_dedicat", rc.get("room"),
                via_stripe=True, count=1)                 # linie proprie (nu daisy-chain), grosime proprie
            stats["receptor_dedicat"] = stats.get("receptor_dedicat", 0) + 1

    # FV-P3: lantul sistemului fotovoltaic T.CC -> INV -> T.CA -> TEG (fluxul electric real:
    # DC panouri -> tablou CC -> invertor -> tablou CA -> general). Segmente L directe intre
    # tablourile PREZENTE; CONSERVATOR la lipsuri: un segment se deseneaza doar daca AMBELE
    # capete sunt plasate (fara punti peste tabloul lipsa — topologia nu se inventeaza).
    # kind=fv_link: EXCLUS din BOM (whitelist-ul _ILUM_KINDS/_PRIZA_KINDS nu-l contine, ca EV)
    # si desenat DOAR pe planul de forta (gate in redraw — tablourile au plan_type="ambele").
    _fv_chain = ("tablou_tcc", "tablou_inv", "tablou_tca", "tablou_teg")
    for _fa, _fb in zip(_fv_chain, _fv_chain[1:]):
        if panels.get(_fa) and panels.get(_fb):
            add(_fa, panels[_fa], _fb, panels[_fb], "fv_link", None, count=1)
            stats["fv_link"] = stats.get("fv_link", 0) + 1

    # MANUNCHI PER DUNGA (BUG 4): cablurile care converg pe ACEEASI dunga se deseneaza PARALEL (offset
    # lateral simetric, alocare geografica dupa latura de intrare), NU cumulate intr-o linie groasa.
    # Non-stripe (lant intra-camera, iluminat) raman neatinse. Capacitate 5 sloturi + surplus cumulat.
    if stripes:
        by_stripe, rest = {}, []
        for c in cables:
            if c.get("via_stripe") and c.get("stripe_idx") is not None:
                by_stripe.setdefault(c["stripe_idx"], []).append(c)
            else:
                rest.append(c)
        new_stripe = []
        for si, grp in by_stripe.items():
            new_stripe.extend(_stripe_parallel(grp, stripes[si]))
        cables = rest + new_stripe
        stats["bundle"] = sum(len(g) for g in by_stripe.values())

    return cables, stats


# ── C3a: asociere PRIZA -> CAMERA (point-in-bbox Vision). PUR: doar calcul, fara circuit_id/desen. ──
def _room_of_point(px, py, rooms, W, H):
    """Camera al carei bbox×(W,H) CONTINE (px,py) — refoloseste math-ul in_room_bbox.
    OVERLAP (mai multe bbox-uri contin punctul) -> cea mai MICA bbox (w*h minim = cea mai specifica).
    FALLBACK (nicio bbox) -> cea mai apropiata camera (min dist la centrul bbox). rooms gol -> None."""
    if not rooms:
        return None
    containing = []   # (aria_bbox_frac, name)
    nearest = None    # (dist, name)
    for r in rooms:
        bb = (r or {}).get("bbox") or {}
        try:
            x = float(bb["x"]); y = float(bb["y"]); w = float(bb["w"]); h = float(bb["h"])
        except (TypeError, ValueError, KeyError):
            continue
        name = str((r or {}).get("name") or "")
        if x * W <= px <= (x + w) * W and y * H <= py <= (y + h) * H:
            containing.append((w * h, name))
        cx, cy = (x + w / 2.0) * W, (y + h / 2.0) * H
        d = math.hypot(px - cx, py - cy)
        if nearest is None or d < nearest[0]:
            nearest = (d, name)
    if containing:
        return min(containing, key=lambda c: c[0])[1]   # cea mai mica bbox conținatoare
    return nearest[1] if nearest else None              # fallback: cea mai apropiata camera


def assign_rooms_to_prizas(elements, rooms, W, H):
    """Pentru fiecare PRIZA/RECEPTOR cu room null/gol -> seteaza el['room'] = camera ei (in-memory, pt. C3b).
    NIVEL 2: include si receptoarele (alimentare_receptor + receptor_internet) -> primesc room geometric
    (point-in-bbox, ca prizele) => enrich poate detecta receptoarele din camera tehnica -> TE-CT.
    Cele care au deja room raman neatinse. PUR pt. restul elementelor. C3a: NU scrie circuit_id,
    NU persista, NU deseneaza. Intoarce lista [(x, y, room)] pt. logare/test."""
    out = []
    for el in (elements or []):
        _et = (el or {}).get("element_type") or ""
        if _et not in _PRIZA_TYPES and _et not in _RECEPTOR_TYPES:
            continue
        try:
            px = float(el["x"]); py = float(el["y"])
        except (TypeError, ValueError, KeyError):
            continue
        if (el.get("room") or ""):
            out.append((px, py, el.get("room")))   # are deja camera -> pastreaza
            continue
        room = _room_of_point(px, py, rooms, W, H)
        el["room"] = room                          # in-memory (pt. C3b)
        out.append((px, py, room))
    return out


# ── C3b: numerotare circuite (PUR). Reguli Dan: iluminat n=max(ceil(W/1000),ceil(becuri/12)); ──
# prize/camera: bucatarie=2, else ceil(nr/5). C1..Cn iluminat -> C{n+1}+ prize. Determinist. NU scrie pe elemente.
_BULB_DEFAULT_W = 25   # bec fara power_w -> 25W (valoarea reala precompletata)


_TECH_ROOM_TOL_PT = 60.0   # decizia Dan (Faza 1 TE-CT): tabloul la <=60pt (~1.2m la 1:50) de bbox
_TECH_SIGNALS = ("tehnic", "technical", "spatiu_tehnic")   # nume RO / function / room_type (Vision)


def _room_is_tech(r):
    """Semnalul de camera TEHNICA al unei camere Vision: name / function / room_type."""
    for k in ("name", "function", "room_type"):
        if any(s in str((r or {}).get(k) or "").strip().lower() for s in _TECH_SIGNALS):
            return True
    return False


def _detect_tech_room(elements, rooms, W, H):
    """Camera TE-CT = POZITIA tabloului_te_ct, DOAR printre camerele cu SEMNAL TEHNIC (name/
    function/room_type Vision — sinteza regulilor Dan #1+#2): tabloul IN bbox-ul unei camere
    tehnice (overlap -> cea mai mica), altfel camera tehnica cu bbox-ul la <=60pt (daca >=2
    tehnice in prag -> ambiguu -> None). Camerele NORMALE nu pot ajunge pe TE-CT indiferent
    de apropiere (regula #1) — MASURAT pe cazurile reale: tabloul era la 2pt de bbox-ul
    'Dormitor 1' (b22) si la 56pt de 'Dressing' (c7890), dar la 100-170pt de 'Spatiu tehnic'
    (bbox-urile Vision sunt mici/nealiniate) -> orice regula pur-geometrica captura camere
    normale. Fara camera tehnica in prag -> None = NIMIC din plan pe TE-CT (sigur; incalzirea
    din formular ramane pe TE-CT). NU foloseste fallback-ul nearest-center al _room_of_point
    (ala alegea la RULETA — bug-ul initial); _room_of_point ramane NEATINS pentru prize."""
    tab = next((el for el in (elements or [])
                if ((el or {}).get("element_type") or "") == "tablou_te_ct"), None)
    if tab is None or not rooms or not W or not H:
        return None
    try:
        px, py = float(tab["x"]), float(tab["y"])
    except (TypeError, ValueError, KeyError):
        return None
    containing = []                                        # (arie_bbox, nume) — doar camere TEHNICE
    near = []                                              # (dist_la_BBOX, nume) in prag — doar TEHNICE
    for r in rooms:
        if not _room_is_tech(r):
            continue
        bb = (r or {}).get("bbox") or {}
        try:
            x, y, w, h = float(bb["x"]), float(bb["y"]), float(bb["w"]), float(bb["h"])
        except (TypeError, ValueError, KeyError):
            continue
        name = str((r or {}).get("name") or "").strip()
        if not name:
            continue
        x0, y0, x1, y1 = x * W, y * H, (x + w) * W, (y + h) * H
        if x0 <= px <= x1 and y0 <= py <= y1:
            containing.append((w * h, name))
        else:
            d = math.hypot(max(x0 - px, 0.0, px - x1), max(y0 - py, 0.0, py - y1))
            if d <= _TECH_ROOM_TOL_PT:
                near.append((d, name))
    if containing:
        return min(containing, key=lambda c: c[0])[1]
    if len(near) == 1:
        return near[0][1]
    return None                                            # 0 in prag (departe) sau >=2 (ambiguu)


def tech_room_from_elements(plan_elements):
    """SURSA UNICA plan<->enrich (Faza 1 TE-CT): camera tehnica = room-ul PERSISTAT al elementului
    tablou_te_ct (scris de assign_circuits cu detectia geometrica stricta pe POZITIA tabloului).
    None daca tabloul lipseste sau room-ul nu e setat (proiect vechi/neregenerat -> apelantul
    poate cadea pe fallback-ul legacy dupa nume)."""
    for el in (plan_elements or []):
        if ((el or {}).get("element_type") or "") == "tablou_te_ct":
            return ((el or {}).get("room") or "").strip() or None
    return None


def _detect_general_panel(elements):
    """Tabloul GENERAL al planului (per-etaj). 'TES' daca planul contine un tablou_tes (etaj) ->
    circuitele generale primesc sufix -TES (C1-TES, C2-TES...), numerotare PROPRIE/locala (analog -TECT).
    Altfel 'TEG' (parter/implicit) -> FARA sufix (C1, C2...) = backward-compat total.
    TE-CT ramane subset separat (camera tehnica), neafectat de asta."""
    for el in (elements or []):
        if ((el or {}).get("element_type") or "") == "tablou_tes":
            return "TES"
    return "TEG"


def _prize_circuit_group(room_name):
    """R3: re-deriva circuitGroup (OGLINDA R1 prizeRuleForRoom.circuitGroup) din numele camerei, in Python.
    Doar BAIE/HOL/KITCHEN = grupuri COMUNE/speciale; restul = numele camerei (circuit propriu).
    ORDINE IDENTICA cu R1 (specific->generic): terasa/tehnic/depozit/camara/dressing/living -> PROPRIU
    (chiar daca ar contine alt substring), apoi baie/bucatar/hol -> grup comun. Coerent cu plasarea (R2)."""
    n = (room_name or "").strip().lower()
    own = (room_name or "").strip() or "(fara camera)"
    if ("teras" in n or "spatiu tehnic" in n or "tehnic" in n
            or "depozit" in n or "camara" in n or "dressing" in n
            or "living" in n or "camera de zi" in n or " zi" in n):
        return own                                                   # camere cu nr. fix -> circuit propriu
    if "baie" in n:
        return "BAIE"                                                # TOATE baile -> 1 circuit comun
    if "bucatar" in n:
        return "KITCHEN"                                             # bucatarie -> 2 circuite (3+3)
    if "hol" in n:
        return "HOL"                                                 # TOATE holurile -> 1 circuit comun
    return own                                                       # dormitor/birou/spalator/garaj/default -> propriu


def compute_circuits(elements, tech_room=None, general="TEG"):
    """Numara/grupeaza circuitele dupa regulile Dan. Daca tech_room (camera cu tablou_te_ct) e dat ->
    elementele din ea = grup -TECT (becuri -> C1-TECT iluminat; prize/alimentari -> C2-TECT, C3-TECT...
    cate 1/element, decuplat de schema). Restul casei = tabloul GENERAL (becuri count -> n_iluminat;
    prize C{n+1}+), EXCLUZAND camera tehnica. `general`='TEG' (parter) -> id-uri BARE (C1, C2...);
    'TES' (etaj) -> sufix -TES (C1-TES, C2-TES...), numerotare PROPRIE/locala (analog -TECT).
    PUR: nu modifica `elements`. Determinist (camere pe nume, elemente pe (y,x)).
    Intoarce {n_iluminat, tech_room, total_bulb_w, nr_becuri, n_circuits,
              circuits:[{id,kind,room,indices}], element_circuit:{index -> 'Cx'}} (becuri tech + TOATE prizele)."""
    elements = elements or []
    tech_l = (tech_room or "").strip().lower()
    gsuf = "" if (general or "TEG") == "TEG" else "-%s" % general   # tabloul general etaj -> sufix -TES

    def is_tech(i):
        return bool(tech_l) and ((elements[i].get("room") or "").strip().lower() == tech_l)

    circuits = []
    element_circuit = {}

    # ── TE-CT (camera tehnica): becuri -> C1-TECT (1 circuit); prize/alimentari -> C2-TECT, C3-TECT... ──
    if tech_l:
        tech_bulbs = [i for i, el in enumerate(elements)
                      if ((el or {}).get("element_type") or "") in _BULB_TYPES and is_tech(i)]
        if tech_bulbs:
            circuits.append({"id": "C1-TECT", "kind": "iluminat", "room": tech_room, "indices": tech_bulbs})
            for i in tech_bulbs:
                element_circuit[i] = "C1-TECT"
        tech_prizas = sorted([i for i, el in enumerate(elements)
                              if ((el or {}).get("element_type") or "") in _PRIZA_TYPES and is_tech(i)],
                             key=lambda i: (float(elements[i].get("y") or 0), float(elements[i].get("x") or 0)))
        nt = 2
        for i in tech_prizas:                                             # cate 1 circuit/element (decuplat)
            cid = "C%d-TECT" % nt
            circuits.append({"id": cid, "kind": "priza", "room": tech_room, "indices": [i]})
            element_circuit[i] = cid
            nt += 1

    # ── TEG: n = max(ceil(total_W/1000), ceil(nr_becuri/12)) — becuri NON-tech ──
    bulb_idx = [i for i, el in enumerate(elements)
                if ((el or {}).get("element_type") or "") in _BULB_TYPES and not is_tech(i)]
    nr_becuri = len(bulb_idx)

    def _bw(i):                                                  # putere bec (null/nenumeric -> default 25W)
        pw = elements[i].get("power_w")
        try:
            return int(pw) if pw not in (None, "") else _BULB_DEFAULT_W
        except (TypeError, ValueError):
            return _BULB_DEFAULT_W

    total_W = sum(_bw(i) for i in bulb_idx)
    n_iluminat = max(math.ceil(total_W / 1000.0), math.ceil(nr_becuri / 12.0), 1) if nr_becuri else 0
    ilum_circuits = []
    for i in range(n_iluminat):
        c = {"id": "C%d%s" % (i + 1, gsuf), "kind": "iluminat", "room": None, "indices": [], "_w": 0}
        circuits.append(c); ilum_circuits.append(c)

    # LPT (egalizare PUTERE + NUMAR): becuri DESC pe putere (tiebreak (y,x) = determinism) -> fiecare la
    # circuitul cu PUTEREA curenta minima (tiebreak: count minim, apoi index circuit). Scrie element_circuit
    # -> assign_circuits le pune circuit_id automat. Becurile TECH (C1-TECT) NU sunt aici (excluse de is_tech).
    if n_iluminat:
        order = sorted(bulb_idx, key=lambda i: (-_bw(i),
                                                float(elements[i].get("y") or 0),
                                                float(elements[i].get("x") or 0)))
        for i in order:
            k = min(range(n_iluminat),
                    key=lambda j: (ilum_circuits[j]["_w"], len(ilum_circuits[j]["indices"]), j))
            ilum_circuits[k]["indices"].append(i)
            ilum_circuits[k]["_w"] += _bw(i)
            element_circuit[i] = ilum_circuits[k]["id"]
    for c in ilum_circuits:
        c.pop("_w", None)                                        # curata cheia temporara (LPT)

    # ── PRIZE TEG pe circuitGroup (R3, din el['room'] -> _prize_circuit_group), EXCLUZAND camera tehnica ──
    # BAIE (toate baile) = 1 circuit comun; HOL (toate holurile) = 1 comun; KITCHEN = 2 circuite (3+3);
    # restul = 1 circuit/camera (INLOCUIESTE ceil/5 — reguli Dan: nr. fix/camera, nu pe nr. prize).
    by_group = {}
    for i, el in enumerate(elements):
        if ((el or {}).get("element_type") or "") in _PRIZA_TYPES and not is_tech(i):
            by_group.setdefault(_prize_circuit_group(el.get("room")), []).append(i)

    next_c = n_iluminat + 1
    for group in sorted(by_group.keys()):                                 # ordine grupuri FIXA
        idxs = sorted(by_group[group],                                    # ordine prize FIXA (y,x)
                      key=lambda i: (float(elements[i].get("y") or 0), float(elements[i].get("x") or 0)))
        k = 2 if group == "KITCHEN" else 1                               # KITCHEN -> 2 circ (3+3); BAIE/HOL/camera -> 1
        per = math.ceil(len(idxs) / k) if k else len(idxs)
        for ci in range(k):
            chunk = idxs[ci * per:(ci + 1) * per]
            if not chunk:                                                 # k=2 dar <2 prize -> fara circuit gol
                continue
            cid = "C%d%s" % (next_c, gsuf)
            circuits.append({"id": cid, "kind": "priza", "room": group, "indices": chunk})
            for j in chunk:
                element_circuit[j] = cid
            next_c += 1

    # ── REGULA 10: INCALZIRE ELECTRICA (VCV + radiatoare) grupate pe (etaj, faza), plafon 2kW, FFD pur ──
    # SURSA UNICA: gruparea (cine-cu-cine + circuit_id) traieste AICI, ca la prize -> planul si documentele
    # (enrich) folosesc ACELASI circuit_id. Merg pe general TEG/TES (NU tech/TE-CT). Distribuitorul de ZONA
    # NU e aici (dedicat 1:1, tratat in enrich). Puterea = reala (power_w editat, fallback default per tip).
    _HEATING_CEILING_W = 2000
    hbucket = {}
    for i, el in enumerate(elements):
        if _grouped_heating_kind((el or {}).get("label")) is None:
            continue
        fl = str((el or {}).get("floor") or "parter").strip().lower()          # split pe (etaj, faza)
        tri = str((el or {}).get("phase") or "mono").strip().lower() in ("tri", "trifazat", "3")
        hbucket.setdefault((fl, tri), []).append(i)

    def _hw(i):                                                    # putere reala (fallback default per tip)
        el = elements[i]
        pw = el.get("power_w")
        try:
            v = int(pw) if pw not in (None, "") else None
        except (TypeError, ValueError):
            v = None
        return v if v is not None else _GROUPED_HEATING_DEFAULT_W.get(_grouped_heating_kind(el.get("label")), 0)

    for key in sorted(hbucket.keys()):                             # ordine grupuri FIXA (etaj, faza)
        tri = key[1]
        order = sorted(hbucket[key], key=lambda i: (-_hw(i),       # FFD: DESC pe putere (determinist)
                                                    float(elements[i].get("y") or 0),
                                                    float(elements[i].get("x") or 0)))
        bins = []                                                  # [{indices, w}] — plafon 2kW
        for i in order:
            w = _hw(i)
            placed = False
            for b in bins:                                         # FFD pur: primul bin care il suporta
                if b["w"] + w <= _HEATING_CEILING_W:
                    b["indices"].append(i); b["w"] += w; placed = True; break
            if not placed:                                         # niciun bin (sau w > plafon) -> bin propriu
                bins.append({"indices": [i], "w": w})
        for b in bins:
            cid = "C%d%s" % (next_c, gsuf)
            circuits.append({"id": cid, "kind": "incalzire", "room": None,
                             "indices": b["indices"], "power_w": b["w"], "tri": tri})
            for j in b["indices"]:
                element_circuit[j] = cid                           # circuit_id PARTAJAT (pt. daisy-chain H3)
            next_c += 1

    return {"n_iluminat": n_iluminat, "tech_room": tech_room, "total_bulb_w": total_W,
            "nr_becuri": nr_becuri, "n_circuits": len(circuits),
            "circuits": circuits, "element_circuit": element_circuit}


def assign_circuits(elements, rooms, W, H):
    """C3c+T1 orchestrator: asociaza prize->camera (C3a) + detecteaza camera TE-CT (din tablou_te_ct) +
    numeroteaza circuite (T1: tech -> -TECT, rest -> TEG) + scrie circuit_id IN-MEMORY (pt. C4/desen).
    Becuri tech -> C1-TECT; prize/alimentari tech -> C2-TECT+; prize rest -> TEG C{n+1}+; becuri rest -> None.
    Determinist/idempotent. Intoarce {n_iluminat, tech_room, n_circuits, circuits,
    updates:[{id, room, circuit_id, changed}]} -> caller-ul persista in DB DOAR `changed`."""
    elements = elements or []
    # snapshot vechi (room+circuit_id) INAINTE de mutatie -> persistare doar daca s-a schimbat.
    # + tabloul TE-CT: room-ul lui (camera tehnica detectata) se persista si el (sursa UNICA
    # pt. enrich — tech_room_from_elements).
    old = {}
    for el in elements:
        et = (el or {}).get("element_type") or ""
        if (et in _PRIZA_TYPES or et in _BULB_TYPES or et in _RECEPTOR_TYPES
                or et == "tablou_te_ct") and el.get("id"):
            old[el["id"]] = (el.get("room"), el.get("circuit_id"))

    assign_rooms_to_prizas(elements, rooms, W, H)          # seteaza el['room'] pe prize (point-in-bbox)
    tech_room = _detect_tech_room(elements, rooms, W, H)   # POZITIA tabloului (strict+60pt unic; None=sigur)
    for el in elements:                                    # persista camera tehnica PE TABLOU (sursa unica)
        if ((el or {}).get("element_type") or "") == "tablou_te_ct":
            el["room"] = tech_room
    general = _detect_general_panel(elements)              # 'TES' daca planul are tablou_tes (etaj) -> sufix -TES; altfel 'TEG'
    info = compute_circuits(elements, tech_room=tech_room, general=general)
    ec = info["element_circuit"]                           # index -> circuit_id (becuri tech + TOATE prizele)

    updates = []
    for idx, el in enumerate(elements):
        et = (el or {}).get("element_type") or ""
        if et == "tablou_te_ct":
            # persista DOAR room-ul (camera tehnica = sursa unica pt. enrich); fara circuit_id
            pid = el.get("id")
            if pid and old.get(pid) != (el.get("room"), el.get("circuit_id")):
                updates.append({"id": pid, "room": el.get("room"),
                                "circuit_id": el.get("circuit_id"), "changed": True})
            continue
        if et not in _PRIZA_TYPES and et not in _BULB_TYPES and et not in _RECEPTOR_TYPES:
            continue
        cid = ec.get(idx)                                  # None pt. becuri non-tech + receptoare DEDICATE; grupatele (VCV/radiator, Regula 10) au cid PARTAJAT
        el["circuit_id"] = cid                             # IN-MEMORY (pt. C4). Receptoare dedicate: cid=None; grupate: cid comun (pt. daisy-chain)
        pid = el.get("id")
        if pid:
            new = (el.get("room"), cid)
            if old.get(pid) != new:
                updates.append({"id": pid, "room": el.get("room"), "circuit_id": cid, "changed": True})
    return {"n_iluminat": info["n_iluminat"], "tech_room": tech_room,
            "n_circuits": info["n_circuits"], "circuits": info["circuits"], "updates": updates}


def _apply_cartus_suffix(doc, page, suffix):
    """Titlul plansei PER TIP in cartusul Zynapse ("... DE ILUMINAT" / "... DE FORTA"):
    citeste celula titlului din metadata PDF (scrisa de cartus_swap la swap) si rescrie
    DOAR acea celula cu titlul de baza + sufix. PDF fara metadata (vechi / cartus nedetectat)
    -> no-op, planul ramane neatins. Defensiv: orice eroare -> no-op."""
    try:
        kw = (doc.metadata or {}).get("keywords") or ""
        m = re.search(r"zy_cartus_title=([0-9.]+),([0-9.]+),([0-9.]+),([0-9.]+)\|(.+)", kw)
        if not m:
            return False
        x0, y0, x1, y1 = (float(m.group(i)) for i in range(1, 5))
        base = m.group(5).strip()
        full = "{} {}".format(base, suffix).strip()
        from cartus_swap import _ctext, _wrap2   # acelasi randare ca la desenul cartusului
        page.draw_rect(fitz.Rect(x0 + 1.0, y0 + 1.0, x1 - 1.0, y1 - 1.0),
                       color=(1, 1, 1), fill=(1, 1, 1))       # goleste DOAR interiorul celulei
        rh = (y1 - y0) / 2.0
        big = max(5.5, min(9.0, rh * 0.78))
        lines = _wrap2(full, "hebo", big, (x1 - x0) - 6.0)[:2]
        if len(lines) == 1:
            _ctext(page, x0, x1, y0 + rh * 1.30, lines[0], big, bold=True)
        else:
            for i, ln in enumerate(lines):
                _ctext(page, x0, x1, y0 + rh * (0.85 + i * 0.95), ln, big, bold=True)
        return True
    except Exception:
        return False


def _apply_cartus_title(doc, page, full_title):
    """PAS 2 (numerotare): scrie TITLUL COMPLET (din autoritatea compute_plansa_numbering) in celula
    titlului — acelasi tipar ca _apply_cartus_suffix, dar cu textul integral in loc de base+sufix.
    PDF fara metadata -> no-op (False); apelantul cade pe sufixul vechi. Defensiv."""
    try:
        kw = (doc.metadata or {}).get("keywords") or ""
        m = re.search(r"zy_cartus_title=([0-9.]+),([0-9.]+),([0-9.]+),([0-9.]+)\|", kw)
        if not m or not full_title:
            return False
        x0, y0, x1, y1 = (float(m.group(i)) for i in range(1, 5))
        from cartus_swap import _ctext, _wrap2
        page.draw_rect(fitz.Rect(x0 + 1.0, y0 + 1.0, x1 - 1.0, y1 - 1.0),
                       color=(1, 1, 1), fill=(1, 1, 1))
        rh = (y1 - y0) / 2.0
        big = max(5.5, min(9.0, rh * 0.78))
        lines = _wrap2(full_title, "hebo", big, (x1 - x0) - 6.0)[:2]
        if len(lines) == 1:
            _ctext(page, x0, x1, y0 + rh * 1.30, lines[0], big, bold=True)
        else:
            for i, ln in enumerate(lines):
                _ctext(page, x0, x1, y0 + rh * (0.85 + i * 0.95), ln, big, bold=True)
        return True
    except Exception:
        return False


def _stamp_plansa_nr(doc, page, plansa_nr):
    """PAS 2 (numerotare): scrie numarul FINAL (IE.N, din autoritate) in casuta "Plansa nr." a
    cartusului — coord din metadata zy_cartus_plansa (scrisa de cartus_swap la swap, post-80dee3a).
    Acelasi tipar ca cartus_swap.restamp_plansa. PDF vechi fara metadata -> no-op gratios (False):
    numarul mostenit al planului de baza ramane, nimic nu crapa. Defensiv."""
    try:
        kw = (doc.metadata or {}).get("keywords") or ""
        m = re.search(r"zy_cartus_plansa=([0-9.]+),([0-9.]+),([0-9.]+),([0-9.]+)", kw)
        if not m or not plansa_nr:
            return False
        x0, y0, x1, y1 = (float(m.group(i)) for i in range(1, 5))
        from cartus_swap import _ctext
        rh = (y1 - y0) / 2.0
        lab = max(4.0, min(6.0, rh * 0.52))
        val = max(5.0, min(8.5, rh * 0.72))
        page.draw_rect(fitz.Rect(x0 + 1.0, y0 + 1.0, x1 - 1.0, y1 - 1.0),
                       color=(1, 1, 1), fill=(1, 1, 1))
        _ctext(page, x0, x1, y0 + rh * 0.80, "Plansa nr.", lab)
        _ctext(page, x0, x1, y0 + rh * 1.78, plansa_nr, val, bold=True)
        return True
    except Exception:
        return False


def redraw_from_plan_elements(base_pdf_base64: str, elements: list, draw_plan_type: str = "iluminat", feeds: list = None, rooms: list = None, plansa_nr: str = None, plansa_titlu: str = None, circuits: list = None, cross_floor: dict = None) -> dict:
    """SUB-PAS 1a 'Obtine plan': redeseneaza elementele EDITATE pe BAZA CURATA (planuri[].pdf_base64).
    F4: deseneaza DOAR elementele cu plan_type in (draw_plan_type, 'ambele') -> iluminat: becuri/intrer./
    tablouri/dunga/legenda; forta: prize/alimentari + tablouri (mostenite) + dunga forta, FARA becuri.
    circuit_id e calculat IN AFARA (assign_circuits pe TOATE elementele -> numerotare cross-plan corecta).
    Coordonate = PUNCTE PDF. Defensiv: element invalid -> sarit; orice eroare -> success:false, fara crash."""
    doc = None
    try:
        raw = base_pdf_base64.split(",", 1)[1] if "," in base_pdf_base64 else base_pdf_base64
        pdf_bytes = base64.b64decode(raw)
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[0]
        # Titlul + numarul cartusului. PAS 2 (numerotare): daca /regenerate-plan a determinat intrarea
        # din AUTORITATE (plansa_nr/plansa_titlu), scrie titlul COMPLET + numarul FINAL (IE.N) —
        # INAINTE de tobytes, deci PDF-ul livrat le contine. Fara ele / PDF vechi fara metadata ->
        # comportamentul vechi (base + sufix; numarul mostenit al planului de baza). Defensiv.
        _stamped_titlu = _apply_cartus_title(doc, page, plansa_titlu) if plansa_titlu else False
        if not _stamped_titlu:
            _apply_cartus_suffix(doc, page, "DE ILUMINAT" if draw_plan_type == "iluminat" else "DE FORTA")
        _stamped_nr = _stamp_plansa_nr(doc, page, plansa_nr) if plansa_nr else False
        # ORIENTAREA prizelor: centroidul REAL al elementelor per camera, din TOATE elementele
        # planului (INAINTE de filtrarea pe plan_type: becurile/intrerupatoarele de pe iluminat
        # fac centroidul robust si pe planul de forta). Acelasi cen_map -> glyph + cablu identice.
        _cen_map = _room_centroids(elements)
        # F4: filtreaza ce DESENAM pe plan_type (numerotarea s-a facut deja pe toate elementele).
        # iluminat -> iluminat+ambele(tablouri); forta -> forta+ambele. Cablurile/legenda urmeaza subsetul.
        elements = [el for el in (elements or [])
                    if ((el or {}).get("plan_type") or "iluminat") in (draw_plan_type, "ambele")]
        n_bulb = n_sw = n_panel = n_priza = n_skip = n_ground = n_receptor = 0
        # PAS 3b: CABLURI dedesubt (compute_cables -> _draw_cable), INAINTE de simboluri.
        # Defensiv: orice eroare la cabluri NU strica regenerarea (becurile/etc. se deseneaza oricum).
        n_cable = 0
        _cables = []   # traseele cablurilor (path = puncte PDF) -> expuse in raspuns pt. overlay-ul editorului
        try:
            # FAZA 2a: rooms(bbox) + W,H din pagina -> prizele se ruteaza pe PERIMETRU (nu prin interior).
            _cables, _cstats = compute_cables(elements, rooms=rooms, W=page.rect.width, H=page.rect.height,
                                              room_centroids=_cen_map)
            for _c in _cables:
                # C2: forța (prize + receptoare -> tablou) = ALBASTRU (_PRIZA_COLOR); iluminat = roșu (default).
                _kind = _c.get("kind") or ""
                # FV-P3: lantul FV DOAR pe planul de forta (tablourile au plan_type="ambele" ->
                # compute_cables il genereaza si la iluminat; acolo il sarim).
                if _kind == "fv_link" and draw_plan_type != "forta":
                    continue
                # GROSIME pe trepte: width din count-ul manunchiului (1/2-3/4+); iluminat count=1 -> neschimbat.
                _draw_cable(page, _c.get("path"),
                            color=_FV_LINK_COLOR if _kind == "fv_link"
                            else _PRIZA_COLOR if (_kind.startswith("priza") or _kind.startswith("receptor") or _kind.startswith("incalzire")) else None,
                            width=_cable_width_for(_c.get("count", 1)))
                n_cable += 1
        except Exception:
            n_cable = 0
        # Priza de pamant: pozitia TEG (o singura data/pagina) pt. legatura perpendiculara TEG->contur.
        _teg = next((e for e in (elements or [])
                     if ((e or {}).get("element_type") or "") == "tablou_teg"), None)
        _teg_xy = None
        if _teg is not None:
            try:
                _teg_xy = (float(_teg["x"]), float(_teg["y"]))
            except (TypeError, ValueError, KeyError):
                _teg_xy = None
        # SIMBOLURILE deasupra cablurilor. Etichetele (bec + priza) NU se mai deseneaza imediat:
        # se COLECTEAZA ca spec-uri si se deseneaza DUPA toate simbolurile, cu anti-coliziune
        # (_resolve_label_overlaps) — etichetele suprapuse se stivuiesc in sus, restul raman pe loc.
        _labels = []
        # PUNCTUL 3: bbox camere (puncte PDF) -> orientarea prizei pe perete (bara + semicerc spre interior).
        _room_px_map = _rooms_to_px(rooms, page.rect.width, page.rect.height)
        for el in (elements or []):
            try:
                et = (el.get("element_type") or "")
                x = float(el["x"]); y = float(el["y"])
            except (TypeError, ValueError, KeyError):
                continue
            if et in _BULB_TYPES:
                _draw_bulb(page, x, y, et, y_offset=0)                               # forma PE TIP (1b)
                _sp = _bulb_label_spec(x, y, et, el.get("power_w"), el.get("circuit_id"))   # eticheta + prefix circuit
                if _sp:
                    _labels.append(_sp)
                n_bulb += 1
            elif et in _SWITCH_TYPES:
                _draw_switch(page, x, y, float(el.get("rotation") or 0.0), et)        # pe tip (deja)
                n_sw += 1
            elif et in _PANEL_TYPES:
                _draw_panel(page, x, y, et)                                          # tablou TEG/TE-CT (1c)
                n_panel += 1
            elif et in _PRIZA_TYPES:
                # O1: ORIENTAREA = rotation-ul PERSISTAT de editor (snap pe peretii REALI — aceeasi
                # sursa pe care o vede inginerul in editor => PDF = editor prin constructie; prizele
                # excentrice pe perete nu se mai intorc). rotation lipsa (vechi) -> centroid (ca
                # inainte); centroid degenerat -> bbox fallback. POZITIA = (x,y) pusa de inginer.
                _wi = _wa = None
                _room_nm = (el.get("room") or "").strip()
                _o = _priza_inward(el.get("rotation"), x, y, _cen_map.get(_room_nm))
                if _o is None and _room_px_map and _room_px_map.get(_room_nm):
                    _, _wi, _wa = _wall_orient(x, y, _room_px_map[_room_nm])   # fallback bbox
                elif _o:
                    _wi, _wa = _o
                _draw_priza(page, x, y, et, rotation=float(el.get("rotation") or 0.0),
                            wall_inward=_wi, wall_along=_wa)
                _sp = _priza_label_spec(x, y, el, inward=_wi)                        # eticheta IN FATA prizei (bold)
                if _sp:
                    _labels.append(_sp)
                n_priza += 1
            elif et == "legenda":
                continue                                                             # caseta legenda = overlay separat (L3); NU simbol, NU skip
            elif et == "ground_electrode_path":
                # Priza de pamant: DOAR la parter (fundatia); defensiv fata de alt floor.
                if str(el.get("floor") or "parter") == "parter" and _draw_ground_electrode(page, el, _teg_xy):
                    n_ground += 1
            elif et == "alimentare_receptor":
                # Receptor (bucata A): simbolul de ALIMENTARE existent (priza_16a = cerc plin), refolosit.
                # `label` (boiler/cuptor/...) + inaltimea de montaj (h=..m, ca la prize) sub simbol.
                _draw_priza(page, x, y, "priza_16a")
                _rl = (el.get("label") or "").strip()
                _rh = _fmt_height(el.get("mount_height_m"))
                _rt = (_rl[:1].upper() + _rl[1:]) if _rl else ""
                if _rt:
                    # acelasi stil ca etichetele prizelor (bold + 9.0, lizibil); receptorul sta LIBER
                    # in camera (nu pe perete) -> eticheta ramane SUB simbol (y+24, aer pt. cercul marit).
                    # O2: echipamentele de INCALZIRE (clasa 1) au descrieri lungi -> WRAP pe cuvinte
                    # la ~25 caractere, max 2 randuri; h=X.Xm pe ULTIMUL rand. Restul (boiler din alta
                    # camera / cuptor / AC / EV): single-line ca inainte.
                    _rfs = 9.0
                    if _is_heating_receptor(_rl) and len(_rt) > 25:
                        _rlines = _wrap_label_25(_rt, 25)
                    else:
                        _rlines = [_rt]
                    if _rh:
                        _rlines[-1] = ("%s  h=%sm" % (_rlines[-1], _rh)).strip()
                    _rw = max(len(ln) for ln in _rlines) * _rfs * 0.50
                    _labels.append({"text": " ".join(_rlines), "lines": _rlines,
                                    "x0": x - _rw / 2.0, "y": y + 24.0, "w": _rw,
                                    "fs": _rfs, "font": "hebo", "color": _PRIZA_COLOR})
                n_receptor += 1
            elif et == "receptor_internet":
                _draw_internet(page, x, y)                                            # simbol RETEA (violet + router + WiFi)
                _nh = _fmt_height(el.get("mount_height_m"))                           # inaltime de montaj (ca la prize)
                if _nh:
                    _nt = "Retea  h=%sm" % _nh
                    _nfs = 7.5
                    _nw = len(_nt) * _nfs * 0.46
                    _labels.append({"text": _nt, "x0": x - _nw / 2.0, "y": y + 22.0, "w": _nw,
                                    "fs": _nfs, "font": "helv", "color": _NET_EDGE})
                n_receptor += 1
            else:
                n_skip += 1                                                          # alt tip necunoscut -> SKIP
        # ETICHETELE deasupra tuturor simbolurilor, cu anti-coliziune. Defensiv: orice eroare la
        # rezolvare NU strica planul — fallback la pozitiile de baza (comportamentul vechi).
        try:
            _labels = _resolve_label_overlaps(_labels)
        except Exception:
            pass
        for _sp in _labels:
            _draw_label_spec(page, _sp)
        # COLOANE de legatura (FORTA): feed TE-CT -> TEG (ambele parter) = linie TEAL solida.
        # Sectiunea vine din feed (result_data.circuits sub_tablou). Doar TE-CT->TEG acum
        # (TES->TEG cross-plansa = follow-up). COLOANA URMEAZA TRASEELE desenate de inginer
        # (autoritar, ca iesirile circuitelor: dunga cea mai apropiata de origine) — coloana merge
        # prin patul comun de cabluri, NU taie prin incaperi. Fara trasee -> L direct (ca inainte).
        # Defensiv: orice eroare -> skip, nu strica planul.
        try:
            if draw_plan_type == "forta" and feeds:
                _pan_xy = {}
                for e in (elements or []):
                    et = (e or {}).get("element_type") or ""
                    if et in _PANEL_TYPES:
                        try:
                            _pan_xy[et] = (float(e["x"]), float(e["y"]))
                        except (TypeError, ValueError, KeyError):
                            pass
                _teg = _pan_xy.get("tablou_teg")
                _col_stripes = _extract_stripes(elements)      # traseele plansei (deja filtrate pe forta)
                for f in (feeds or []):
                    if (isinstance(f, dict) and f.get("type") == "sub_tablou"
                            and f.get("feeds_panel") == "TE-CT" and _teg and _pan_xy.get("tablou_te_ct")):
                        _a = _pan_xy["tablou_te_ct"]
                        _si = _nearest_stripe_idx(_a, _col_stripes) if _col_stripes else None
                        # BUG 4: coloana TE-CT primeste un SLOT propriu (offset lateral fix, dincolo de
                        # manunchiurile de prize centrate ±(cap-1)/2*gap) -> nu mai acopera restul.
                        _cp = (_stripe_path(_a, _teg, _col_stripes[_si], offset=_COLUMN_STRIPE_OFFSET)
                               if _si is not None else None)
                        _draw_column(page, _a, _teg, path=_cp)
        except Exception:
            pass
        # TRAVERSARE INTRE NIVELURI (cross-plansa, varianta A): pe plansa cu TEG -> coloana TEG ->
        # PROIECTIA TES (pe traseele desenate, slot propriu OPUS coloanei TE-CT) + simbol "URCA";
        # pe plansa cu TES -> doar simbolul "VINE DE JOS" la TES (coloana urca prin planseu).
        # cross_floor = {"mode": "up"/"down", "xy": (x,y), "label": str} — construit de /regenerate-plan
        # (proiectia = pozitia TES transformata cu floor_offset, cascada grid->pereti->identitate).
        # Defensiv: orice eroare -> skip, planul ramane intact.
        try:
            if draw_plan_type == "forta" and isinstance(cross_floor, dict) and cross_floor.get("xy"):
                _cxy = (float(cross_floor["xy"][0]), float(cross_floor["xy"][1]))
                if cross_floor.get("mode") == "up":
                    _teg2 = None
                    for e in (elements or []):
                        if ((e or {}).get("element_type") or "") == "tablou_teg":
                            try:
                                _teg2 = (float(e["x"]), float(e["y"]))
                            except (TypeError, ValueError, KeyError):
                                pass
                    if _teg2:
                        _st2 = _extract_stripes(elements)
                        _si2 = _nearest_stripe_idx(_cxy, _st2) if _st2 else None
                        # slot OPUS coloanei TE-CT (−offset) -> cele doua coloane nu se acopera pe traseu
                        _cp2 = (_stripe_path(_cxy, _teg2, _st2[_si2], offset=-_COLUMN_STRIPE_OFFSET)
                                if _si2 is not None else None)
                        _draw_column(page, _cxy, _teg2, path=_cp2, color=_TES_COLUMN_COLOR)
                    _draw_floor_crossing(page, _cxy[0], _cxy[1], up=True, label=cross_floor.get("label"))
                elif cross_floor.get("mode") == "down":
                    _draw_floor_crossing(page, _cxy[0], _cxy[1], up=False, label=cross_floor.get("label"))
        except Exception:
            pass
        # LEGENDA (L3): overlay DEASUPRA tuturor simbolurilor, DOAR daca inginerul a adaugat elementul "legenda".
        n_legend = 0
        try:
            _leg = next((e for e in (elements or [])
                         if ((e or {}).get("element_type") or "") == "legenda"), None)
            if _leg is not None:
                _draw_legend(page, float(_leg["x"]), float(_leg["y"]), build_legend_rows(elements, draw_plan_type, feeds, circuits, cross_floor=cross_floor))
                n_legend = 1
        except Exception:
            n_legend = 0
        out = doc.tobytes(deflate=True)
        return {
            "success": True,
            "pdf_base64": base64.b64encode(out).decode("utf-8"),
            "filename": "Plan_{}_editat.pdf".format(draw_plan_type),
            "size_bytes": len(out),
            # PAS 2 (numerotare): numarul/titlul FINAL aplicat (None = comportament vechi) -> frontend-ul
            # persista source_plansa_nr corect pe planse_forta. stamped_* = daca s-au scris efectiv pe cartus.
            "plansa_nr": plansa_nr,
            "plansa_titlu": plansa_titlu,
            "plansa_stamped": bool(_stamped_nr),
            "detected": {"bulbs_drawn": n_bulb, "switches_drawn": n_sw, "panels_drawn": n_panel,
                         "prizas_drawn": n_priza, "cables_drawn": n_cable, "skipped": n_skip,
                         "legend_drawn": n_legend, "ground_drawn": n_ground, "receptor_drawn": n_receptor},
            # Traseele cablurilor (din compute_cables, ACEEASI sursa ca desenul PDF) pt. overlay-ul Konva.
            # Coordonate in PUNCTE PDF (ca x,y ale elementelor) -> frontend le inmulteste cu png_meta.scale.
            "cables": [{"path": [[round(px, 1), round(py, 1)] for (px, py) in (c.get("path") or [])],
                        "kind": c.get("kind")} for c in _cables],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        if doc is not None:
            try:
                doc.close()
            except Exception:
                pass
        gc.collect()


def draw_plan_elements(data: dict) -> dict:
    """Desenează becuri în centrul camerelor.
    Cale 1 (preferată): bbox-uri Vision din data['rooms'] (fracții 0-1) -> robust.
    Cale 2 (fallback): regex pe textul de suprafață (_find_room_centers).
    Plasă de siguranță: 0 camere găsite → returnează planul NEMODIFICAT."""
    try:
        pdf_b64 = data.get("pdf_base64") or ""
        raw = pdf_b64.split(",", 1)[1] if "," in pdf_b64 else pdf_b64
        pdf_bytes = base64.b64decode(raw)
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[0]
        W, H = page.rect.width, page.rect.height
        # Titlul cartusului: plansa generata aici e ILUMINAT (n8n "Draw Iluminat Plan").
        # No-op daca PDF-ul nu are metadata de cartus (vechi / cartus nedetectat la swap).
        _apply_cartus_suffix(doc, page, "DE ILUMINAT")

        # Geometrie CAD (centroizi perete-la-perete) DOAR pe faza PT (apply_geometry din n8n).
        # Defensiv: ORICE eroare -> geoms=None -> fallback TOTAL la centrul bbox Vision.
        # Generarea becurilor NU trebuie să eșueze niciodată din cauza geometriei.
        rooms = data.get("rooms")
        geoms = None
        walls = None   # (h_segs, v_segs) pt. R2 holuri — doar pe cale geometrică (apply_geometry)
        if data.get("apply_geometry") and rooms:
            try:
                import geometry
                geoms = geometry.extract_room_geometry(pdf_bytes, rooms, W, H)
                h_segs, v_segs, _dd = geometry._collect(page)
                walls = (h_segs, v_segs)
            except Exception:
                geoms = None; walls = None

        # APARATAJ (MVP): întrerupătoare lângă uși — DOAR pe faza PT (apply_geometry), cale vectorială.
        # Aditiv, defensiv: ORICE eroare -> fără întrerupătoare, becurile NU sunt afectate.
        # bbox-uri camere (px) — pt. asocierea întrerupător↔cameră (regula "bec garantat")
        rboxes = []
        for r in (rooms or []):
            bb = (r or {}).get("bbox") or {}
            try:
                rboxes.append((float(bb["x"])*W, float(bb["y"])*H, float(bb["w"])*W, float(bb["h"])*H))
            except (TypeError, ValueError, KeyError):
                rboxes.append(None)

        # APARATAJ: întrerupătoarele se calculează MAI JOS, DUPĂ `centers` (paritate 1:1 — un
        # întrerupător per bec). rboxes (de mai sus) e folosit acolo pentru maparea bec->ușă.

        # Cale nouă: dacă primim camere cu bbox de la Vision (fracții 0-1),
        # desenăm becurile din centrele lor — robust, independent de text/regex.
        # Altfel -> fallback la calea veche cu regex pe textul de suprafață.
        vision_centers, vision_stats = _vision_centers(rooms, W, H, geoms, walls)
        if vision_centers:
            source = "vision_bbox"
            centers = vision_centers
        else:
            source = "text_regex"
            centers = _find_room_centers(page, W, H)
            vision_stats = {"rooms_geometric": 0, "rooms_fallback": 0, "bbox_fixed": 0,
                            "bulbs_dedup": 0, "bulbs_guaranteed": 0, "bulbs_separated": 0}

        # NOTĂ: garanția "fiecare cameră are bec" + plasarea off-wall sunt acum ÎN _vision_centers
        # (pasă autoritară: ancoră geometric/clip + invariant final). Aici nu mai sunt gărzi separate.

        # plasă de siguranță: nu desena nimic dacă n-am găsit camere
        if len(centers) == 0:
            out = doc.tobytes(deflate=True)
            return {
                "success": True,
                "source": source,
                "pdf_base64": base64.b64encode(out).decode("utf-8"),
                "filename": f"Plan_{data.get('plansa_nr','') or 'IE'}_iluminat.pdf",
                "size_bytes": len(out),
                "detected": {"rooms_found": 0, "elements_drawn": 0,
                             "rooms_geometric": 0, "rooms_fallback": 0,
                             "bbox_fixed": 0, "bulbs_dedup": 0, "bulbs_guaranteed": 0,
                             "note": "Nicio cameră detectată. Plan nemodificat."},
            }

        # REGULA TIP+PUTERE pe camera (basic, editabil): atasata pe fiecare corp DEJA plasat.
        # NU schimba cate corpuri / pozitiile (decise de _vision_centers cu geometry).
        for c in centers:
            _bt, _bw = _bulb_rule_for_room(c.get("label"))
            c["_bulb_type"] = _bt
            c["_bulb_pw"] = _bw

        # APARATAJ (paritate 1:1): UN întrerupător per BEC, calculat din `centers`. DOAR pe faza PT
        # (apply_geometry), cale vectorială. Aditiv, defensiv: ORICE eroare -> fără întrerupătoare,
        # becurile NU sunt afectate. (Plasare: la ușa camerei becului dacă există, altfel lângă bec.)
        # REGULA SP: corpurile cu senzor (aplica_senzor, ex. terase) NU primesc întrerupător —
        # se exclud din pairing; cablarea lor directa la TEG e deja in compute_cables (senzor_teg).
        switches = []
        if data.get("apply_geometry"):
            try:
                import geometry
                doors = geometry.extract_doors(page, W, H)
                columns = geometry.extract_columns(page)
                h_segs, v_segs, _dd = geometry._collect(page)
                _sw_centers = [c for c in centers if c.get("_bulb_type") != "aplica_senzor"]
                switches = _switch_centers(_sw_centers, doors, columns, h_segs, v_segs, W, H, rboxes)
            except Exception:
                switches = []

        # vision_bbox: cy e deja centrul camerei -> fără offset (bec în centru).
        # text_regex: cy e poziția textului "A:" -> -22 (bec deasupra textului).
        y_offset = 0 if source == "vision_bbox" else -22
        for c in centers:
            _draw_bulb(page, c["x"], c["y"], c.get("_bulb_type") or "aplica_tavan", y_offset=y_offset)

        # APARATAJ: desenează întrerupătoarele (după becuri, pe aceeași planșă)
        for s in switches:
            _draw_switch(page, s["x"], s["y"], s["angle"], s.get("element_type", "intrerupator_simplu"))

        out = doc.tobytes(deflate=True)

        # ADITIV (editor interactiv): versiune PNG a planului final, din ACELAȘI `page`
        # (după ce becurile + întrerupătoarele sunt desenate -> pixel-identic cu PDF-ul),
        # + metadate de mapare puncte-PDF -> pixeli-PNG (overlay aliniat).
        # Defensiv: ORICE eroare la raster -> png None; NU afectează pdf_base64/centers.
        png_base64 = None
        png_meta = None
        try:
            _png_dpi = 120                      # 120 DPI (redus de la 150) -> ~36% mai putin RAM/PNG
            _png_scale = _png_dpi / 72.0        # scale DINAMIC -> png_meta.scale; consumatorii citesc de aici
            _pix = page.get_pixmap(matrix=fitz.Matrix(_png_scale, _png_scale))
            png_base64 = base64.b64encode(_pix.tobytes("png")).decode("utf-8")
            png_meta = {
                "dpi": _png_dpi,
                "scale": _png_scale,            # factor puncte-PDF -> pixeli-PNG (= dpi/72)
                "pdf_width_pt": W,
                "pdf_height_pt": H,
                "png_width_px": _pix.width,
                "png_height_px": _pix.height,
            }
            _pix = None                          # elibereaza pixmap-ul (raw ~mare) imediat dupa base64
        except Exception:
            png_base64 = None
            png_meta = None

        # rooms_found = nr. camere (o cameră poate avea 2 becuri); elements_drawn = becuri.
        rooms_found = len({c.get("room") for c in centers}) if source == "vision_bbox" else len(centers)

        # ADITIV (editor interactiv): persistă becuri + întrerupătoare în Supabase plan_elements.
        # OPȚIONAL + NON-BLOCANT: project_id gol / Supabase indisponibil / ORICE eroare -> se sare,
        # planul se generează NORMAL (pdf_base64/png_base64/centers neafectate). Idempotent în
        # save_plan_elements (DELETE project_id+floor, apoi INSERT) -> re-generarea înlocuiește.
        _project_uuid = (data.get("project_id") or "").strip()
        if _project_uuid:
            try:
                from supabase_client import save_plan_elements
                _floor = str(data.get("floor") or "parter")
                _elements = []
                for c in centers:
                    _elements.append({
                        "project_id": _project_uuid, "floor": _floor,
                        # tip + putere din regula pe camera (_bulb_rule_for_room); inginerul schimbă în editor
                        "element_type": c.get("_bulb_type") or "aplica_tavan",
                        "label": None, "room": c.get("label"),
                        "x": round(c["x"], 1), "y": round(c["y"], 1),
                        "wall_mounted": False, "rotation": 0,
                        "circuit_id": None, "source_panel": None, "power_w": c.get("_bulb_pw"), "z_index": 0,
                    })
                for s in switches:
                    _elements.append({
                        "project_id": _project_uuid, "floor": _floor,
                        "element_type": "intrerupator_simplu",
                        "label": None, "room": s.get("room"),   # = camera becului (paritate 1:1)
                        "x": round(s["x"], 1), "y": round(s["y"], 1),
                        "wall_mounted": True, "rotation": round(float(s.get("angle", 0)), 3),
                        "circuit_id": None, "source_panel": None, "power_w": None, "z_index": 0,
                    })
                save_plan_elements(_project_uuid, _elements)
            except Exception:
                pass  # NON-BLOCANT: persistența eșuată NU strică generarea planului

        return {
            "success": True,
            "source": source,
            "pdf_base64": base64.b64encode(out).decode("utf-8"),
            "filename": f"Plan_{data.get('plansa_nr','') or 'IE'}_iluminat.pdf",
            "size_bytes": len(out),
            "png_base64": png_base64,
            "png_meta": png_meta,
            "detected": {
                "rooms_found": rooms_found,
                "elements_drawn": len(centers),
                "rooms_geometric": vision_stats["rooms_geometric"],
                "rooms_fallback": vision_stats["rooms_fallback"],
                "bbox_fixed": vision_stats["bbox_fixed"],
                "bulbs_dedup": vision_stats["bulbs_dedup"],
                "bulbs_guaranteed": vision_stats["bulbs_guaranteed"],
                "bulbs_separated": vision_stats["bulbs_separated"],
                "switches_drawn": len(switches),
                "switches_certain": sum(1 for s in switches if s.get("certain")),
                "switches": [{"x": round(s["x"], 1), "y": round(s["y"], 1),
                              "angle": round(float(s.get("angle", 0)), 3),
                              "room": s.get("room")} for s in switches],   # room = numele camerei becului
                # element_type + power_w (regula _bulb_rule_for_room, deja calculate ca _bulb_type/_bulb_pw):
                # frontend-ul le foloseste la INSERT-ul plan_elements -> editorul arata acelasi corp ca PDF-ul.
                "centers": [{"x": round(c["x"], 1), "y": round(c["y"], 1),
                             "label": c["label"][:40],
                             "element_type": c.get("_bulb_type") or "aplica_tavan",
                             "power_w": c.get("_bulb_pw")} for c in centers],
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        # RAM: inchide documentul PyMuPDF pe ORICE cale (succes/early-return/exceptie) + colecteaza.
        # NU schimba raspunsul (out/png_base64 sunt deja extrase ca bytes/str inainte de finally).
        try:
            doc.close()
        except Exception:
            pass
        gc.collect()
