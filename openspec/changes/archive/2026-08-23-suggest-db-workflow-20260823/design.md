## Context

Current `--suggest-db` uses `db_suggester.suggest_from_signals` which only checks aggregate AI probability. Community DB lookup is performed by signal C5 during analysis but is not consulted by the suggestion workflow. No deduplication against existing DB entries.

## Goals / Non-Goals

**Goals:**
- Add explicit DB presence check before suggestion
- Evaluate online AI indication separately using C1, C2, C5, C4 signals
- Enrich suggestion metadata with `db_status` and `online_ai_indication`
- Keep CLI interface stable

**Non-Goals:**
- Automatic PR creation to community DB repo
- Changing scoring math or signal implementations
- Modifying LLM Judge

## Decisions

**Extend db_suggester with DB check**
- Add `artist_in_db(artist, community_db)` using existing `CommunityDB.lookup` with fuzzy option from config.
- Rationale: reuse existing lookup logic, no new dependency.
- Alternative: duplicate lookup code → rejected.

**Online AI indication**
- Evaluate `results` for C1 subscore >=0.8, C2 >=0.7, C5 >0.0 combined with press-text buzzword density.
- Rationale: matches forensic rationale in SIGNALS.md, lightweight.
- Alternative: call separate API → rejected.

**Suggestion metadata**
- Extend `DBSuggestion` with optional fields `db_status`, `online_ai_indication`, `reason_code`.
- Keep `to_dict` backward compatible by adding fields with defaults.

## Risks / Trade-offs

- False negatives if DB is stale → Mitigation: TTL cache already handles fallback, suggestion notes `db_lookup_stale`.
- Online check adds latency → Mitigation: only run when `--online` enabled, reuse signals already computed.
