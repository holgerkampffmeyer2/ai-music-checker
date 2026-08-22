## 1. Projekt Setup

- [ ] 1.1 Optional dependency musicbrainzngs zu pyproject.toml optional dependencies hinzufügen
- [ ] 1.2 Config-Schema erweitern um neue Signal-Weights und Flags für musicbrainz/release-frequency

## 2. MusicBrainz Artist Verification

- [ ] 2.1 Signal C7 MusicBrainzArtistVerification in signals/context.py implementieren
- [ ] 2.2 Artist existence check und Release-Historie Abfrage via musicbrainzngs
- [ ] 2.3 Tests für C7 mit gemockten MusicBrainz Antworten erstellen

## 3. Metadaten Encoder Validation

- [ ] 3.1 M1 Patterns um Encoder-Strings und encoded_by Marker erweitern
- [ ] 3.2 Sterile Metadata Detection in signals/metadata.py ergänzen
- [ ] 3.3 Tests für Encoder Validation hinzufügen

## 4. Spektrale Analyse

- [ ] 4.1 Spectral Flatness Signal T13 in signals/technical.py mit ffmpeg astats implementieren
- [ ] 4.2 High-Frequency Resampling Detection Signal T14 implementieren
- [ ] 4.3 Unit Tests für T13/T14 mit synthetischen ffmpeg Outputs

## 5. Release Frequency Heuristik

- [ ] 5.1 Context Signal C8 ReleaseFrequencyHeuristic implementieren
- [ ] 5.2 Integration mit MusicBrainz Release Count
- [ ] 5.3 Tests für hohe Cadence Erkennung

## 6. Dokumentation & CI

- [ ] 6.1 README um neue Flags und Signale ergänzen
- [ ] 6.2 ruff/mypy prüfen, Tests grün
- [ ] 6.3 Openspec Change archivieren nach Implementierung
