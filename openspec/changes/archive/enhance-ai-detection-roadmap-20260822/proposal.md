## Why

Der AI-Music-Checker erkennt heute bereits High-Frequency Cutoff und Basis-Metadaten, hat jedoch keine robusten Online-Artist-Verification, Spektral-Flachheit und Resampling-Artefakt-Signale. Aktuelle Generatoren wie Suno/Udio v2 erreichen 84%+ Detektionslücken. Erweiterung der Heuristiken und Kontextsignale ist nötig, um Spezifität und Recall zu erhöhen.

## What Changes

- Erweiterung der Context-Signale um MusicBrainz Artist-Verification und Release-Frequenz Heuristik
- Neue Technical-Signale für Spektrale Flachheit/Contrast und Resampling-Notch Erkennung
- Erweiterung der Metadaten-Validierung um Encoder-Strings, Generator IDs und ID3-Anomalien
- Optionale Integration externer Audio-Fingerprint/APIs als opt-in Context-Signale
- Dokumentation und Tests für neue Signale, keine Breaking Changes an bestehender CLI

## Capabilities

### New Capabilities
- `musicbrainz-artist-verification`: Prüft Artist-Existenz, Release-Historie, erstes Release-Datum und Genre-Konsistenz via MusicBrainz
- `spectral-flatness-analysis`: Misst spektrale Gleichförmigkeit und Contrast als Indikator für synthetische Spektren
- `high-frequency-resampling-detection`: Erkennt typische Resampling-Notches bei 14-16 kHz aus Suno/Udio Pipelines
- `metadata-encoder-validation`: Validiert ID3 Encoder-Strings, Generator-Marker und sterile Metadaten-Muster
- `release-frequency-heuristic`: Heuristik für Release-Cadence über Online-Datenbanken, Flag für >x Releases/Woche

### Modified Capabilities
- `technical-signals`: Erweiterung um T13+ ohne Änderung bestehender T1-T7 Verträge
- `context-signals`: Erweiterung um neue Online-Quellen, bestehende C1-C5 bleiben kompatibel

## Impact

- Betroffene Code: `ai_music_checker/signals/technical.py`, `signals/context.py`, `signals/metadata.py`, `config.json`
- Neue optionale Abhängigkeit `musicbrainzngs` für MusicBrainz-Integration
- CLI-Flags bleiben stabil, neue Signale sind default deaktiviert und per Config/Flag aktivierbar
- Keine Breaking Changes für bestehende JSON-Schema v1
