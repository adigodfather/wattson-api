-- ILUMINAT DE SIGURANTA (I7-2011 cap. 7.23 + SR EN 1838). Doua mecanisme diferite:
--   (a) EVACUARE  = corp AUTONOM cu acumulator -> element_type NOU 'corp_evacuare'
--   (b) ANTIPANICA = KIT pe un corp NORMAL existent -> coloana NOUA `kit_panica` (becul ramane bec)
--
-- ORDINE DE APLICARE (Dan): rulati ACEASTA migratie INAINTE de deploy-ul care scrie `kit_panica`
-- si 'corp_evacuare'. Altfel INSERT-ul in plan_elements pica pe coloana/CHECK inexistent, iar
-- save_plan_elements e NON-BLOCANT (inghite eroarea) -> elementele planului s-ar pierde TACUT.
-- (Aceeasi nota ca la migratia `phase`, din acelasi motiv.)

alter table public.plan_elements
  add column if not exists kit_panica boolean not null default false;

comment on column public.plan_elements.kit_panica is
  'Corp de iluminat normal echipat cu kit de emergenta 2h (iluminat antipanica). Becul ramane pe circuitul lui normal; se schimba doar culoarea pe plansa si un rand in lista de cantitati.';

-- CHECK-ul se rescrie INTREG (Postgres nu poate extinde un check existent). Lista de mai jos e
-- derivata din tipurile VII din cod: _BULB_TYPES / _SWITCH_TYPES / _PANEL_TYPES / _PRIZA_TYPES
-- (draw_elements.py) + tipurile de traseu + receptoarele. Fata de ultima migratie versionata
-- (20260705, 23 valori) s-au adaugat intre timp direct in baza: panou_led, banda_led_path,
-- banda_led_driver, fv_chain_path, tablou_tes(existent), tablou_tca. Aici sunt TOATE la un loc.
alter table public.plan_elements drop constraint if exists chk_element_type;

alter table public.plan_elements add constraint chk_element_type check (
  element_type = any (array[
    -- corpuri de iluminat
    'lustra_led', 'aplica_tavan', 'aplica_perete', 'aplica_senzor', 'panou_led', 'banda_led',
    -- iluminat de siguranta: corpul de evacuare, autonom (NU e in _BULB_TYPES -> circuit propriu)
    'corp_evacuare',
    -- banda LED: traseul desenat + driverul lui
    'banda_led_path', 'banda_led_driver',
    -- aparataj
    'intrerupator_simplu', 'intrerupator_cap_scara', 'intrerupator_dublu', 'intrerupator_triplu',
    -- tablouri (inclusiv FV)
    'tablou_teg', 'tablou_tes', 'tablou_te_ct', 'transformator',
    'tablou_tcc', 'tablou_inv', 'tablou_tca',
    -- prize
    'priza_simpla', 'priza_dubla', 'priza_16a', 'priza_exterior_ip44',
    -- desen (trasee) + legenda
    'legenda', 'traseu', 'ground_electrode_path', 'fv_chain_path',
    -- receptoare
    'alimentare_receptor', 'receptor_internet'
  ])
);
