## Purpose

Heuristik zur Erkennung unrealistischer Release-Frequenzen von AI-Artists.

## ADDED Requirements

### Requirement: Release cadence measurement
The system SHALL measure releases per time window for verified artist.
#### Scenario: High cadence
- **WHEN** artist has >4 releases per month
- **THEN** signal returns high AI suspicion

### Requirement: Platform presence check
The system SHALL verify artist presence across multiple platforms.
#### Scenario: Single platform only
- **WHEN** artist exists only on one streaming platform
- **THEN** signal returns elevated AI suspicion
