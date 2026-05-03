-- Add v2 ghostwriter output fields to pending_items
ALTER TABLE pending_items ADD COLUMN IF NOT EXISTS key_bullets jsonb;
ALTER TABLE pending_items ADD COLUMN IF NOT EXISTS analysis text;
