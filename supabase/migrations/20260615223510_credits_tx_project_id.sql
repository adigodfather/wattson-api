-- Coloana project_id in credits_transactions: legatura CURATA proiect -> consum
-- (afisare cost in /projects + rapoarte viitoare). Inlocuieste match-ul fragil pe note.
alter table public.credits_transactions add column if not exists project_id uuid;

create index if not exists idx_credits_tx_project_id
  on public.credits_transactions (project_id) where project_id is not null;

-- backfill tranzactiile 'generation' existente (extrage uuid din note 'proj=<uuid>')
update public.credits_transactions
set project_id = substring(note from 'proj=([0-9a-fA-F-]{36})')::uuid
where type = 'generation' and project_id is null
  and substring(note from 'proj=([0-9a-fA-F-]{36})') is not null;

-- consume_credits: populeaza project_id la insert. Idempotenta RAMANE pe note (logica neschimbata).
-- Restul IDENTIC cu 20260615221731 (detectie faza normalizata).
create or replace function public.consume_credits(
  p_surface_mp numeric,
  p_phase text,
  p_project_id uuid default null
)
returns jsonb
language plpgsql
security definer
set search_path to 'public'
as $function$
declare
  v_uid uuid := auth.uid();
  v_per_m2 integer;
  v_cost integer;
  v_balance integer;
  v_new_balance integer;
begin
  if v_uid is null then
    return jsonb_build_object('success', false, 'error', 'Neautentificat');
  end if;
  if p_surface_mp is null or p_surface_mp <= 0 then
    return jsonb_build_object('success', false, 'error', 'Suprafata invalida');
  end if;

  v_per_m2 := case
    when lower(regexp_replace(coalesce(p_phase, ''), '[^a-zA-Z]', '', 'g')) like '%pt%'
    then 3 else 1 end;
  v_cost := ceil(p_surface_mp * v_per_m2)::integer;

  if p_project_id is not null and exists (
    select 1 from public.credits_transactions
    where user_id = v_uid and type = 'generation'
      and note like 'proj=' || p_project_id::text || '%'
  ) then
    select credits_balance into v_balance from public.profiles where id = v_uid;
    return jsonb_build_object('success', true, 'new_balance', v_balance,
      'cost', v_cost, 'note', 'deja consumat');
  end if;

  select credits_balance into v_balance from public.profiles where id = v_uid for update;
  if not found then
    return jsonb_build_object('success', false, 'error', 'Profil inexistent');
  end if;

  if v_balance < v_cost then
    return jsonb_build_object('success', false, 'error', 'Sold insuficient',
      'cost', v_cost, 'balance', v_balance);
  end if;

  v_new_balance := v_balance - v_cost;
  update public.profiles set credits_balance = v_new_balance where id = v_uid;

  insert into public.credits_transactions (user_id, amount, type, balance_after, note, project_id)
  values (v_uid, -v_cost, 'generation', v_new_balance,
    'proj=' || coalesce(p_project_id::text, 'n/a')
      || ' ' || coalesce(p_phase, '') || ' ' || p_surface_mp::text || 'mp',
    p_project_id);

  return jsonb_build_object('success', true, 'new_balance', v_new_balance, 'cost', v_cost);
end;
$function$;
