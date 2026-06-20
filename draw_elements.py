import base64
import math
import re
import fitz  # PyMuPDF

# Roșu pentru planșa de iluminat (RGB 0-1)
RED = (0.86, 0.16, 0.16)

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


def _draw_bulb(page, cx, cy, r=9.0, y_offset=-22):
    """Simbol standard corp de iluminat: cerc cu X (două diametre la 45°), roșu.
    y_offset: deplasare verticală față de (cx, cy). Default -22 = deasupra ancorei
    de suprafață (cale text_regex). vision_bbox cheamă cu y_offset=0 (centrul real)."""
    center = fitz.Point(cx, cy + y_offset)  # y_offset negativ = în sus
    # cerc
    page.draw_circle(center, r, color=RED, width=1.2)
    # X = două diagonale la 45°, rază = r
    import math
    d = r * math.cos(math.radians(45))
    page.draw_line(fitz.Point(center.x - d, center.y - d),
                   fitz.Point(center.x + d, center.y + d), color=RED, width=1.2)
    page.draw_line(fitz.Point(center.x - d, center.y + d),
                   fitz.Point(center.x + d, center.y - d), color=RED, width=1.2)


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
    """Niciun bec NON-geometric nu trebuie să cadă în bbox-ul ALTEI camere (Vision dă bbox-uri
    suprapuse -> becul fallback al unei camere ajunge vizual în zona vecinei = a 2-a 'lumină' acolo).
    Pentru fiecare astfel de bec, îl mută în propriul bbox la un punct care: NU e în bbox-ul altei
    camere, e off-wall, și departe de alte becuri. Becul GEOMETRIC (sursă de adevăr) rămâne pe loc.
    Dacă propriul bbox e complet înghițit (niciun loc liber) -> lasă (limită open-plan). -> nr. mutate."""
    def in_other(px, py, ri):
        for k, b in enumerate(boxes):
            if k == ri or b is None:
                continue
            if b[0]*W <= px <= (b[0]+b[2])*W and b[1]*H <= py <= (b[1]+b[3])*H:
                return True
        return False

    moved = 0
    for c in centers:
        if c.get("geometric"):
            continue
        ri = c["room"]
        if ri is None or ri >= len(boxes) or boxes[ri] is None:
            continue
        if not in_other(c["x"], c["y"], ri):
            continue   # becul e deja DOAR în camera lui -> ok
        bx, by, bw, bh = boxes[ri]
        bx0, by0, bx1, by1 = bx*W, by*H, (bx+bw)*W, (by+bh)*H
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
        if not used_geometric:
            cxc, cyc = _clip_region(x * W, y * H, w * W, h * H, h_segs, v_segs)
            rooms_fallback += 1

        # COUNT (1 vs 2 becuri) pe ARIA DIN CARTUȘ (area_m2, citită din textul bilanțului):
        # ~0% variație între generări ȘI exactă (= aria reală). NU pe aria GEOMETRICĂ — poligonul
        # poate over-merge (ex. Camera de zi geom 49.7 vs cartuș 35.75 -> ar putea umfla gresit count-ul).
        # `area` = area_m2 cartuș când există; fallback la aria bbox doar dacă lipsește din cartuș.
        if area >= ROOM_LARGE_M2:
            # 2 becuri pe axa LUNGĂ a bbox-ului, re-centrate pe (cxc, cyc). PROTEJATE (coverage intentionat).
            if w * W >= h * H:
                dx = (w / 6.0) * W   # jumătatea distanței dintre pozițiile 1/3 și 2/3
                centers.append({"x": cxc - dx, "y": cyc, "label": label, "room": idx, "geometric": used_geometric, "protected": True})
                centers.append({"x": cxc + dx, "y": cyc, "label": label, "room": idx, "geometric": used_geometric, "protected": True})
            else:
                dy = (h / 6.0) * H
                centers.append({"x": cxc, "y": cyc - dy, "label": label, "room": idx, "geometric": used_geometric, "protected": True})
                centers.append({"x": cxc, "y": cyc + dy, "label": label, "room": idx, "geometric": used_geometric, "protected": True})
        else:
            # R2 — HOL alungit (bbox aspect>2, fallback): 1 bec in MIJLOCUL holului, garantat off-wall.
            # Axa SCURTA (perp) = mijloc intre cei 2 pereti lungi; daca DOAR UNUL se gaseste -> mijloc
            # intre el si marginea bbox (holul deschis pe o latura, ex. Hol central spre living). Axa
            # LUNGA = centru, apoi NUDGE off-wall daca o partitie transversala cade acolo. Astfel becul
            # nu cade pe perete nici pe zid transversal. 1 bec (consistent cu count-ul pe aria cartus).
            hall_done = False
            if (not used_geometric) and h_segs is not None and v_segs is not None:
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
                # 1 bec la ANCORĂ (centroid geometric SAU centrul regiunii clipate — deja în interior).
                centers.append({"x": cxc, "y": cyc, "label": label, "room": idx, "geometric": used_geometric, "protected": used_geometric})

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
        if g and g.get("geometric") and g.get("centroid"):
            try:
                ax, ay = float(g["centroid"]["x"]), float(g["centroid"]["y"])
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


def _draw_switch(page, x, y, angle):
    """Simbol întrerupător SR EN 60617: punct PLIN + tijă oblică CLAR vizibilă (maneta), spre cameră.
    Tija pornește de la MARGINEA punctului (nu din centru) ca să se vadă integral; groasă (2px)."""
    dx, dy = math.cos(angle), math.sin(angle)
    c = fitz.Point(x, y)
    start = fitz.Point(x + SWITCH_R * dx, y + SWITCH_R * dy)
    end = fitz.Point(x + (SWITCH_R + SWITCH_STEM) * dx, y + (SWITCH_R + SWITCH_STEM) * dy)
    page.draw_line(start, end, color=RED, width=2.0)              # maneta — vizibila
    page.draw_circle(c, SWITCH_R, color=RED, fill=RED, width=0.8)  # punct plin peste capat


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


def _switch_centers(doors, columns, h_segs, v_segs, W, H, room_boxes=None):
    """Poziția întrerupătorului per ușă: latura de deschidere (mâner), LIPIT pe linia peretelui lângă
    toc, spre interiorul camerei; evită sâmburii; fallback la incertitudine.
    Tag 'room' = camera pe care o SERVEȘTE (în care se deschide ușa) — pt. regula 'bec garantat'.
    -> [{x,y,angle,certain,room}]."""
    def served_room(d):
        # camera = bbox-ul care conține un punct ÎN FAȚA ușii, pe direcția de deschidere (swing)
        if not room_boxes:
            return None
        ux, uy = d["swing"]
        px = d["x"] + ux * 55.0; py = d["y"] + uy * 55.0
        for k, b in enumerate(room_boxes):
            if b and b[0] <= px <= b[0]+b[2] and b[1] <= py <= b[1]+b[3]:
                return k
        return None

    out = []
    for d in doors:
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

        out.append({"x": sx, "y": sy, "angle": math.atan2(uy, ux), "certain": d["certain"],
                    "room": served_room(d)})
    return out


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

        switches = []
        if data.get("apply_geometry"):
            try:
                import geometry
                doors = geometry.extract_doors(page, W, H)
                columns = geometry.extract_columns(page)
                h_segs, v_segs, _dd = geometry._collect(page)
                switches = _switch_centers(doors, columns, h_segs, v_segs, W, H, rboxes)
            except Exception:
                switches = []

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

        # vision_bbox: cy e deja centrul camerei -> fără offset (bec în centru).
        # text_regex: cy e poziția textului "A:" -> -22 (bec deasupra textului).
        y_offset = 0 if source == "vision_bbox" else -22
        for c in centers:
            _draw_bulb(page, c["x"], c["y"], y_offset=y_offset)

        # APARATAJ: desenează întrerupătoarele (după becuri, pe aceeași planșă)
        for s in switches:
            _draw_switch(page, s["x"], s["y"], s["angle"])

        out = doc.tobytes(deflate=True)

        # ADITIV (editor interactiv): versiune PNG a planului final, din ACELAȘI `page`
        # (după ce becurile + întrerupătoarele sunt desenate -> pixel-identic cu PDF-ul),
        # + metadate de mapare puncte-PDF -> pixeli-PNG (overlay aliniat).
        # Defensiv: ORICE eroare la raster -> png None; NU afectează pdf_base64/centers.
        png_base64 = None
        png_meta = None
        try:
            _png_scale = 150 / 72.0
            _pix = page.get_pixmap(matrix=fitz.Matrix(_png_scale, _png_scale))
            png_base64 = base64.b64encode(_pix.tobytes("png")).decode("utf-8")
            png_meta = {
                "dpi": 150,
                "scale": _png_scale,            # factor puncte-PDF -> pixeli-PNG
                "pdf_width_pt": W,
                "pdf_height_pt": H,
                "png_width_px": _pix.width,
                "png_height_px": _pix.height,
            }
        except Exception:
            png_base64 = None
            png_meta = None

        # rooms_found = nr. camere (o cameră poate avea 2 becuri); elements_drawn = becuri.
        rooms_found = len({c.get("room") for c in centers}) if source == "vision_bbox" else len(centers)
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
                "centers": [{"x": round(c["x"], 1), "y": round(c["y"], 1),
                             "label": c["label"][:40]} for c in centers],
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
