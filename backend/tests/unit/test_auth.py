"""Tests for the opt-in API-token gate (app.api.deps.require_api_token)."""

import pytest
from fastapi import HTTPException

from app.api import deps
from app.core import config


def _set_token(monkeypatch, value):
    """Point get_settings() at a Settings whose APP_API_TOKEN is ``value``."""
    settings = config.Settings(APP_API_TOKEN=value)
    monkeypatch.setattr(deps, "get_settings", lambda: settings)


async def test_no_token_configured_is_open(monkeypatch):
    _set_token(monkeypatch, None)
    # No exception even without any Authorization header.
    assert await deps.require_api_token(authorization=None) is None


async def test_correct_token_passes(monkeypatch):
    _set_token(monkeypatch, "s3cret")
    assert await deps.require_api_token(authorization="Bearer s3cret") is None


@pytest.mark.parametrize(
    "header",
    [None, "", "s3cret", "Bearer", "Bearer wrong", "Basic s3cret", "Bearer s3cretx"],
)
async def test_bad_token_rejected(monkeypatch, header):
    _set_token(monkeypatch, "s3cret")
    with pytest.raises(HTTPException) as exc:
        await deps.require_api_token(authorization=header)
    assert exc.value.status_code == 401


async def test_case_insensitive_scheme(monkeypatch):
    _set_token(monkeypatch, "s3cret")
    # Scheme is case-insensitive, token value is not.
    assert await deps.require_api_token(authorization="bearer s3cret") is None
