create table if not exists public.conversations (
    id uuid primary key default gen_random_uuid(),
    owner_user_id uuid not null references auth.users (id) on delete cascade,
    title text not null check (char_length(title) between 1 and 120),
    state text not null default 'open' check (state = 'open'),
    created_at timestamptz not null default now(),
    last_activity_at timestamptz not null default now(),
    unique (id, owner_user_id)
);

create index if not exists conversations_owner_activity_idx
    on public.conversations (owner_user_id, last_activity_at desc, id desc);

create table if not exists public.messages (
    id uuid primary key default gen_random_uuid(),
    conversation_id uuid not null,
    owner_user_id uuid not null references auth.users (id) on delete cascade,
    role text not null default 'installer' check (role = 'installer'),
    content_text text not null check (char_length(content_text) between 1 and 8000),
    processing_state text not null default 'received' check (processing_state = 'received'),
    created_at timestamptz not null default now(),
    foreign key (conversation_id, owner_user_id)
        references public.conversations (id, owner_user_id) on delete cascade
);

create index if not exists messages_owner_conversation_order_idx
    on public.messages (owner_user_id, conversation_id, created_at, id);

alter table public.conversations enable row level security;
alter table public.messages enable row level security;

drop policy if exists conversations_select_own on public.conversations;
create policy conversations_select_own on public.conversations
    for select to authenticated
    using ((select auth.uid()) = owner_user_id);

drop policy if exists conversations_insert_own on public.conversations;
create policy conversations_insert_own on public.conversations
    for insert to authenticated
    with check ((select auth.uid()) = owner_user_id);

drop policy if exists conversations_update_own_activity on public.conversations;
create policy conversations_update_own_activity on public.conversations
    for update to authenticated
    using ((select auth.uid()) = owner_user_id)
    with check ((select auth.uid()) = owner_user_id);

drop policy if exists messages_select_own on public.messages;
create policy messages_select_own on public.messages
    for select to authenticated
    using ((select auth.uid()) = owner_user_id);

drop policy if exists messages_insert_own on public.messages;
create policy messages_insert_own on public.messages
    for insert to authenticated
    with check ((select auth.uid()) = owner_user_id);

revoke all on public.conversations, public.messages from anon;
grant select, insert on public.conversations, public.messages to authenticated;
revoke update on public.conversations from authenticated;
grant update (last_activity_at) on public.conversations to authenticated;

create or replace function public.update_conversation_activity_from_message()
returns trigger
language plpgsql
set search_path = pg_catalog, public
as $$
begin
    update public.conversations
       set last_activity_at = new.created_at
     where id = new.conversation_id
       and owner_user_id = new.owner_user_id;
    return new;
end;
$$;

revoke all on function public.update_conversation_activity_from_message() from public, anon, authenticated;

drop trigger if exists messages_update_conversation_activity on public.messages;
create trigger messages_update_conversation_activity
    after insert on public.messages
    for each row execute function public.update_conversation_activity_from_message();
