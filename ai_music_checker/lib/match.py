"""Vendored matching utilities from wav-to-aac-converter."""
from __future__ import annotations

import re
from difflib import SequenceMatcher

NON_WORD_RE = re.compile(r"[^\w\s]")
MULTI_DASH_RE = re.compile(r"-{2,}")
BRACKET_CLEANUP_RE = re.compile(r"[\[\(].*?[\]\)]")
REMIX_KEYWORDS_RE = re.compile(r"\b(remix|edit|mix|version|vip|dub|instrumental|acapella|vocal|radio|extended|original)\b", re.IGNORECASE)


def clean_title_for_search(title: str) -> str:
    """Clean title for search comparison."""
    if not title:
        return ""
    title = NON_WORD_RE.sub(" ", title)
    title = BRACKET_CLEANUP_RE.sub("", title)
    title = REMIX_KEYWORDS_RE.sub("", title)
    title = MULTI_DASH_RE.sub("-", title)
    return " ".join(title.split()).strip().lower()


def _word_containment(a: str, b: str) -> bool:
    """Check if words of a are contained in b."""
    a_words = set(a.split())
    b_words = set(b.split())
    return a_words.issubset(b_words) or b_words.issubset(a_words)


def _fuzzy_match(a: str, b: str) -> float:
    """Fuzzy match using SequenceMatcher."""
    return SequenceMatcher(None, a, b).ratio()


def calculate_match_confidence(query: str, candidate: str) -> float:
    """
    Calculate match confidence between query and candidate.
    Returns 0.0-1.0.
    """
    if not query or not candidate:
        return 0.0

    q = clean_title_for_search(query)
    c = clean_title_for_search(candidate)

    if q == c:
        return 1.0

    if _word_containment(q, c):
        return 0.95

    return _fuzzy_match(q, c)