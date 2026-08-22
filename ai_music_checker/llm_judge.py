"""Optional LLM second-opinion judge."""
from __future__ import annotations
from typing import Any

def judge(agg: Any, signals: list[Any]) -> dict[str, Any] | None:
    """Return LLM judgement dict or None if disabled."""
    return None
