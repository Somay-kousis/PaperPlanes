"""Tests for app.core.nodes.ingestion.chunk_node: chunking, page propagation."""

from app.core.nodes.ingestion.chunk_node import (
    chunk_node,
    chunk_pages,
    estimate_tokens,
)


def _page(page_number: int, text: str) -> dict:
    return {"page_number": page_number, "text": text}


def test_estimate_tokens_uses_four_chars_per_token():
    assert estimate_tokens("a" * 400) == 100
    assert estimate_tokens("") == 1  # floor of 1, never zero


def test_single_small_page_produces_one_chunk():
    pages = [_page(1, "A short paragraph that fits comfortably in one chunk.")]
    chunks = chunk_pages(pages)
    assert len(chunks) == 1
    assert chunks[0]["page_number"] == 1
    assert chunks[0]["chunk_index"] == 0


def test_chunks_respect_max_token_budget_roughly():
    # Many distinct paragraphs, each individually well under the max, so the
    # chunker's own flush-at-max logic (not the oversized hard-splitter)
    # governs sizing.
    paragraphs = [f"Paragraph number {i} with some more filler words here." for i in range(200)]
    pages = [_page(1, "\n\n".join(paragraphs))]
    chunks = chunk_pages(pages, min_tokens=500, max_tokens=800)

    assert len(chunks) > 1
    # Every chunk but possibly the last should be at/near the target size;
    # none should wildly exceed max_tokens (a couple hundred tokens of
    # slack is expected since we flush *after* crossing the threshold).
    for chunk in chunks[:-1]:
        assert chunk["token_count"] <= 800 + 200


def test_page_number_propagates_to_chunk_start_page():
    pages = [
        _page(1, "Short page one text."),
        _page(2, "Short page two text."),
    ]
    chunks = chunk_pages(pages)
    # Both pages are small enough to land in the same chunk; the chunk
    # should be tagged with the page it *started* on.
    assert chunks[0]["page_number"] == 1


def test_chunk_crossing_pages_keeps_starting_page_number():
    long_paragraph_page1 = "word " * 150  # ~150 tokens, well under max
    long_paragraph_page2 = "other " * 150
    pages = [_page(5, long_paragraph_page1), _page(6, long_paragraph_page2)]
    chunks = chunk_pages(pages, min_tokens=50, max_tokens=1000)
    assert chunks[0]["page_number"] == 5


def test_heading_starts_new_chunk_once_buffer_has_min_tokens():
    body = "word " * 150  # ~150 tokens -> estimate_tokens ~ len//4
    text = f"{body}\n\n## Methods\n\nSome methods text here."
    pages = [_page(1, text)]
    chunks = chunk_pages(pages, min_tokens=100, max_tokens=800)
    assert len(chunks) == 2
    assert chunks[1]["text"].startswith("## Methods")


def test_oversized_paragraph_is_hard_split():
    huge = "word " * 2000  # ~2000 tokens of unbroken text
    pages = [_page(1, huge)]
    chunks = chunk_pages(pages, min_tokens=500, max_tokens=800)
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk["token_count"] <= 800


def test_chunk_indices_are_sequential():
    pages = [_page(1, f"Paragraph {i}.\n\n" * 1) for i in range(5)]
    chunks = chunk_pages(pages)
    assert [c["chunk_index"] for c in chunks] == list(range(len(chunks)))


def test_chunk_node_marks_failed_when_no_pages():
    result = chunk_node({"pages": []})
    assert result["status"] == "failed"
    assert "fail_reason" in result


def test_chunk_node_short_circuits_on_prior_failure():
    result = chunk_node({"status": "failed", "fail_reason": "already broken"})
    assert result == {}


def test_chunk_node_returns_chunks_on_success():
    pages = [_page(1, "Some perfectly ordinary paragraph of text.")]
    result = chunk_node({"pages": pages})
    assert "chunks" in result
    assert len(result["chunks"]) == 1
