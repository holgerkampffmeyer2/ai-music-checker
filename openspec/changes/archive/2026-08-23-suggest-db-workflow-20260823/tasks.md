## 1. Tests first

- [x] 1.1 Write test for artist_in_db check with exact, alias, fuzzy matches
- [x] 1.2 Write test for evaluate_online_ai_indication with C1/C2/C5 thresholds
- [x] 1.3 Write test for suggestion metadata enrichment db_status and online_ai_indication

## 2. Core implementation

- [x] 2.1 Add `artist_in_db` helper to db_suggester using CommunityDB.lookup
- [x] 2.2 Implement `evaluate_online_ai_indication` based on signal results
- [x] 2.3 Extend `DBSuggestion` dataclass with `db_status`, `online_ai_indication`, `reason_code`
- [x] 2.4 Update `suggest_from_signals` to perform DB check and online indication evaluation

## 3. CLI integration

- [x] 3.1 Update `_handle_suggest_db` to load community DB when online enabled
- [x] 3.2 Adjust output printing to show db_status and online_ai_indication

## 4. Integration & docs

- [x] 4.1 Add integration test for `--suggest-db --online` with mocked DB
- [x] 4.2 Update SIGNALS.md note about suggestion workflow
