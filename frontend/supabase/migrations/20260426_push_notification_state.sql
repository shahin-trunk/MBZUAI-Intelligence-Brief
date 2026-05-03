-- briefs.notified_at: set once when the first successful push fan-out completes
-- for this brief_date. Not reset on audio_status cycles (curation re-approval
-- flips audio_status back to 'pending' and then 'ready' again, but notified_at
-- stays set so the webhook does not duplicate-push).
ALTER TABLE briefs ADD COLUMN IF NOT EXISTS notified_at timestamptz;

COMMENT ON COLUMN briefs.notified_at IS
  'Set once when the first successful push fan-out completes for this brief_date. Not reset on audio_status re-approval cycles.';

CREATE INDEX IF NOT EXISTS briefs_pending_notify_idx
  ON briefs (brief_date)
  WHERE notified_at IS NULL;

-- push_tokens.environment: sandbox (TestFlight / dev builds) vs production
-- (App Store). Needed so TestFlight testers and prod users can coexist — the
-- Edge Function routes each token to api.sandbox.push.apple.com or
-- api.push.apple.com based on this column.
ALTER TABLE push_tokens
  ADD COLUMN IF NOT EXISTS environment text NOT NULL DEFAULT 'production'
  CHECK (environment IN ('production', 'sandbox'));

ALTER TABLE push_tokens DROP CONSTRAINT IF EXISTS push_tokens_user_id_token_key;
ALTER TABLE push_tokens
  ADD CONSTRAINT push_tokens_user_id_token_env_key
  UNIQUE (user_id, token, environment);
