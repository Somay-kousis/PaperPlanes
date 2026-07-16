"""Structured (JSON) logging configuration and request-id context.

``configure_logging()`` installs a hand-rolled JSON formatter on the root
logger so every log line -- ours and any library's -- comes out as one JSON
object per line: easy to ship to CloudWatch/whatever and grep/query later.
Set ``LOG_FORMAT=plain`` for a human-readable line during local development.

The request-id context (``request_id_var``) is a ``contextvars.ContextVar``
populated by the request middleware in ``app.main``; the formatter picks it
up automatically when set, so any log line emitted while handling a request
carries its ``request_id`` without every call site needing to pass it
explicitly.
"""

from __future__ import annotations

import json
import logging
import os
from contextvars import ContextVar
from datetime import UTC, datetime

# Populated by the request middleware for the duration of a request; empty
# string outside of a request (e.g. at startup/shutdown or in a background
# task that hasn't been given a request id).
request_id_var: ContextVar[str] = ContextVar("request_id", default="")

# Attributes every ``logging.LogRecord`` carries by default. Anything else set
# on a record (i.e. passed via ``extra=``) is treated as caller-supplied
# structured context and folded into the JSON output.
_STANDARD_LOG_RECORD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__)


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects.

    Fields: ``timestamp`` (UTC ISO 8601), ``level``, ``logger``, ``message``,
    ``request_id`` (when set), plus any ``extra=`` fields passed by the
    caller. Exception info, if present, is rendered under ``exc_info``.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        request_id = request_id_var.get()
        if request_id:
            payload["request_id"] = request_id

        for key, value in record.__dict__.items():
            if key not in _STANDARD_LOG_RECORD_ATTRS and key not in payload:
                payload[key] = value

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


class PlainFormatter(logging.Formatter):
    """Human-readable formatter for local development (``LOG_FORMAT=plain``)."""

    def __init__(self) -> None:
        super().__init__(
            fmt="%(asctime)s %(levelname)-8s %(name)s [%(request_id)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )

    def format(self, record: logging.LogRecord) -> str:
        record.request_id = request_id_var.get() or "-"
        return super().format(record)


def configure_logging() -> None:
    """Install a structured formatter on the root logger.

    Respects ``LOG_LEVEL`` (default ``INFO``) and ``LOG_FORMAT`` (``json``
    default, or ``plain`` for local dev readability). Safe to call more than
    once (e.g. across test runs) -- it replaces any handlers it previously
    installed rather than stacking them.
    """
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    fmt = os.environ.get("LOG_FORMAT", "json").lower()

    formatter: logging.Formatter = PlainFormatter() if fmt == "plain" else JSONFormatter()

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [handler]
