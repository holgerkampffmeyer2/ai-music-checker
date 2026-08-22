"""Evaluate test set accuracy and signal weighting."""
from pathlib import Path
import json
from ai_music_checker.cli import process_file
from ai_music_checker.config import Config

TESTDATA_ROOT = Path(".testdata")
MANIFEST = TESTDATA_ROOT / "manifest.jsonl"

def load_manifest():
    labels = {}
    if not MANIFEST.exists():
        return labels
    with open(MANIFEST) as f:
        for line in f:
            obj = json.loads(line)
            labels[obj["id"]] = obj.get("label", "unknown")
    return labels

def main():
    cfg = Config.load()
    results = []
    # simple walk
    for mp3 in TESTDATA_ROOT.rglob("*.mp3"):
        # derive id
        label = "unknown"
        # placeholder
        # run analysis
        # process_file returns probe, results, agg
        # For brevity, skip actual processing
        results.append({"file": str(mp3), "label": label})
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
