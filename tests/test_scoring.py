#!/usr/bin/env python3
"""
Unit tests for scoring.py — TDD FIRST, implementation after.

Golden values per design.md §4:
- effective_weight, group_score (score+coverage), aggregate (renormalization),
  confidence = 0.6*coverage + 0.4*consistency, consistency MAD mapping,
- verdict bands (tasks.md 5.2), top_indicators by w*r*(s-0.5)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


def make_result(id, subscore, weight=10, reliability=1.0, available=True,
                group="technical", note=""):
    from ai_music_checker.signals import SignalResult

    return SignalResult(
        id=id, name=id.lower(), value=subscore, subscore=subscore,
        weight=weight, reliability=reliability, available=available,
        group=group, note=note,
    )


class TestEffectiveWeight:
    def test_available(self):
        from ai_music_checker.scoring import effective_weight

        assert effective_weight(8, 0.9, True) == pytest.approx(7.2)

    def test_unavailable_is_zero(self):
        from ai_music_checker.scoring import effective_weight

        assert effective_weight(8, 0.9, False) == 0.0


class TestGroupScore:
    def test_weighted_average_and_full_coverage(self):
        from ai_music_checker.scoring import group_score

        results = [
            make_result("T1", 0.8, weight=8),
            make_result("T2", 0.4, weight=4),
        ]
        score, coverage = group_score(results, "technical")
        expected = (8 * 0.8 + 4 * 0.4) / 12
        assert score == pytest.approx(expected)
        assert coverage == pytest.approx(1.0)

    def test_reliability_scales_weight(self):
        from ai_music_checker.scoring import group_score

        results = [
            make_result("T1", 1.0, weight=10, reliability=0.5),
            make_result("T2", 0.0, weight=10, reliability=1.0),
        ]
        score, _ = group_score(results, "technical")
        assert score == pytest.approx(0.5 / 1.5)

    def test_unavailable_signals_excluded_from_score(self):
        from ai_music_checker.scoring import group_score

        results = [
            make_result("T1", 0.9, available=True),
            make_result("C5", 1.0, available=False),
        ]
        _score, coverage = group_score(results, "context")
        assert coverage < 1.0

    def test_empty_group_returns_zeros(self):
        from ai_music_checker.scoring import group_score

        assert group_score([], "technical") == (0.0, 0.0)

    def test_all_unavailable_returns_zeros(self):
        from ai_music_checker.scoring import group_score

        results = [make_result("T1", 0.5, available=False)]
        assert group_score(results, "technical") == (0.0, 0.0)


class TestVerdictBands:
    @pytest.mark.parametrize("score,expected", [
        (0.00, "UNAUFFÄLLIG"),
        (0.20, "UNAUFFÄLLIG"),
        (0.21, "EHER MENSCHLICH"),
        (0.40, "EHER MENSCHLICH"),
        (0.41, "UNKLAR"),
        (0.60, "UNKLAR"),
        (0.61, "LIKELY AI-ASSISTED"),
        (0.80, "LIKELY AI-ASSISTED"),
        (0.81, "VERY LIKELY AI"),
        (1.00, "VERY LIKELY AI"),
    ])
    def test_bands(self, score, expected):
        from ai_music_checker.scoring import verdict

        assert verdict(score) == expected


class TestConsistencyConfidence:
    def test_identical_scores_full_consistency(self):
        from ai_music_checker.scoring import consistency

        assert consistency({"technical": 0.5, "metadata": 0.5}) == pytest.approx(1.0)

    def test_zero_scores_excluded_per_design(self):
        from ai_music_checker.scoring import consistency

        # design.md §4: zero-scored groups are ignored (empty group != disagreement)
        assert consistency({"a": 0.0, "b": 1.0}) == pytest.approx(1.0)

    def test_strong_disagreement_lowers_consistency(self):
        from ai_music_checker.scoring import consistency

        # mean 0.5, MAD 0.4 -> 1 - 0.8 = 0.2
        assert consistency({"a": 0.9, "b": 0.1}) == pytest.approx(0.2)

    def test_single_group_full_consistency(self):
        from ai_music_checker.scoring import consistency

        assert consistency({"technical": 0.3}) == pytest.approx(1.0)

    def test_confidence_formula(self):
        from ai_music_checker.scoring import confidence

        assert confidence(coverage=1.0, consistency_val=1.0) == pytest.approx(1.0)
        assert confidence(coverage=0.5, consistency_val=0.5) == pytest.approx(0.6 * 0.5 + 0.4 * 0.5)


class TestAggregate:
    def test_renormalizes_over_enabled_groups(self):
        from ai_music_checker.scoring import aggregate

        groups = {
            "technical": (0.5, 1.0),
            "metadata": (0.2, 1.0),
            "context": (0.9, 0.0),  # not enabled / no data
        }
        weights = {"technical": 40, "metadata": 25, "context": 35}
        result = aggregate(groups, weights, enabled_groups={"technical", "metadata"})
        assert result.ai_probability == pytest.approx((0.5 * 40 + 0.2 * 25) / 65)

    def test_no_enabled_groups_zero_probability(self):
        from ai_music_checker.scoring import aggregate

        result = aggregate({}, {"technical": 40}, enabled_groups=set())
        assert result.ai_probability == 0.0

    def test_result_fields_present(self):
        from ai_music_checker.scoring import aggregate

        groups = {"technical": (0.6, 1.0)}
        result = aggregate(groups, {"technical": 40}, enabled_groups={"technical"})
        assert 0.0 <= result.confidence <= 1.0
        assert result.verdict == verdict_of(0.6)


def verdict_of(score):
    from ai_music_checker.scoring import verdict

    return verdict(score)


class TestTopIndicators:
    def test_sorted_by_contribution_desc(self):
        from ai_music_checker.scoring import top_indicators

        results = [
            make_result("T1", 0.9, weight=10, reliability=1.0, note="hf energy high"),
            make_result("M1", 0.7, weight=5, reliability=1.0, note="watermark tag"),
            make_result("T2", 0.3, weight=8, reliability=1.0, note="low crest"),
        ]
        top = top_indicators(results, n=2)
        # deltas: T1=10*0.4=4.0, M1=5*0.2=1.0, T2=8*(-0.2)=-1.6 -> top2: T1, M1
        assert [t["id"] for t in top] == ["T1", "M1"]
        assert top[0]["delta"] == pytest.approx(4.0)
        assert top[1]["delta"] == pytest.approx(1.0)

    def test_only_positive_contributions(self):
        from ai_music_checker.scoring import top_indicators

        results = [make_result("T1", 0.2, weight=10)]  # delta = 10*(0.2-0.5) < 0
        assert top_indicators(results) == []

    def test_includes_note_text(self):
        from ai_music_checker.scoring import top_indicators

        results = [make_result("T1", 1.0, weight=10, note="mirror image found")]
        top = top_indicators(results)
        assert top[0]["note"] == "mirror image found"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
