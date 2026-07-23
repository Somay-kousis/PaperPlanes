-- Same fix as migration 006, applied to the claims vector index used by
-- cross-paper contradiction search (claims_repo.search_similar_active_claims).
--
-- That query filters user_id plus an equality on status='active' and orders by
-- embedding distance. With the original (user_id, embedding) index the status
-- predicate forces a FULL SCAN. Moving status into the vector index prefix lets
-- the index vector-search serve the (user_id, status)-filtered ANN directly.
--
-- Note to future editors: the migration runner splits statements on the
-- semicolon character before stripping dash-dash comment lines, so this comment
-- block must not contain a semicolon.

DROP INDEX IF EXISTS claims@claims_embedding_idx;
CREATE VECTOR INDEX IF NOT EXISTS claims_embedding_idx
  ON claims (user_id, status, embedding);
