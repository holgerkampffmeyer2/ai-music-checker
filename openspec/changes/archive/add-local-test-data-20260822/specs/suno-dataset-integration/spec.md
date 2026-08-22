## Purpose

Stellt Suno Audio Samples für Regressionstests bereit und ermöglicht konditionale Tests.

## ADDED Requirements

### Requirement: Suno samples are accessible
The system SHALL expose helper to list locally cached Suno mp3 files.
#### Scenario: Samples present
- **WHEN** .testdata contains Suno files
- **THEN** helper returns non-empty list

### Requirement: Tests skip when data missing
The system SHALL skip integration tests if Suno data is not present.
#### Scenario: No data
- **WHEN** .testdata is empty
- **THEN** tests are skipped with clear reason
