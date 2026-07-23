-- Semantic memory: distilled notes, entity/claim knowledge graph,
-- contradiction tracking, and higher-level reflections.

CREATE TABLE IF NOT EXISTS memory_notes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  content STRING NOT NULL,
  keywords STRING[] NOT NULL DEFAULT '{}', tags STRING[] NOT NULL DEFAULT '{}',
  context STRING,
  embedding VECTOR(1024) NOT NULL,
  importance FLOAT NOT NULL DEFAULT 0.5,
  strength FLOAT NOT NULL DEFAULT 1.0,
  last_accessed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  access_count INT NOT NULL DEFAULT 0,
  confidence FLOAT NOT NULL DEFAULT 0.7,
  is_user_stated BOOL NOT NULL DEFAULT false,
  source_episode_id UUID REFERENCES episodes(id),
  derived_from UUID[] NOT NULL DEFAULT '{}',
  status STRING NOT NULL DEFAULT 'active',
  valid_at TIMESTAMPTZ NOT NULL DEFAULT now(), invalid_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(), expired_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS memory_links (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_note_id UUID NOT NULL REFERENCES memory_notes(id),
  target_note_id UUID NOT NULL REFERENCES memory_notes(id),
  relation_type STRING NOT NULL,
  weight FLOAT NOT NULL DEFAULT 1.0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(), invalid_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS entities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  type STRING NOT NULL,
  canonical_name STRING NOT NULL,
  embedding VECTOR(1024) NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}',
  first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS entity_aliases (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_id UUID NOT NULL REFERENCES entities(id),
  alias STRING NOT NULL
);

CREATE TABLE IF NOT EXISTS claims (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  paper_id UUID NOT NULL REFERENCES papers(id),
  subject_entity_id UUID REFERENCES entities(id),
  predicate STRING NOT NULL,
  object_entity_id UUID REFERENCES entities(id),
  object_value STRING,
  statement STRING NOT NULL,
  source_chunk_id UUID REFERENCES chunks(id),
  embedding VECTOR(1024) NOT NULL,
  confidence FLOAT NOT NULL DEFAULT 0.7,
  status STRING NOT NULL DEFAULT 'active',
  valid_at TIMESTAMPTZ NOT NULL DEFAULT now(), invalid_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(), expired_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS contradictions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  claim_a_id UUID NOT NULL REFERENCES claims(id),
  claim_b_id UUID NOT NULL REFERENCES claims(id),
  rationale STRING NOT NULL,
  detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolved BOOL NOT NULL DEFAULT false, resolution_note STRING
);

CREATE TABLE IF NOT EXISTS reflections (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  content STRING NOT NULL,
  cites UUID[] NOT NULL DEFAULT '{}',
  trigger_reason STRING NOT NULL,
  importance FLOAT NOT NULL DEFAULT 0.5,
  embedding VECTOR(1024) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
