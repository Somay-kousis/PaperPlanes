-- Audit trail for every mutation made against the memory subsystem.

CREATE TABLE IF NOT EXISTS memory_audit_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  actor STRING NOT NULL,
  action STRING NOT NULL,
  target_table STRING NOT NULL, target_id UUID NOT NULL,
  reason STRING,
  details JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
