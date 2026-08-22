# ai-music-checker — Project Plan

Estimate AI-generation likelihood of music files (MP3/WAV/FLAC/AIFF) by combining
technical signal analysis (ffmpeg/ffprobe), metadata inspection, and optional
online context research. Outputs: machine-readable analysis JSON + ASCII
confidence indicator on the CLI.

**Decisions:** Python 3 · English docs/UI · location `/mnt/c/work/music/ai-music-checker`
· online lookups behind an opt-in `--online` flag · no hard network dependency.

## 1. Goal & Scope

- Single-file or batch analysis of local audio files
- Detect *signals* that correlate with AI-generated music (Suno, Udio, Stable Audio, etc.)
- Aggregate weighted evidence → probability score + confidence + human-readable verdict
- Offline-first: all technical + metadata checks work without network
- Optional `--online` enriches with MusicBrainz, Discogs, SoundCloud (if key present),
  community AI-database checks
- No model inference on audio — purely forensic/heuristic

## 2. Background / Reference Case

Case study `BV062026_CLMX_-_Freedom_(XTD_Version).mp3`: legit promo MP3
(Beatport release 2026-06-23), but flagged "likely AI-assisted" by Music Worx
editorial; artist has no real footprint (21 IG followers); label shows
content-farm release patterns. Lesson: **no single signal proves AI** — the tool
must aggregate weighted evidence and state its own confidence honestly.

## 3. Architecture / Project Structure

```
ai-music-checker/
├── README.md
├── PLAN.md
├── LICENSE            (MIT)
├── pyproject.toml
├── config.json        (weights, thresholds, source order — user-overridable)
├── .gitignore
├── ai_music_checker/
│   ├── __init__.py
│   ├── cli.py         argparse entry, console script `ai-music-checker`
│   ├── probe.py       ffprobe wrapper (tags, streams, format)
│   ├── lib/           vendored helpers from wav-to-aac-converter
│   │   ├── __init__.py
│   │   ├── shell.py   run_cmd, shq, retry, NetworkError
│   │   ├── http.py    fetch_url, load_env
│   │   └── match.py   fuzzy match / confidence scoring
│   ├── signals/
│   │   ├── __init__.py
│   │   ├── technical.py    T1–T7  (local, always on)
│   │   ├── metadata.py     M1–M4  (local, always on)
│   │   └── context.py      C1–C5  (only with --online)
│   ├── community_db.py  curated AI-artist DB fetch/cache/lookup (TDD)
│   ├── llm_judge.py     optional LLM second-opinion (opt-in, M9)
│   ├── scoring.py     normalization, weighting, verdict, confidence
│   ├── report.py      JSON emitter (schema v1)
│   └── ui.py          ASCII gauge / bars / indicator list
└── tests/
    ├── fixtures/      small synthetic + reference tracks
    ├── test_scoring.py
    ├── test_community_db.py          # unit tests for community DB
    └── integration/
        └── test_context_with_community_db.py
```

## 4. Criteria Catalog (checklist)

Subscore `s ∈ [0,1]` per criterion (1 = strong AI indication), piecewise-linear
thresholds documented per item and tunable via config.json.
`r` = reliability of the criterion itself, `w` = weight (sums to 100).

### Group T — Technical (ffmpeg, local) — group weight 0.40

| ID  | Criterion | Measurement | s→1 when | w | r |
|-----|-----------|-------------|----------|---|---|
| T1  | HF energy profile | volumedetect after highpass @16k/19k, spectral mirror check | hard cutoff ≤16 kHz or mirror artifacts above cutoff | 12 | 0.6 |
| T2  | Dynamics / loudness | loudnorm JSON (I, LRA, TP) + astats crest factor | crest <8 dB, LRA <3 LU wall-of-sound | 8 | 0.5 |
| T3  | Stereo anomalies | side-channel energy distribution | unnatural uniform width / mono master of "club" track | 4 | 0.4 |
| T4  | Noise floor, seams, fades | silence chunks, autocorrelation loop-seam scan, fade shape | digital silence blocks, audible seam repetition | 8 | 0.5 |
| T5  | Encoder chain | encoder/comment tags, LAME Info header generations | suspicious generator strings (see M1) | 5 | 0.7 |
| T6  | Sample-rate artifacts | spectral imaging above cutoff, upsample hints | images/mirrors indicating upscaled generation | 5 | 0.5 |
| T7  | BPM/duration sanity | ffprobe/BPM est. vs claimed genre | implausible combos | 3 | 0.3 |

### Group M — Metadata (local) — group weight 0.25

| ID  | Criterion | Measurement | s→1 when | w | r |
|-----|-----------|-------------|----------|---|---|
| M1  | Watermark/tag scan | all tags/comments vs known-generator pattern list ("suno", "udio", "stable audio", …) + benign whitelist (Promo-Cloud etc.) | direct hit | 12 | 0.9 |
| M2  | Identifier gaps | ISRC/catalog/UPC presence on claimed label release | missing despite commercial context | 7 | 0.5 |
| M3  | Cover provenance | embedded art EXIF/software strings (Midjourney, DALL·E…) | generator string found | 5 | 0.6 |
| M4  | Naming heuristics | artist-name shape (short acronyms like CLMX), version-suffix patterns, catalog-number filenames | multiple heuristic hits | 6 | 0.4 |

### Group C — Context (opt-in `--online`) — group weight 0.35

| ID  | Criterion | Source | s→1 when | w | r |
|-----|-----------|--------|----------|---|---|
| C1  | Artist footprint | MusicBrainz (keyless), Discogs, optional SoundCloud API-v2 (client-id from .env; reuse converter logic, graceful skip) | no entity / negligible followers & releases | 9 | 0.85 |
| C2  | Label pattern | Discogs/MB label stats: cadence, one-release-artist ratio | content-farm signature | 5 | 0.7 |
| C3  | Release DB presence | MB/Discogs/Beatport existence + age | absent everywhere | 4 | 0.6 |
| C4  | Press text / editorial tags | optional page URL input; buzzword density + editorial "AI-assisted" tags found in page | explicit tag / generic text | 3 | 0.6 |
| C5  | Community AI databases | curated JSON DB (hosted on GitHub, configurable URL) + best-effort isthisbandai.org lookup | artist listed in DB with confidence ≥ medium | 4 | 0.8 |

### Community AI Database — C5 Detail

**Data model** (`schema_version: 1.0`):

```json
{
  "schema_version": "1.0",
  "updated": "2026-08-22",
  "license": "CC0-1.0",
  "entries": [
    {
      "id": "clmx",
      "name": "CLMX",
      "aliases": ["Cli-Max", "@clmxmusic"],
      "type": "artist",
      "labels": ["Balearic Vibes Records"],
      "ai_confidence": "high",
      "evidence": [
        {
          "url": "https://pro.music-worx.com/release/freedom-balearic-vibes",
          "note": "editorial 'Likely AI-assisted'",
          "date": "2026-07"
        }
      ],
      "added": "2026-08-22",
      "verified": "2026-08-22"
    }
  ]
}
```

- `ai_confidence`: `"high" | "medium" | "low"` → C5 subscore 1.0 / 0.7 / 0.4
- `evidence`: array of source URLs + notes for auditability
- Matching: exact casefold on `name` + `aliases`; fuzzy opt-in via config (threshold ≥0.9 Jaro-Winkler, flagged as `"fuzzy": true` in result)

**Hosting:** Separate GitHub repo `holgerkampffmeyer2/ai-artists-db` with:
- `known_ai_artists.json` at root
- `schema.json` (JSON Schema) + CI workflow `.github/workflows/validate.yml` running `jsonschema` validation on PRs
- README with contribution guide (PR template: name, aliases, evidence URLs, confidence justification)
- Default fetch URL in config: `https://raw.githubusercontent.com/holgerkampffmeyer2/ai-artists-db/main/known_ai_artists.json`

**Tool integration** (`ai_music_checker/community_db.py`):

```python
class CommunityDB:
    def __init__(self, config): ...
    def load_bundled(self) -> Db: ...           # shipped with package
    def fetch_remote(self, url: str) -> Db: ... # with ETag/Last-Modified + TTL
    def load_or_fetch(self) -> Db: ...          # tries remote → cache → bundled
    def lookup(self, artist: str, aliases: List[str]) -> Match | None: ...
    def subscore(self, match: Match) -> float: ...  # high=1.0, med=0.7, low=0.4
```

**Cache:** `~/.cache/ai-music-checker/known_ai_artists.json` + `fetched_at` timestamp; TTL config `community_db.ttl_hours` (default 24h). Offline → use stale cache + note in analysis.

## 5. Scoring Model

```
W_i        = w_i * r_i * availability_i          # effective weight
group_g    = Σ(W_i*s_i) / Σ(W_i)                 # per group, unavailable drop out
P(ai)      = Σ(group_weight_g * group_g) / Σ(group_weight_g over enabled groups)
confidence = 0.6*coverage + 0.4*consistency
coverage   = ΣW_available / ΣW_possible(enabled groups)
consistency= 1 - normalized mean pairwise |Δgroup_g| (agreement between signal families)
```

Verdict bands:
- ≤0.20 UNAUFFÄLLIG
- 0.21–0.40 EHER MENSCHLICH
- 0.41–0.60 UNKLAR
- 0.61–0.80 LIKELY AI-ASSISTED
- >0.80 VERY LIKELY AI

Top indicators = largest positive/negative `W_i*(s_i−0.5)` contributions.

## 6. Output Design

### JSON (schema_version 1.0)

```json
{
  "schema_version": "1.0",
  "file": {
    "path": "...",
    "size": 12109614,
    "duration_s": 295.13,
    "codec": "mp3",
    "sample_rate": 44100,
    "bitrate": 320000
  },
  "provenance": {
    "timestamp": "...",
    "mode": "online",
    "tool_versions": { "ffmpeg": "6.1.1" },
    "config_hash": "..."
  },
  "signals": [
    {
      "id": "C1",
      "name": "artist_footprint",
      "value": 0.95,
      "subscore": 0.95,
      "weight": 9,
      "reliability": 0.85,
      "available": true,
      "note": "no MB/Discogs entity"
    },
    {
      "id": "C5",
      "name": "community_ai_db",
      "value": 1.0,
      "subscore": 1.0,
      "weight": 4,
      "reliability": 0.8,
      "available": true,
      "note": "CLMX listed in community DB (high confidence)"
    }
  ],
  "groups": {
    "technical": { "score": 0.35, "coverage": 1.0 },
    "metadata": { "score": 0.48, "coverage": 1.0 },
    "context": { "score": 0.81, "coverage": 0.9 }
  },
  "result": {
    "ai_probability": 0.72,
    "verdict": "LIKELY AI-ASSISTED",
    "confidence": 0.61,
    "top_indicators": [
      { "id": "C1", "delta": "+0.09", "text": "No artist history (MusicBrainz/Discogs)" },
      { "id": "C2", "delta": "+0.08", "text": "Label: >20 releases/month, many one-hit projects" },
      { "id": "C5", "delta": "+0.08", "text": "CLMX listed in community AI DB (high)" }
    ],
    "manual_research_hints": [
      "search 'CLMX' on Discogs",
      "check label release cadence on MusicBrainz"
    ]
  },
  "llm_judge": {
    "enabled": true,
    "backend": "openrouter",
    "model": "openai/gpt-4o-mini",
    "probability": 0.78,
    "confidence": 0.65,
    "reasoning": "Press text uses generic 'journey into golden future' phrasing typical of AI marketing; artist has zero discogs footprint despite 2026 label release; technical signals inconclusive but metadata pattern matches known AI-label patterns.",
    "agrees_with_deterministic": true,
    "key_disagreements": []
  },
  "final_ensemble": {
    "ai_probability": 0.74,
    "method": "weighted_average(deterministic=0.7, llm=0.3)"
  }
}
```

### CLI — Full (default)

```
$ ai-music-checker "CLMX - Freedom.mp3" --json freedom.analysis.json [--online]
┌ ai-music-checker ── CLMX - Freedom (XTD Version).mp3 ──────────────────┐
│                                                                          │
│  human ◄░░░░░░░░▒▒▒▒▓▓▓▓████████████████► AI                            │
│                     ▲ 72 %   LIKELY AI-ASSISTED                        │
│  statement confidence:  [███████░░░░░░░] 61 %                          │
│                                                                          │
│  technical  ███████░░░ 0.55   metadata ██████░░░░ 0.48                 │
│  context    █████████░ 0.81                                           │
│                                                                          │
│  ▲ +0.09  C1 no artist history (MusicBrainz/Discogs)                   │
│  ▲ +0.08  C2 label: >20 releases/month, many one-hit projects          │
│  ▲ +0.07  C4 editorial tag "likely AI-assisted"                        │
│  ▲ +0.08  C5 CLMX listed in community AI DB (high confidence)          │
│  ▼ -0.03  T1 full spectrum beyond 19 kHz                               │
└──────────────────────────────────────────────────────────────────────────┘
```

### CLI — Brief (`--brief`)

```
ai-music-checker: 72% AI  ██████████████░░░░░░░  conf 61%  LIKELY AI-ASSISTED  CLMX - Freedom.mp3
```

### Exit Codes
- 0  analysis completed (result in JSON + stdout)
- 1  usage / file error
- 2  ffprobe/ffmpeg missing

## 7. Configuration (config.json)

```json
{
  "weights": {
    "technical": 40,
    "metadata": 25,
    "context": 35
  },
  "criteria": {
    "T1": { "threshold_khz": 16, "severe_khz": 14 },
    "T2": { "crest_db_threshold": 8, "lra_lu_threshold": 3 },
    "M1": { "patterns": ["suno","udio","stable audio","riffusion","musicgen","aiva","soundraw","boomy","ecrett","mubert","loudly"], "whitelist": ["promo-cloud","konkah engine"] },
    "M4": { "acronym_artist_max_len": 5, "suffixes": ["xtd","extended","remix","vocal","instrumental","radio edit"] }
  },
  "metadata_sources": ["musicbrainz","discogs","soundcloud"],
  "soundcloud_client_id_env": "SOUNDCLOUD_CLIENT_ID",
  "request_timeout_s": 10,
  "retry_attempts": 3,
  "community_db": {
    "enabled": true,
    "url": "https://raw.githubusercontent.com/holgerkampffmeyer2/ai-artists-db/main/known_ai_artists.json",
    "ttl_hours": 24,
    "fuzzy_enabled": false,
    "fuzzy_threshold": 0.9
  },
  "llm_judge": {
    "enabled": false,
    "backend": "openrouter",
    "model": "openai/gpt-4o-mini",
    "api_key_env": "OPENROUTER_API_KEY",
    "timeout_s": 30,
    "temperature": 0.1,
    "max_tokens": 1500,
    "prompt_template": "builtin_v1"
  }
}
```

## 8. Reuse from wav-to-aac-converter

Directly vendored (~150 LOC into `ai_music_checker/lib/`):

| Source | Functions | Purpose in checker |
|--------|-----------|-------------------|
| `src/utils.py` | `run_cmd`, `shq` | safe ffmpeg/ffprobe subprocess calls |
| | `retry`, `NetworkError`, `fetch_url` | HTTP lookups with exponential backoff |
| | `load_env`, `validate_soundcloud_client_id` | `.env` + key handling |
| | `calculate_match_confidence`, `_fuzzy_match`, `_word_containment` | match scoring "does this online hit really belong to our file?" |
| | filename parsing helpers (`_parse_separators`, bracket regexes) | naming heuristics (M4) |
| `src/audio_processing.py` | `analyze_loudness` (src/audio_processing.py:25-40) | loudnorm JSON parsing → T2 dynamics |
| `src/metadata.py` | `_lookup_musicbrainz`, `_lookup_itunes`, `_lookup_deezer`, `_lookup_bandcamp`, `_lookup_soundcloud`, `METADATA_SOURCE_DISPATCH`, lookup caches | full dispatch architecture for context group (C1–C5) |
| `src/cover_art.py` | embedded artwork extraction (read path only) | cover EXIF/software check (M3) |

Not reused: encoding, cover embedding, batch parallelism, metadata writing.

## 9. SoundCloud / API Key Handling

Optional enrichment, not a dependency. The converter's logic (`SOUNDCLOUD_CLIENT_ID`
from `.env`, graceful skip when unset, confidence scoring in `try_soundcloud_api_result`)
is reused as-is. If the key is present → include SC footprint signal (profile exists? followers? uploads?). If absent → skip, score renormalizes. Discogs/MusicBrainz remain primary keyless sources.

## 10. Milestones & Tasks

| Milestone | Tasks |
|-----------|-------|
| M0 | `git init`, write `PLAN.md`, `README.md`, `.gitignore`, `pyproject.toml`, `config.json` (default), `LICENSE` |
| M1 | Skeleton: `cli.py`, `probe.py`, `lib/*`, `scoring.py` (math only), `report.py` (JSON schema), `ui.py` (stubs) |
| M2 | Implement technical signals T1–T7 in `signals/technical.py` (ffmpeg-driven, unit-testable) |
| M3 | Implement metadata signals M1–M4 in `signals/metadata.py` |
| M4 | ASCII UI: gauge, group bars, top-indicator list, `--brief` mode |
| M5 | Context module `--online`: MusicBrainz/Discogs/SoundCloud lookups + caches, manual-research hints |
| M6 | **Community DB (TDD):** write unit tests `test_community_db.py` → implement `community_db.py` → write integration tests `test_context_with_community_db.py` → wire C5 into `signals/context.py` → seed `ai-artists-db` repo with schema + CI + initial entries |
| M7 | Golden-file tests: synthetic fixtures + reference track (Freedom.mp3); CI smoke test |
| M8 | Polish: config override precedence, help text, error messages, README usage |
| **M9** | **LLM Judge (opt-in):** `llm_judge.py` with pluggable backends (OpenAI, Anthropic, Ollama, OpenRouter); `--llm` flag + `--llm-backend`/`--llm-model` CLI overrides; structured prompt v1 from deterministic signals + metadata + optional press text; strict JSON output schema; response caching (`~/.cache/ai-music-checker/llm/` keyed by prompt hash); separate `llm_judge` section in output JSON; optional `final_ensemble` weighted combo; docs: env var setup (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`) |

## 11. Test Strategy

- **Unit:** scoring math (golden values for known inputs), normalization edge cases, weight renormalization when groups disabled
- **Community DB unit tests** (`tests/test_community_db.py`):
  - Schema validation: valid entry passes; rejects missing fields, invalid `ai_confidence` enum, duplicate `id`, malformed URLs
  - Lookup: exact match, case-insensitive, alias match, fuzzy above threshold (flagged), no-match returns None
  - Subscore mapping: high→1.0, medium→0.7, low→0.4
  - Bundled load reads package resource
  - Remote fetch: ETag 304 returns cached; timeout falls back to cache; corrupt cache falls back to bundled
  - Config override: custom `url`, `enabled: false` skips network entirely
- **Integration tests** (`tests/integration/test_context_with_community_db.py`):
  - `--online` produces C5 signal in analysis JSON with subscore & note
  - Offline fallback to bundled still produces C5
  - `community_db.enabled: false` → no C5 signal
  - `--brief` output includes C5 delta
  - Fixture "CLMX" → C5 high (golden regression anchor)
- **Audio fixtures** (generated by ffmpeg):
  - sine sweep 20Hz–22kHz (full spectrum reference)
  - lowpassed @14kHz (mimics Suno-style cutoff)
  - white noise + digital silence chunks (T4)
  - dual-mono vs true stereo (T3)
- **Reference fixture:** copy of `BV062026_CLMX_-_Freedom_(XTD_Version).mp3` → expected offline score ~0.35–0.45; with `--online` expected ≥0.60 LIKELY AI-ASSISTED
- **CI:** `pytest -v` on push; lint `ruff` / `mypy`

## 12. Limits, Risks, Legal Notes

- **No audio-only proof:** modern generators (Udio v4, Suno v4) produce full-bandwidth audio; technical signals alone are weak
- **False positives:** real artists with minimal footprint, bedroom producers with heavy compression, legitimate promo MP3s lacking ISRC
- **API rate limits:** MusicBrainz 1 req/s (set UA), Discogs 60 req/min (token optional), SoundCloud undocumented → implement polite backoff + caching
- **Scraping fragility:** `isthisbandai.org` best-effort; maintain local curated JSON list as primary
- **Legal:** only reads public metadata; no DRM circumvention; user responsible for files analyzed
- **Community DB:** entries are curated claims with evidence URLs; not legal determinations; CC0 license maximizes reuse
- **Distribution:** single-file script or `pipx` install; no compilation needed

## 13. Open Review Questions

1. Verdict labels: German or English? (CLI outputs currently English — consistent with docs decision)
2. Confidence formula weights (0.6/0.4 coverage/consistency) — tune after M2–M3?
3. Should T4 seam detection use numpy autocorrelation (adds dep) or pure ffmpeg silencedetect (simpler, weaker)?
4. **Community DB repo:** separate `holgerkampffmeyer2/ai-artists-db` (recommended) or same repo `data/`? Confirm org/account.
5. **Seed data:** research & seed ~10–15 documented entries during implementation (e.g., The Velvet Sundown, Anna Indiana) or scaffold schema + placeholders for later curation?
6. **License:** CC0-1.0 (public domain dedication) or CC-BY-4.0 (attribution)? CC0 maximizes reuse.
7. **Matching strictness:** default exact+alias only; fuzzy opt-in via config — acceptable?
8. Batch mode: process multiple files sequentially? Parallel? Output summary table?
9. Config precedence: file → env vars → CLI flags? Define clearly.
10. **LLM Judge weight in ensemble**: default 0.3 LLM / 0.7 deterministic — tune after eval?
11. **Prompt versioning**: store prompt hash in output for reproducibility?
12. **Local LLM support**: Ollama backend for fully offline LLM judging?