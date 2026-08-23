#!/usr/bin/env python3
"""Helper to export ai-music-checker JSON to Agent-readable Markdown."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_json(path: Path | None, stdin: bool) -> dict:
    if stdin or path is None:
        data = json.load(sys.stdin)
    else:
        data = json.loads(path.read_text(encoding="utf-8"))
    return data


def format_md(data: dict) -> str:
    file_info = data.get("file", {})
    result = data.get("result", {})
    groups = data.get("groups", {})
    signals = data.get("signals", [])
    llm = data.get("llm_judge", {})

    lines = []
    lines.append(f"# AI Musik Checker Review")
    lines.append(f"**File:** {file_info.get('name')} `{file_info.get('path')}`")
    lines.append(f"**Format:** {file_info.get('format')} | **Duration:** {file_info.get('duration_s')}s | **Sample Rate:** {file_info.get('sample_rate_hz')} Hz")
    lines.append("")
    lines.append("## Deterministische Einschätzung")
    lines.append(f"- AI Probability: {result.get('ai_probability')} – {result.get('verdict')}")
    lines.append(f"- Confidence: {result.get('confidence')} | Coverage: {result.get('coverage')} | Consistency: {result.get('consistency')}")
    lines.append("")
    lines.append("## Gruppen Scores")
    for g, v in groups.items():
        lines.append(f"- {g}: {v.get('score')}  coverage {v.get('coverage')}")
    lines.append("")
    lines.append("## Top Indicators")
    for ind in result.get("top_indicators", [])[:10]:
        lines.append(f"- {ind.get('id')}: {ind.get('note', '')}")
    lines.append("")
    lines.append("## Signale Übersicht")
    for s in signals:
        lines.append(f"- {s.get('id')} [{s.get('group')}]: subscore={s.get('subscore')} weight={s.get('weight')} available={s.get('available')} note={s.get('note')}")
    lines.append("")
    if llm:
        lines.append("## LLM Agent Kontext")
        lines.append(f"Mode: {llm.get('mode')} | Backend: {llm.get('backend')}")
        prompt = llm.get('prompt') or ""
        if prompt:
            lines.append("")
            lines.append("### Prompt")
            lines.append("```")
            lines.append(prompt[:2000])
            lines.append("```")
    lines.append("")
    lines.append("Bitte LLMResult erzeugen: probability, confidence, reasoning, agrees_with_deterministic, key_disagreements")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Export ai-music-checker JSON to Agent Markdown")
    parser.add_argument("--json", type=Path, help="JSON input file")
    parser.add_argument("-o", "--out", type=Path, help="Output Markdown file")
    args = parser.parse_args()

    data = load_json(args.json, args.json is None)
    md = format_md(data)

    if args.out:
        args.out.write_text(md, encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(md)


if __name__ == "__main__":
    main()
