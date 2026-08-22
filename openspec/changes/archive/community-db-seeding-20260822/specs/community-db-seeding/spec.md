## Purpose

Stellt sicher dass Community DB mit bekannten AI Artists vorbefüllt ist.

## ADDED Requirements

### Requirement: Seed data
The system SHALL provide seed data for known AI artists.
#### Scenario: Seed loaded
- **WHEN** DB is initialized
- **THEN** known artists are present

### Requirement: Evaluation order
The system SHALL evaluate artist → DB check → signals → score adjustment.
#### Scenario: Order enforced
- **WHEN** file is analyzed
- **THEN** steps follow defined order
