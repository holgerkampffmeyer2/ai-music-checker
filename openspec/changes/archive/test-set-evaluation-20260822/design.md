## Context

Testdaten liegen in .testdata/, Evaluation soll offline ohne CLI Änderung laufen.

## Goals / Non-Goals

**Goals:**
- Reproduzierbare Metriken für Test-Set
- Gewichts-Sweep ohne User-CLI

**Non-Goals:**
- Neue CLI Flags für Endnutzer
- Änderungen am Scoring Algorithmus selbst

## Decisions

- Evaluation als Script `scripts/evaluate_testset.py`, nicht CLI
- Metriken via sklearn-like Berechnung, kein ML-Dependency
- Gewichts-Sweep via Config Kopien

## Risks / Trade-offs

- [Testdaten Qualität] → Mitigation: Labels müssen validiert sein
