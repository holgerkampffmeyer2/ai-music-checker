# ai-music-checker

Forensic heuristic tool to estimate AI-generation likelihood of music files
(MP3/WAV/FLAC/AIFF). Combines technical signal analysis, metadata inspection,
and optional online context research.

**Status:** Planning phase — see [PLAN.md](PLAN.md) for full specification.

## Quick Start (planned)

```bash
# Offline analysis (technical + metadata only)
ai-music-checker track.mp3 --json analysis.json

# With online enrichment (MusicBrainz, Discogs, SoundCloud)
ai-music-checker track.mp3 --online --json analysis.json

# Brief one-liner output
ai-music-checker track.mp3 --brief
```

## Design Principles

- Offline-first: core signals require no network
- Transparent: every indicator shown with weight & reliability
- No ML inference — purely forensic/heuristic
- Reuses battle-tested ffmpeg/ffprobe wrappers from wav-to-aac-converter

## Development

```bash
pip install -e .
pytest -v
```

See [PLAN.md](PLAN.md) for milestones, criteria catalog, and open questions.