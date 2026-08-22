#!/usr/bin/env python3
"""Metadata signals M1–M4 (local, always on).

Weights/reliabilities per PLAN.md §4:
- M1 watermark_scan    w=12 r=0.9
- M2 identifier_gaps   w=7  r=0.5
- M3 cover_provenance  w=5  r=0.6
- M4 naming_heuristics w=6  r=0.4
"""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from typing import TYPE_CHECKING, Any, List

from ai_music_checker.signals import SignalResult

if TYPE_CHECKING:
    from ai_music_checker.config import Config
    from ai_music_checker.probe import FileProbe


AI_IMAGE_TOOL_PATTERNS = (
    "midjourney", "dall-e", "dalle", "stable diffusion", "stable-diffusion",
    "firefly", "flux", "ideogram", "leonardo.ai",
)

_CATALOG_RE = re.compile(r"\b[A-Z]{2,}\d{4,}\b")

_M2_IDENTIFIER_KEYS = {
    "isrc": ("isrc", "tsrc"),
    "catalog": ("catalog", "catalognumber"),
    "upc/barcode": ("barcode", "upc", "ean"),
}


def _criteria_value(config: Any, signal_id: str, field: str) -> Any:
    try:
        return config.criteria[signal_id][field]
    except (AttributeError, KeyError, TypeError):
        from ai_music_checker.config import DEFAULTS

        return DEFAULTS["criteria"].get(signal_id, {}).get(field)


class BaseSignal:
    group = "metadata"

    def available(self, config: Any) -> bool:
        return True


class M1(BaseSignal):
    id = "M1"
    name = "watermark_scan"
    weight = 12
    reliability = 0.9

    def compute(self, probe: FileProbe, config: Config) -> SignalResult:
        patterns = [p.lower() for p in _criteria_value(config, "M1", "patterns") or []]
        whitelist = [w.lower() for w in _criteria_value(config, "M1", "whitelist") or []]

        hits: List[str] = []
        for tag_key, value in (probe.tags or {}).items():
            cleaned = str(value).lower()
            for term in whitelist:
                cleaned = cleaned.replace(term, "")
            for pattern in patterns:
                if pattern in cleaned:
                    hits.append(f"pattern '{pattern}' in tag '{tag_key}'")

        subscore = 1.0 if hits else 0.0
        note = "; ".join(hits[:3]) if hits else "no generator patterns in tags"
        return SignalResult(
            id=self.id, name=self.name, value=float(len(hits)), subscore=subscore,
            weight=self.weight, reliability=self.reliability, available=True,
            note=note, group=self.group,
        )


class M2(BaseSignal):
    id = "M2"
    name = "identifier_gaps"
    weight = 7
    reliability = 0.5

    def compute(self, probe: FileProbe, config: Config) -> SignalResult:
        tags = {k.lower(): v for k, v in (probe.tags or {}).items()}
        found = [
            category
            for category, keys in _M2_IDENTIFIER_KEYS.items()
            if any(key in tags for key in keys)
        ]
        if len(found) >= 3:
            subscore, note_detail = 0.0, "all identifiers present"
        elif found:
            subscore = 0.3
            note_detail = f"present: {', '.join(found)}"
        else:
            subscore = 0.6
            note_detail = "no ISRC/catalog/UPC in tags"
        return SignalResult(
            id=self.id, name=self.name, value=float(len(found)), subscore=subscore,
            weight=self.weight, reliability=self.reliability, available=True,
            note=note_detail, group=self.group,
        )


def _cover_software_strings(probe: FileProbe) -> List[str]:
    """Extract embedded artwork and read its EXIF/comment strings via exiftool."""
    if shutil.which("exiftool") is None:
        return []
    from ai_music_checker.lib.shell import run_cmd, shq

    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "cover.jpg")
        ok, _, _ = run_cmd(
            f"ffmpeg -y -v error -i {shq(str(probe.path))} "
            f"-map 0:v:0 -frames:v 1 {shq(out)}",
            timeout=30,
        )
        if not ok or not os.path.exists(out):
            return []
        ok, stdout, _ = run_cmd(
            f"exiftool -j -Software -Artist -Comment -ImageDescription {shq(out)}",
            timeout=15,
        )
        if not ok:
            return []
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return []
        if not isinstance(data, list) or not data:
            return []
        return [str(v) for v in data[0].values() if isinstance(v, str)]


class M3(BaseSignal):
    id = "M3"
    name = "cover_provenance"
    weight = 5
    reliability = 0.6

    def compute(self, probe: FileProbe, config: Config) -> SignalResult:
        if not probe.has_cover_stream:
            return SignalResult(
                id=self.id, name=self.name, value=0.0, subscore=0.5,
                weight=self.weight, reliability=self.reliability, available=True,
                note="no embedded cover", group=self.group,
            )
        strings = [s.lower() for s in _cover_software_strings(probe)]
        hits = [
            p for p in AI_IMAGE_TOOL_PATTERNS
            if any(p in s for s in strings)
        ]
        subscore = 1.0 if hits else 0.0
        note = f"generator string: {hits[0]}" if hits else "cover present, no generator strings"
        return SignalResult(
            id=self.id, name=self.name, value=float(len(hits)), subscore=subscore,
            weight=self.weight, reliability=self.reliability, available=True,
            note=note, group=self.group,
        )


_M4_SCORE_MAP = {0: 0.0, 1: 0.35, 2: 0.65}


class M4(BaseSignal):
    id = "M4"
    name = "naming_heuristics"
    weight = 6
    reliability = 0.4

    def compute(self, probe: FileProbe, config: Config) -> SignalResult:
        max_len = _criteria_value(config, "M4", "acronym_artist_max_len") or 5
        suffixes = _criteria_value(config, "M4", "suffixes") or []

        stem = probe.path.stem.replace("_", " ")
        notes: List[str] = []

        catalog_match = _CATALOG_RE.search(stem)
        artist_part = None
        if " - " in stem:
            left, right = stem.split(" - ", 1)
            if catalog_match and left.startswith(catalog_match.group(0)):
                left = left[len(catalog_match.group(0)):].lstrip()
            artist_part = left.strip()
            title_lower = right.lower()
        else:
            title_lower = stem.lower()

        if catalog_match:
            notes.append(f"catalog-number-like token '{catalog_match.group(0)}'")

        if (
            artist_part
            and len(artist_part) <= max_len
            and artist_part.isupper()
            and any(c.isalpha() for c in artist_part)
        ):
            notes.append(f"short uppercase artist '{artist_part}'")

        suffix_hits = []
        for suffix in suffixes:
            pattern = r"\b" + re.escape(str(suffix).lower()) + r"\b"
            if re.search(pattern, title_lower):
                suffix_hits.append(suffix)
        if suffix_hits:
            notes.append(f"suffix '{suffix_hits[0]}'")

        n = len(notes)
        subscore = _M4_SCORE_MAP.get(min(n, 3), 0.9) if n < 3 else 0.9
        note = "; ".join(notes) if notes else "no naming heuristics hit"
        return SignalResult(
            id=self.id, name=self.name, value=float(n), subscore=subscore,
            weight=self.weight, reliability=self.reliability, available=True,
            note=note, group=self.group,
        )


METADATA_SIGNALS = [M1(), M2(), M3(), M4()]
