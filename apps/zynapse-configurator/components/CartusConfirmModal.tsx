"use client";

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { isPhasePT } from '@/lib/constants';
import { CREDIT_PRICING } from '@/components/CreditCalculator';

interface CartusData {
  titlu_proiect: string;
  beneficiar: string;
  amplasament: string;
  sef_proiect: string;
  numar_proiect: string;
  data_proiect: string;
  faza: string;
}

// Suprafețe detectate de Vision din cartuș/bilanț (Pas 1). desfasurata_mp = bază de preț (Pas 3).
export interface VisionSurfaces {
  construita_mp: number | null;
  utila_mp: number | null;
  desfasurata_mp: number | null;
  note?: string;
}

interface CartusConfirmModalProps {
  isOpen: boolean;
  initialData: CartusData;
  onConfirm: (data: CartusData) => void;
  onCancel: () => void;
  surfaces?: VisionSurfaces | null;   // suprafețe Vision (FALLBACK — folosit doar dacă lipsește textul vectorial)
  detectedConstruitaMp?: number | null;  // CONSTRUITA determinista (text vectorial /validate-plan) = bază preț
  manualSurfaceMp?: number;           // suprafața tastată de user în calculator
  balance?: number;                   // sold Z-Coins curent (profile.credits_balance)
}

export default function CartusConfirmModal({
  isOpen,
  initialData,
  onConfirm,
  onCancel,
  surfaces = null,
  detectedConstruitaMp = null,
  manualSurfaceMp = 0,
  balance = 0,
}: CartusConfirmModalProps) {
  const [data, setData] = useState<CartusData>(initialData);
  const [errors, setErrors] = useState<Partial<CartusData>>({});

  useEffect(() => {
    if (isOpen) {
      setData(initialData);
      setErrors({});
    }
  }, [isOpen, initialData]);


  if (!isOpen) return null;

  const handleChange = (field: keyof CartusData, value: string) => {
    setData(prev => ({ ...prev, [field]: value }));
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: undefined }));
    }
  };

  const validate = (): boolean => {
    const newErrors: Partial<CartusData> = {};
    const required: (keyof CartusData)[] = [
      'titlu_proiect', 'beneficiar', 'amplasament',
      'sef_proiect', 'numar_proiect', 'data_proiect', 'faza'
    ];

    required.forEach(field => {
      if (!data[field] || data[field].trim() === '') {
        newErrors[field] = 'Acest câmp este obligatoriu';
      }
    });

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleConfirm = () => {
    if (validate()) {
      onConfirm(data);
    }
  };

  // ── Cost real (preview) — ACEEAȘI regulă ca DB consume_credits: greatest(CONSTRUITA, declarat) ──
  // Baza = CONSTRUITA determinista din textul plansei (/validate-plan). Vision (surfaces) = doar fallback.
  // Serverul (/api/generate) re-extrage ACEEASI valoare determinista -> ce vezi aici = ce se debiteaza.
  const detected = detectedConstruitaMp ?? surfaces?.construita_mp ?? null;
  const surfaceBilled = Math.max(detected ?? 0, manualSurfaceMp || 0);
  const perM2 = isPhasePT(data.faza)
    ? CREDIT_PRICING.perM2.dtac + CREDIT_PRICING.perM2.pt
    : CREDIT_PRICING.perM2.dtac;
  const cost = surfaceBilled > 0 ? Math.ceil(surfaceBilled * perM2) : 0;
  const masurat = detected != null && detected >= (manualSurfaceMp || 0);   // construita din plan vs declarată
  const insufficient = cost > 0 && balance < cost;
  const fmt = (n: number) => n.toLocaleString('ro-RO', { maximumFractionDigits: 2 });
  const fazaLabel = isPhasePT(data.faza) ? 'DTAC+PT' : 'DTAC';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-gray-900 border-b border-gray-700 p-6 z-10">
          <h2 className="text-2xl font-bold text-white">
            Confirmă datele proiectului
          </h2>
          <p className="text-sm text-gray-400 mt-1">
            Verifică și editează datele extrase din planul tău. Toate câmpurile sunt obligatorii.
          </p>
        </div>

        <div className="p-6 space-y-4">
          <Field
            label="Titlu proiect"
            value={data.titlu_proiect}
            onChange={v => handleChange('titlu_proiect', v)}
            error={errors.titlu_proiect}
            placeholder="ex: CONSTRUIRE CASA D+P+M"
          />

          <Field
            label="Beneficiar"
            value={data.beneficiar}
            onChange={v => handleChange('beneficiar', v)}
            error={errors.beneficiar}
            placeholder="ex: POPESCU ION"
          />

          <Field
            label="Amplasament"
            value={data.amplasament}
            onChange={v => handleChange('amplasament', v)}
            error={errors.amplasament}
            placeholder="ex: com. X, sat Y, nr. cad. ..., jud. Z"
            multiline
          />

          <Field
            label="Șef proiect"
            value={data.sef_proiect}
            onChange={v => handleChange('sef_proiect', v)}
            error={errors.sef_proiect}
            placeholder="ex: arh. Ion Popescu"
          />

          <div className="grid grid-cols-2 gap-4">
            <Field
              label="Nr. proiect"
              value={data.numar_proiect}
              onChange={v => handleChange('numar_proiect', v)}
              error={errors.numar_proiect}
              placeholder="ex: 87/2025"
            />

            <Field
              label="Data proiect"
              value={data.data_proiect}
              onChange={v => handleChange('data_proiect', v)}
              error={errors.data_proiect}
              placeholder="MM.YYYY"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Faza <span className="text-red-400">*</span>
            </label>
            <select
              value={data.faza}
              onChange={e => handleChange('faza', e.target.value)}
              className={`w-full px-3 py-2 bg-gray-800 border rounded-lg text-white ${
                errors.faza ? 'border-red-500' : 'border-gray-700'
              }`}
            >
              <option value="">— Alege —</option>
              <option value="DTAC">DTAC</option>
              <option value="DTAC+PT">DTAC + PT</option>
              <option value="PT">PT</option>
              <option value="DE">DE (Detalii Execuție)</option>
            </select>
            {errors.faza && (
              <p className="text-red-400 text-xs mt-1">{errors.faza}</p>
            )}
          </div>
        </div>

        <div className="sticky bottom-0 bg-gray-900 border-t border-gray-700 p-6">
          {/* ── Cost real (preview) — pe ce plătești înainte de generare ── */}
          {surfaceBilled > 0 && (
            <div className="mb-4 p-3 rounded-lg" style={{
              background: insufficient ? 'rgba(226,75,74,0.08)' : 'rgba(55,138,221,0.08)',
              border: `1px solid ${insufficient ? 'rgba(226,75,74,0.30)' : 'rgba(55,138,221,0.25)'}`,
            }}>
              <div className="flex justify-between text-sm" style={{ color: '#C8CAD6' }}>
                <span>{masurat ? 'Suprafață detectată din plan' : 'Suprafață (declarată)'}</span>
                <span className="font-semibold" style={{ color: '#E2E4E9' }}>{fmt(surfaceBilled)} m²</span>
              </div>
              <div className="flex justify-between text-sm mt-1" style={{ color: '#C8CAD6' }}>
                <span>Cost <span style={{ color: '#8B8FA8' }}>({fazaLabel}, {perM2} Z-Coin/m²)</span></span>
                <span className="font-bold" style={{ color: '#5BB8F5' }}>{fmt(cost)} Z-Coins</span>
              </div>
              <div className="flex justify-between text-xs mt-1" style={{ color: '#8B8FA8' }}>
                <span>Soldul tău</span>
                <span>{fmt(balance)} Z-Coins</span>
              </div>
              {insufficient && (
                <div className="mt-2 text-xs" style={{ color: '#F09595' }}>
                  Sold insuficient: ai nevoie de {fmt(cost)} Z-Coins, ai {fmt(balance)}.
                </div>
              )}
            </div>
          )}
          <div className="flex justify-end gap-3">
            <button
              onClick={onCancel}
              className="px-5 py-2 text-gray-300 hover:text-white border border-gray-700 rounded-lg hover:bg-gray-800 transition"
            >
              Anulează
            </button>
            {insufficient ? (
              <Link
                href="/home"
                className="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition"
              >
                Cumpără credite
              </Link>
            ) : (
              <button
                onClick={handleConfirm}
                className="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition"
              >
                Confirmă și continuă
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

interface FieldProps {
  label: string;
  value: string;
  onChange: (v: string) => void;
  error?: string;
  placeholder?: string;
  multiline?: boolean;
}

function Field({ label, value, onChange, error, placeholder, multiline }: FieldProps) {
  const baseClass = `w-full px-3 py-2 bg-gray-800 border rounded-lg text-white placeholder-gray-500 ${
    error ? 'border-red-500' : 'border-gray-700'
  }`;
  return (
    <div>
      <label className="block text-sm font-medium text-gray-300 mb-1">
        {label} <span className="text-red-400">*</span>
      </label>
      {multiline ? (
        <textarea
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder={placeholder}
          rows={2}
          className={baseClass}
        />
      ) : (
        <input
          type="text"
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder={placeholder}
          className={baseClass}
        />
      )}
      {error && (
        <p className="text-red-400 text-xs mt-1">{error}</p>
      )}
    </div>
  );
}
