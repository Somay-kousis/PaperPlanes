# Memory-eval suite

LongMemEval-style probes that exercise the **real, running** PaperPlanes
stack over HTTP -- not mocks, not unit tests against `app.*` internals.
A green scorecard is evidence the CockroachDB-backed memory engine
actually drives agent behavior end to end.

## Running it

```bash
cd backend
docker compose up -d   # from the repo root, if not already running
.venv/bin/python -m tests.eval.run_eval
```

Configure the target with `PAPERPLANES_BASE_URL` (defaults to
`http://localhost:8000`):

```bash
PAPERPLANES_BASE_URL=http://localhost:8000 .venv/bin/python -m tests.eval.run_eval
```

The runner checks `GET /api/readyz` first; if the stack isn't up it
prints an error and exits `2` without hanging on the first probe. It
exits `1` if any probe fails, `0` if all pass.

## What each probe demonstrates

1. **Knowledge-update / contradiction** (`probe_contradiction`) -- uploads
   two tiny synthetic PDFs making conflicting claims about the same
   fictitious system's score on the same fictitious benchmark (unique
   names per run, so it never collides with seeded demo data or a prior
   run), ingests them **sequentially** (concurrent ingestion isn't
   process-safe -- PyMuPDF4LLM's parser holds a process-global lock), and
   asserts `GET /api/contradictions` surfaces a row whose two claims trace
   back to those two papers. Cleans up both papers afterward (best
   effort) so repeated runs don't accumulate test data.

2. **Temporal point-in-time (`as_of`)** (`probe_temporal`) --
   `GET /api/memory/notes?as_of=...` reconstructs *transaction-time*
   state (`created_at <= as_of AND (expired_at IS NULL OR expired_at >
   as_of)`). Asserts the note set visible "now" differs from the note set
   visible at an instant before the earliest current note existed --
   proving bi-temporal time travel, not just a status filter. Falls back
   to a structural check (endpoint accepts `as_of`, returns a well-formed
   result) if no notes exist yet to time-travel across.

3. **Decision-driving (cross-session)** (`probe_decision_driving`) -- the
   money shot. States a fact (a made-up cloud-provider preference, unique
   per run) in session 1, then asks a dependent question in a **brand
   new** session 2 that shares no checkpointer history with session 1.
   Asserts the answer reflects the fact -- proving memory changes
   behavior across sessions, not just within one conversation's context
   window. Contrasts against a control: a third new session asked an
   unrelated question, where the fact must *not* leak in, proving
   retrieval is selective rather than the model just repeating everything
   it's ever seen.

4. **Abstention** (`probe_abstention`) -- asks about a paper/benchmark
   that was never ingested (a fabricated name unique to this run) and
   asserts the reply hedges (or at least doesn't fabricate a confident
   score for it) rather than confidently inventing an answer.

## Files

- `support.py` -- shared HTTP/PDF/polling helpers (`ProbeResult`,
  `make_pdf_bytes`, `wait_for_paper_ready`, session/message helpers).
- `probes.py` -- the four probe implementations (`ALL_PROBES`).
- `run_eval.py` -- the CLI entrypoint (`python -m tests.eval.run_eval`).

## Design notes

- Every probe mixes a fresh `uuid.uuid4().hex[:8]` token into whatever
  content it writes (paper text, chat facts, fictitious paper/benchmark
  names) so the suite is safe to re-run against a live, already-seeded
  backend: nothing it asserts on can match a prior run's data or the
  demo seed data by accident.
- Probes run sequentially in `run_eval.py`, not concurrently -- partly
  because probe 1 must ingest its two papers one at a time anyway, and
  partly to keep the scorecard's timings and any failure easy to read.
- This suite is intentionally *not* pytest: it's a submission artifact
  meant to be run against the live demo stack and read as a scorecard,
  not wired into CI (there is no fixture standing up a fresh backend
  here -- see `tests/unit` and `tests/integration` for that kind of test).
