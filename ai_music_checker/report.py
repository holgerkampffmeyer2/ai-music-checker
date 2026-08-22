#!/usr/bin/env python3
"""JSON report emitter (schema v1.0)."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from ai_music_checker.probe import FileProbe
from ai_music_checker.scoring import AggregateResult, top_indicators

SCHEMA_VERSION = "1.0"

_ENCODER_TAG_KEYS = ("encoder", "tsse", "writing_library", "software")


def _file_section(probe: FileProbe) -> Dict[str, Any]:
    return {
        "path": str(probe.path),
        "name": probe.path.name,
        "format": probe.format_name,
        "duration_s": probe.duration,
        "bitrate_bps": probe.bitrate,
        "sample_rate_hz": probe.sample_rate,
        "channels": probe.channels,
        "codec": probe.codec,
    }


def _provenance_section(probe: FileProbe) -> Dict[str, Any]:
    encoder = next(
        (probe.tags[k] for k in _ENCODER_TAG_KEYS if probe.tags.get(k)), None
    )
    return {
        "encoder": encoder,
        "tags_present": bool(probe.tags),
        "tag_keys": sorted(probe.tags.keys()),
        "has_cover_stream": probe.has_cover_stream,
    }


def _signals_section(results: List[Any]) -> List[Dict[str, Any]]:
    return [
        {
            "id": r.id,
            "name": r.name,
            "group": r.group,
            "value": round(r.value, 6),
            "subscore": round(r.subscore, 6),
            "weight": r.weight,
            "reliability": r.reliability,
            "available": r.available,
            "note": r.note,
        }
        for r in results
    ]


def _groups_section(agg: AggregateResult) -> Dict[str, Dict[str, float]]:
    return {
        group: {"score": round(score, 4), "coverage": round(cov, 4)}
        for group, (score, cov) in agg.groups.items()
    }


def _manual_research_hints(results: List[Any]) -> List[str]:
    hints = [
        f"{r.id} unavailable: {r.note or 'dependency missing'}"
        for r in results
        if not r.available
    ]
    return hints


def build(
    probe: FileProbe,
    results: List[Any],
    agg: AggregateResult,
    llm_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build the schema v1.0 analysis dict."""
    data: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "file": _file_section(probe),
        "provenance": _provenance_section(probe),
        "signals": _signals_section(results),
        "groups": _groups_section(agg),
        "result": {
            "ai_probability": round(agg.ai_probability, 4),
            "verdict": agg.verdict,
            "confidence": round(agg.confidence, 4),
            "coverage": round(agg.coverage, 4),
            "consistency": round(agg.consistency, 4),
            "top_indicators": top_indicators(list(results)),
            "manual_research_hints": _manual_research_hints(list(results)),
        },
    }
    if llm_result is not None:
        data["llm_judge"] = llm_result
    return data


def to_json(data: Dict[str, Any], indent: int = 2) -> str:
    return json.dumps(data, indent=indent, ensure_ascii=False)
