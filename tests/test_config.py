#!/usr/bin/env python3
"""
Unit tests for config.py — TDD FIRST, implementation after.

Tests cover:
- Defaults load without file/env/cli
- config.json overrides defaults
- Env vars (AIMC_) override config values (flat + nested)
- CLI overrides win over everything
- Missing/invalid input handled gracefully
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

DEFAULTS_SNAPSHOT = {
    "weights": {"technical": 40, "metadata": 25, "context": 35},
    "request_timeout_s": 10,
}


@pytest.fixture
def repo_config_path():
    return Path(__file__).parent.parent / "config.json"


class TestDefaults:
    """Loading with defaults only."""

    def test_load_without_any_source(self):
        from ai_music_checker.config import Config

        cfg = Config.load(config_path=None, environ={})
        assert cfg.weights == {"technical": 40, "metadata": 25, "context": 35}
        assert cfg.request_timeout_s == 10
        assert cfg.retry_attempts == 3

    def test_community_db_defaults(self):
        from ai_music_checker.config import Config

        cfg = Config.load(config_path=None, environ={})
        assert cfg.community_db["enabled"] is True
        assert "url" in cfg.community_db

    def test_llm_judge_disabled_by_default(self):
        from ai_music_checker.config import Config

        cfg = Config.load(config_path=None, environ={})
        assert cfg.llm_judge["enabled"] is False


class TestFileOverrides:
    """config.json overrides defaults."""

    def test_repo_config_json_is_used(self, repo_config_path):
        from ai_music_checker.config import Config

        cfg = Config.load(config_path=repo_config_path, environ={})
        assert cfg.metadata_sources == ["musicbrainz", "discogs", "soundcloud"]
        assert cfg.criteria["T1"]["threshold_khz"] == 16

    def test_custom_config_file_overrides_defaults(self, tmp_path):
        from ai_music_checker.config import Config

        custom = tmp_path / "config.json"
        custom.write_text(json.dumps({"request_timeout_s": 42}))
        cfg = Config.load(config_path=custom, environ={})
        assert cfg.request_timeout_s == 42
        # untouched keys keep defaults
        assert cfg.retry_attempts == 3

    def test_missing_config_file_falls_back_to_defaults(self, tmp_path):
        from ai_music_checker.config import Config

        cfg = Config.load(config_path=tmp_path / "nope.json", environ={})
        assert cfg.request_timeout_s == 10

    def test_invalid_json_config_falls_back_to_defaults(self, tmp_path):
        from ai_music_checker.config import Config

        bad = tmp_path / "config.json"
        bad.write_text("{not json")
        cfg = Config.load(config_path=bad, environ={})
        assert cfg.request_timeout_s == 10


class TestEnvOverrides:
    """AIMC_ env vars override file/defaults."""

    def test_flat_env_override(self, repo_config_path):
        from ai_music_checker.config import Config

        cfg = Config.load(
            config_path=repo_config_path,
            environ={"AIMC_REQUEST_TIMEOUT_S": "99"},
        )
        assert cfg.request_timeout_s == 99

    def test_nested_env_override_bool(self, repo_config_path):
        from ai_music_checker.config import Config

        cfg = Config.load(
            config_path=repo_config_path,
            environ={"AIMC_COMMUNITY_DB_ENABLED": "false"},
        )
        assert cfg.community_db["enabled"] is False

    def test_env_beats_file(self, tmp_path):
        from ai_music_checker.config import Config

        f = tmp_path / "config.json"
        f.write_text(json.dumps({"request_timeout_s": 42}))
        cfg = Config.load(config_path=f, environ={"AIMC_REQUEST_TIMEOUT_S": "7"})
        assert cfg.request_timeout_s == 7

    def test_non_numeric_value_for_int_key_ignored(self, repo_config_path):
        from ai_music_checker.config import Config

        cfg = Config.load(
            config_path=repo_config_path,
            environ={"AIMC_REQUEST_TIMEOUT_S": "not-a-number"},
        )
        assert cfg.request_timeout_s == 10


class TestCliOverrides:
    """CLI overrides win over env/file/defaults."""

    def test_cli_beats_env(self, repo_config_path):
        from ai_music_checker.config import Config

        cfg = Config.load(
            config_path=repo_config_path,
            environ={"AIMC_REQUEST_TIMEOUT_S": "99"},
            cli_overrides={"request_timeout_s": 5},
        )
        assert cfg.request_timeout_s == 5

    def test_cli_nested_section_override(self, repo_config_path):
        from ai_music_checker.config import Config

        cfg = Config.load(
            config_path=repo_config_path,
            environ={},
            cli_overrides={"community_db.url": "https://custom/db.json"},
        )
        assert cfg.community_db["url"] == "https://custom/db.json"

    def test_none_values_in_cli_overrides_ignored(self, repo_config_path):
        from ai_music_checker.config import Config

        cfg = Config.load(
            config_path=repo_config_path,
            environ={},
            cli_overrides={"request_timeout_s": None},
        )
        assert cfg.request_timeout_s == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
