"""
utils/normalizer.py
===================
Intent normalizer — strips polite filler and canonicalises synonym verbs
so that "please can you launch chrome for me" becomes "open chrome" before
it reaches the command router.

This keeps command pattern lists short and deterministic.
No NLP libraries required — pure string rules.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Polite prefix patterns to strip (order matters — longest first)
# ---------------------------------------------------------------------------
_POLITE_PREFIXES: list[str] = [
    r"nova[,\s]+please\s+can\s+you\s+",
    r"nova[,\s]+could\s+you\s+",
    r"nova[,\s]+can\s+you\s+",
    r"nova[,\s]+please\s+",
    r"nova[,\s]+",
    r"please\s+can\s+you\s+",
    r"please\s+could\s+you\s+",
    r"can\s+you\s+please\s+",
    r"could\s+you\s+please\s+",
    r"can\s+you\s+",
    r"could\s+you\s+",
    r"please\s+",
    r"would\s+you\s+",
    r"i\s+want\s+you\s+to\s+",
    r"i\s+want\s+to\s+",
    r"i\s+need\s+you\s+to\s+",
    r"i\s+need\s+to\s+",
]

# ---------------------------------------------------------------------------
# Polite suffix patterns to strip
# ---------------------------------------------------------------------------
_POLITE_SUFFIXES: list[str] = [
    r"\s+for\s+me\s*$",
    r"\s+please\s*$",
    r"\s+now\s*$",
    r"\s+right\s+now\s*$",
    r"\s+for\s+me\s+please\s*$",
]

# ---------------------------------------------------------------------------
# Verb synonym map  →  canonical verb
# ---------------------------------------------------------------------------
_VERB_SYNONYMS: dict[str, str] = {
    "launch":  "open",
    "start":   "open",
    "run":     "open",
    "fire up": "open",
    "boot":    "open",
    "bring up":"open",
    "find":    "search",
    "look for":"search",
    "look up": "search",
    "show me": "search",
    "tell me about": "wikipedia",
    "who is":  "wikipedia",
    "what is": "wikipedia",
}

# Pre-compile all patterns for performance
_compiled_prefixes = [re.compile(p, re.IGNORECASE) for p in _POLITE_PREFIXES]
_compiled_suffixes = [re.compile(p, re.IGNORECASE) for p in _POLITE_SUFFIXES]


def normalize_intent(text: str) -> str:
    """
    Strip polite filler and canonicalise synonym verbs.

    Returns a clean, lowercase intent string ready for command matching.

    Examples:
        "Please can you launch Chrome for me" → "open chrome"
        "Find Python tutorials on YouTube"    → "search python tutorials on youtube"
        "Nova, open WhatsApp"                 → "open whatsapp"
        "What is Python?"                     → "wikipedia python"
    """
    if not text:
        return ""

    result = text.strip().lower()

    # Strip polite prefixes
    for pattern in _compiled_prefixes:
        result = pattern.sub("", result, count=1).strip()
        if result != text.strip().lower():
            break  # Stop after first match to avoid over-stripping

    # Strip polite suffixes
    for pattern in _compiled_suffixes:
        result = pattern.sub("", result).strip()

    # Normalise verb synonyms (longest multi-word synonyms first)
    for synonym in sorted(_VERB_SYNONYMS, key=len, reverse=True):
        if result.startswith(synonym):
            result = _VERB_SYNONYMS[synonym] + result[len(synonym):]
            break

    return result.strip()
