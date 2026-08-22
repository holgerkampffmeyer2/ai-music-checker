"""Seed community DB with known AI artists."""
import json
from pathlib import Path

SEED = [
    {
        "id": "clmx",
        "name": "CLMX",
        "aliases": ["Cli-Max"],
        "type": "artist",
        "ai_confidence": "high",
        "evidence": [],
        "added": "2026-08-22",
        "verified": "2026-08-22"
    }
]

def main():
    out = Path(".testdata/seed_community_db.json")
    out.write_text(json.dumps({"entries": SEED}, indent=2))
    print(f"Seed written to {out}")

if __name__ == "__main__":
    main()
