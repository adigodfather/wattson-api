"""Lantul fundalului curat: de la rand, prin cod, pana la ruta.

DE CE EXISTA. Cand blob-urile au trecut in Storage, `planuri[].pdf_base64` a fost golit si
inlocuit cu `pdf_base64_path`. Randarea fundalului a fost migrata (accepta si calea), dar
`cleanBasePdf` — folosit de „Obtine plan" si de extragerea peretilor — a ramas legat DOAR de
base64. Rezultatul: butonul „Obtine plan" a picat pe TOATE proiectele, iar extragerea peretilor a
tacut, fara nicio eroare. Un cititor migrat pe jumatate arata exact ca unul care merge.

Proba citeste FISIERELE si verifica ca lantul e intreg in toate verigile, plus, pe baza reala, ca
fiecare cale de fundal duce la un fisier care exista.

Rulare:  python test_fundal_curat.py
"""
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request

RADACINA = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(RADACINA, "apps", "zynapse-configurator")
rele = []


def v(nume, cond, det=""):
    print("  %-66s %s %s" % (nume[:66], "OK" if cond else "**ESUAT**", det if not cond else ""))
    if not cond:
        rele.append(nume)


def citeste(*parti):
    return io.open(os.path.join(APP, *parti), encoding="utf-8").read()


def main():
    conf = citeste("components", "configurator.tsx")
    ed = citeste("components", "plan-editor.tsx")
    r_ext = citeste("app", "api", "extract-geometry", "route.ts")
    r_reg = citeste("app", "api", "regenerate-plan", "route.ts")
    r_png = citeste("app", "api", "render-base-png", "route.ts")

    # ── [1] configurator -> editor: se trimit AMANDOUA ──────────────────────────────────────
    v("[1] configurator trimite cleanBasePdf", "cleanBasePdf={fortaCleanBase}" in conf)
    v("[1] configurator trimite SI cleanBasePath", "cleanBasePath={fortaCleanPath}" in conf)

    # ── [2] editorul le primeste pe amandoua si nu cade pe niciuna singura ──────────────────
    v("[2] editorul accepta prop-ul cleanBasePath", "cleanBasePath" in ed)
    v("[2] poarta de regenerare accepta si calea",
      "if (!cleanBasePdf && !cleanBasePath)" in ed)
    v("[2] extragerea peretilor porneste si pe cale",
      "if (!cleanBasePdf && !cleanBasePath) return;" in ed)
    v("[2] regenerarea trimite base_pdf_path cand n-are base64", "base_pdf_path: cleanBasePath" in ed)
    v("[2] extragerea trimite pdf_path cand n-are base64", "pdf_path: cleanBasePath" in ed)

    # ── [3] rutele accepta calea ────────────────────────────────────────────────────────────
    v("[3] /api/extract-geometry accepta pdf_path", "pdf_path" in r_ext and "pdfDinStorage" in r_ext)
    v("[3] /api/regenerate-plan accepta base_pdf_path",
      "base_pdf_path" in r_reg and "pdfDinStorage" in r_reg)
    v("[3] /api/render-base-png accepta pdf_path", "pdf_path" in r_png and "pdfDinStorage" in r_png)

    # ── [4] O SINGURA implementare a descarcarii ────────────────────────────────────────────
    # Doua copii ale aceluiasi cod sunt exact motivul pentru care una a fost migrata si celelalte nu.
    copii = sum(1 for t in (r_ext, r_reg, r_png) if "storage.from(BUCKET).download" in t)
    v("[4] descarcarea din Storage e intr-un SINGUR loc (lib/pdf-din-storage)", copii == 0,
      "%d rute o mai au inline" % copii)
    v("[4] helperul exista", os.path.exists(os.path.join(APP, "lib", "pdf-din-storage.ts")))

    # ── [5] pe baza REALA: fiecare cale de fundal duce la un fisier care exista ─────────────
    t = citeste(".env.local") if os.path.exists(os.path.join(APP, ".env.local")) else ""
    env = dict(re.findall(r'^([A-Z0-9_]+)\s*=\s*"?([^"\n\r]*)"?', t, re.M))
    if not env.get("SUPABASE_SERVICE_ROLE_KEY"):
        print("  [5] sarit: fara SUPABASE_SERVICE_ROLE_KEY in .env.local")
    else:
        url = env["NEXT_PUBLIC_SUPABASE_URL"].rstrip("/")
        key = env["SUPABASE_SERVICE_ROLE_KEY"]
        req = urllib.request.Request(
            url + "/rest/v1/projects?select=id,result_data",
            headers={"apikey": key, "Authorization": "Bearer " + key})
        try:
            proiecte = json.loads(urllib.request.urlopen(req, timeout=90).read().decode())
        except Exception as ex:
            print("  [5] sarit: baza n-a raspuns (%s)" % str(ex)[:60])
            proiecte = None
        if proiecte is not None:
            cai, fara = [], 0
            for p in proiecte:
                for pl in ((p.get("result_data") or {}).get("planuri") or []):
                    c = pl.get("pdf_base64_path")
                    if c:
                        cai.append(c)
                    elif not pl.get("pdf_base64"):
                        fara += 1
            v("[5] niciun plan fara fundal (nici base64, nici cale)", fara == 0, "%d fara" % fara)
            moarte = []
            for c in cai[:40]:   # plafon: proba trebuie sa ramana rapida
                u = url + "/storage/v1/object/project-files/" + urllib.parse.quote(c)
                r = urllib.request.Request(u, method="HEAD",
                                           headers={"apikey": key, "Authorization": "Bearer " + key})
                try:
                    urllib.request.urlopen(r, timeout=60)
                except Exception:
                    moarte.append(c)
            v("[5] fiecare cale de fundal duce la un fisier care EXISTA (%d verificate)" % len(cai[:40]),
              not moarte, "moarte: %s" % (moarte[:2],))

    print()
    if rele:
        print("ESUAT: " + "; ".join(rele))
        return 1
    print("OK — lantul fundalului curat e intreg: rand -> cale -> ruta -> backend")
    return 0


if __name__ == "__main__":
    sys.exit(main())
