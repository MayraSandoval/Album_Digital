create table if not exists public.album_records (
    collection text not null,
    item_id text not null,
    unique_key text,
    data jsonb not null,
    primary key (collection, item_id),
    unique (collection, unique_key)
);

alter table public.album_records enable row level security;
revoke all on table public.album_records from public, anon, authenticated;
grant all on table public.album_records to service_role;

insert into storage.buckets (id, name, public)
values ('album-fotos', 'album-fotos', false)
on conflict do nothing;

do $$
begin
    if not exists (
        select 1 from storage.buckets where id = 'album-fotos' and public = false
    ) then
        raise exception 'El bucket album-fotos debe existir y ser privado.';
    end if;
end $$;
