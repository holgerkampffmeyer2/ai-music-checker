# AGENTS.md — ai-music-checker

## Project Overview

Forensic heuristic tool to estimate AI-generation likelihood of music files (MP3/WAV/FLAC/AIFF). Combines technical signal analysis (ffmpeg), metadata inspection, and optional online context research. No model inference — purely rule-based scoring.

## Setup

```bash
cd /mnt/c/work/music/ai-music-checker
source .venv/bin/activate
```

All commands below assume the venv is active.

## Essential Commands

### Run tests
```bash
rtk pytest tests/ -v
```

### Lint
```bash
ruff check ai_music_checker/
```

### Type check
```bash
mypy ai_music_checker
```

### Analyze a single file
```bash
ai-music-checker track.mp3

# Alternative: direct Python module call
python -m ai_music_checker.cli track.mp3
```

### Analyze all MP3s in directory
```bash
ai-music-checker *.mp3
```

### Brief one-line output
```bash
ai-music-checker *.mp3 --brief
```

### JSON output
```bash
ai-music-checker track.mp3 --json result.json
ai-music-checker *.mp3 --json output_dir/
```

### Online mode (MusicBrainz, Discogs, Community DB)
```bash
ai-music-checker track.mp3 --online
```

### Heavy mode (FFT, phase, transient analysis)
```bash
ai-music-checker track.mp3 --heavy
```

### Full mode
```bash
ai-music-checker track.mp3 --online --heavy
```

### Disable color
```bash
ai-music-checker track.mp3 --no-color
```

## CLI Flags

| Flag | Description |
|------|-------------|
| `--brief` | Single-line output per file |
| `--json <path>` | JSON output (file path or `-` for stdout) |
| `--online` | Enable context group (MusicBrainz, Discogs, Community DB) |
| `--heavy` | Enable heavy signals (FFT, phase, transients) |
| `--llm-agent` | Enable LLM second-opinion via agent skill |
| `--no-color` | Disable ANSI color |
| `--config <path>` | Custom config.json |
| `--max-workers <n>` | Parallel workers (default 5) |
| `--recursive` | Recursive directory scan |
| `--check-evidence` | Check evidence URLs in community DB and report status |
| `--apply` | Apply changes (remove broken evidence after retention period) |
| `--suggest-db` | Suggest new community DB entries based on analysis |
| `--min-ai-probability` | Minimum AI probability to suggest DB entry (default: 0.6) |
| `--save-suggestions <path>` | Save DB suggestions to JSON file |

## DB Suggestion Workflow (`--suggest-db`)

The `--suggest-db` flag implements a complete workflow for proposing new artists to the community AI artist database:

### Workflow Steps

1. **Analyse track** — Full signal analysis (technical, metadata, context if `--online`)
2. **Check community DB** — Look up artist in cached/fetched DB (exact + alias + optional fuzzy)
3. **Evaluate online AI indication** — Check C1 (artist footprint), C2 (label pattern), C5 (community DB), C4 (press text)
4. **Propose entry** — If AI probability ≥ `--min-ai-probability` (default 0.6):
   - Artist already in DB with `high` confidence → no suggestion (already documented)
   - Artist in DB with `medium`/`low` → suggestion with `db_status: already_in_db`
   - Not in DB → suggestion with `db_status: not_in_db` and `online_ai_indication` flag

### Usage

```bash
# Basic suggestion with threshold
ai-music-checker track.mp3 --suggest-db --min-ai-probability 0.6

# With online context signals (recommended)
ai-music-checker track.mp3 --online --suggest-db --min-ai-probability 0.6

# Batch processing with JSON output
ai-music-checker *.mp3 --online --suggest-db --save-suggestions suggestions.json
```

### Suggestion Output

Each suggestion includes:
- `db_status`: `not_in_db` | `already_in_db`
- `online_ai_indication`: boolean
- `reason_code`: comma-separated codes (e.g., `C1_no_footprint,C2_content_farm,C5_db_match`)
- `evidence`: local analysis + online signals with URLs and dates

## Exit Codes

- `0` — analysis completed
- `1` — usage / file error
- `2` — ffmpeg/ffprobe missing

## Project Structure

```
ai_music_checker/
├── cli.py              # Entry point, argparse, batch processing
├── probe.py            # ffprobe wrapper (tags, streams, format)
├── lib/
│   ├── shell.py        # run_cmd, shq (subprocess helpers)
│   ├── http.py         # fetch_url with retry/backoff
│   └── match.py        # Fuzzy match, confidence scoring
├── signals/
│   ├── technical.py    # T1–T7 (always on)
│   ├── metadata.py     # M1–M4 (always on)
│   ├── context.py      # C1–C5 (--online)
│   ├── heavy.py        # T8–T13 (--heavy)
│   └── soundcloud.py   # C6 (opt-in SoundCloud API)
├── community_db.py     # AI-artist DB fetch/cache/lookup
├── llm_judge.py        # Optional LLM second-opinion (--llm)
├── scoring.py          # Weighted aggregation, verdict, confidence
├── report.py           # JSON emitter (schema v1)
└── ui.py               # ASCII gauge, bars, indicator list
```

## Signal Groups & Weights

| Group | Weight | Signals | Mode |
|-------|--------|---------|------|
| Technical | 15% | T1–T7 | always on |
| Metadata | 5% | M1–M4 | always on |
| Context | 80% | C1–C5 | `--online` |
| Heavy | opt-in | T8–T13 | `--heavy` |

## Verdict Bands

| Score | Verdict |
|-------|---------|
| ≤0.20 | UNOBTRUSIVE |
| 0.21–0.40 | LIKELY HUMAN |
| 0.41–0.60 | UNCLEAR |
| 0.61–0.80 | LIKELY AI-ASSISTED |
| >0.80 | VERY LIKELY AI |

## Configuration

Precedence: CLI > ENV (AIMC_) > config.json > defaults

Config file: `config.json` in project root.

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `AIMC_COMMUNITY_DB_ENABLED` | Enable/disable community DB |
| `SOUNDCLOUD_CLIENT_ID` | SoundCloud API key |
| `OPENROUTER_API_KEY` | LLM judge API key |

## Key Files

- `PLAN.md` — Full project spec, scoring model, JSON schema
- `config.json` — Weights, thresholds, DB config
- `tests/` — pytest suite (169 tests)
- `.github/workflows/test.yml` — CI tests on push/PR
- `.github/workflows/release.yml` — Build binaries on tag push (v*)
- `pyinstaller/ai-music-checker.spec` — PyInstaller build config
- `install.sh` — Binary install script

## Rules

- Always run from project root `/mnt/c/work/music/ai-music-checker`
- Activate venv before running: `source .venv/bin/activate`
- Run `ruff check` before committing
- MP3 files in root are test data — do not delete
- Community AI Artists DB is source of truth in separate repo `/mnt/c/work/ai-artists-db/known_ai_artists.json`. Future DB entries must be added there, not in `ai_music_checker/data/known_ai_artists.json`. Local bundled copy is deprecated and will be removed.

## Build & Release

### Build binary locally
```bash
pip install pyinstaller
pyinstaller pyinstaller/ai-music-checker.spec
# Binary: dist/ai-music-checker/ai-music-checker
```

### Create release
```bash
git tag v0.1.0
git push origin v0.1.0
# GitHub Actions builds Linux + macOS binaries and creates release
```

### Release process
1. Update version in `pyproject.toml`
2. Commit changes
3. Create tag: `git tag v<version>`
4. Push tag: `git push origin v<version>`
5. GitHub Actions runs tests, builds binaries, creates GitHub Release
