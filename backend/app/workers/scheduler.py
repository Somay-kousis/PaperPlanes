"""APScheduler wiring for the periodic reflection background job.

``start_scheduler()``/``stop_scheduler()`` are the two functions the app
orchestrator wires into the FastAPI lifespan (``app.main``'s
``lifespan()``) -- this module deliberately never imports or touches
``app.main`` itself. Interval is read directly from the
``REFLECTION_INTERVAL_SECONDS`` env var (default 600s / 10 minutes) rather
than through ``app.core.config.Settings``, so enabling/tuning this doesn't
require a config.py change; an interval <= 0 disables the scheduler
entirely (``start_scheduler()`` becomes a no-op returning ``None``).

Two safeguards on the scheduled job itself:

- **In-flight guard**: a module-level flag skips a tick outright if the
  previous cycle hasn't finished (on top of APScheduler's own
  ``max_instances=1``, which would otherwise just queue/drop the
  overlapping run silently) -- a reflection cycle should never run
  concurrently with itself.
- **Frequency cap**: the configured interval is clamped to
  ``MIN_INTERVAL_SECONDS`` even if misconfigured lower, and
  ``coalesce=True`` collapses any missed ticks (e.g. after the event loop
  was blocked) into a single catch-up run instead of firing repeatedly.
"""

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_SECONDS = 600
MIN_INTERVAL_SECONDS = 30

_scheduler: Any = None
_in_flight = False


def _interval_seconds() -> int:
    """Read+validate ``REFLECTION_INTERVAL_SECONDS``; defensive against bad env values.

    A non-integer value falls back to the default. A positive value is
    clamped up to ``MIN_INTERVAL_SECONDS`` (the frequency cap); a
    zero/negative value is returned as-is so the caller can treat it as
    "disabled" rather than silently clamping a deliberate opt-out.
    """
    raw = os.getenv("REFLECTION_INTERVAL_SECONDS", str(DEFAULT_INTERVAL_SECONDS))
    try:
        interval = int(raw)
    except ValueError:
        logger.warning(
            "Invalid REFLECTION_INTERVAL_SECONDS=%r; using default %ds",
            raw,
            DEFAULT_INTERVAL_SECONDS,
        )
        return DEFAULT_INTERVAL_SECONDS
    if interval <= 0:
        return interval
    return max(interval, MIN_INTERVAL_SECONDS)


async def _run_reflection_tick() -> None:
    """APScheduler job body: the in-flight guard lives here, not in the worker itself."""
    global _in_flight
    if _in_flight:
        logger.info("Reflection tick skipped -- previous cycle still in flight")
        return

    _in_flight = True
    try:
        from app.workers.reflection_worker import run_reflection_pass

        result = await run_reflection_pass(trigger_reason="scheduled")
        logger.info("Scheduled reflection cycle complete: %s", result)
    except Exception:
        # Belt-and-suspenders: run_reflection_pass already catches its own
        # failures, but a scheduled job raising would otherwise be logged
        # and swallowed silently deep inside APScheduler's executor.
        logger.warning("Scheduled reflection cycle failed", exc_info=True)
    finally:
        _in_flight = False


def build_scheduler() -> Any:
    """Construct (but do not start) an ``AsyncIOScheduler``."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    return AsyncIOScheduler()


def start_scheduler() -> Any | None:
    """Start the reflection-cycle background job.

    No-op (returns the existing scheduler) if already started. Returns
    ``None`` without constructing a scheduler at all if
    ``REFLECTION_INTERVAL_SECONDS <= 0`` (disabled).
    """
    global _scheduler

    if _scheduler is not None:
        logger.info("Reflection scheduler already running; start_scheduler() is a no-op")
        return _scheduler

    interval = _interval_seconds()
    if interval <= 0:
        logger.info("Reflection scheduler disabled (REFLECTION_INTERVAL_SECONDS <= 0)")
        return None

    scheduler = build_scheduler()
    scheduler.add_job(
        _run_reflection_tick,
        "interval",
        seconds=interval,
        id="reflection_cycle",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info("Reflection scheduler started (interval=%ds)", interval)
    return scheduler


def stop_scheduler() -> None:
    """Stop and clear the background scheduler, if running; safe to call repeatedly/idempotently."""
    global _scheduler
    if _scheduler is None:
        return
    try:
        _scheduler.shutdown(wait=False)
    except Exception:
        logger.warning("Error shutting down reflection scheduler", exc_info=True)
    finally:
        _scheduler = None
