## Purpose

Ermöglicht optionalen LLM Second-Opinion auf Basis der Signal-Ergebnisse.

## ADDED Requirements

### Requirement: LLM judge optional
The system SHALL allow enabling LLM judge via config.
#### Scenario: Enabled
- **WHEN** llm_judge.enabled is true
- **THEN** signal is computed and included in scoring

### Requirement: LLM input sanitization
The system SHALL pass only signal summaries to LLM.
#### Scenario: Privacy
- **WHEN** LLM is called
- **THEN** no raw audio data is sent
