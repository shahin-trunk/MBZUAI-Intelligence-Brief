-- Regional Research Scout tables
-- Run this in the Supabase SQL Editor

-- 1. Entity watchlist — tracked institutions for the regional research scout
create table scout_entity_watchlist (
  id uuid primary key default gen_random_uuid(),
  entity_name text unique not null,
  aliases text[] default '{}',
  priority text not null default 'standard'
    check (priority in ('high', 'standard')),
  notes text,
  enabled boolean not null default true,
  last_hit_date date,
  created_at timestamptz not null default now()
);

create index idx_watchlist_enabled on scout_entity_watchlist (enabled);

-- 2. Scout run log — one row per pipeline run
create table scout_run_log (
  id uuid primary key default gen_random_uuid(),
  run_date date not null,
  model text not null,
  search_count int not null default 0,
  candidates_returned int not null default 0,
  candidates_passed_triage int not null default 0,
  candidates_in_brief int not null default 0,
  input_tokens int not null default 0,
  output_tokens int not null default 0,
  cost_usd numeric(8,4) not null default 0,
  duration_seconds numeric(8,1) not null default 0,
  raw_output jsonb,
  created_at timestamptz not null default now()
);

create index idx_run_log_date on scout_run_log (run_date desc);

-- 3. RLS policies
alter table scout_entity_watchlist enable row level security;
alter table scout_run_log enable row level security;

-- All authenticated users can read
create policy "Authenticated users can read watchlist"
  on scout_entity_watchlist for select
  to authenticated
  using (true);

create policy "Authenticated users can read run log"
  on scout_run_log for select
  to authenticated
  using (true);

-- Admin-only insert/update/delete on watchlist
create policy "Admins can insert watchlist"
  on scout_entity_watchlist for insert
  to authenticated
  with check (
    exists (
      select 1 from user_profiles
      where user_profiles.id = auth.uid()
        and user_profiles.role = 'admin'
    )
  );

create policy "Admins can update watchlist"
  on scout_entity_watchlist for update
  to authenticated
  using (
    exists (
      select 1 from user_profiles
      where user_profiles.id = auth.uid()
        and user_profiles.role = 'admin'
    )
  );

create policy "Admins can delete watchlist"
  on scout_entity_watchlist for delete
  to authenticated
  using (
    exists (
      select 1 from user_profiles
      where user_profiles.id = auth.uid()
        and user_profiles.role = 'admin'
    )
  );

-- Admin-only insert on run log (pipeline writes via service role, but RLS still needed)
create policy "Admins can insert run log"
  on scout_run_log for insert
  to authenticated
  with check (
    exists (
      select 1 from user_profiles
      where user_profiles.id = auth.uid()
        and user_profiles.role = 'admin'
    )
  );

create policy "Admins can update run log"
  on scout_run_log for update
  to authenticated
  using (
    exists (
      select 1 from user_profiles
      where user_profiles.id = auth.uid()
        and user_profiles.role = 'admin'
    )
  );

-- 4. Seed data — initial entity watchlist
insert into scout_entity_watchlist (entity_name, aliases, priority, notes) values
  -- High priority
  ('Khalifa University', '{"KU", "Digital Future Institute"}', 'high', 'Top UAE research university — direct competitor'),
  ('KAUST', '{"King Abdullah University of Science and Technology"}', 'high', 'Saudi flagship research university'),
  ('NYU Abu Dhabi', '{"NYUAD"}', 'high', 'Leading liberal arts and research institution in Abu Dhabi'),
  ('Qatar Computing Research Institute', '{"QCRI"}', 'high', 'Major Gulf AI/NLP research lab under HBKU'),
  ('UAEU', '{"UAE University", "United Arab Emirates University"}', 'high', 'Oldest UAE university — flagship national institution'),

  -- Standard
  ('American University of Sharjah', '{"AUS"}', 'standard', null),
  ('AURAK', '{"American University of Ras Al Khaimah"}', 'standard', null),
  ('Ajman University', '{}', 'standard', null),
  ('University of Wollongong Dubai', '{"UOW Dubai"}', 'standard', null),
  ('Heriot-Watt Dubai', '{}', 'standard', null),
  ('Zayed University', '{"ZU"}', 'standard', null),
  ('RIT Dubai', '{}', 'standard', null),
  ('MBRU', '{"Mohammed Bin Rashid University of Medicine"}', 'standard', null),
  ('Sorbonne Abu Dhabi', '{"Paris-Sorbonne University Abu Dhabi"}', 'standard', null),
  ('SPARK', '{"Sharjah Research Technology Innovation Park"}', 'standard', null),
  ('Dubai Silicon Oasis', '{"DSO"}', 'standard', null),
  ('TDRA', '{}', 'standard', 'UAE Telecommunications and Digital Government Regulatory Authority'),
  ('MoHESR', '{"Ministry of Higher Education and Scientific Research UAE"}', 'standard', null),
  ('ADEK', '{"Abu Dhabi Department of Education and Knowledge"}', 'standard', null),
  ('KHDA', '{}', 'standard', 'Knowledge and Human Development Authority — Dubai education regulator'),
  ('imec', '{}', 'standard', 'Belgian nanoelectronics institute with UAE partnerships'),
  ('King Fahd University', '{"KFUPM", "King Fahd University of Petroleum and Minerals"}', 'standard', null),
  ('Qatar Foundation', '{}', 'standard', null),
  ('Qatar Science & Technology Park', '{"QSTP"}', 'standard', null),
  ('SDAIA', '{"Saudi Data and AI Authority"}', 'standard', 'Saudi national AI authority');
