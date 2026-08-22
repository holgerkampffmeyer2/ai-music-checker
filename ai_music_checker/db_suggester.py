"""DB Entry Suggester — suggest new community DB entries based on analysis."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from ai_music_checker.signals import SignalResult


@dataclass
class DBSuggestion:
    """Suggested new entry for the community database."""
    id: str
    name: str
    aliases: list[str] = field(default_factory=list)
    type: str = "artist"
    labels: list[str] = field(default_factory=list)
    ai_confidence: str = "medium"
    evidence: list[dict[str, Any]] = field(default_factory=list)
    reason: str = ""
    indicators: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON output."""
        return {
            "id": self.id,
            "name": self.name,
            "aliases": self.aliases,
            "type": self.type,
            "labels": self.labels,
            "ai_confidence": self.ai_confidence,
            "evidence": self.evidence,
            "added": datetime.now().strftime("%Y-%m-%d"),
            "verified": datetime.now().strftime("%Y-%m-%d"),
            "_suggestion": {
                "reason": self.reason,
                "indicators": self.indicators,
            }
        }


def _generate_id(name: str) -> str:
    """Generate kebab-case ID from artist name."""
    # Remove special chars, convert to lowercase, replace spaces with hyphens
    id_str = re.sub(r'[^a-z0-9\s-]', '', name.lower())
    id_str = re.sub(r'\s+', '-', id_str.strip())
    # Limit length
    return id_str[:50]


def suggest_from_signals(
    probe: Any,
    results: list[SignalResult],
    ai_probability: float,
    verdict: str,
    min_confidence: float = 0.6,
) -> DBSuggestion | None:
    """Suggest a new DB entry based on analysis signals.
    
    Args:
        probe: FileProbe object with file metadata
        results: List of SignalResult from analysis
        ai_probability: Calculated AI probability score
        verdict: Verdict string (e.g., "LIKELY AI-ASSISTED")
        min_confidence: Minimum AI probability to suggest entry
    
    Returns:
        DBSuggestion if entry should be added, None otherwise
    """
    # Only suggest if AI probability is high enough
    if ai_probability < min_confidence:
        return None
    
    # Extract artist from probe tags or filename
    tags = probe.tags or {}
    artist = tags.get("artist") or tags.get("album_artist")
    
    if not artist:
        # Try filename parsing
        stem = probe.path.stem
        if " - " in stem:
            artist = stem.split(" - ")[0].strip()
        else:
            artist = stem
    
    if not artist or len(artist) < 2:
        return None
    
    # Collect indicators
    indicators = []
    indicator_details = []
    
    for r in results:
        if r.available and r.subscore > 0.5:
            indicators.append(r.id)
            indicator_details.append(f"{r.id}: {r.note}")
    
    # Determine confidence level based on indicators
    if len(indicators) >= 5 or ai_probability > 0.8:
        confidence = "high"
    elif len(indicators) >= 3 or ai_probability > 0.6:
        confidence = "medium"
    else:
        confidence = "low"
    
    # Build evidence list
    evidence = []
    
    # Add technical indicators as evidence
    technical_hits = [r for r in results if r.group == "technical" and r.subscore > 0.5]
    if technical_hits:
        evidence.append({
            "url": f"local-analysis://{probe.path.name}",
            "note": f"Technical analysis: {', '.join(r.id for r in technical_hits)}",
            "date": datetime.now().strftime("%Y-%m"),
            "last_checked": datetime.now().strftime("%Y-%m-%d"),
            "status": "valid",
        })
    
    # Add metadata indicators as evidence
    metadata_hits = [r for r in results if r.group == "metadata" and r.subscore > 0.5]
    if metadata_hits:
        evidence.append({
            "url": f"local-analysis://{probe.path.name}#metadata",
            "note": f"Metadata analysis: {', '.join(r.id for r in metadata_hits)}",
            "date": datetime.now().strftime("%Y-%m"),
            "last_checked": datetime.now().strftime("%Y-%m-%d"),
            "status": "valid",
        })
    
    # Ensure we have at least one evidence item
    if not evidence:
        evidence.append({
            "url": f"local-analysis://{probe.path.name}",
            "note": f"AI probability: {ai_probability:.0%}, verdict: {verdict}",
            "date": datetime.now().strftime("%Y-%m"),
            "last_checked": datetime.now().strftime("%Y-%m-%d"),
            "status": "valid",
        })
    
    # Build suggestion
    id_val = _generate_id(artist)
    reason = f"AI probability {ai_probability:.0%} ({verdict}), {len(indicators)} suspicious indicators"
    
    suggestion = DBSuggestion(
        id=id_val,
        name=artist,
        aliases=[],
        type="artist",
        labels=[],
        ai_confidence=confidence,
        evidence=evidence,
        reason=reason,
        indicators=indicator_details,
    )
    
    return suggestion


def suggest_from_batch(
    suggestions: list[DBSuggestion],
    min_occurrences: int = 2,
) -> list[DBSuggestion]:
    """Filter batch suggestions to only include artists appearing multiple times.
    
    Args:
        suggestions: List of all suggestions from batch analysis
        min_occurrences: Minimum times an artist must appear to be suggested
    
    Returns:
        Filtered list with only frequent artists
    """
    # Count occurrences by artist ID
    counts: dict[str, int] = {}
    for s in suggestions:
        counts[s.id] = counts.get(s.id, 0) + 1
    
    # Filter to only frequent artists
    filtered = []
    seen = set()
    for s in suggestions:
        if counts[s.id] >= min_occurrences and s.id not in seen:
            seen.add(s.id)
            # Update reason with occurrence count
            s.reason = f"Appeared {counts[s.id]} times in batch. {s.reason}"
            filtered.append(s)
    
    return filtered


def suggestions_to_json(suggestions: list[DBSuggestion]) -> str:
    """Convert suggestions to JSON format."""
    data = {
        "schema_version": "1.0.0",
        "generated": datetime.now().isoformat(),
        "suggestions": [s.to_dict() for s in suggestions],
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


def save_suggestions(suggestions: list[DBSuggestion], path: Path) -> None:
    """Save suggestions to a JSON file."""
    path.write_text(suggestions_to_json(suggestions), encoding="utf-8")
