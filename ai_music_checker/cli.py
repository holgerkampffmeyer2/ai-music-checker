#!/usr/bin/env python3
"""CLI entry point for ai-music-checker."""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from ai_music_checker.config import Config
from ai_music_checker.lib.shell import run_cmd
from ai_music_checker.probe import FileProbe, ProbeError, probe_file
from ai_music_checker.report import build, to_json
from ai_music_checker.scoring import AggregateResult, aggregate, group_score

# Import signals to register them
from ai_music_checker.signals import (  # noqa: F401
    SIGNAL_REGISTRY,
    metadata,
    run_all_signals,
    technical,
)
from ai_music_checker.ui import render_brief, render_full

# Import context signals for online mode
try:
    from ai_music_checker.signals import context
    CONTEXT_AVAILABLE = True
except ImportError:
    CONTEXT_AVAILABLE = False

# Import SoundCloud signals for online mode
try:
    from ai_music_checker.signals import soundcloud
    SOUNDCLOUD_AVAILABLE = True
except ImportError:
    SOUNDCLOUD_AVAILABLE = False

# Audio file extensions
AUDIO_EXTENSIONS = {'.mp3', '.wav', '.flac', '.aiff', '.aif', '.m4a', '.ogg', '.opus'}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ai-music-checker",
        description="Forensic heuristic tool to estimate AI-generation likelihood of music files",
    )
    parser.add_argument(
        "files",
        nargs="*",
        type=Path,
        help="Audio files or directories to analyze (MP3, WAV, FLAC, AIFF, M4A, OGG, etc.)",
    )
    parser.add_argument(
        "--recursive",
        "-r",
        action="store_true",
        help="Recursively scan directories for audio files",
    )
    parser.add_argument(
        "--online",
        action="store_true",
        help="Enable online context signals (MusicBrainz, Discogs, SoundCloud, Community DB)",
    )
    parser.add_argument(
        "--heavy",
        action="store_true",
        help="Enable compute-intensive signals (spectral mirror, phase, transient, stem separation)",
    )
    parser.add_argument(
        "--brief",
        action="store_true",
        help="Brief one-line output per file",
    )
    parser.add_argument(
        "--json",
        type=Path,
        metavar="FILE",
        help="Write JSON output to FILE (or '-' for stdout)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        metavar="FILE",
        help="Path to config.json",
    )
    parser.add_argument(
        "--show-config",
        action="store_true",
        help="Show effective config and exit",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version and exit",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=5,
        help="Max parallel workers for batch processing (default: 5)",
    )
    parser.add_argument(
        "--check-evidence",
        action="store_true",
        help="Check evidence URLs in community DB and report status",
    )
    parser.add_argument(
        "--suggest-db",
        action="store_true",
        help="Suggest new community DB entries based on analysis",
    )
    parser.add_argument(
        "--min-ai-probability",
        type=float,
        default=0.6,
        help="Minimum AI probability to suggest DB entry (default: 0.6)",
    )
    parser.add_argument(
        "--save-suggestions",
        type=Path,
        metavar="FILE",
        help="Save DB suggestions to JSON file",
    )
    return parser.parse_args()


def collect_audio_files(paths: list[Path], recursive: bool = False) -> list[Path]:
    """Collect audio files from given paths (files or directories).
    
    Args:
        paths: List of file or directory paths
        recursive: If True, scan directories recursively
    
    Returns:
        List of audio file paths
    """
    audio_files: list[Path] = []
    
    for path in paths:
        if path.is_file():
            if path.suffix.lower() in AUDIO_EXTENSIONS:
                audio_files.append(path)
        elif path.is_dir():
            if recursive:
                for ext in AUDIO_EXTENSIONS:
                    audio_files.extend(path.rglob(f"*{ext}"))
                    audio_files.extend(path.rglob(f"*{ext.upper()}"))
            else:
                for ext in AUDIO_EXTENSIONS:
                    audio_files.extend(path.glob(f"*{ext}"))
                    audio_files.extend(path.glob(f"*{ext.upper()}"))
    
    # Remove duplicates and sort
    seen = set()
    unique_files = []
    for f in audio_files:
        resolved = f.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique_files.append(f)
    
    return sorted(unique_files)


def load_signals(online: bool, config: Config, heavy: bool = False) -> list[Any]:
    """Load all signals from registry, filtering by availability.
    
    Args:
        online: Enable online context signals
        config: Configuration object
        heavy: Enable compute-intensive signals (T8-T10, T12)
    """
    all_signals = list(SIGNAL_REGISTRY)
    
    # Add context signals if online
    if online and CONTEXT_AVAILABLE:
        for sig in context.CONTEXT_SIGNALS:
            all_signals.append(sig)
    
    # Add SoundCloud signals if online
    if online and SOUNDCLOUD_AVAILABLE:
        for sig in soundcloud.SOUNDCLOUD_SIGNALS:
            all_signals.append(sig)
    
    # Add heavy signals if enabled
    if heavy:
        try:
            from ai_music_checker.signals import heavy as heavy_signals
            for sig in heavy_signals.HEAVY_SIGNALS:
                all_signals.append(sig)
        except ImportError:
            pass  # heavy.py not implemented yet
    
    return all_signals


def process_file(
    filepath: Path,
    config: Config,
    online: bool,
    heavy: bool = False,
) -> tuple[FileProbe, list[Any], AggregateResult]:
    """Process a single audio file.
    
    Args:
        filepath: Path to audio file
        config: Configuration object
        online: Enable online context signals
        heavy: Enable compute-intensive signals
    """
    # Probe the file
    probe = probe_file(filepath)
    
    # Load signals
    signals = load_signals(online, config, heavy)
    
    # Run signals
    results = run_all_signals(probe, config, signals)
    
    # Compute group scores
    group_scores = {}
    for group in ["technical", "metadata", "context"]:
        group_scores[group] = group_score(results, group)
    
    # Aggregate
    enabled_groups = {"technical", "metadata"}
    if online:
        enabled_groups.add("context")
    agg = aggregate(group_scores, config.weights, enabled_groups)
    
    return probe, results, agg


def _process_file_wrapper(args: tuple) -> tuple[Path, FileProbe, list[Any], AggregateResult, str | None]:
    """Wrapper for parallel processing."""
    filepath, config, online, heavy = args
    try:
        probe, results, agg = process_file(filepath, config, online, heavy)
        return (filepath, probe, results, agg, None)
    except Exception as e:
        return (filepath, None, None, None, str(e))


def main() -> int:
    args = parse_args()
    
    # Handle version flag
    if args.version:
        from ai_music_checker import __version__
        print(f"ai-music-checker {__version__}")
        return 0
    
    # Handle show-config flag
    if args.show_config:
        cli_overrides = {}
        if args.online:
            cli_overrides["community_db.enabled"] = True
        if args.config:
            cli_overrides["config_path"] = str(args.config)
        config = Config.load(cli_overrides=cli_overrides, config_path=args.config)
        print(json.dumps(config.__dict__, indent=2, default=str))
        return 0
    
    # Handle check-evidence flag
    if args.check_evidence:
        return _handle_check_evidence(args)
    
    # Handle suggest-db flag
    if args.suggest_db:
        return _handle_suggest_db(args)
    
    # Check required files
    if not args.files:
        print("ERROR: No files provided. Use --help for usage.", file=sys.stderr)
        return 1
    
    # Check ffprobe availability
    ok, _, _ = run_cmd("ffprobe -version")
    if not ok:
        print("ERROR: ffprobe not found. Please install ffmpeg.", file=sys.stderr)
        return 2
    
    # Collect audio files from input paths (files and directories)
    audio_files = collect_audio_files(args.files, args.recursive)
    
    if not audio_files:
        print("ERROR: No audio files found in provided paths.", file=sys.stderr)
        return 1
    
    # Load config
    cli_overrides = {}
    if args.online:
        cli_overrides["community_db.enabled"] = True
    if args.config:
        cli_overrides["config_path"] = str(args.config)
    
    config = Config.load(cli_overrides=cli_overrides, config_path=args.config)
    
    use_color = sys.stdout.isatty() and not args.no_color
    
    # Single file mode
    if len(audio_files) == 1:
        filepath = audio_files[0]
        try:
            probe, results, agg = process_file(filepath, config, args.online, args.heavy)
        except ProbeError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"ERROR processing {filepath}: {e}", file=sys.stderr)
            return 1
        
        report_data = build(probe, results, agg)
        
        if args.json:
            json_output = to_json(report_data)
            if args.json == Path("-"):
                print(json_output)
            else:
                args.json.write_text(json_output, encoding="utf-8")
        elif args.brief:
            print(render_brief(agg, probe, use_color))
        else:
            print(render_full(agg, results, probe, use_color))
        
        return 0
    
    # Batch mode
    success_count = 0
    error_count = 0
    
    if len(audio_files) >= 4:
        # Parallel processing
        print(f"Processing {len(audio_files)} files in parallel (max {args.max_workers} workers)...")
        with ProcessPoolExecutor(max_workers=min(args.max_workers, len(audio_files))) as executor:
            futures = {
                executor.submit(_process_file_wrapper, (fp, config, args.online, args.heavy)): fp
                for fp in audio_files
            }
            for future in as_completed(futures):
                filepath, probe, results, agg, error = future.result()
                if error:
                    print(f"ERROR {filepath.name}: {error}", file=sys.stderr)
                    error_count += 1
                    continue
                
                report_data = build(probe, results, agg)
                
                if args.json:
                    json_output = to_json(report_data)
                    if args.json == Path("-"):
                        print(json_output)
                    else:
                        # Write to separate file per input
                        out_path = args.json.parent / f"{filepath.stem}_analysis.json"
                        out_path.write_text(json_output, encoding="utf-8")
                elif args.brief:
                    print(render_brief(agg, probe, use_color))
                else:
                    print(render_full(agg, results, probe, use_color))
                
                success_count += 1
    else:
        # Sequential processing
        print(f"Processing {len(audio_files)} files...")
        for filepath in audio_files:
            try:
                probe, results, agg = process_file(filepath, config, args.online, args.heavy)
            except Exception as e:
                print(f"ERROR {filepath.name}: {e}", file=sys.stderr)
                error_count += 1
                continue
            
            report_data = build(probe, results, agg)
            
            if args.json:
                json_output = to_json(report_data)
                if args.json == Path("-"):
                    print(json_output)
                else:
                    out_path = args.json.parent / f"{filepath.stem}_analysis.json"
                    out_path.write_text(json_output, encoding="utf-8")
            elif args.brief:
                print(render_brief(agg, probe, use_color))
            else:
                print(render_full(agg, results, probe, use_color))
            
            success_count += 1
    
    print(f"\nBatch complete: {success_count}/{len(audio_files)} succeeded, {error_count} failed")
    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())


def _handle_check_evidence(args: argparse.Namespace) -> int:
    """Handle --check-evidence flag."""
    from ai_music_checker.community_db import load_or_fetch
    from ai_music_checker.evidence_checker import check_database_evidence, generate_evidence_report
    
    # Load config
    cli_overrides = {}
    if args.config:
        cli_overrides["config_path"] = str(args.config)
    config = Config.load(cli_overrides=cli_overrides, config_path=args.config)
    
    # Load database
    db = load_or_fetch(config.community_db)
    if db is None:
        print("ERROR: Could not load community database", file=sys.stderr)
        return 1
    
    # Convert to dict for checker
    db_dict = {
        "schema_version": db.schema_version,
        "updated": db.updated,
        "license": db.license,
        "entries": [
            {
                "id": e.id,
                "name": e.name,
                "aliases": e.aliases,
                "type": e.type,
                "labels": e.labels,
                "ai_confidence": e.ai_confidence,
                "evidence": e.evidence,
                "added": e.added,
                "verified": e.verified,
            }
            for e in db.entries
        ]
    }
    
    # Check evidence
    print("Checking evidence URLs...")
    results = check_database_evidence(db_dict)
    
    # Generate report
    report = generate_evidence_report(results)
    print(report)
    
    return 0


def _handle_suggest_db(args: argparse.Namespace) -> int:
    """Handle --suggest-db flag."""
    if not args.files:
        print("ERROR: No files provided for suggestion. Use --help for usage.", file=sys.stderr)
        return 1
    
    from ai_music_checker.db_suggester import suggest_from_signals, save_suggestions
    
    # Load config
    cli_overrides = {}
    if args.online:
        cli_overrides["community_db.enabled"] = True
    if args.config:
        cli_overrides["config_path"] = str(args.config)
    config = Config.load(cli_overrides=cli_overrides, config_path=args.config)
    
    # Collect audio files
    audio_files = collect_audio_files(args.files, args.recursive)
    
    if not audio_files:
        print("ERROR: No audio files found in provided paths.", file=sys.stderr)
        return 1
    
    # Process files and collect suggestions
    suggestions = []
    print(f"Analyzing {len(audio_files)} files for DB suggestions...")
    
    for filepath in audio_files:
        try:
            probe, results, agg = process_file(filepath, config, args.online, args.heavy)
        except Exception as e:
            print(f"ERROR {filepath.name}: {e}", file=sys.stderr)
            continue
        
        # Suggest entry if AI probability is high enough
        suggestion = suggest_from_signals(
            probe, results, agg.ai_probability, agg.verdict,
            min_confidence=args.min_ai_probability
        )
        if suggestion:
            suggestions.append(suggestion)
    
    if not suggestions:
        print("No suggestions generated. All files below threshold or analysis failed.")
        return 0
    
    # Print suggestions
    print(f"\nGenerated {len(suggestions)} suggestion(s):\n")
    for s in suggestions:
        print(f"  - {s.name} ({s.ai_confidence} confidence)")
        print(f"    Reason: {s.reason}")
        print(f"    Indicators: {', '.join(s.indicators[:5])}")
        print()
    
    # Save if requested
    if args.save_suggestions:
        save_suggestions(suggestions, args.save_suggestions)
        print(f"Suggestions saved to {args.save_suggestions}")
    
    return 0