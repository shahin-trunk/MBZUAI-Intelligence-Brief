-- Brief v2: Card reader support
-- Adds new ghostwriter output fields, entity logos, saved items, and reader interaction logging.

-- 1. Add v2 columns to brief_items (old columns remain for backward compat)
alter table brief_items
  add column if not exists key_bullets jsonb,
  add column if not exists analysis text,
  add column if not exists primary_entity text,
  add column if not exists exhibits jsonb,
  add column if not exists audio_url text;

-- 2. Entity logos lookup table
create table entity_logos (
  entity_name text primary key,
  logo_path text not null,
  aliases text[] default '{}',
  category text not null default 'company'
    check (category in ('company', 'university', 'government', 'energy', 'finance', 'defense', 'org', 'model', 'other')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_entity_logos_aliases on entity_logos using gin (aliases);

-- 3. Saved items (swipe-right collection)
create table saved_items (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id),
  brief_date date not null,
  item_id text not null,
  saved_at timestamptz not null default now(),
  unique (user_id, brief_date, item_id)
);

create index idx_saved_items_user on saved_items (user_id, saved_at desc);

-- 4. Reader interaction logging
create table reader_interactions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id),
  brief_date date not null,
  item_id text not null,
  action text not null
    check (action in ('dismissed', 'saved', 'expanded', 'audio_played', 'research_requested')),
  created_at timestamptz not null default now()
);

create index idx_reader_interactions_user_date on reader_interactions (user_id, brief_date);

-- 5. RLS
alter table entity_logos enable row level security;
alter table saved_items enable row level security;
alter table reader_interactions enable row level security;

-- entity_logos: public read (logos are not user-scoped)
create policy "Anyone can read entity_logos"
  on entity_logos for select to authenticated
  using (true);

create policy "Admins can manage entity_logos"
  on entity_logos for all to authenticated
  using (exists (
    select 1 from user_profiles
    where user_profiles.id = auth.uid()
      and user_profiles.role = 'admin'
  ));

-- saved_items: own-user only
create policy "Users can read own saved_items"
  on saved_items for select to authenticated
  using (user_id = auth.uid());

create policy "Users can insert own saved_items"
  on saved_items for insert to authenticated
  with check (user_id = auth.uid());

create policy "Users can delete own saved_items"
  on saved_items for delete to authenticated
  using (user_id = auth.uid());

-- reader_interactions: insert own, read own
create policy "Users can insert own reader_interactions"
  on reader_interactions for insert to authenticated
  with check (user_id = auth.uid());

create policy "Users can read own reader_interactions"
  on reader_interactions for select to authenticated
  using (user_id = auth.uid());
