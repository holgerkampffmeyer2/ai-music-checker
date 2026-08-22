"""Tests for evidence checker and DB suggester."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestEvidenceChecker:
    """Tests for evidence URL checking."""

    def test_check_evidence_url_valid(self):
        from ai_music_checker.evidence_checker import check_evidence_url
        
        with patch("ai_music_checker.evidence_checker.fetch_url") as mock_fetch:
            mock_fetch.return_value = "<html>Some valid content with enough length to pass the check</html>"
            
            result = check_evidence_url("https://example.com/valid")
            
            assert result.status == "valid"
            assert result.url == "https://example.com/valid"
            assert result.last_checked  # Should have a date

    def test_check_evidence_url_broken_empty(self):
        from ai_music_checker.evidence_checker import check_evidence_url
        
        with patch("ai_music_checker.evidence_checker.fetch_url") as mock_fetch:
            mock_fetch.return_value = None
            
            result = check_evidence_url("https://example.com/empty")
            
            assert result.status == "broken"
            assert "no content" in result.note.lower()

    def test_check_evidence_url_broken_timeout(self):
        from ai_music_checker.evidence_checker import check_evidence_url
        
        with patch("ai_music_checker.evidence_checker.fetch_url") as mock_fetch:
            mock_fetch.side_effect = TimeoutError("timeout")
            
            result = check_evidence_url("https://example.com/timeout")
            
            assert result.status == "broken"
            assert "timeout" in result.note.lower()

    def test_check_evidence_url_broken_404(self):
        from ai_music_checker.evidence_checker import check_evidence_url
        
        with patch("ai_music_checker.evidence_checker.fetch_url") as mock_fetch:
            mock_fetch.return_value = "404 Not Found - The page you requested was not found"
            
            result = check_evidence_url("https://example.com/404")
            
            assert result.status == "broken"
            assert "404" in result.note or "not found" in result.note.lower()

    def test_check_database_evidence(self):
        from ai_music_checker.evidence_checker import check_database_evidence
        
        db = {
            "entries": [
                {
                    "id": "test-1",
                    "evidence": [
                        {"url": "https://example.com/valid"},
                        {"url": "https://example.com/broken"},
                    ]
                }
            ]
        }
        
        with patch("ai_music_checker.evidence_checker.fetch_url") as mock_fetch:
            # First call valid, second call raises exception
            mock_fetch.side_effect = ["<html>Valid content here</html>", OSError("error")]
            
            results = check_database_evidence(db)
            
            assert "test-1" in results
            assert len(results["test-1"]) == 2
            assert results["test-1"][0].status == "valid"
            assert results["test-1"][1].status == "broken"

    def test_generate_evidence_report(self):
        from ai_music_checker.evidence_checker import generate_evidence_report, EvidenceStatus
        
        results = {
            "test-artist": [
                EvidenceStatus(
                    url="https://example.com",
                    status="valid",
                    last_checked="2024-01-15",
                    note="URL accessible"
                )
            ]
        }
        
        report = generate_evidence_report(results)
        
        assert "test-artist" in report
        assert "https://example.com" in report
        assert "valid" in report.lower()


class TestDBSuggester:
    """Tests for DB entry suggestions."""

    def test_generate_id(self):
        from ai_music_checker.db_suggester import _generate_id
        
        assert _generate_id("CLMX") == "clmx"
        assert _generate_id("Anna Indiana") == "anna-indiana"
        assert _generate_id("The Velvet Sundown") == "the-velvet-sundown"

    def test_suggest_from_signals_below_threshold(self):
        from ai_music_checker.db_suggester import suggest_from_signals
        from ai_music_checker.signals import SignalResult
        
        # Create mock probe
        probe = MagicMock()
        probe.tags = {"artist": "Test Artist"}
        probe.path = Path("/path/to/test.mp3")
        
        # Create low-probability results
        results = [
            SignalResult(
                id="T1", name="hf_energy_profile", value=0.0,
                subscore=0.2, weight=12, reliability=0.6,
                available=True, note="test", group="technical"
            )
        ]
        
        # Should return None (below threshold)
        suggestion = suggest_from_signals(
            probe, results, ai_probability=0.3, verdict="UNAUFFÄLLIG",
            min_confidence=0.6
        )
        
        assert suggestion is None

    def test_suggest_from_signals_above_threshold(self):
        from ai_music_checker.db_suggester import suggest_from_signals
        from ai_music_checker.signals import SignalResult
        
        # Create mock probe
        probe = MagicMock()
        probe.tags = {"artist": "AI Artist"}
        probe.path = Path("/path/to/test.mp3")
        
        # Create high-probability results
        results = [
            SignalResult(
                id="T1", name="hf_energy_profile", value=0.0,
                subscore=0.8, weight=12, reliability=0.6,
                available=True, note="cutoff detected", group="technical"
            ),
            SignalResult(
                id="M1", name="watermark_scan", value=1.0,
                subscore=0.9, weight=12, reliability=0.9,
                available=True, note="suno detected", group="metadata"
            ),
        ]
        
        # Should return suggestion
        suggestion = suggest_from_signals(
            probe, results, ai_probability=0.75, verdict="LIKELY AI-ASSISTED",
            min_confidence=0.6
        )
        
        assert suggestion is not None
        assert suggestion.name == "AI Artist"
        assert suggestion.ai_confidence in ("high", "medium", "low")
        assert len(suggestion.evidence) > 0

    def test_suggest_from_batch_filters_low_count(self):
        from ai_music_checker.db_suggester import suggest_from_batch, DBSuggestion
        
        suggestions = [
            DBSuggestion(id="artist-a", name="Artist A", reason="test", indicators=["T1"]),
            DBSuggestion(id="artist-b", name="Artist B", reason="test", indicators=["T1"]),
            DBSuggestion(id="artist-a", name="Artist A", reason="test", indicators=["T1"]),
        ]
        
        # Filter with min_occurrences=2
        filtered = suggest_from_batch(suggestions, min_occurrences=2)
        
        assert len(filtered) == 1
        assert filtered[0].id == "artist-a"

    def test_suggestions_to_json(self):
        from ai_music_checker.db_suggester import suggestions_to_json, DBSuggestion
        
        suggestions = [
            DBSuggestion(
                id="test-artist",
                name="Test Artist",
                ai_confidence="high",
                evidence=[{"url": "test", "note": "test", "date": "2024-01",
                          "last_checked": "2024-01-15", "status": "valid"}]
            )
        ]
        
        json_str = suggestions_to_json(suggestions)
        data = json.loads(json_str)
        
        assert data["schema_version"] == "1.0.0"
        assert len(data["suggestions"]) == 1
        assert data["suggestions"][0]["name"] == "Test Artist"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
