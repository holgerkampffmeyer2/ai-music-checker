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
    for mp3 in TESTDATA_ROOT.rglob("*.mp3"):
        try:
            probe, sigs, agg = process_file(mp3, cfg, online=False, heavy=False)
            results.append({
                "file": str(mp3),
                "ai_probability": round(agg.ai_probability, 4),
                "verdict": agg.verdict,
                "confidence": round(agg.confidence, 4)
            })
        except Exception as e:
            results.append({"file": str(mp3), "error": str(e)})
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
