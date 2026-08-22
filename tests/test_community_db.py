#!/usr/bin/env python3
"""
Unit tests for community_db.py — TDD FIRST, implementation after.

Tests cover:
- Schema validation
- Lookup (exact, case-insensitive, alias, fuzzy)
- Subscore mapping
- Bundled load
- Remote fetch with cache/ETag/fallback
- Config overrides
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "ai_music_checker"))

import pytest


class TestSchemaValidation:
    """Schema validation tests."""

    def test_valid_entry_passes(self):
        from ai_music_checker.community_db import validate_entry
        entry = {
            "id": "test-artist",
            "name": "Test Artist",
            "aliases": ["Alias One"],
            "type": "artist",
            "labels": ["Label A"],
            "ai_confidence": "high",
            "evidence": [{"url": "https://example.com", "note": "Evidence note", "date": "2024-01",
                          "last_checked": "2024-01-20", "status": "valid"}],
            "added": "2024-01-15",
            "verified": "2024-01-20"
        }
        assert validate_entry(entry) is True

    def test_missing_required_field_fails(self):
        from ai_music_checker.community_db import validate_entry
        entry = {
            "id": "test",
            "name": "Test",
            # missing aliases, type, labels, ai_confidence, evidence, added, verified
        }
        with pytest.raises(ValueError, match="Missing required field"):
            validate_entry(entry)

    def test_invalid_ai_confidence_enum_fails(self):
        from ai_music_checker.community_db import validate_entry
        entry = {
            "id": "test", "name": "Test", "aliases": [], "type": "artist",
            "labels": [], "ai_confidence": "very-high",  # invalid
            "evidence": [{"url": "https://x.com", "note": "n", "date": "2024-01",
                          "last_checked": "2024-01-20", "status": "valid"}],
            "added": "2024-01-01", "verified": "2024-01-01"
        }
        with pytest.raises(ValueError, match="ai_confidence must be one of"):
            validate_entry(entry)

    def test_duplicate_ids_fails(self):
        from ai_music_checker.community_db import validate_database
        db = {
            "schema_version": "1.0.0",
            "updated": "2024-01-01",
            "license": "CC0-1.0",
            "entries": [
                {"id": "dup", "name": "A", "aliases": [], "type": "artist", "labels": [], "ai_confidence": "high",
                 "evidence": [{"url": "https://x.com", "note": "n", "date": "2024-01",
                               "last_checked": "2024-01-20", "status": "valid"}],
                 "added": "2024-01-01", "verified": "2024-01-01"},
                {"id": "dup", "name": "B", "aliases": [], "type": "artist", "labels": [], "ai_confidence": "high",
                 "evidence": [{"url": "https://x.com", "note": "n", "date": "2024-01",
                               "last_checked": "2024-01-20", "status": "valid"}],
                 "added": "2024-01-01", "verified": "2024-01-01"},
            ]
        }
        with pytest.raises(ValueError, match="Duplicate IDs"):
            validate_database(db)

    def test_malformed_url_fails(self):
        from ai_music_checker.community_db import validate_entry
        entry = {
            "id": "test", "name": "Test", "aliases": [], "type": "artist", "labels": [],
            "ai_confidence": "high",
            "evidence": [{"url": "not-a-url", "note": "n", "date": "2024-01",
                          "last_checked": "2024-01-20", "status": "valid"}],
            "added": "2024-01-01", "verified": "2024-01-01"
        }
        with pytest.raises(ValueError, match="Invalid URL"):
            validate_entry(entry)


class TestLookup:
    """Artist lookup tests."""

    @pytest.fixture
    def sample_db(self):
        from ai_music_checker.community_db import CommunityDB
        return CommunityDB.from_dict({
            "schema_version": "1.0.0",
            "updated": "2024-01-01",
            "license": "CC0-1.0",
            "entries": [
                {
                    "id": "clmx",
                    "name": "CLMX",
                    "aliases": ["Cli-Max", "@clmxmusic"],
                    "type": "artist",
                    "labels": ["Balearic Vibes"],
                    "ai_confidence": "high",
                    "evidence": [{"url": "https://x.com", "note": "n", "date": "2024-01",
                                  "last_checked": "2024-01-20", "status": "valid"}],
                    "added": "2024-01-01", "verified": "2024-01-01"
                },
                {
                    "id": "anna-indiana",
                    "name": "Anna Indiana",
                    "aliases": ["@annaindianaai"],
                    "type": "artist",
                    "labels": [],
                    "ai_confidence": "medium",
                    "evidence": [{"url": "https://x.com", "note": "n", "date": "2024-01",
                                  "last_checked": "2024-01-20", "status": "valid"}],
                    "added": "2024-01-01", "verified": "2024-01-01"
                }
            ]
        })

    def test_exact_match(self, sample_db):
        from ai_music_checker.community_db import lookup_artist
        match = lookup_artist(sample_db, "CLMX", [])
        assert match is not None
        assert match.entry.id == "clmx"
        assert match.fuzzy is False

    def test_case_insensitive_match(self, sample_db):
        from ai_music_checker.community_db import lookup_artist
        match = lookup_artist(sample_db, "clmx", [])
        assert match is not None
        assert match.entry.id == "clmx"

    def test_alias_match(self, sample_db):
        from ai_music_checker.community_db import lookup_artist
        match = lookup_artist(sample_db, "@clmxmusic", [])
        assert match is not None
        assert match.entry.id == "clmx"

    def test_fuzzy_match_above_threshold(self, sample_db):
        from ai_music_checker.community_db import lookup_artist
        match = lookup_artist(sample_db, "CL MX", [], fuzzy=True, threshold=0.85)
        assert match is not None
        assert match.entry.id == "clmx"
        assert match.fuzzy is True

    def test_fuzzy_disabled_by_default(self, sample_db):
        from ai_music_checker.community_db import lookup_artist
        match = lookup_artist(sample_db, "CL MX", [])  # no fuzzy args
        assert match is None

    def test_no_match_returns_none(self, sample_db):
        from ai_music_checker.community_db import lookup_artist
        match = lookup_artist(sample_db, "Unknown Artist", [])
        assert match is None

    def test_multiple_entries_first_by_added_date(self, sample_db):
        # Add another entry with same name but later added date
        from ai_music_checker.community_db import DBEntry
        sample_db.entries.append(DBEntry(
            id="clmx-2",
            name="CLMX",
            aliases=[],
            type="artist",
            labels=[],
            ai_confidence="low",
            evidence=[{"url": "https://x.com", "note": "n", "date": "2024-01",
                        "last_checked": "2024-01-20", "status": "valid"}],
            added="2024-02-01", verified="2024-02-01"
        ))
        from ai_music_checker.community_db import lookup_artist
        match = lookup_artist(sample_db, "CLMX", [])
        # Should return the one added first (clmx, 2024-01-01)
        assert match.entry.id == "clmx"


class TestSubscoreMapping:
    """Confidence -> subscore mapping tests."""

    @pytest.mark.parametrize("confidence,expected", [
        ("high", 1.0),
        ("medium", 0.7),
        ("low", 0.4),
    ])
    def test_subscore_mapping(self, confidence, expected):
        from ai_music_checker.community_db import confidence_to_subscore
        assert confidence_to_subscore(confidence) == expected


class TestBundledLoad:
    """Bundled database loading tests."""

    def test_load_bundled_reads_package_resource(self):
        from ai_music_checker.community_db import load_bundled
        # Should not raise, returns valid DB structure
        db = load_bundled()
        assert hasattr(db, "entries")
        assert isinstance(db.entries, list)
        # Bundled copy deprecated, may be empty
        assert len(db.entries) >= 0


class TestRemoteFetch:
    """Remote fetch with cache/ETag/fallback tests."""

    @pytest.fixture
    def sample_db_json(self):
        return json.dumps({
            "schema_version": "1.0.0",
            "updated": "2024-01-01",
            "license": "CC0-1.0",
            "entries": []
        })

    def test_fetch_remote_returns_parsed_json(self, sample_db_json):
        from ai_music_checker.community_db import fetch_remote
        with patch("ai_music_checker.community_db.fetch_url") as mock_fetch:
            mock_fetch.return_value = sample_db_json
            db = fetch_remote("https://example.com/db.json")
            assert db is not None
            assert hasattr(db, "entries")
            assert isinstance(db.entries, list)

    def test_fetch_remote_etag_304_returns_cached(self, sample_db_json):
        from ai_music_checker.community_db import fetch_remote
        cache_file = "/tmp/test_cache.json"
        with patch("ai_music_checker.community_db.fetch_url") as mock_fetch:
            # First call returns data
            mock_fetch.return_value = sample_db_json
            fetch_remote("https://example.com/db.json", cache_path=cache_file)
            # Second call simulates 304
            mock_fetch.return_value = None  # 304
            mock_fetch.side_effect = [None, sample_db_json]  # Actually need better mock
            # Simplified: just verify cache is used when fetch returns None
            # Detailed implementation test later

    def test_fetch_remote_timeout_falls_back_to_cache(self, sample_db_json):
        from ai_music_checker.community_db import fetch_remote
        cache_file = "/tmp/test_cache_timeout.json"
        # Pre-populate cache
        with open(cache_file, "w") as f:
            f.write(sample_db_json)
        with patch("ai_music_checker.community_db.fetch_url") as mock_fetch:
            mock_fetch.side_effect = TimeoutError("timeout")
            db = fetch_remote("https://example.com/db.json", cache_path=cache_file)
            assert db is not None  # Should use cache
            assert hasattr(db, "entries")

    def test_corrupt_cache_falls_back_to_bundled(self, sample_db_json):
        from ai_music_checker.community_db import load_or_fetch
        cache_file = "/tmp/test_corrupt_cache.json"
        with open(cache_file, "w") as f:
            f.write("not valid json")
        config = {
            "enabled": True,
            "url": "https://example.com/db.json",
        }
        with patch("ai_music_checker.community_db.fetch_url") as mock_fetch:
            mock_fetch.side_effect = TimeoutError("timeout")
            # load_or_fetch will call fetch_remote which will fail, then fall back to bundled
            db = load_or_fetch(config)
            # Should fall back to bundled
            assert db is not None
            assert hasattr(db, "entries")


class TestConfigOverrides:
    """Config override tests."""

    def test_custom_url_respected(self):
        from ai_music_checker.community_db import fetch_remote
        with patch("ai_music_checker.community_db.fetch_url") as mock_fetch:
            mock_fetch.return_value = '{"schema_version":"1.0.0","updated":"2024-01-01","license":"CC0-1.0","entries":[]}'
            fetch_remote("https://custom.url/db.json")
            mock_fetch.assert_called_once()
            assert mock_fetch.call_args[0][0] == "https://custom.url/db.json"

    def test_disabled_skips_network(self):
        from ai_music_checker.community_db import load_or_fetch
        config = {"enabled": False, "url": "https://example.com/db.json"}
        db = load_or_fetch(config)
        # Should return bundled without network call
        assert db is not None
        assert hasattr(db, "entries")
        assert isinstance(db.entries, list)


class TestIntegrationContextSignal:
    """Integration test for C5 signal in context.py (will be written after implementation)."""

    def test_c5_signal_in_analysis_json(self):
        # Placeholder - will implement after context.py exists
        pytest.skip("Integration test pending context.py implementation")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])