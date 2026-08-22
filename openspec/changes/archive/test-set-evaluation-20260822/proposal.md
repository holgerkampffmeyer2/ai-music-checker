## Why

Die Treffergenauigkeit und Gewichtung der Signale kann ohne systematische Evaluation des Test-Sets nicht objektiv verbessert werden. Es fehlt an reproduzierbarer Metrik und Gewichts-Sweep.

## What Changes

- Test-Set Evaluation als internes Tool, nicht als User-CLI
- Labeled Testdatenbank `.testdata/` wird ausgewertet
- Metriken Precision/Recall/F1/ROC pro Signal und Gesamtscore
- Gewichts-Optimierung via Sweep über config.json
- Report als JSON/Markdown

## Capabilities

### New Capabilities
- `test-set-evaluation`: Batch Evaluation von labeled Testdaten mit Metriken und Reporting
- `signal-weight-tuning`: Systematischer Gewichts-Sweep und Empfindlichkeitsanalyse

### Modified Capabilities
- `scoring`: Keine Verhaltensänderung, nur Erweiterung um Evaluations-Metriken

## Impact

- Neue Scripts `scripts/evaluate_testset.py`
- Tests nutzen `.testdata/`
- Keine Breaking Changes für CLI
