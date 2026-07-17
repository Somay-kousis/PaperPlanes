"""Tests for app.memory.db.retry: exponential-backoff retry on SQLSTATE 40001."""

import pytest

from app.memory.db.retry import RetriesExhaustedError, run_transaction


class SerializationFailure(Exception):
    """Stand-in for a driver exception carrying a 40001 SQLSTATE."""

    def __init__(self, message: str = "restart transaction: retry txn"):
        super().__init__(message)
        self.sqlstate = "40001"


class OtherDbError(Exception):
    """A non-retryable error, e.g. a unique constraint violation."""

    def __init__(self):
        super().__init__("duplicate key value")
        self.sqlstate = "23505"


def _no_sleep(_seconds: float) -> None:
    return None


def test_succeeds_on_first_try_without_retrying():
    calls = []

    def fn():
        calls.append(1)
        return "ok"

    result = run_transaction(fn, sleep=_no_sleep)
    assert result == "ok"
    assert len(calls) == 1


def test_retries_then_succeeds():
    attempts = {"count": 0}

    def fn():
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise SerializationFailure()
        return "success"

    result = run_transaction(fn, max_attempts=5, sleep=_no_sleep)
    assert result == "success"
    assert attempts["count"] == 3


def test_gives_up_after_max_attempts():
    attempts = {"count": 0}

    def always_fails():
        attempts["count"] += 1
        raise SerializationFailure()

    with pytest.raises(RetriesExhaustedError):
        run_transaction(always_fails, max_attempts=3, sleep=_no_sleep)

    assert attempts["count"] == 3


def test_non_retryable_error_propagates_immediately():
    attempts = {"count": 0}

    def fn():
        attempts["count"] += 1
        raise OtherDbError()

    with pytest.raises(OtherDbError):
        run_transaction(fn, max_attempts=5, sleep=_no_sleep)

    assert attempts["count"] == 1


def test_retryable_detected_via_message_substring():
    # Some drivers may not surface a clean .sqlstate attribute; the message
    # substring check is a fallback.
    attempts = {"count": 0}

    def fn():
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise RuntimeError("ERROR: restart transaction: retry txn (RETRY_SERIALIZABLE)")
        return "ok"

    result = run_transaction(fn, max_attempts=3, sleep=_no_sleep)
    assert result == "ok"


def test_invalid_max_attempts_raises():
    with pytest.raises(ValueError):
        run_transaction(lambda: "ok", max_attempts=0, sleep=_no_sleep)


def test_sleep_called_with_increasing_backoff():
    sleeps: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    attempts = {"count": 0}

    def fn():
        attempts["count"] += 1
        if attempts["count"] < 4:
            raise SerializationFailure()
        return "ok"

    run_transaction(
        fn, max_attempts=5, base_delay=0.1, max_delay=10.0, sleep=fake_sleep
    )
    assert len(sleeps) == 3
    # Full-jitter backoff: each sleep is in [0, base_delay * 2**attempt].
    assert 0 <= sleeps[0] <= 0.1
    assert 0 <= sleeps[1] <= 0.2
    assert 0 <= sleeps[2] <= 0.4
