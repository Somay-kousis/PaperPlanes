"""Paper upload/listing endpoints (Week 1).

Both ingestion entry points (direct PDF upload, arXiv id/URL) create a
``papers`` row (``status='pending'``), upload the source PDF to S3, and
then kick off ``build_ingestion_graph()`` in a background ``asyncio``
task -- the request returns 202 immediately with the paper's id/title/
status, and clients poll ``GET /api/papers/{id}/status`` (or list) to
watch it move through ``parsing -> embedding -> ready``/``failed``.
"""

import asyncio
import logging
import uuid
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.api.schema.papers import (
    ArxivIngestRequest,
    PaperCreateResponse,
    PaperListItem,
    PaperListOut,
    PaperStatusOut,
)
from app.core.graph.builder import build_ingestion_graph
from app.core.graph.state import IngestionState
from app.memory.db import papers_repo
from app.memory.db.users_repo import ensure_demo_user
from app.services import arxiv_service, s3_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/papers", tags=["papers"])

# Keep references to background ingestion tasks so they aren't garbage
# collected mid-flight; discarded automatically once each finishes.
_background_tasks: set[asyncio.Task[Any]] = set()


def _run_in_background(coro: Any) -> None:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def _run_ingestion(paper_id: str, user_id: str, s3_key: str) -> None:
    """Run the ingestion graph for one paper; never raises (all failures recorded on the row)."""
    try:
        await papers_repo.update_paper_status(paper_id, "parsing")
        graph = build_ingestion_graph()
        input_state: IngestionState = {
            "user_id": user_id,
            "paper_id": paper_id,
            "s3_key": s3_key,
            "status": "parsing",
        }
        await graph.ainvoke(input_state)
    except Exception as exc:
        logger.exception("Ingestion failed for paper %s", paper_id)
        try:
            await papers_repo.update_paper_status(paper_id, "failed", fail_reason=str(exc))
        except Exception:
            logger.exception("Also failed to record failure status for paper %s", paper_id)


@router.post("", status_code=202, response_model=PaperCreateResponse)
async def upload_paper(file: UploadFile = File(...)) -> PaperCreateResponse:
    """Upload a PDF for ingestion; ingestion runs in the background."""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    user_uuid = await ensure_demo_user()
    title = file.filename or "Untitled upload"
    paper_id = uuid.uuid4()
    s3_key = f"papers/{paper_id}.pdf"

    try:
        await papers_repo.insert_paper(
            paper_id=paper_id, user_id=user_uuid, s3_key=s3_key, title=title
        )
        await s3_service.upload_bytes(s3_key, data)
    except Exception as exc:
        logger.exception("Failed to create/upload paper")
        await _best_effort_delete(paper_id)
        raise HTTPException(status_code=503, detail=f"Could not start ingestion: {exc}") from exc

    _run_in_background(_run_ingestion(str(paper_id), str(user_uuid), s3_key))

    return PaperCreateResponse(id=str(paper_id), title=title, status="pending")


@router.post("/arxiv", status_code=202, response_model=PaperCreateResponse)
async def upload_paper_arxiv(payload: ArxivIngestRequest) -> PaperCreateResponse:
    """Ingest a paper by arXiv id/URL; ingestion runs in the background."""
    try:
        arxiv_id = arxiv_service.parse_arxiv_id(payload.arxiv_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    user_uuid = await ensure_demo_user()

    try:
        metadata = await arxiv_service.fetch_metadata(arxiv_id)
    except Exception as exc:
        logger.exception("Failed to fetch arXiv metadata for %s", arxiv_id)
        raise HTTPException(
            status_code=502, detail=f"Could not fetch arXiv metadata: {exc}"
        ) from exc

    title = metadata.get("title") or arxiv_id
    paper_id = uuid.uuid4()
    s3_key = f"papers/{paper_id}.pdf"

    try:
        await papers_repo.insert_paper(
            paper_id=paper_id,
            user_id=user_uuid,
            s3_key=s3_key,
            title=title,
            authors=metadata.get("authors"),
            arxiv_id=arxiv_id,
            published_at=metadata.get("published_at"),
        )
        pdf_bytes = await arxiv_service.download_pdf(arxiv_id)
        await s3_service.upload_bytes(s3_key, pdf_bytes)
    except Exception as exc:
        logger.exception("Failed to ingest arXiv paper %s", arxiv_id)
        await _best_effort_delete(paper_id)
        raise HTTPException(status_code=503, detail=f"Could not start ingestion: {exc}") from exc

    _run_in_background(_run_ingestion(str(paper_id), str(user_uuid), s3_key))

    return PaperCreateResponse(id=str(paper_id), title=title, status="pending")


async def _best_effort_delete(paper_id: uuid.UUID) -> None:
    try:
        await papers_repo.delete_paper(paper_id)
    except Exception:
        logger.exception("Failed to roll back paper row %s after setup failure", paper_id)


@router.get("", response_model=PaperListOut)
async def list_papers() -> PaperListOut:
    """List papers for the demo user."""
    user_uuid = await ensure_demo_user()
    rows = await papers_repo.list_papers(user_uuid)
    return PaperListOut(items=[PaperListItem(**row) for row in rows])


@router.get("/{paper_id}/status", response_model=PaperStatusOut)
async def get_paper_status(paper_id: str) -> PaperStatusOut:
    """Fetch a single paper's ingestion status/fail_reason/chunk_count."""
    row = await papers_repo.get_paper_status(paper_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown paper_id: {paper_id!r}")
    return PaperStatusOut(**row)


@router.delete("/{paper_id}", status_code=204, response_model=None)
async def delete_paper(paper_id: str) -> None:
    """Delete a paper's chunks and its row (the S3 object is left in place)."""
    await papers_repo.delete_paper(paper_id)
