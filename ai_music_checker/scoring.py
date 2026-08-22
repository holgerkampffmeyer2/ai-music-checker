#!/usr/bin/env python3
"""Pure scoring functions: weights, group scores, aggregation, verdict, confidence."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ai_music_checker.signals import SignalResult


@dataclass
class AggregateResult:
    ai_probability: float
    verdict: str
    confidence: float
    coverage: float
    consistency: float
    groups: dict[str, tuple[float, float]]  # group -> (score, coverage)


def effective_weight(weight: int, reliability: float, available: bool = True) -> float:
    return weight * reliability * (1.0 if available else 0.0)


def group_score(results: list[SignalResult], group: str) -> tuple[float, float]:
    """Weighted subscore and coverage for one signal group."""
    group_results = [r for r in results if r.group == group]
    if not group_results:
        return (0.0, 0.0)
    avail_w = sum(
        effective_weight(r.weight, r.reliability, r.available) for r in group_results
    )
    if avail_w == 0:
        return (0.0, 0.0)
    score = sum(
        effective_weight(r.weight, r.reliability, r.available) * r.subscore
        for r in group_results
    ) / avail_w
    full_w = sum(effective_weight(r.weight, r.reliability, True) for r in group_results)
    coverage = avail_w / full_w if full_w > 0 else 0.0
    return (score, coverage)


VERDICT_BANDS: list[tuple[float, str]] = [
    (0.20, "UNAUFFÄLLIG"),
    (0.40, "EHER MENSCHLICH"),
    (0.60, "UNKLAR"),
    (0.80, "LIKELY AI-ASSISTED"),
    (float("inf"), "VERY LIKELY AI"),
]


def verdict(score: float) -> str:
    for upper, label in VERDICT_BANDS:
        if score <= upper:
            return label
    return VERDICT_BANDS[-1][1]


def consistency(group_scores: dict[str, float]) -> float:
    """Mean-absolute-deviation-based agreement between group scores (0..1)."""
    values = [s for s in group_scores.values() if s > 0]
    if len(values) < 2:
        return 1.0
    mean = sum(values) / len(values)
    mean_abs_dev = sum(abs(v - mean) for v in values) / len(values)
    return max(0.0, 1.0 - mean_abs_dev * 2)


def confidence(coverage: float, consistency_val: float) -> float:
    return 0.6 * coverage + 0.4 * consistency_val


def aggregate(
    group_scores: dict[str, tuple[float, float]],
    weights: dict[str, int],
    enabled_groups: set[str] | None = None,
) -> AggregateResult:
    """Renormalized weighted aggregate over enabled groups with coverage > 0."""
    active: dict[str, tuple[float, float]] = {}
    for name, pair in group_scores.items():
        if enabled_groups is not None and name not in enabled_groups:
            continue
        _score, cov = pair
        if weights.get(name, 0) > 0 and cov > 0:
            active[name] = pair

    total_weight = sum(weights[g] for g in active)
    probability = (
        sum(weights[g] * active[g][0] for g in active) / total_weight
        if total_weight > 0
        else 0.0
    )
    coverage = sum(active[g][1] for g in active) / len(active) if active else 0.0
    cons = consistency({g: active[g][0] for g in active})
    conf = confidence(coverage, cons)

    return AggregateResult(
        ai_probability=probability,
        verdict=verdict(probability),
        confidence=conf,
        coverage=coverage,
        consistency=cons,
        groups=dict(group_scores),
    )


def top_indicators(results: list[SignalResult], n: int = 3) -> list[dict[str, Any]]:
    """Signals with the largest positive contributions w*r*(s-0.5), sorted desc."""
    scored: list[tuple[float, SignalResult]] = []
    for r in results:
        if not r.available:
            continue
        delta = effective_weight(r.weight, r.reliability) * (r.subscore - 0.5)
        if delta > 0:
            scored.append((delta, r))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [
        {"id": r.id, "delta": round(delta, 4), "note": r.note}
        for delta, r in scored[:n]
    ]
