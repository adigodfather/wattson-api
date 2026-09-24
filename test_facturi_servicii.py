# -*- coding: utf-8 -*-
"""Facturarea de servicii: CUI, adresa fiscala, si IDEMPOTENTA abonamentelor.

De ce exista testul: aici se emit documente fiscale automat, la scadenta, fara ca cineva sa apese
ceva. Doua lucruri nu au voie sa cedeze:
  - o factura sa iasa de DOUA ori (nu se sterge, se storneaza);
  - un esec sa treaca tacut.
Garda de idempotenta sta in BAZA (index unic pe abonament+luna), deci se verifica pe baza reala, nu
pe rationament.

Capetele verificate:
  [A] validatorul de CUI — CUI-uri REALE trec, inventate cad, prefixul RO si lungimile;
  [B] clientul de servicii ajunge la SmartBill cu judet + localitate (lectia ZN0001) si cu
      descrierea LIBERA, nu cu „Z-Coins";
  [C] emiterea are claim atomic: un rand care nu e 'pending' se sare, fara sa cheme SmartBill;
  [D] IDEMPOTENTA pe baza REALA: a doua factura pe aceeasi luna e respinsa de index;
  [F] fluxul zilnic scrie rezultatul PE ABONAMENT (motivul esecului, nu doar un steag);
  [E] ziua de emitere 1..25, cele trei coloane de rezultat si stergerea clientului — pazite de baza.

Rulare:  python test_facturi_servicii.py
"""
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

RADACINA = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(RADACINA, "apps", "zynapse-configurator")
rele, sarite = [], []


def v(nume, cond, det=""):
    print("  %-66s %s %s" % (nume[:66], "OK" if cond else "**ESUAT**", det if not cond else ""))
    if not cond:
        rele.append(nume)


def sari(nume, motiv):
    print("  %-66s SARIT  %s" % (nume[:66], motiv[:70]))
    sarite.append(nume)


def _node(tmp, cod):
    f = os.path.join(tmp, "ruleaza.js")
    io.open(f, "w", encoding="utf-8").write(cod)
    r = subprocess.run(["node", f], capture_output=True, shell=(os.name == "nt"))
    out = r.stdout.decode("utf-8", "replace").strip()
    if not out:
        print("     node: %s" % (r.stderr.decode("utf-8", "replace")[:300] or "(fara iesire)"))
        return None
    return json.loads(out)


def parte_js():
    tmp = tempfile.mkdtemp(prefix="facserv_")
    r = subprocess.run(["npx", "tsc", os.path.join("lib", "facturiServicii.ts"),
                        os.path.join("lib", "cui.ts"), "--outDir", tmp, "--module", "commonjs",
                        "--target", "es2020", "--skipLibCheck", "--moduleResolution", "node"],
                       cwd=APP, capture_output=True, shell=(os.name == "nt"))
    fs = os.path.join(tmp, "facturiServicii.js")
    if not os.path.exists(fs):
        v("modulele se compileaza", False, (r.stdout or r.stderr).decode("utf-8", "replace")[:220])
        return
    v("modulele se compileaza", True)

    sablon = """
const cui = require(__CUI__);
const fs = require(__FS__);
const sb = require(__SB__);
process.env.SMARTBILL_USERNAME='u'; process.env.SMARTBILL_TOKEN='t'; process.env.SMARTBILL_VAT_CODE='1';
process.env.SMARTBILL_SERIES='ZN'; process.env.SMARTBILL_SERIES_SERVICII='ZS';
const out = { cui: {}, payload: null, claim: null };
for (const c of ['46403400','RO46403400','14399840','13548146','12345678','99999999','1','','abc','RO'])
  out.cui[c || '(gol)'] = { valid: cui.esteCuiValid(c), eroare: cui.eroareCui(c) };

// [B] clientul de servicii -> ce ajunge la SmartBill. `createInvoice` se opreste la retea, dar
// `buildInvoicePayload` e pur: se cheama direct, cu aceeasi forma pe care o construieste modulul.
const client = { id:'c1', denumire:'SCHRACK TECHNIK SRL', cui:'RO46403400', adresa:'Str. X 1',
                 judet:'Cluj', localitate:'Cluj-Napoca', email:'facturi@schrack.ro' };
const billing = { type:'company_custom', name:client.denumire, vatCode:client.cui,
                  address:client.adresa, county:client.judet, city:client.localitate, email:client.email };
const p = sb.buildInvoicePayload({email:client.email},
            {amount_ron:1500, credits:0, order_id:'f1'},
            {billing, seriesKind:'servicii', produs:{name:'Automatizare citire scheme'}});
out.payload = { serie:p.seriesName, city:p.client.city ?? null, county:p.client.county ?? null,
                nume:p.client.name, cif:p.client.vatCode ?? null,
                produs:p.products[0].name, pret:p.products[0].price, tva:p.products[0].taxPercentage };

// [C] claim atomic la emitere: randul nu e 'pending' -> nu se cheama SmartBill deloc
let retea = false;
global.fetch = async () => { retea = true; throw new Error('nu trebuia chemat'); };
const adminFals = { from(){ const b={op:null};
  b.update=()=>{b.op='update';return b;}; b.select=()=>b; b.eq=()=>b; b.or=()=>b;
  b.single=()=>({then:(r)=>r({data:null,error:null})});
  b.then=(r)=>r({ data: b.op==='update' ? [] : null, error:null });   // claim NU prinde randul
  return b; } };
// [F] fluxul zilnic scrie rezultatul PE ABONAMENT. Stub-ul intoarce un abonament scadent, apoi
// lasa claim-ul pe factura sa nu prinda randul -> abonamentul trebuie sa ramana cu motivul pe el.
function fluxFals(insertPica) {
  const scrieri = [];
  const admin = { from(t){ const b = { op:null };
    b.select=()=>b; b.eq=()=>b; b.lte=()=>b; b.or=()=>b;
    b.insert=(d)=>{ b.op='insert'; b.d=d; return b; };
    b.update=(d)=>{ b.op='update'; if (t==='abonamente_servicii') scrieri.push(d); return b; };
    b.single=()=>({ then:(r)=>r(insertPica ? { data:null, error:{ code:'23505' } }
                                           : { data:{ id:'f1' }, error:null }) });
    b.then=(r)=>r(b.op===null && t==='abonamente_servicii'
      ? { data:[{ id:'a1', client_id:'c1', descriere:'Mentenanta', suma_ron:100 }], error:null }
      : { data:[], error:null });      // claim-ul pe factura NU prinde randul
    return b; } };
  return { admin, scrieri };
}
(async () => {
  out.claim = await fs.emiteSiTrimite(adminFals, 'f-inexistent');
  out.claim_retea = retea;
  out.azi = fs.aziRo(new Date('2026-09-25T21:30:00Z'));
  const esec = fluxFals(false);
  out.flux_esec = await fs.ruleazaAbonamente(esec.admin, new Date('2026-09-10T08:00:00Z'));
  out.flux_esec_scrieri = esec.scrieri;
  const dubla = fluxFals(true);
  out.flux_dubla = await fs.ruleazaAbonamente(dubla.admin, new Date('2026-09-10T08:00:00Z'));
  out.flux_dubla_scrieri = dubla.scrieri;
  console.log(JSON.stringify(out));
})();
"""
    cod = (sablon.replace("__CUI__", json.dumps(os.path.join(tmp, "cui.js").replace("\\", "/")))
                 .replace("__FS__", json.dumps(fs.replace("\\", "/")))
                 .replace("__SB__", json.dumps(os.path.join(tmp, "smartbill.js").replace("\\", "/"))))
    d = _node(tmp, cod)
    if not d:
        v("scenariile ruleaza", False)
        return

    c = d["cui"]
    for bun in ("46403400", "RO46403400", "14399840", "13548146"):
        v("[A] CUI real «%s» e acceptat" % bun, c[bun]["valid"] is True, json.dumps(c[bun]))
    for rau in ("12345678", "99999999", "1", "(gol)", "abc", "RO"):
        v("[A] «%s» e respins, cu motiv" % rau, c[rau]["valid"] is False and bool(c[rau]["eroare"]),
          json.dumps(c[rau]))

    p = d["payload"]
    v("[B] factura de servicii merge pe seria de SERVICII", p["serie"] == "ZS", json.dumps(p))
    v("[B] judetul si localitatea ajung la SmartBill",
      p["city"] == "Cluj-Napoca" and p["county"] == "Cluj", json.dumps(p))
    v("[B] clientul e firma, cu CIF-ul ei", p["nume"] == "SCHRACK TECHNIK SRL" and p["cif"] == "RO46403400")
    v("[B] descrierea e cea LIBERA, nu «Z-Coins»",
      p["produs"] == "Automatizare citire scheme" and "Z-Coins" not in p["produs"])
    v("[B] suma si TVA-ul raman ca la credite (0%)", p["pret"] == 1500 and p["tva"] == 0)

    v("[C] un rand care nu e 'pending' se SARE", d["claim"]["status"] == "sarita", json.dumps(d["claim"]))
    v("[C] si NU se cheama SmartBill deloc", d["claim_retea"] is False)
    v("[C] ziua se ia pe fusul Romaniei, nu pe UTC", d["azi"]["zi"] == 26 and d["azi"]["perioada"] == "2026-09",
      json.dumps(d["azi"]))

    # [F] esecul nu se pierde: ajunge PE abonament, cu motivul, nu doar in raspunsul fluxului.
    sc = d["flux_esec_scrieri"]
    v("[F] un abonament scadent care pica e numarat", d["flux_esec"]["esuate"] == 1, json.dumps(d["flux_esec"]))
    v("[F] se scrie EXACT o data pe abonament", len(sc) == 1, json.dumps(sc))
    v("[F] scrierea are data rularii", bool(sc and sc[0].get("ultima_rulare_at")), json.dumps(sc[:1]))
    v("[F] scrierea are MOTIVUL, nu doar un steag",
      bool(sc and "pending" in str(sc[0].get("ultima_eroare"))), json.dumps(sc[:1]))
    # Deja facturat luna asta e garda care si-a facut treaba, nu un esec — abonamentul nu se
    # innegreste degeaba, si se noteaza luna acoperita.
    sd = d["flux_dubla_scrieri"]
    v("[F] «deja facturat» e SARIT, nu esuat",
      d["flux_dubla"]["sarite"] == 1 and d["flux_dubla"]["esuate"] == 0, json.dumps(d["flux_dubla"]))
    v("[F] si STERGE eroarea veche in loc s-o lase",
      bool(sd) and sd[0].get("ultima_eroare") is None and sd[0].get("ultima_perioada") == "2026-09",
      json.dumps(sd[:1]))


def parte_baza():
    """[D]+[E] Idempotenta si garzile, pe baza REALA. Randurile de proba se sterg."""
    cale = os.environ.get("ZYN_REF_DIR") or os.path.join(
        os.path.expanduser("~"), "AppData", "Local", "Temp", "claude", "C--zynapse",
        "5b519f49-43dc-4160-a968-3479d7ea863e", "scratchpad")
    if not os.path.isdir(cale):
        sari("[D] idempotenta pe baza reala", "directorul cu ref.py lipseste")
        return
    sys.path.insert(0, cale)
    try:
        import ref
    except Exception as e:
        sari("[D] idempotenta pe baza reala", str(e)[:70])
        return

    def cer(metoda, q, corp=None, prefer="return=representation"):
        h = dict(ref.A_)
        h["Content-Type"] = "application/json"
        if prefer:
            h["Prefer"] = prefer
        r = urllib.request.Request(ref.U_ + q, method=metoda,
                                   data=json.dumps(corp).encode() if corp is not None else None, headers=h)
        return json.loads(urllib.request.urlopen(r, timeout=60).read().decode() or "[]")

    marca = int(time.time())
    cid = aid = None
    try:
        cid = cer("POST", "/rest/v1/clienti_servicii", {
            "denumire": "PROBA TEST SRL", "cui": "T%d" % marca, "adresa": "Str. Probei 1",
            "judet": "Cluj", "localitate": "Cluj-Napoca", "email": "proba@exemplu.ro"})[0]["id"]
        aid = cer("POST", "/rest/v1/abonamente_servicii", {
            "client_id": cid, "descriere": "Mentenanta", "suma_ron": 100,
            "zi_emitere": 10, "data_start": "2026-09-01"})[0]["id"]

        cer("POST", "/rest/v1/facturi_servicii", {
            "client_id": cid, "abonament_id": aid, "perioada": "2026-09",
            "descriere": "Mentenanta 09", "suma_ron": 100})
        v("[D] prima factura pe luna trece", True)
        try:
            cer("POST", "/rest/v1/facturi_servicii", {
                "client_id": cid, "abonament_id": aid, "perioada": "2026-09",
                "descriere": "DUBLURA", "suma_ron": 100}, prefer="return=minimal")
            v("[D] A DOUA factura pe aceeasi luna e RESPINSA", False, "a trecut — idempotenta NU tine")
        except urllib.error.HTTPError as e:
            v("[D] A DOUA factura pe aceeasi luna e RESPINSA", e.code == 409, "HTTP %s" % e.code)
        cer("POST", "/rest/v1/facturi_servicii", {
            "client_id": cid, "abonament_id": aid, "perioada": "2026-10",
            "descriere": "Mentenanta 10", "suma_ron": 100})
        v("[D] luna urmatoare trece (indexul nu blocheaza tot)", True)
        cer("POST", "/rest/v1/facturi_servicii", {"client_id": cid, "descriere": "singulara A", "suma_ron": 1})
        cer("POST", "/rest/v1/facturi_servicii", {"client_id": cid, "descriere": "singulara B", "suma_ron": 1})
        v("[D] doua facturi SINGULARE trec amandoua", True)

        # Plafonul e 25, nu 28: 26 si 28 trebuie RESPINSE acum, 25 acceptata. Cazul cu 28 conteaza
        # dublu — pana ieri trecea, deci daca CHECK-ul nou n-ar fi fost aplicat, testul ar tace.
        for zi, ok in ((26, False), (28, False), (0, False), (25, True)):
            try:
                r = cer("POST", "/rest/v1/abonamente_servicii", {
                    "client_id": cid, "descriere": "x", "suma_ron": 1, "zi_emitere": zi,
                    "data_start": "2026-09-01"})
                if ok:
                    cer("DELETE", "/rest/v1/abonamente_servicii?id=eq." + r[0]["id"], prefer="return=minimal")
                v("[E] zi_emitere=%d %s" % (zi, "acceptata" if ok else "respinsa"), ok)
            except urllib.error.HTTPError as e:
                v("[E] zi_emitere=%d %s" % (zi, "acceptata" if ok else "respinsa"), not ok, "HTTP %s" % e.code)

        # Cele trei coloane de rezultat: EXISTA si ACCEPTA valori. Fara ele, `ruleazaAbonamente` ar
        # scrie in gol (scrierile sunt non-blocante), iar esecul n-ar aparea niciodata pe ecran.
        cer("PATCH", "/rest/v1/abonamente_servicii?id=eq." + aid, {
            "ultima_rulare_at": "2026-09-25T09:00:00Z",
            "ultima_eroare": "SmartBill: seria nu exista",
            "ultima_perioada": "2026-09"}, prefer="return=minimal")
        dus = cer("GET", "/rest/v1/abonamente_servicii"
                  "?select=ultima_rulare_at,ultima_eroare,ultima_perioada&id=eq." + aid)[0]
        v("[E] ultima_rulare_at se scrie si se citeste", bool(dus["ultima_rulare_at"]))
        v("[E] ultima_eroare pastreaza motivul intreg",
          dus["ultima_eroare"] == "SmartBill: seria nu exista", repr(dus["ultima_eroare"]))
        v("[E] ultima_perioada retine luna", dus["ultima_perioada"] == "2026-09", repr(dus["ultima_perioada"]))
        cer("PATCH", "/rest/v1/abonamente_servicii?id=eq." + aid,
            {"ultima_eroare": None}, prefer="return=minimal")
        gol = cer("GET", "/rest/v1/abonamente_servicii?select=ultima_eroare&id=eq." + aid)[0]
        v("[E] ultima_eroare se STERGE la o rulare reusita", gol["ultima_eroare"] is None)

        try:
            cer("DELETE", "/rest/v1/clienti_servicii?id=eq." + cid, prefer="return=minimal")
            v("[E] clientul cu abonamente NU se poate sterge", False, "s-a sters")
        except urllib.error.HTTPError as e:
            v("[E] clientul cu abonamente NU se poate sterge", e.code == 409, "HTTP %s" % e.code)
    except urllib.error.HTTPError as e:
        sari("[D] idempotenta pe baza reala", "pregatirea a picat: HTTP %s" % e.code)
    finally:
        if cid:
            cer("DELETE", "/rest/v1/facturi_servicii?client_id=eq." + cid, prefer="return=minimal")
            cer("DELETE", "/rest/v1/abonamente_servicii?client_id=eq." + cid, prefer="return=minimal")
            cer("DELETE", "/rest/v1/clienti_servicii?id=eq." + cid, prefer="return=minimal")
            ramas = len(cer("GET", "/rest/v1/clienti_servicii?select=id&id=eq." + cid))
            v("randurile de proba s-au sters", ramas == 0)


def main():
    parte_js()
    parte_baza()
    if rele:
        print("\n".join("ESUAT: " + x for x in rele))
    elif sarite:
        print("PARTIAL — a trecut tot ce s-a rulat, dar s-au SARIT: %s" % ", ".join(sarite))
    else:
        print("OK — CUI, adresa fiscala si idempotenta abonamentelor se poarta cum trebuie")
    return 1 if rele else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
