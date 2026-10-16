"""
utils/helpers.py
================
General-purpose text utilities used across the Nova pipeline.

These functions are pure (no side-effects, no I/O) so they can be
unit-tested without any mocking.
"""

from __future__ import annotations

import re
import string
from typing import Optional


# ---------------------------------------------------------------------------
# Text normalisation
# ---------------------------------------------------------------------------

def normalize_text(text: str) -> str:
    """
    Return *text* in a canonical form suitable for command matching:
    - Strip leading/trailing whitespace
    - Lowercase
    - Remove punctuation (except hyphens inside words)
    - Collapse multiple spaces into one

    >>> normalize_text("Open Chrome!  ")
    'open chrome'
    >>> normalize_text("What's the weather in Noida?")
    "what's the weather in noida"
    """
    if not text:
        return ""
    text = text.strip().lower()
    # Remove punctuation except apostrophes (contractions) and hyphens
    text = re.sub(r"[^\w\s'\-]", " ", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---------------------------------------------------------------------------
# Parameter extraction
# ---------------------------------------------------------------------------

def extract_after(text: str, markers: list[str]) -> Optional[str]:
    """
    Extract the substring that follows the *first* matching marker phrase.

    Example:
        extract_after("search youtube for python tutorials",
                      ["search youtube for", "youtube search for"])
        → "python tutorials"

        extract_after("weather in noida", ["weather in"])
        → "noida"
    """
    text_lower = text.lower()
    for marker in markers:
        marker_lower = marker.lower()
        idx = text_lower.find(marker_lower)
        if idx != -1:
            after = text[idx + len(marker):].strip()
            return after if after else None
    return None


# ---------------------------------------------------------------------------
# Keyword scoring
# ---------------------------------------------------------------------------

def keyword_score(text: str, keywords: list[str]) -> float:
    """
    Return a simple relevance score in [0.0, 1.0] indicating how many of
    *keywords* appear in *text* as whole words.

    >>> keyword_score("open chrome", ["open", "chrome"])
    1.0
    >>> keyword_score("launch chrome", ["open", "chrome"])
    0.5
    """
    if not keywords:
        return 0.0
    text_words = set(normalize_text(text).split())
    matches = sum(1 for kw in keywords if kw.lower() in text_words)
    return matches / len(keywords)


# ---------------------------------------------------------------------------
# Safety helpers
# ---------------------------------------------------------------------------

def truncate(text: str, max_length: int = 500) -> str:
    """
    Truncate *text* to *max_length* characters.
    Used as a safety guard before processing any user-supplied strings.
    """
    if len(text) > max_length:
        return text[:max_length]
    return text


def contains_forbidden(text: str, forbidden: frozenset[str]) -> bool:
    """
    Return True if *text* contains any word from the *forbidden* set.
    Used by the security layer before any action is executed.

    >>> contains_forbidden("shutdown now", frozenset({"shutdown"}))
    True
    >>> contains_forbidden("open chrome", frozenset({"shutdown"}))
    False
    """
    words = set(normalize_text(text).split())
    return bool(words & forbidden)
