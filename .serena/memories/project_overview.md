# ai-music-checker — Projektüberblick

Forensisches Heuristik-CLI zur Abschätzung der KI-Generierungswahrscheinlichkeit von Musikdateien (MP3/WAV/FLAC/AIFF).

## Stack
- Python 3.10+, stdlib-first, pytest, ruff, mypy. Keine ML-Inferenz im Kern.
- Externe Tools: ffmpeg/ffprobe.

## Struktur
- `ai_music_checker/` — Package: `probe.py`, `config.py`, `scoring.py`, `report.py`, `ui.py`, `cli.py` (teils noch nicht implementiert), `community_db.py`, `llm_judge.py` (geplant)
- `ai_music_checker/lib/` — vendored aus wav-to-aac-converter: `shell.py` (run_cmd/shq/retry), `http.py` (fetch_url/load_env), `match.py` (fuzzy_match)
- `ai_music_checker/signals/` — Signal-Protocol + Registry; Gruppen: technical (T1–T7, w=45 gesamt in config), metadata (M1–M4), context (C1–C5, nur --online)
- `tests/` — TDD: Tests ZUERST schreiben, dann Implementierung
- `openspec/changes/ai-music-checker/` — proposal/design/tasks/specs (tasks.md = Fortschrittsquelle)

## Konventionen
- Scoring: subscore 0..1 (1 = starke KI-Indikation); effektives Gewicht w*r*(available); Verdict-Bands: ≤0.20 UNAUFFÄLLIG, 0.21–0.40 EHER MENSCHLICH, 0.41–0.60 UNKLAR, 0.61–0.80 LIKELY AI-ASSISTED, >0.80 VERY LIKELY AI
- confidence = 0.6*coverage + 0.4*consistency
- Config-Präzedenz: CLI > env (AIMC_) > config.json > defaults
- JSON-Schema v1.0 in report.py; deterministisch
- Community DB: `/mnt/c/work/ai-artists-db` (separates Repo), bundled Kopie unter `ai_music_checker/data/known_ai_artists.json`, Cache ~/.cache/ai-music-checker/
- LLM Judge (M9): opt-in --llm, Backends OpenAI/Anthropic/Ollama/OpenRouter, Cache nach SHA256(prompt+model+temp)
- Exit codes: 0 ok, 1 usage/file error, 2 ffprobe/ffmpeg fehlt

## Befehle
- Tests: `.venv/bin/python -m pytest tests/ -v` (venv nötig, System-Python ist externally-managed)
- Dev-Install: python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
