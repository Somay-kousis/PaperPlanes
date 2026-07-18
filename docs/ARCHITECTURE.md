# PaperPlanes Memory Architecture

> Working draft — expanded as the engine is built. See the plan summary in README.

## The four memory tiers (CoALA), all in one CockroachDB cluster

| Tier | What | Where |
|---|---|---|
| Working | Active LangGraph state per session | `CockroachDBSaver` checkpoint tables (thread_id = session_id) |
| Episodic | Raw chat turns, reading events | `episodes` |
| Semantic | Facts, notes, entities, claims, reflections | `memory_notes`, `entities`, `claims`, `reflections` |
| Procedural | Prompts and agent skills (versioned) | `prompts/` (repo) + future `skills` table |

## Bi-temporal model (Zep)

Every memory row carries two timelines:

- **Event time**: `valid_at` / `invalid_at` — when the fact was true in the world.
- **Transaction time**: `created_at` / `expired_at` — when the system learned/retired it.

Contradicted knowledge is **invalidated, never deleted**. `GET /api/memory/notes?as_of=<ts>` reconstructs what the agent believed at any point in time.

## Write path (Mem0)

1. Haiku extracts atomic fact candidates from a turn / paper claims from a chunk.
2. Vector search (top-k) finds semantically adjacent existing memories.
3. An LLM tool-call decides per candidate: **ADD / UPDATE / INVALIDATE / NOOP**.
4. The decision is applied in one short transaction (never held across an LLM call) and audited.

## Retrieval scoring (Generative Agents + MemoryBank)

```
score = recency × importance × relevance
recency = e^(-Δt / S)        # Ebbinghaus retention; S = strength
```

Accessing a memory reinforces `S`; neglected memories decay and are eventually archived (soft) by the reflection worker.

## Contradiction detection

Claims are (subject_entity, predicate, object) triples with source chunk provenance.
At ingestion, new claims are vector-matched against active claims on the same entities;
a Haiku judge classifies contradicts/supports/unrelated. Contradictions flag both claims
as `disputed`, write a `contradictions` row with rationale, and surface in the UI.

## Reflection worker (Letta sleep-time compute)

Background pass, gated by an importance-sum threshold + frequency cap:
decay/archive → reflection generation (insights citing `derived_from`) → latent-contradiction sweep.

## Audit ("memory diff")

Every read/add/update/invalidate/archive by any actor (agent, user, reflection worker, MCP)
writes `memory_audit_log` with a before/after snapshot — rendered as a diff in the Memory Inspector.

## MCP self-introspection

The chat agent's `memory_introspect` tool talks to the CockroachDB Cloud **Managed MCP Server**
(`mcp:read` scope): schema discovery + read-only SQL over its own memory tables, audited server-side.
Used for meta-questions ("how many papers did I read this month?").

## Embedding normalization (important)

CockroachDB C-SPANN vector indexes accelerate **L2 only**. All embeddings are L2-normalized at a
single choke point (`memory/db/vectorstore.py`) — for unit vectors, L2 ordering ≡ cosine ordering.
