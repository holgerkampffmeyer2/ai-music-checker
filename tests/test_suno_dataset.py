"""Integration tests using Suno dataset."""
import pytest
from pathlib import Path
from testdata_helpers import list_suno_samples

pytestmark = pytest.mark.skipif(
    not list_suno_samples(),
    reason="Suno test data not downloaded. Run scripts/download_testdata.py first."
)

def test_suno_samples_detected():
    samples = list_suno_samples()
    assert samples, "No Suno samples found"
    # Basic sanity: at least one file exists
    for p in samples[:5]:
        assert p.exists() and p.stat().st_size > 0
