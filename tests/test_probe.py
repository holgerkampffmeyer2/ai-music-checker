#!/usr/bin/env python3
"""
Unit tests for probe.py and the signal runner — TDD FIRST, implementation after.

Tests cover:
- probe_file parses sample ffprobe JSON output correctly
- Defensive parsing (missing fields, string numbers)
- Error handling (missing file, ffprobe failure, invalid JSON)
- SignalResult dataclass defaults
- SIGNAL_REGISTRY / run_all_signals filtering
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

SAMPLE_FFPROBE = {
    "streams": [
        {
            "index": 0,
            "codec_name": "mp3",
            "codec_type": "audio",
            "sample_rate": "44100",
            "channels": 2,
            "bit_rate": "320000",
            "tags": {"encoder": "LAME3.100"},
        }
    ],
    "format": {
        "filename": "/tmp/freedom.mp3",
        "format_name": "mp3",
        "duration": "213.5",
        "size": "8540000",
        "bit_rate": "320000",
        "nb_streams": 1,
        "tags": {"ARTIST": "CLMX", "title": "Freedom", "TSSE": "LAME3.100"},
    },
}


@pytest.fixture
def probed(tmp_path):
    from ai_music_checker.probe import probe_file

    f = tmp_path / "freedom.mp3"
    f.write_bytes(b"\x00")
    with patch("ai_music_checker.probe.run_cmd") as mock_run:
        mock_run.return_value = (True, json.dumps(SAMPLE_FFPROBE), "")
        result = probe_file(f)
    return result, mock_run


class TestProbeFile:
    """probe_file parsing tests."""

    def test_returns_fileprobe(self, probed):
        from ai_music_checker.probe import FileProbe

        result, _ = probed
        assert isinstance(result, FileProbe)

    def test_format_fields(self, probed):
        result, _ = probed
        assert result.format_name == "mp3"
        assert result.duration == pytest.approx(213.5)
        assert result.bitrate == 320000

    def test_stream_fields_from_audio_stream(self, probed):
        result, _ = probed
        assert result.codec == "mp3"
        assert result.sample_rate == 44100
        assert result.channels == 2

    def test_tags_normalized_lowercase(self, probed):
        result, _ = probed
        # ARTIST in source -> artist key here; value preserved
        assert result.tags["artist"] == "CLMX"
        assert result.tags["title"] == "Freedom"

    def test_ffprobe_command_uses_json_and_quoted_path(self, probed, tmp_path):
        _, mock_run = probed
        cmd = mock_run.call_args[0][0]
        assert "-print_format" in cmd
        assert "json" in cmd
        assert "-show_format" in cmd
        assert "-show_streams" in cmd

    def test_ffprobe_command_quotes_paths_with_spaces(self, tmp_path):
        from ai_music_checker.probe import probe_file

        f = tmp_path / "my track.mp3"
        f.write_bytes(b"\x00")
        with patch("ai_music_checker.probe.run_cmd") as mock_run:
            mock_run.return_value = (True, json.dumps(SAMPLE_FFPROBE), "")
            probe_file(f)
        cmd = mock_run.call_args[0][0]
        assert f"'{f}'" in cmd  # shell-quoted because of the space

    def test_missing_file_raises_filenotfound(self, tmp_path):
        from ai_music_checker.probe import probe_file

        with pytest.raises(FileNotFoundError):
            probe_file(tmp_path / "does_not_exist.mp3")

    def test_ffprobe_failure_raises_probe_error(self, tmp_path):
        from ai_music_checker.probe import ProbeError, probe_file

        f = tmp_path / "broken.mp3"
        f.write_bytes(b"\x00")
        with patch("ai_music_checker.probe.run_cmd") as mock_run:
            mock_run.return_value = (False, "", "Invalid data found")
            with pytest.raises(ProbeError, match="Invalid data"):
                probe_file(f)

    def test_invalid_json_raises_probe_error(self, tmp_path):
        from ai_music_checker.probe import ProbeError, probe_file

        f = tmp_path / "broken.mp3"
        f.write_bytes(b"\x00")
        with patch("ai_music_checker.probe.run_cmd") as mock_run:
            mock_run.return_value = (True, "not json {", "")
            with pytest.raises(ProbeError):
                probe_file(f)

    def test_missing_optional_fields_default_to_none(self, tmp_path):
        from ai_music_checker.probe import probe_file

        f = tmp_path / "minimal.wav"
        f.write_bytes(b"\x00")
        minimal = {"streams": [], "format": {"format_name": "wav"}}
        with patch("ai_music_checker.probe.run_cmd") as mock_run:
            mock_run.return_value = (True, json.dumps(minimal), "")
            result = probe_file(f)
        assert result.duration is None
        assert result.bitrate is None
        assert result.sample_rate is None
        assert result.channels is None
        assert result.codec is None
        assert result.tags == {}

    def test_cover_stream_detection(self, tmp_path):
        from ai_music_checker.probe import probe_file

        f = tmp_path / "with_cover.mp3"
        f.write_bytes(b"\x00")
        data = json.loads(json.dumps(SAMPLE_FFPROBE))
        data["streams"].append(
            {
                "index": 1,
                "codec_name": "mjpeg",
                "codec_type": "video",
                "disposition": {"attached_pic": 1},
            }
        )
        with patch("ai_music_checker.probe.run_cmd") as mock_run:
            mock_run.return_value = (True, json.dumps(data), "")
            result = probe_file(f)
        assert result.has_cover_stream is True


class TestSignalResult:
    """SignalResult dataclass tests."""

    def test_defaults(self):
        from ai_music_checker.signals import SignalResult

        r = SignalResult(id="T1", name="hf_energy_profile", value=0.5, subscore=0.6, weight=8, reliability=0.9)
        assert r.available is True
        assert r.note == ""

    def test_roundtrip_fields(self):
        from ai_music_checker.signals import SignalResult

        r = SignalResult(id="C5", name="community_db", value=1.0, subscore=1.0, weight=5, reliability=1.0,
                         available=True, note="matched clmx")
        assert r.id == "C5" and r.note == "matched clmx"


class TestSignalRunner:
    """SIGNAL_REGISTRY + run_all_signals tests."""

    @pytest.fixture
    def dummy_signals(self):
        from ai_music_checker.signals import SignalResult

        class SigA:  # available technical signal
            id, name, group, weight, reliability = "T1", "sig_a", "technical", 8, 0.9

            def available(self, config):
                return True

            def compute(self, probe, config):
                return SignalResult(id=self.id, name=self.name, value=1.0, subscore=0.7,
                                    weight=self.weight, reliability=self.reliability)

        class SigB:  # unavailable context signal (no --online)
            id, name, group, weight, reliability = "C5", "sig_b", "context", 5, 1.0

            def available(self, config):
                return False

            def compute(self, probe, config):  # pragma: no cover - must not be called
                raise AssertionError("compute called on unavailable signal")

        class SigC:
            id, name, group, weight, reliability = "M1", "sig_c", "metadata", 4, 0.8

            def available(self, config):
                return True

            def compute(self, probe, config):
                return SignalResult(id=self.id, name=self.name, value=0.0, subscore=0.1,
                                    weight=self.weight, reliability=self.reliability)

        return [SigA(), SigB(), SigC()]

    def test_registry_is_list(self):
        from ai_music_checker.signals import SIGNAL_REGISTRY

        assert isinstance(SIGNAL_REGISTRY, list)

    def test_runner_skips_unavailable_signals(self, dummy_signals):
        from ai_music_checker.signals import run_all_signals

        results = run_all_signals(probe=None, config=None, registry=dummy_signals)
        ids = [r.id for r in results]
        assert ids == ["T1", "M1"]  # C5 skipped, order preserved

    def test_runner_returns_signal_results(self, dummy_signals):
        from ai_music_checker.signals import SignalResult, run_all_signals

        results = run_all_signals(probe=None, config=None, registry=dummy_signals)
        assert all(isinstance(r, SignalResult) for r in results)

    def test_runner_empty_registry(self):
        from ai_music_checker.signals import run_all_signals

        assert run_all_signals(probe=None, config=None, registry=[]) == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
