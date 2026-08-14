"""Tests for app.core.logging: the JSON formatter and request-id context."""

import json
import logging

import pytest

from app.core.logging import JSONFormatter, PlainFormatter, configure_logging, request_id_var


def _make_record(
    message: str = "hello", level: int = logging.INFO, extra: dict | None = None
) -> logging.LogRecord:
    record = logging.LogRecord(
        name="app.test",
        level=level,
        pathname="test.py",
        lineno=1,
        msg=message,
        args=None,
        exc_info=None,
    )
    if extra:
        for key, value in extra.items():
            setattr(record, key, value)
    return record


@pytest.fixture(autouse=True)
def _reset_request_id():
    """Ensure the request-id contextvar doesn't leak between tests."""
    token = request_id_var.set("")
    yield
    request_id_var.reset(token)


class TestJSONFormatter:
    def test_emits_valid_json_with_expected_fields(self):
        formatter = JSONFormatter()
        record = _make_record(message="hello world")

        output = formatter.format(record)
        payload = json.loads(output)

        assert payload["message"] == "hello world"
        assert payload["level"] == "INFO"
        assert payload["logger"] == "app.test"
        assert "timestamp" in payload and payload["timestamp"]

    def test_includes_extra_fields(self):
        formatter = JSONFormatter()
        record = _make_record(message="request completed", extra={"status_code": 200})

        payload = json.loads(formatter.format(record))

        assert payload["status_code"] == 200

    def test_request_id_present_when_contextvar_set(self):
        formatter = JSONFormatter()
        token = request_id_var.set("abc-123")
        try:
            record = _make_record()
            payload = json.loads(formatter.format(record))
        finally:
            request_id_var.reset(token)

        assert payload["request_id"] == "abc-123"

    def test_request_id_absent_when_contextvar_unset(self):
        formatter = JSONFormatter()
        record = _make_record()

        payload = json.loads(formatter.format(record))

        assert "request_id" not in payload

    def test_includes_exception_info(self):
        formatter = JSONFormatter()
        try:
            raise ValueError("boom")
        except ValueError:
            import sys

            record = logging.LogRecord(
                name="app.test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=1,
                msg="failed",
                args=None,
                exc_info=sys.exc_info(),
            )

        payload = json.loads(formatter.format(record))

        assert "ValueError" in payload["exc_info"]
        assert "boom" in payload["exc_info"]


class TestPlainFormatter:
    def test_output_is_not_json(self):
        formatter = PlainFormatter()
        record = _make_record(message="hello world")

        output = formatter.format(record)

        with pytest.raises(json.JSONDecodeError):
            json.loads(output)
        assert "hello world" in output
        assert "INFO" in output


class TestConfigureLogging:
    def test_default_format_is_json(self, monkeypatch):
        monkeypatch.delenv("LOG_FORMAT", raising=False)
        monkeypatch.delenv("LOG_LEVEL", raising=False)

        configure_logging()

        root = logging.getLogger()
        assert isinstance(root.handlers[0].formatter, JSONFormatter)

    def test_plain_format_env_var(self, monkeypatch):
        monkeypatch.setenv("LOG_FORMAT", "plain")

        configure_logging()

        root = logging.getLogger()
        assert isinstance(root.handlers[0].formatter, PlainFormatter)

        monkeypatch.delenv("LOG_FORMAT", raising=False)
        configure_logging()

    def test_log_level_env_var(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "WARNING")

        configure_logging()

        assert logging.getLogger().level == logging.WARNING

        monkeypatch.delenv("LOG_LEVEL", raising=False)
        configure_logging()

    def test_does_not_stack_handlers_on_repeated_calls(self):
        configure_logging()
        configure_logging()
        configure_logging()

        assert len(logging.getLogger().handlers) == 1
