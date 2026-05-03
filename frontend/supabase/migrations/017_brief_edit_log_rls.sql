-- Enable RLS on brief_edit_log (missing from migration 016).
-- Without this, the audit table is exposed via the anon role.

alter table brief_edit_log enable row level security;

create policy "Analysts and admins can read brief_edit_log"
  on brief_edit_log for select to authenticated
  using (exists (
    select 1 from user_profiles
    where user_profiles.id = auth.uid()
      and user_profiles.role in ('admin', 'analyst')
  ));

create policy "Analysts and admins can insert brief_edit_log"
  on brief_edit_log for insert to authenticated
  with check (exists (
    select 1 from user_profiles
    where user_profiles.id = auth.uid()
      and user_profiles.role in ('admin', 'analyst')
  ));
