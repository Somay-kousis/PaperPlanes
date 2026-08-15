"""Tests for app.memory.db.vectorstore.normalize_embedding."""

import math

import pytest

from app.memory.db.vectorstore import normalize_embedding


def _l2_norm(vec: list[float]) -> float:
    return math.sqrt(sum(c * c for c in vec))


def test_normalized_vector_has_unit_l2_norm():
    vec = [3.0, 4.0]  # norm 5
    normalized = normalize_embedding(vec)
    assert _l2_norm(normalized) == pytest.approx(1.0)
    assert normalized == pytest.approx([0.6, 0.8])


def test_zero_vector_returned_unchanged():
    vec = [0.0, 0.0, 0.0]
    normalized = normalize_embedding(vec)
    assert normalized == [0.0, 0.0, 0.0]


def test_direction_preserved():
    vec = [1.0, 2.0, 2.0]  # norm 3
    normalized = normalize_embedding(vec)
    assert normalized == pytest.approx([1 / 3, 2 / 3, 2 / 3])


def test_already_unit_vector_is_stable():
    vec = [1.0, 0.0, 0.0]
    normalized = normalize_embedding(vec)
    assert normalized == pytest.approx([1.0, 0.0, 0.0])


def test_negative_components_handled():
    vec = [-3.0, 4.0]  # norm 5
    normalized = normalize_embedding(vec)
    assert _l2_norm(normalized) == pytest.approx(1.0)
    assert normalized == pytest.approx([-0.6, 0.8])


def test_high_dimensional_vector_normalizes_to_unit_norm():
    vec = [1.0] * 1024
    normalized = normalize_embedding(vec)
    assert _l2_norm(normalized) == pytest.approx(1.0)


def test_does_not_mutate_input():
    vec = [3.0, 4.0]
    original = list(vec)
    normalize_embedding(vec)
    assert vec == original
