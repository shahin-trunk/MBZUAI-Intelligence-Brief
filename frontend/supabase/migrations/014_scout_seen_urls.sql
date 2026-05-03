-- 014_scout_seen_urls.sql
--
-- Persist the scout seen-URL cache across Cloud Run runs.
--
-- Before this migration the cache was stored in
-- backend/output/seen_urls_cache.json, which is ephemeral on Cloud Run.
-- The cache reset every run, so infrequent-publishing sources
-- (tii/g42/khazna/presight) kept re-yielding the same stale press
-- releases daily — all of which were then culled at date_filter.
-- Persisting the cache in Supabase fixes that root cause.
--
-- Applied to production on 2026-04-15 via the Supabase MCP. This file
-- is the idempotent definition so local / CI environments and future
-- branch rebuilds stay consistent with the deployed schema.

CREATE TABLE IF NOT EXISTS public.scout_seen_urls (
  collector_name text NOT NULL,
  url text NOT NULL,
  first_seen_at timestamptz NOT NULL DEFAULT now(),
  last_seen_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (collector_name, url)
);

CREATE INDEX IF NOT EXISTS scout_seen_urls_collector_idx
  ON public.scout_seen_urls (collector_name);

-- Mirror RLS posture of other pipeline tables (dropped_items,
-- pipeline_runs, event_memory): service role only, no public access.
ALTER TABLE public.scout_seen_urls ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE public.scout_seen_urls IS
  'Seen-URL cache for infrequent-publishing scouts (tii, g42, khazna, presight). Written by backend/pipeline/seen_cache.py each run; read to skip already-yielded URLs on the next run.';
