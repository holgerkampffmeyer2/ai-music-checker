## Purpose

Unterstützt systematisches Tuning der Signal-Gewichte zur Verbesserung der Treffergenauigkeit.

## ADDED Requirements

### Requirement: Weight sweep
The system SHALL evaluate multiple weight configurations and compare metrics.
#### Scenario: Sweep run
- **WHEN** weight sweep is executed
- **THEN** best configuration by f1 is identified

### Requirement: Sensitivity analysis
The system SHALL report signal importance per metric change.
#### Scenario: Analysis output
- **WHEN** sweep completes
- **THEN** report lists top contributing signals
