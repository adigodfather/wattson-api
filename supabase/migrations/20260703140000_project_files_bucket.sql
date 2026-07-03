-- Problema 5, ETAPA 0: bucket PRIVAT pentru PDF-urile proiectelor + RLS owner-only.
-- Muta blob-urile base64 din projects.result_data in Storage (pastram doar referinte).
-- Path: <user_id>/<project_id>/<nume_fisier>  -> RLS verifica ownership pe primul folder.
-- Bucket PRIVAT (spre deosebire de company-logos care e public) -> citire DOAR prin signed URL.
-- Izolatie testata in rollback: user A vede doar folderul lui; user B blocat (select+insert).

insert into storage.buckets (id, name, public)
  values ('project-files', 'project-files', false)
  on conflict (id) do nothing;

-- owner-only pe toate operatiile: userul acceseaza DOAR obiectele unde primul folder = uid-ul lui.
-- (storage.foldername(name))[1] = primul segment din path = <user_id>.
drop policy if exists pf_owner_select on storage.objects;
drop policy if exists pf_owner_insert on storage.objects;
drop policy if exists pf_owner_update on storage.objects;
drop policy if exists pf_owner_delete on storage.objects;

create policy pf_owner_select on storage.objects for select to authenticated
  using (bucket_id = 'project-files' and (storage.foldername(name))[1] = auth.uid()::text);
create policy pf_owner_insert on storage.objects for insert to authenticated
  with check (bucket_id = 'project-files' and (storage.foldername(name))[1] = auth.uid()::text);
create policy pf_owner_update on storage.objects for update to authenticated
  using (bucket_id = 'project-files' and (storage.foldername(name))[1] = auth.uid()::text);
create policy pf_owner_delete on storage.objects for delete to authenticated
  using (bucket_id = 'project-files' and (storage.foldername(name))[1] = auth.uid()::text);
