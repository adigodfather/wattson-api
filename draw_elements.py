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


def _vision_centers(rooms, W, H):
    """Centre din bbox Vision (fracții 0-1) -> puncte PDF.
    rooms = listă de { name, area_m2, bbox: {x, y, w, h} } cu x,y,w,h în [0,1].
    Cameră mare (area_m2 >= ROOM_LARGE_M2; fallback = aria bbox ca proxy) -> 2 becuri
    pe axa LUNGĂ a bbox-ului (la 1/3 și 2/3); altfel 1 bec la centru. MAX 2 becuri/cameră.
    Ignoră tăcut camerele fără bbox numeric valid."""
    centers = []
    for idx, r in enumerate(rooms or []):
        bb = (r or {}).get("bbox") or {}
        try:
            x = float(bb.get("x")); y = float(bb.get("y"))
            w = float(bb.get("w")); h = float(bb.get("h"))
        except (TypeError, ValueError):
            continue
        label = str((r or {}).get("name") or "")
        # mărimea camerei: area_m2 din Vision; fallback la aria bbox (proxy la ~1:71)
        try:
            area = float((r or {}).get("area_m2") or 0)
        except (TypeError, ValueError):
            area = 0.0
        if area <= 0:
            area = (w * h) * (W * H) * _PT2_TO_M2
        if area >= ROOM_LARGE_M2:
            # 2 becuri pe axa LUNGĂ: orizontală dacă w*W >= h*H, altfel verticală
            if w * W >= h * H:
                cy = (y + h / 2.0) * H
                centers.append({"x": (x + w / 3.0) * W, "y": cy, "label": label, "room": idx})
                centers.append({"x": (x + 2.0 * w / 3.0) * W, "y": cy, "label": label, "room": idx})
            else:
                cx = (x + w / 2.0) * W
                centers.append({"x": cx, "y": (y + h / 3.0) * H, "label": label, "room": idx})
                centers.append({"x": cx, "y": (y + 2.0 * h / 3.0) * H, "label": label, "room": idx})
        else:
            centers.append({"x": (x + w / 2.0) * W, "y": (y + h / 2.0) * H, "label": label, "room": idx})
    return centers


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

        # Cale nouă: dacă primim camere cu bbox de la Vision (fracții 0-1),
        # desenăm becurile din centrele lor — robust, independent de text/regex.
        # Altfel -> fallback la calea veche cu regex pe textul de suprafață.
        vision_centers = _vision_centers(data.get("rooms"), W, H)
        if vision_centers:
            source = "vision_bbox"
            centers = vision_centers
        else:
            source = "text_regex"
            centers = _find_room_centers(page, W, H)

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
                "centers": [{"x": round(c["x"], 1), "y": round(c["y"], 1),
                             "label": c["label"][:40]} for c in centers],
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
