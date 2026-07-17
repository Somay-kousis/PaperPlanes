"""chunk_node: splits parsed, page-aware paper text into embeddable chunks.

Section-aware, cheaply token-bounded (~500-800 tokens, using a
``len(text) // 4`` estimate rather than a real tokenizer -- good enough
for sizing, not for billing): paragraphs are grouped into a running
buffer, a chunk is flushed once the buffer crosses ``MAX_CHUNK_TOKENS``,
and a heading always starts a new chunk once the buffer already holds at
least ``MIN_CHUNK_TOKENS``. A pathological paragraph with no internal
breaks larger than ``MAX_CHUNK_TOKENS`` is hard-split on whitespace so no
single chunk balloons past the target. Each chunk keeps the page number
it started on.
"""

import re
from typing import Any

from app.core.graph.state import IngestionState

MIN_CHUNK_TOKENS = 500
MAX_CHUNK_TOKENS = 800

_CHARS_PER_TOKEN = 4
_HEADING_RE = re.compile(r"^#{1,6}\s+\S.*$")


def estimate_tokens(text: str) -> int:
    """Cheap token-count estimate: ~4 characters per token."""
    return max(1, len(text) // _CHARS_PER_TOKEN)


def _split_paragraphs(text: str) -> list[str]:
    """Split one page's text into paragraph units, keeping headings standalone."""
    paragraphs: list[str] = []
    current: list[str] = []

    def _flush() -> None:
        if current:
            paragraphs.append("\n".join(current).strip())
            current.clear()

    for line in text.splitlines():
        stripped = line.strip()
        if _HEADING_RE.match(stripped):
            _flush()
            paragraphs.append(stripped)
        elif stripped == "":
            _flush()
        else:
            current.append(line)
    _flush()
    return [p for p in paragraphs if p]


def _split_oversized(paragraph: str, max_tokens: int) -> list[str]:
    """Hard-split a paragraph with no internal breaks into ~max_tokens-sized pieces."""
    max_chars = max_tokens * _CHARS_PER_TOKEN
    words = paragraph.split(" ")
    pieces: list[str] = []
    current: list[str] = []
    current_len = 0
    for word in words:
        if current and current_len + len(word) + 1 > max_chars:
            pieces.append(" ".join(current))
            current, current_len = [], 0
        current.append(word)
        current_len += len(word) + 1
    if current:
        pieces.append(" ".join(current))
    return pieces


def chunk_pages(
    pages: list[dict[str, Any]],
    *,
    min_tokens: int = MIN_CHUNK_TOKENS,
    max_tokens: int = MAX_CHUNK_TOKENS,
) -> list[dict[str, Any]]:
    """Chunk page-aware text into ``~min_tokens``-``max_tokens``, page-tagged chunks.

    Returns a list of ``{"chunk_index", "page_number", "text", "token_count"}``
    dicts, in document order.
    """
    chunks: list[dict[str, Any]] = []
    buf_parts: list[str] = []
    buf_tokens = 0
    buf_page: int | None = None

    def _flush() -> None:
        nonlocal buf_parts, buf_tokens, buf_page
        if not buf_parts:
            return
        text = "\n\n".join(buf_parts)
        chunks.append(
            {"page_number": buf_page, "text": text, "token_count": estimate_tokens(text)}
        )
        buf_parts = []
        buf_tokens = 0
        buf_page = None

    for page in pages:
        page_number = page["page_number"]
        for paragraph in _split_paragraphs(page["text"]):
            is_heading = bool(_HEADING_RE.match(paragraph))
            paragraph_tokens = estimate_tokens(paragraph)

            if is_heading and buf_tokens >= min_tokens:
                _flush()

            if paragraph_tokens > max_tokens:
                _flush()
                for piece in _split_oversized(paragraph, max_tokens):
                    buf_page = page_number
                    buf_parts = [piece]
                    buf_tokens = estimate_tokens(piece)
                    _flush()
                continue

            if buf_page is None:
                buf_page = page_number
            buf_parts.append(paragraph)
            buf_tokens += paragraph_tokens

            if buf_tokens >= max_tokens:
                _flush()

    _flush()

    for index, chunk in enumerate(chunks):
        chunk["chunk_index"] = index
    return chunks


def chunk_node(state: IngestionState, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Split parsed, page-aware text into chunks suitable for embedding."""
    if state.get("status") == "failed":
        return {}

    chunks = chunk_pages(state.get("pages", []))
    if not chunks:
        return {"status": "failed", "fail_reason": "Chunking produced no chunks"}
    return {"chunks": chunks}
