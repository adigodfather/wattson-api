"use client";

import { useState, useEffect } from 'react';

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
  surfaces?: VisionSurfaces | null;   // Pas 2: primit, NU afișat încă (rândul de cost = Pas 3)
}

export default function CartusConfirmModal({
  isOpen,
  initialData,
  onConfirm,
  onCancel,
  surfaces = null,
}: CartusConfirmModalProps) {
  const [data, setData] = useState<CartusData>(initialData);
  const [errors, setErrors] = useState<Partial<CartusData>>({});

  useEffect(() => {
    if (isOpen) {
      setData(initialData);
      setErrors({});
    }
  }, [isOpen, initialData]);

  // Pas 2 (temporar): confirmă că surfaces ajunge în modal. Se elimină la Pas 3 (rândul de cost).
  useEffect(() => {
    if (isOpen) console.log("[CartusModal] surfaces primite (Pas 2):", surfaces);
  }, [isOpen, surfaces]);

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

        <div className="sticky bottom-0 bg-gray-900 border-t border-gray-700 p-6 flex justify-end gap-3">
          <button
            onClick={onCancel}
            className="px-5 py-2 text-gray-300 hover:text-white border border-gray-700 rounded-lg hover:bg-gray-800 transition"
          >
            Anulează
          </button>
          <button
            onClick={handleConfirm}
            className="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition"
          >
            Confirmă și continuă
          </button>
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
