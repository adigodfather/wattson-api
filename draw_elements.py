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


def _point_in_box(px, py, box, W, H):
    """box = (x, y, w, h) fracții 0-1; px,py în puncte PDF.
    True dacă punctul cade în interiorul bbox-ului (margini incluse)."""
    bx, by, bw, bh = box
    return (bx * W <= px <= (bx + bw) * W) and (by * H <= py <= (by + bh) * H)


def _free_midpoint_1d(lo, hi, olo, ohi):
    """Pe intervalul [lo, hi], scoate suprapunerea [olo, ohi] și întoarce mijlocul
    celei mai LARGI părți libere rămase (latura lo sau latura hi).
    None dacă suprapunerea acoperă tot intervalul (nu rămâne nimic liber)."""
    olo = max(lo, olo); ohi = min(hi, ohi)
    left_w = olo - lo      # partea liberă [lo, olo]
    right_w = hi - ohi     # partea liberă [ohi, hi]
    if left_w <= 0 and right_w <= 0:
        return None
    return (ohi + hi) / 2.0 if right_w >= left_w else (lo + olo) / 2.0


def _nudge_out_of_neighbors(cx, cy, own_box, others, W, H):
    """Gardă anti-intruziune: dacă becul (cx,cy) al unei camere cade în bbox-ul unei
    camere VECINE (tipic un hol lat/în-L al cărui centru-bbox intră peste vecină),
    mută becul pe axa LUNGĂ a PROPRIULUI bbox, în mijlocul părții care NU se suprapune
    cu vecina. Întoarce (nx, ny, moved).
    CONSERVATOR: se activează DOAR la intruziune reală; dacă nu se poate ieși fără a
    părăsi propriul bbox sau fără a intra în ALTĂ cameră -> păstrează poziția originală
    (mai bine un bec ușor deplasat decât unul în camera greșită)."""
    hit = next((ob for ob in others if _point_in_box(cx, cy, ob, W, H)), None)
    if hit is None:
        return cx, cy, False   # fără intruziune -> NEATINS (camere normale)

    ox, oy, ow, oh = own_box
    x0, x1 = ox * W, (ox + ow) * W
    y0, y1 = oy * H, (oy + oh) * H
    hx0, hx1 = hit[0] * W, (hit[0] + hit[2]) * W
    hy0, hy1 = hit[1] * H, (hit[1] + hit[3]) * H

    if (x1 - x0) >= (y1 - y0):
        # bandă orizontală -> alunecă pe X, păstrează Y în centrul propriu
        mid = _free_midpoint_1d(x0, x1, hx0, hx1)
        if mid is None:
            return cx, cy, False
        nx, ny = mid, (y0 + y1) / 2.0
    else:
        # bandă verticală -> alunecă pe Y, păstrează X în centrul propriu
        mid = _free_midpoint_1d(y0, y1, hy0, hy1)
        if mid is None:
            return cx, cy, False
        nx, ny = (x0 + x1) / 2.0, mid

    # validare: noua poziție trebuie să fie în PROPRIUL bbox ȘI în afara ORICĂREI vecine
    if not (x0 <= nx <= x1 and y0 <= ny <= y1):
        return cx, cy, False
    if any(_point_in_box(nx, ny, ob, W, H) for ob in others):
        return cx, cy, False
    return nx, ny, True


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


def _clamp_to_contour(px, py, contour):
    """A — ține becul în interiorul conturului global al clădirii (x0,y0,x1,y1 în puncte PDF).
    Dacă becul cade ÎN AFARA conturului -> tras la cea mai apropiată poziție din interior.
    Becurile din interior -> NEATINSE. Întoarce (nx, ny, moved)."""
    if contour is None:
        return px, py, False
    x0, y0, x1, y1 = contour
    nx = min(max(px, x0), x1)
    ny = min(max(py, y0), y1)
    return nx, ny, (abs(nx - px) > 1e-6 or abs(ny - py) > 1e-6)


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


def _vision_centers(rooms, W, H, geoms=None, walls=None):
    """Centre din bbox Vision (fracții 0-1) -> puncte PDF.
    rooms = listă de { name, area_m2, bbox: {x, y, w, h} } cu x,y,w,h în [0,1].
    geoms = OPȚIONAL, listă PARALELĂ cu rooms (de la geometry.extract_room_geometry).
            Dacă o cameră are centroid geometric (geometric=True) -> becul folosește
            centroidul geometric (centrat perete-la-perete). Altfel -> centru bbox Vision
            (comportament NESCHIMBAT). Lipsă/None -> totul pe Vision (zero regresie).
    Cameră mare (area_m2 >= ROOM_LARGE_M2; fallback = aria bbox ca proxy) -> 2 becuri
    pe axa LUNGĂ a bbox-ului (la 1/3 și 2/3); altfel 1 bec la centru. MAX 2 becuri/cameră.
    La 2 becuri pe cameră geometrică: aceeași orientare+distanță (axa lungă bbox), dar
    perechea RE-CENTRATĂ pe centroidul geometric. Ignoră tăcut camerele fără bbox valid.
    GARDĂ anti-intruziune (single-bulb, cale bbox): dacă becul ar cădea în bbox-ul altei
    camere (hol lat/în-L), e mutat în partea liberă a propriului bbox (vezi _nudge_out_of_neighbors)."""
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

    # A — contur global al clădirii = union bbox-uri (aprox.), cu padding interior 2%.
    # LIMITĂ ONESTĂ: union-ul include ORICE bbox -> un bbox Vision GREȘIT își extinde singur
    # conturul. Garda prinde DOAR becurile în afara TUTUROR camerelor (alb total); NU corectează
    # un bbox mutat în interiorul clădirii (ex. terasa casa pt, al cărei bbox e parte din union).
    valid = [b for b in boxes if b is not None]
    contour = None
    if valid:
        xmn = min(b[0] for b in valid); ymn = min(b[1] for b in valid)
        xmx = max(b[0] + b[2] for b in valid); ymx = max(b[1] + b[3] for b in valid)
        padx = (xmx - xmn) * 0.02; pady = (ymx - ymn) * 0.02
        contour = ((xmn + padx) * W, (ymn + pady) * H, (xmx - padx) * W, (ymx - pady) * H)

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

        # centrul camerei: centroid geometric (dacă a reușit) ALTFEL centru bbox Vision (ca până acum)
        cxc = (x + w / 2.0) * W
        cyc = (y + h / 2.0) * H
        g = geoms[idx] if (geoms and idx < len(geoms)) else None
        used_geometric = bool(g and g.get("geometric") and g.get("centroid"))
        if used_geometric:
            try:
                cxc = float(g["centroid"]["x"]); cyc = float(g["centroid"]["y"])
                rooms_geometric += 1
            except (TypeError, ValueError, KeyError):
                used_geometric = False     # date geometrice corupte -> centru bbox
                rooms_fallback += 1
        else:
            rooms_fallback += 1

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
            # R2 — HOL (bbox alungit, fallback, cu pereți): 1/2 becuri pe lungime, centrate între
            # cei 2 pereți paraleli. DOAR dacă ambii pereți se găsesc clar; altfel conservator (1 bec).
            hall_done = False
            if (not used_geometric) and h_segs is not None:
                bx, by, bw, bh = x * W, y * H, w * W, h * H
                if max(bw, bh) / max(min(bw, bh), 1.0) > HALL_ASPECT:
                    if bw >= bh:   # hol orizontal -> pereți sus/jos (H), becuri pe axa X
                        c1 = _wall_coord_near(by, bx, bx + bw, h_segs, "H")
                        c2 = _wall_coord_near(by + bh, bx, bx + bw, h_segs, "H")
                        if c1 is not None and c2 is not None:
                            perp = (c1 + c2) / 2.0
                            xs = ([bx + bw/3.0, bx + 2*bw/3.0] if bw * _PX_TO_M > HALL_2BULB_M
                                  else [bx + bw/2.0])
                            for px in xs:
                                centers.append({"x": px, "y": perp, "label": label, "room": idx, "geometric": False, "protected": False})
                            hall_done = True
                    else:          # hol vertical -> pereți stânga/dreapta (V), becuri pe axa Y
                        c1 = _wall_coord_near(bx, by, by + bh, v_segs, "V")
                        c2 = _wall_coord_near(bx + bw, by, by + bh, v_segs, "V")
                        if c1 is not None and c2 is not None:
                            perp = (c1 + c2) / 2.0
                            ys = ([by + bh/3.0, by + 2*bh/3.0] if bh * _PX_TO_M > HALL_2BULB_M
                                  else [by + bh/2.0])
                            for py in ys:
                                centers.append({"x": perp, "y": py, "label": label, "room": idx, "geometric": False, "protected": False})
                            hall_done = True
            if not hall_done:
                # GARDĂ anti-intruziune (8c6c743) — single-bulb pe cale bbox; geometric/normal neatins.
                if not used_geometric:
                    others = [ob for j, ob in enumerate(boxes) if j != idx and ob is not None]
                    ncx, ncy, moved = _nudge_out_of_neighbors(cxc, cyc, (x, y, w, h), others, W, H)
                    if moved:
                        print("[draw_elements] bec '%s' muta din intruziune: (%.0f,%.0f)->(%.0f,%.0f)"
                              % (label, cxc, cyc, ncx, ncy))
                        cxc, cyc = ncx, ncy
                centers.append({"x": cxc, "y": cyc, "label": label, "room": idx, "geometric": used_geometric, "protected": used_geometric})

    # A — clamp final la contur: orice bec în afara conturului -> tras în interior.
    # Becurile interne (marea majoritate) -> NEATINSE (_clamp_to_contour întoarce moved=False).
    bulbs_clamped = 0
    if contour is not None:
        for c in centers:
            nx, ny, moved = _clamp_to_contour(c["x"], c["y"], contour)
            if moved:
                print("[draw_elements] bec '%s' clamp la contur: (%.0f,%.0f)->(%.0f,%.0f)"
                      % (c["label"], c["x"], c["y"], nx, ny))
                c["x"] = nx; c["y"] = ny
                bulbs_clamped += 1

    # DEDUP GLOBAL (ULTIMUL pas, prinde si dublurile din R2): becuri din camere DIFERITE prea
    # apropiate -> elimina duplicatul (pastreaza geometricul, min 1 bec/camera). Pareto-safe.
    centers, bulbs_dedup = _dedup_centers(centers, boxes, W, H)

    stats = {
        "rooms_geometric": rooms_geometric,   # E — câte camere au folosit centroid CAD
        "rooms_fallback": rooms_fallback,      # E — câte au căzut pe bbox Vision
        "bulbs_clamped": bulbs_clamped,        # A — câte becuri trase în contur
        "bbox_fixed": bbox_fixed,              # C — câte bbox-uri corectate
        "bulbs_dedup": bulbs_dedup,            # dedup — câte becuri duplicate eliminate
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


WALL_CLEAR = 14.0   # px: un bec mai aproape de atât de o linie de perete -> tras spre interior


def _nearest_wall(px, py, h_segs, v_segs):
    """(dist, axis, coord) pentru cel mai apropiat perete care ACOPERĂ punctul. axis='H'->coord=y; 'V'->x."""
    best = (1e9, None, None)
    for (x0, x1, y) in h_segs:
        if min(x0, x1) - 4 <= px <= max(x0, x1) + 4 and abs(y - py) < best[0]:
            best = (abs(y - py), "H", y)
    for (y0, y1, x) in v_segs:
        if min(y0, y1) - 4 <= py <= max(y0, y1) + 4 and abs(x - px) < best[0]:
            best = (abs(x - px), "V", x)
    return best


def _push_off_walls(centers, rboxes, h_segs, v_segs, clear=WALL_CLEAR):
    """GARD FINAL off-wall: orice bec la <clear px de un perete e împins PERPENDICULAR spre interiorul
    camerei (la 'clear' px de zid), clamp în propriul bbox. Becurile curate (în mijloc, >clear de orice
    perete) NU se ating. Întrerupătoarele NU trec pe aici (sunt desenate separat). -> nr. mutate."""
    moved = 0
    for c in centers:
        d0, axis, wc = _nearest_wall(c["x"], c["y"], h_segs, v_segs)
        if axis is None or d0 >= clear:
            continue
        b = rboxes[c["room"]] if (c["room"] is not None and c["room"] < len(rboxes)) else None
        if not b:
            continue
        bx0, by0, bx1, by1 = b[0], b[1], b[0] + b[2], b[1] + b[3]
        nx, ny = c["x"], c["y"]
        if axis == "H":
            cy = (by0 + by1) / 2.0
            ny = min(max((wc + clear) if cy >= wc else (wc - clear), by0 + 2), by1 - 2)
        else:
            cx = (bx0 + bx1) / 2.0
            nx = min(max((wc + clear) if cx >= wc else (wc - clear), bx0 + 2), bx1 - 2)
        # acceptă DOAR dacă becul ajunge mai DEPARTE de orice perete (cameră mică -> nu înrăutăți)
        dn = _nearest_wall(nx, ny, h_segs, v_segs)[0]
        if dn > d0 + 1.0:
            c["x"], c["y"] = nx, ny; moved += 1
    return moved


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
            vision_stats = {"rooms_geometric": 0, "rooms_fallback": 0,
                            "bulbs_clamped": 0, "bbox_fixed": 0, "bulbs_dedup": 0}

        # REGULA: orice cameră cu ÎNTRERUPĂTOR are ≥1 bec (întrerupătorul comandă becul).
        # Dacă o cameră servită de un întrerupător n-are bec (Baie 2/Cămară etc.) -> adaugă unul
        # (centroid geometric dacă există, altfel centru bbox), PROTEJAT (nu-l scoate dedup-ul).
        switch_bulbs = 0
        if switches and source == "vision_bbox":
            # 'have' = camere care au un bec ÎN PROPRIUL bbox (robust: prinde și becul mutat AFARĂ
            # din cameră de gardă -> camera pare goală deși are un bec cu eticheta ei).
            have = set()
            for c in centers:
                b = rboxes[c["room"]] if (c["room"] is not None and c["room"] < len(rboxes)) else None
                if b and b[0] <= c["x"] <= b[0]+b[2] and b[1] <= c["y"] <= b[1]+b[3]:
                    have.add(c["room"])
            for s in switches:
                rid = s.get("room")
                if rid is None or rid in have:
                    continue
                g = geoms[rid] if (geoms and rid < len(geoms)) else None
                if g and g.get("geometric") and g.get("centroid"):
                    bx, by = g["centroid"]["x"], g["centroid"]["y"]
                elif rid < len(rboxes) and rboxes[rid]:
                    b = rboxes[rid]; bx, by = b[0] + b[2]/2.0, b[1] + b[3]/2.0
                else:
                    continue
                centers.append({"x": bx, "y": by, "room": rid, "geometric": False, "protected": True,
                                "label": (rooms[rid].get("name", "") if rid < len(rooms) else "")})
                have.add(rid); switch_bulbs += 1
                print("[draw_elements] bec garantat (intrerupator fara bec) -> cam idx %d" % rid)

        # GARD FINAL off-wall: trage becurile căzute pe perete spre interiorul camerei (orice cauză:
        # centroid pe cameră îngustă / fallback / mutat de gardă). Întrerupătoarele NU sunt afectate.
        bulbs_offwall = 0
        if source == "vision_bbox" and walls:
            bulbs_offwall = _push_off_walls(centers, rboxes, walls[0], walls[1])

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
                             "bulbs_clamped": 0, "bbox_fixed": 0, "bulbs_dedup": 0,
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
        # rooms_found = nr. camere (o cameră poate avea 2 becuri); elements_drawn = becuri.
        rooms_found = len({c.get("room") for c in centers}) if source == "vision_bbox" else len(centers)
        return {
            "success": True,
            "source": source,
            "pdf_base64": base64.b64encode(out).decode("utf-8"),
            "filename": f"Plan_{data.get('plansa_nr','') or 'IE'}_iluminat.pdf",
            "size_bytes": len(out),
            "detected": {
                "rooms_found": rooms_found,
                "elements_drawn": len(centers),
                "rooms_geometric": vision_stats["rooms_geometric"],
                "rooms_fallback": vision_stats["rooms_fallback"],
                "bulbs_clamped": vision_stats["bulbs_clamped"],
                "bbox_fixed": vision_stats["bbox_fixed"],
                "bulbs_dedup": vision_stats["bulbs_dedup"],
                "switch_bulbs_added": switch_bulbs,
                "bulbs_offwall": bulbs_offwall,
                "switches_drawn": len(switches),
                "switches_certain": sum(1 for s in switches if s.get("certain")),
                "centers": [{"x": round(c["x"], 1), "y": round(c["y"], 1),
                             "label": c["label"][:40]} for c in centers],
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
