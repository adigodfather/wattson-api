"use client";

import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/components/auth-provider";
import { createClient } from "@/lib/supabase";

// Chat AI V1.5 — widget custom (tema Zynapse), DOAR pentru useri logati.
// UX (Faza 1.5): panou TRANSPARENT (doar bulele plutesc; header + input raman carduri solide),
// bule OPACE (lizibile peste orice pagina), mesaj de bun-venit ca PRIMA bula, badge "1" pe buton
// (apare la 5s de la incarcare cat timp panoul e inchis; dispare la deschidere; REAPARE cand vine
// un raspuns cu panoul inchis) si modul BUG (raportare erori -> /api/bugs -> dashboard admin,
// recompensata MANUAL cu Z-coins de admin dupa verificare).

type Msg = { role: "user" | "assistant"; content: string };

const ACCENT = "#378ADD";
const ACCENT_L = "#5BB8F5";
const WELCOME = "Buna, sunt asistentul tau virtual, te pot ajuta si ghida pe platforma Zynapse.";
const BUG_TEXT =
  "Aceasta este sectiunea noastra dedicata pentru erori sau neconformalitati, va rugam sa ne " +
  "comunicati erorile intampinate si un operator se va ocupa de aceasta problema, veti fii " +
  "rasplatiti cu Z-coins pentru ajutorul dvs. Multumim echipa Zynapse!";

const CARD_BG = "#12141B";                      // header + input (solide, discrete)
const BUBBLE_AI = "#1A1D26";                    // bula assistant: OPACA (lizibila pe orice fundal)
const BUBBLE_USER = "#2563A8";                  // bula user: albastru OPAC

export default function ChatWidget() {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [unread, setUnread] = useState(false);
  const [mode, setMode] = useState<"chat" | "bug">("chat");
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [bugText, setBugText] = useState("");
  const [bugState, setBugState] = useState<"idle" | "sending" | "sent" | "error">("idle");
  const loadedRef = useRef(false);
  const openRef = useRef(false);
  openRef.current = open;
  const listRef = useRef<HTMLDivElement | null>(null);

  // badge "1" la 5 secunde dupa incarcare (bun-venit "necitit"), doar daca panoul e inchis
  useEffect(() => {
    if (!user) return;
    const t = setTimeout(() => { if (!openRef.current) setUnread(true); }, 5000);
    return () => clearTimeout(t);
  }, [user]);

  // istoricul din chat_messages la PRIMA deschidere (sursa de adevar, cross-device)
  useEffect(() => {
    if (!open || loadedRef.current || !user) return;
    loadedRef.current = true;
    const supabase = createClient();
    supabase
      .from("chat_messages")
      .select("role, content")
      .order("created_at", { ascending: false })
      .limit(30)
      .then(({ data }) => {
        if (data?.length) setMessages((data as Msg[]).reverse());
      });
  }, [open, user]);

  // autoscroll la mesaje noi
  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [messages, loading, open, mode]);

  if (!user) return null;   // doar useri logati

  function toggleOpen() {
    setOpen(o => {
      const next = !o;
      if (next) setUnread(false);   // deschiderea "citeste" tot
      return next;
    });
  }

  async function send() {
    const text = input.trim();
    if (!text || loading) return;
    setErr(null);
    setInput("");
    const history = messages.slice(-10);
    setMessages(prev => [...prev, { role: "user", content: text }]);
    setLoading(true);
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, history }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setErr(String(data?.error || "Eroare — încearcă din nou."));
        return;
      }
      setMessages(prev => [...prev, { role: "assistant", content: String(data?.reply || "") }]);
      if (!openRef.current) setUnread(true);   // raspuns sosit cu panoul inchis -> badge
    } catch {
      setErr("Eroare de rețea — încearcă din nou.");
    } finally {
      setLoading(false);
    }
  }

  async function sendBug() {
    const text = bugText.trim();
    if (!text || bugState === "sending") return;
    setBugState("sending");
    try {
      const res = await fetch("/api/bugs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: text }),
      });
      if (!res.ok) { setBugState("error"); return; }
      setBugText("");
      setBugState("sent");
    } catch {
      setBugState("error");
    }
  }

  const bubbleStyle = (role: Msg["role"]): React.CSSProperties => ({
    alignSelf: role === "user" ? "flex-end" : "flex-start",
    maxWidth: "85%", padding: "9px 13px", borderRadius: 12,
    fontSize: 13, lineHeight: 1.55, whiteSpace: "pre-wrap",
    background: role === "user" ? BUBBLE_USER : BUBBLE_AI,
    border: role === "user" ? "1px solid rgba(91,184,245,0.45)" : "1px solid rgba(255,255,255,0.10)",
    color: role === "user" ? "#FFFFFF" : "#D6D9E4",
    boxShadow: "0 3px 14px rgba(0,0,0,0.45)",   // bulele "plutesc" pe panoul transparent
  });

  return (
    <>
      {/* butonul flotant + badge "1" */}
      <button type="button" aria-label={open ? "Închide asistentul" : "Deschide asistentul"}
        onClick={toggleOpen}
        style={{
          position: "fixed", right: 20, bottom: 20, zIndex: 60,
          width: 52, height: 52, borderRadius: "50%", cursor: "pointer",
          background: open ? "rgba(255,255,255,0.06)" : ACCENT,
          border: open ? "1px solid rgba(255,255,255,0.14)" : `1px solid ${ACCENT}`,
          color: "#fff", fontSize: 22, lineHeight: 1,
          boxShadow: "0 4px 18px rgba(0,0,0,0.45)",
          transition: "background-color .15s ease",
        }}>
        {open ? "×" : "💬"}
        {unread && !open && (
          <span aria-hidden style={{
            position: "absolute", top: -3, right: -3, minWidth: 19, height: 19,
            borderRadius: 999, background: "#E24B4A", color: "#fff",
            fontSize: 11, fontWeight: 800, lineHeight: "19px", textAlign: "center",
            border: "2px solid #0A0B0E", padding: "0 3px",
          }}>1</span>
        )}
      </button>

      {/* panoul de chat — TRANSPARENT: doar bulele + header/input (carduri) plutesc */}
      {open && (
        <div style={{
          position: "fixed", right: 20, bottom: 84, zIndex: 60,
          width: "min(370px, calc(100vw - 32px))", height: "min(540px, calc(100vh - 120px))",
          display: "flex", flexDirection: "column", overflow: "hidden",
          background: "transparent", fontFamily: "inherit",
        }}>
          {/* header (card solid) */}
          <div style={{ padding: "10px 14px", borderRadius: 12, background: CARD_BG,
            border: "1px solid rgba(255,255,255,0.10)", boxShadow: "0 4px 16px rgba(0,0,0,0.45)",
            display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#3ECFA0" }} />
            <span style={{ fontSize: 13.5, fontWeight: 700, color: "#E2E4E9" }}>Asistent Zynapse</span>
            <button type="button" onClick={() => { setMode(m => m === "bug" ? "chat" : "bug"); setBugState("idle"); }}
              title={mode === "bug" ? "Înapoi la chat" : "Raportează o eroare"}
              style={{ marginLeft: "auto", padding: "4px 10px", borderRadius: 8, cursor: "pointer",
                fontSize: 11.5, fontWeight: 700, fontFamily: "inherit",
                background: mode === "bug" ? "rgba(226,75,74,0.18)" : "rgba(255,255,255,0.05)",
                border: mode === "bug" ? "1px solid rgba(226,75,74,0.45)" : "1px solid rgba(255,255,255,0.12)",
                color: mode === "bug" ? "#F09595" : "#C8CAD6" }}>
              ⚠️ Bug
            </button>
          </div>

          {mode === "chat" ? (
            <>
              {/* mesajele — zona transparenta, doar bulele */}
              <div ref={listRef} style={{ flex: 1, overflowY: "auto", padding: "12px 2px",
                display: "flex", flexDirection: "column", gap: 10 }}>
                {/* bun-venit: PRIMA bula assistant (sintetica, doar vizuala) */}
                {messages.length === 0 && <div style={bubbleStyle("assistant")}>{WELCOME}</div>}
                {messages.map((m, i) => (
                  <div key={i} style={bubbleStyle(m.role)}>{m.content}</div>
                ))}
                {loading && (
                  <div style={{ ...bubbleStyle("assistant"), color: "#8B8FA8" }}>Asistentul scrie…</div>
                )}
                {err && (
                  <div style={{ alignSelf: "stretch", fontSize: 12, color: "#F09595", padding: "7px 10px",
                    background: "rgba(35,12,12,0.92)", border: "1px solid rgba(214,40,40,0.4)", borderRadius: 8 }}>
                    {err}
                  </div>
                )}
              </div>

              {/* input + disclaimer (card solid) */}
              <div style={{ padding: 10, borderRadius: 12, background: CARD_BG,
                border: "1px solid rgba(255,255,255,0.10)", boxShadow: "0 4px 16px rgba(0,0,0,0.45)" }}>
                <div style={{ display: "flex", gap: 8 }}>
                  <input value={input} onChange={e => setInput(e.target.value)}
                    onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void send(); } }}
                    placeholder="Scrie o întrebare…" maxLength={2000}
                    style={{ flex: 1, padding: "9px 12px", borderRadius: 9, fontSize: 13, fontFamily: "inherit",
                      outline: "none", background: "rgba(255,255,255,0.05)",
                      border: "1px solid rgba(255,255,255,0.10)", color: "#E2E4E9" }} />
                  <button type="button" onClick={() => void send()} disabled={loading || !input.trim()}
                    style={{ padding: "9px 14px", borderRadius: 9, fontSize: 13, fontWeight: 700, fontFamily: "inherit",
                      cursor: loading || !input.trim() ? "not-allowed" : "pointer",
                      background: loading || !input.trim() ? "rgba(255,255,255,0.05)" : ACCENT,
                      border: "1px solid " + (loading || !input.trim() ? "rgba(255,255,255,0.10)" : ACCENT),
                      color: loading || !input.trim() ? "#545870" : "#fff" }}>
                    Trimite
                  </button>
                </div>
                <div style={{ fontSize: 10.5, color: "#8B8FA8", marginTop: 7, lineHeight: 1.45 }}>
                  Răspunsurile AI sunt orientative — verifică normativul în vigoare.
                </div>
              </div>
            </>
          ) : (
            /* modul BUG — raportare erori (card solid, lizibil) */
            <div style={{ flex: 1, marginTop: 10, padding: 14, borderRadius: 12, background: CARD_BG,
              border: "1px solid rgba(255,255,255,0.10)", boxShadow: "0 4px 16px rgba(0,0,0,0.45)",
              display: "flex", flexDirection: "column", gap: 10, overflowY: "auto" }}>
              <div style={{ fontSize: 12.5, color: "#C8CAD6", lineHeight: 1.6 }}>{BUG_TEXT}</div>
              <textarea value={bugText} onChange={e => setBugText(e.target.value)}
                placeholder="Descrie eroarea întâmpinată (pașii, ce ai așteptat, ce s-a întâmplat)…"
                maxLength={3000} rows={6}
                style={{ resize: "vertical", padding: "10px 12px", borderRadius: 9, fontSize: 13,
                  fontFamily: "inherit", outline: "none", background: "rgba(255,255,255,0.05)",
                  border: "1px solid rgba(255,255,255,0.10)", color: "#E2E4E9", minHeight: 110 }} />
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <button type="button" onClick={() => void sendBug()}
                  disabled={bugState === "sending" || bugText.trim().length < 10}
                  style={{ padding: "9px 16px", borderRadius: 9, fontSize: 13, fontWeight: 700, fontFamily: "inherit",
                    cursor: bugState === "sending" || bugText.trim().length < 10 ? "not-allowed" : "pointer",
                    background: bugState === "sending" || bugText.trim().length < 10 ? "rgba(255,255,255,0.05)" : ACCENT,
                    border: "1px solid " + (bugState === "sending" || bugText.trim().length < 10 ? "rgba(255,255,255,0.10)" : ACCENT),
                    color: bugState === "sending" || bugText.trim().length < 10 ? "#545870" : "#fff" }}>
                  {bugState === "sending" ? "Se trimite…" : "Trimite raportul"}
                </button>
                {bugState === "sent" && <span style={{ fontSize: 12, color: "#3ECFA0" }}>Mulțumim! Raportul a fost trimis. ✓</span>}
                {bugState === "error" && <span style={{ fontSize: 12, color: "#F09595" }}>Trimiterea a eșuat — încearcă din nou.</span>}
              </div>
            </div>
          )}
        </div>
      )}
    </>
  );
}
