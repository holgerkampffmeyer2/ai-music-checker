"""Community AI Artists Database — fetch, cache, lookup."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Import vendored utils
from ai_music_checker.lib.http import fetch_url
from ai_music_checker.lib.match import calculate_match_confidence


@dataclass
class DBEntry:
    id: str
    name: str
    aliases: list[str]
    type: str
    labels: list[str]
    ai_confidence: str
    evidence: list[dict]
    added: str
    verified: str


@dataclass
class CommunityDB:
    schema_version: str
    updated: str
    license: str
    entries: list[DBEntry]

    @classmethod
    def from_dict(cls, data: dict) -> CommunityDB:
        return cls(
            schema_version=data["schema_version"],
            updated=data["updated"],
            license=data["license"],
            entries=[DBEntry(**e) for e in data["entries"]]
        )

    def lookup(self, artist: str, aliases: list[str], fuzzy: bool = False, threshold: float = 0.9) -> Match | None:
        """Find matching entry. Exact casefold on name + aliases first, then fuzzy if enabled."""
        search_terms = [artist] + aliases
        search_terms = [s.strip().lower() for s in search_terms if s.strip()]

        # Exact match
        for entry in self.entries:
            entry_terms = [entry.name.lower()] + [a.lower() for a in entry.aliases]
            if any(term in entry_terms for term in search_terms):
                return Match(entry, fuzzy=False)

        # Fuzzy match
        if fuzzy:
            for entry in self.entries:
                entry_terms = [entry.name] + entry.aliases
                for term in entry_terms:
                    for search in search_terms:
                        score = calculate_match_confidence(search, term)
                        if score >= threshold:
                            return Match(entry, fuzzy=True)
        return None


@dataclass
class Match:
    entry: DBEntry
    fuzzy: bool


# Confidence mapping
CONFIDENCE_MAP = {
    "high": 1.0,
    "medium": 0.7,
    "low": 0.4,
}


def confidence_to_subscore(confidence: str) -> float:
    """Map confidence level to subscore."""
    return CONFIDENCE_MAP.get(confidence, 0.0)


def validate_entry(entry: dict) -> bool:
    """Validate a single entry against schema requirements."""
    required = ["id", "name", "aliases", "type", "labels", "ai_confidence", "evidence", "added", "verified"]
    for field in required:
        if field not in entry:
            raise ValueError(f"Missing required field: {field}")

    if entry["ai_confidence"] not in ("high", "medium", "low"):
        raise ValueError("ai_confidence must be one of: high, medium, low")

    if not isinstance(entry["aliases"], list):
        raise TypeError("aliases must be a list")

    if not isinstance(entry["labels"], list):
        raise TypeError("labels must be a list")

    if not isinstance(entry["evidence"], list) or len(entry["evidence"]) == 0:
        raise ValueError("evidence must be a non-empty list")

    for ev in entry["evidence"]:
        if not all(k in ev for k in ("url", "note", "date", "last_checked", "status")):
            raise ValueError("evidence items must have url, note, date, last_checked, status")
        if not re.match(r"^https?://", ev["url"]):
            raise ValueError(f"Invalid URL: {ev['url']}")
        if not re.match(r"^\d{4}-\d{2}$", ev["date"]):
            raise ValueError(f"Invalid evidence date format (expected YYYY-MM): {ev['date']}")
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", ev["last_checked"]):
            raise ValueError(f"Invalid last_checked format (expected YYYY-MM-DD): {ev['last_checked']}")
        if ev["status"] not in ("valid", "broken", "outdated"):
            raise ValueError(f"Invalid status: {ev['status']}")

    if not re.match(r"^\d{4}-\d{2}-\d{2}$", entry["added"]):
        raise ValueError(f"Invalid added date format: {entry['added']}")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", entry["verified"]):
        raise ValueError(f"Invalid verified date format: {entry['verified']}")

    return True


def validate_database(db: dict) -> bool:
    """Validate entire database."""
    required_top = ["schema_version", "updated", "license", "entries"]
    for field in required_top:
        if field not in db:
            raise ValueError(f"Missing top-level field: {field}")

    ids = [e["id"] for e in db["entries"]]
    if len(ids) != len(set(ids)):
        dupes = [x for x in ids if ids.count(x) > 1]
        raise ValueError(f"Duplicate IDs: {dupes}")

    for entry in db["entries"]:
        validate_entry(entry)

    return True


# Cache paths
def get_cache_dir() -> Path:
    cache_dir = Path.home() / ".cache" / "ai-music-checker"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_db_cache_path() -> Path:
    return get_cache_dir() / "known_ai_artists.json"


def load_bundled() -> CommunityDB:
    """Load bundled database from package resources."""
    # For now, try to load from installed package or local data dir
    try:
        from importlib.resources import files
        data = files("ai_music_checker.data").joinpath("known_ai_artists.json").read_text()
        return CommunityDB.from_dict(json.loads(data))
    except (FileNotFoundError, json.JSONDecodeError, ModuleNotFoundError, KeyError):
        # Fallback: try local data file
        local_path = Path(__file__).parent.parent / "data" / "known_ai_artists.json"
        if local_path.exists():
            with open(local_path) as f:
                return CommunityDB.from_dict(json.load(f))
        # Last resort: minimal valid DB
        return CommunityDB(
            schema_version="1.0.0",
            updated=datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),
            license="CC0-1.0",
            entries=[]
        )


def fetch_remote(url: str, cache_path: Path | None = None) -> CommunityDB | None:
    """Fetch remote DB with ETag/Last-Modified caching."""
    if cache_path is None:
        cache_path = get_db_cache_path()
    elif isinstance(cache_path, str):
        cache_path = Path(cache_path)

    if cache_path.exists():
        # TODO: implement ETag/Last-Modified headers
        pass

    try:
        content = fetch_url(url, timeout=10)
    except TimeoutError:
        # Network failure (timeout, DNS, connection refused, etc.) - try cache
        if cache_path.exists():
            try:
                with open(cache_path) as f:
                    return CommunityDB.from_dict(json.load(f))
            except (json.JSONDecodeError, KeyError) as e:
                logger.debug(f"Failed to parse cache: {e}")
        return None

    try:
        data = json.loads(content)
        validate_database(data)
        # Write cache
        with open(cache_path, "w") as f:
            json.dump(data, f)
        return CommunityDB.from_dict(data)
    except (json.JSONDecodeError, ValueError) as e:
        # Corrupt data - try cache
        logger.debug(f"Remote DB invalid: {e}")
        if cache_path.exists():
            try:
                with open(cache_path) as f:
                    return CommunityDB.from_dict(json.load(f))
            except (json.JSONDecodeError, KeyError) as e2:
                logger.debug(f"Cache also corrupt: {e2}")
        return None


def load_or_fetch(config: dict) -> CommunityDB | None:
    """Load DB: remote (with cache fallback) or bundled."""
    if not config.get("enabled", True):
        return load_bundled()

    url = config.get("url", "https://raw.githubusercontent.com/holgerkampffmeyer2/ai-artists-db/main/known_ai_artists.json")
    db = fetch_remote(url)
    if db is not None:
        return db
    return load_bundled()


def lookup_artist(db: CommunityDB, artist: str, aliases: list[str],
                  fuzzy: bool = False, threshold: float = 0.9) -> Match | None:
    """Convenience function for lookup."""
    return db.lookup(artist, aliases, fuzzy, threshold)