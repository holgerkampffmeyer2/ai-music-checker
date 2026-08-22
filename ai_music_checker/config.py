#!/usr/bin/env python3
"""Config dataclass + loader with precedence CLI > env (AIMC_) > config.json > defaults."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ENV_PREFIX = "AIMC_"

DEFAULTS: dict[str, Any] = {
    "weights": {"technical": 40, "metadata": 25, "context": 35},
    "criteria": {
        "T1": {"threshold_khz": 16, "severe_khz": 14},
        "T2": {"crest_db_threshold": 8, "lra_lu_threshold": 3},
        "M1": {
            "patterns": [
                "suno", "udio", "stable audio", "riffusion", "musicgen",
                "aiva", "soundraw", "boomy", "ecrett", "mubert", "loudly",
            ],
            "whitelist": ["promo-cloud", "konkah engine"],
        },
        "M4": {
            "acronym_artist_max_len": 5,
            "suffixes": ["xtd", "extended", "remix", "vocal", "instrumental", "radio edit"],
        },
    },
    "metadata_sources": ["musicbrainz", "discogs", "soundcloud"],
    "soundcloud_client_id_env": "SOUNDCLOUD_CLIENT_ID",
    "request_timeout_s": 10,
    "retry_attempts": 3,
    "community_db": {
        "enabled": True,
        "url": "https://raw.githubusercontent.com/holgerkampffmeyer2/ai-artists-db/main/known_ai_artists.json",
        "ttl_hours": 24,
        "fuzzy_enabled": False,
        "fuzzy_threshold": 0.9,
        "evidence": {
            "check": False,
            "retention_days": 30,
        },
    },
    "llm_judge": {
        "enabled": False,
        "backend": "openrouter",
        "model": "openai/gpt-4o-mini",
        "api_key_env": "OPENROUTER_API_KEY",
        "timeout_s": 30,
        "temperature": 0.1,
        "max_tokens": 1500,
        "prompt_template": "builtin_v1",
    },
    "db_suggest": {
        "enabled": False,
        "min_ai_probability": 0.6,
    },
}


def deep_update(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge `override` into `base` (returns new dict)."""
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_update(out[key], value)
        else:
            out[key] = value
    return out


def _parse_env_value(raw: str) -> Any:
    lower = raw.strip().lower()
    if lower in ("true", "false"):
        return lower == "true"
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


@dataclass
class Config:
    weights: dict[str, int] = field(default_factory=lambda: dict(DEFAULTS["weights"]))
    criteria: dict[str, Any] = field(default_factory=lambda: json.loads(json.dumps(DEFAULTS["criteria"])))
    metadata_sources: list[str] = field(default_factory=lambda: list(DEFAULTS["metadata_sources"]))
    soundcloud_client_id_env: str = DEFAULTS["soundcloud_client_id_env"]
    request_timeout_s: int = DEFAULTS["request_timeout_s"]
    retry_attempts: int = DEFAULTS["retry_attempts"]
    community_db: dict[str, Any] = field(default_factory=lambda: dict(DEFAULTS["community_db"]))
    llm_judge: dict[str, Any] = field(default_factory=lambda: dict(DEFAULTS["llm_judge"]))
    db_suggest: dict[str, Any] = field(default_factory=lambda: dict(DEFAULTS["db_suggest"]))

    @classmethod
    def load(
        cls,
        cli_overrides: dict[str, Any] | None = None,
        config_path: str | Path | None = None,
        environ: dict[str, str] | None = None,
    ) -> Config:
        env = dict(os.environ if environ is None else environ)

        merged: dict[str, Any] = {}
        file_data = cls._read_config_file(config_path)
        if file_data:
            merged = deep_update(merged, file_data)
        merged = deep_update(merged, cls._env_overrides(env))
        cli_data = cls._cli_overrides(cli_overrides or {})
        merged = deep_update(merged, cli_data)

        full = deep_update(cls._defaults_snapshot(), merged)
        return cls._from_dict(full)

    @staticmethod
    def _defaults_snapshot() -> dict[str, Any]:
        return json.loads(json.dumps(DEFAULTS))

    @staticmethod
    def _read_config_file(config_path: str | Path | None) -> dict[str, Any]:
        if config_path is None:
            repo_default = Path(__file__).resolve().parent.parent / "config.json"
            config_path = repo_default if repo_default.exists() else None
        if config_path is None:
            return {}
        try:
            raw = Path(config_path).read_text(encoding="utf-8")
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _env_overrides(env: dict[str, str]) -> dict[str, Any]:
        section_names = ("community_db", "llm_judge", "weights", "criteria")
        overrides: dict[str, Any] = {}
        for key, raw in env.items():
            if not key.startswith(ENV_PREFIX):
                continue
            rest = key[len(ENV_PREFIX):].lower()
            value = _parse_env_value(raw)
            placed = False
            for section in section_names:
                if rest == section:
                    overrides[section] = value
                    placed = True
                    break
                if rest.startswith(section + "_"):
                    sub_key = rest[len(section) + 1:]
                    overrides.setdefault(section, {})[sub_key] = value
                    placed = True
                    break
            if not placed:
                overrides[rest] = value
        return overrides

    @staticmethod
    def _cli_overrides(cli_overrides: dict[str, Any]) -> dict[str, Any]:
        overrides: dict[str, Any] = {}
        for key, value in cli_overrides.items():
            if value is None:
                continue
            path = key.lower().split(".")
            node: dict[str, Any] = overrides
            for part in path[:-1]:
                node = node.setdefault(part, {})
            node[path[-1]] = value
        return overrides

    @classmethod
    def _coerce(cls, value: Any, default: Any) -> Any:
        """Coerce `value` to the type of `default`; return default on failure."""
        if isinstance(default, bool):
            if isinstance(value, bool):
                return value
            if isinstance(value, str) and value.strip().lower() in ("true", "false"):
                return value.strip().lower() == "true"
            return default
        if isinstance(default, int) and not isinstance(default, bool):
            try:
                return int(value)
            except (TypeError, ValueError):
                return default
        if isinstance(default, float):
            try:
                return float(value)
            except (TypeError, ValueError):
                return default
        if isinstance(default, list):
            return value if isinstance(value, list) else default
        if isinstance(default, dict):
            if not isinstance(value, dict):
                return dict(default)
            out = dict(default)
            for key, sub in value.items():
                if key in out:
                    out[key] = cls._coerce(sub, out[key])
            return out
        return value if isinstance(value, str) else default

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> Config:
        cfg = cls()
        defaults = cls._defaults_snapshot()
        for key in defaults:
            if key in data:
                setattr(cfg, key, cls._coerce(data[key], defaults[key]))
        return cfg
