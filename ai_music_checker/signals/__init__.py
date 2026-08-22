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
    # Determine if artist is in community DB to skip online context signals
    skip_online = False
    try:
        tags = probe.tags or {}
        artist = tags.get("artist") or tags.get("album_artist")
        community_db = getattr(config, "community_db", None)
        if artist and community_db and community_db.get("enabled", True):
            from ai_music_checker.community_db import load_or_fetch, lookup_artist
            db = load_or_fetch(community_db)
            if db and db.entries:
                aliases = [v for k, v in tags.items() if k in ("artist","album_artist","performer") and v != artist]
                fuzzy = community_db.get("fuzzy_enabled", False)
                threshold = community_db.get("fuzzy_threshold", 0.9)
                match = lookup_artist(db, artist, aliases, fuzzy, threshold)
                if match:
                    skip_online = True
    except Exception:  # noqa: BLE001
        skip_online = False

    for signal in registry if registry is not None else SIGNAL_REGISTRY:
        if not signal.available(config):
            continue
        # Skip online context signals if artist found in community DB
        if skip_online:
            group = getattr(signal, "group", "")
            sid = getattr(signal, "id", "")
            if group == "context" and sid != "C5":
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
