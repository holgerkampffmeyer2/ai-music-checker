# Specifications: ai-music-checker

## Purpose
Forensic heuristic tool to estimate AI-generation likelihood of music files by combining technical signal analysis, metadata inspection, and optional online context research.

## ADDED Requirements

### Requirement: Core Analysis Engine
The tool SHALL analyze local audio files (MP3, WAV, FLAC, AIFF) and produce a deterministic AI-likelihood score with confidence indicator.

#### Scenario: Single file offline analysis
- **WHEN** user runs `ai-music-checker track.mp3 --json out.json`
- **THEN** tool reads file, computes all Technical (T1–T7) and Metadata (M1–M4) signals, outputs JSON with schema_version 1.0 containing file info, signals, groups, result with ai_probability, verdict, confidence, top_indicators

#### Scenario: Batch analysis
- **WHEN** user runs `ai-music-checker *.mp3 --json batch.json`
- **THEN** tool processes each file sequentially, outputs JSON array of analysis results

### Requirement: Technical Signal Group (T1–T7)
The tool SHALL compute 7 technical signals from ffmpeg/ffprobe analysis.

#### Scenario: HF energy profile (T1)
- **WHEN** analyzing audio
- **THEN** tool runs volumedetect after highpass @16kHz/19kHz, detects spectral mirror artifacts, outputs subscore 0–1 where hard cutoff ≤16kHz → high score

#### Scenario: Dynamics/loudness (T2)
- **WHEN** analyzing audio
- **THEN** tool parses loudnorm JSON (I, LRA, TP) + astats crest factor, crest <8dB & LRA <3 LU → high score

#### Scenario: Stereo anomalies (T3)
- **WHEN** analyzing audio
- **THEN** tool measures side-channel energy distribution, unnatural uniform width → elevated score

#### Scenario: Noise floor, seams, fades (T4)
- **WHEN** analyzing audio
- **THEN** tool detects digital silence chunks, loop-seam repetition via autocorrelation, unnatural fade shapes → elevated score

#### Scenario: Encoder chain (T5)
- **WHEN** analyzing audio
- **THEN** tool extracts encoder/comment tags, LAME Info header generations, suspicious generator strings → elevated score

#### Scenario: Sample-rate artifacts (T6)
- **WHEN** analyzing audio
- **THEN** tool detects spectral imaging above cutoff, upsample hints → elevated score

#### Scenario: BPM/duration sanity (T7)
- **WHEN** analyzing audio
- **THEN** tool estimates BPM vs claimed genre, implausible combos → minor score

### Requirement: Metadata Signal Group (M1–M4)
The tool SHALL compute 4 metadata signals from file tags.

#### Scenario: Watermark/tag scan (M1)
- **WHEN** reading file tags
- **THEN** tool scans all tags/comments against known-generator patterns (suno, udio, stable audio, etc.) with whitelist (promo-cloud, konkah engine), direct hit → max score

#### Scenario: Identifier gaps (M2)
- **WHEN** reading file tags on claimed commercial release
- **THEN** tool checks ISRC/catalog/UPC presence, missing → moderate score

#### Scenario: Cover provenance (M3)
- **WHEN** embedded artwork present
- **THEN** tool extracts EXIF/software strings (Midjourney, DALL·E, Stable Diffusion), generator string found → elevated score

#### Scenario: Naming heuristics (M4)
- **WHEN** parsing filename
- **THEN** tool applies heuristics: short acronym artist names (CLMX), version suffixes (xtd, extended), catalog-number patterns, multiple hits → moderate score

### Requirement: Context Signal Group (C1–C5, opt-in --online)
The tool SHALL compute 5 context signals when `--online` flag is provided.

#### Scenario: Artist footprint (C1)
- **WHEN** `--online` enabled
- **THEN** tool queries MusicBrainz (keyless), Discogs, optional SoundCloud API-v2 (client-id from .env), no entity / negligible followers → high score

#### Scenario: Label pattern (C2)
- **WHEN** `--online` enabled
- **THEN** tool queries Discogs/MB label stats: cadence, one-release-artist ratio, content-farm signature → moderate score

#### Scenario: Release DB presence (C3)
- **WHEN** `--online` enabled
- **THEN** tool checks MB/Discogs/Beatport existence + age, absent everywhere → moderate score

#### Scenario: Press text / editorial tags (C4)
- **WHEN** `--online` enabled and URL provided
- **THEN** tool fetches page, buzzword density + editorial "AI-assisted" tags → moderate score

#### Scenario: Community AI database (C5)
- **WHEN** `--online` enabled
- **THEN** tool fetches curated JSON DB from GitHub (configurable URL, TTL cache), exact+alias match on artist name, confidence high/med/low → subscore 1.0/0.7/0.4

### Requirement: Community AI Artist Database
The project SHALL maintain a curated JSON database of known AI artists hosted on GitHub.

#### Scenario: DB schema validation
- **WHEN** PR submitted to ai-artists-db repo
- **THEN** CI validates JSON against schema.json (schema_version, entries with id, name, aliases, type, labels, ai_confidence, evidence[], added, verified)

#### Scenario: Tool fetches DB
- **WHEN** `--online` enabled
- **THEN** tool fetches remote URL with ETag/Last-Modified, caches to `~/.cache/ai-music-checker/known_ai_artists.json` with 24h TTL, falls back to stale cache → bundled copy on failure

#### Scenario: Matching
- **WHEN** looking up artist
- **THEN** tool matches exact casefold on name + aliases; fuzzy opt-in via config (Jaro-Winkler ≥0.9, flagged as fuzzy)

### Requirement: Optional LLM Judge (M9, opt-in --llm)
The tool SHALL provide an optional LLM-based semantic second opinion when `--llm` flag is provided.

#### Scenario: LLM analysis
- **WHEN** `--llm` enabled
- **THEN** tool builds structured prompt from deterministic signals + metadata + optional press text, calls configured backend (OpenAI, Anthropic, Ollama, OpenRouter), returns strict JSON with probability, confidence, reasoning, agrees_with_deterministic, key_disagreements

#### Scenario: Response caching
- **WHEN** LLM called
- **THEN** tool caches response keyed by prompt hash in `~/.cache/ai-music-checker/llm/`, reuses on identical input

#### Scenario: Output integration
- **WHEN** LLM judge runs
- **THEN** output JSON includes separate `llm_judge` section + optional `final_ensemble` weighted combo (default 0.7 deterministic / 0.3 LLM)

### Requirement: Output Formats
The tool SHALL produce machine-readable JSON and human-readable ASCII CLI output.

#### Scenario: Full JSON output
- **WHEN** `--json out.json` provided
- **THEN** tool writes schema_version 1.0 JSON with all signals, groups, result, llm_judge (if enabled), final_ensemble (if enabled)

#### Scenario: ASCII gauge (default)
- **WHEN** no `--brief` flag
- **THEN** tool prints boxed gauge with human←→AI spectrum, percentage, verdict, confidence bar, group scores, top indicators with deltas

#### Scenario: Brief one-liner
- **WHEN** `--brief` flag
- **THEN** tool prints single line: `ai-music-checker: XX% AI ████░░ conf YY% VERDICT file.mp3`

### Requirement: Configuration
The tool SHALL be configurable via `config.json` with env var and CLI override precedence.

#### Scenario: Config precedence
- **WHEN** config loaded
- **THEN** precedence: CLI flags > env vars > config.json > built-in defaults

#### Scenario: Weights and thresholds
- **WHEN** config edited
- **THEN** user can override group weights, criterion thresholds, whitelists, source order, community_db URL/TTL, llm_judge backend/model

### Requirement: Test Coverage
The tool SHALL have comprehensive test coverage.

#### Scenario: Unit tests
- **WHEN** running `pytest tests/`
- **THEN** scoring math golden values, normalization edges, weight renormalization, community_db schema validation, lookup/match/subscore, cache fallback logic all pass

#### Scenario: Integration tests
- **WHEN** running `pytest tests/integration/`
- **THEN** `--online` produces C5 signal, offline fallback works, `community_db.enabled: false` skips C5, `--brief` includes C5 delta, Freedom.mp3 fixture regression anchor

#### Scenario: Audio fixtures
- **WHEN** tests need audio
- **THEN** fixtures generated by ffmpeg: sine sweep 20Hz–22kHz, lowpassed @14kHz, white noise + silence chunks, dual-mono vs true stereo

#### Scenario: CI pipeline
- **WHEN** push to main
- **THEN** GitHub Actions runs `pytest -v`, `ruff`, `mypy` on Python 3.10+

## Constraints
- Python 3.10+
- Offline-first: all T/M signals work without network
- No audio model inference / neural network dependencies
- Deterministic core: same input → same output (except LLM judge)
- Single binary / pipx installable
- MIT license