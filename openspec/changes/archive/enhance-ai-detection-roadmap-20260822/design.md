## Context

AI-Music-Checker nutzt ffmpeg-basierte Heuristiken mit Signal-Gruppen Technical/Metadata/Context. Signale sind in `ai_music_checker/signals/` implementiert, Konfiguration in `config.json`. Keine externen Python-Abhängigkeiten aktuell.

## Goals / Non-Goals

**Goals:**
- Neue Signale für MusicBrainz, Spektral-Flachheit, Resampling-Notch, Metadaten-Encoder und Release-Frequenz hinzufügen
- Bestehende CLI und JSON-Schema v1 beibehalten
- Optionale Features hinter Config-Flags und `--online`

**Non-Goals:**
- ML-Modelle oder PyTorch Integration in dieser Roadmap
- Breaking Changes an bestehenden Signalen
- Pflicht-Abhängigkeiten zu externen APIs

## Decisions

**MusicBrainz Integration**
- Wahl: `musicbrainzngs` als optionaler extra dependency. Alternative: Raw HTTP + urllib, aber Library bietet Paginierung und User-Agent Handling.
- Signale bleiben stateless, Caching via bestehendem `lib/http` mit TTL.

**Spektral-Analyse**
- Kurzfristig ffmpeg-basiert via `astats`, `spec` Filter und `ebur128`. Alternative librosa erfordert NumPy/SciPy, daher als Phase 2 hinter Flag `--spectral`.
- Resampling-Notch über Bandpass + volumedetect pro Band, konsistent zu T1.

**Metadaten-Encoder**
- Erweiterung von `signals/metadata.py` M1 Patterns um `encoded_by` und Encoder-Strings. Keine neue Abhängigkeit.

**Release-Frequenz**
- Implementierung als Context-Signal C7, nutzt MusicBrainz Release-Count. Spotify API optional für Follower-Zahl, hinter Env-Flag.

## Risks / Trade-offs

- [MusicBrainz Rate Limits] → Mitigation: Request Timeout, Retry mit Backoff, optionaler Cache
- [Falsche Positive bei spektraler Flachheit] → Mitigation: Kombination mit anderen Signalen, niedrige Gewichtung initial
- [Optionale Abhängigkeit] → Mitigation: Lazy import, graceful degrade wenn `musicbrainzngs` fehlt

## Migration Plan

- Neue Signale sind default deaktiviert, Aktivierung via `config.json` oder CLI-Flag
- Kein Daten-Migration nötig
- Rollback durch Config-Änderung möglich
