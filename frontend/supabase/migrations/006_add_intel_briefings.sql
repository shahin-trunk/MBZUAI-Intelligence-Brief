-- Add intel_briefings column for pre-generated strategic Q&A cards
ALTER TABLE engagements ADD COLUMN IF NOT EXISTS intel_briefings jsonb;

-- Shape: array of { id, topic, question, answer, detail, status }
-- status: "pending" | "ready" | "error"
COMMENT ON COLUMN engagements.intel_briefings IS 'Pre-generated strategic intel Q&A cards for the engagement';
