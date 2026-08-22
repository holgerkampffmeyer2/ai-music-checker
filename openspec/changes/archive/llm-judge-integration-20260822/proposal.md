## Why

LLM Second-Opinion fehlt als optionales Signal. Doku und Code erwähnen die Komponente nur teilweise.

## What Changes

- Optionaler LLM Judge als zusätzliches Signal
- Config Flag llm_judge.enabled
- Integration in Scoring als optionales Signal

## Capabilities

### New Capabilities
- `llm-judge-integration`: Optionaler LLM Second-Opinion auf aggregierte Signale

## Impact

- ai_music_checker/llm_judge.py Erweiterung
- Config, CLI Flag --llm
