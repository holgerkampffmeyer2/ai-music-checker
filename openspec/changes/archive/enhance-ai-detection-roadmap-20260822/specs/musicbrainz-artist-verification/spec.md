## Purpose

Verifiziert Künstler-Existenz und Release-Historie via MusicBrainz um AI-Generator-Artists und One-Release-Profile zu identifizieren.

## ADDED Requirements

### Requirement: Artist existence check
The system SHALL query MusicBrainz for the artist name extracted from file tags or filename.
#### Scenario: Artist found
- **WHEN** artist name exists in MusicBrainz
- **THEN** signal returns footprint found with artist id

#### Scenario: Artist not found
- **WHEN** MusicBrainz returns empty artist list
- **THEN** signal returns subscore indicating missing footprint

### Requirement: Release history check
The system SHALL retrieve release count and first release date for verified artist.
#### Scenario: Multiple releases over years
- **WHEN** artist has >=3 releases spread over >12 months
- **THEN** signal returns low AI suspicion

#### Scenario: Single recent release
- **WHEN** artist has 1 release within last 30 days
- **THEN** signal returns high AI suspicion
