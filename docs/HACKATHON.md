# Hackathon Tool Usage — CockroachDB × AWS "Build with Agentic Memory"

## CockroachDB tools used (requirement: ≥2)

1. **Distributed Vector Indexing** — `VECTOR(1024)` columns with C-SPANN vector indexes
   (`CREATE VECTOR INDEX ... (user_id, embedding)`, multi-tenant prefix pattern) power chunk
   retrieval, memory-note retrieval, entity dedup, and claim contradiction matching.
2. **Cloud Managed MCP Server** — the agent's `memory_introspect` tool: read-only, audited,
   schema-aware SQL over the agent's own memory store for meta-questions.
3. *(Bonus)* **ccloud CLI** — cluster provisioning script in `docs/PRODUCTION.md`.
4. *(Bonus)* **Agent Skills Repo** — used as a development-time aid in Claude Code.

## AWS services used (requirement: ≥1)

1. **Amazon Bedrock** — Amazon Nova Pro (chat agent + claim extraction), Nova Lite (fast
   entity/fact extraction and contradiction judging), Titan Text Embeddings V2 (1024-dim
   embeddings). Nova models bill through standard AWS consumption; the model IDs are a
   config swap (`BEDROCK_CHAT_MODEL_ID`/`BEDROCK_FAST_MODEL_ID`).
2. **Amazon S3** — PDF storage (private bucket, presigned GETs).
3. **Amazon EC2** — demo deployment (docker compose + Caddy HTTPS, IAM instance profile).

## Links

- Demo: _TBD_
- Video: _TBD_
