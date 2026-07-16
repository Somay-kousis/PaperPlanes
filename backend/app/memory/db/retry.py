"""Retry wrapper for CockroachDB serialization failures.

CockroachDB uses optimistic concurrency control and can abort a
transaction with SQLSTATE 40001 ("serialization failure" /
`retry transaction`) under contention. The standard mitigation is a
client-side retry loop with exponential backoff. ``run_transaction`` wraps
an arbitrary zero-arg callable (typically a closure that opens a
transaction, does work, and commits) and retries it on that specific
error class.
"""

import asyncio
import logging
import random
import time
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

# CockroachDB's SQLSTATE for serialization failures / transaction retry errors.
SERIALIZATION_FAILURE_SQLSTATE = "40001"


class RetriesExhaustedError(RuntimeError):
    """Raised when ``run_transaction`` exhausts its retry budget."""


def _is_retryable(exc: BaseException) -> bool:
    """Return True if ``exc`` looks like a CockroachDB serialization failure.

    Checks common attribute names used by psycopg/psycopg2/SQLAlchemy to
    surface a SQLSTATE code (``sqlstate``, ``pgcode``), falling back to a
    substring check on the message so hand-rolled test exceptions (or
    drivers we haven't special-cased) still work.
    """
    sqlstate = getattr(exc, "sqlstate", None) or getattr(exc, "pgcode", None)
    if sqlstate == SERIALIZATION_FAILURE_SQLSTATE:
        return True
    orig = getattr(exc, "orig", None)
    if orig is not None and orig is not exc:
        if _is_retryable(orig):
            return True
    message = str(exc)
    return SERIALIZATION_FAILURE_SQLSTATE in message or "restart transaction" in message.lower()


def run_transaction[T](
    fn: Callable[[], T],
    *,
    max_attempts: int = 5,
    base_delay: float = 0.1,
    max_delay: float = 2.0,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Run ``fn`` with exponential-backoff retry on serialization failures.

    ``fn`` should be idempotent from the caller's perspective (typically:
    open a transaction, do work, commit) since it may be invoked multiple
    times. Retries only trigger on errors that look like SQLSTATE 40001;
    any other exception propagates immediately.

    Backoff is ``base_delay * 2**attempt`` (capped at ``max_delay``) plus
    "full jitter" (a uniform random value in ``[0, computed_delay]``), the
    scheme recommended by AWS's exponential-backoff-and-jitter guidance to
    avoid thundering-herd retries under contention.

    Raises ``RetriesExhaustedError`` (chaining the last underlying
    exception) if ``max_attempts`` is reached without success.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    last_exc: BaseException | None = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - intentionally broad, filtered below
            if not _is_retryable(exc):
                raise
            last_exc = exc
            if attempt == max_attempts - 1:
                break
            delay = min(base_delay * (2**attempt), max_delay)
            jittered = random.uniform(0, delay)
            logger.warning(
                "Retrying transaction after serialization failure "
                "(attempt %d/%d, sleeping %.3fs): %s",
                attempt + 1,
                max_attempts,
                jittered,
                exc,
            )
            sleep(jittered)

    raise RetriesExhaustedError(
        f"Transaction did not succeed after {max_attempts} attempts"
    ) from last_exc


async def run_transaction_async[T](
    fn: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 5,
    base_delay: float = 0.1,
    max_delay: float = 2.0,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> T:
    """Async twin of ``run_transaction`` for coroutine-based DB calls.

    Identical retry/backoff semantics (same SQLSTATE 40001 detection, same
    full-jitter exponential backoff), but awaits ``fn`` and ``sleep``
    instead of calling them synchronously -- for the async SQLAlchemy
    engine used by the memory-notes repo, where a blocking ``time.sleep``
    would stall the event loop.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    last_exc: BaseException | None = None
    for attempt in range(max_attempts):
        try:
            return await fn()
        except Exception as exc:  # noqa: BLE001 - intentionally broad, filtered below
            if not _is_retryable(exc):
                raise
            last_exc = exc
            if attempt == max_attempts - 1:
                break
            delay = min(base_delay * (2**attempt), max_delay)
            jittered = random.uniform(0, delay)
            logger.warning(
                "Retrying async transaction after serialization failure "
                "(attempt %d/%d, sleeping %.3fs): %s",
                attempt + 1,
                max_attempts,
                jittered,
                exc,
            )
            await sleep(jittered)

    raise RetriesExhaustedError(
        f"Transaction did not succeed after {max_attempts} attempts"
    ) from last_exc
