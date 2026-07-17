"""The four LongMemEval-style probes.

Each probe is an independent async function ``(client) -> ProbeResult``
that drives the real running stack over HTTP -- no mocking, no direct
``app.*`` imports. See the module docstring in ``run_eval.py`` (and
``README.md``) for what each one demonstrates and how to run them.
"""

from __future__ import annotations

import re
import time
import uuid
from datetime import UTC, datetime, timedelta

import httpx

from tests.eval.support import (
    IngestionFailed,
    IngestionTimedOut,
    ProbeResult,
    create_session,
    delete_paper_best_effort,
    make_pdf_bytes,
    send_message,
    upload_pdf,
    wait_for_paper_ready,
)

_HEDGE_PHRASES = [
    "don't have",
    "do not have",
    "no information",
    "not mention",
    "cannot provide",
    "can't provide",
    "unable to find",
    "no record",
    "not aware",
    "don't know",
    "do not know",
    "not contain",
    "couldn't find",
    "could not find",
    "no details",
    "not able to",
    "haven't come across",
    "have not come across",
    "no such paper",
]


def _elapsed(start: float) -> float:
    return round(time.monotonic() - start, 2)


async def probe_contradiction(client: httpx.AsyncClient) -> ProbeResult:
    """Probe 1: knowledge-update / contradiction.

    Uploads two tiny synthetic PDFs that make conflicting claims about
    MemGPT's score on the same (fictitious, unique-per-run) benchmark
    (ingested sequentially -- concurrent ingestion is not process-safe),
    polls each to ``ready``, then asserts ``GET /api/contradictions``
    surfaces a row linking a claim from each paper.

    The claim's *subject* is deliberately the real, well-known "MemGPT"
    name rather than a fully fabricated one: cross-paper contradiction
    detection ranks candidates by ``subject_entity_id`` match first (see
    ``app.memory.db.claims_repo.search_similar_active_claims``), which
    depends on the entity-resolution/dedup step recognizing both
    mentions as the same entity -- a well-known name gives the
    entity/claim-extraction models a much more reliable target to
    resolve consistently than an ad hoc invented one. Only the
    benchmark name and scores are unique per run.
    """
    name = "1. knowledge-update / contradiction"
    start = time.monotonic()
    token = uuid.uuid4().hex[:8]
    benchmark_name = f"WidgetQA-{token}"

    paper_a_pdf = make_pdf_bytes(
        title=f"EvalMemGPT-{token}: Benchmarking a Memory-Augmented Agent",
        body=(
            f"Abstract. We evaluate MemGPT on the {benchmark_name} document "
            f"question-answering benchmark. MemGPT achieves 89% accuracy on "
            f"{benchmark_name}, a state-of-the-art result that outperforms all "
            "prior baselines by a wide margin.\n\n"
            f"1. Results. MemGPT achieves 89% accuracy on the {benchmark_name} "
            "benchmark, outperforming all prior baselines we compared against."
        ),
    )
    paper_b_pdf = make_pdf_bytes(
        title=f"MemGPT-{token} Recheck: A Reproduction Study",
        body=(
            f"Abstract. We reproduce the MemGPT evaluation on the "
            f"{benchmark_name} benchmark and find substantially weaker "
            f"performance. MemGPT achieves only 42% accuracy on "
            f"{benchmark_name}. Contrary to the original report, we do not "
            "observe state-of-the-art results.\n\n"
            f"1. Results. In our runs MemGPT achieves 42% accuracy on the "
            f"{benchmark_name} benchmark, far below previously reported numbers."
        ),
    )

    paper_id_a: str | None = None
    paper_id_b: str | None = None
    try:
        created_a = await upload_pdf(client, f"A_EvalMemGPT_{token}.pdf", paper_a_pdf)
        paper_id_a = created_a["id"]
        await wait_for_paper_ready(client, paper_id_a)

        # Sequential on purpose: ingest one paper fully before starting the
        # next -- concurrent ingestion is not process-safe (see
        # app.services.pdf_service's parse lock docstring).
        created_b = await upload_pdf(client, f"B_MemGPT_Recheck_{token}.pdf", paper_b_pdf)
        paper_id_b = created_b["id"]
        await wait_for_paper_ready(client, paper_id_b)

        response = await client.get("/api/contradictions", params={"limit": 500})
        response.raise_for_status()
        items = response.json()["items"]

        expected_pair = {paper_id_a, paper_id_b}
        match = next(
            (
                item
                for item in items
                if {item["claim_a"]["paper_id"], item["claim_b"]["paper_id"]} == expected_pair
            ),
            None,
        )

        if match is None:
            return ProbeResult(
                name=name,
                passed=False,
                detail=(
                    f"no contradiction found linking paper {paper_id_a} and {paper_id_b} "
                    f"(subject='MemGPT', benchmark={benchmark_name!r}); "
                    f"{len(items)} contradiction(s) total on the server"
                ),
                duration_s=_elapsed(start),
            )

        return ProbeResult(
            name=name,
            passed=True,
            detail=(
                f"contradiction {match['id']} links {match['claim_a']['statement']!r} vs "
                f"{match['claim_b']['statement']!r}: {match['rationale']}"
            ),
            duration_s=_elapsed(start),
        )
    except (IngestionFailed, IngestionTimedOut, httpx.HTTPError) as exc:
        return ProbeResult(
            name=name,
            passed=False,
            detail=f"error: {exc}",
            duration_s=_elapsed(start),
            error=str(exc),
        )
    finally:
        if paper_id_a:
            await delete_paper_best_effort(client, paper_id_a)
        if paper_id_b:
            await delete_paper_best_effort(client, paper_id_b)


async def probe_temporal(client: httpx.AsyncClient) -> ProbeResult:
    """Probe 2: temporal point-in-time (``as_of``).

    ``GET /api/memory/notes`` reconstructs transaction-time state
    (``created_at <= as_of AND (expired_at IS NULL OR expired_at >
    as_of)``) when ``as_of`` is given. Asserts the note set visible "now"
    differs from the note set visible at an instant before any current
    note existed -- bi-temporal time travel. Falls back to a structural
    check (endpoint accepts ``as_of``, returns a well-formed result) if no
    notes exist yet to time-travel across.
    """
    name = "2. temporal point-in-time (as_of)"
    start = time.monotonic()
    try:
        now_iso = datetime.now(UTC).isoformat()
        now_resp = await client.get(
            "/api/memory/notes", params={"as_of": now_iso, "limit": 500}
        )
        now_resp.raise_for_status()
        now_items = now_resp.json()["items"]

        if not now_items:
            return ProbeResult(
                name=name,
                passed=True,
                detail=(
                    "no memory notes exist yet; verified GET /api/memory/notes accepts "
                    "`as_of` and returns a well-formed (empty) result -- bi-temporal "
                    "filtering could not be exercised against real data"
                ),
                duration_s=_elapsed(start),
            )

        created_ats = [
            datetime.fromisoformat(item["created_at"].replace("Z", "+00:00"))
            for item in now_items
        ]
        earliest = min(created_ats)
        before_iso = (earliest - timedelta(minutes=1)).isoformat()

        before_resp = await client.get(
            "/api/memory/notes", params={"as_of": before_iso, "limit": 500}
        )
        before_resp.raise_for_status()
        before_items = before_resp.json()["items"]

        now_ids = {item["id"] for item in now_items}
        before_ids = {item["id"] for item in before_items}

        passed = len(before_ids) < len(now_ids) and before_ids != now_ids
        detail = (
            f"{len(now_ids)} note(s) visible as_of=now vs {len(before_ids)} visible "
            f"as_of={before_iso} (1 minute before the earliest note's created_at); "
            f"sets differ: {passed}"
        )
        return ProbeResult(name=name, passed=passed, detail=detail, duration_s=_elapsed(start))
    except httpx.HTTPError as exc:
        return ProbeResult(
            name=name,
            passed=False,
            detail=f"error: {exc}",
            duration_s=_elapsed(start),
            error=str(exc),
        )


async def probe_decision_driving(client: httpx.AsyncClient) -> ProbeResult:
    """Probe 3 (the money shot): decision-driving memory.

    States a fact in session 1, then -- in a brand-new session 2 with no
    shared checkpointer history -- asks a question whose answer depends
    on that fact and asserts the reply reflects it. Contrasts against a
    control: a third, new session asked something unrelated, where the
    fact must NOT leak in -- proving memory selectively drives behavior
    rather than the model just parroting everything it's ever seen.
    """
    name = "3. decision-driving (cross-session)"
    start = time.monotonic()
    token = uuid.uuid4().hex[:8]
    marker = f"Cloudify-{token}"
    fact = f"For this project, my preferred cloud provider is {marker}."
    question = "What cloud provider do I prefer for this project?"
    control_question = "In general, what's a pleasant hobby to pick up on a rainy weekend?"

    try:
        session_fact = await create_session(client)
        await send_message(client, session_fact, fact)

        session_query = await create_session(client)
        query_reply = await send_message(client, session_query, question)
        query_text = query_reply["reply"]["content"]

        session_control = await create_session(client)
        control_reply = await send_message(client, session_control, control_question)
        control_text = control_reply["reply"]["content"]

        recalled = marker.lower() in query_text.lower()
        leaked_into_control = marker.lower() in control_text.lower()
        passed = recalled and not leaked_into_control

        detail = (
            f"stated {marker!r} in session {session_fact}; new session {session_query} "
            f"recalled it in its answer: {recalled}; control session {session_control} "
            f"(unrelated question) leaked the marker: {leaked_into_control}"
        )
        return ProbeResult(name=name, passed=passed, detail=detail, duration_s=_elapsed(start))
    except httpx.HTTPError as exc:
        return ProbeResult(
            name=name,
            passed=False,
            detail=f"error: {exc}",
            duration_s=_elapsed(start),
            error=str(exc),
        )


async def probe_abstention(client: httpx.AsyncClient) -> ProbeResult:
    """Probe 4: abstention.

    Asks about a paper/benchmark that was never ingested (a fabricated
    name unique to this run) and asserts the agent hedges rather than
    confidently inventing a specific score for it.
    """
    name = "4. abstention (never-ingested topic)"
    start = time.monotonic()
    token = uuid.uuid4().hex[:8]
    fake_paper = f"Zephyrine-Quorlax-{token}"
    fake_benchmark = f"GlimmerBench-{token}"
    question = (
        f"What accuracy did the paper '{fake_paper}' report on the "
        f"{fake_benchmark} evaluation?"
    )

    try:
        session_id = await create_session(client)
        reply = await send_message(client, session_id, question)
        text = reply["reply"]["content"]
        lowered = text.lower()

        hedged = any(phrase in lowered for phrase in _HEDGE_PHRASES)
        # Fallback: even without an explicit hedge phrase, the reply must not
        # fabricate a confident percentage tied to the fictitious paper.
        fabricated_number = bool(re.search(r"\d{1,3}(\.\d+)?\s*%", text)) and (
            fake_paper.lower() in lowered
        )
        passed = hedged or not fabricated_number

        detail = (
            f"asked about never-ingested {fake_paper!r}/{fake_benchmark!r}; "
            f"hedged={hedged}, fabricated a number for it={fabricated_number}; "
            f"reply: {text[:160]!r}"
        )
        return ProbeResult(name=name, passed=passed, detail=detail, duration_s=_elapsed(start))
    except httpx.HTTPError as exc:
        return ProbeResult(
            name=name,
            passed=False,
            detail=f"error: {exc}",
            duration_s=_elapsed(start),
            error=str(exc),
        )


ALL_PROBES = [
    probe_contradiction,
    probe_temporal,
    probe_decision_driving,
    probe_abstention,
]
