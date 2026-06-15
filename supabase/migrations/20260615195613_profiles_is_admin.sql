-- Flag admin pe profiles (temporar: DTAC+PT doar pentru admin la lansare).
alter table public.profiles add column if not exists is_admin boolean not null default false;
update public.profiles set is_admin = true where id = '1ff11302-b070-43b2-95bc-9f880388e87b';
