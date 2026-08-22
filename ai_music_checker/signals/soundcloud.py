#!/usr/bin/env python3
"""SoundCloud-specific signal -- C6: SoundCloud fingerprint.

Uses SoundCloud API v2 with confidence scoring to analyze tracks.
Requires SOUNDCLOUD_CLIENT_ID in environment.
"""
from __future__ import annotations

import json
import os
import re
from difflib import SequenceMatcher
from typing import TYPE_CHECKING, Any

from ai_music_checker.lib.http import fetch_url, load_env
from ai_music_checker.signals import SignalResult
from ai_music_checker.signals.context import BaseContextSignal

if TYPE_CHECKING:
    from ai_music_checker.config import Config
    from ai_music_checker.probe import FileProbe


def _clean_title_for_search(title: str) -> str:
    """Clean title for search comparison."""
    if not title:
        return ""
    # Remove non-word characters
    title = re.sub(r"[^\w\s]", " ", title)
    # Remove common suffixes
    title = re.sub(r"\b(remix|edit|mix|version|vip|dub|instrumental|acapella|vocal|radio|extended|original)\b", "", title, flags=re.IGNORECASE)
    # Collapse whitespace
    title = re.sub(r"\s+", " ", title).strip().lower()
    return title


def _calculate_match_confidence(query: str, candidate: str) -> float:
    """Calculate match confidence between query and candidate."""
    if not query or not candidate:
        return 0.0
    
    q = _clean_title_for_search(query)
    c = _clean_title_for_search(candidate)
    
    if q == c:
        return 1.0
    
    # Word containment check
    q_words = set(q.split())
    c_words = set(c.split())
    if q_words.issubset(c_words) or c_words.issubset(q_words):
        return 0.95
    
    # Fuzzy match
    return SequenceMatcher(None, q, c).ratio()


class SoundCloudAnalyzer:
    """SoundCloud API v2 analyzer with confidence scoring."""
    
    def __init__(self, client_id: str):
        self.client_id = client_id
        self.base_url = "https://api-v2.soundcloud.com"
    
    def search_tracks(self, query: str, limit: int = 5) -> list[dict]:
        """Search SoundCloud for tracks."""
        from urllib.parse import quote
        url = (
            f"{self.base_url}/search/tracks"
            f"?q={quote(query)}&client_id={self.client_id}&limit={limit}"
        )
        content = fetch_url(url, timeout=10)
        if not content:
            return []
        try:
            data = json.loads(content)
            return data.get("collection", [])
        except json.JSONDecodeError:
            return []
    
    def get_track_details(self, track_id: int) -> dict | None:
        """Get detailed track information."""
        url = f"{self.base_url}/tracks/{track_id}?client_id={self.client_id}"
        content = fetch_url(url, timeout=10)
        if not content:
            return None
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return None
    
    def analyze_track(self, artist: str, title: str, config: dict) -> dict | None:
        """Analyze a track on SoundCloud with confidence scoring."""
        query = f"{artist} {title}"
        results = self.search_tracks(query)
        
        if not results:
            return None
        
        confidence_threshold = config.get("soundcloud_confidence_threshold", 0.6)
        
        for track in results:
            api_title = track.get("title", "")
            uploader = track.get("user", {}).get("username", "")
            artwork = track.get("artwork_url", "")
            permalink = track.get("permalink_url", "")
            track_id = track.get("id")
            
            if not api_title:
                continue
            
            # Calculate confidence
            confidence = _calculate_match_confidence(f"{artist} {title}", api_title)
            
            if confidence >= confidence_threshold:
                # Upgrade artwork to t500x500
                if artwork and "-large.jpg" in artwork:
                    artwork = artwork.replace("-large.jpg", "-t500x500.jpg")
                
                return {
                    "title": api_title,
                    "artist": uploader,
                    "thumbnail": artwork,
                    "url": permalink,
                    "track_id": track_id,
                    "confidence": confidence,
                }
        
        return None


class C6(BaseContextSignal):
    """SoundCloud fingerprint -- API v2 analysis with confidence scoring."""
    id = "C6"
    name = "soundcloud_fingerprint"
    weight = 7
    reliability = 0.7

    def available(self, config: Any) -> bool:
        """Available if SOUNDCLOUD_CLIENT_ID is set."""
        client_id = os.environ.get(config.soundcloud_client_id_env if hasattr(config, 'soundcloud_client_id_env') else "SOUNDCLOUD_CLIENT_ID")
        return bool(client_id)

    def compute(self, probe: FileProbe, config: Config) -> SignalResult:
        """Analyze track on SoundCloud with confidence scoring."""
        # Get artist/title from tags
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
        
        if not artist or not title:
            return SignalResult(
                id=self.id, name=self.name, value=0.0, subscore=0.5,
                weight=self.weight, reliability=self.reliability, available=True,
                note="no artist/title identified", group=self.group,
            )
        
        # Get SoundCloud client ID
        load_env()
        client_id_env = config.soundcloud_client_id_env if hasattr(config, 'soundcloud_client_id_env') else "SOUNDCLOUD_CLIENT_ID"
        client_id = os.environ.get(client_id_env)
        
        if not client_id:
            return SignalResult(
                id=self.id, name=self.name, value=0.0, subscore=0.0,
                weight=self.weight, reliability=self.reliability, available=False,
                note="no SoundCloud client ID", group=self.group,
            )
        
        # Analyze on SoundCloud
        analyzer = SoundCloudAnalyzer(client_id)
        result = analyzer.analyze_track(artist, title, {
            "soundcloud_confidence_threshold": 0.6
        })
        
        if result is None:
            return SignalResult(
                id=self.id, name=self.name, value=0.0, subscore=0.0,
                weight=self.weight, reliability=self.reliability, available=True,
                note=f"no SoundCloud match for '{artist} - {title}'", group=self.group,
            )
        
        # Score based on confidence and track characteristics
        confidence = result["confidence"]
        
        # High confidence match with low follower count = suspicious
        # (AI aliases often have minimal presence)
        track_details = analyzer.get_track_details(result["track_id"])
        
        follower_count = 0
        if track_details:
            user = track_details.get("user", {})
            follower_count = user.get("followers_count", 0)
        
        # Scoring logic
        if confidence > 0.9 and follower_count < 100:
            subscore = 0.7
            note = f"high confidence match ({confidence:.2f}) with low followers ({follower_count})"
        elif confidence > 0.8:
            subscore = 0.3
            note = f"good match ({confidence:.2f}), {follower_count} followers"
        else:
            subscore = 0.1
            note = f"partial match ({confidence:.2f}), {follower_count} followers"
        
        return SignalResult(
            id=self.id, name=self.name, value=confidence, subscore=subscore,
            weight=self.weight, reliability=self.reliability, available=True,
            note=note, group=self.group,
        )


SOUNDCLOUD_SIGNALS = [C6()]
