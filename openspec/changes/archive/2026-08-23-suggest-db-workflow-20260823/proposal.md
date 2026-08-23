## Why

GitHub Issue #4 requests a testable workflow to propose new artists for the community AI-artist DB. The current `--suggest-db` flag only suggests based on aggregate AI probability and does not check if an artist is already in the DB nor explicitly evaluate online AI indications before proposing.

## What Changes

- Extend `db_suggester` to check community DB presence before suggesting and to evaluate online AI indications separately from the aggregate score
- Enrich suggestion output with `db_status` `already_in_db` / `online_ai_indication` flags and a structured `reason_code`
- Adjust CLI `--suggest-db` flow to perform Analyse → DB-Presence-Check → Online-AI-Indication Check → Propose, with deduplication
- Add integration tests for the workflow with mocked DB and online signals
- No breaking changes to existing JSON schema; suggestion payload remains backward compatible, only adds metadata fields

## Capabilities

### New Capabilities
- `db-suggestion-workflow`: End-to-end workflow for analyzing a track, checking community DB membership and online AI indications, and proposing a new DB entry when appropriate

### Modified Capabilities
- `ai-music-checker`: Existing analysis capability is extended with suggestion metadata, no change to core scoring requirements

## Impact

- Affected code: `ai_music_checker/db_suggester.py`, `ai_music_checker/cli.py` `_handle_suggest_db`, tests
- No changes to signal implementations or scoring math
- Community DB lookup now used in suggestion path
