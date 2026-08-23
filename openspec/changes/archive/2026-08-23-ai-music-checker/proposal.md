# Proposal: ai-music-checker

## Summary

Forensic heuristic tool to estimate AI-generation likelihood of music files (MP3/WAV/FLAC/AIFF) by combining technical signal analysis (ffmpeg/ffprobe), metadata inspection, and optional online context research. Outputs: machine-readable analysis JSON + ASCII confidence indicator on the CLI.

Includes:
- 16 deterministic criteria across Technical, Metadata, and Context groups
- Community-curated AI artist database (hosted on GitHub, CC0-licensed)
- Optional LLM Judge module for semantic second opinion on borderline cases

## Problem Statement

Modern AI music generators (Suno, Udio, Stable Audio, MusicGen, etc.) produce increasingly convincing tracks that enter commercial channels (Beatport, Spotify, promo pools). Existing tools focus on audio fingerprinting or model-specific detection, which rapidly becomes obsolete. There's no forensic, heuristic-based tool that:
- Works offline-first (no audio upload, no model inference)
- Combines technical, metadata, and contextual signals transparently
- States its own confidence honestly
- Allows community curation of known AI artists
- Provides optional LLM semantic analysis for borderline cases

## Target Users

- DJs, producers, label A&Rs vetting promos
- Music supervisors, sync agents clearing tracks
- Researchers studying AI music proliferation
- Open-source contributors extending detection heuristics

## Scope

### In Scope
- Single-file and batch analysis of local audio files
- Technical signals: spectral analysis, loudness/dynamics, stereo image, noise/seams, encoder chain, sample-rate artifacts, BPM sanity
- Metadata signals: watermark tag scan, identifier gaps, cover EXIF provenance, naming heuristics
- Context signals (opt-in `--online`): artist footprint (MusicBrainz, Discogs, SoundCloud), label patterns, release DB presence, press text analysis, community AI database
- Community AI artist database: JSON hosted on GitHub, fetched with caching/TTL, exact+alias matching
- Optional LLM Judge (opt-in `--llm`): pluggable backends (OpenAI, Anthropic, Ollama, OpenRouter), structured prompt from deterministic signals, strict JSON output, response caching
- Output: JSON (schema v1.0) + ASCII CLI gauge + `--brief` one-liner
- Configurable weights, thresholds, source order via `config.json`

### Out of Scope
- Audio model inference / neural network detection
- DRM circumvention or watermark extraction
- Real-time streaming analysis
- Legal determinations (tool provides heuristic evidence only)
- GUI / web interface

## Success Criteria

1. **Offline analysis** completes in <5s for typical 4-min MP3
2. **Deterministic verdict** on reference fixture (CLMX - Freedom) lands in LIKELY AI-ASSISTED (≥0.60) with `--online`
3. **False positive rate** <10% on curated human-produced test set
4. **LLM Judge** improves borderline (0.4–0.6) classification by ≥15% when rich press text available
5. **Community DB** accepts PRs with CI validation; tool fetches with graceful fallback
6. **CI passes** on every push: unit tests, integration tests, lint (ruff), type check (mypy)