#!/usr/bin/env python3
"""
Unit tests for metadata signals M1–M4 — TDD FIRST, implementation after.

Weights/reliabilities per PLAN.md §4:
- M1 watermark_scan    w=12 r=0.9  (direct generator-pattern hit)
- M2 identifier_gaps   w=7  r=0.5  (ISRC/catalog/UPC presence)
- M3 cover_provenance  w=5  r=0.6  (generator string in artwork EXIF)
- M4 naming_heuristics w=6  r=0.4  (multiple heuristic hits)
"""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


@pytest.fixture
def config():
    from ai_music_checker.config import Config

    return Config.load(environ={})


def make_probe(tmp_path, filename="track.mp3", tags=None, has_cover=False):
    from ai_music_checker.probe import FileProbe

    streams = [{"codec_type": "audio", "codec_name": "mp3"}]
    if has_cover:
        streams.append({"codec_type": "video", "codec_name": "mjpeg",
                        "disposition": {"attached_pic": 1}})
    p = tmp_path / filename
    p.write_bytes(b"\x00")
    return FileProbe(path=p, format_name="mp3", codec="mp3",
                     tags=tags or {}, streams=streams)


class TestSignalContract:
    """All M-signals follow the Signal protocol shape."""

    @pytest.mark.parametrize("cls_id,name,weight,reliability", [
        ("M1", "watermark_scan", 12, 0.9),
        ("M2", "identifier_gaps", 7, 0.5),
        ("M3", "cover_provenance", 5, 0.6),
        ("M4", "naming_heuristics", 6, 0.4),
    ])
    def test_class_attributes(self, cls_id, name, weight, reliability):
        import ai_music_checker.signals.metadata as m

        sig = getattr(m, f"M{cls_id[1]}")()
        assert sig.id == cls_id
        assert sig.name == name
        assert sig.group == "metadata"
        assert sig.weight == weight
        assert pytest.approx(sig.reliability) == reliability
        assert sig.available(config=None) is True


class TestM1WatermarkScan:
    def test_direct_hit_suno_tag(self, config, tmp_path):
        import ai_music_checker.signals.metadata as m

        probe = make_probe(tmp_path, tags={"comment": "created with Suno v4"})
        result = m.M1().compute(probe, config)
        assert result.subscore == 1.0
        assert "suno" in result.note.lower()

    def test_case_insensitive_match(self, config, tmp_path):
        import ai_music_checker.signals.metadata as m

        probe = make_probe(tmp_path, tags={"comment": "Made with UDIO"})
        result = m.M1().compute(probe, config)
        assert result.subscore == 1.0

    def test_clean_tags_score_zero(self, config, tmp_path):
        import ai_music_checker.signals.metadata as m

        probe = make_probe(tmp_path, tags={"artist": "CLMX", "title": "Freedom"})
        result = m.M1().compute(probe, config)
        assert result.subscore == 0.0

    def test_no_tags_score_zero(self, config, tmp_path):
        import ai_music_checker.signals.metadata as m

        probe = make_probe(tmp_path, tags={})
        result = m.M1().compute(probe, config)
        assert result.subscore == 0.0

    def test_whitelisted_value_not_flagged(self, config, tmp_path):
        import ai_music_checker.signals.metadata as m

        # 'promo-cloud' is whitelisted; a value containing only that must not hit
        probe = make_probe(tmp_path, tags={"comment": "distributed via promo-cloud"})
        result = m.M1().compute(probe, config)
        assert result.subscore == 0.0

    def test_whitelist_does_not_hide_other_hits(self, config, tmp_path):
        import ai_music_checker.signals.metadata as m

        probe = make_probe(tmp_path, tags={"comment": "promo-cloud + suno master"})
        result = m.M1().compute(probe, config)
        assert result.subscore == 1.0

    def test_encoder_tag_scanned_too(self, config, tmp_path):
        import ai_music_checker.signals.metadata as m

        probe = make_probe(tmp_path, tags={"encoder": "LAME3.100 (mubert)"})
        result = m.M1().compute(probe, config)
        assert result.subscore == 1.0


class TestM2IdentifierGaps:
    def test_all_identifiers_present_zero(self, config, tmp_path):
        import ai_music_checker.signals.metadata as m

        probe = make_probe(tmp_path, tags={
            "isrc": "DEXX72000001", "catalognumber": "BVR062",
            "barcode": "4066000000000",
        })
        result = m.M2().compute(probe, config)
        assert result.subscore == 0.0

    def test_some_identifiers_low_score(self, config, tmp_path):
        import ai_music_checker.signals.metadata as m

        probe = make_probe(tmp_path, tags={"isrc": "DEXX72000001"})
        result = m.M2().compute(probe, config)
        assert result.subscore == pytest.approx(0.3)

    def test_no_identifiers_moderate_high(self, config, tmp_path):
        import ai_music_checker.signals.metadata as m

        probe = make_probe(tmp_path, tags={"artist": "CLMX"})
        result = m.M2().compute(probe, config)
        assert result.subscore == pytest.approx(0.6)

    def test_tsrc_alias_recognized(self, config, tmp_path):
        import ai_music_checker.signals.metadata as m

        probe = make_probe(tmp_path, tags={"tsrc": "DEXX72000002"})
        result = m.M2().compute(probe, config)
        assert result.subscore == pytest.approx(0.3)

    def test_note_lists_found_identifiers(self, config, tmp_path):
        import ai_music_checker.signals.metadata as m

        probe = make_probe(tmp_path, tags={"isrc": "DEXX72000001"})
        result = m.M2().compute(probe, config)
        assert "isrc" in result.note.lower()


class TestM3CoverProvenance:
    def test_no_cover_moderate_subscore(self, config, tmp_path):
        import ai_music_checker.signals.metadata as m

        probe = make_probe(tmp_path, has_cover=False)
        result = m.M3().compute(probe, config)
        assert result.subscore == pytest.approx(0.5)
        assert "cover" in result.note.lower()

    def test_generator_string_in_exif_full_score(self, config, tmp_path):
        import ai_music_checker.signals.metadata as m

        probe = make_probe(tmp_path, has_cover=True)
        with patch.object(m, "_cover_software_strings",
                          return_value=["Generated with Midjourney v6"]):
            result = m.M3().compute(probe, config)
        assert result.subscore == 1.0

    def test_clean_cover_strings_zero(self, config, tmp_path):
        import ai_music_checker.signals.metadata as m

        probe = make_probe(tmp_path, has_cover=True)
        with patch.object(m, "_cover_software_strings", return_value=["Adobe Photoshop"]):
            result = m.M3().compute(probe, config)
        assert result.subscore == 0.0

    def test_image_tool_patterns_checked(self, config, tmp_path):
        import ai_music_checker.signals.metadata as m

        probe = make_probe(tmp_path, has_cover=True)
        with patch.object(m, "_cover_software_strings",
                          return_value=["stable diffusion xl"]):
            result = m.M3().compute(probe, config)
        assert result.subscore == 1.0


class TestM4NamingHeuristics:
    def test_freedom_reference_filename_three_hits(self, config, tmp_path):
        import ai_music_checker.signals.metadata as m

        probe = make_probe(
            tmp_path,
            filename="BV062026_CLMX_-_Freedom_(XTD_Version).mp3",
        )
        result = m.M4().compute(probe, config)
        # catalog number BV062026 + short uppercase artist CLMX + xtd suffix
        assert result.subscore == pytest.approx(0.9)

    def test_plain_name_zero(self, config, tmp_path):
        import ai_music_checker.signals.metadata as m

        probe = make_probe(tmp_path, filename="Kylie Minogue - Padam Padam.mp3")
        result = m.M4().compute(probe, config)
        assert result.subscore == 0.0

    def test_one_hit_low_score(self, config, tmp_path):
        import ai_music_checker.signals.metadata as m

        # long lowercase-ish artist, one suffix only
        probe = make_probe(tmp_path, filename="Nalin & Kane - Beachball (Extended Mix).mp3")
        result = m.M4().compute(probe, config)
        assert result.subscore == pytest.approx(0.35)

    def test_catalog_pattern_detected(self, config, tmp_path):
        import ai_music_checker.signals.metadata as m

        probe = make_probe(tmp_path, filename="AB12345_Some_Title.mp3")
        result = m.M4().compute(probe, config)
        assert "catalog" in result.note.lower()

    def test_acronym_artist_detected(self, config, tmp_path):
        import ai_music_checker.signals.metadata as m

        probe = make_probe(tmp_path, filename="CLMX - Freedom.mp3")
        result = m.M4().compute(probe, config)
        assert result.subscore == pytest.approx(0.35)

    def test_suffix_word_match_case_insensitive(self, config, tmp_path):
        import ai_music_checker.signals.metadata as m

        probe = make_probe(tmp_path, filename="Someone - Nightcall (Radio Edit).mp3")
        result = m.M4().compute(probe, config)
        assert result.subscore == pytest.approx(0.35)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
