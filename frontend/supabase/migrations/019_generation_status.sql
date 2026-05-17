-- Migration 019: Add generation_status column to briefs table
-- Tracks Celery task status for async audio/script generation
-- Date: 2026-05-17

ALTER TABLE "public"."briefs"
  ADD COLUMN IF NOT EXISTS "generation_status" jsonb DEFAULT '{}';

COMMENT ON COLUMN "public"."briefs"."generation_status" IS
  'Tracks async Celery task status for script/audio generation (llm_script, learning_fr, learning_ar, item_audio)';
