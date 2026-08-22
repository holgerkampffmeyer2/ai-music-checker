## Why

Tests für AI-Detektion benötigen reproduzierbare echte AI-Audio-Samples. Ohne lokale Testdatenbank sind Integrationstests flaky und CI benötigt Netzwerkzugriff auf Hugging Face.

## What Changes

- Lokale, gitignored Testdatenbank `.testdata/` für Suno-Audio Samples
- Script `scripts/download_testdata.py` zum Spiegel des Hugging Face Datasets `Humair332/suno-audio`
- Test-Helpers und opt-in Integrationstests die nur laufen wenn Daten vorhanden
- Dokumentation TESTDATA.md

## Capabilities

### New Capabilities
- `local-test-data-management`: Verwaltung, Download und Manifest für lokale Testdaten
- `suno-dataset-integration`: Laden und Katalogisieren von Suno Audio Samples für Regressionstests

### Modified Capabilities
- `testing`: Tests werden konditional auf Vorhandensein von Testdaten

## Impact

- Neue Dateien: scripts/download_testdata.py, tests/testdata_helpers.py, tests/test_suno_dataset.py, TESTDATA.md
- .gitignore Anpassung
- Optional Dependency `datasets` für Download-Script
- Keine Breaking Changes
