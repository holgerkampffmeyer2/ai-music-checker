"""DB Entry Suggester — suggest new community DB entries based on analysis."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
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
    db_status: str = "not_in_db"
    online_ai_indication: bool = False
    reason_code: str = ""
    
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
            "added": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),
            "verified": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),
            "db_status": self.db_status,
            "online_ai_indication": self.online_ai_indication,
            "reason_code": self.reason_code,
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


class DBMatchResult:
    """Result of artist DB lookup."""
    def __init__(self, entry: Any, fuzzy: bool = False):
        self.entry = entry
        self.fuzzy = fuzzy


def artist_in_db(artist: str, community_db: Any, fuzzy: bool = False, threshold: float = 0.9, aliases: list[str] | None = None) -> DBMatchResult | None:
    """Check if artist is in community database.
    
    Args:
        artist: Artist name to look up
        community_db: CommunityDB instance
        fuzzy: Enable fuzzy matching
        threshold: Fuzzy match threshold (Jaro-Winkler)
        aliases: Optional list of aliases to include in search
    
    Returns:
        DBMatchResult if found, None otherwise
    """
    if community_db is None:
        return None
    
    # Use the existing lookup method
    search_aliases = aliases or []
    match = community_db.lookup(artist, search_aliases, fuzzy=fuzzy, threshold=threshold)
    if match:
        return DBMatchResult(match.entry, fuzzy=match.fuzzy)
    return None


def evaluate_online_ai_indication(results: list[SignalResult]) -> tuple[bool, str]:
    """Evaluate if online signals indicate AI origin.
    
    Args:
        results: List of SignalResult from analysis
        
    Returns:
        Tuple of (indication: bool, reason_code: str)
    """
    # Get context signals
    c1 = next((r for r in results if r.id == "C1" and r.available), None)
    c2 = next((r for r in results if r.id == "C2" and r.available), None)
    c5 = next((r for r in results if r.id == "C5" and r.available), None)
    
    indication_parts = []
    online_ai = False
    
    # C1: Artist footprint - high subscore means no footprint (suspicious)
    if c1 and c1.subscore >= 0.8:
        online_ai = True
        indication_parts.append("C1_no_footprint")
    
    # C2: Label pattern - high subscore means content farm pattern
    if c2 and c2.subscore >= 0.7:
        online_ai = True
        indication_parts.append("C2_content_farm")
    
    # C5: Community DB - any positive match indicates AI
    if c5 and c5.subscore > 0.0:
        online_ai = True
        indication_parts.append("C5_db_match")
    
    # C4: Press text buzzwords (if available)
    c4 = next((r for r in results if r.id == "C4" and r.available), None)
    if c4 and c4.subscore >= 0.5:
        online_ai = True
        indication_parts.append("C4_press_buzzwords")
    
    reason_code = ",".join(indication_parts) if indication_parts else "no_online_indication"
    return online_ai, reason_code


def suggest_from_signals(
    probe: Any,
    results: list[SignalResult],
    ai_probability: float,
    verdict: str,
    min_confidence: float = 0.6,
    community_db: Any = None,
) -> DBSuggestion | None:
    """Suggest a new DB entry based on analysis signals.
    
    Args:
        probe: FileProbe object with file metadata
        results: List of SignalResult from analysis
        ai_probability: Calculated AI probability score
        verdict: Verdict string (e.g., "LIKELY AI-ASSISTED")
        min_confidence: Minimum AI probability to suggest entry
        community_db: Optional CommunityDB instance for DB presence check
    
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
    
    # Check if artist already in community DB
    db_status = "not_in_db"
    if community_db is not None:
        db_match = artist_in_db(artist, community_db)
        if db_match:
            db_status = "already_in_db"
            # If already in DB with high confidence, don't suggest
            if db_match.entry.ai_confidence == "high":
                return None
    
    # Evaluate online AI indication
    online_ai_indication, reason_code = evaluate_online_ai_indication(results)
    
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
            "date": datetime.now(tz=timezone.utc).strftime("%Y-%m"),
            "last_checked": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),
            "status": "valid",
        })
    
    # Add metadata indicators as evidence
    metadata_hits = [r for r in results if r.group == "metadata" and r.subscore > 0.5]
    if metadata_hits:
        evidence.append({
            "url": f"local-analysis://{probe.path.name}#metadata",
            "note": f"Metadata analysis: {', '.join(r.id for r in metadata_hits)}",
            "date": datetime.now(tz=timezone.utc).strftime("%Y-%m"),
            "last_checked": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),
            "status": "valid",
        })
    
    # Add online indication as evidence if applicable
    if online_ai_indication:
        evidence.append({
            "url": f"local-analysis://{probe.path.name}#online",
            "note": f"Online AI indication: {reason_code}",
            "date": datetime.now(tz=timezone.utc).strftime("%Y-%m"),
            "last_checked": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),
            "status": "valid",
        })
    
    # Ensure we have at least one evidence item
    if not evidence:
        evidence.append({
            "url": f"local-analysis://{probe.path.name}",
            "note": f"AI probability: {ai_probability:.0%}, verdict: {verdict}",
            "date": datetime.now(tz=timezone.utc).strftime("%Y-%m"),
            "last_checked": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),
            "status": "valid",
        })
    
    # Build reason
    reason_parts = [f"AI probability {ai_probability:.0%} ({verdict})"]
    if online_ai_indication:
        reason_parts.append(f"Online AI indication: {reason_code}")
    if db_status == "already_in_db":
        reason_parts.append("Artist already in community DB")
    reason_parts.append(f"{len(indicators)} suspicious indicators")
    reason = ", ".join(reason_parts)
    
    # Build suggestion
    id_val = _generate_id(artist)
    
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
        db_status=db_status,
        online_ai_indication=online_ai_indication,
        reason_code=reason_code,
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
        "generated": datetime.now(tz=timezone.utc).isoformat(),
        "suggestions": [s.to_dict() for s in suggestions],
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


def save_suggestions(suggestions: list[DBSuggestion], path: Path) -> None:
    """Save suggestions to a JSON file."""
    path.write_text(suggestions_to_json(suggestions), encoding="utf-8")
