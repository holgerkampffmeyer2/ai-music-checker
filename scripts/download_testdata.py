"""Download Suno test dataset for local testing.

Usage:
  python scripts/download_testdata.py --dataset Humair332/suno-audio --split train --limit 20
  python scripts/download_testdata.py --dataset Humair332/suno-audio --data-dir batch_0

Dataset is cached under .testdata/ and gitignored.
"""
from __future__ import annotations
import argparse
from pathlib import Path
from datasets import load_dataset

ROOT = Path(__file__).resolve().parents[1] / ".testdata"
ROOT.mkdir(parents=True, exist_ok=True)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", default="Humair332/suno-audio")
    p.add_argument("--data-dir", default=None)
    p.add_argument("--split", default="train")
    p.add_argument("--limit", type=int, default=None)
    args = p.parse_args()

    print(f"Loading {args.dataset}...")
    ds = load_dataset(args.dataset, data_dir=args.data_dir, split=args.split)
    if args.limit:
        ds = ds.select(range(min(args.limit, len(ds))))

    out_dir = ROOT / args.dataset.replace("/", "_")
    if args.data_dir:
        out_dir = out_dir / args.data_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    meta_path = out_dir / "manifest.jsonl"
    count = 0
    for ex in ds:
        # ex contains audio dict with path or bytes
        audio = ex.get("audio")
        if not audio:
            continue
        # Save audio bytes to file
        # Try to get filename from metadata
        name = ex.get("file_name") or ex.get("id") or f"sample_{count}"
        ext = ".mp3"
        # datasets audio may be a dict with 'bytes'
        try:
            import io
            from datasets.features import Audio
            # If audio is a dict with 'path'
            if isinstance(audio, dict) and "path" in audio:
                src = Path(audio["path"])
                dst = out_dir / f"{name}{ext}"
                dst.write_bytes(src.read_bytes())
            elif isinstance(audio, dict) and "bytes" in audio:
                dst = out_dir / f"{name}{ext}"
                dst.write_bytes(audio["bytes"])
            else:
                # audio may be bytes directly
                dst = out_dir / f"{name}{ext}"
                dst.write_bytes(audio)
        except Exception as e:
            print(f"Skip {name}: {e}")
            continue
        # Write manifest
        with open(meta_path, "a", encoding="utf-8") as f:
            f.write(f"{{\n  \"id\": {name},\n  \"label\": {ex.get('label', 'unknown')}\n}}\n")
        count += 1
        print(f"Saved {count}: {name}")

    print(f"Done. {count} samples saved to {out_dir}")

if __name__ == "__main__":
    main()
