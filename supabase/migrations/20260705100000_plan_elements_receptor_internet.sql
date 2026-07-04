-- Receptoare bucata A: permite element_type 'receptor_internet' in plan_elements (retea date/RJ45).
-- Simbol PROPRIU (dreptunghi turcoaz + router alb + 3 unde WiFi), NU refoloseste alimentarea.
-- Aditiv / backward-compatible: doar extinde CHECK-ul chk_element_type cu inca o valoare (22 -> 23).

alter table public.plan_elements drop constraint if exists chk_element_type;

alter table public.plan_elements add constraint chk_element_type check (
  element_type = any (array[
    'lustra_led', 'aplica_tavan', 'aplica_perete', 'aplica_senzor', 'banda_led',
    'intrerupator_simplu', 'intrerupator_cap_scara', 'intrerupator_dublu', 'intrerupator_triplu',
    'tablou_teg', 'tablou_tes', 'tablou_te_ct', 'transformator',
    'priza_simpla', 'priza_dubla', 'priza_16a', 'priza_exterior_ip44',
    'legenda', 'traseu', 'ground_electrode_path',
    'alimentare_receptor', 'receptor_internet'
  ])
);
