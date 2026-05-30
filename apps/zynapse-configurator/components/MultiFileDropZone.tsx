"use client";

import { useRef, useState, useCallback } from "react";

interface MultiFileDropZoneProps {
  files: File[];
  onChange: (files: File[]) => void;
  maxFiles?: number;
}

const FLOOR_LABELS = ["Parter", "Etaj 1", "Mansardă"];

function floorLabel(idx: number): string {
  return FLOOR_LABELS[idx] || `Nivel ${idx + 1}`;
}

/**
 * Multi-upload drop zone (Epic 3.11). Adaptat la design-system-ul Zynapse
 * (inline-style, paleta dark glass) pentru consistență vizuală.
 * Ordinea fișierelor = ordinea etajelor (primul = parter).
 */
export default function MultiFileDropZone({
  files,
  onChange,
  maxFiles = 3,
}: MultiFileDropZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const addFiles = useCallback(
    (incoming: File[]) => {
      const valid = incoming.filter(
        (f) => f.type.startsWith("image/") || f.type === "application/pdf"
      );
      if (!valid.length) return;
      onChange([...files, ...valid].slice(0, maxFiles));
    },
    [files, onChange, maxFiles]
  );

  const removeAt = (idx: number) => onChange(files.filter((_, i) => i !== idx));

  const atLimit = files.length >= maxFiles;

  return (
    <div className="mb-5">
      <label
        className="block text-[12px] font-semibold tracking-wide mb-1.5"
        style={{ color: "#8B8FA8" }}
      >
        Planșe arhitectură
      </label>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          if (!atLimit) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          if (!atLimit) addFiles(Array.from(e.dataTransfer.files));
        }}
        onClick={() => !atLimit && inputRef.current?.click()}
        className="rounded-xl py-7 px-5 text-center transition-all duration-200"
        style={{
          border: `2px dashed ${dragging ? "#378ADD" : "rgba(255,255,255,0.1)"}`,
          background: dragging ? "rgba(55,138,221,0.05)" : "rgba(255,255,255,0.02)",
          cursor: atLimit ? "not-allowed" : "pointer",
          opacity: atLimit ? 0.5 : 1,
        }}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept="image/*,.pdf"
          className="hidden"
          onChange={(e) => addFiles(Array.from(e.target.files || []))}
        />
        <div className="mb-2.5">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" className="mx-auto opacity-30">
            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            <polyline points="17,8 12,3 7,8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            <line x1="12" y1="3" x2="12" y2="15" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </div>
        <div className="text-sm" style={{ color: "#8B8FA8" }}>
          {atLimit
            ? `Maxim ${maxFiles} planșe încărcate`
            : dragging
            ? "Eliberează pentru a adăuga"
            : files.length === 0
            ? "Trage planșele sau click pentru selectare"
            : `${files.length}/${maxFiles} planșe — click pentru a adăuga`}
        </div>
        <div className="text-[11px] mt-1" style={{ color: "#545870" }}>
          PDF, JPG, PNG — primul = parter, apoi etaj, mansardă
        </div>
      </div>

      {files.length > 0 && (
        <div className="mt-3 flex flex-col gap-2">
          {files.map((f, i) => (
            <div
              key={`${f.name}-${i}`}
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg"
              style={{
                background: "rgba(255,255,255,0.03)",
                border: "1px solid rgba(255,255,255,0.07)",
              }}
            >
              <span
                className="text-[11px] font-bold tracking-wide shrink-0"
                style={{ color: "#5BB8F5", minWidth: 64 }}
              >
                {floorLabel(i)}
              </span>
              <span
                className="flex-1 text-sm truncate"
                style={{ color: "#C8CAD6" }}
              >
                {f.name}
              </span>
              <span className="text-[11px] shrink-0" style={{ color: "#545870" }}>
                {(f.size / 1024 / 1024).toFixed(1)} MB
              </span>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  removeAt(i);
                }}
                className="shrink-0 text-base leading-none px-1"
                style={{ background: "none", border: "none", color: "#545870", cursor: "pointer" }}
                onMouseOver={(e) => (e.currentTarget.style.color = "#E24B4A")}
                onMouseOut={(e) => (e.currentTarget.style.color = "#545870")}
                aria-label={`Șterge ${f.name}`}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
