"""arXiv lookup/download service.

Resolves an arXiv id (or a full ``abs``/``pdf`` URL containing one) to its
metadata (title, authors, published date) via the arXiv Atom API, and to
its PDF bytes via a direct download from ``arxiv.org``.
"""

import re
import xml.etree.ElementTree as ET
from datetime import date
from typing import Any

import httpx

_ATOM_NS = "{http://www.w3.org/2005/Atom}"

# Matches both old-style ("hep-th/9901001") and new-style ("2310.08560",
# optionally versioned "2310.08560v2") arXiv ids, wherever they appear in
# a bare id or a full arxiv.org URL.
_ARXIV_ID_RE = re.compile(r"(\d{4}\.\d{4,5}(?:v\d+)?|[a-z-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?)")


def parse_arxiv_id(value: str) -> str:
    """Extract a bare arXiv id from a bare id or a full arXiv URL.

    Raises ``ValueError`` if no id-shaped substring is found.
    """
    match = _ARXIV_ID_RE.search(value.strip())
    if not match:
        raise ValueError(f"Could not parse an arXiv id from: {value!r}")
    return match.group(1)


async def fetch_metadata(arxiv_id: str) -> dict[str, Any]:
    """Fetch paper metadata (title, authors, published_at) for an arXiv id."""
    url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()

    root = ET.fromstring(response.text)
    entry = root.find(f"{_ATOM_NS}entry")
    if entry is None:
        raise ValueError(f"No arXiv entry found for id {arxiv_id!r}")

    title_el = entry.find(f"{_ATOM_NS}title")
    title = " ".join(title_el.text.split()) if title_el is not None and title_el.text else None

    authors = [
        name_el.text.strip()
        for author_el in entry.findall(f"{_ATOM_NS}author")
        if (name_el := author_el.find(f"{_ATOM_NS}name")) is not None and name_el.text
    ]

    published_at: date | None = None
    published_el = entry.find(f"{_ATOM_NS}published")
    if published_el is not None and published_el.text:
        published_at = date.fromisoformat(published_el.text[:10])

    return {"title": title, "authors": authors, "published_at": published_at}


async def download_pdf(arxiv_id: str) -> bytes:
    """Download the PDF bytes for an arXiv id."""
    url = f"https://arxiv.org/pdf/{arxiv_id}"
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
    return response.content
