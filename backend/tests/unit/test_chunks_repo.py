"""Tests for app.memory.db.chunks_repo: vector literal formatting + store_chunks wiring.

``store_chunks`` itself is exercised with the DB call mocked out (via
monkeypatching ``asyncio.to_thread``) so this stays a DB-free unit test.
"""

import math

import pytest

from app.memory.db.chunks_repo import format_vector_literal, store_chunks


def test_format_vector_literal_basic():
    assert format_vector_literal([0.1, 0.2]) == "[0.10000000,0.20000000]"


def test_format_vector_literal_negative_components():
    literal = format_vector_literal([-0.5, 0.25])
    assert literal == "[-0.50000000,0.25000000]"


def test_format_vector_literal_empty_vector():
    assert format_vector_literal([]) == "[]"


def test_format_vector_literal_is_bracketed_csv():
    literal = format_vector_literal([1.0, 2.0, 3.0])
    assert literal.startswith("[")
    assert literal.endswith("]")
    assert literal.count(",") == 2


def test_format_vector_literal_roundtrips_reasonably():
    vec = [1 / 3, -2 / 7, 0.0]
    literal = format_vector_literal(vec)
    parsed = [float(x) for x in literal.strip("[]").split(",")]
    for original, roundtripped in zip(vec, parsed, strict=True):
        assert math.isclose(original, roundtripped, abs_tol=1e-6)


async def test_store_chunks_returns_zero_for_empty_chunks():
    # No DB/thread work should happen at all for an empty batch.
    assert await store_chunks(user_id="u1", paper_id="p1", chunks=[]) == 0


async def test_store_chunks_builds_rows_and_delegates_to_thread(monkeypatch):
    captured = {}

    async def fake_to_thread(fn, dsn, rows):
        captured["dsn"] = dsn
        captured["rows"] = rows
        return len(rows)

    monkeypatch.setattr("app.memory.db.chunks_repo.asyncio.to_thread", fake_to_thread)

    chunks = [
        {
            "chunk_index": 0,
            "page_number": 1,
            "text": "hello",
            "token_count": 2,
            "embedding": [0.1, 0.2],
        },
        {
            "chunk_index": 1,
            "page_number": 2,
            "text": "world",
            "token_count": 2,
            "embedding": [0.3, 0.4],
        },
    ]
    count = await store_chunks(user_id="user-1", paper_id="paper-1", chunks=chunks)

    assert count == 2
    rows = captured["rows"]
    assert len(rows) == 2
    # (id, user_id, paper_id, chunk_index, page_number, text, token_count, embedding_literal)
    assert rows[0][1] == "user-1"
    assert rows[0][2] == "paper-1"
    assert rows[0][3] == 0
    assert rows[0][4] == 1
    assert rows[0][5] == "hello"
    assert rows[0][7] == "[0.10000000,0.20000000]"


async def test_store_chunks_propagates_thread_errors(monkeypatch):
    async def failing_to_thread(fn, dsn, rows):
        raise RuntimeError("db exploded")

    monkeypatch.setattr("app.memory.db.chunks_repo.asyncio.to_thread", failing_to_thread)

    with pytest.raises(RuntimeError):
        await store_chunks(
            user_id="u",
            paper_id="p",
            chunks=[{"chunk_index": 0, "page_number": 1, "text": "x", "embedding": [0.0]}],
        )
