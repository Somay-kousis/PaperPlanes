"""Tests for app.memory.retriever: ANN candidates -> rescoring -> reinforcement.

``score_candidates`` is pure and tested directly for ordering correctness.
``retrieve_and_reinforce`` is tested with ``notes_repo``/``audit`` swapped
for lightweight fakes (no DB) and an injectable ``embed_fn`` (no Titan/boto3
call), mirroring the style in ``tests/unit/test_writer.py``.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.memory.retriever import retrieve_and_reinforce, score_candidates

NOW = datetime.now(UTC)


def make_candidate(
    note_id: str,
    *,
    distance: float = 0.5,
    importance: float = 0.5,
    strength: float = 1.0,
    last_accessed_at: datetime | None = None,
    access_count: int = 0,
) -> dict[str, Any]:
    return {
        "id": note_id,
        "user_id": "user-1",
        "content": f"content for {note_id}",
        "importance": importance,
        "strength": strength,
        "last_accessed_at": last_accessed_at or NOW,
        "access_count": access_count,
        "distance": distance,
    }


# --------------------------------------------------------------------------
# score_candidates: pure scoring/ordering
# --------------------------------------------------------------------------


def test_score_candidates_empty_returns_empty():
    assert score_candidates([], now=NOW) == []


def test_score_candidates_orders_by_combined_score_descending():
    # High relevance (distance=0.1) + high importance should beat a
    # mediocre-relevance, low-importance note, even if slightly staler.
    strong = make_candidate("strong", distance=0.1, importance=0.9, strength=10.0)
    weak = make_candidate("weak", distance=1.4, importance=0.1, strength=10.0)

    scored = score_candidates([weak, strong], now=NOW)

    assert [c["id"] for c in scored] == ["strong", "weak"]
    assert scored[0]["score"] > scored[1]["score"]


def test_score_candidates_attaches_recency_relevance_score_fields():
    candidate = make_candidate("c1", distance=0.2, importance=0.5, strength=100.0)
    scored = score_candidates([candidate], now=NOW)
    row = scored[0]
    assert "recency" in row and "relevance" in row and "score" in row
    assert 0.0 <= row["recency"] <= 1.0
    assert -1.0 <= row["relevance"] <= 1.0


def test_score_candidates_does_not_mutate_input():
    candidate = make_candidate("c1")
    original = dict(candidate)
    score_candidates([candidate], now=NOW)
    assert candidate == original


def test_score_candidates_recency_decays_with_elapsed_time():
    # Same importance/relevance, but one was accessed long ago with low
    # strength -- it should decay and score lower than a freshly-accessed one.
    fresh = make_candidate(
        "fresh", distance=0.3, importance=0.5, strength=100.0, last_accessed_at=NOW
    )
    stale = make_candidate(
        "stale",
        distance=0.3,
        importance=0.5,
        strength=100.0,
        last_accessed_at=NOW - timedelta(days=30),
    )
    scored = score_candidates([fresh, stale], now=NOW)
    assert [c["id"] for c in scored] == ["fresh", "stale"]


def test_score_candidates_stable_relative_order_for_ties():
    a = make_candidate("a", distance=0.5, importance=0.5)
    b = make_candidate("b", distance=0.5, importance=0.5)
    scored = score_candidates([a, b], now=NOW)
    assert scored[0]["score"] == pytest.approx(scored[1]["score"])


# --------------------------------------------------------------------------
# retrieve_and_reinforce: wiring around notes_repo/audit
# --------------------------------------------------------------------------


class RetrieverRepo:
    def __init__(self, candidates: list[dict[str, Any]]):
        self.candidates = candidates
        self.search_calls: list[tuple[str, int]] = []
        self.reinforced: list[tuple[str, float, int]] = []
        self.audits: list[dict[str, Any]] = []

    async def search_similar_active_notes(self, user_id, embedding, *, limit=20):
        self.search_calls.append((user_id, limit))
        return self.candidates

    async def reinforce_note(self, note_id, *, new_strength, new_access_count):
        self.reinforced.append((note_id, new_strength, new_access_count))

    async def write_audit(self, conn_or_session=None, **kwargs):
        self.audits.append(kwargs)
        return "audit-1"


def wire(monkeypatch: pytest.MonkeyPatch, repo: RetrieverRepo) -> None:
    from app.memory import audit
    from app.memory.db import notes_repo

    monkeypatch.setattr(notes_repo, "search_similar_active_notes", repo.search_similar_active_notes)
    monkeypatch.setattr(notes_repo, "reinforce_note", repo.reinforce_note)
    monkeypatch.setattr(audit, "write_audit", repo.write_audit)


async def _embed_fn(text: str) -> list[float]:
    return [1.0, 0.0]


async def test_retrieve_returns_empty_when_no_candidates(monkeypatch):
    repo = RetrieverRepo([])
    wire(monkeypatch, repo)

    result = await retrieve_and_reinforce("user-1", "what do I know?", embed_fn=_embed_fn)

    assert result == []
    assert repo.reinforced == []
    assert repo.audits == []


async def test_retrieve_requests_active_notes_with_ann_limit(monkeypatch):
    repo = RetrieverRepo([make_candidate("c1")])
    wire(monkeypatch, repo)

    await retrieve_and_reinforce(
        "user-1", "query", ann_limit=42, top_k=5, embed_fn=_embed_fn
    )

    assert repo.search_calls == [("user-1", 42)]


async def test_retrieve_reinforces_and_audits_each_returned_note(monkeypatch):
    repo = RetrieverRepo([make_candidate("c1", strength=1.0, access_count=0)])
    wire(monkeypatch, repo)

    result = await retrieve_and_reinforce("user-1", "query", embed_fn=_embed_fn)

    assert [n["id"] for n in result] == ["c1"]
    assert repo.reinforced == [("c1", pytest.approx(2.0), 1)]
    assert repo.audits[0]["action"] == "read"
    assert repo.audits[0]["target_id"] == "c1"
    assert "score" in repo.audits[0]["details"]


async def test_retrieve_truncates_to_top_k(monkeypatch):
    candidates = [
        make_candidate(f"c{i}", distance=0.1 * i, importance=0.5) for i in range(10)
    ]
    repo = RetrieverRepo(candidates)
    wire(monkeypatch, repo)

    result = await retrieve_and_reinforce("user-1", "query", top_k=3, embed_fn=_embed_fn)

    assert len(result) == 3
    # Best relevance (lowest distance) should be first.
    assert result[0]["id"] == "c0"


async def test_retrieve_continues_when_reinforce_fails(monkeypatch):
    repo = RetrieverRepo([make_candidate("c1"), make_candidate("c2", distance=0.6)])

    async def failing_reinforce(note_id, *, new_strength, new_access_count):
        if note_id == "c1":
            raise RuntimeError("db down")
        repo.reinforced.append((note_id, new_strength, new_access_count))

    wire(monkeypatch, repo)
    monkeypatch.setattr(repo, "reinforce_note", failing_reinforce)
    from app.memory.db import notes_repo

    monkeypatch.setattr(notes_repo, "reinforce_note", failing_reinforce)

    result = await retrieve_and_reinforce("user-1", "query", embed_fn=_embed_fn)

    # Both notes are still returned even though c1's reinforcement raised.
    assert {n["id"] for n in result} == {"c1", "c2"}
    assert repo.reinforced == [("c2", pytest.approx(2.0), 1)]


async def test_retrieve_uses_embed_fn_not_real_titan_client(monkeypatch):
    repo = RetrieverRepo([make_candidate("c1")])
    wire(monkeypatch, repo)
    calls = []

    async def spy_embed(text):
        calls.append(text)
        return [0.5, 0.5]

    await retrieve_and_reinforce("user-1", "my query text", embed_fn=spy_embed)

    assert calls == ["my query text"]


async def test_retrieve_supports_sync_embed_fn(monkeypatch):
    repo = RetrieverRepo([make_candidate("c1")])
    wire(monkeypatch, repo)

    def sync_embed(text):
        return [1.0, 1.0]

    result = await retrieve_and_reinforce("user-1", "query", embed_fn=sync_embed)
    assert len(result) == 1
