# Testdatenbank

Lokale Testdaten für Regressionstests sind in `.testdata/` abgelegt und gitignored.

## Suno Dataset

Hugging Face Dataset `Humair332/suno-audio` wird lokal gespiegelt, um Tests gegen echte AI-Audio zu haben.

Setup:
```bash
pip install datasets
python scripts/download_testdata.py --dataset Humair332/suno-audio --limit 50
```

Optionaler Batch:
```bash
python scripts/download_testdata.py --dataset Humair332/suno-audio --data-dir batch_0 --limit 20
```

Die Daten landen unter:
`.testdata/Humair332_suno-audio/`

Tests nutzen `tests/testdata_helpers.py` und werden automatisch übersprungen, wenn die Daten nicht vorhanden sind.

Hinweis: Erstes Laden kann groß sein. Für CI kannst du `--limit` nutzen oder die Daten extern bereitstellen.
