# geometry.py — Extractor geometric din pereti CAD vectoriali (PyMuPDF / fitz).
#
# IZOLAT: NU se importa in fluxul de productie (draw_elements.py / main.py / n8n).
# Pas R&D: din pereentii reali ai planului (layere OCG) scoatem, per camera:
#   - centroid geometric (pentru becuri centrate corect),
#   - segmente de perete (pentru prize, viitor),
#   - usi (arce de deschidere; pentru intrerupatoare, viitor).
#
# Hibrid + defensiv: daca geometria nu inchide o camera cu aria ~ cea Vision (±15%),
# intoarce geometric=False si consumatorul ramane pe fallback-ul Vision (bbox).

import math

import fitz  # PyMuPDF

# Layere OCG care contin pereti (confirmate pe planul real cu doc.get_ocgs()).
WALL_LAYERS = ("PERETI EXTERIORI", "Structural - Bearing")
# Arcele de usa (door swing) sunt desenate pe layerul peretilor exteriori.
DOOR_LAYER = "PERETI EXTERIORI"

# pt^2 -> m^2 la scara planului (identic cu draw_elements._PT2_TO_M2).
_PT2_TO_M2 = 6.205e-4

MIN_WALL_LEN = 15.0          # pt; segmente mai scurte = zgomot/hasuri -> ignorate
AXIS_TOL = 2.0              # pt; cat de aproape de H/V pur trebuie sa fie un segment
DOOR_R_MIN, DOOR_R_MAX = 30.0, 50.0   # raza arc usa (pt); chord ~ r*sqrt(2)
# AREA_TOL = 0.15          # (vechi) poarta "±15% vs aria Vision" — NEUTILIZATA acum (vezi FIX 2).
SPAN_SLACK = 6.0           # pt; toleranta cand verificam ca un perete acopera centrul
DOOR_EDGE_MARGIN = 26.0    # pt; cat de aproape de o latura trebuie un arc ca sa fie "usa camerei"

# FIX 1 — seed robust: grila de seed-uri in interiorul bbox (fractii pe fiecare axa, evita marginile)
SEED_FRACS = (0.2, 0.35, 0.5, 0.65, 0.8)
SEED_WALL_TOL = 8.0        # pt; un seed la <8pt de un perete = pe perete -> sarit
# FIX 2 — validare pe plauzibilitate geometrica interna (nu vs aria Vision)
MAX_ASPECT = 6.0           # raportul laturilor (max/min) admis
MIN_AREA_M2 = 2.0          # arie geometrica minima plauzibila pentru o camera reala
RECT_SAME_TOL = 10.0       # pt; doua dreptunghiuri mai apropiate de atat = acelasi (pt. support)

# BALUSTRADA — taie over-merge-ul, pastreaza clusterul sanatos (~1.38x)
MAX_AREA_RATIO = 1.8       # REGULA 1: PLAFON area_geom <= 1.8 x area_vision (NU si jos)
OVERLAP_REJECT = 0.40      # REGULA 2: doua camere cu overlap > 40% din cea mica = conflict
CLUSTER_RATIO = 1.38       # mediana clusterului sanatos (referinta pt. tie-break la overlap)


def _collect(page):
    """Extrage o singura data toate segmentele H/V de pe layerele de pereti + arcele de usa.
    h_segs: (x0, x1, y) orizontale; v_segs: (y0, y1, x) verticale; doors: (cx, cy, r)."""
    h_segs, v_segs, doors = [], [], []
    for d in page.get_drawings():
        lay = d.get("layer")
        is_wall = lay in WALL_LAYERS
        is_door = (lay == DOOR_LAYER)
        for it in d.get("items", []):
            kind = it[0]
            if kind == "l" and is_wall:
                p1, p2 = it[1], it[2]
                dx, dy = abs(p1.x - p2.x), abs(p1.y - p2.y)
                if dx > MIN_WALL_LEN and dy < AXIS_TOL:
                    h_segs.append((min(p1.x, p2.x), max(p1.x, p2.x), (p1.y + p2.y) / 2.0))
                elif dy > MIN_WALL_LEN and dx < AXIS_TOL:
                    v_segs.append((min(p1.y, p2.y), max(p1.y, p2.y), (p1.x + p2.x) / 2.0))
            elif kind == "c" and is_door:
                pts = [it[1], it[2], it[3], it[4]]
                chord = math.hypot(pts[0].x - pts[3].x, pts[0].y - pts[3].y)
                r = chord / math.sqrt(2.0)   # arc ~ sfert de cerc -> chord = r*sqrt(2)
                if DOOR_R_MIN <= r <= DOOR_R_MAX:
                    cx = sum(p.x for p in pts) / 4.0
                    cy = sum(p.y for p in pts) / 4.0
                    doors.append((cx, cy, r))
    return h_segs, v_segs, doors


MIN_WALL_LINE = 22.0   # pt; lungime utila minima a unei LINII de perete agregate (anti-zgomot)
MERGE_GAP = 14.0       # pt; uneste segmente colineare separate de goluri mici (usi/cote)


def _aggregate(segs, axis_tol=2.5):
    """Uneste segmentele colineare (acelasi x pt. V, acelasi y pt. H) intr-o LINIE de perete:
    (pos, [intervale unite pe cealalta axa], lungime_totala). Asa tratam fragmentarea CAD."""
    lines = []  # [pos, [(a0,a1),...]]
    for (a0, a1, pos) in sorted(segs, key=lambda s: s[2]):
        for L in lines:
            if abs(L[0] - pos) <= axis_tol:
                L[1].append((a0, a1))
                break
        else:
            lines.append([pos, [(a0, a1)]])
    out = []
    for pos, ivs in lines:
        ivs.sort()
        merged = []
        for a0, a1 in ivs:
            if merged and a0 <= merged[-1][1] + MERGE_GAP:
                merged[-1] = (merged[-1][0], max(merged[-1][1], a1))
            else:
                merged.append((a0, a1))
        total = sum(b - a for a, b in merged)
        out.append((pos, merged, total))
    return out


def _room_rect(cx, cy, hlines, vlines, max_reach):
    """Cel mai mic dreptunghi inchis de LINII de perete in jurul punctului (cx, cy):
    cea mai apropiata linie V stanga/dreapta si H sus/jos care acopera centrul.
    Intoarce (left, right, top, bottom) sau None pe laturile negasite."""
    left = right = top = bottom = None
    bl = br = bt = bb = max_reach
    for (pos, ivs, total) in vlines:
        if total < MIN_WALL_LINE:
            continue
        if not any(a - SPAN_SLACK <= cy <= b + SPAN_SLACK for a, b in ivs):
            continue
        if pos < cx and (cx - pos) <= bl:
            bl = cx - pos; left = pos
        elif pos > cx and (pos - cx) <= br:
            br = pos - cx; right = pos
    for (pos, ivs, total) in hlines:
        if total < MIN_WALL_LINE:
            continue
        if not any(a - SPAN_SLACK <= cx <= b + SPAN_SLACK for a, b in ivs):
            continue
        if pos < cy and (cy - pos) <= bt:
            bt = cy - pos; top = pos
        elif pos > cy and (pos - cy) <= bb:
            bb = pos - cy; bottom = pos
    return left, right, top, bottom


def _on_wall(x, y, hlines, vlines, tol=SEED_WALL_TOL):
    """True daca punctul (x,y) cade pe/langa o linie de perete (seed invalid)."""
    for (pos, ivs, total) in vlines:
        if total >= MIN_WALL_LINE and abs(pos - x) <= tol and \
                any(a - SPAN_SLACK <= y <= b + SPAN_SLACK for a, b in ivs):
            return True
    for (pos, ivs, total) in hlines:
        if total >= MIN_WALL_LINE and abs(pos - y) <= tol and \
                any(a - SPAN_SLACK <= x <= b + SPAN_SLACK for a, b in ivs):
            return True
    return False


def _walls_in_rect(h_segs, v_segs, l, r, t, b, pad=8.0):
    """Segmentele de perete (H/V) ale caror mijloc cade in dreptunghiul [l,r]x[t,b] (cu pad)."""
    out = []
    for (x0, x1, y) in h_segs:
        mx = (x0 + x1) / 2.0
        if l - pad <= mx <= r + pad and t - pad <= y <= b + pad:
            out.append({"x1": round(x0, 1), "y1": round(y, 1), "x2": round(x1, 1), "y2": round(y, 1),
                        "orientation": "H", "length": round(x1 - x0, 1)})
    for (y0, y1, x) in v_segs:
        my = (y0 + y1) / 2.0
        if l - pad <= x <= r + pad and t - pad <= my <= b + pad:
            out.append({"x1": round(x, 1), "y1": round(y0, 1), "x2": round(x, 1), "y2": round(y1, 1),
                        "orientation": "V", "length": round(y1 - y0, 1)})
    return out


def _door_side(dx, dy, l, r, t, b):
    """Latura (N/S/E/W) cea mai apropiata de arcul de usa fata de dreptunghiul camerei."""
    cand = {
        "W": abs(dx - l), "E": abs(dx - r),
        "N": abs(dy - t), "S": abs(dy - b),
    }
    side = min(cand, key=cand.get)
    return side if cand[side] <= DOOR_EDGE_MARGIN else None


def _doors_in_rect(doors, l, r, t, b):
    """Arcele de usa al caror centru cade in marginea dreptunghiului camerei, cu latura N/S/E/W."""
    out = []
    for (dxc, dyc, _r) in doors:
        if (l - DOOR_EDGE_MARGIN <= dxc <= r + DOOR_EDGE_MARGIN and
                t - DOOR_EDGE_MARGIN <= dyc <= b + DOOR_EDGE_MARGIN):
            out.append({"x": round(dxc, 1), "y": round(dyc, 1),
                        "wall": _door_side(dxc, dyc, l, r, t, b)})
    return out


def _rect_overlap_pct(a, b):
    """Procentul de suprapunere a doua dreptunghiuri (l,r,t,b), raportat la aria celui mai mic."""
    l = max(a[0], b[0]); r = min(a[1], b[1])
    t = max(a[2], b[2]); bo = min(a[3], b[3])
    if r <= l or bo <= t:
        return 0.0
    inter = (r - l) * (bo - t)
    amin = min((a[1] - a[0]) * (a[3] - a[2]), (b[1] - b[0]) * (b[3] - b[2]))
    return inter / amin if amin > 0 else 0.0


def extract_room_geometry(pdf_bytes, vision_rooms, W, H):
    """Pentru fiecare camera Vision (cu bbox 0-1) incearca centroid geometric din pereti.

    Intoarce o lista PARALELA cu vision_rooms; fiecare element:
      name, geometric(bool), centroid({x,y}|None in puncte PDF), wall_segments[],
      doors[], area_geometric_m2|None, area_vision_m2, reason.
    Defensiv: erori per-camera prinse -> geometric=False, liste goale, fara crash.
    """
    out = []

    # extragerea peretilor/usilor o facem o singura data (poate esua -> totul pe fallback)
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[0]
        h_segs, v_segs, doors = _collect(page)
        # agregam segmentele fragmentate in linii de perete (o singura data)
        hlines = _aggregate(h_segs)
        vlines = _aggregate(v_segs)
        have_geom = bool(h_segs or v_segs)
    except Exception as e:  # pragma: no cover - plan invalid
        h_segs, v_segs, doors = [], [], []
        have_geom = False
        for r in (vision_rooms or []):
            out.append({
                "name": str((r or {}).get("name") or ""), "geometric": False,
                "centroid": None, "wall_segments": [], "doors": [],
                "area_geometric_m2": None,
                "area_vision_m2": float((r or {}).get("area_m2") or 0) or 0.0,
                "reason": "PDF invalid: %s" % e,
            })
        return out

    for r in (vision_rooms or []):
        name = str((r or {}).get("name") or "")
        try:
            area_vision = float((r or {}).get("area_m2") or 0) or 0.0
        except (TypeError, ValueError):
            area_vision = 0.0

        rec = {
            "name": name, "geometric": False, "centroid": None,
            "wall_segments": [], "doors": [],
            "area_geometric_m2": None, "area_vision_m2": area_vision, "reason": "",
        }
        try:
            bb = (r or {}).get("bbox") or {}
            bx = float(bb["x"]) * W; by = float(bb["y"]) * H
            bw = float(bb["w"]) * W; bh = float(bb["h"]) * H
        except (KeyError, TypeError, ValueError):
            rec["reason"] = "bbox lipsa/invalid"
            out.append(rec)
            continue

        if not have_geom:
            rec["reason"] = "fara geometrie de pereti in PDF"
            out.append(rec)
            continue

        try:
            cx0 = bx + bw / 2.0
            cy0 = by + bh / 2.0
            # raza de cautare: generos fata de bbox (Vision poate fi larg/decalat)
            max_reach = max(bw, bh) * 1.1 + 40.0

            # REGULA 1 — PLAFON de arie vs Vision (doar limita de sus; nu respinge sub Vision)
            ceiling = MAX_AREA_RATIO * area_vision if area_vision > 0 else float("inf")

            # FIX 1 — multi-seed: grila de seed-uri in bbox; sari peste cele cazute pe perete
            cands = []   # (l, r, t, b, area_geom, aspect)
            n_over_ceiling = 0
            for fx in SEED_FRACS:
                for fy in SEED_FRACS:
                    sx = bx + fx * bw
                    sy = by + fy * bh
                    if _on_wall(sx, sy, hlines, vlines):
                        continue
                    l, rr, t, b = _room_rect(sx, sy, hlines, vlines, max_reach)
                    if None in (l, rr, t, b) or rr <= l or b <= t:
                        continue
                    w = rr - l; h = b - t
                    aspect = max(w, h) / min(w, h)
                    area_geom = w * h * _PT2_TO_M2
                    # FIX 2 — plauzibilitate geometrica INTERNA (nu vs aria Vision)
                    if aspect > MAX_ASPECT or area_geom < MIN_AREA_M2:
                        continue
                    if area_geom > ceiling:            # REGULA 1: over-merge -> aruncat
                        n_over_ceiling += 1
                        continue
                    cands.append((l, rr, t, b, area_geom, aspect))

            if cands:
                # grupeaza dreptunghiurile ~identice -> support (cate seed-uri au convers la ele)
                groups = []   # [l, r, t, b, area, aspect, support]
                for c in cands:
                    for g in groups:
                        if all(abs(c[i] - g[i]) <= RECT_SAME_TOL for i in range(4)):
                            g[6] += 1
                            break
                    else:
                        groups.append(list(c) + [1])
                # prefera dreptunghiuri pe care 2+ seed-uri sunt de acord (anti-fluke open-door);
                # alege cel mai MARE plauzibil; tie-break SOFT pe apropierea de aria Vision
                strong = [g for g in groups if g[6] >= 2] or groups
                best = max(strong, key=lambda g: (round(g[4], 1), -abs(g[4] - area_vision)))
                l, rr, t, b, area_geom, aspect, support = best

                rec["wall_segments"] = _walls_in_rect(h_segs, v_segs, l, rr, t, b)
                rec["doors"] = _doors_in_rect(doors, l, rr, t, b)
                rec["area_geometric_m2"] = round(area_geom, 2)
                rec["geometric"] = True
                rec["centroid"] = {"x": round((l + rr) / 2.0, 1), "y": round((t + b) / 2.0, 1)}
                rec["reason"] = "validat geometric: aspect %.1f, arie %.1fm2, %d seed-uri de acord" % (
                    aspect, area_geom, support)
                # temp pentru REGULA 2 (sters inainte de return)
                rec["_rect"] = (l, rr, t, b)
                rec["_ratio"] = (area_geom / area_vision) if area_vision > 0 else None
                rec["_support"] = support
            else:
                # niciun dreptunghi plauzibil sub plafon: populam walls/doors din seed-ul central
                # (DOAR daca nu e over-merge, ca sa nu lasam pereti inselatori)
                l, rr, t, b = _room_rect(cx0, cy0, hlines, vlines, max_reach)
                if None not in (l, rr, t, b) and rr > l and b > t:
                    w = rr - l; h = b - t
                    area_geom = w * h * _PT2_TO_M2
                    aspect = max(w, h) / min(w, h)
                    rec["area_geometric_m2"] = round(area_geom, 2)
                    over = area_vision > 0 and area_geom > ceiling
                    if not over:
                        rec["wall_segments"] = _walls_in_rect(h_segs, v_segs, l, rr, t, b)
                        rec["doors"] = _doors_in_rect(doors, l, rr, t, b)
                    if over:
                        rec["reason"] = "respins REGULA 1: arie %.1fm2 > %.1fx Vision (%.1fm2) - over-merge" % (
                            area_geom, MAX_AREA_RATIO, area_vision)
                    elif aspect > MAX_ASPECT:
                        rec["reason"] = "respins: aspect ratio %.1f > %.0f (fasie/colaps perete)" % (
                            aspect, MAX_ASPECT)
                    elif area_geom < MIN_AREA_M2:
                        rec["reason"] = "respins: arie %.1fm2 < %.1f (sub-spatiu/colaps)" % (
                            area_geom, MIN_AREA_M2)
                    else:
                        rec["reason"] = "respins: niciun seed valid (toate pe perete)"
                else:
                    missing = [s for s, v in zip("LRTB", (l, rr, t, b)) if v is None]
                    rec["reason"] = "open-plan / camera exterioara: fara pereti pe %s" % ",".join(missing)
        except Exception as e:  # pragma: no cover - defensiv per camera
            rec["reason"] = "eroare per camera: %s" % e

        out.append(rec)

    # ── REGULA 2 — fara suprapuneri intre camere (un dreptunghi nu poate fi doua camere) ──
    # Rezolvare greedy: cat timp exista o pereche cu overlap > OVERLAP_REJECT, demoteaza
    # perdantul (fit mai prost fata de clusterul ~1.38; tie-break: mai putine seed-uri).
    def _fit(rec):
        ratio = rec.get("_ratio")
        base = abs(ratio - CLUSTER_RATIO) if ratio is not None else 1.0
        return (base, -rec.get("_support", 0))   # mai mare = mai prost

    changed = True
    while changed:
        changed = False
        geos = [r for r in out if r.get("geometric") and r.get("_rect")]
        for i in range(len(geos)):
            for j in range(i + 1, len(geos)):
                ov = _rect_overlap_pct(geos[i]["_rect"], geos[j]["_rect"])
                if ov > OVERLAP_REJECT:
                    loser, winner = (geos[i], geos[j]) if _fit(geos[i]) >= _fit(geos[j]) else (geos[j], geos[i])
                    loser["geometric"] = False
                    loser["centroid"] = None
                    loser["wall_segments"] = []
                    loser["doors"] = []
                    loser["reason"] = "respins REGULA 2: overlap %.0f%% cu '%s', pierdut tie-break (ratio %.2f)" % (
                        ov * 100, winner["name"], loser.get("_ratio") or 0.0)
                    loser.pop("_rect", None)
                    changed = True
                    break
            if changed:
                break

    for r in out:   # curatam cheile temporare
        r.pop("_rect", None); r.pop("_ratio", None); r.pop("_support", None)

    return out
