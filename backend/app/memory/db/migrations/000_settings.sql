-- Cluster-level settings required for vector index support.
-- On CockroachDB Cloud (serverless/dedicated with restricted admin), this
-- SET CLUSTER SETTING may fail with an insufficient-privilege error because
-- tenants can't alter certain cluster settings themselves (the setting may
-- already be enabled cluster-wide, or must be enabled by the operator).
-- scripts/init_db.py treats a failure on this file as a non-fatal warning,
-- not a hard failure, and continues applying the remaining migrations.
SET CLUSTER SETTING feature.vector_index.enabled = true;
