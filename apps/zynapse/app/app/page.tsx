"use client";
import { useState, useRef, DragEvent, ChangeEvent } from "react";
import Link from "next/link";

type Phase = "DTAC" | "PT" | "";

export default function AppPage() {
  const [phase, setPhase] = useState<Phase>("");
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [projectName, setProjectName] = useState("");
  const [address, setAddress] = useState("");
  const [status, setStatus] = useState<"idle" | "uploading" | "done" | "error">("idle");
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const webhookUrl = process.env.NEXT_PUBLIC_N8N_WEBHOOK_URL || "";

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) setFile(f);
  }

  function handleFile(e: ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (f) setFile(f);
  }

  async function handleSubmit() {
    if (!file || !phase) return;
    setStatus("uploading");
    setError("");

    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("phase", phase);
      fd.append("projectName", projectName);
      fd.append("address", address);

      const res = await fetch(webhookUrl, { method: "POST", body: fd });
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      setStatus("done");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Eroare necunoscută");
      setStatus("error");
    }
  }

  const canSubmit = !!file && !!phase && status === "idle";

  return (
    <div className="min-h-screen flex flex-col" style={{ background: "var(--bg)" }}>
      {/* Top bar */}
      <header className="flex items-center justify-between px-6 py-4" style={{ borderBottom: "1px solid var(--border)" }}>
        <Link href="/" className="flex items-center gap-2 font-extrabold text-sm" style={{ color: "var(--text)" }}>
          <span style={{ color: "var(--accent)" }}>⚡</span> ZYNAPSE
        </Link>
        <span className="text-xs font-mono px-2 py-0.5 rounded" style={{ background: "#00C89611", color: "var(--accent)", border: "1px solid #00C89633" }}>
          Generator proiect electric
        </span>
      </header>

      <main className="flex-1 flex items-start justify-center px-4 py-12">
        <div className="w-full max-w-2xl">
          {status === "done" ? (
            <SuccessScreen onReset={() => { setStatus("idle"); setFile(null); setPhase(""); setProjectName(""); setAddress(""); }} />
          ) : (
            <>
              <div className="mb-8">
                <p className="text-xs font-mono uppercase tracking-widest mb-2" style={{ color: "var(--accent)" }}>Pas 1 din 3</p>
                <h1 className="text-2xl font-extrabold mb-1" style={{ color: "var(--text)" }}>Generează proiect electric</h1>
                <p className="text-sm" style={{ color: "var(--muted)" }}>Încarcă planșa, selectează faza și lasă AI-ul să lucreze.</p>
              </div>

              {/* Phase selector */}
              <div className="mb-6">
                <label className="text-xs font-mono uppercase tracking-widest mb-3 block" style={{ color: "var(--muted)" }}>
                  Tipul proiectului
                </label>
                <div className="grid grid-cols-2 gap-3">
                  {([
                    { key: "DTAC", label: "DTAC", color: "#F59E0B", desc: "Schema monofilară + memoriu tehnic", outputs: ["Schema monofilară", "Tablou electric", "Memoriu DTAC"] },
                    { key: "PT", label: "PT – Proiect Tehnic", color: "#6366F1", desc: "Planuri complete + BOM + memoriu extins", outputs: ["Plan prize + iluminat", "Schema monofilară PT", "BOM materiale", "Memoriu complet"] },
                  ] as const).map((p) => (
                    <button key={p.key} onClick={() => setPhase(p.key)}
                      className="text-left rounded-xl p-4 transition-all"
                      style={{
                        background: phase === p.key ? p.color + "15" : "var(--bg2)",
                        border: `1.5px solid ${phase === p.key ? p.color : "var(--border)"}`,
                      }}>
                      <div className="font-extrabold text-sm mb-1 tracking-wide" style={{ color: p.color }}>{p.label}</div>
                      <div className="text-xs mb-2" style={{ color: "var(--muted)" }}>{p.desc}</div>
                      {p.outputs.map((o) => (
                        <div key={o} className="text-xs flex items-center gap-1.5" style={{ color: "var(--muted2)" }}>
                          <span style={{ color: p.color }}>✓</span>{o}
                        </div>
                      ))}
                    </button>
                  ))}
                </div>
              </div>

              {/* File drop */}
              <div className="mb-6">
                <label className="text-xs font-mono uppercase tracking-widest mb-3 block" style={{ color: "var(--muted)" }}>
                  Planșă arhitecturală
                </label>
                <div
                  onClick={() => inputRef.current?.click()}
                  onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
                  onDragLeave={() => setDragging(false)}
                  onDrop={handleDrop}
                  className="rounded-xl p-8 text-center cursor-pointer transition-all"
                  style={{
                    background: dragging ? "#00C89608" : "var(--bg2)",
                    border: `2px dashed ${dragging ? "var(--accent)" : file ? "#00C896" : "var(--border)"}`,
                  }}>
                  <input ref={inputRef} type="file" accept=".dwg,.pdf,.jpg,.jpeg,.png,.webp" className="hidden" onChange={handleFile} />
                  {file ? (
                    <div>
                      <div className="text-2xl mb-2">📄</div>
                      <div className="text-sm font-bold" style={{ color: "var(--accent)" }}>{file.name}</div>
                      <div className="text-xs mt-1" style={{ color: "var(--muted)" }}>{(file.size / 1024).toFixed(0)} KB · click pentru a schimba</div>
                    </div>
                  ) : (
                    <div>
                      <div className="text-3xl mb-3">📐</div>
                      <div className="text-sm font-semibold mb-1" style={{ color: "var(--text)" }}>Trage fișierul aici sau click</div>
                      <div className="text-xs" style={{ color: "var(--muted)" }}>DWG · PDF · JPG · PNG acceptate</div>
                    </div>
                  )}
                </div>
              </div>

              {/* Optional fields */}
              <div className="grid grid-cols-2 gap-3 mb-6">
                {[
                  { label: "Denumire proiect", value: projectName, set: setProjectName, placeholder: "ex: Casa Ionescu P+1" },
                  { label: "Adresă obiectiv", value: address, set: setAddress, placeholder: "ex: Cluj-Napoca, str. Eroilor 12" },
                ].map((f) => (
                  <div key={f.label}>
                    <label className="text-xs font-mono uppercase tracking-widest mb-2 block" style={{ color: "var(--muted)" }}>
                      {f.label} <span style={{ color: "var(--muted2)" }}>(opțional)</span>
                    </label>
                    <input
                      type="text" value={f.value} onChange={(e) => f.set(e.target.value)}
                      placeholder={f.placeholder}
                      className="w-full px-3 py-2 rounded-lg text-sm outline-none transition"
                      style={{
                        background: "var(--bg2)", border: "1px solid var(--border)",
                        color: "var(--text)", fontFamily: "var(--font-geist-sans)",
                      }}
                    />
                  </div>
                ))}
              </div>

              {/* Error */}
              {status === "error" && (
                <div className="mb-4 px-4 py-3 rounded-lg text-xs" style={{ background: "#EF444411", border: "1px solid #EF444444", color: "#EF4444" }}>
                  {error}
                </div>
              )}

              {/* Submit */}
              <button
                onClick={handleSubmit}
                disabled={!canSubmit}
                className="w-full py-3.5 rounded-xl font-bold text-sm tracking-wide transition"
                style={{
                  background: canSubmit ? "linear-gradient(90deg, #00C896, #6366F1)" : "var(--bg2)",
                  color: canSubmit ? "#fff" : "var(--muted2)",
                  border: canSubmit ? "none" : "1px solid var(--border)",
                  cursor: canSubmit ? "pointer" : "not-allowed",
                  opacity: status === "uploading" ? 0.7 : 1,
                }}>
                {status === "uploading" ? "⚡ Se procesează..." : "⚡ Generează proiect"}
              </button>

              <p className="text-center text-xs mt-4" style={{ color: "var(--muted2)" }}>
                Fără cont · Fără card · Rezultat în minute
              </p>
            </>
          )}
        </div>
      </main>
    </div>
  );
}

function SuccessScreen({ onReset }: { onReset: () => void }) {
  return (
    <div className="text-center py-12">
      <div className="text-5xl mb-4">✅</div>
      <h2 className="text-2xl font-extrabold mb-2" style={{ color: "var(--text)" }}>Proiect trimis!</h2>
      <p className="text-sm mb-8" style={{ color: "var(--muted)" }}>
        Sistemul procesează planșa. Vei primi rezultatul în câteva minute.
      </p>
      <div className="rounded-xl p-6 mb-8 text-left font-mono text-xs leading-loose" style={{ background: "var(--bg2)", border: "1px solid var(--border)", color: "var(--muted)" }}>
        <div><span style={{ color: "var(--accent)" }}>✓</span> Planșă primită și validată</div>
        <div><span style={{ color: "var(--accent)" }}>✓</span> Camerele sunt detectate de AI</div>
        <div><span style={{ color: "#6366F1" }}>→</span> Calculând circuite, siguranțe, cabluri...</div>
        <div><span style={{ color: "#6366F1" }}>→</span> Generând memoriu tehnic...</div>
        <div className="mt-2 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full animate-pulse inline-block" style={{ background: "var(--accent)" }} />
          <span style={{ color: "var(--accent)" }}>Processing...</span>
        </div>
      </div>
      <button onClick={onReset} className="px-6 py-2.5 rounded-xl text-sm font-bold transition hover:opacity-80"
        style={{ border: "1px solid var(--border)", color: "var(--muted)" }}>
        ← Proiect nou
      </button>
    </div>
  );
}
