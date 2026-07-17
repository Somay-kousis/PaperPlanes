"""PDF parsing service, built on ``pymupdf4llm`` + PyMuPDF (``fitz``).

Converts PDF bytes into page-aware markdown text -- one dict per page
(``{"page_number": int, "text": str}``, 1-indexed) -- and strips
everything from a detected References/Bibliography heading onward via a
cheap regex heuristic (not a layout-aware citation parser).
"""

import re
import threading
from typing import Any

_REFERENCES_HEADING_RE = re.compile(
    r"^#{0,3}\s*(references|bibliography|works cited)\s*$",
    re.IGNORECASE,
)

# pymupdf4llm.to_markdown loads a process-global onnxruntime model that is NOT
# thread-safe: two ingestions parsing concurrently (LangGraph runs the sync
# parse node in a threadpool, so parallel uploads land on separate threads)
# corrupt that shared state permanently -- after which EVERY subsequent parse
# in the worker returns empty ("no extractable text") until the process
# restarts. Serialising the parse behind this lock is the cheap, robust fix;
# parsing is fast and not the ingestion bottleneck, so the added contention is
# negligible.
_PARSE_LOCK = threading.Lock()


def pdf_to_markdown(pdf_bytes: bytes) -> list[dict[str, Any]]:
    """Convert PDF bytes to page-aware markdown, with references stripped.

    Returns a list of ``{"page_number": int, "text": str}`` dicts, one per
    kept page (1-indexed, document order). Raises ``ValueError`` if the
    PDF cannot be opened or parsed at all -- callers (``parse_node``)
    treat that as a fatal ingestion failure.
    """
    import fitz
    import pymupdf4llm

    # Serialise the whole open->to_markdown->close cycle: see _PARSE_LOCK.
    with _PARSE_LOCK:
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        except Exception as exc:
            raise ValueError(f"Could not open PDF: {exc}") from exc

        try:
            if doc.page_count == 0:
                raise ValueError("PDF has no pages")
            raw_pages = pymupdf4llm.to_markdown(doc, page_chunks=True)
        except Exception as exc:
            raise ValueError(f"Could not parse PDF content: {exc}") from exc
        finally:
            doc.close()

    pages = [
        {"page_number": page["metadata"]["page_number"], "text": page["text"]}
        for page in raw_pages
    ]
    return strip_references(pages)


def strip_references(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop pages at/after a detected References/Bibliography heading.

    Heuristic: scans each page's lines (in order) for one that looks like
    a standalone "References"/"Bibliography"/"Works Cited" heading
    (optionally markdown ``#``-prefixed, case-insensitive). The page
    containing the heading is truncated just before it; every subsequent
    page is dropped entirely. Not layout-aware -- a false-positive match
    would truncate more aggressively than intended, but this is an
    acceptable cheap heuristic for Week 1.
    """
    result = []
    for page in pages:
        lines = page["text"].splitlines()
        heading_index = next(
            (i for i, line in enumerate(lines) if _REFERENCES_HEADING_RE.match(line.strip())),
            None,
        )
        if heading_index is None:
            result.append(page)
            continue
        truncated_text = "\n".join(lines[:heading_index]).strip()
        result.append({"page_number": page["page_number"], "text": truncated_text})
        break
    return result
