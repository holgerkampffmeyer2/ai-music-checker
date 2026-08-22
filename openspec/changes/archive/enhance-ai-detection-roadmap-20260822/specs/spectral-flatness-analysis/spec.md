## Purpose

Misst spektrale Gleichförmigkeit und Contrast um überperfekte AI-Spektren von natürlichen Aufnahmen zu unterscheiden.

## ADDED Requirements

### Requirement: Spectral flatness measurement
The system SHALL compute spectral flatness over the full audio duration.
#### Scenario: Flat spectrum detected
- **WHEN** spectral flatness exceeds threshold
- **THEN** signal returns high AI suspicion

#### Scenario: Natural spectrum
- **WHEN** spectral flatness is within human music range
- **THEN** signal returns low AI suspicion

### Requirement: Spectral contrast measurement
The system SHALL compute spectral contrast across sub-bands.
#### Scenario: Low contrast
- **WHEN** contrast is below threshold
- **THEN** signal returns high AI suspicion
