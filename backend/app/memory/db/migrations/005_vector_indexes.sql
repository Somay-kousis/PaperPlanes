-- Vector indexes for similarity search, plus secondary indexes supporting
-- the memory engine's common access patterns.
--
-- Note: `CREATE INDEX IF NOT EXISTS` requires an explicit index name in
-- CockroachDB (as in Postgres) -- an anonymous `CREATE INDEX ON ...`
-- cannot be combined with `IF NOT EXISTS` since there would be nothing to
-- check existence against. The secondary indexes below are therefore
-- given explicit names, deviating from the unnamed form in the original
-- spec text.

CREATE VECTOR INDEX IF NOT EXISTS chunks_embedding_idx   ON chunks       (user_id, embedding);
CREATE VECTOR INDEX IF NOT EXISTS notes_embedding_idx    ON memory_notes (user_id, embedding);
CREATE VECTOR INDEX IF NOT EXISTS entities_embedding_idx ON entities     (user_id, embedding);
CREATE VECTOR INDEX IF NOT EXISTS claims_embedding_idx   ON claims       (user_id, embedding);

CREATE INDEX IF NOT EXISTS memory_notes_user_status_valid_idx
  ON memory_notes (user_id, status, valid_at);

CREATE INDEX IF NOT EXISTS claims_user_status_subject_idx
  ON claims (user_id, status, subject_entity_id);

CREATE INDEX IF NOT EXISTS memory_links_source_note_idx
  ON memory_links (source_note_id);

CREATE INDEX IF NOT EXISTS memory_audit_log_user_target_created_idx
  ON memory_audit_log (user_id, target_id, created_at);
