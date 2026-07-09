-- Regula 10 (receptoare termice): coloana `phase` pe plan_elements pentru VCV / radiatoare
-- (mono/tri PER ELEMENT) + distribuitor de zona. Valori: 'mono' | 'tri'.
-- Aditiv / backward-compatible: default 'mono'; elementele existente (fara faza) raman monofazate.
-- gruparea VCV+radiatoare (compute_circuits) separa clasele mono/tri pe baza acestei coloane.
--
-- ORDINE DE APLICARE (Dan): rulati ACEASTA migratie INAINTE de deploy-ul care citeste `phase`
-- (finalize/route.ts selecteaza coloana). Altfel finalize da eroare (coloana inexistenta).

alter table public.plan_elements
  add column if not exists phase text default 'mono';

alter table public.plan_elements drop constraint if exists chk_phase;

alter table public.plan_elements add constraint chk_phase check (
  phase is null or phase in ('mono', 'tri')
);
