"""ASCII UI renderer for ai-music-checker."""
from __future__ import annotations

from typing import Any

from ai_music_checker.scoring import AggregateResult
from ai_music_checker.signals import SignalResult

# Box drawing characters
GAUGE_FULL = "█"
GAUGE_EMPTY = "░"
GAUGE_PARTIAL = "▒"
GAUGE_STRONG = "▓"

# Verdict colors (using ANSI if TTY)
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    GRAY = "\033[90m"


def _colorize(text: str, color: str, use_color: bool) -> str:
    if not use_color:
        return text
    return f"{color}{text}{Colors.RESET}"


def _verdict_color(verdict: str, use_color: bool) -> str:
    if verdict == "UNAUFFÄLLIG":
        return _colorize(verdict, Colors.GREEN, use_color)
    elif verdict == "EHER MENSCHLICH":
        return _colorize(verdict, Colors.CYAN, use_color)
    elif verdict == "UNKLAR":
        return _colorize(verdict, Colors.YELLOW, use_color)
    elif verdict == "LIKELY AI-ASSISTED":
        return _colorize(verdict, Colors.MAGENTA, use_color)
    elif verdict == "VERY LIKELY AI":
        return _colorize(verdict, Colors.RED, use_color)
    return verdict


def _build_gauge(value: float, width: int = 30, use_color: bool = True) -> str:
    """Build a box-drawing gauge for probability value."""
    filled = int(value * width)
    
    # Build segments with zone coloring
    zones = []
    for i in range(width):
        if i < filled:
            if i < int(0.2 * width):
                char = GAUGE_EMPTY
                color = Colors.GREEN
            elif i < int(0.4 * width):
                char = GAUGE_PARTIAL
                color = Colors.CYAN
            elif i < int(0.6 * width):
                char = GAUGE_PARTIAL
                color = Colors.YELLOW
            elif i < int(0.8 * width):
                char = GAUGE_STRONG
                color = Colors.MAGENTA
            else:
                char = GAUGE_FULL
                color = Colors.RED
            zones.append(_colorize(char, color, use_color))
        else:
            zones.append(_colorize(GAUGE_EMPTY, Colors.GRAY, use_color))
    
    return "".join(zones)


def _build_compact_gauge(value: float, width: int = 15, use_color: bool = True) -> str:
    """Build a compact single-line gauge."""
    filled = int(value * width)
    _empty = width - filled
    
    zones = []
    for i in range(width):
        if i < filled:
            if i < int(0.2 * width):
                char = GAUGE_EMPTY
                color = Colors.GREEN
            elif i < int(0.4 * width):
                char = GAUGE_PARTIAL
                color = Colors.CYAN
            elif i < int(0.6 * width):
                char = GAUGE_PARTIAL
                color = Colors.YELLOW
            elif i < int(0.8 * width):
                char = GAUGE_STRONG
                color = Colors.MAGENTA
            else:
                char = GAUGE_FULL
                color = Colors.RED
            zones.append(_colorize(char, color, use_color))
        else:
            zones.append(_colorize(GAUGE_EMPTY, Colors.GRAY, use_color))
    
    return "".join(zones)


def _format_group_bar(name: str, score: float, coverage: float, width: int = 20, use_color: bool = True) -> str:
    """Format a group score as a mini bar."""
    bar = _build_gauge(score, width, use_color)
    pct = f"{score*100:.0f}%"
    cov = f"({coverage*100:.0f}%)"
    return f"  {name:12} {bar} {pct} {cov}"


def render_full(
    agg: AggregateResult,
    signals: list[SignalResult],
    probe: Any,
    use_color: bool = True,
    top_n: int = 3,
) -> str:
    """Render full-mode output with gauge, groups, and top indicators."""
    lines = []
    
    # Header
    filename = probe.path.name if hasattr(probe, 'path') else "unknown"
    lines.append(_colorize(f"╭─ {filename}", Colors.BOLD, use_color))
    lines.append(_colorize("│", Colors.GRAY, use_color))
    
    # Main gauge
    gauge = _build_gauge(agg.ai_probability, 40, use_color)
    verdict = _verdict_color(agg.verdict, use_color)
    pct = f"{agg.ai_probability*100:.1f}%"
    lines.append(_colorize("│", Colors.GRAY, use_color) + f"  {gauge} {pct}  {verdict}")
    
    # Confidence bar
    conf_bar = _build_gauge(agg.confidence, 20, use_color)
    conf_pct = f"{agg.confidence*100:.0f}%"
    lines.append(_colorize("│", Colors.GRAY, use_color) + f"  Confidence: {conf_bar} {conf_pct}")
    lines.append(_colorize("│", Colors.GRAY, use_color))
    
    # Group scores
    lines.append(_colorize("│ Group scores:", Colors.BOLD, use_color))
    group_order = ["technical", "metadata", "context"]
    for g in group_order:
        if g in agg.groups:
            score, cov = agg.groups[g]
            if cov > 0:
                lines.append(_format_group_bar(g, score, cov, 18, use_color))
    lines.append(_colorize("│", Colors.GRAY, use_color))
    
    # Top indicators
    indicators = [
        {"id": s.id, "delta": s.subscore * s.weight * s.reliability * (s.subscore - 0.5), "note": s.note}
        for s in signals
        if s.available and s.subscore > 0.5
    ]
    indicators.sort(key=lambda x: x["delta"], reverse=True)
    
    if indicators:
        lines.append(_colorize("│ Top indicators:", Colors.BOLD, use_color))
        for ind in indicators[:top_n]:
            arrow = "▲" if ind["delta"] > 0 else "▼"
            lines.append(_colorize(f"│   {arrow} {ind['id']}: {ind['note']}", Colors.YELLOW, use_color))
    else:
        lines.append(_colorize("│ No strong indicators", Colors.GRAY, use_color))
    
    # Consistency / Coverage
    lines.append(_colorize("│", Colors.GRAY, use_color))
    lines.append(_colorize(f"│ Consistency: {agg.consistency*100:.0f}%  Coverage: {agg.coverage*100:.0f}%", Colors.GRAY, use_color))
    lines.append(_colorize("╰" + "─" * 60, Colors.GRAY, use_color))
    
    return "\n".join(lines)


def render_brief(
    agg: AggregateResult,
    probe: Any,
    use_color: bool = True,
) -> str:
    """Render brief single-line output."""
    filename = probe.path.name if hasattr(probe, 'path') else "unknown"
    gauge = _build_compact_gauge(agg.ai_probability, 12, use_color)
    verdict = _verdict_color(agg.verdict, use_color)
    pct = f"{agg.ai_probability*100:.0f}%"
    conf = f"{agg.confidence*100:.0f}%"
    
    return f"{gauge} {pct}  {conf}  {verdict}  {filename}"


def render_json(data: dict[str, Any], indent: int = 2) -> str:
    """Render JSON output."""
    import json
    return json.dumps(data, indent=indent, ensure_ascii=False)