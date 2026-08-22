"""Signal protocol, registry and runner."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

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
    group: str = ""  # "technical" | "metadata" | "context"
    evidence: list[dict[str, Any]] | None = None  # evidence URLs with date and status


@runtime_checkable
class Signal(Protocol):
    id: str
    name: str
    group: str       # "technical" | "metadata" | "context"
    weight: int
    reliability: float

    def compute(self, probe: FileProbe, config: Any) -> SignalResult: ...

    def available(self, config: Any) -> bool: ...


SIGNAL_REGISTRY: list[Any] = []


def register(signal: Any) -> Any:
    """Append a signal instance to SIGNAL_REGISTRY."""
    SIGNAL_REGISTRY.append(signal)
    return signal


def run_all_signals(
    probe: FileProbe,
    config: Any,
    registry: list[Any] | None = None,
) -> list[SignalResult]:
    """Run all registry signals where available(config), preserving order."""
    results: list[SignalResult] = []
    for signal in registry if registry is not None else SIGNAL_REGISTRY:
        if not signal.available(config):
            continue
        results.append(signal.compute(probe, config))
    return results


# Auto-register built-in signals
def _register_builtin_signals() -> None:
    from ai_music_checker.signals.metadata import METADATA_SIGNALS
    from ai_music_checker.signals.technical import TECHNICAL_SIGNALS
    for sig in TECHNICAL_SIGNALS:
        register(sig)
    for sig in METADATA_SIGNALS:
        register(sig)


_register_builtin_signals()
