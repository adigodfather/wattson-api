"use client";
import Link from "next/link";
import { useState } from "react";

export default function Nav() {
  const [open, setOpen] = useState(false);

  return (
    <nav style={{ borderBottom: "1px solid var(--border)", background: "rgba(8,12,20,0.85)", backdropFilter: "blur(12px)" }}
      className="fixed top-0 left-0 right-0 z-50">
      <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2 font-bold tracking-tight text-base">
          <span style={{ color: "var(--accent)" }}>⚡</span>
          <span style={{ color: "var(--text)" }}>ZYNAPSE</span>
        </Link>

        {/* Desktop links */}
        <div className="hidden md:flex items-center gap-6 text-sm" style={{ color: "var(--muted)" }}>
          <a href="#cum-functioneaza" className="hover:text-white transition">Cum funcționează</a>
          <a href="#features" className="hover:text-white transition">Features</a>
          <a href="#pricing" className="hover:text-white transition">Prețuri</a>
        </div>

        {/* CTA */}
        <div className="hidden md:flex items-center gap-3">
          <Link href="/app"
            className="text-sm px-4 py-2 rounded-lg font-semibold transition hover:opacity-90"
            style={{ background: "var(--accent)", color: "#000" }}>
            Încearcă gratuit
          </Link>
        </div>

        {/* Mobile burger */}
        <button className="md:hidden p-1" onClick={() => setOpen(!open)} style={{ color: "var(--muted)" }}>
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            {open ? <path d="M18 6L6 18M6 6l12 12"/> : <path d="M4 6h16M4 12h16M4 18h16"/>}
          </svg>
        </button>
      </div>

      {open && (
        <div className="md:hidden px-4 pb-4 flex flex-col gap-3 text-sm" style={{ borderTop: "1px solid var(--border)", color: "var(--muted)" }}>
          <a href="#cum-functioneaza" className="hover:text-white py-2" onClick={() => setOpen(false)}>Cum funcționează</a>
          <a href="#features" className="hover:text-white py-2" onClick={() => setOpen(false)}>Features</a>
          <a href="#pricing" className="hover:text-white py-2" onClick={() => setOpen(false)}>Prețuri</a>
          <Link href="/app" className="text-center py-2 rounded-lg font-semibold"
            style={{ background: "var(--accent)", color: "#000" }}>
            Încearcă gratuit
          </Link>
        </div>
      )}
    </nav>
  );
}
