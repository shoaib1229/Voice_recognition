"""
services/wikipedia_service.py
=============================
REST client for the official Wikipedia summary API.

Features:
- Queries https://en.wikipedia.org/api/rest_v1/page/summary/{title}
- Extracts a concise 1-3 sentence summary suitable for spoken output.
- Handles missing pages (404), disambiguation notices, and network timeouts.
"""

from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass
from typing import Optional

import requests

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class WikipediaSummary:
    """Structured Wikipedia knowledge summary."""
    title: str
    summary: str
    page_url: str


class WikipediaService:
    """
    Fetches encyclopedic summaries from Wikipedia's public REST API.
    """

    def __init__(self, timeout: float = 5.0) -> None:
        self.timeout = timeout
        self.headers = {
            "User-Agent": "NovaVoiceAssistant/1.0 (Desktop Voice Assistant Portfolio Project)",
            "Accept": "application/json",
        }

    def search_summary(self, topic: str, max_sentences: int = 2) -> tuple[Optional[WikipediaSummary], str]:
        """
        Retrieve a concise summary for *topic*.

        Returns:
            Tuple of (WikipediaSummary | None, spoken_message: str).
        """
        clean_topic = topic.strip()
        if not clean_topic:
            return None, "Please specify a topic to look up on Wikipedia."

        encoded_title = urllib.parse.quote(clean_topic.replace(" ", "_"))
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded_title}"

        try:
            logger.debug("Querying Wikipedia summary for topic: %r", clean_topic)
            response = requests.get(url, headers=self.headers, timeout=self.timeout)

            if response.status_code == 404:
                return None, f"I couldn't find an encyclopedic article on Wikipedia for '{clean_topic}'."

            response.raise_for_status()
            data = response.json()

            title = data.get("title", clean_topic)
            extract = data.get("extract", "").strip()

            if not extract:
                return None, f"Wikipedia has a page for '{title}', but no brief summary was available."

            # Trim to max_sentences for comfortable voice output
            sentences = re.split(r"(?<=[.!?])\s+", extract)
            shortened = " ".join(sentences[:max_sentences]).strip()

            page_url = data.get("content_urls", {}).get("desktop", {}).get("page", "")

            result = WikipediaSummary(
                title=title,
                summary=shortened,
                page_url=page_url,
            )
            return result, shortened

        except requests.Timeout:
            logger.warning("Wikipedia API request timed out for topic: %r", clean_topic)
            return None, "The Wikipedia service took too long to respond. Please try again."

        except requests.RequestException as exc:
            logger.error("Network error calling Wikipedia API: %s", exc)
            return None, "Could not connect to Wikipedia. Please check your internet connection."

        except Exception as exc:
            logger.error("Unexpected error retrieving Wikipedia summary: %s", exc)
            return None, f"An error occurred while looking up '{clean_topic}'."
