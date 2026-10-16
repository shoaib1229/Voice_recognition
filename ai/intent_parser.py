"""Compatibility module: command intents are routed by the local registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ParsedIntent:
    """A locally classified conversational intent; actions stay in the registry."""
    is_action: bool
    action_id: Optional[str]
    parameters: dict[str, str]
    conversational_reply: Optional[str]
    raw_user_input: str
    confidence: float = 1.0


class IntentParser:
    """Do not execute actions here; the assistant's allowlisted registry owns them."""

    def parse(self, user_input: str) -> ParsedIntent:
        return ParsedIntent(False, None, {}, None, user_input, 0.0)