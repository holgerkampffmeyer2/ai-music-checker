## Purpose

Verwaltet lokale, gitignored Testdaten für reproduzierbare Integrationstests.

## ADDED Requirements

### Requirement: Test data directory is gitignored
The system SHALL keep test data under .testdata/ which is excluded from git.
#### Scenario: Git ignore check
- **WHEN** .gitignore is inspected
- **THEN** .testdata/ is listed

### Requirement: Download script exists
The system SHALL provide a script to download and mirror Hugging Face datasets locally.
#### Scenario: Script runs successfully
- **WHEN** download script is executed with valid dataset id
- **THEN** data files are written under .testdata/
