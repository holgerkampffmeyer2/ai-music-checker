"""ffprobe wrapper: FileProbe dataclass + probe_file()."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ai_music_checker.lib.shell import run_cmd, shq

FFPROBE_CMD = "ffprobe -v quiet -print_format json -show_format -show_streams {path}"


class ProbeError(RuntimeError):
    """Raised when ffprobe fails or returns unparseable output."""


@dataclass
class FileProbe:
    path: Path
    format_name: str = ""
    duration: float | None = None
    bitrate: int | None = None
    sample_rate: int | None = None
    channels: int | None = None
    codec: str | None = None
    tags: dict[str, str] = field(default_factory=dict)
    streams: list[dict[str, Any]] = field(default_factory=list)

    @property
    def audio_stream(self) -> dict[str, Any] | None:
        for s in self.streams:
            if s.get("codec_type") == "audio":
                return s
        return None

    @property
    def has_cover_stream(self) -> bool:
        for s in self.streams:
            if s.get("disposition", {}).get("attached_pic") == 1:
                return True
            if s.get("codec_type") == "video" and s.get("codec_name") in (
                "mjpeg", "png", "gif", "bmp"
            ):
                return True
        return False


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _normalize_tags(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    return {str(k).lower(): str(v) for k, v in raw.items()}


def probe_file(path: str | Path) -> FileProbe:
    """Run ffprobe on `path` and parse its JSON output defensively."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"No such file: {p}")

    ok, out, err = run_cmd(FFPROBE_CMD.format(path=shq(str(p))))
    if not ok:
        raise ProbeError(f"ffprobe failed for {p}: {err.strip()}")
    try:
        data = json.loads(out)
    except json.JSONDecodeError as exc:
        raise ProbeError(f"ffprobe returned invalid JSON for {p}: {exc}") from exc

    fmt = data.get("format", {}) or {}
    streams = data.get("streams", []) or []
    if not isinstance(streams, list):
        streams = []

    tags: dict[str, str] = {}
    for source in [fmt.get("tags")] + [s.get("tags") for s in streams]:
        tags.update(_normalize_tags(source))

    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)

    return FileProbe(
        path=p,
        format_name=str(fmt.get("format_name", "")),
        duration=_to_float(fmt.get("duration")),
        bitrate=_to_int(fmt.get("bit_rate")),
        sample_rate=_to_int(audio.get("sample_rate")) if audio else None,
        channels=_to_int(audio.get("channels")) if audio else None,
        codec=str(audio.get("codec_name")) if audio and audio.get("codec_name") else None,
        tags=tags,
        streams=streams,
    )
