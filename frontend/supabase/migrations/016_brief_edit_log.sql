-- Post-publish edit/delete audit log for live briefs
create table if not exists brief_edit_log (
  id uuid primary key default gen_random_uuid(),
  brief_date date not null,
  item_id text not null,
  action text not null check (action in ('edit', 'delete')),
  previous_item jsonb not null,
  updated_fields jsonb,
  analyst_id uuid not null references auth.users(id),
  created_at timestamptz not null default now()
);

create index idx_brief_edit_log_date on brief_edit_log (brief_date);
