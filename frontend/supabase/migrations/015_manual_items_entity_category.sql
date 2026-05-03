-- 015_manual_items_entity_category.sql
--
-- 1. Adds `primary_entity_category` to manual_items (was missed in 014).
-- 2. Creates the `manual_entries` table for the admin pre-curation queue.

-- ── 1. manual_items: add missing column ─────────────────────────────────

alter table manual_items
  add column if not exists primary_entity_category text
    check (primary_entity_category in (
      'company','university','government','energy','finance',
      'defense','org','model','country','other'
    ));

comment on column manual_items.primary_entity_category is
  'One of 10 entity_logos.category values. Matches the constraint on brief_items and pending_items (migration 014).';

-- ── 2. manual_entries: admin pre-curation queue ─────────────────────────

create table if not exists manual_entries (
  id uuid primary key default gen_random_uuid(),
  created_by text not null,
  headline text not null default '',
  summary text not null default '',
  source_url text,
  brief_section text default '',
  notes text,
  target_date date not null,
  status text not null default 'pending'
    check (status in ('pending', 'ingested', 'expired', 'cancelled')),
  ingested_at timestamptz,
  created_at timestamptz not null default now()
);

create index idx_manual_entries_target_date
  on manual_entries (target_date, status);

-- RLS
alter table manual_entries enable row level security;

create policy "Admins and analysts can read manual_entries"
  on manual_entries for select to authenticated
  using (exists (
    select 1 from user_profiles
    where user_profiles.id = auth.uid()
      and user_profiles.role in ('admin', 'analyst')
  ));

create policy "Admins and analysts can modify manual_entries"
  on manual_entries for all to authenticated
  using (exists (
    select 1 from user_profiles
    where user_profiles.id = auth.uid()
      and user_profiles.role in ('admin', 'analyst')
  ));
