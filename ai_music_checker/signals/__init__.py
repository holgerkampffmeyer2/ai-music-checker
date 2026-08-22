#!/usr/bin/env python3
"""Signal protocol, registry and runner."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, List, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ai_music_checker.probe import FileProbe


@dataclass
class SignalResult:
    id: str          # e.g. "T1"
    name: str        # e.g. "hf_energy_profile"
    value: float     # raw measured value
    subscore: float  # normalized 0..1 (1 = strong AI indication)
    weight: int      # from config
    reliability: float  # from config
    available: bool = True  # False if dependency missing (e.g. no network)
    note: str = ""   # human-readable detail


@runtime_checkable
class Signal(Protocol):
    id: str
    name: str
    group: str       # "technical" | "metadata" | "context"
    weight: int
    reliability: float

    def compute(self, probe: FileProbe, config: Any) -> SignalResult: ...

    def available(self, config: Any) -> bool: ...


SIGNAL_REGISTRY: List[Any] = []


def register(signal: Any) -> Any:
    """Append a signal instance to SIGNAL_REGISTRY."""
    SIGNAL_REGISTRY.append(signal)
    return signal


def run_all_signals(
    probe: FileProbe,
    config: Any,
    registry: List[Any] | None = None,
) -> List[SignalResult]:
    """Run all registry signals where available(config), preserving order."""
    results: List[SignalResult] = []
    for signal in registry if registry is not None else SIGNAL_REGISTRY:
        if not signal.available(config):
            continue
        results.append(signal.compute(probe, config))
    return results
