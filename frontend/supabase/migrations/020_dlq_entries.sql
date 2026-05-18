-- Dead Letter Queue for Celery task failures.
-- Captures task failures when max retries are exhausted, enabling
-- operators to inspect, diagnose, and retry failed tasks.

CREATE TABLE IF NOT EXISTS dlq_entries (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    task_name text NOT NULL,           -- e.g. "generate_phrase_audio", "generate_item_audio"
    task_id text,                      -- Celery task ID for traceability
    target_date text,                  -- Brief date
    item_id text,                      -- Item identifier
    lang text,                         -- Target language (fr, ar, en)
    phrase_idx integer,                -- Phrase index within learning content
    script_idx integer,                -- Script index (1-4)
    error_type text NOT NULL,          -- Python exception class name
    error_message text NOT NULL,       -- Exception message (truncated to 2000 chars)
    traceback text,                    -- Optional full traceback
    task_args jsonb,                   -- Full task arguments for exact re-submission
    created_at timestamptz DEFAULT now(),
    retried_at timestamptz,            -- When a retry was attempted
    retry_count integer DEFAULT 0,     -- Number of retry attempts from DLQ
    resolved boolean DEFAULT false     -- True on successful retry or manual dismissal
);

CREATE INDEX idx_dlq_entries_resolved_created ON dlq_entries (resolved, created_at DESC);
CREATE INDEX idx_dlq_entries_item_id ON dlq_entries (item_id);
CREATE INDEX idx_dlq_entries_task_name ON dlq_entries (task_name);
