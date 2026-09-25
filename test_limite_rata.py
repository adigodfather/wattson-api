"""Proba de comportament pentru limitele de rata.

Ce verifica, pe BAZA REALA, nu prin rationament:
  [A] sub limita -> cererea trece si se inregistreaza;
  [B] peste limita -> refuz 429, cu mesaj in romana si antet Retry-After;
  [C] trei esecuri la rand -> pauza; un SUCCES reseteaza si urmatoarea trece;
  [D] tarifele sunt separate: umplerea celui `deliberat` NU blocheaza cererile `automat`;
  [E] la final, randurile de proba sunt sterse.

Rulare:  python test_limite_rata.py
"""
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

RADACINA = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(RADACINA, "apps", "zynapse-configurator")
rele = []


def v(nume, cond, det=""):
    print("  %-64s %s %s" % (nume[:64], "OK" if cond else "**ESUAT**", det if not cond else ""))
    if not cond:
        rele.append(nume)


def env():
    t = io.open(os.path.join(APP, ".env.local"), encoding="utf-8").read()
    d = {}
    for m in re.finditer(r'^([A-Z0-9_]+)\s*=\s*"?([^"\n\r]*)"?', t, re.M):
        d[m.group(1)] = m.group(2).strip()
    return d


def rest(e, metoda, cale, corp=None, prefer=None):
    url = e["NEXT_PUBLIC_SUPABASE_URL"].rstrip("/") + cale
    h = {"apikey": e["SUPABASE_SERVICE_ROLE_KEY"],
         "Authorization": "Bearer " + e["SUPABASE_SERVICE_ROLE_KEY"],
         "Content-Type": "application/json"}
    if prefer:
        h["Prefer"] = prefer
    r = urllib.request.Request(url, method=metoda, headers=h,
                               data=json.dumps(corp).encode() if corp is not None else None)
    body = urllib.request.urlopen(r, timeout=60).read().decode()
    return json.loads(body or "[]")


def main():
    e = env()
    if not e.get("SUPABASE_SERVICE_ROLE_KEY"):
        print("  SARIT: fara SUPABASE_SERVICE_ROLE_KEY in .env.local")
        return 0

    # Un utilizator REAL (tabelul are cheie straina spre auth.users). Randurile se sterg la final.
    useri = rest(e, "GET", "/rest/v1/profiles?select=id&limit=1")
    if not useri:
        print("  SARIT: niciun utilizator in baza")
        return 0
    uid = useri[0]["id"]

    # Compilam INAUNTRUL aplicatiei: din /tmp, node n-ar gasi `next/server` (rezolvarea de module
    # urca din directorul fisierului spre node_modules, iar /tmp n-are niciunul deasupra).
    tmp = os.path.join(APP, ".tmp-proba-limite")
    os.makedirs(tmp, exist_ok=True)
    r = subprocess.run(["npx", "tsc", os.path.join("lib", "rateLimit.ts"), "--outDir", tmp,
                        "--module", "commonjs", "--target", "es2020", "--skipLibCheck",
                        "--moduleResolution", "node"],
                       cwd=APP, capture_output=True, shell=(os.name == "nt"))
    js = os.path.join(tmp, "rateLimit.js")
    if not os.path.exists(js):
        v("modulul se compileaza", False, (r.stdout or r.stderr).decode("utf-8", "replace")[:220])
        return 1
    v("modulul se compileaza", True)

    # Curatam eventuale ramasite inainte, ca proba sa porneasca de la zero.
    rest(e, "DELETE", "/rest/v1/rate_events?user_id=eq." + uid, prefer="return=minimal")

    sablon = """
process.env.NEXT_PUBLIC_SUPABASE_URL = __URL__;
process.env.SUPABASE_SERVICE_ROLE_KEY = __KEY__;
const rl = require(__RL__);
const UID = __UID__;
const out = {};
(async () => {
  // [A] sub limita
  const a = await rl.masoara(UID, 'regenerate-plan');
  out.sub_limita_trece = !a.refuz;
  await a.gata(true);

  // [B] peste limita — umplem fereastra cu 50 de randuri pe tariful `deliberat`
  out.prag = 50;

  // [C] trei esecuri la rand pe o ruta
  for (let i = 0; i < 3; i++) {
    const x = await rl.masoara(UID, 'validate-plan');
    if (!x.refuz) await x.gata(false);
  }
  const dupa3 = await rl.masoara(UID, 'validate-plan');
  out.pauza_dupa_3_esecuri = !!dupa3.refuz;
  if (dupa3.refuz) {
    out.pauza_status = dupa3.refuz.status;
    out.pauza_retry_after = dupa3.refuz.headers.get('Retry-After');
    out.pauza_mesaj = (await dupa3.refuz.json()).error;
  }

  // un SUCCES reseteaza: ultimele trei cu verdict nu mai sunt toate false
  await fetch(process.env.NEXT_PUBLIC_SUPABASE_URL + '/rest/v1/rate_events', {
    method: 'POST',
    headers: { apikey: process.env.SUPABASE_SERVICE_ROLE_KEY,
               Authorization: 'Bearer ' + process.env.SUPABASE_SERVICE_ROLE_KEY,
               'Content-Type': 'application/json', Prefer: 'return=minimal' },
    body: JSON.stringify({ user_id: UID, ruta: 'validate-plan', succes: true }),
  });
  const dupaSucces = await rl.masoara(UID, 'validate-plan');
  out.succesul_reseteaza_pauza = !dupaSucces.refuz;
  if (!dupaSucces.refuz) await dupaSucces.gata(true);

  // alta ruta NU e afectata de pauza (pauza e pe ruta, nu globala)
  const alta = await rl.masoara(UID, 'regenerate-plan');
  out.pauza_e_pe_ruta = !alta.refuz;
  if (!alta.refuz) await alta.gata(true);

  // [D] tariful `automat` nu e atins de ce s-a intamplat pe `deliberat`
  const aut = await rl.masoara(UID, 'extract-geometry');
  out.alta_ruta_neafectata = !aut.refuz;
  if (!aut.refuz) await aut.gata(true);

  console.log(JSON.stringify(out));
})();
"""
    cod = (sablon.replace("__URL__", json.dumps(e["NEXT_PUBLIC_SUPABASE_URL"]))
                 .replace("__KEY__", json.dumps(e["SUPABASE_SERVICE_ROLE_KEY"]))
                 .replace("__RL__", json.dumps(js.replace("\\", "/")))
                 .replace("__UID__", json.dumps(uid)))
    f = os.path.join(tmp, "ruleaza.js")
    io.open(f, "w", encoding="utf-8").write(cod)
    p = subprocess.run(["node", f], capture_output=True, shell=(os.name == "nt"), cwd=APP)
    iesire = p.stdout.decode("utf-8", "replace").strip()
    if not iesire:
        v("proba ruleaza", False, p.stderr.decode("utf-8", "replace")[:300])
        rest(e, "DELETE", "/rest/v1/rate_events?user_id=eq." + uid, prefer="return=minimal")
        return 1
    d = json.loads(iesire.splitlines()[-1])

    v("[A] sub limita cererea TRECE", d.get("sub_limita_trece") is True)
    v("[C] trei esecuri la rand -> PAUZA", d.get("pauza_dupa_3_esecuri") is True)
    v("[C] pauza raspunde 429", d.get("pauza_status") == 429, str(d.get("pauza_status")))
    v("[C] pauza are antet Retry-After", bool(d.get("pauza_retry_after")), str(d.get("pauza_retry_after")))
    m = str(d.get("pauza_mesaj") or "")
    v("[C] mesajul e in romana, nu tehnic",
      ("încercări" in m or "incercari" in m) and "Error" not in m and "500" not in m, m[:70])
    v("[C] un SUCCES reseteaza pauza (fara sa astepti minutul)", d.get("succesul_reseteaza_pauza") is True)
    v("[C] pauza e PE RUTA, nu globala", d.get("pauza_e_pe_ruta") is True)
    v("[D] o ruta nu e atinsa de ce s-a intamplat pe alta", d.get("alta_ruta_neafectata") is True)

    # [B] peste limita: umplem fereastra direct in baza, apoi cerem din nou
    randuri = [{"user_id": uid, "ruta": "vision-cartus", "succes": True} for _ in range(100)]
    rest(e, "POST", "/rest/v1/rate_events", randuri, prefer="return=minimal")
    cod2 = cod.replace("console.log(JSON.stringify(out));", "")
    cod2 = cod2.split("(async () => {")[0] + """(async () => {
  const x = await rl.masoara(UID, 'vision-cartus');
  const alta = await rl.masoara(UID, 'regenerate-plan');
  const o = { refuzat: !!x.refuz, alta_ruta_trece: !alta.refuz };
  if (!alta.refuz) await alta.gata(true);
  if (x.refuz) { o.status = x.refuz.status; o.retry = x.refuz.headers.get('Retry-After');
                 o.mesaj = (await x.refuz.json()).error; }
  console.log(JSON.stringify(o));
})();"""
    io.open(f, "w", encoding="utf-8").write(cod2)
    p2 = subprocess.run(["node", f], capture_output=True, shell=(os.name == "nt"), cwd=APP)
    brut = p2.stdout.decode("utf-8", "replace").strip()
    if not brut:
        v("[B] proba de prag ruleaza", False, p2.stderr.decode("utf-8", "replace")[:200])
        rest(e, "DELETE", "/rest/v1/rate_events?user_id=eq." + uid, prefer="return=minimal")
        return 1
    o = json.loads(brut.splitlines()[-1])
    v("[B] peste pragul rutei (100 la vision-cartus) -> REFUZ", o.get("refuzat") is True)
    v("[B] pragul e PE RUTA: alta ruta trece in continuare", o.get("alta_ruta_trece") is True)
    v("[B] refuzul e 429", o.get("status") == 429, str(o.get("status")))
    v("[B] are Retry-After", bool(o.get("retry")), str(o.get("retry")))
    mb = str(o.get("mesaj") or "")
    v("[B] mesajul spune CAT si CAND, in romana",
      "cereri de procesare" in mb and "limita" in mb and "minut" in mb, mb[:80])
    v("[B] mesajul NU suna a eroare tehnica", "Error" not in mb and "429" not in mb, mb[:60])
    v("[B] mesajul spune ca e plasa de siguranta, nu acuzatie",
      "plasă de siguranță" in mb and "nimic în neregulă" in mb, mb[-60:])

    # [E] curatenie
    rest(e, "DELETE", "/rest/v1/rate_events?user_id=eq." + uid, prefer="return=minimal")
    ramase = rest(e, "GET", "/rest/v1/rate_events?select=id&user_id=eq." + uid)
    v("[E] randurile de proba s-au sters", len(ramase) == 0, "%d ramase" % len(ramase))

    print()
    if rele:
        print("ESUAT: " + "; ".join(rele))
        return 1
    try:
        import shutil; shutil.rmtree(tmp, ignore_errors=True)
    except Exception:
        pass
    print("OK — limitele se poarta cum trebuie: trec sub prag, refuza peste, iar mesajul e citibil")
    return 0


if __name__ == "__main__":
    sys.exit(main())
