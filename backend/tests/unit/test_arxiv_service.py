"""Tests for app.services.arxiv_service.parse_arxiv_id (pure, no network)."""

import pytest

from app.services.arxiv_service import parse_arxiv_id


@pytest.mark.parametrize(
    "value,expected",
    [
        ("2310.08560", "2310.08560"),
        ("2310.08560v2", "2310.08560v2"),
        ("https://arxiv.org/abs/2310.08560", "2310.08560"),
        ("http://arxiv.org/abs/2310.08560v1", "2310.08560v1"),
        ("https://arxiv.org/pdf/2310.08560", "2310.08560"),
        ("https://arxiv.org/pdf/2310.08560.pdf", "2310.08560"),
        ("  2310.08560  ", "2310.08560"),
        ("arxiv.org/abs/2310.08560v3", "2310.08560v3"),
    ],
)
def test_parse_arxiv_id_variants(value, expected):
    assert parse_arxiv_id(value) == expected


def test_parse_arxiv_id_rejects_garbage():
    with pytest.raises(ValueError):
        parse_arxiv_id("not an arxiv id at all")


def test_parse_arxiv_id_rejects_empty_string():
    with pytest.raises(ValueError):
        parse_arxiv_id("")
