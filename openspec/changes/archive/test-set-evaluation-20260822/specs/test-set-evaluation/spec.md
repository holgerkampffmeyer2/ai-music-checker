## Purpose

Ermöglicht reproduzierbare Bewertung der Detektionsgenauigkeit auf einem labeled Test-Set.

## ADDED Requirements

### Requirement: Batch evaluation
The system SHALL evaluate all samples in .testdata/ against ground truth labels.
#### Scenario: Evaluation run
- **WHEN** evaluation script is executed
- **THEN** metrics file is created with precision/recall/f1 per verdict band

### Requirement: Metrics report
The system SHALL compute overall precision, recall, f1 and ROC AUC.
#### Scenario: Metrics generated
- **WHEN** evaluation completes
- **THEN** report contains per-signal contributions and overall score
