"""Shared helpers for the memory-eval probes: HTTP plumbing, PDF synthesis,
and the polling loops the probes need to wait on real ingestion/chat work.

Kept dependency-light on purpose (httpx + fitz/PyMuPDF, both already
project dependencies) -- this suite drives the real running stack over
HTTP, it does not import ``app.*`` directly.
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx

DEFAULT_BASE_URL = "http://localhost:8000"

# Bedrock-backed ingestion/chat calls are slow relative to a normal HTTP
# request (embedding + Nova Pro claim extraction/chat generation per
# chunk/turn); give every request generous headroom rather than tuning a
# fragile per-call timeout.
REQUEST_TIMEOUT_S = 120.0

PAPER_READY_TIMEOUT_S = 180.0
PAPER_POLL_INTERVAL_S = 2.0


def get_base_url() -> str:
    """Resolve the base URL to run probes against (env-overridable)."""
    return os.environ.get("PAPERPLANES_BASE_URL", DEFAULT_BASE_URL)


def make_client() -> httpx.AsyncClient:
    """Build the shared ``httpx.AsyncClient`` used by every probe."""
    return httpx.AsyncClient(base_url=get_base_url(), timeout=REQUEST_TIMEOUT_S)


@dataclass
class ProbeResult:
    """Outcome of a single probe, ready to render as one scorecard row."""

    name: str
    passed: bool
    detail: str
    duration_s: float
    error: str | None = None


@dataclass
class ProbeContext:
    """A unique per-run token/namespace so repeated runs don't collide.

    Every probe that writes new data (papers, chat facts) mixes this
    token into its content so re-running the suite against a live,
    already-seeded backend never matches on stale rows from a prior run
    or from demo seed data.
    """

    token: str = field(default_factory=lambda: uuid.uuid4().hex[:8])


def make_pdf_bytes(title: str, body: str) -> bytes:
    """Render a tiny one-page PDF with real, extractable text.

    Uses ``page.insert_textbox`` over a full-page rect (NOT
    ``page.insert_text`` at a point -- that draws along an unwrapped
    baseline and runs long lines off the page, so only the first few
    words survive extraction). Returns raw PDF bytes suitable for
    multipart upload.
    """
    import fitz

    doc = fitz.open()
    try:
        page = doc.new_page()
        rect = fitz.Rect(50, 50, page.rect.width - 50, page.rect.height - 50)
        text = f"{title}\n\n{body}"
        page.insert_textbox(rect, text, fontsize=11)
        return doc.tobytes()
    finally:
        doc.close()


# A fresh user id per eval run, so probes never accumulate memory notes on the
# shared demo user across runs (which degrades cross-session recall and makes the
# decision-driving probe flaky). All sessions in one run share it, so within-run
# cross-session recall still works; each run starts from an empty memory.
RUN_USER_ID = str(uuid.uuid4())


async def create_session(client: httpx.AsyncClient) -> str:
    """POST /api/sessions -> new session id (scoped to this run's isolated user)."""
    response = await client.post("/api/sessions", json={"user_id": RUN_USER_ID})
    response.raise_for_status()
    return response.json()["id"]


async def send_message(client: httpx.AsyncClient, session_id: str, content: str) -> dict[str, Any]:
    """POST /api/sessions/{id}/messages -> the full ChatReply body."""
    response = await client.post(
        f"/api/sessions/{session_id}/messages",
        json={"content": content, "user_id": RUN_USER_ID},
    )
    response.raise_for_status()
    return response.json()


async def upload_pdf(client: httpx.AsyncClient, filename: str, pdf_bytes: bytes) -> dict[str, Any]:
    """POST /api/papers (multipart upload) -> the 202 PaperCreateResponse body."""
    files = {"file": (filename, pdf_bytes, "application/pdf")}
    response = await client.post("/api/papers", files=files)
    response.raise_for_status()
    return response.json()


class IngestionFailed(RuntimeError):
    """Raised when a paper reaches ``status == "failed"`` while polling."""


class IngestionTimedOut(RuntimeError):
    """Raised when a paper never reaches a terminal status in time."""


async def wait_for_paper_ready(
    client: httpx.AsyncClient,
    paper_id: str,
    *,
    timeout_s: float = PAPER_READY_TIMEOUT_S,
    interval_s: float = PAPER_POLL_INTERVAL_S,
) -> dict[str, Any]:
    """Poll GET /api/papers/{id}/status until ``ready`` (or raise on ``failed``/timeout)."""
    deadline = time.monotonic() + timeout_s
    last_status: dict[str, Any] = {}
    while time.monotonic() < deadline:
        response = await client.get(f"/api/papers/{paper_id}/status")
        response.raise_for_status()
        last_status = response.json()
        status = last_status.get("status")
        if status == "ready":
            return last_status
        if status == "failed":
            raise IngestionFailed(
                f"paper {paper_id} failed to ingest: {last_status.get('fail_reason')!r}"
            )
        await asyncio.sleep(interval_s)
    raise IngestionTimedOut(
        f"paper {paper_id} did not reach 'ready' within {timeout_s}s (last: {last_status!r})"
    )


async def delete_paper_best_effort(client: httpx.AsyncClient, paper_id: str) -> None:
    """Best-effort cleanup so re-running the suite doesn't pile up demo papers."""
    try:
        await client.delete(f"/api/papers/{paper_id}")
    except Exception:
        pass
