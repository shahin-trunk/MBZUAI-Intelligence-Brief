-- Add bio_facts JSONB column to engagements table for structured biographical data
-- (current_roles, previous_roles, recognition) displayed in the dossier sidebar.
ALTER TABLE engagements ADD COLUMN IF NOT EXISTS bio_facts jsonb;
