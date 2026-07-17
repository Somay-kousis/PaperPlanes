"""Tests for citation/context-block assembly in app.core.nodes.chat.agent_node."""

from app.core.nodes.chat.agent_node import (
    _citations_from_chunks,
    _format_context_blocks,
)


def _chunk(**overrides):
    base = {
        "chunk_id": "chunk-1",
        "paper_id": "paper-1",
        "paper_title": "Attention Is All You Need",
        "page_number": 3,
        "text": "The Transformer architecture relies entirely on attention mechanisms.",
    }
    base.update(overrides)
    return base


def test_format_context_blocks_empty_when_no_chunks():
    assert _format_context_blocks([]) == "(No paper excerpts were retrieved for this turn.)"


def test_format_context_blocks_numbers_sequentially_from_one():
    chunks = [_chunk(chunk_id=f"c{i}", text=f"text {i}") for i in range(3)]
    blocks = _format_context_blocks(chunks)
    assert "[1] " in blocks
    assert "[2] " in blocks
    assert "[3] " in blocks
    assert blocks.index("[1]") < blocks.index("[2]") < blocks.index("[3]")


def test_format_context_blocks_includes_title_and_page():
    blocks = _format_context_blocks([_chunk()])
    assert "Attention Is All You Need" in blocks
    assert "p. 3" in blocks


def test_format_context_blocks_omits_page_when_missing():
    blocks = _format_context_blocks([_chunk(page_number=None)])
    assert "p. " not in blocks


def test_format_context_blocks_defaults_title_when_missing():
    blocks = _format_context_blocks([_chunk(paper_title=None)])
    assert "Untitled paper" in blocks


def test_citations_from_chunks_maps_fields():
    citations = _citations_from_chunks([_chunk()])
    assert citations == [
        {
            "chunk_id": "chunk-1",
            "paper_id": "paper-1",
            "paper_title": "Attention Is All You Need",
            "page_number": 3,
            "snippet": "The Transformer architecture relies entirely on attention mechanisms.",
        }
    ]


def test_citations_from_chunks_truncates_snippet_to_200_chars():
    long_text = "x" * 500
    citations = _citations_from_chunks([_chunk(text=long_text)])
    assert len(citations[0]["snippet"]) == 200


def test_citations_from_chunks_preserves_order():
    chunks = [_chunk(chunk_id=f"c{i}") for i in range(5)]
    citations = _citations_from_chunks(chunks)
    assert [c["chunk_id"] for c in citations] == [f"c{i}" for i in range(5)]


def test_citations_from_chunks_empty_list():
    assert _citations_from_chunks([]) == []
