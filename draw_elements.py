import base64
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


def _vision_centers(rooms, W, H, geoms=None):
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
            # 2 becuri pe axa LUNGĂ a bbox-ului, re-centrate pe (cxc, cyc)
            if w * W >= h * H:
                dx = (w / 6.0) * W   # jumătatea distanței dintre pozițiile 1/3 și 2/3
                centers.append({"x": cxc - dx, "y": cyc, "label": label, "room": idx})
                centers.append({"x": cxc + dx, "y": cyc, "label": label, "room": idx})
            else:
                dy = (h / 6.0) * H
                centers.append({"x": cxc, "y": cyc - dy, "label": label, "room": idx})
                centers.append({"x": cxc, "y": cyc + dy, "label": label, "room": idx})
        else:
            # GARDĂ anti-intruziune (8c6c743) — DOAR single-bulb pe cale bbox (NU geometric/mari).
            # Camerele normale (centru în propriul bbox) NU se ating: _nudge întoarce moved=False.
            if not used_geometric:
                others = [ob for j, ob in enumerate(boxes) if j != idx and ob is not None]
                ncx, ncy, moved = _nudge_out_of_neighbors(cxc, cyc, (x, y, w, h), others, W, H)
                if moved:
                    print("[draw_elements] bec '%s' muta din intruziune: (%.0f,%.0f)->(%.0f,%.0f)"
                          % (label, cxc, cyc, ncx, ncy))
                    cxc, cyc = ncx, ncy
            centers.append({"x": cxc, "y": cyc, "label": label, "room": idx})

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

    stats = {
        "rooms_geometric": rooms_geometric,   # E — câte camere au folosit centroid CAD
        "rooms_fallback": rooms_fallback,      # E — câte au căzut pe bbox Vision
        "bulbs_clamped": bulbs_clamped,        # A — câte becuri trase în contur
        "bbox_fixed": bbox_fixed,              # C — câte bbox-uri corectate
    }
    return centers, stats


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
        if data.get("apply_geometry") and rooms:
            try:
                import geometry
                geoms = geometry.extract_room_geometry(pdf_bytes, rooms, W, H)
            except Exception:
                geoms = None

        # Cale nouă: dacă primim camere cu bbox de la Vision (fracții 0-1),
        # desenăm becurile din centrele lor — robust, independent de text/regex.
        # Altfel -> fallback la calea veche cu regex pe textul de suprafață.
        vision_centers, vision_stats = _vision_centers(rooms, W, H, geoms)
        if vision_centers:
            source = "vision_bbox"
            centers = vision_centers
        else:
            source = "text_regex"
            centers = _find_room_centers(page, W, H)
            vision_stats = {"rooms_geometric": 0, "rooms_fallback": 0,
                            "bulbs_clamped": 0, "bbox_fixed": 0}

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
                             "bulbs_clamped": 0, "bbox_fixed": 0,
                             "note": "Nicio cameră detectată. Plan nemodificat."},
            }

        # vision_bbox: cy e deja centrul camerei -> fără offset (bec în centru).
        # text_regex: cy e poziția textului "A:" -> -22 (bec deasupra textului).
        y_offset = 0 if source == "vision_bbox" else -22
        for c in centers:
            _draw_bulb(page, c["x"], c["y"], y_offset=y_offset)

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
                "centers": [{"x": round(c["x"], 1), "y": round(c["y"], 1),
                             "label": c["label"][:40]} for c in centers],
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
