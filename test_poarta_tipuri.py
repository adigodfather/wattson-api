"""Poarta tipurilor de cladire: ce poate GENERA un client, si ce doar adminul.

DE CE EXISTA. Marcajul `soon` bloca la inceput doar BUTONUL din configurator; oricine trimitea
direct payload-ul la /api/generate genera orice tip. De atunci ruta are poarta ei
(`poateGeneraTip`), care citeste ACEEASI lista. Pe 26 sept Public si Industrial erau inca DESCHISE
clientilor — nimeni nu verificase tabelul intreg.

Proba nu testeaza doar functia: RULEAZA CHIAR handler-ul POST al rutei /api/generate, cu o cerere
simulata. Se inlocuiesc doar autentificarea si baza (un client fals, cu `is_admin` ales de proba)
si orice iesire in retea (backend, n8n, fetch — toate arunca, deci nimic nu pleaca spre Render sau
n8n). „Trece de poarta" inseamna ca cererea a ajuns pana la `acquire_generation_lock`, nu doar ca
n-a primit 403.

Rulare:  python test_poarta_tipuri.py
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

RADACINA = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(RADACINA, "apps", "zynapse-configurator")
rele = []

# CE E DESCHIS CLIENTILOR — decizia lui Dan, 26 sept. Spatiul comercial ramane inchis pana la
# acordul lui dupa raportul de pregatire; cand se deschide, se muta aici (o linie) si proba o cere.
DESCHISE_CLIENTILOR = {"casa_unifamiliala", "duplex"}

# ── HAMUL: transpileaza CHIAR route.ts + constants.ts + floors.ts si le leaga de stub-uri ───────
HAM = {
    "build.cjs": r'''
const ts = require("typescript"), fs = require("fs"), path = require("path");
const tr = (src, out, repl) => {
  let js = ts.transpileModule(fs.readFileSync(src, "utf8"),
    { compilerOptions: { module: ts.ModuleKind.ES2020, target: ts.ScriptTarget.ES2020 } }).outputText;
  // next/server e CommonJS: importul cu nume nu merge din ESM -> il transform in destructurare
  js = js.replace(/import \{([^}]+)\} from "next\/server";/,
                  (_m, nume) => `import __ns from "next/server.js"; const {${nume}} = __ns;`);
  for (const [a, b] of repl) js = js.split(a).join(b);
  fs.writeFileSync(path.join(__dirname, out), js);
};
tr("lib/floors.ts", "floors.mjs", []);
tr("lib/constants.ts", "constants.mjs", [['"./floors"', '"./floors.mjs"']]);
tr("app/api/generate/route.ts", "route.mjs", [
  ['"next/headers"', '"./stubs/headers.mjs"'],
  ['"@/lib/supabase"', '"./stubs/supabase.mjs"'],
  ['"@/lib/constants"', '"./constants.mjs"'],
  ['"@/lib/backend-fetch"', '"./stubs/backend-fetch.mjs"'],
  ['"@/lib/storage-pdf"', '"./stubs/storage-pdf.mjs"'],
]);
''',
    "run.mjs": r'''
import fs from "fs";
// Nicio cerere nu pleaca din proba: fetch-ul global arunca.
globalThis.fetch = async (u) => { throw new Error("STUB: fetch blocat spre " + u); };
const { POST } = await import("./route.mjs");
const { NextRequest } = (await import("next/server.js")).default;
const cazuri = JSON.parse(fs.readFileSync(new URL("./cazuri.json", import.meta.url), "utf8"));
const out = [];
for (const [tip, admin] of cazuri) {
  globalThis.__ADMIN = admin; globalThis.__URMA = [];
  const req = new NextRequest("http://localhost/api/generate", { method: "POST",
    body: JSON.stringify({ building_type: tip, surface_mp: 120, cartus_proiect: { faza: "DTAC" } }) });
  let status, err;
  try { const r = await POST(req); status = r.status; const j = await r.json().catch(() => ({})); err = j.error; }
  catch (e) { status = "EXCEPTIE"; err = String(e.message || e); }
  out.push({ tip, admin, status, err: (err || "").slice(0, 90), urma: globalThis.__URMA });
}
process.stdout.write(JSON.stringify(out));
''',
    "stubs/headers.mjs": r'''
export async function cookies() { return { get: () => undefined }; }
''',
    # Utilizator autentificat; `is_admin` vine din globalThis.__ADMIN. Orice alt acces la baza
    # intoarce un rezultat gol, iar fiecare acces se NOTEAZA — asa se vede pana unde a ajuns cererea.
    "stubs/supabase.mjs": r'''
const gol = { data: null, error: { message: "STUB: fara baza" } };
const lant = () => new Proxy(() => {}, {
  get: (_t, k) => (k === "then" ? undefined : (k === "single" || k === "maybeSingle")
    ? async () => globalThis.__ULTIMUL_TABEL === "profiles"
        ? { data: { is_admin: globalThis.__ADMIN === true, credits_balance: 100000 }, error: null } : gol
    : lant()),
  apply: () => lant(),
});
export function createServerClient() {
  return {
    auth: { getUser: async () => ({ data: { user: { id: "00000000-0000-0000-0000-00000000proba" } }, error: null }) },
    from: (t) => { globalThis.__ULTIMUL_TABEL = t; (globalThis.__URMA ||= []).push("from:" + t); return lant(); },
    rpc: async (f) => { (globalThis.__URMA ||= []).push("rpc:" + f); return gol; },
    storage: { from: () => lant() },
  };
}
''',
    "stubs/backend-fetch.mjs": r'''
export async function fetchBackend() { throw new Error("STUB: backend-ul NU se contacteaza din proba"); }
''',
    "stubs/storage-pdf.mjs": r'''
const n = async () => null;
export const mutaScalar = n, mutaIntrari = n, mutaLista = n, rezumat = () => ({});
''',
}


def v(nume, cond, det=""):
    print("  %-66s %s %s" % (nume[:66], "OK" if cond else "**ESUAT**", det if not cond else ""))
    if not cond:
        rele.append(nume)


def ruleaza(cazuri):
    """Construieste hamul INTR-UN DIRECTOR DIN APLICATIE (ca `next/server` sa se rezolve din
    node_modules), il ruleaza si il sterge."""
    d = tempfile.mkdtemp(prefix=".proba-poarta-", dir=APP)
    try:
        for nume, cod in HAM.items():
            cale = os.path.join(d, nume)
            os.makedirs(os.path.dirname(cale), exist_ok=True)
            io.open(cale, "w", encoding="utf-8", newline="").write(cod)
        io.open(os.path.join(d, "cazuri.json"), "w", encoding="utf-8").write(json.dumps(cazuri))
        b = subprocess.run(["node", os.path.join(d, "build.cjs")], capture_output=True, text=True, cwd=APP)
        if b.returncode != 0:
            return None, (b.stdout + b.stderr)[-400:]
        r = subprocess.run(["node", os.path.join(d, "run.mjs")], capture_output=True, cwd=APP)
        out = r.stdout.decode("utf-8", "replace")
        if not out.strip():
            return None, r.stderr.decode("utf-8", "replace")[-400:]
        return json.loads(out), ""
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    src = io.open(os.path.join(APP, "lib", "constants.ts"), encoding="utf-8").read()
    i0 = src.index("export const BUILDING_SUBTYPES")
    toate = re.findall(r'value: "([a-z_]+)"', src[i0:src.index("\n};", i0)])
    v("[0] lista de tipuri citita din constants.ts (control: sunt 16)", len(toate) == 16, str(len(toate)))

    rez, err = ruleaza([[t, a] for t in toate for a in (False, True)])
    v("[0] handler-ul real al rutei a rulat", rez is not None, err)
    for c in (rez or []):
        trecut = "rpc:acquire_generation_lock" in c["urma"]
        if c["admin"]:
            v("[admin]  %-23s trece de poarta" % c["tip"], trecut and c["status"] != 403,
              "status %s, urma %s" % (c["status"], c["urma"]))
        elif c["tip"] in DESCHISE_CLIENTILOR:
            v("[client] %-23s TRECE de poarta" % c["tip"], trecut and c["status"] != 403,
              "status %s, urma %s" % (c["status"], c["urma"]))
        else:
            v("[client] %-23s 403 LA POARTA" % c["tip"],
              c["status"] == 403 and c["urma"] == ["from:profiles"] and "disponibil" in c["err"],
              "status %s, urma %s, %s" % (c["status"], c["urma"], c["err"][:40]))

    rt = io.open(os.path.join(APP, "app", "api", "generate", "route.ts"), encoding="utf-8").read()
    v("[*] ruta citeste poarta din constants (SURSA UNICA)",
      'import { isPhasePT, poateGeneraTip } from "@/lib/constants"' in rt)
    v("[*] adminul vine din profil (baza), nu din cerere", "prof?.is_admin === true" in rt)
    i = rt.index("poateGeneraTip(String(parsed?.building_type")
    v("[*] poarta sta INAINTEA lock-ului si a n8n",
      i < rt.index("acquire_generation_lock") and i < rt.index("N8N_WEBHOOK,"))

    print()
    if rele:
        print("ESUAT: " + "; ".join(rele))
        return 1
    print("OK — clientii genereaza doar %s; restul doar adminul" % sorted(DESCHISE_CLIENTILOR))
    return 0


if __name__ == "__main__":
    sys.exit(main())
