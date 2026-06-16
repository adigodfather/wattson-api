-- A5-B: consume_credits factureaza pe suprafata CORECTA = max(desfasurata reala Vision, manual).
-- Anti-frauda: userul nu poate plati mai putin declarand o suprafata mica.
-- Citeste desfasurata din projects.result_data via p_project_id (SECURITY DEFINER -> ocoleste RLS;
-- proiectul e salvat INAINTE de consum). desfasurata null / fara surfaces / project_id null -> manual.
-- Restul (verificare sold, scadere, tranzactie, idempotenta, detectie faza) NESCHIMBAT.
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
  v_desfasurata numeric;
  v_surface_final numeric;
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

  -- suprafata reala (desfasurata) din proiectul PROPRIU; null -> ramane pe manual
  if p_project_id is not null then
    select (result_data->'project_info'->'surfaces'->>'desfasurata_mp')::numeric
      into v_desfasurata
      from public.projects
      where id = p_project_id and user_id = v_uid;
  end if;
  -- factureaza pe maximul dintre real si manual (niciodata sub ce declara userul)
  v_surface_final := greatest(coalesce(v_desfasurata, 0), p_surface_mp);

  v_cost := ceil(v_surface_final * v_per_m2)::integer;

  -- idempotenta (neschimbata)
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

  -- nota auditabila: suprafata facturata + manual + desfasurata
  insert into public.credits_transactions (user_id, amount, type, balance_after, note, project_id)
  values (v_uid, -v_cost, 'generation', v_new_balance,
    'proj=' || coalesce(p_project_id::text, 'n/a')
      || ' ' || coalesce(p_phase, '') || ' ' || v_surface_final::text || 'mp'
      || ' (man=' || p_surface_mp::text || ', desf=' || coalesce(v_desfasurata::text, 'null') || ')',
    p_project_id);

  return jsonb_build_object('success', true, 'new_balance', v_new_balance, 'cost', v_cost,
    'surface_billed', v_surface_final, 'manual', p_surface_mp, 'desfasurata', v_desfasurata);
end;
$function$;
