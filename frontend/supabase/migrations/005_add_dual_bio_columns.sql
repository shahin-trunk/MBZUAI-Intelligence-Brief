-- Add dual-bio columns to engagements table for Concise/Extended profile toggle.
-- Concise: short CV sidebar + 4-5 sentence HTML narrative
-- Extended: full CV sidebar + 3-4 paragraph HTML narrative
ALTER TABLE engagements ADD COLUMN IF NOT EXISTS bio_concise_cv jsonb;
ALTER TABLE engagements ADD COLUMN IF NOT EXISTS bio_concise_narrative text;
ALTER TABLE engagements ADD COLUMN IF NOT EXISTS bio_extended_cv jsonb;
ALTER TABLE engagements ADD COLUMN IF NOT EXISTS bio_extended_narrative text;
ALTER TABLE engagements ADD COLUMN IF NOT EXISTS research_chips jsonb;
