'use client'

import { useEffect, useState, type ChangeEvent } from 'react'
import { createClient } from '@/lib/supabase'
import AppHeader from '@/components/AppHeader'

type Profile = {
  firma_nume: string
  firma_cui: string
  firma_reg_com: string
  firma_tel: string
  firma_email: string
  firma_adresa: string
  firma_logo_url: string
  proiectant_nume: string
  desenator_nume: string
}

const EMPTY: Profile = {
  firma_nume: '',
  firma_cui: '',
  firma_reg_com: '',
  firma_tel: '',
  firma_email: '',
  firma_adresa: '',
  firma_logo_url: '',
  proiectant_nume: '',
  desenator_nume: '',
}

const ALLOWED_TYPES = ['image/png', 'image/jpeg', 'image/svg+xml', 'image/webp']
const MAX_SIZE = 2 * 1024 * 1024 // 2 MB

export default function SettingsPage() {
  const supabase = createClient()

  const [profile, setProfile] = useState<Profile>(EMPTY)
  const [userId, setUserId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [msg, setMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      const { data: { user } } = await supabase.auth.getUser()
      if (cancelled) return
      if (!user) {
        setLoading(false)
        return
      }
      setUserId(user.id)

      const { data } = await supabase
        .from('profiles')
        .select(
          'firma_nume, firma_cui, firma_reg_com, firma_tel, firma_email, firma_adresa, firma_logo_url, proiectant_nume, desenator_nume'
        )
        .eq('id', user.id)
        .single()

      if (!cancelled && data) {
        setProfile({
          firma_nume: data.firma_nume ?? '',
          firma_cui: data.firma_cui ?? '',
          firma_reg_com: data.firma_reg_com ?? '',
          firma_tel: data.firma_tel ?? '',
          firma_email: data.firma_email ?? '',
          firma_adresa: data.firma_adresa ?? '',
          firma_logo_url: data.firma_logo_url ?? '',
          proiectant_nume: data.proiectant_nume ?? '',
          desenator_nume: data.desenator_nume ?? '',
        })
      }
      setLoading(false)
    }
    load()
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function update<K extends keyof Profile>(key: K, value: Profile[K]) {
    setProfile(p => ({ ...p, [key]: value }))
  }

  async function handleSave() {
    if (!userId) return
    setSaving(true)
    setMsg(null)

    const { error } = await supabase
      .from('profiles')
      .update(profile)
      .eq('id', userId)

    if (error) {
      setMsg({ type: 'error', text: `Eroare la salvare: ${error.message}` })
    } else {
      setMsg({ type: 'success', text: 'Datele firmei au fost salvate.' })
    }
    setSaving(false)
  }

  async function handleLogoUpload(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file || !userId) return

    if (file.size > MAX_SIZE) {
      setMsg({ type: 'error', text: 'Fișier prea mare. Maxim 2 MB.' })
      e.target.value = ''
      return
    }
    if (!ALLOWED_TYPES.includes(file.type)) {
      setMsg({ type: 'error', text: 'Format invalid. Acceptat: PNG, JPEG, SVG, WebP.' })
      e.target.value = ''
      return
    }

    setUploading(true)
    setMsg(null)

    // Remove any existing logos in the user's folder
    const { data: existing } = await supabase.storage
      .from('company-logos')
      .list(userId, { limit: 100 })
    if (existing && existing.length > 0) {
      const paths = existing.map(f => `${userId}/${f.name}`)
      await supabase.storage.from('company-logos').remove(paths)
    }

    // Upload new logo
    const ext = file.type
      .replace('image/', '')
      .replace('jpeg', 'jpg')
      .replace('svg+xml', 'svg')
    const path = `${userId}/logo.${ext}`

    const { error: uploadError } = await supabase.storage
      .from('company-logos')
      .upload(path, file, { upsert: true, cacheControl: '3600' })

    if (uploadError) {
      setMsg({ type: 'error', text: `Eroare upload: ${uploadError.message}` })
      setUploading(false)
      return
    }

    // Get public URL with cache-buster
    const { data: { publicUrl } } = supabase.storage
      .from('company-logos')
      .getPublicUrl(path)
    const finalUrl = `${publicUrl}?t=${Date.now()}`

    // Persist URL on profile
    const { error: updateError } = await supabase
      .from('profiles')
      .update({ firma_logo_url: finalUrl })
      .eq('id', userId)

    if (updateError) {
      setMsg({ type: 'error', text: `Eroare salvare URL: ${updateError.message}` })
    } else {
      setProfile(p => ({ ...p, firma_logo_url: finalUrl }))
      setMsg({ type: 'success', text: 'Logo încărcat cu succes.' })
    }
    setUploading(false)
    e.target.value = ''
  }

  async function handleLogoDelete() {
    if (!userId || !profile.firma_logo_url) return
    if (!confirm('Ștergi logo-ul firmei?')) return

    setUploading(true)
    setMsg(null)

    const { data: existing } = await supabase.storage
      .from('company-logos')
      .list(userId, { limit: 100 })
    if (existing && existing.length > 0) {
      const paths = existing.map(f => `${userId}/${f.name}`)
      await supabase.storage.from('company-logos').remove(paths)
    }

    const { error } = await supabase
      .from('profiles')
      .update({ firma_logo_url: null })
      .eq('id', userId)

    if (error) {
      setMsg({ type: 'error', text: `Eroare: ${error.message}` })
    } else {
      setProfile(p => ({ ...p, firma_logo_url: '' }))
      setMsg({ type: 'success', text: 'Logo șters.' })
    }
    setUploading(false)
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: '#0A0B0E' }}>
        <div style={{ color: '#545870' }}>Se încarcă...</div>
      </div>
    )
  }

  if (!userId) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: '#0A0B0E' }}>
        <div style={{ color: '#8B8FA8' }}>
          Trebuie să fii autentificat.{' '}
          <a href="/login" style={{ color: '#5BB8F5', textDecoration: 'underline' }}>Login</a>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen" style={{ background: '#0A0B0E' }}>
      <AppHeader />

      <div className="max-w-3xl mx-auto px-6 py-10">
        <header className="mb-8">
          <h1 className="text-2xl font-bold tracking-tight m-0" style={{ color: '#E2E4E9' }}>Setări firmă</h1>
          <p className="mt-2 m-0 text-sm" style={{ color: '#545870' }}>
            Datele de mai jos apar în cartușul fiecărei scheme generate de Zynapse.
          </p>
        </header>

        {msg && (
          <div className="mb-6 px-4 py-3 rounded-lg text-sm"
            style={{
              background: msg.type === 'success' ? 'rgba(29,158,117,0.12)' : 'rgba(226,75,74,0.10)',
              border: `1px solid ${msg.type === 'success' ? 'rgba(29,158,117,0.25)' : 'rgba(226,75,74,0.20)'}`,
              color: msg.type === 'success' ? '#3ECFA0' : '#F09595',
            }}>
            {msg.text}
          </div>
        )}

        {/* Logo */}
        <section className="rounded-xl p-6 mb-4"
          style={{ background: 'rgba(255,255,255,0.025)', border: '1px solid rgba(255,255,255,0.07)' }}>
          <h2 className="text-base font-semibold m-0 mb-1" style={{ color: '#E2E4E9' }}>Logo firmă</h2>
          <p className="text-sm mt-1 mb-4 m-0" style={{ color: '#545870' }}>PNG, JPEG, SVG sau WebP. Maxim 2 MB.</p>

          <div className="flex items-center gap-6">
            <div className="w-28 h-28 rounded-xl flex items-center justify-center overflow-hidden"
              style={{ background: 'rgba(255,255,255,0.04)', border: '2px dashed rgba(255,255,255,0.1)' }}>
              {profile.firma_logo_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={profile.firma_logo_url} alt="Logo firmă" className="max-w-full max-h-full object-contain" />
              ) : (
                <span className="text-xs text-center px-2" style={{ color: '#3A3D50' }}>Fără logo</span>
              )}
            </div>

            <div className="flex flex-col gap-2">
              <label className="inline-flex items-center justify-center px-4 py-2 rounded-lg text-sm font-medium cursor-pointer"
                style={{ background: 'rgba(55,138,221,0.15)', border: '1px solid rgba(55,138,221,0.3)', color: '#5BB8F5' }}>
                {uploading ? 'Se încarcă...' : profile.firma_logo_url ? 'Schimbă logo' : 'Încarcă logo'}
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/svg+xml,image/webp"
                  onChange={handleLogoUpload}
                  disabled={uploading}
                  className="hidden"
                />
              </label>
              {profile.firma_logo_url && (
                <button type="button" onClick={handleLogoDelete} disabled={uploading}
                  className="px-4 py-2 rounded-lg text-sm font-medium font-[inherit] cursor-pointer"
                  style={{ background: 'rgba(226,75,74,0.08)', border: '1px solid rgba(226,75,74,0.2)', color: '#F09595' }}>
                  Șterge logo
                </button>
              )}
            </div>
          </div>
        </section>

        {/* Date firmă */}
        <section className="rounded-xl p-6 mb-4"
          style={{ background: 'rgba(255,255,255,0.025)', border: '1px solid rgba(255,255,255,0.07)' }}>
          <h2 className="text-base font-semibold m-0 mb-1" style={{ color: '#E2E4E9' }}>Date firmă</h2>
          <p className="text-sm mt-1 mb-4 m-0" style={{ color: '#545870' }}>Apar în partea stângă a cartușului schemei.</p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Field label="Denumire firmă" value={profile.firma_nume} onChange={v => update('firma_nume', v)} placeholder="S.C. EXEMPLU S.R.L." />
            <Field label="CUI / CIF" value={profile.firma_cui} onChange={v => update('firma_cui', v)} placeholder="RO12345678" />
            <Field label="Reg. Comerțului" value={profile.firma_reg_com} onChange={v => update('firma_reg_com', v)} placeholder="J5/1234/2024" />
            <Field label="Telefon" value={profile.firma_tel} onChange={v => update('firma_tel', v)} placeholder="0712 345 678" />
            <Field label="Email" type="email" value={profile.firma_email} onChange={v => update('firma_email', v)} placeholder="contact@firma.ro" />
            <Field label="Adresă" value={profile.firma_adresa} onChange={v => update('firma_adresa', v)} placeholder="Str. Exemplu nr. 1, Cluj-Napoca" />
          </div>
        </section>

        {/* Roluri */}
        <section className="rounded-xl p-6 mb-6"
          style={{ background: 'rgba(255,255,255,0.025)', border: '1px solid rgba(255,255,255,0.07)' }}>
          <h2 className="text-base font-semibold m-0 mb-1" style={{ color: '#E2E4E9' }}>Roluri proiectant</h2>
          <p className="text-sm mt-1 mb-4 m-0" style={{ color: '#545870' }}>Numele care apar la „Proiectat" și „Desenat" în cartuș.</p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Field label="Proiectant" value={profile.proiectant_nume} onChange={v => update('proiectant_nume', v)} placeholder="Ing. Nume Prenume" />
            <Field label="Desenator" value={profile.desenator_nume} onChange={v => update('desenator_nume', v)} placeholder="St. Ing. Nume Prenume" />
          </div>
        </section>

        <div className="flex justify-end">
          <button onClick={handleSave} disabled={saving}
            className="px-6 py-2.5 rounded-xl text-sm font-semibold font-[inherit] cursor-pointer transition-all duration-200"
            style={{
              background: saving ? 'rgba(255,255,255,0.05)' : 'linear-gradient(135deg, #378ADD 0%, #1D9E75 100%)',
              border: 'none',
              color: saving ? '#545870' : '#fff',
              cursor: saving ? 'not-allowed' : 'pointer',
              boxShadow: saving ? 'none' : '0 0 24px rgba(55,138,221,0.25)',
            }}>
            {saving ? 'Se salvează...' : 'Salvează datele'}
          </button>
        </div>
      </div>
    </div>
  )
}

function Field({
  label,
  value,
  onChange,
  type = 'text',
  placeholder = '',
}: {
  label: string
  value: string
  onChange: (v: string) => void
  type?: string
  placeholder?: string
}) {
  return (
    <label className="block">
      <span className="text-[11px] font-semibold tracking-widest uppercase block mb-1.5" style={{ color: '#545870' }}>{label}</span>
      <input
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-3 py-2 rounded-lg text-sm outline-none font-[inherit]"
        style={{
          background: 'rgba(255,255,255,0.04)',
          border: '1px solid rgba(255,255,255,0.08)',
          color: '#E2E4E9',
        }}
      />
    </label>
  )
}
