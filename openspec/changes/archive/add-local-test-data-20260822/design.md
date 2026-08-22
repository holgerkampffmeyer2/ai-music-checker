## Context

Tests laufen aktuell ohne echte AI-Audio Samples. CI kann nicht auf Hugging Face zugreifen.

## Goals / Non-Goals

**Goals:**
- Lokale Testdaten mit gitignore
- Optionaler Download via datasets library

**Non-Goals:**
- Daten in Repo committen
- Pflicht-Dependency für CI

## Decisions

- Speicherung unter `.testdata/`, gitignored
- Download Script `scripts/download_testdata.py` mit `datasets.load_dataset`
- Tests mit pytest `skipif` wenn Daten fehlen
- Kein Daten-Cache in Repo

## Risks / Trade-offs

- [Große Datenmenge] → Mitigation: Limit Parameter und Batch-Download
- [datasets Dependency] → Mitigation: Optional, Script läuft nur bei Bedarf
