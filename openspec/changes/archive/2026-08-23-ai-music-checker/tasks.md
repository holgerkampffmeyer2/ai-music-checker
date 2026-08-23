# Tasks: ai-music-checker

## 1. Project Setup & Skeleton (M0, M1)

- [x] 1.1 Initialize Python package structure: `ai_music_checker/` with `__init__.py`, `cli.py`, `probe.py`, `config.py`, `scoring.py`, `report.py`, `ui.py`
- [x] 1.2 Create `lib/` vendor directory: copy `shell.py`, `http.py`, `match.py` from wav-to-aac-converter with provenance comments
- [x] 1.3 Write `config.py`: Config dataclass + loader with precedence (CLI > env > config.json > defaults)
- [x] 1.4 Write `pyproject.toml`: dependencies, console script `ai-music-checker`, dev deps (pytest, ruff, mypy)
- [x] 1.5 Write default `config.json` with all weights, thresholds, community_db, llm_judge sections
- [x] 1.6 Write `.gitignore`, `LICENSE` (MIT), `README.md` (link to PLAN.md)
- [x] 1.7 `git init` (already done), initial commit with skeleton

## 2. Signal Protocol & Runner (M1)

- [x] 2.1 Define `SignalResult` dataclass and `Signal` Protocol in `signals/__init__.py`
- [x] 2.2 Implement `SIGNAL_REGISTRY` list and `run_all_signals(probe, config)` function
- [x] 2.3 Write `probe.py`: `FileProbe` dataclass + `probe_file(path)` using ffprobe JSON output
- [x] 2.4 Unit test: `probe.py` parses sample ffprobe output correctly

## 3. Technical Signals T1–T7 (M2)

- [x] 3.1 Implement `T1_hf_energy`: highpass @16k/19k + volumedetect + spectral mirror check
- [x] 3.2 Implement `T2_dynamics`: loudnorm JSON (I, LRA, TP) + astats crest factor
- [x] 3.3 Implement `T3_stereo`: side-channel energy distribution analysis
- [x] 3.4 Implement `T4_noise_seams`: silencedetect + autocorrelation for loop seams (start with ffmpeg silencedetect)
- [x] 3.5 Implement `T5_encoder_chain`: encoder/comment tags, LAME Info header parsing
- [x] 3.6 Implement `T6_sr_artifacts`: spectral imaging detection above cutoff
- [x] 3.7 Implement `T7_bpm_sanity`: BPM estimation vs genre plausibility
- [x] 3.8 Write unit tests for each T-signal using synthetic audio fixtures

## 4. Metadata Signals M1–M4 (M3)

- [x] 4.1 Implement `M1_watermark_scan`: tag/comment pattern matching with whitelist
- [x] 4.2 Implement `M2_identifier_gaps`: ISRC/catalog/UPC presence check
- [x] 4.3 Implement `M3_cover_provenance`: embedded artwork EXIF extraction + software string scan
- [x] 4.4 Implement `M4_naming_heuristics`: filename parsing (acronyms, suffixes, catalog patterns)
- [x] 4.5 Write unit tests for each M-signal with mocked tag data
- [x] 4.6 Adjusted M4 weight: 6 → 4 (reduced false positive rate)

## 5. Scoring Engine (M1–M3)

- [x] 5.1 Implement `effective_weight`, `group_score`, `aggregate`, `confidence`, `consistency` in `scoring.py`
- [x] 5.2 Define verdict bands: UNAUFFÄLLIG ≤0.20, EHER MENSCHLICH 0.21–0.40, UNKLAR 0.41–0.60, LIKELY AI-ASSISTED 0.61–0.80, VERY LIKELY AI >0.80
- [x] 5.3 Implement top-indicators extraction: largest `W_i*(s_i-0.5)` contributions
- [x] 5.4 Write unit tests: golden values for known input combinations, edge cases (all unavailable, zero weights, renormalization)

## 6. Report & JSON Output (M1–M3)

- [x] 6.1 Define output dataclasses: `FileInfo`, `Provenance`, `SignalResult`, `GroupResult`, `Result`, `AnalysisJSON` (as dicts in report.py)
- [x] 6.2 Implement `report.build()` → dict → JSON with schema_version 1.0
- [x] 6.3 Validate JSON schema against test golden file (schema at `data/schema.json`)
- [x] 6.4 Test: `--json out.json` produces valid schema v1.0 output
- [x] 6.5 Added `validate_output()` function with jsonschema validation

## 7. ASCII UI (M4)

- [x] 7.1 Implement full-mode renderer: box-drawing gauge (░▒▓█ zones), percentage, verdict, confidence bar, group bars, top-indicator table with ▲/▼
- [x] 7.2 Implement `--brief` mode: single line with compact gauge, percentage, confidence, verdict, filename
- [x] 7.3 Test: CLI output matches mockups in PLAN.md

## 8. Context Signals C1–C5 + Community DB (M5, M6) — TDD

- [x] 8.1 **Write `tests/test_community_db.py` FIRST** (TDD):
  - Schema validation: valid entry passes, rejects missing fields, invalid ai_confidence enum, duplicate id, malformed URLs
  - Lookup: exact match, case-insensitive, alias match, fuzzy ≥0.9 (flagged), no-match returns None
  - Subscore mapping: high→1.0, medium→0.7, low→0.4
  - Bundled load reads package resource
  - Remote fetch: ETag 304 returns cached; timeout falls back to cache; corrupt cache falls back to bundled
  - Config override: custom URL, `enabled: false` skips network
- [x] 8.2 Implement `community_db.py`: `DBEntry`, `CommunityDB`, `load_bundled`, `fetch_remote`, `load_or_fetch`, `lookup`, `subscore`
- [x] 8.3 Implement cache: `~/.cache/ai-music-checker/known_ai_artists.json` with `fetched_at`, TTL from config
- [x] 8.4 Create `ai-artists-db` repo: `known_ai_artists.json`, `schema.json`, `.github/workflows/validate.yml` (jsonschema), README with contribution guide
- [x] 8.5 Seed `ai-artists-db` with initial entries (CLMX + 5–10 documented cases)
- [x] 8.6 Implement context signals in `signals/context.py`:
  - `C1_artist_footprint`: MusicBrainz + Discogs + optional SoundCloud
  - `C2_label_pattern`: Discogs/MB label stats (cadence, one-release-artist ratio)
  - `C3_release_db_presence`: MB/Discogs/Beatport existence + age
  - `C4_press_text`: optional URL fetch + buzzword density + editorial tags
  - `C5_community_db`: uses `community_db.py` lookup
- [x] 8.7 Write `tests/integration/test_context_with_community_db.py`:
  - `--online` produces C5 signal in analysis JSON
  - Offline fallback to bundled still produces C5
  - `community_db.enabled: false` → no C5 signal
  - `--brief` output includes C5 delta
  - Freedom.mp3 fixture → C5 high (regression anchor)

## 9. CLI Integration & Config Precedence (M1–M5)

- [x] 9.1 Wire all pieces in `cli.py`: arg parsing, config loading, file iteration, signal runner, scoring, report, UI
- [x] 9.2 Implement exit codes: 0 success, 1 usage/file error, 2 ffprobe/ffmpeg missing
- [x] 9.3 Test config precedence: CLI > env (AIMC_) > config.json > defaults
- [x] 9.4 Add `--show-config` debug flag
- [x] 9.5 Add `--version` flag
- [x] 9.6 Batch mode: directory input with `--recursive` and `--max-workers` for parallel processing
- [x] 9.7 Heavy signals: `--heavy` flag enables T8–T10, T12 compute-intensive signals

## 10. Audio Fixtures & Regression Anchors (M7)

- [x] 10.1 Write `tests/generate_fixtures.py`: generates synthetic WAV files via ffmpeg
  - `full_spectrum.wav`: sine sweep 20Hz–22kHz
  - `lowpass_14khz.wav`: lowpassed @14kHz (Suno-style)
  - `silence_chunks.wav`: digital silence blocks
  - `dual_mono.wav`: L=R vs true stereo
- [x] 10.2 Copy reference fixture: `BV062026_CLMX_-_Freedom_(XTD_Version).mp3` → `tests/fixtures/reference/freedom.mp3` (gitignored, document in README)
- [x] 10.3 Add golden integration test: Freedom.mp3 offline score ~0.35–0.45, with `--online` ≥0.60 LIKELY AI-ASSISTED
- [x] 10.4 Created `tests/fixtures/corpus.json` with 22 labeled examples (12 human, 10 AI) for calibration

## 11. Heavy Signals T8–T10, T12 (M7-M8) — NEW

- [x] 11.1 Implement `T8_spectral_mirror`: Nyquist/2 mirroring detection via FFT
- [x] 11.2 Implement `T9_phase_coherence`: L/R channel phase correlation analysis
- [x] 11.3 Implement `T10_transient_preservation`: Onset detection + transient sharpness measurement
- [x] 11.4 Implement `T12_stem_separation`: Placeholder for stem separation artifacts (demucs/spleeter)
- [x] 11.5 Register heavy signals in `signals/heavy.py` with `HEAVY_SIGNALS` list
- [x] 11.6 CLI `--heavy` flag loads heavy signals via `load_signals(heavy=True)`
- [x] 11.7 Unit tests for heavy signals (contract + behavior)

## 12. SoundCloud Special Logic C6 (M6) — NEW

- [x] 12.1 Implement `signals/soundcloud.py`: SoundCloud API v2 client with confidence scoring
- [x] 12.2 Adapt confidence scoring from wav-to-aac-converter (`search_soundcloud_api`, `try_soundcloud_api_result`)
- [x] 12.3 Add `C6_soundcloud_fingerprint`: searches SoundCloud with artist/title, scores by match confidence + follower count
- [x] 12.4 Available when `SOUNDCLOUD_CLIENT_ID` env var is set
- [x] 12.5 Auto-loaded when `--online` flag is passed
- [x] 12.6 Unit tests for confidence scoring logic

## 13. LLM Judge Module (M9) — Optional, Post-M8

- [x] 13.1 **Write `tests/test_llm_judge.py` FIRST** (TDD):
  - Prompt builder produces correct structure from deterministic result + metadata
  - Response cache keyed by SHA256(prompt + model + temperature)
  - Backend mock returns valid JSON, parsed into LLMResult
  - Cache hit returns cached response without network call
- [x] 13.2 Implement `llm_judge.py`:
  - `LLMBackend` protocol + `OpenAIBackend`, `AnthropicBackend`, `OllamaBackend`, `OpenRouterBackend`
  - `build_prompt_v1(aggregate, probe, press_text)` → string
  - `analyze()` calls backend, validates JSON response, returns `LLMResult`
  - Cache in `~/.cache/ai-music-checker/llm/<hash>.json`
- [x] 13.3 Add `--llm-agent`, `--llm-backend`, `--llm-model` CLI flags
- [x] 13.4 Extend `report.py` and `ui.py` for `llm_judge` section + optional `final_ensemble`
- [x] 13.5 Add `llm_judge` config section to `config.json` and `Config` dataclass
- [x] 13.6 Integration test: `--online --llm` produces both sections in JSON

## 14. CI / Polish (M8)

- [x] 14.1 GitHub Actions workflow: `pytest -v`, `ruff check`, `mypy` on Python 3.10, 3.11, 3.12
- [x] 14.2 Pre-commit hooks: `ruff`, `mypy`
- [x] 14.3 Verify `pip install -e .` works, `ai-music-checker` runs from PATH
- [x] 14.4 Update `README.md` with usage examples, config reference, fixture generation
- [x] 14.5 Run full test suite locally, fix any flaky tests
- [x] 14.6 Performance check: single file <5s offline, <15s online

## 15. Documentation & Archive

- [x] 15.1 Final review of PLAN.md vs implemented features
- [x] 15.2 Update `openspec/changes/ai-music-checker/` artifacts if any drift
- [ ] 15.3 `openspec archive ai-music-checker -y` (after implementation complete)
- [ ] 15.4 Tag release `v0.1.0`, push to GitHub
- [x] 15.5 Update `SIGNALS.md` with all signals including heavy (T8–T10, T12) and SoundCloud (C6)
- [x] 15.6 Update `README.md` with actual usage examples

## 16. Remote Repositories Setup — NEW

- [x] 16.1 Add upstream remote: `git remote add upstream https://github.com/holgerkampffmeyer2/ai-music-checker.git`
- [x] 16.2 Add ai-artists-db remote reference: document in README that community DB is at https://github.com/holgerkampffmeyer2/ai-artists-db.git