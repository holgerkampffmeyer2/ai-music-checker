# ai-music-checker

![AI Music Checker](assets/ai-music-checker.png)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://github.com/holgerkampffmeyer2/ai-music-checker)
[![License](https://img.shields.io/github/license/holgerkampffmeyer2/ai-music-checker)](https://github.com/holgerkampffmeyer2/ai-music-checker)
[![Tests](https://github.com/holgerkampffmeyer2/ai-music-checker/actions/workflows/test.yml/badge.svg)](https://github.com/holgerkampffmeyer2/ai-music-checker/actions/workflows/test.yml)

Forensic heuristic tool to estimate AI-generation likelihood of music files (MP3/WAV/FLAC/AIFF). Combines technical signal analysis, metadata inspection, and optional online context research.

## Installation

### From Binary (Recommended)

Download the latest release for your platform from [Releases](https://github.com/holgerkampffmeyer2/ai-music-checker/releases) or use the install script:

```bash
curl -fsSL https://raw.githubusercontent.com/holgerkampffmeyer2/ai-music-checker/main/install.sh | bash
```

### From Source

```bash
# Clone repository
git clone https://github.com/holgerkampffmeyer2/ai-music-checker.git
cd ai-music-checker

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in editable mode
pip install -e .

# Or install with dev dependencies
pip install -e ".[dev]"
```

### Run Without Installation

```bash
# Create venv and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Or run directly as module (after pip install)
python -m ai_music_checker.cli track.mp3
```

**Prerequisites:**
- Python 3.10+
- ffmpeg/ffprobe installed and in PATH (binary installs include bundled ffmpeg)

## Quick Start

```bash
# Basic analysis (offline, technical + metadata signals only)
ai-music-checker track.mp3

# Alternative: direct Python module call (no install needed)
python -m ai_music_checker.cli track.mp3

# Brief one-line output
ai-music-checker track.mp3 --brief

# JSON output for programmatic use
ai-music-checker track.mp3 --json analysis.json

# Verbose full-mode output with group scores and indicators
ai-music-checker track.mp3 --no-color
```

## Usage Modes

### Single File Analysis

```bash
# Offline analysis (default) — no network required
ai-music-checker track.mp3

# Online enrichment — queries MusicBrainz, Discogs, SoundCloud, Community DB
ai-music-checker track.mp3 --online

# Heavy signals — compute-intensive FFT, phase, transient analysis
ai-music-checker track.mp3 --heavy

# Full online + heavy mode
ai-music-checker track.mp3 --online --heavy

# LLM second opinion via agent skill — no external API key needed
ai-music-checker track.mp3 --llm-agent
ai-music-checker track.mp3 --llm-agent --online --heavy --json result.json
```

### Batch Processing

```bash
# Process multiple files
ai-music-checker *.mp3

# Process entire directory
ai-music-checker /path/to/music/

# Recursive directory scan
ai-music-checker /path/to/music/ --recursive

# Parallel processing (default: 5 workers)
ai-music-checker /path/to/music/ --recursive --max-workers 8

# Mixed file types
ai-music-checker *.mp3 *.wav *.flac
```

### Output Formats

```bash
# Full ASCII output (default)
ai-music-checker track.mp3
╭─ track.mp3
│
│  ░░░░░░░░░░░░░░░░░░░░▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒ 37%  LIKELY AI-ASSISTED
│  Confidence: ░░░░░░░░░░░░░░░░░░░░ 62%
│
│ Group scores:
│   technical  ░░░░░░░░░░░░░░░░░░░░ 42% (100%)
│   metadata   ░░░░░░░░░░░░░░░░░░░░ 15% (100%)
│   context    ░░░░░░░░░░░░░░░░░░░░ 68% (85%)
│
│ Top indicators:
│   ▲ C1: no footprint found for 'CLMX'
│   ▲ T1: hard cutoff below severe threshold
│   ▲ M4: short uppercase artist 'CLMX'
╰────────────────────────────────────────────────────────────

# Brief single-line output
ai-music-checker track.mp3 --brief
░░░░░░░░░░ 37%  62%  LIKELY AI-ASSISTED  track.mp3

# JSON output (schema v1.0)
ai-music-checker track.mp3 --json result.json
cat result.json | jq '.result.verdict'

# JSON to stdout
ai-music-checker track.mp3 --json -

# Batch JSON (one file per input)
ai-music-checker *.mp3 --json output_dir/
```

### Configuration

```bash
# Use custom config file
ai-music-checker track.mp3 --config /path/to/config.json

# Show effective configuration and exit
ai-music-checker --show-config

# Disable colored output
ai-music-checker track.mp3 --no-color
```

### Evidence Checking

```bash
# Check evidence URLs in community database
ai-music-checker --check-evidence

# Check and apply changes (remove broken evidence after retention period)
ai-music-checker --check-evidence --apply

# Suggest new DB entries from analyzed files
ai-music-checker *.mp3 --suggest-db --min-ai-probability 0.7

# Save suggestions to file
ai-music-checker *.mp3 --suggest-db --save-suggestions suggestions.json
```

### DB Suggestion Workflow (`--suggest-db`)

The `--suggest-db` flag implements a complete workflow for proposing new artists to the community AI artist database:

#### Workflow Steps

1. **Analyse track** — Full signal analysis (technical, metadata, context if `--online`)
2. **Check community DB** — Look up artist in cached/fetched DB (exact + alias + optional fuzzy)
3. **Evaluate online AI indication** — Check C1 (artist footprint), C2 (label pattern), C5 (community DB), C4 (press text)
4. **Propose entry** — If AI probability ≥ `--min-ai-probability` (default 0.6):
   - Artist already in DB with `high` confidence → no suggestion (already documented)
   - Artist in DB with `medium`/`low` → suggestion with `db_status: already_in_db`
   - Not in DB → suggestion with `db_status: not_in_db` and `online_ai_indication` flag

#### Usage

```bash
# Basic suggestion with threshold
ai-music-checker track.mp3 --suggest-db --min-ai-probability 0.6

# With online context signals (recommended)
ai-music-checker track.mp3 --online --suggest-db --min-ai-probability 0.6

# Batch processing with JSON output
ai-music-checker *.mp3 --online --suggest-db --save-suggestions suggestions.json
```

#### Suggestion Output

Each suggestion includes:
- `db_status`: `not_in_db` | `already_in_db`
- `online_ai_indication`: boolean
- `reason_code`: comma-separated codes (e.g., `C1_no_footprint,C2_content_farm,C5_db_match`)
- `evidence`: local analysis + online signals with URLs and dates

### Environment Variables

All config options can be overridden via environment variables with `AIMC_` prefix:

```bash
# Enable community DB
export AIMC_COMMUNITY_DB_ENABLED=true

# Set custom SoundCloud client ID
export SOUNDCLOUD_CLIENT_ID=your_client_id_here

# LLM judge API key for external backends (openrouter/ollama)
# Not needed for --llm-agent which uses the internal agent skill
export OPENROUTER_API_KEY=your_key_here

# Override group weights
export AIMC_WEIGHTS_TECHNICAL=15
export AIMC_WEIGHTS_METADATA=5
export AIMC_WEIGHTS_CONTEXT=80
```

## Signal Catalog

| Group | Weight | Signals | Description |
|-------|--------|---------|-------------|
| **Technical** | 15% | T1–T7 | Spectral, dynamics, stereo, noise, encoder, sample-rate, BPM |
| **Metadata** | 5% | M1–M4 | Watermarks, identifiers, cover art, naming heuristics |
| **Context** | 80% | C1–C5 | Artist footprint, label pattern, release DB, press text, community DB (strongest indicator) |
| **Heavy** | opt-in | T8–T13 | Spectral mirror, phase coherence, transients, spectral flatness, stem separation, HF resampling |
| **SoundCloud** | opt-in | C6 | API v2 search with confidence scoring |

### Signal Details

| ID | Name | Weight | Reliability | Description |
|----|------|--------|-------------|-------------|
| T1 | hf_energy_profile | 12 | 0.6 | High-frequency energy analysis (16kHz/14kHz cutoffs) |
| T2 | dynamics_loudness | 8 | 0.5 | Dynamic range and loudness analysis (crest factor, LRA) |
| T3 | stereo_anomalies | 4 | 0.4 | Mid/side energy distribution (mono detection) |
| T4 | noise_seams_fades | 8 | 0.5 | Digital silence blocks and loop seams |
| T5 | encoder_chain | 5 | 0.7 | Generator patterns in encoder tags |
| T6 | sr_artifacts | 5 | 0.5 | Sample rate anomalies and upsample hints |
| T7 | bpm_duration_sanity | 3 | 0.3 | Track duration sanity check |
| T8 | spectral_mirror | 7 | 0.6 | Nyquist/2 mirroring detection (heavy) |
| T9 | phase_coherence | 6 | 0.5 | L/R channel phase correlation (heavy) |
| T10 | transient_preservation | 5 | 0.4 | Onset detection and transient sharpness (heavy) |
| T11 | spectral_flatness | 6 | 0.5 | Ebur128 loudness variance proxy for spectral flatness (heavy) |
| T12 | stem_consistency | 4 | 0.3 | Stem separation analysis (placeholder) |
| T13 | hf_resampling | 5 | 0.4 | High-frequency resampling cutoff detection (heavy) |
| M1 | watermark_scan | 12 | 0.9 | Generator pattern matching in tags |
| M2 | identifier_gaps | 7 | 0.5 | ISRC/catalog/UPC presence check |
| M3 | cover_provenance | 5 | 0.6 | Embedded artwork EXIF/software strings |
| M4 | naming_heuristics | 4 | 0.4 | Filename parsing (acronyms, suffixes, catalog patterns) |
| C1 | artist_footprint | 5 | 0.6 | MusicBrainz, Discogs, SoundCloud presence |
| C2 | label_pattern | 6 | 0.5 | Release cadence and label statistics |
| C3 | release_db_presence | 7 | 0.6 | MB/Discogs/Beatport existence and age |
| C4 | press_text | 5 | 0.4 | Buzzword density in linked pages |
| C5 | community_db | 9 | 0.8 | Known AI artists database lookup |
| C6 | soundcloud_fingerprint | 7 | 0.7 | SoundCloud API v2 with confidence scoring |

## Verdict Bands

| Score Range | Verdict | Meaning |
|-------------|---------|---------|
| ≤0.20 | UNOBTRUSIVE | No suspicious signals |
| 0.21–0.40 | LIKELY HUMAN | Likely human-made |
| 0.41–0.60 | UNCLEAR | Uncertain |
| 0.61–0.80 | LIKELY AI-ASSISTED | AI-assisted likely |
| >0.80 | VERY LIKELY AI | Very likely AI-generated |

## Configuration

Precedence: **CLI > ENV (AIMC_) > config.json > defaults**

### config.json

```json
{
  "weights": {
    "technical": 15,
    "metadata": 5,
    "context": 80
  },
  "criteria": {
    "T1": {"threshold_khz": 16, "severe_khz": 14},
    "M1": {
      "patterns": ["suno", "udio", "stable audio"],
      "whitelist": ["promo-cloud"]
    }
  },
  "community_db": {
    "enabled": true,
    "url": "https://raw.githubusercontent.com/holgerkampffmeyer2/ai-artists-db/main/known_ai_artists.json",
    "ttl_hours": 24
  },
  "evidence": {
    "check_urls": false,
    "timeout_s": 10
  },
  "db_suggest": {
    "enabled": false,
    "min_ai_probability": 0.6
  }
}
```

## Community AI Artist Database

The tool uses a curated database of known AI artists/labels maintained at:
**https://github.com/holgerkampffmeyer2/ai-artists-db**

Entries include: CLMX, Anna Indiana, The Velvet Sundown, AIVA, Soundraw, Boomy, Mubert, Loudly, and more.

### Contributing to the Database

The easiest way to contribute is via GitHub Issues:

1. Go to [ai-artists-db Issues](https://github.com/holgerkampffmeyer2/ai-artists-db/issues/new/choose)
2. Select **"Add AI Artist Entry"** template
3. Fill in artist details and evidence
4. Submit — maintainer reviews and auto-creates PR

Alternatively, fork the repo and submit a PR directly. See [CONTRIBUTING.md](https://github.com/holgerkampffmeyer2/ai-artists-db#contributing) for details.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest -v

# Run specific test class
pytest tests/test_signals_technical.py::TestT1HfEnergyProfile -v

# Lint
ruff check .

# Type check
mypy ai_music_checker

# Generate test fixtures
python tests/generate_fixtures.py
```

### Build Binary

```bash
pip install pyinstaller
pyinstaller pyinstaller/ai-music-checker.spec
# Output: dist/ai-music-checker/ai-music-checker
```

### Release

```bash
# 1. Update version in pyproject.toml
# 2. Commit changes
# 3. Create and push tag
git tag v0.1.0
git push origin v0.1.0
# GitHub Actions runs tests, builds binaries, creates GitHub Release
```

## JSON Schema

Output follows schema v1.0 defined in `data/schema.json`. Example structure:

```json
{
  "schema_version": "1.0",
  "file": {
    "path": "/path/to/track.mp3",
    "name": "track.mp3",
    "format": "mp3",
    "duration_s": 213.5,
    "bitrate_bps": 320000,
    "sample_rate_hz": 44100,
    "channels": 2,
    "codec": "mp3"
  },
  "provenance": {
    "encoder": "LAME3.100",
    "tags_present": true,
    "tag_keys": ["artist", "title", "album"],
    "has_cover_stream": false
  },
  "signals": [
    {
      "id": "T1",
      "name": "hf_energy_profile",
      "group": "technical",
      "value": -45.2,
      "subscore": 0.0,
      "weight": 12,
      "reliability": 0.6,
      "available": true,
      "note": "full HF energy above 16 kHz"
    }
  ],
  "groups": {
    "technical": {"score": 0.42, "coverage": 1.0},
    "metadata": {"score": 0.15, "coverage": 1.0},
    "context": {"score": 0.68, "coverage": 0.85}
  },
  "result": {
    "ai_probability": 0.37,
    "verdict": "LIKELY AI-ASSISTED",
    "confidence": 0.62,
    "coverage": 0.95,
    "consistency": 0.78,
    "top_indicators": [
      {"id": "C1", "delta": 0.12, "note": "no footprint found for 'CLMX'"}
    ],
    "manual_research_hints": []
  }
}
```

## License

MIT — see [LICENSE](LICENSE)