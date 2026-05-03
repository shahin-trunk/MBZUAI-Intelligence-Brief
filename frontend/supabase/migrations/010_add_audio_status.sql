-- Add audio_status column for tracking audio generation progress.
-- Values: 'pending', 'generating_script', 'generating_audio', 'uploading', 'ready', 'failed'
-- NULL = no audio generation tracked (backward compat for old briefs).
ALTER TABLE briefs ADD COLUMN IF NOT EXISTS audio_status text;
