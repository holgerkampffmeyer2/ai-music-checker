## Purpose

Definiert klare Reihenfolge der Signal-Auswertung.

## ADDED Requirements

### Requirement: Fixed order
The system SHALL follow artist → DB → signals → score.
#### Scenario: Consistent
- **WHEN** analysis runs
- **THEN** order is deterministic
