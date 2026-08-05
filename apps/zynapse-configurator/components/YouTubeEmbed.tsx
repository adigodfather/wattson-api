"use client";

// ─── YouTube cu încărcare LENEȘĂ ─────────────────────────────────────────────
// Un iframe YouTube montat direct aduce ~1MB de scripturi la FIECARE vizită, chiar dacă
// nimeni nu dă play — pe landing-ul public asta costă viteză (și scor SEO). Aici afișăm
// doar thumbnail-ul (o singură imagine) + un buton real; iframe-ul se creează abia la click.
// Domeniul e youtube-nocookie.com: fără cookie de tracking până când userul chiar pornește
// videoclipul (GDPR).

import { useState } from "react";

const ACCENT = "#378ADD";

export default function YouTubeEmbed({
  videoId,
  start = 0,
  title = "Videoclip de prezentare",
}: {
  videoId: string;
  start?: number;        // secunda de start (din ?t= al linkului)
  title?: string;
}) {
  const [playing, setPlaying] = useState(false);
  // maxresdefault există pentru clipul nostru (verificat); pentru orice alt id fără el,
  // onError coboară pe hqdefault (disponibil întotdeauna).
  const [thumb, setThumb] = useState(`https://i.ytimg.com/vi/${videoId}/maxresdefault.jpg`);

  const frame: React.CSSProperties = {
    position: "relative",
    width: "100%",
    aspectRatio: "16 / 9",          // responsive fără înălțime fixă
    borderRadius: 16,
    overflow: "hidden",
    background: "#0E1014",
    border: "1px solid rgba(255,255,255,0.09)",
    boxShadow: "0 18px 50px rgba(0,0,0,0.45)",
  };

  if (playing) {
    return (
      <div style={frame}>
        <iframe
          src={`https://www.youtube-nocookie.com/embed/${videoId}?start=${start}&autoplay=1&rel=0`}
          title={title}
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
          allowFullScreen
          style={{ position: "absolute", inset: 0, width: "100%", height: "100%", border: "none" }}
        />
      </div>
    );
  }

  return (
    <div style={frame}>
      <style>{`
        .zy-yt-btn { transition: transform .15s ease, background-color .15s ease, box-shadow .15s ease; }
        .zy-yt-play:hover .zy-yt-btn { transform: scale(1.07); box-shadow: 0 0 34px rgba(55,138,221,0.55); }
        .zy-yt-play:focus-visible { outline: 2px solid #5BB8F5; outline-offset: 3px; }
        @media (prefers-reduced-motion: reduce) { .zy-yt-btn { transition: none; } }
      `}</style>
      <button
        type="button"
        className="zy-yt-play"
        onClick={() => setPlaying(true)}
        aria-label={`Redă videoclipul: ${title}`}
        style={{
          position: "absolute", inset: 0, width: "100%", height: "100%",
          padding: 0, border: "none", background: "transparent", cursor: "pointer",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontFamily: "inherit",
        }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={thumb}
          alt=""
          aria-hidden="true"
          onError={() => setThumb(`https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`)}
          style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover" }}
        />
        {/* voal ușor: butonul rămâne lizibil pe orice cadru */}
        <span aria-hidden="true" style={{ position: "absolute", inset: 0, background: "rgba(10,11,14,0.34)" }} />
        <span
          aria-hidden="true"
          className="zy-yt-btn"
          style={{
            // scalează cu cadrul: pe mobil un disc de 76px ar acoperi un sfert din lățime
            position: "relative", width: "clamp(54px, 9vw, 76px)", height: "clamp(54px, 9vw, 76px)",
            borderRadius: "50%",
            background: `linear-gradient(135deg, ${ACCENT}, #5BB8F5)`,
            display: "flex", alignItems: "center", justifyContent: "center",
            boxShadow: "0 0 26px rgba(55,138,221,0.4)",
          }}
        >
          {/* triunghi play, ușor decalat la dreapta pentru echilibru optic */}
          <svg viewBox="0 0 24 24" width="38%" height="38%" style={{ marginLeft: "9%", display: "block" }}>
            <path d="M4 2 L21 12 L4 22 Z" fill="#fff" />
          </svg>
        </span>
      </button>
    </div>
  );
}
