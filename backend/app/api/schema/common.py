"""Shared pydantic response models used across route modules."""

from typing import Any

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """Standard error body for stubbed/unimplemented endpoints and failures."""

    detail: str


class HealthStatus(BaseModel):
    """GET /api/healthz response body."""

    status: str
    checks: dict[str, Any]


class ReadyStatus(BaseModel):
    """GET /api/readyz response body."""

    ready: bool
    checks: dict[str, Any]
