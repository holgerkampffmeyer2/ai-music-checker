#!/usr/bin/env python3
"""
Unit tests for report.py — TDD FIRST, implementation after.

Tests cover:
- build() emits schema_version "1.0" with file/provenance/signals/groups/result
- Signal serialization roundtrip
- manual_research_hints from unavailable signals
- llm_judge section only when provided
- to_json produces parseable JSON
"""

import json
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


@pytest.fixture
def probe(tmp_path):
    from ai_music_checker.probe import FileProbe

    f = tmp_path / "freedom.mp3"
    f.write_bytes(b"\x00")
    return FileProbe(
        path=f,
        format_name="mp3",
        duration=213.5,
        bitrate=320000,
        sample_rate=44100,
        channels=2,
        codec="mp3",
        tags={"artist": "CLMX", "title": "Freedom", "encoder": "LAME3.100"},
        streams=[{"codec_type": "audio", "codec_name": "mp3"}],
    )


@pytest.fixture
def results():
    return [
        make_result("T1", 0.9, weight=8, note="hf energy above 16k"),
        make_result("M1", 0.0, weight=5, group="metadata"),
        make_result("C5", 1.0, weight=5, group="context", available=False,
                    note="community db offline"),
    ]


@pytest.fixture
def aggregate():
    from ai_music_checker.scoring import aggregate

    groups = {"technical": (0.9, 1.0), "metadata": (0.0, 1.0), "context": (0.0, 0.0)}
    return aggregate(groups, {"technical": 40, "metadata": 25, "context": 35},
                     enabled_groups={"technical", "metadata", "context"})


class TestBuild:
    def test_schema_version(self, probe, results, aggregate):
        from ai_music_checker.report import build

        data = build(probe, results, aggregate)
        assert data["schema_version"] == "1.0"

    def test_file_section(self, probe, results, aggregate):
        from ai_music_checker.report import build

        data = build(probe, results, aggregate)
        f = data["file"]
        assert f["name"] == "freedom.mp3"
        assert f["format"] == "mp3"
        assert f["duration_s"] == pytest.approx(213.5)
        assert f["bitrate_bps"] == 320000
        assert f["sample_rate_hz"] == 44100
        assert f["channels"] == 2
        assert f["codec"] == "mp3"

    def test_provenance_section(self, probe, results, aggregate):
        from ai_music_checker.report import build

        data = build(probe, results, aggregate)
        p = data["provenance"]
        assert p["encoder"] == "LAME3.100"
        assert p["tags_present"] is True
        assert "artist" in p["tag_keys"]

    def test_signals_serialized_with_all_fields(self, probe, results, aggregate):
        from ai_music_checker.report import build

        data = build(probe, results, aggregate)
        sigs = {s["id"]: s for s in data["signals"]}
        assert set(sigs.keys()) == {"T1", "M1", "C5"}
        t1 = sigs["T1"]
        for key in ("id", "name", "group", "value", "subscore", "weight",
                    "reliability", "available", "note"):
            assert key in t1
        assert t1["subscore"] == pytest.approx(0.9)
        assert sigs["C5"]["available"] is False

    def test_groups_section_from_aggregate(self, probe, results, aggregate):
        from ai_music_checker.report import build

        data = build(probe, results, aggregate)
        g = data["groups"]["technical"]
        assert g["score"] == pytest.approx(0.9)
        assert g["coverage"] == pytest.approx(1.0)

    def test_result_section(self, probe, results, aggregate):
        from ai_music_checker.report import build

        data = build(probe, results, aggregate)["result"]
        for key in ("ai_probability", "verdict", "confidence", "coverage",
                    "consistency", "top_indicators", "manual_research_hints"):
            assert key in data
        assert 0.0 <= data["ai_probability"] <= 1.0
        assert isinstance(data["verdict"], str)

    def test_top_indicators_passthrough(self, probe, results, aggregate):
        from ai_music_checker.report import build

        hints = build(probe, results, aggregate)["result"]["top_indicators"]
        assert hints[0]["id"] == "T1"

    def test_manual_hints_for_unavailable_signals(self, probe, results, aggregate):
        from ai_music_checker.report import build

        hints = build(probe, results, aggregate)["result"]["manual_research_hints"]
        assert any("C5" in h for h in hints)

    def test_no_hints_when_all_available(self, probe, results, aggregate):
        from ai_music_checker.report import build

        all_available = [make_result("T1", 0.5)]
        data = build(probe, all_available, aggregate)
        assert data["result"]["manual_research_hints"] == []

    def test_llm_judge_only_when_provided(self, probe, results, aggregate):
        from ai_music_checker.report import build

        without = build(probe, results, aggregate)
        assert "llm_judge" not in without

        llm = {"probability": 0.8, "confidence": 0.7, "reasoning": "r",
               "agrees_with_deterministic": True, "key_disagreements": []}
        with_llm = build(probe, results, aggregate, llm_result=llm)
        assert with_llm["llm_judge"] == llm

    def test_golden_structure_minimal_input(self, probe):
        from ai_music_checker.report import build
        from ai_music_checker.scoring import aggregate

        agg = aggregate({}, {}, enabled_groups=set())
        data = build(probe, [], agg)
        assert list(data.keys()) == [
            "schema_version", "file", "provenance", "signals", "groups", "result"
        ]
        assert data["signals"] == []
        assert data["result"]["ai_probability"] == 0.0
        assert data["result"]["verdict"] == "UNAUFFÄLLIG"


class TestToJson:
    def test_produces_parseable_json(self, probe, results, aggregate):
        from ai_music_checker.report import build, to_json

        text = to_json(build(probe, results, aggregate))
        parsed = json.loads(text)
        assert parsed["schema_version"] == "1.0"

    def test_umlauts_not_escaped(self, probe, results, aggregate):
        from ai_music_checker.report import build, to_json

        text = to_json(build(probe, results, aggregate))
        assert "LIKELY AI-ASSISTED" in text or "UNAUFF" in text or '"verdict"' in text
        assert json.loads(text)["result"]["verdict"] in (
            "UNAUFFÄLLIG", "EHER MENSCHLICH", "UNKLAR",
            "LIKELY AI-ASSISTED", "VERY LIKELY AI",
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
