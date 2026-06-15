-- Fix detectie faza in consume_credits: robusta la formate cu puncte/spatii.
-- "DTAC+PT", "D.T.A.C. + P.T.", "PT", "P.T." -> 3/mp; "DTAC", "D.T.A.C." -> 1/mp.
-- Normalizare: scoate tot ce nu e litera, lowercase, cauta "pt" (ca regula frontend isPhasePT).
-- Restul functiei IDENTIC cu 20260615194840 (doar linia de detectie se schimba).
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

  -- PRET SERVER-SIDE: DTAC=1/mp, DTAC+PT=3/mp.
  -- Detectie faza ROBUSTA la format: normalizeaza (doar litere, lowercase) apoi cauta 'pt'.
  v_per_m2 := case
    when lower(regexp_replace(coalesce(p_phase, ''), '[^a-zA-Z]', '', 'g')) like '%pt%'
    then 3 else 1 end;
  v_cost := ceil(p_surface_mp * v_per_m2)::integer;

  -- IDEMPOTENTA: daca exista deja un consum 'generation' pentru acest project_id -> nu re-scadem.
  if p_project_id is not null and exists (
    select 1 from public.credits_transactions
    where user_id = v_uid and type = 'generation'
      and note like 'proj=' || p_project_id::text || '%'
  ) then
    select credits_balance into v_balance from public.profiles where id = v_uid;
    return jsonb_build_object('success', true, 'new_balance', v_balance,
      'cost', v_cost, 'note', 'deja consumat');
  end if;

  -- LOCK pe randul de profil (atomicitate)
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

  insert into public.credits_transactions (user_id, amount, type, balance_after, note)
  values (v_uid, -v_cost, 'generation', v_new_balance,
    'proj=' || coalesce(p_project_id::text, 'n/a')
      || ' ' || coalesce(p_phase, '') || ' ' || p_surface_mp::text || 'mp');

  return jsonb_build_object('success', true, 'new_balance', v_new_balance, 'cost', v_cost);
end;
$function$;
