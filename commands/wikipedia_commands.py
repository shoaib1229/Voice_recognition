"""
commands/wikipedia_commands.py
==============================
Wikipedia command querying the official Wikipedia summary API.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from commands.base import BaseCommand, CommandResult
from core.context import Context
from services.wikipedia_service import WikipediaService
from utils.normalizer import normalize_intent


class WikipediaCommand(BaseCommand):
    """Looks up encyclopedic summaries from Wikipedia."""

    name = "info.wikipedia"
    aliases = [
        "tell me about",
        "who is",
        "what is",
        "search wikipedia for",
        "wikipedia search for",
        "wikipedia",
    ]
    priority = 12
    description = "Looks up topics and people on Wikipedia."

    def __init__(self, wiki_service: Optional[WikipediaService] = None) -> None:
        self.wiki = wiki_service or WikipediaService()

    def matches(self, text: str) -> float:
        norm = normalize_intent(text)
        # Avoid intercepting date/time questions like "what is today's date" or "what is the time"
        if "time" in norm or "date" in norm or "weather" in norm:
            return 0.0

        for alias in self.aliases:
            if norm.startswith(alias + " "):
                return 0.95
        if norm.startswith("wikipedia "):
            return 0.95
        return 0.0

    def extract_params(self, text: str) -> dict[str, Any]:
        norm = normalize_intent(text)
        for alias in (
            "search wikipedia for ",
            "wikipedia search for ",
            "tell me about ",
            "who is ",
            "what is ",
            "wikipedia ",
        ):
            if norm.startswith(alias):
                topic = norm[len(alias):].strip()
                topic = re.sub(r"[^\w\s-]", "", topic).strip()
                return {"topic": topic}
        return {}

    def execute(self, params: dict[str, Any], context: Context) -> CommandResult:
        topic = params.get("topic", "").strip()
        if not topic:
            return CommandResult.fail(
                self.name,
                "Please specify what topic or person you would like to look up on Wikipedia.",
                error="Missing topic parameter",
            )

        summary_data, message = self.wiki.search_summary(topic)
        if summary_data is not None:
            return CommandResult.ok(
                self.name,
                message,
                data={"title": summary_data.title, "url": summary_data.page_url},
            )
        return CommandResult.fail(self.name, message, error=message)


def create_wikipedia_commands(wiki_service: Optional[WikipediaService] = None) -> list[BaseCommand]:
    """Factory creating Wikipedia commands."""
    return [WikipediaCommand(wiki_service)]
