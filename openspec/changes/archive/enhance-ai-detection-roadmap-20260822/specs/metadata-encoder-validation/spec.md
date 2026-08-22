## Purpose

Validiert ID3/FFprobe Metadaten auf Generator-Marker und sterile Encoder-Strings.

## ADDED Requirements

### Requirement: Encoder string validation
The system SHALL detect encoder strings indicating AI generators.
#### Scenario: Suno/Udio marker found
- **WHEN** encoded_by contains suno|udio|aiva
- **THEN** signal returns high AI suspicion

### Requirement: Sterile metadata detection
The system SHALL flag files with missing artist/title or generic encoder LAVF.
#### Scenario: Sterile tags
- **WHEN** tags are minimal and encoder is LAVF
- **THEN** signal returns elevated AI suspicion
