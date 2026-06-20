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
SELECT_AREA_RATIO = 1.5    # SELECTIE: prefera cel mai mare rect cu arie <= 1.5x aria cartus
                           # (evita over-merge-ul in vecin -> bec pe perete la camere mici inchise)
OVERLAP_REJECT = 0.40      # REGULA 2: doua camere cu overlap > 40% din cea mica = conflict
CLUSTER_RATIO = 1.38       # mediana clusterului sanatos (referinta pt. tie-break la overlap)
BBOX_CONTAIN_TOL = 12.0    # REGULA 3: toleranta MINIMA (px) la bbox-containment
# REGULA 3 relaxata calibrat: toleranta ADAPTIVA = max(TOL, CONTAIN_FRAC * latura_mica_bbox).
# Motiv: Vision poate da un bbox DEPLASAT; un centroid CORECT din pereti iese putin din el
# (ex. living casa pt: centroid real la 47px stanga de bbox-ul deplasat la dreapta -> respins fals
# cu TOL=12). Tol proportional cu camera lasa abaterea mica sa treaca, dar o EVADARE reala in vecin
# (centroidul aterizeaza in CENTRUL altei camere, la sute de px >> CONTAIN_FRAC*latura) ramane
# respinsa. Anti-evadarea intre camere e asigurata si de REGULA 2 (overlap geometric), NEATINSA.
CONTAIN_FRAC = 0.15        # fractiune din latura mica a bbox-ului tolerata la iesirea centroidului


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
        doc.close()   # RAM: documentul nu mai e folosit dupa extragerea peretilor/usilor
    except Exception as e:  # pragma: no cover - plan invalid
        try:
            doc.close()
        except Exception:
            pass
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
                # prefera dreptunghiuri pe care 2+ seed-uri sunt de acord (anti-fluke open-door)
                strong = [g for g in groups if g[6] >= 2] or groups
                # SELECTIE pe ARIA CARTUS (area_vision, stabila ~0%): cel mai MARE dreptunghi a carui
                # arie NU depaseste SELECT_AREA_RATIO x aria cartus -> evita over-merge-ul in camera
                # vecina (cauza poligonului respins de REGULA 2/3 la camere mici inchise -> bec pe
                # perete). Daca niciunul sub plafon -> cel mai mare disponibil (degradare gratioasa).
                if area_vision > 0:
                    cap = SELECT_AREA_RATIO * area_vision
                    pool = [g for g in strong if g[4] <= cap] or strong
                    best = max(pool, key=lambda g: (round(g[4], 1), g[6]))
                else:
                    best = max(strong, key=lambda g: (round(g[4], 1), -abs(g[4] - area_vision)))
                l, rr, t, b, area_geom, aspect, support = best

                cgx = round((l + rr) / 2.0, 1)
                cgy = round((t + b) / 2.0, 1)

                # walls/doors raman MEREU (prize/intrerupatoare), chiar daca centroidul e respins
                rec["wall_segments"] = _walls_in_rect(h_segs, v_segs, l, rr, t, b)
                rec["doors"] = _doors_in_rect(doors, l, rr, t, b)
                rec["area_geometric_m2"] = round(area_geom, 2)

                # REGULA 3 (relaxata calibrat) — bbox-containment ADAPTIV la marimea camerei.
                # Tol = max(TOL, CONTAIN_FRAC * latura_mica). Camerele mari tolereaza o deplasare
                # mai mare a bbox-ului Vision; o evadare reala (sute de px) ramane respinsa, iar
                # overlap-ul geometric intre camere e prins separat de REGULA 2.
                tol = max(BBOX_CONTAIN_TOL, CONTAIN_FRAC * min(bw, bh))
                inside = (bx - tol <= cgx <= bx + bw + tol and
                          by - tol <= cgy <= by + bh + tol)
                if not inside:
                    # geometric ramane False, centroid None -> fallback Vision (centru bbox)
                    rec["reason"] = "respins bbox-containment: centroid (%d,%d) iese din bbox Vision (tol %.0f)" % (
                        cgx, cgy, tol)
                else:
                    rec["geometric"] = True
                    rec["centroid"] = {"x": cgx, "y": cgy}
                    rec["reason"] = "validat geometric: aspect %.1f, arie %.1fm2, %d seed-uri de acord" % (
                        aspect, area_geom, support)
                    # temp pentru REGULA 2 (sters inainte de return)
                    rec["_rect"] = (l, rr, t, b)
                    rec["_ratio"] = (area_geom / area_vision) if area_vision > 0 else None
                    rec["_support"] = support
                    rec["_bbc"] = (cx0, cy0)   # centru bbox Vision -> dezambiguare pe pozitie (REGULA 2)
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
    # Rezolvare greedy: cat timp exista o pereche cu overlap > OVERLAP_REJECT, demoteaza perdantul.
    # DEZAMBIGUARE PE POZITIE (primar): cand 2 camere concureaza pe acelasi dreptunghi, cea al carei
    # rect e cel mai DEPARTE de propriul centru bbox e cea care a EVADAT in vecina -> pierde. Astfel
    # fiecare camera pastreaza dreptunghiul de langa ea (Dressing<->Hol central, in locuri diferite).
    # Tie-break secundar: fit pe aspect-ratio (~1.38); tertiar: mai putine seed-uri.
    def _fit(rec):
        rect = rec.get("_rect"); bbc = rec.get("_bbc")
        if rect and bbc:
            rcx = (rect[0] + rect[1]) / 2.0; rcy = (rect[2] + rect[3]) / 2.0
            dist = math.hypot(rcx - bbc[0], rcy - bbc[1])
        else:
            dist = 1e9
        ratio = rec.get("_ratio")
        base = abs(ratio - CLUSTER_RATIO) if ratio is not None else 1.0
        return (dist, base, -rec.get("_support", 0))   # mai mare = mai prost (a evadat mai departe)

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
        r.pop("_rect", None); r.pop("_ratio", None); r.pop("_support", None); r.pop("_bbc", None)

    return out


# ── ADITIV (aparataj): geometria usilor + samburi, pentru plasarea intrerupatoarelor ──
# NU se folosesc in fluxul de becuri/camere; sunt apelate separat din draw_elements.

def _bezier_point(p, t):
    """Punct pe curba bezier cubica (p = 4 fitz.Point) la parametrul t in [0,1]."""
    mt = 1.0 - t
    return (mt**3*p[0].x + 3*mt*mt*t*p[1].x + 3*mt*t*t*p[2].x + t**3*p[3].x,
            mt**3*p[0].y + 3*mt*mt*t*p[1].y + 3*mt*t*t*p[2].y + t**3*p[3].y)


def _circumcenter(a, b, c):
    """Centrul cercului prin 3 puncte (tuple). None daca sunt ~coliniare.
    Folosit ca BALAMA a usii (centrul arcului de deschidere)."""
    ax, ay = a; bx, by = b; cx, cy = c
    d = 2.0 * (ax*(by-cy) + bx*(cy-ay) + cx*(ay-by))
    if abs(d) < 1e-6:
        return None
    a2 = ax*ax+ay*ay; b2 = bx*bx+by*by; c2 = cx*cx+cy*cy
    return ((a2*(by-cy) + b2*(cy-ay) + c2*(ay-by)) / d,
            (a2*(cx-bx) + b2*(ax-cx) + c2*(bx-ax)) / d)


def _near_wall_count(pt, h_segs, v_segs, tol=9.0):
    """Cate axe de perete (V/H) trec prin punct (0/1/2). Capatul arcului 'pe perete'
    (strike/toc) -> >=1; capatul 'in camera' (deschidere) -> de obicei 0."""
    px, py = pt; n = 0
    if any(abs(x-px) <= tol and min(y0,y1)-tol <= py <= max(y0,y1)+tol for (y0,y1,x) in v_segs):
        n += 1
    if any(abs(y-py) <= tol and min(x0,x1)-tol <= px <= max(x0,x1)+tol for (x0,x1,y) in h_segs):
        n += 1
    return n


def extract_doors(page, W, H):
    """Pentru fiecare arc de usa: geometria de pozitionare aparataj.
    dict per usa: {x,y, width, hinge, strike, opentip, swing:(ux,uy normalizat catre camera), certain}.
    'strike' = capatul de pe perete (langa toc, latura manerului); 'swing' = directia spre interiorul
    camerei in care se deschide usa. certain=False cand latura nu poate fi decisa geometric (colt)."""
    h_segs, v_segs, _doors = _collect(page)
    out = []
    for d in page.get_drawings():
        if d.get("layer") != DOOR_LAYER:
            continue
        for it in d.get("items", []):
            if it[0] != "c":
                continue
            p = [it[1], it[2], it[3], it[4]]
            chord = math.hypot(p[0].x - p[3].x, p[0].y - p[3].y)
            if not (DOOR_R_MIN <= chord / math.sqrt(2.0) <= DOOR_R_MAX):
                continue
            e1 = (p[0].x, p[0].y); e2 = (p[3].x, p[3].y)
            hinge = _circumcenter(e1, _bezier_point(p, 0.5), e2)
            if hinge is None:
                continue
            on1 = _near_wall_count(e1, h_segs, v_segs)
            on2 = _near_wall_count(e2, h_segs, v_segs)
            if on1 != on2:
                strike, opentip = (e1, e2) if on1 > on2 else (e2, e1)
                certain = True
            else:
                strike, opentip = e1, e2
                certain = False
            ux, uy = opentip[0]-hinge[0], opentip[1]-hinge[1]
            ln = math.hypot(ux, uy) or 1.0
            out.append({
                "x": (e1[0]+e2[0])/2.0, "y": (e1[1]+e2[1])/2.0,
                "width": math.hypot(e1[0]-e2[0], e1[1]-e2[1]),
                "hinge": hinge, "strike": strike, "opentip": opentip,
                "swing": (ux/ln, uy/ln), "certain": certain,
            })
    return out


def extract_columns(page):
    """Samburi de rezistenta (Structural - Bearing: patrate mici pline ~25-30cm), clusterizati.
    Intoarce lista de (x,y) centre in puncte PDF — pentru evitarea coliziunii aparatajului."""
    sq = []
    for d in page.get_drawings():
        if d.get("layer") != WALL_LAYERS[1]:   # "Structural - Bearing"
            continue
        r = d.get("rect")
        if r is None:
            continue
        w = r.width; h = r.height
        if 6 <= w <= 20 and 6 <= h <= 20 and max(w, h) / max(min(w, h), 0.1) < 1.6:
            sq.append(((r.x0+r.x1)/2.0, (r.y0+r.y1)/2.0))
    cols = []; used = [False]*len(sq)
    for i in range(len(sq)):
        if used[i]:
            continue
        gx, gy, n = sq[i][0], sq[i][1], 1
        used[i] = True
        for j in range(i+1, len(sq)):
            if not used[j] and math.hypot(sq[j][0]-sq[i][0], sq[j][1]-sq[i][1]) < 18.0:
                gx += sq[j][0]; gy += sq[j][1]; n += 1; used[j] = True
        cols.append((gx/n, gy/n))
    return cols
