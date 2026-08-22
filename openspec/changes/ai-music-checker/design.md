# Design: ai-music-checker

## Context

Greenfield Python CLI tool. Reference implementation patterns from existing `wav-to-aac-converter` (same workspace) for ffmpeg/ffprobe wrappers, HTTP retry logic, SoundCloud API integration, filename parsing, match confidence scoring. Target: Python 3.10+, offline-first, deterministic core, optional network enrichment.

## Goals / Non-Goals

**Goals:**
- Modular, testable signal pipeline: each criterion independent, composable
- Clear separation: signal extraction → normalization → weighting → verdict
- Pluggable online sources (MusicBrainz, Discogs, SoundCloud, Community DB, LLM)
- Deterministic JSON output (schema v1) + polished ASCII UI
- TDD from day one: unit + integration + fixture-based regression

**Non-Goals:**
- Audio ML inference
- Real-time/streaming analysis
- GUI/Web interface
- DRM/watermark extraction
- Legal determinations

## Decisions

### 1. Module Layout (Package: `ai_music_checker`)

```
ai_music_checker/
├── __init__.py           # version, exports
├── cli.py                # argparse, subcommands, exit codes
├── probe.py              # ffprobe wrapper → FileProbe dataclass
├── config.py             # Config dataclass + loader (CLI > env > file > defaults)
├── scoring.py            # pure functions: normalize, weight, aggregate, verdict, confidence
├── report.py             # JSON emitter (schema v1), dataclasses for output
├── ui.py                 # ASCII renderer (gauge, bars, brief)
├── lib/                  # vendored from wav-to-aac-converter
│   ├── shell.py          # run_cmd, shq, retry, NetworkError
│   ├── http.py           # fetch_url, load_env
│   └── match.py          # fuzzy_match, calculate_match_confidence
├── signals/
│   ├── __init__.py       # SignalProtocol, registry
│   ├── technical.py      # T1–T7 implementations
│   ├── metadata.py       # M1–M4 implementations
│   └── context.py        # C1–C5 implementations (require --online)
├── community_db.py       # DB fetch/cache/lookup (TDD)
└── llm_judge.py          # LLM backend abstraction, prompt builder, cache (M9)
```

### 2. Signal Protocol (Strategy Pattern)

```python
# signals/__init__.py
from dataclasses import dataclass
from typing import Protocol, Optional

@dataclass
class SignalResult:
    id: str                    # e.g. "T1"
    name: str                  # e.g. "hf_energy_profile"
    value: float               # raw measured value
    subscore: float            # normalized 0..1 (1 = strong AI indication)
    weight: int                # from config
    reliability: float         # from config
    available: bool            # False if dependency missing (e.g. no network)
    note: str                  # human-readable detail

class Signal(Protocol):
    id: str
    name: str
    group: str                 # "technical" | "metadata" | "context"
    weight: int
    reliability: float

    def compute(self, probe: FileProbe, config: Config) -> SignalResult: ...
    def available(self, config: Config) -> bool: ...
```

Each signal module registers instances in `SIGNAL_REGISTRY = [T1(), T2(), ..., C5()]`. Runner filters by `available(config)` and group enablement.

### 3. Data Flow

```
cli.py
  ├─ parse args → Config (merged)
  ├─ for each file:
  │    ├─ probe.py → FileProbe (tags, streams, format, duration, etc.)
  │    ├─ signals.run_all(probe, config) → list[SignalResult]
  │    ├─ scoring.aggregate(results, config) → AggregateResult
  │    ├─ if --llm: llm_judge.analyze(aggregate, probe, config) → LLMResult
  │    ├─ report.build(probe, results, aggregate, llm_result) → AnalysisJSON
  │    └─ ui.render(aggregate, llm_result, brief_flag) → stdout
```

### 4. Scoring Math (Pure Functions)

```python
# scoring.py
def effective_weight(w: int, r: float, available: bool) -> float:
    return w * r * (1.0 if available else 0.0)

def group_score(results: list[SignalResult], group: str) -> tuple[float, float]:
    """Returns (score, coverage) for group."""
    group_results = [r for r in results if SIGNAL_META[r.id].group == group]
    if not group_results: return (0.0, 0.0)
    total_w = sum(effective_weight(r.weight, r.reliability, r.available) for r in group_results)
    if total_w == 0: return (0.0, 0.0)
    score = sum(effective_weight(r.weight, r.reliability, r.available) * r.subscore
                for r in group_results) / total_w
    coverage = sum(effective_weight(r.weight, r.reliability, r.available)
                   for r in group_results if r.available) / \
               sum(effective_weight(r.weight, r.reliability, True) for r in group_results)
    return (score, coverage)

def aggregate(group_scores: dict[str, tuple[float, float]], config: Config) -> AggregateResult:
    # group weights from config.weights (technical=40, metadata=25, context=35)
    # renormalize over enabled groups (context excluded if not --online)
    ...

def confidence(coverage: float, consistency: float) -> float:
    return 0.6 * coverage + 0.4 * consistency

def consistency(group_scores: dict[str, float]) -> float:
    vals = [s for s, _ in group_scores.values() if s > 0]
    if len(vals) < 2: return 1.0
    mean = sum(vals) / len(vals)
    mean_abs_dev = sum(abs(v - mean) for v in vals) / len(vals)
    return max(0.0, 1.0 - mean_abs_dev * 2)  # maps 0.5 dev → 0
```

### 5. Configuration System

```python
# config.py
@dataclass
class Config:
    weights: GroupWeights
    criteria: CriteriaConfig
    metadata_sources: list[str]
    soundcloud_client_id_env: str
    request_timeout_s: int
    retry_attempts: int
    community_db: CommunityDBConfig
    llm_judge: LLMJudgeConfig

    @classmethod
    def load(cls, cli_overrides: dict = None) -> "Config":
        # 1. defaults
        # 2. config.json (if exists)
        # 3. env vars (prefix AIMC_)
        # 4. CLI overrides
        # merge with deep update for nested dicts
```

Env var prefix: `AIMC_` (e.g., `AIMC_LLM_JUDGE_ENABLED=true`, `AIMC_COMMUNITY_DB_URL=...`).

### 6. Community DB Design

```python
# community_db.py
@dataclass
class DBEntry:
    id: str
    name: str
    aliases: list[str]
    type: str
    labels: list[str]
    ai_confidence: Literal["high", "medium", "low"]
    evidence: list[Evidence]
    added: date
    verified: date

@dataclass
class CommunityDB:
    schema_version: str
    updated: date
    license: str
    entries: list[DBEntry]

    def lookup(self, artist: str, aliases: list[str], fuzzy: bool, threshold: float) -> Optional[Match]:
        # exact casefold on name + aliases first
        # if fuzzy and no exact: Jaro-Winkler ≥ threshold on name
        # returns Match(entry, fuzzy=bool)
```

Cache: `~/.cache/ai-music-checker/known_ai_artists.json` with `fetched_at` ISO timestamp. TTL from config (default 24h). Stale cache used offline with warning in signal note.

### 7. LLM Judge Design (M9)

```python
# llm_judge.py
class LLMBackend(Protocol):
    async def complete(self, prompt: str, config: LLMJudgeConfig) -> str: ...

class OpenAIBackend: ...
class AnthropicBackend: ...
class OllamaBackend: ...
class OpenRouterBackend: ...

PROMPT_V1 = """You are a music forensics analyst. Given deterministic signal analysis of an audio file,
provide a semantic second opinion on AI-generation likelihood.

DETERMINISTIC RESULT:
{deterministic_json}

FILE METADATA:
{file_metadata}

PRESS TEXT (if any):
{press_text}

Respond ONLY with JSON:
{
  "probability": 0.0-1.0,
  "confidence": 0.0-1.0,
  "reasoning": "concise explanation",
  "agrees_with_deterministic": true|false,
  "key_disagreements": ["..."]
}"""

def build_prompt(aggregate: AggregateResult, probe: FileProbe, press_text: str) -> str: ...
```

Cache key: SHA256(prompt + model + temperature). Stored in `~/.cache/ai-music-checker/llm/<hash>.json`.

### 8. JSON Schema (v1.0)

Defined in `report.py` using `dataclasses` + `dataclass-json` or manual `to_dict()`. Key structure:

```json
{
  "schema_version": "1.0",
  "file": {...},
  "provenance": {...},
  "signals": [SignalResult...],
  "groups": {"technical": {"score": 0.35, "coverage": 1.0}, ...},
  "result": {"ai_probability": 0.72, "verdict": "LIKELY AI-ASSISTED", "confidence": 0.61, "top_indicators": [...], "manual_research_hints": [...]},
  "llm_judge": {...},           // optional
  "final_ensemble": {...}       // optional
}
```

### 9. ASCII UI Design

- **Full mode**: Box-drawing chars (┌─┐│└┘├┤┬┴┼), gauge bar with 4 color zones (░▒▓█), group bars, top-indicator table with ▲/▼ deltas
- **Brief mode**: Single line with compact gauge (15 chars), percentage, confidence, verdict, filename
- No external UI libs; pure string formatting

### 10. Test Architecture

```
tests/
├── fixtures/
│   ├── synthetic/
│   │   ├── full_spectrum.wav       # sine sweep 20-22kHz
│   │   ├── lowpass_14khz.wav       # mimics Suno cutoff
│   │   ├── silence_chunks.wav      # digital silence blocks
│   │   └── dual_mono.wav           # mono L=R vs true stereo
│   └── reference/
│       └── freedom.mp3             # CLMX fixture (gitignored, local copy)
├── test_scoring.py                 # pure math golden values
├── test_community_db.py            # schema, lookup, cache, fallback
├── test_llm_judge.py               # prompt build, cache, backend mock
└── integration/
    ├── test_context_signals.py     # --online C1–C5 with mocked HTTP
    └── test_cli.py                 # end-to-end CLI with fixtures
```

Fixtures generated by `tests/generate_fixtures.py` (run once, committed).

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| ffprobe output parsing brittle | Wrap in probe.py with defensive parsing; version-pin test fixtures |
| Online APIs rate-limited / changed | Polite UA, exponential backoff, generous timeouts, cache aggressively |
| Community DB stale / poisoned | CI schema validation, signed releases, TTL + bundled fallback, evidence URLs required |
| LLM non-determinism | Temperature 0.1, strict JSON schema, prompt version hash in output, cache by prompt hash |
| False positives on niche human artists | High reliability weights on technical signals, conservative thresholds, manual research hints |
| Config complexity | Sensible defaults, `--show-config` debug flag, documented precedence |

## Alternatives Considered

| Decision | Alternative | Why Rejected |
|----------|-------------|--------------|
| Strategy pattern for signals | Monolithic analyzer class | Harder to test, extend, disable per-criterion |
| JSON config + env + CLI | YAML/TOML only | JSON stdlib, no extra dep; env for secrets |
| OpenRouter as default LLM | OpenAI direct | Single key → multiple models; cheaper fallback |
| Separate ai-artists-db repo | data/ in this repo | Independent versioning, community PRs, CI validation |
| Jaro-Winkler for fuzzy | Levenshtein / rapidfuzz | No extra dep; stdlib `difflib.SequenceMatcher` close enough |

## Open Questions for Implementation

1. **Verdict labels**: English (current) vs German — lock to English per docs decision
2. **T4 seam detection**: Start with `ffmpeg -af silencedetect` (no numpy); upgrade to autocorrelation if needed
3. **Batch parallelism**: Sequential first; add `--jobs N` later if profiling shows need
4. **Prompt versioning**: Store `prompt_hash` in output for reproducibility — implement from M9 start