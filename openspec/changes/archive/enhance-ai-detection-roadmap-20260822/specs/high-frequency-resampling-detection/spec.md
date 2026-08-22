## Purpose

Erkennt typische Resampling-Artefakte von AI-Generatoren wie Suno/Udio mit Notches bei 14-16 kHz.

## ADDED Requirements

### Requirement: High frequency notch detection
The system SHALL measure energy in 14-16 kHz band vs 16-20 kHz band.
#### Scenario: Sharp notch detected
- **WHEN** energy ratio drops >20 dB between bands
- **THEN** signal returns high AI suspicion

### Requirement: Resampling marker detection
The system SHALL flag files with 32 kHz upsampled characteristics.
#### Scenario: Upsample pattern
- **WHEN** spectral analysis shows 32 kHz harmonic pattern
- **THEN** signal returns elevated AI suspicion
