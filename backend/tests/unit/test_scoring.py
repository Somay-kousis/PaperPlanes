"""Tests for app.memory.scoring: Ebbinghaus decay, reinforcement, combined score."""

import math

import pytest

from app.memory.scoring import combined_score, ebbinghaus_retention, reinforce


class TestEbbinghausRetention:
    def test_zero_elapsed_time_is_full_retention(self):
        assert ebbinghaus_retention(0, strength=10.0) == 1.0

    def test_retention_decays_monotonically_with_time(self):
        strength = 5.0
        r1 = ebbinghaus_retention(1.0, strength)
        r2 = ebbinghaus_retention(10.0, strength)
        r3 = ebbinghaus_retention(100.0, strength)
        assert r1 > r2 > r3

    def test_retention_increases_monotonically_with_strength(self):
        dt = 10.0
        r_weak = ebbinghaus_retention(dt, strength=1.0)
        r_strong = ebbinghaus_retention(dt, strength=100.0)
        assert r_strong > r_weak

    def test_matches_closed_form(self):
        dt, strength = 3.0, 7.0
        expected = math.exp(-dt / strength)
        assert ebbinghaus_retention(dt, strength) == pytest.approx(expected)

    def test_retention_bounded_in_zero_one(self):
        for dt in (0, 1, 50, 10_000):
            r = ebbinghaus_retention(dt, strength=3.0)
            assert 0.0 <= r <= 1.0

    def test_nonpositive_strength_returns_zero(self):
        assert ebbinghaus_retention(10.0, strength=0.0) == 0.0
        assert ebbinghaus_retention(10.0, strength=-1.0) == 0.0

    def test_negative_dt_treated_as_zero_elapsed(self):
        assert ebbinghaus_retention(-5.0, strength=10.0) == 1.0


class TestReinforce:
    def test_first_reinforcement_increases_strength(self):
        new_strength = reinforce(strength=10.0, access_count=0)
        assert new_strength > 10.0

    def test_diminishing_returns_across_reinforcements(self):
        s = 10.0
        boost_1 = reinforce(s, access_count=0) - s
        boost_2 = reinforce(s, access_count=1) - s
        boost_3 = reinforce(s, access_count=5) - s
        assert boost_1 > boost_2 > boost_3 > 0

    def test_reinforce_matches_formula(self):
        strength, access_count = 4.0, 2
        expected = strength * (1 + 1 / (access_count + 1))
        assert reinforce(strength, access_count) == pytest.approx(expected)

    def test_negative_access_count_raises(self):
        with pytest.raises(ValueError):
            reinforce(strength=1.0, access_count=-1)

    def test_nonpositive_strength_raises(self):
        with pytest.raises(ValueError):
            reinforce(strength=0.0, access_count=0)


class TestCombinedScore:
    def test_bounds_with_default_weights(self):
        # Default weights sum to 1.0, so with all-1 or all-0 inputs the
        # result stays within [0, 1].
        assert combined_score(1.0, 1.0, 1.0) == pytest.approx(1.0)
        assert combined_score(0.0, 0.0, 0.0) == pytest.approx(0.0)

    def test_matches_weighted_sum_formula(self):
        recency, importance, relevance = 0.9, 0.4, 0.6
        expected = 0.3 * recency + 0.3 * importance + 0.4 * relevance
        assert combined_score(recency, importance, relevance) == pytest.approx(expected)

    def test_relevance_weighted_more_than_others_by_default(self):
        # Bumping relevance alone should move the score more than bumping
        # recency or importance by the same amount, given default weights.
        base = combined_score(0.5, 0.5, 0.5)
        bump_relevance = combined_score(0.5, 0.5, 0.9) - base
        bump_recency = combined_score(0.9, 0.5, 0.5) - base
        assert bump_relevance > bump_recency

    def test_custom_weights_are_respected(self):
        score = combined_score(
            1.0, 0.0, 0.0, recency_weight=2.0, importance_weight=0.0, relevance_weight=0.0
        )
        assert score == pytest.approx(2.0)
