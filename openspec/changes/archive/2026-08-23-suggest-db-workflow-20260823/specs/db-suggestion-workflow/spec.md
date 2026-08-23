## Purpose

Provides a testable workflow to analyse a track, check community DB membership and online AI indications, and propose a new community DB entry when appropriate.

## ADDED Requirements

### Requirement: Suggestion workflow with DB presence check
The system SHALL check if an artist is already present in the community AI artist DB before creating a suggestion.

#### Scenario: Artist already in DB with high confidence
- **WHEN** `--suggest-db` is run for a file whose artist matches a DB entry with `ai_confidence` high
- **THEN** system returns `db_status: already_in_db` and does not emit a new suggestion

#### Scenario: Artist not in DB
- **WHEN** `--suggest-db` is run for a file whose artist does not match any DB entry
- **THEN** system proceeds to online AI indication evaluation and may emit a suggestion

### Requirement: Online AI indication evaluation
The system SHALL evaluate online signals C1, C2, C5 and press-text buzzwords to determine if online resources indicate AI origin.

#### Scenario: Online signals indicate AI
- **WHEN** `--online` is enabled and C5 community DB lookup is negative but C1 footprint is zero and C2 label pattern score >=0.7
- **THEN** suggestion includes `online_ai_indication: true` and `reason_code` includes `online_indication`

#### Scenario: Online signals inconclusive
- **WHEN** `--online` is enabled but no online signal exceeds configured thresholds
- **THEN** suggestion may still be created based solely on deterministic signals if AI probability >= threshold

### Requirement: Suggestion generation with enriched metadata
The system SHALL generate a DB suggestion containing artist name, confidence, evidence list, and structured reason metadata.

#### Scenario: Suggestion meets threshold
- **WHEN** AI probability >= `--min-ai-probability` and artist not already in DB
- **THEN** system returns a `DBSuggestion` with `name`, `ai_confidence`, `evidence`, `reason`, `indicators`, `db_status`, `online_ai_indication`

#### Scenario: Suggestion below threshold
- **WHEN** AI probability < `--min-ai-probability`
- **THEN** system returns no suggestion
