"""Niciun hook dupa un return timpuriu in PlanEditor (React #310).

DE CE EXISTA. Pachetul 3 a pus doua `useMemo` DUPA doua return-uri timpurii (spinner-ul cat se
incarca fundalul, mesajul cand lipseste). La o plansa mare, prima randare iesea pe spinner (71 de
hook-uri), a doua trecea mai departe (72) -> „Rendered more hooks than during the previous render",
si editorul crapa pe tot ecranul. Casa mica mergea, fiindca isi randa fundalul destul de repede cat
sa sara peste spinner — deci defectul arata ca depinde de DATE, desi era pur de ordine.

Verificarea de atunci a fost un `grep` pe indentare fixa (`^  return `), care a ratat return-urile
aflate intr-un `if { }`, pe 4 spatii. Proba asta citeste componenta cu COMPILATORUL TypeScript si
ia in seama doar return-urile si hook-urile al caror cel mai apropiat stramos-functie e chiar
componenta — nu un callback, nu un efect, nu un handler.

Rulare:  python test_hooks_ordine.py
"""
import io
import json
import os
import subprocess
import sys
import tempfile

RADACINA = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(RADACINA, "apps", "zynapse-configurator")
rele = []

SCANER = r"""
const ts = require(process.argv[2] + "/node_modules/typescript");
const fs = require("fs");
const file = process.argv[3], comp = process.argv[4];
const src = ts.createSourceFile(file, fs.readFileSync(file, "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
const line = (n) => src.getLineAndCharacterOfPosition(n.getStart()).line + 1;
const isFn = (n) => ts.isFunctionDeclaration(n) || ts.isFunctionExpression(n) || ts.isArrowFunction(n) || ts.isMethodDeclaration(n);
let c = null;
ts.forEachChild(src, function f(n) {
  if (ts.isFunctionDeclaration(n) && n.name && n.name.text === comp) c = n;
  ts.forEachChild(n, f);
});
if (!c) { process.stdout.write(JSON.stringify({ gasit: false })); process.exit(0); }
const returns = [], hooks = [];
function walk(n, owner) {
  const own = isFn(n) ? n : owner;
  if (own === c) {
    if (ts.isReturnStatement(n)) returns.push(line(n));
    if (ts.isCallExpression(n) && ts.isIdentifier(n.expression) && /^use[A-Z]/.test(n.expression.text))
      hooks.push({ l: line(n), nume: n.expression.text });
  }
  ts.forEachChild(n, (x) => walk(x, own));
}
ts.forEachChild(c.body, (x) => walk(x, c));
process.stdout.write(JSON.stringify({ gasit: true, returns, hooks }));
"""


def v(nume, cond, det=""):
    print("  %-66s %s %s" % (nume[:66], "OK" if cond else "**ESUAT**", det if not cond else ""))
    if not cond:
        rele.append(nume)


def scaneaza(fisier, componenta):
    lucru = tempfile.mkdtemp(prefix="hooks_")
    try:
        js = os.path.join(lucru, "scan.cjs")
        io.open(js, "w", encoding="utf-8").write(SCANER)
        r = subprocess.run(["node", js, APP, fisier, componenta], capture_output=True, text=True,
                           shell=(os.name == "nt"), cwd=APP)
        return json.loads(r.stdout) if r.stdout.strip() else {"gasit": False, "err": r.stderr[:300]}
    finally:
        import shutil
        shutil.rmtree(lucru, ignore_errors=True)


def main():
    for fisier, comp in (("components/plan-editor.tsx", "PlanEditor"),):
        rez = scaneaza(fisier, comp)
        v("[%s] componenta a fost gasita de parser" % comp, rez.get("gasit"), rez.get("err", ""))
        if not rez.get("gasit"):
            continue
        rets, hooks = rez["returns"], rez["hooks"]
        # CONTROL: daca parserul nu vede niciun hook, proba n-ar dovedi nimic
        v("[%s] parserul vede hook-urile (control: sunt zeci)" % comp, len(hooks) > 20,
          "%d vazute" % len(hooks))
        v("[%s] parserul vede return-urile (control: cel putin cel final)" % comp, len(rets) >= 1)
        final = max(rets) if rets else 0
        timpurii = [r for r in rets if r != final]
        if timpurii:
            primul = min(timpurii)
            dupa = [h for h in hooks if h["l"] > primul]
            v("[%s] NICIUN hook dupa primul return timpuriu (linia %d)" % (comp, primul), not dupa,
              "; ".join("linia %d %s" % (h["l"], h["nume"]) for h in dupa))
        # hook-urile adaugate in pachetul 3 sunt sus, nu jos
        idx = [h["l"] for h in hooks if h["nume"] == "useMemo"]
        v("[%s] cele doua useMemo ale legaturilor sunt inaintea return-urilor" % comp,
          not timpurii or all(l < min(timpurii) for l in idx))

    print()
    if rele:
        print("ESUAT: " + "; ".join(rele))
        return 1
    print("OK — ordinea hook-urilor nu mai depinde de ce iese din return-urile timpurii")
    return 0


if __name__ == "__main__":
    sys.exit(main())
