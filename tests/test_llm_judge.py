"""Tests for LLM judge module."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from ai_music_checker.llm_judge import build_prompt_v1, _cache_key


class DummyAgg:
    ai_probability = 0.73

    class Signals:
        @staticmethod
        def __iter__():
            return iter([])


class DummyProbe:
    path = Path("/tmp/test.mp3")
    duration = 120.5
    sample_rate = 44100


def test_build_prompt_contains_core_fields():
    agg = DummyAgg()
    probe = DummyProbe()
    prompt = build_prompt_v1(agg, probe, [])
    assert "test.mp3" in prompt
    assert "0.73" in prompt
    assert "Respond with JSON" in prompt


def test_cache_key_deterministic():
    k1 = _cache_key("same prompt", "model")
    k2 = _cache_key("same prompt", "model")
    assert k1 == k2
    k3 = _cache_key("diff", "model")
    assert k1 != k3


def test_prompt_includes_signals():
    class Sig:
        id = "T1"
        subscore = 0.8
        note = "ok"

    class Agg:
        ai_probability = 0.5

    class Probe:
        path = Path("/a/b.wav")
        duration = 60
        sample_rate = 48000

    prompt = build_prompt_v1(Agg(), Probe(), [Sig()])
    assert "T1: subscore=0.8 note=ok" in prompt
