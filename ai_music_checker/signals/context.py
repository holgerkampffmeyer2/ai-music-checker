#!/usr/bin/env python3
"""Context signals C1–C5 (online, optional)."""
from __future__ import annotations

import json
import os
import re
from typing import TYPE_CHECKING, Any

from ai_music_checker.community_db import CommunityDB, confidence_to_subscore, lookup_artist
from ai_music_checker.lib.http import fetch_url, load_env
from ai_music_checker.signals import SignalResult

if TYPE_CHECKING:
    from ai_music_checker.config import Config
    from ai_music_checker.probe import FileProbe


def _criteria_value(config: Any, signal_id: str, field: str) -> Any:
    try:
        return config.criteria[signal_id][field]
    except (AttributeError, KeyError, TypeError):
        from ai_music_checker.config import DEFAULTS
        return DEFAULTS["criteria"].get(signal_id, {}).get(field)


def _get_artist_title(probe: FileProbe) -> tuple[str | None, str | None]:
    """Extract artist and title from probe tags or filename."""
    tags = probe.tags or {}
    artist = tags.get("artist") or tags.get("album_artist")
    title = tags.get("title")
    
    if not artist or not title:
        # Fallback to filename parsing
        stem = probe.path.stem
        if " - " in stem:
            artist, title = stem.split(" - ", 1)
        else:
            title = stem
            artist = None
    
    return artist, title


class BaseContextSignal:
    group = "context"
    
    def available(self, config: Any) -> bool:
        return True  # Available if online mode enabled (checked in CLI)


class C1(BaseContextSignal):
    """Artist footprint — presence in MusicBrainz, Discogs, SoundCloud."""
    id = "C1"
    name = "artist_footprint"
    weight = 5  # Reduced from 8 for lower false positive rate
    reliability = 0.6

    def compute(self, probe: FileProbe, config: Config) -> SignalResult:
        artist, _ = _get_artist_title(probe)
        if not artist:
            return SignalResult(
                id=self.id, name=self.name, value=0.0, subscore=0.5,
                weight=self.weight, reliability=self.reliability, available=True,
                note="no artist identified", group=self.group,
            )
        
        hits: list[str] = []
        
        # MusicBrainz
        mb = self._check_musicbrainz(artist)
        if mb:
            hits.append(f"MusicBrainz: {mb}")
        
        # Discogs
        dg = self._check_discogs(artist)
        if dg:
            hits.append(f"Discogs: {dg}")
        
        # SoundCloud (if client ID configured)
        sc = self._check_soundcloud(artist, config)
        if sc:
            hits.append(f"SoundCloud: {sc}")
        
        subscore = 0.0 if hits else 0.8
        note = "; ".join(hits[:3]) if hits else f"no footprint found for '{artist}'"
        
        return SignalResult(
            id=self.id, name=self.name, value=float(len(hits)), subscore=subscore,
            weight=self.weight, reliability=self.reliability, available=True,
            note=note, group=self.group,
        )
    
    def _check_musicbrainz(self, artist: str) -> str | None:
        try:
            url = f"https://musicbrainz.org/ws/2/artist/?query=artist:{artist}&fmt=json&limit=1"
            data = fetch_url(url, timeout=5)
            if not data:
                return None
            resp = json.loads(data)
            artists = resp.get("artists", [])
            if artists:
                return artists[0].get("id", "found")
        except (json.JSONDecodeError, OSError, TimeoutError):
            pass
        return None
    
    def _check_discogs(self, artist: str) -> str | None:
        try:
            url = f"https://api.discogs.com/database/search?q={artist}&type=artist&per_page=1"
            data = fetch_url(url, timeout=5)
            if not data:
                return None
            resp = json.loads(data)
            results = resp.get("results", [])
            if results:
                return str(results[0].get("id", "found"))
        except (json.JSONDecodeError, OSError, TimeoutError):
            pass
        return None
    
    def _check_soundcloud(self, artist: str, config: Config) -> str | None:
        client_id = os.environ.get(config.soundcloud_client_id_env)
        if not client_id:
            return None
        try:
            url = f"https://api-v2.soundcloud.com/search?q={artist}&client_id={client_id}&limit=1"
            data = fetch_url(url, timeout=5)
            if not data:
                return None
            resp = json.loads(data)
            collection = resp.get("collection", [])
            if collection:
                return str(collection[0].get("id", "found"))
        except (json.JSONDecodeError, OSError, TimeoutError):
            pass
        return None


class C2(BaseContextSignal):
    """Label pattern — release cadence, one-release-artist ratio from Discogs/MB."""
    id = "C2"
    name = "label_pattern"
    weight = 6
    reliability = 0.5

    def compute(self, probe: FileProbe, config: Config) -> SignalResult:
        artist, _ = _get_artist_title(probe)
        if not artist:
            return SignalResult(
                id=self.id, name=self.name, value=0.0, subscore=0.5,
                weight=self.weight, reliability=self.reliability, available=True,
                note="no artist identified", group=self.group,
            )
        
        # Try Discogs first
        label_info = self._check_discogs_labels(artist)
        if label_info is None:
            label_info = self._check_musicbrainz_labels(artist)
        
        if label_info is None:
            return SignalResult(
                id=self.id, name=self.name, value=0.0, subscore=0.3,
                weight=self.weight, reliability=self.reliability, available=True,
                note="no label data found", group=self.group,
            )
        
        cadence, one_release_ratio, label_count = label_info
        
        # Scoring: high cadence + high one-release ratio = suspicious
        cadence_score = min(1.0, cadence / 12.0)  # 12+ releases/year = max
        ratio_score = one_release_ratio  # already 0..1
        subscore = (cadence_score + ratio_score) / 2
        
        note = f"cadence {cadence:.1f}/yr, {one_release_ratio*100:.0f}% one-release, {label_count} labels"
        
        return SignalResult(
            id=self.id, name=self.name, value=cadence, subscore=subscore,
            weight=self.weight, reliability=self.reliability, available=True,
            note=note, group=self.group,
        )
    
    def _check_discogs_labels(self, artist: str) -> tuple[float, float, int] | None:
        try:
            # Search for artist
            url = f"https://api.discogs.com/database/search?q={artist}&type=artist&per_page=1"
            data = fetch_url(url, timeout=10)
            if not data:
                return None
            resp = json.loads(data)
            results = resp.get("results", [])
            if not results:
                return None
            artist_id = results[0].get("id")
            if not artist_id:
                return None
            
            # Get releases
            url = f"https://api.discogs.com/artists/{artist_id}/releases?per_page=100"
            data = fetch_url(url, timeout=10)
            if not data:
                return None
            resp = json.loads(data)
            releases = resp.get("releases", [])
            
            labels = set()
            years = set()
            for rel in releases:
                lbl = rel.get("label", [])
                if isinstance(lbl, list):
                    for l in lbl:
                        if l:
                            labels.add(l)
                elif lbl:
                    labels.add(lbl)
                year = rel.get("year")
                if year:
                    years.add(year)
            
            if not years:
                return None
            
            span = max(years) - min(years) + 1
            cadence = len(releases) / span
            one_release = sum(1 for l in labels if sum(1 for r in releases if self._release_has_label(r, l)) == 1)
            one_release_ratio = one_release / len(labels) if labels else 0
            
            return cadence, one_release_ratio, len(labels)
        except (json.JSONDecodeError, OSError, TimeoutError, ValueError):
            pass
        return None
    
    def _release_has_label(self, release: dict, label: str) -> bool:
        lbl = release.get("label", [])
        if isinstance(lbl, list):
            return label in lbl
        return lbl == label
    
    def _check_musicbrainz_labels(self, artist: str) -> tuple[float, float, int] | None:
        try:
            url = f"https://musicbrainz.org/ws/2/artist/?query=artist:{artist}&fmt=json&limit=1"
            data = fetch_url(url, timeout=10)
            if not data:
                return None
            resp = json.loads(data)
            artists = resp.get("artists", [])
            if not artists:
                return None
            artist_id = artists[0].get("id")
            if not artist_id:
                return None
            
            # Get release groups
            url = f"https://musicbrainz.org/ws/2/release-group?artist={artist_id}&fmt=json&limit=100"
            data = fetch_url(url, timeout=10)
            if not data:
                return None
            resp = json.loads(data)
            rgs = resp.get("release-groups", [])
            
            labels = set()
            years = set()
            for rg in rgs:
                date = rg.get("first-release-date")
                if date:
                    years.add(date[:4])
            
            if not years:
                return None
            
            span = max(int(y) for y in years) - min(int(y) for y in years) + 1
            cadence = len(rgs) / span
            # MB doesn't easily give label info without more calls
            one_release_ratio = 0.3  # placeholder
            
            return cadence, one_release_ratio, len(labels)
        except (json.JSONDecodeError, OSError, TimeoutError, ValueError):
            pass
        return None


class C3(BaseContextSignal):
    """Release database presence — MB/Discogs/Beatport existence + age."""
    id = "C3"
    name = "release_db_presence"
    weight = 7
    reliability = 0.6

    def compute(self, probe: FileProbe, config: Config) -> SignalResult:
        artist, title = _get_artist_title(probe)
        if not artist or not title:
            return SignalResult(
                id=self.id, name=self.name, value=0.0, subscore=0.5,
                weight=self.weight, reliability=self.reliability, available=True,
                note="no artist/title identified", group=self.group,
            )
        
        hits: list[str] = []
        age_years = None
        
        # MusicBrainz
        mb_age = self._check_musicbrainz_release(artist, title)
        if mb_age is not None:
            hits.append(f"MusicBrainz ({mb_age}yr)")
            age_years = mb_age
        
        # Discogs
        dg_age = self._check_discogs_release(artist, title)
        if dg_age is not None:
            hits.append(f"Discogs ({dg_age}yr)")
            if age_years is None:
                age_years = dg_age
        
        # Beatport (basic search)
        bp = self._check_beatport(artist, title)
        if bp:
            hits.append("Beatport")
        
        # Scoring: no presence = suspicious, very old = less suspicious
        if not hits:
            subscore = 0.7
            note = f"no DB presence for '{artist} - {title}'"
        elif age_years is not None and age_years > 5:
            subscore = 0.1
            note = "; ".join(hits)
        else:
            subscore = 0.3
            note = "; ".join(hits)
        
        return SignalResult(
            id=self.id, name=self.name, value=float(age_years or 0), subscore=subscore,
            weight=self.weight, reliability=self.reliability, available=True,
            note=note, group=self.group,
        )
    
    def _check_musicbrainz_release(self, artist: str, title: str) -> int | None:
        try:
            url = f"https://musicbrainz.org/ws/2/recording/?query=artist:{artist}%20AND%20recording:{title}&fmt=json&limit=1"
            data = fetch_url(url, timeout=10)
            if not data:
                return None
            resp = json.loads(data)
            recordings = resp.get("recordings", [])
            if not recordings:
                return None
            rec = recordings[0]
            date = rec.get("first-release-date")
            if date:
                year = int(date[:4])
                from datetime import datetime
                return datetime.now().year - year
        except (json.JSONDecodeError, OSError, TimeoutError, ValueError):
            pass
        return None
    
    def _check_discogs_release(self, artist: str, title: str) -> int | None:
        try:
            url = f"https://api.discogs.com/database/search?q={artist}%20{title}&type=release&per_page=1"
            data = fetch_url(url, timeout=10)
            if not data:
                return None
            resp = json.loads(data)
            results = resp.get("results", [])
            if not results:
                return None
            year = results[0].get("year")
            if year:
                from datetime import datetime
                return datetime.now().year - int(year)
        except (json.JSONDecodeError, OSError, TimeoutError, ValueError):
            pass
        return None
    
    def _check_beatport(self, artist: str, title: str) -> bool:
        try:
            url = f"https://www.beatport.com/search?q={artist}%20{title}"
            data = fetch_url(url, timeout=10)
            return data is not None and len(data) > 1000
        except (OSError, TimeoutError):
            pass
        return False


class C4(BaseContextSignal):
    """Press text analysis — buzzword density, editorial tags from URLs in tags."""
    id = "C4"
    name = "press_text"
    weight = 5
    reliability = 0.4

    AI_BUZZWORDS = (
        "ai-generated", "ai generated", "artificial intelligence", "machine learning",
        "neural network", "deep learning", "generative", "suno", "udio", "stable audio",
        "musicgen", "riffusion", "aiva", "soundraw", "boomy", "mubert", "loudly",
        "ai music", "algorithmic composition", "procedural generation",
    )

    def compute(self, probe: FileProbe, config: Config) -> SignalResult:
        tags = probe.tags or {}
        urls: list[str] = []
        
        # Extract URLs from comment, description, etc.
        for key, val in tags.items():
            if isinstance(val, str):
                found = re.findall(r'https?://\S+', val)
                urls.extend(found)
        
        if not urls:
            return SignalResult(
                id=self.id, name=self.name, value=0.0, subscore=0.0,
                weight=self.weight, reliability=self.reliability, available=True,
                note="no URLs in tags", group=self.group,
            )
        
        total_buzz = 0
        total_words = 0
        checked = 0
        
        for url in urls[:3]:  # Limit to 3 URLs
            text = self._fetch_page_text(url)
            if text:
                checked += 1
                words = len(text.split())
                total_words += words
                buzz = sum(1 for bw in self.AI_BUZZWORDS if bw.lower() in text.lower())
                total_buzz += buzz
        
        if checked == 0:
            subscore = 0.0
            note = "URLs found but none fetchable"
        else:
            density = total_buzz / max(1, total_words / 1000)  # per 1000 words
            subscore = min(1.0, density / 5.0)  # 5+ per 1000 = max
            note = f"{checked} URLs checked, {total_buzz} AI buzzwords ({density:.1f}/1k words)"
        
        return SignalResult(
            id=self.id, name=self.name, value=float(total_buzz), subscore=subscore,
            weight=self.weight, reliability=self.reliability, available=True,
            note=note, group=self.group,
        )
    
    def _fetch_page_text(self, url: str) -> str | None:
        try:
            load_env()
            html = fetch_url(url, timeout=10)
            if not html:
                return None
            # Strip HTML tags
            text = re.sub(r'<[^>]+>', ' ', html)
            text = re.sub(r'\s+', ' ', text)
            return text[:5000]  # Limit
        except (OSError, TimeoutError):
            return None


class C5(BaseContextSignal):
    """Community DB lookup — known AI artists database."""
    id = "C5"
    name = "community_db"
    weight = 9
    reliability = 0.8

    def __init__(self):
        self._db: CommunityDB | None = None
        self._config_hash: str | None = None
    
    def available(self, config: Any) -> bool:
        # Only available if community DB is enabled in config
        return config.community_db.get("enabled", True)
    
    def compute(self, probe: FileProbe, config: Config) -> SignalResult:
        artist, _ = _get_artist_title(probe)
        if not artist:
            return SignalResult(
                id=self.id, name=self.name, value=0.0, subscore=0.0,
                weight=self.weight, reliability=self.reliability, available=True,
                note="no artist identified", group=self.group,
            )
        
        # Load or fetch DB
        from ai_music_checker.community_db import load_or_fetch
        db = load_or_fetch(config.community_db)
        
        if db is None or not db.entries:
            return SignalResult(
                id=self.id, name=self.name, value=0.0, subscore=0.0,
                weight=self.weight, reliability=self.reliability, available=False,
                note="community DB unavailable", group=self.group,
            )
        
        # Lookup artist
        aliases = []
        tags = probe.tags or {}
        for key in ["artist", "album_artist", "performer"]:
            if key in tags and tags[key] != artist:
                aliases.append(tags[key])
        
        fuzzy = config.community_db.get("fuzzy_enabled", False)
        threshold = config.community_db.get("fuzzy_threshold", 0.9)
        
        match = lookup_artist(db, artist, aliases, fuzzy, threshold)
        
        if match is None:
            return SignalResult(
                id=self.id, name=self.name, value=0.0, subscore=0.0,
                weight=self.weight, reliability=self.reliability, available=True,
                note=f"'{artist}' not in community DB", group=self.group,
            )
        
        entry = match.entry
        subscore = confidence_to_subscore(entry.ai_confidence)
        
        fuzzy_note = " (fuzzy)" if match.fuzzy else ""
        
        # Evidence mit Datum und Status
        evidence_parts = []
        for e in entry.evidence[:2]:
            date_str = e.get('date', '')
            status_str = e.get('status', 'unknown')
            last_checked = e.get('last_checked', '')
            evidence_parts.append(f"{e['url']} ({date_str}, {status_str}, checked: {last_checked})")
        evidence_str = "; ".join(evidence_parts)
        note = f"found: {entry.name} [{entry.ai_confidence}] — {evidence_str}{fuzzy_note}"
        
        return SignalResult(
            id=self.id, name=self.name, value=subscore, subscore=subscore,
            weight=self.weight, reliability=self.reliability, available=True,
            note=note, group=self.group,
            evidence=[{"url": e["url"], "note": e["note"], "date": e["date"],
                       "last_checked": e.get("last_checked"), "status": e.get("status")}
                      for e in entry.evidence],
        )


CONTEXT_SIGNALS = [C1(), C2(), C3(), C4(), C5()]