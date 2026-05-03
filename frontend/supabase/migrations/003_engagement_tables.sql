-- Executive Engagement tables
-- Run this in the Supabase SQL Editor

-- 1. Engagements table
create table engagements (
  id text primary key,
  visitor_name text not null,
  visitor_title text not null,
  visitor_organization text not null,
  date date not null,
  time text not null,
  location text not null,
  format text not null default 'In person'
    check (format in ('In person', 'Virtual', 'Hybrid')),

  -- LLM-generated content
  bio text,
  credential_tags text[] default '{}',
  mutual_interests jsonb default '[]',
  suggested_questions jsonb default '[]',

  -- Materials (admin-uploaded)
  materials jsonb default '[]',

  -- Metadata
  created_by text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_engagements_date on engagements (date asc);

-- 2. Engagement follow-ups table
create table engagement_followups (
  id uuid primary key default gen_random_uuid(),
  engagement_id text not null references engagements(id) on delete cascade,
  question text not null,
  answer text not null,
  detail text,
  asked_by text not null,
  created_at timestamptz not null default now()
);

create index idx_followups_engagement on engagement_followups (engagement_id, created_at desc);

-- 3. Engagement requests table
create table engagement_requests (
  id uuid primary key default gen_random_uuid(),
  engagement_id text not null references engagements(id) on delete cascade,
  message text not null,
  requested_by text not null,
  status text not null default 'open'
    check (status in ('open', 'in_progress', 'done')),
  created_at timestamptz not null default now(),
  resolved_at timestamptz
);

create index idx_requests_engagement on engagement_requests (engagement_id);
create index idx_requests_status on engagement_requests (status);

-- 4. Auto-update trigger for engagements.updated_at
create or replace function update_engagement_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger engagements_updated_at
  before update on engagements
  for each row execute function update_engagement_updated_at();

-- 5. RLS policies
alter table engagements enable row level security;
alter table engagement_followups enable row level security;
alter table engagement_requests enable row level security;

-- All authenticated users can read
create policy "Authenticated users can read engagements"
  on engagements for select
  to authenticated
  using (true);

create policy "Authenticated users can read followups"
  on engagement_followups for select
  to authenticated
  using (true);

create policy "Authenticated users can read requests"
  on engagement_requests for select
  to authenticated
  using (true);

-- Admin-only insert/update on engagements
create policy "Admins can insert engagements"
  on engagements for insert
  to authenticated
  with check (
    exists (
      select 1 from user_profiles
      where user_profiles.id = auth.uid()
        and user_profiles.role = 'admin'
    )
  );

create policy "Admins can update engagements"
  on engagements for update
  to authenticated
  using (
    exists (
      select 1 from user_profiles
      where user_profiles.id = auth.uid()
        and user_profiles.role = 'admin'
    )
  );

create policy "Admins can delete engagements"
  on engagements for delete
  to authenticated
  using (
    exists (
      select 1 from user_profiles
      where user_profiles.id = auth.uid()
        and user_profiles.role = 'admin'
    )
  );

-- All authenticated users can insert followups and requests
create policy "Authenticated users can insert followups"
  on engagement_followups for insert
  to authenticated
  with check (true);

create policy "Authenticated users can insert requests"
  on engagement_requests for insert
  to authenticated
  with check (true);

-- Admin-only update on requests (mark done)
create policy "Admins can update requests"
  on engagement_requests for update
  to authenticated
  using (
    exists (
      select 1 from user_profiles
      where user_profiles.id = auth.uid()
        and user_profiles.role = 'admin'
    )
  );

-- 6. Storage bucket for engagement materials
-- Run this separately or via Supabase dashboard:
-- insert into storage.buckets (id, name, public) values ('engagement-materials', 'engagement-materials', false);
