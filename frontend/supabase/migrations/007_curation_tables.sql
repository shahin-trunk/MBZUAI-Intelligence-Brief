-- Analyst Curation Workflow tables
-- Adds the human-in-the-loop curation layer between the AI pipeline and brief publication.

-- 0. Add 'analyst' to the user_profiles role constraint
alter table user_profiles drop constraint user_profiles_role_check;
alter table user_profiles add constraint user_profiles_role_check
  check (role in ('reader', 'admin', 'analyst'));

-- 1. pending_briefs — one row per pipeline run awaiting analyst review
create table pending_briefs (
  id uuid primary key default gen_random_uuid(),
  brief_date date not null,
  status text not null default 'pending'
    check (status in ('pending', 'in_review', 'approved', 'published')),
  claimed_by uuid references auth.users(id),
  claimed_at timestamptz,
  approved_at timestamptz,
  published_at timestamptz,
  shadow_recommendation jsonb,
  gatekeeper_output jsonb,
  source_metadata_lookup jsonb,
  pipeline_stats jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index idx_pending_briefs_date on pending_briefs (brief_date);
create index idx_pending_briefs_status on pending_briefs (status);

-- 2. pending_items — candidate items in the draft slate
create table pending_items (
  id uuid primary key default gen_random_uuid(),
  pending_brief_id uuid not null references pending_briefs(id) on delete cascade,
  item_id text not null,
  tier text not null default 'proposed'
    check (tier in ('proposed', 'pool')),
  section text not null,
  headline text not null,
  main_bullet text,
  context text,
  implication text,
  source_name text,
  source_url text,
  composite_score numeric default 0,
  significance_level text,
  rank integer,
  depth text,
  is_model_release boolean not null default false,
  model_release_data jsonb,
  raw_item jsonb not null,
  created_at timestamptz not null default now()
);

create index idx_pending_items_brief on pending_items (pending_brief_id);
create index idx_pending_items_tier on pending_items (tier);

-- 3. curation_decisions — records analyst editorial decisions for calibration
create table curation_decisions (
  id uuid primary key default gen_random_uuid(),
  pending_brief_id uuid not null references pending_briefs(id) on delete cascade,
  item_id text not null,
  decision text not null
    check (decision in ('keep', 'remove', 'promote', 'demote', 'edit', 'reorder', 'add')),
  original_tier text,
  original_section text,
  original_rank integer,
  final_section text,
  final_rank integer,
  edit_fields jsonb,
  analyst_id uuid not null references auth.users(id),
  created_at timestamptz not null default now()
);

create index idx_curation_decisions_brief on curation_decisions (pending_brief_id);

-- 4. manual_items — items the analyst adds during curation
create table manual_items (
  id uuid primary key default gen_random_uuid(),
  pending_brief_id uuid not null references pending_briefs(id) on delete cascade,
  section text not null,
  headline text not null,
  main_bullet text not null,
  context text,
  implication text,
  source_name text,
  source_url text,
  significance_level text default 'medium',
  added_by uuid not null references auth.users(id),
  created_at timestamptz not null default now()
);

create index idx_manual_items_brief on manual_items (pending_brief_id);

-- 5. Enable RLS on all new tables
alter table pending_briefs enable row level security;
alter table pending_items enable row level security;
alter table curation_decisions enable row level security;
alter table manual_items enable row level security;

-- 6. RLS policies — admin + analyst access

-- pending_briefs
create policy "Analysts and admins can read pending_briefs"
  on pending_briefs for select to authenticated
  using (exists (
    select 1 from user_profiles
    where user_profiles.id = auth.uid()
      and user_profiles.role in ('admin', 'analyst')
  ));

create policy "Analysts and admins can insert pending_briefs"
  on pending_briefs for insert to authenticated
  with check (exists (
    select 1 from user_profiles
    where user_profiles.id = auth.uid()
      and user_profiles.role in ('admin', 'analyst')
  ));

create policy "Analysts and admins can update pending_briefs"
  on pending_briefs for update to authenticated
  using (exists (
    select 1 from user_profiles
    where user_profiles.id = auth.uid()
      and user_profiles.role in ('admin', 'analyst')
  ));

-- pending_items
create policy "Analysts and admins can read pending_items"
  on pending_items for select to authenticated
  using (exists (
    select 1 from user_profiles
    where user_profiles.id = auth.uid()
      and user_profiles.role in ('admin', 'analyst')
  ));

create policy "Analysts and admins can modify pending_items"
  on pending_items for all to authenticated
  using (exists (
    select 1 from user_profiles
    where user_profiles.id = auth.uid()
      and user_profiles.role in ('admin', 'analyst')
  ));

-- curation_decisions
create policy "Analysts and admins can read curation_decisions"
  on curation_decisions for select to authenticated
  using (exists (
    select 1 from user_profiles
    where user_profiles.id = auth.uid()
      and user_profiles.role in ('admin', 'analyst')
  ));

create policy "Analysts and admins can insert curation_decisions"
  on curation_decisions for insert to authenticated
  with check (exists (
    select 1 from user_profiles
    where user_profiles.id = auth.uid()
      and user_profiles.role in ('admin', 'analyst')
  ));

-- manual_items
create policy "Analysts and admins can read manual_items"
  on manual_items for select to authenticated
  using (exists (
    select 1 from user_profiles
    where user_profiles.id = auth.uid()
      and user_profiles.role in ('admin', 'analyst')
  ));

create policy "Analysts and admins can modify manual_items"
  on manual_items for all to authenticated
  using (exists (
    select 1 from user_profiles
    where user_profiles.id = auth.uid()
      and user_profiles.role in ('admin', 'analyst')
  ));
