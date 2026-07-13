"use client";

import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/components/auth-provider";
import { createClient } from "@/lib/supabase";

// Chat AI V1 — widget custom (tema Zynapse), DOAR pentru useri logati. Buton flotant jos-dreapta ->
// panou cu istoric + input. Istoricul = chat_messages (RLS: doar ale userului; incarcat la prima
// deschidere), trimiterea = /api/chat (auth + rate limit 25/zi + forward la n8n — Faza 2).
// Stateless pe server: trimitem ultimele mesaje ca istoric in fiecare cerere.

type Msg = { role: "user" | "assistant"; content: string };

const ACCENT = "#378ADD";
const ACCENT_L = "#5BB8F5";

export default function ChatWidget() {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const loadedRef = useRef(false);
  const listRef = useRef<HTMLDivElement | null>(null);

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
  }, [messages, loading, open]);

  if (!user) return null;   // doar useri logati

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
    } catch {
      setErr("Eroare de rețea — încearcă din nou.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      {/* butonul flotant */}
      <button type="button" aria-label={open ? "Închide asistentul" : "Deschide asistentul"}
        onClick={() => setOpen(o => !o)}
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
      </button>

      {/* panoul de chat */}
      {open && (
        <div style={{
          position: "fixed", right: 20, bottom: 84, zIndex: 60,
          width: "min(370px, calc(100vw - 32px))", height: "min(540px, calc(100vh - 120px))",
          display: "flex", flexDirection: "column", overflow: "hidden",
          background: "#0E0F14", borderRadius: 14,
          border: "1px solid rgba(255,255,255,0.10)",
          boxShadow: "0 12px 40px rgba(0,0,0,0.55)",
          fontFamily: "inherit",
        }}>
          {/* header */}
          <div style={{ padding: "12px 16px", borderBottom: "1px solid rgba(255,255,255,0.07)",
            display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#3ECFA0" }} />
            <span style={{ fontSize: 13.5, fontWeight: 700, color: "#E2E4E9" }}>Asistent Zynapse</span>
            <span style={{ fontSize: 11, color: "#545870", marginLeft: "auto" }}>platformă + normative</span>
          </div>

          {/* mesajele */}
          <div ref={listRef} style={{ flex: 1, overflowY: "auto", padding: 14,
            display: "flex", flexDirection: "column", gap: 10 }}>
            {messages.length === 0 && !loading && (
              <div style={{ fontSize: 12.5, color: "#8B8FA8", lineHeight: 1.6, padding: "8px 4px" }}>
                Salut! Te pot ajuta cu <b style={{ color: "#C8CAD6" }}>platforma</b> (cum generezi,
                editorul, creditele) și cu <b style={{ color: "#C8CAD6" }}>regulile normative</b> aplicate
                de Zynapse (prize, RCCB, secțiuni de cablu). Ce te interesează?
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} style={{
                alignSelf: m.role === "user" ? "flex-end" : "flex-start",
                maxWidth: "85%", padding: "8px 12px", borderRadius: 10,
                fontSize: 13, lineHeight: 1.55, whiteSpace: "pre-wrap",
                background: m.role === "user" ? "rgba(55,138,221,0.14)" : "rgba(255,255,255,0.04)",
                border: m.role === "user" ? "1px solid rgba(55,138,221,0.35)" : "1px solid rgba(255,255,255,0.07)",
                color: m.role === "user" ? ACCENT_L : "#C8CAD6",
              }}>
                {m.content}
              </div>
            ))}
            {loading && (
              <div style={{ alignSelf: "flex-start", fontSize: 12.5, color: "#8B8FA8", padding: "6px 4px" }}>
                Asistentul scrie…
              </div>
            )}
            {err && (
              <div style={{ alignSelf: "stretch", fontSize: 12, color: "#F09595", padding: "6px 10px",
                background: "rgba(214,40,40,0.10)", border: "1px solid rgba(214,40,40,0.25)", borderRadius: 8 }}>
                {err}
              </div>
            )}
          </div>

          {/* input + disclaimer */}
          <div style={{ padding: 12, borderTop: "1px solid rgba(255,255,255,0.07)" }}>
            <div style={{ display: "flex", gap: 8 }}>
              <input value={input} onChange={e => setInput(e.target.value)}
                onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void send(); } }}
                placeholder="Scrie o întrebare…" maxLength={2000}
                style={{ flex: 1, padding: "9px 12px", borderRadius: 9, fontSize: 13, fontFamily: "inherit",
                  outline: "none", background: "rgba(255,255,255,0.04)",
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
            <div style={{ fontSize: 10.5, color: "#545870", marginTop: 7, lineHeight: 1.45 }}>
              Răspunsurile AI sunt orientative — verifică normativul în vigoare.
            </div>
          </div>
        </div>
      )}
    </>
  );
}
