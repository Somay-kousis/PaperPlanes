-- Put status into the memory-notes vector index prefix so the live retrieval
-- query (user_id equality plus status='active' equality, ordered by
-- embedding distance) is served by an index vector-search instead of a full
-- scan.
--
-- The original index was (user_id, embedding). Filtering only user_id uses the
-- index, but adding the equality predicate on status (not in the index prefix)
-- makes the optimizer fall back to a FULL SCAN plus top-k, as confirmed via
-- EXPLAIN. C-SPANN vector indexes support equality prefix columns before the
-- vector column, so moving status into the prefix lets the vector-search node
-- serve the filtered ANN directly.
--
-- The temporal predicates were dropped from the retrieval query itself in
-- notes_repo.search_similar_active_notes, because an active status already
-- encodes current validity. Point-in-time reconstruction still applies the
-- temporal columns on the as_of path.

DROP INDEX IF EXISTS memory_notes@notes_embedding_idx;
CREATE VECTOR INDEX IF NOT EXISTS notes_embedding_idx
  ON memory_notes (user_id, status, embedding);
