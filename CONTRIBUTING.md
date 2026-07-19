# Contributing to PaperPlanes

This is a research-companion agent whose **memory is the product**. Before you touch
code, spend an hour understanding the memory model — the interesting parts aren't the
FastAPI routes or the React pages, they're the ~10 files in `backend/app/memory/`.

This guide is the fast path in: what to read, in what order, and the background that makes
it click.

---

## 1. Background reading (the papers)

You don't need all six deeply. Read the first three properly; skim the rest for the one
idea each contributes. Each maps directly onto code in this repo.

| # | Paper | The one idea | Where it lives |
|---|-------|--------------|----------------|
| **1** | **Mem0** — *Building Production-Ready AI Agents with Scalable Long-Term Memory* | The **ADD / UPDATE / INVALIDATE / NOOP** write path — memory as a decision, not an append | `memory/writer.py`, `core/prompts/memory_decision.md` |
| **2** | **Zep / Graphiti** — *A Temporal Knowledge Graph Architecture for Agent Memory* | **Bi-temporal**: invalidate, don't delete; query state `as_of` any time | `memory/db/notes_repo.py`, `migrations/003_semantic.sql` |
| **3** | **A-MEM** — *Agentic Memory for LLM Agents* | Notes carry keywords/tags/context + **links** between memories | `writer._generate_links`, `memory_links` table |
| 4 | **Generative Agents** (Stanford "Smallville") | Retrieval = **recency × importance × relevance** | `memory/scoring.py`, `memory/retriever.py` |
| 5 | **MemoryBank** | The **Ebbinghaus forgetting curve** (`R = e^(−Δt/S)`) | `scoring.ebbinghaus_retention` |
| 6 | **Letta / MemGPT** | Async **reflection** ("sleep-time compute") | `memory/reflection.py`, `app/workers/` |

**Framing:** the **CoALA** survey gives the four-tier taxonomy (working / episodic /
semantic / procedural) behind the pitch "all four tiers in one cluster." Read its taxonomy
figure, skip the rest.

> Short on time? **Mem0 + Zep** are the product's spine. Read those two and nothing else.

---

## 2. Tech stack — ranked by how much it matters here

**Must actually understand:**

- **CockroachDB specifics** (the differentiator, *not* "just Postgres"):
  - `VECTOR(1024)` + **C-SPANN vector indexes**, the `<->` L2 operator
  - **SERIALIZABLE** isolation → `SQLSTATE 40001` retries (why `memory/db/retry.py` exists)
  - Bi-temporal columns: `valid_at`/`invalid_at` (event time) vs `created_at`/`expired_at` (txn time)
  - **Recursive CTEs** for graph traversal (`memory/graph_traversal.py`)
- **LangGraph** — `StateGraph`, nodes, conditional edges, checkpointers. The whole app is
  two compiled graphs in `core/graph/builder.py`.
- **Embeddings & ANN basics** — cosine vs L2, and why we **normalize to unit vectors** so
  L2 order ≡ cosine order (`memory/db/vectorstore.normalize_embedding`).

**Know enough to navigate:** FastAPI (async routes + lifespan), asyncio (`to_thread`,
locks), Amazon Bedrock (Converse API, `with_structured_output`, Nova Pro/Lite + Titan),
Pydantic (structured LLM output, e.g. `MemoryDecision`).

**Skim / reference only:** React 19 + Vite (the demo surface), Docker Compose, S3/EC2, and
the Managed **MCP** Server (the agent runs read-only SQL over its own memory).

---

## 3. Reading order — follow the data, not the folders

Read the codebase the way a fact flows through it, not top-down by directory.

```
1. START HERE — the map
   backend/app/core/graph/builder.py       both graphs in ~120 lines; read the docstrings
   backend/app/memory/db/migrations/*.sql   the schema IS the data model (001 → 007 in order)

2. THE MEMORY ENGINE (the actual product)
   memory/scoring.py        pure math, no I/O — easiest entry, read first
   memory/writer.py         the Mem0 4-branch decision (the heart)
   memory/retriever.py      ANN + rescore + reinforce-on-read
   memory/db/notes_repo.py  supersede_note (atomic) + list_notes(as_of) — bi-temporal
   memory/db/retry.py       the SQLSTATE 40001 retry loop
   memory/contradiction.py  claim-vs-claim judge

3. HOW A CHAT TURN USES IT (chat graph, in edge order)
   core/nodes/chat/  load_context → retrieve → assemble_context
                     → agent → write_episodes → extract_facts → memory_write

4. HOW A PAPER GETS INGESTED (ingestion graph, in edge order)
   core/nodes/ingestion/  fetch → parse → chunk → embed → store_chunks
                          → extract_entities → extract_claims → contradiction_check

5. THE PROMPTS (what the LLM is actually asked)
   core/prompts/  memory_decision.md, claim_extraction.md, contradiction_judge.md

6. PROOF IT WORKS (read last — it validates everything above)
   tests/integration/test_core_features_live.py   the 10 real-row tests

7. THE WRITE-UP
   docs/ARCHITECTURE.md → docs/HACKATHON.md
```

**Fastest possible path:** `builder.py` docstrings → `003_semantic.sql` → `writer.py` →
`test_core_features_live.py`. Those four tell 80% of the story.

---

## 4. Running it locally

```bash
# full stack (CockroachDB v25.2 single-node + backend + frontend)
cp .env.example .env          # add AWS creds for real LLM calls; echo mode runs without them
docker compose up --build
docker compose exec backend python -m app.scripts.init_db
# open http://localhost/
```

Dev servers (hot reload):

```bash
cd backend  && uvicorn app.main:app --reload
cd frontend && npm install && npm run dev
```

The stack **self-degrades**: with no AWS creds it runs in echo mode, with no DB it compiles
the graph without a checkpointer. One compiled graph covers CI through full production — you
never branch between a "real" and a "fake" pipeline.

---

## 5. Checks before you push

**Backend** (Python 3.12, Ruff, line length 100, `asyncio_mode = auto`):

```bash
cd backend
ruff check .
pytest tests/unit tests/integration -q
```

**Frontend** (Oxlint):

```bash
cd frontend
npm run lint
npm run build
```

**The live suite** (real CockroachDB + real Bedrock — needs a DB and AWS creds; auto-skips
without them):

```bash
cd backend
DATABASE_URL="postgresql://root@localhost:26257/defaultdb?sslmode=disable" \
  pytest tests/integration/test_core_features_live.py -s -v
```

---

## 6. House rules

- **Invalidate, don't delete.** Never hard-delete a memory row. Contradicted knowledge is
  versioned out with `invalid_at`/`expired_at` so `as_of` history stays queryable.
- **Never hold a transaction open across an LLM call.** Decide first (LLM), then apply in
  one short transaction. See `writer._consolidate_one`.
- **Wrap every write path in `run_transaction`** (`memory/db/retry.py`) — CockroachDB will
  abort contended `SERIALIZABLE` txns with `40001`, and the retry is how 25/25 concurrent
  writers survive.
- **Normalize embeddings at exactly one choke point** (`vectorstore.normalize_embedding`).
  Unit vectors keep L2 ordering equivalent to cosine.
- **Audit every memory mutation** (`memory/audit.py`). The Memory Inspector's diff view is
  built entirely from `memory_audit_log`.
- **New nodes must self-degrade,** not raise — check `state["status"] == "failed"` and
  no-op, matching the existing ingestion nodes, so a paper always reaches a terminal state.

---

## 7. Where to look when…

| You want to change… | Start in |
|---|---|
| how facts are consolidated (the 4 branches) | `memory/writer.py` + `prompts/memory_decision.md` |
| how memories are ranked / decay | `memory/scoring.py`, `memory/retriever.py` |
| contradiction detection | `memory/contradiction.py`, `nodes/ingestion/contradiction_check_node.py` |
| the schema | `memory/db/migrations/*.sql` (add a new numbered file; migrations are ordered) |
| what the agent can do | `nodes/chat/agent_node.py` + the tools it carries |
| the API surface | `app/api/routes/` |
| the demo UI | `frontend/src/pages/` (Memory Inspector is the wow-factor) |
