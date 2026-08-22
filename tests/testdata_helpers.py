"""Test data helpers for Suno dataset."""
from pathlib import Path

TESTDATA_ROOT = Path(__file__).parent.parent / ".testdata"

def suno_audio_dir(batch=None):
    base = TESTDATA_ROOT / "Humair332_suno-audio"
    if batch:
        base = base / batch
    return base

def list_suno_samples(batch=None):
    d = suno_audio_dir(batch)
    if not d.exists():
        return []
    return sorted(d.glob("*.mp3"))
