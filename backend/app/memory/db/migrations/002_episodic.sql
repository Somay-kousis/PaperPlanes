-- Episodic memory: raw conversation/ingestion events, prior to
-- distillation into semantic memory notes/claims.

CREATE TABLE IF NOT EXISTS episodes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  session_id UUID REFERENCES sessions(id),
  type STRING NOT NULL,
  role STRING,
  content STRING NOT NULL,
  source_ref JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
