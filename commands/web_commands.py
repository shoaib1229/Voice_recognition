"""
commands/web_commands.py
========================
Modular commands for web search, video discovery, website shortcuts, and URL opening.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from commands.base import BaseCommand, CommandResult
from core.context import Context
from services.search_service import SearchService
from utils.normalizer import normalize_intent


class GoogleSearchCommand(BaseCommand):
    """Searches Google for a user-specified query."""

    name = "web.search_google"
    aliases = [
        "search google for",
        "google search for",
        "search the web for",
        "search for",
        "google",
    ]
    priority = 15
    description = "Searches Google for a query."

    def __init__(self, search_service: Optional[SearchService] = None) -> None:
        self.search = search_service or SearchService()

    def matches(self, text: str) -> float:
        norm = normalize_intent(text)
        for alias in self.aliases:
            if norm.startswith(alias + " "):
                return 0.95
        return 0.0

    def extract_params(self, text: str) -> dict[str, Any]:
        norm = normalize_intent(text)
        for alias in self.aliases:
            if norm.startswith(alias + " "):
                query = norm[len(alias):].strip()
                return {"query": query}
        return {}

    def execute(self, params: dict[str, Any], context: Context) -> CommandResult:
        query = params.get("query", "").strip()
        result = self.search.search_google(query)
        if result.success:
            return CommandResult.ok(self.name, result.message, data={"url": result.url, "query": query})
        return CommandResult.fail(self.name, result.message, error=result.message)


class YouTubeSearchCommand(BaseCommand):
    """Searches YouTube for videos."""

    name = "web.search_youtube"
    aliases = [
        "search youtube for",
        "youtube search for",
        "find on youtube",
        "look for on youtube",
        "play on youtube",
        "youtube",
    ]
    priority = 15
    description = "Searches YouTube for a topic or video."

    def __init__(self, search_service: Optional[SearchService] = None) -> None:
        self.search = search_service or SearchService()

    def matches(self, text: str) -> float:
        norm = normalize_intent(text)
        if norm.startswith("search youtube for ") or norm.startswith("youtube search for "):
            return 1.0
        if "on youtube" in norm or norm.startswith("youtube "):
            return 0.95
        if norm.startswith("play song ") or norm.startswith("open song ") or norm.startswith("play music "):
            return 0.95
        if norm.startswith("play "):
            # e.g. "play believer", "play despacito"
            return 0.95
        return 0.0

    @staticmethod
    def _clean_query(raw: str) -> str:
        q = raw.strip()
        # If query is "a song" or "the song", normalize to "song"
        if re.match(r"^(?:a|the)\s+song$", q, flags=re.IGNORECASE):
            return "song"
        # If query begins with "song <title>" or "the song <title>" or "a song <title>"
        q = re.sub(r"^(?:the\s+song|a\s+song|song)\s+", "", q, flags=re.IGNORECASE).strip()
        q = q.rstrip("?.!").strip()
        return q

    def extract_params(self, text: str) -> dict[str, Any]:
        raw_text = text.strip()
        norm = normalize_intent(text).rstrip("?.! ")

        # 1. Direct patterns like "search youtube for <query>"
        if norm.startswith("search youtube for "):
            return {"query": self._clean_query(norm[19:])}
        if norm.startswith("youtube search for "):
            return {"query": self._clean_query(norm[19:])}
        if norm.startswith("youtube "):
            return {"query": self._clean_query(norm[8:])}

        # 2. Pattern: "<action> <target> on youtube"
        # e.g. "Play song Believer on YouTube", "Can you please open a song on YouTube?"
        match = re.search(r"(?:search|find|look for|play|open)\s+(.+?)\s+on\s+youtube(?:\?|\.|\!)?\s*$", raw_text, flags=re.IGNORECASE)
        if match:
            return {"query": self._clean_query(match.group(1))}

        match_norm = re.search(r"(?:search|find|look for|play|open)\s+(.+?)\s+on\s+youtube", norm)
        if match_norm:
            return {"query": self._clean_query(match_norm.group(1))}

        # 3. Pattern: "play song <title>", "open song <title>", "play music <title>"
        match_play_song = re.search(r"\b(?:play|open)\s+(?:the\s+song|a\s+song|song|music)\s+(.+)$", raw_text, flags=re.IGNORECASE)
        if match_play_song:
            return {"query": self._clean_query(match_play_song.group(1))}

        # 4. Pattern: "play <title>" e.g. "Play Believer", "Play Despacito"
        match_play = re.search(r"\bplay\s+(.+)$", raw_text, flags=re.IGNORECASE)
        if match_play:
            return {"query": self._clean_query(match_play.group(1))}

        if norm.startswith("play song "):
            return {"query": self._clean_query(norm[10:])}
        if norm.startswith("open song "):
            return {"query": self._clean_query(norm[10:])}
        if norm.startswith("play music "):
            return {"query": self._clean_query(norm[11:])}
        if norm.startswith("play "):
            return {"query": self._clean_query(norm[5:])}

        return {}

    def execute(self, params: dict[str, Any], context: Context) -> CommandResult:
        query = params.get("query", "").strip()
        result = self.search.search_youtube(query)
        if result.success:
            return CommandResult.ok(self.name, result.message, data={"url": result.url, "query": query})
        return CommandResult.fail(self.name, result.message, error=result.message)


class GitHubSearchCommand(BaseCommand):
    """Searches GitHub for repositories and code."""

    name = "web.search_github"
    aliases = [
        "search github for",
        "github search for",
        "find on github",
    ]
    priority = 15
    description = "Searches GitHub for projects or code."

    def __init__(self, search_service: Optional[SearchService] = None) -> None:
        self.search = search_service or SearchService()

    def matches(self, text: str) -> float:
        norm = normalize_intent(text)
        if norm.startswith("search github for ") or "on github" in norm:
            return 0.95
        return 0.0

    def extract_params(self, text: str) -> dict[str, Any]:
        norm = normalize_intent(text)
        if norm.startswith("search github for "):
            return {"query": norm[18:].strip()}
        match = re.search(r"(?:search|find)\s+(.+?)\s+on\s+github", norm)
        if match:
            return {"query": match.group(1).strip()}
        return {}

    def execute(self, params: dict[str, Any], context: Context) -> CommandResult:
        query = params.get("query", "").strip()
        result = self.search.search_github(query)
        if result.success:
            return CommandResult.ok(self.name, result.message, data={"url": result.url, "query": query})
        return CommandResult.fail(self.name, result.message, error=result.message)


class OpenWebsiteShortcutCommand(BaseCommand):
    """Opens a pre-registered website shortcut (Google, YouTube, GitHub, etc.)."""

    def __init__(
        self,
        site_key: str,
        aliases: list[str],
        description: str,
        search_service: Optional[SearchService] = None,
    ) -> None:
        self.name = f"web.open_{site_key}"
        self.site_key = site_key
        self.aliases = aliases
        self.priority = 10
        self.description = description
        self.search = search_service or SearchService()

    def matches(self, text: str) -> float:
        norm = normalize_intent(text)
        for alias in self.aliases:
            if norm == alias or norm.startswith(alias + " "):
                return 1.0
            if alias in norm:
                return 0.85
        return 0.0

    def execute(self, params: dict[str, Any], context: Context) -> CommandResult:
        result = self.search.open_site(self.site_key)
        if result.success:
            return CommandResult.ok(self.name, result.message, data={"url": result.url})
        return CommandResult.fail(self.name, result.message, error=result.message)


class OpenURLCommand(BaseCommand):
    """Opens a validated external URL in the browser."""

    name = "web.open_url"
    aliases = ["open url", "go to", "visit", "open website"]
    priority = 5  # Lower priority than specific named application commands
    description = "Opens a validated web URL in the browser."

    def __init__(self, search_service: Optional[SearchService] = None) -> None:
        self.search = search_service or SearchService()

    def matches(self, text: str) -> float:
        norm = normalize_intent(text)
        # Check if text contains http or domain-like string
        if "http://" in norm or "https://" in norm or ".com" in norm or ".org" in norm or ".net" in norm:
            return 0.8
        return 0.0

    def extract_params(self, text: str) -> dict[str, Any]:
        norm = normalize_intent(text)
        for prefix in ("open url ", "go to ", "visit ", "open website ", "open "):
            if norm.startswith(prefix):
                target = norm[len(prefix):].strip()
                return {"url": target}
        return {"url": norm}

    def execute(self, params: dict[str, Any], context: Context) -> CommandResult:
        url = params.get("url", "").strip()
        result = self.search.open_url(url)
        if result.success:
            return CommandResult.ok(self.name, result.message, data={"url": result.url})
        return CommandResult.fail(self.name, result.message, error=result.message)


def create_web_commands(search_service: Optional[SearchService] = None) -> list[BaseCommand]:
    """Factory creating all web search and shortcut commands."""
    svc = search_service or SearchService()
    return [
        GoogleSearchCommand(svc),
        YouTubeSearchCommand(svc),
        GitHubSearchCommand(svc),
        OpenWebsiteShortcutCommand("google", ["open google", "go to google", "launch google"], "Opens Google homepage.", svc),
        OpenWebsiteShortcutCommand("youtube", ["open youtube", "go to youtube", "launch youtube"], "Opens YouTube homepage.", svc),
        OpenWebsiteShortcutCommand("github", ["open github", "go to github", "launch github"], "Opens GitHub.", svc),
        OpenWebsiteShortcutCommand("gmail", ["open gmail", "check my email", "open my email", "open email", "go to gmail"], "Opens Gmail.", svc),
        OpenWebsiteShortcutCommand("linkedin", ["open linkedin", "go to linkedin", "launch linkedin"], "Opens LinkedIn.", svc),
        OpenWebsiteShortcutCommand("chatgpt", ["open chatgpt", "open chat gpt", "go to chatgpt", "launch chatgpt"], "Opens ChatGPT.", svc),
        OpenWebsiteShortcutCommand("whatsapp_web", ["open whatsapp web", "launch whatsapp web"], "Opens WhatsApp Web.", svc),
        OpenURLCommand(svc),
    ]
