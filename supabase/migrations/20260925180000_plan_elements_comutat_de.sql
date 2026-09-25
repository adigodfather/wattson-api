-- CINE COMUTA CE: asocierea bec <-> intrerupator, stocata (pachetul 1).
--
-- Pana acum asocierea nu exista nicaieri. `compute_cables` o recalcula la fiecare generare, desena
-- cablul si o arunca. Intrebarea „ce bec comuta intrerupatorul asta" n-avea cui sa fie pusa — nici
-- editorului, nici BOM-ului, nici inginerului.
--
-- DE CE PE BEC si nu pe intrerupator: becul e partea la care intrebarea trebuie sa aiba MEREU un
-- raspuns. Un bec pe care nu-l comuta nimic e un defect (azi il numaram ca `skip_bec_fara_sw` si nu
-- se vede nicaieri); tinand campul pe bec, lipsa se vede chiar pe randul care are problema.
--
-- DE CE O LISTA si nu un singur id: CAP-SCARA. Acolo UN bec e comutat de DOUA intrerupatoare, si
-- amandoua trebuie sa poata ajunge la tablou. Un `uuid` simplu (ca `copiat_din`) n-ar fi incaput
-- cazul. In baza de azi sunt 9 astfel de becuri.
--
-- NULLABLE si FARA valoare implicita: cele 1366 de randuri existente raman valide neatinse. NULL
-- inseamna „nu s-a calculat inca" si se completeaza singur la prima regenerare; `{}` (lista goala)
-- inseamna „s-a calculat si chiar nu-l comuta nimic" — doua stari diferite, pe care un default le-ar
-- fi confundat.
--
-- DE CE UN TRIGGER si nu o cheie straina: Postgres nu pune FK pe ELEMENTELE unui array, deci
-- `on delete set null` (tiparul lui `copiat_din`) nu e disponibil aici. Fara ceva, stergerea unui
-- intrerupator ar lasa id-uri moarte in becuri pana la urmatoarea regenerare. Curatenia sta IN BAZA,
-- nu in memoria celui care scrie codul de stergere: asa invariantul tine si cand se sterge din
-- editor, din SQL sau dintr-un script viitor.

alter table public.plan_elements
  add column if not exists comutat_de uuid[];

comment on column public.plan_elements.comutat_de is
  'Doar pe becuri: id-urile intrerupatoarelor care comuta becul asta (plan_elements.id). NULL = '
  'nu s-a calculat inca (se completeaza la "Obtine plan"); {} = s-a calculat si nu-l comuta nimic. '
  'LISTA, nu un id: la cap-scara acelasi bec e comutat de doua intrerupatoare. Curatat automat de '
  'trg_comutat_de_curata cand un intrerupator e sters.';

-- Cautarea „cine mai arata spre intrerupatorul asta" (o face triggerul la fiecare stergere).
-- Partial: tine doar randurile care chiar au asocierea (azi: zero).
create index if not exists idx_plan_elements_comutat_de
  on public.plan_elements using gin (comutat_de)
  where comutat_de is not null;

-- Echivalentul lui `on delete set null` pentru un array: la stergerea oricarui element, id-ul lui
-- dispare din listele care-l pomeneau. Becul ramane, doar ca nu-l mai comuta acel intrerupator;
-- urmatoarea regenerare ii da altul, dupa reguli.
-- `security invoker`, nu `definer`: cine sterge un intrerupator are deja drept de UPDATE pe becurile
-- lui (plan_elements_update_own), iar id-urile nu trec niciodata dintr-un proiect in altul. Verificat
-- pe comportament, ca utilizator autentificat CU RLS pornit (lista 2 -> 1 dupa stergere). O functie
-- care scrie ocolind RLS fara sa fie nevoie e o usa deschisa degeaba.
create or replace function public.comutat_de_curata()
returns trigger
language plpgsql
security invoker
set search_path = public
as $$
begin
  update public.plan_elements
     set comutat_de = array_remove(comutat_de, old.id)
   where comutat_de @> array[old.id];
  return old;
end;
$$;

drop trigger if exists trg_comutat_de_curata on public.plan_elements;
create trigger trg_comutat_de_curata
  after delete on public.plan_elements
  for each row execute function public.comutat_de_curata();
