"""
services/search_service.py
==========================
Safe web search and URL opener service.

Security Rules:
- Only allows http:// and https:// schemes for URL navigation.
- Rejects file://, javascript:, data:, and shell injection vectors.
- Encodes all search queries with urllib.parse.quote_plus.
- Validates shortcut targets against config/app_registry.py ALLOWED_SITES.
"""

from __future__ import annotations

import urllib.parse
import webbrowser
from dataclasses import dataclass
from typing import Optional

from config.app_registry import ALLOWED_SITES
from utils.logger import get_logger

logger = get_logger(__name__)

SAFE_SCHEMES = frozenset({"http", "https"})


@dataclass(frozen=True)
class SearchResult:
    """Structured result returned by web search and URL operations."""
    success: bool
    message: str
    url: str


class SearchService:
    """
    Executes web searches, opens website shortcuts, and validates external URLs.
    """

    def open_site(self, site_key: str) -> SearchResult:
        """
        Open a pre-approved website shortcut from ALLOWED_SITES.

        Args:
            site_key: Canonical key (e.g. 'google', 'youtube', 'github', 'gmail', 'chatgpt', 'whatsapp_web').
        """
        clean_key = site_key.strip().lower()
        if clean_key not in ALLOWED_SITES:
            return SearchResult(
                success=False,
                message=f"I don't have '{clean_key}' registered as a website shortcut.",
                url="",
            )

        entry = ALLOWED_SITES[clean_key]
        try:
            logger.info("Opening website shortcut: %s (%s)", entry.display_name, entry.url)
            webbrowser.open(entry.url)
            return SearchResult(
                success=True,
                message=f"Opening {entry.display_name}.",
                url=entry.url,
            )
        except Exception as exc:
            logger.error("Failed to open website %s: %s", entry.display_name, exc)
            return SearchResult(
                success=False,
                message=f"Could not open {entry.display_name}: {exc}",
                url=entry.url,
            )

    def search_google(self, query: str) -> SearchResult:
        """Execute a Google web search for *query*."""
        clean_query = query.strip()
        if not clean_query:
            return SearchResult(
                success=False,
                message="Please specify what you would like to search for on Google.",
                url="",
            )

        encoded = urllib.parse.quote_plus(clean_query)
        url = f"https://www.google.com/search?q={encoded}"

        try:
            logger.info("Performing Google search for: %r", clean_query)
            webbrowser.open(url)
            return SearchResult(
                success=True,
                message=f"Searching Google for '{clean_query}'.",
                url=url,
            )
        except Exception as exc:
            logger.error("Failed to launch Google search: %s", exc)
            return SearchResult(
                success=False,
                message=f"Could not perform Google search: {exc}",
                url=url,
            )

    def search_youtube(self, query: str) -> SearchResult:
        """Execute a YouTube video search for *query*."""
        clean_query = query.strip()
        if not clean_query:
            return SearchResult(
                success=False,
                message="Please specify what you would like to search for on YouTube.",
                url="",
            )

        encoded = urllib.parse.quote_plus(clean_query)
        url = f"https://www.youtube.com/results?search_query={encoded}"

        try:
            logger.info("Performing YouTube search for: %r", clean_query)
            webbrowser.open(url)
            return SearchResult(
                success=True,
                message=f"Searching YouTube for '{clean_query}'.",
                url=url,
            )
        except Exception as exc:
            logger.error("Failed to launch YouTube search: %s", exc)
            return SearchResult(
                success=False,
                message=f"Could not perform YouTube search: {exc}",
                url=url,
            )

    def search_github(self, query: str) -> SearchResult:
        """Execute a GitHub code/repository search for *query*."""
        clean_query = query.strip()
        if not clean_query:
            return SearchResult(
                success=False,
                message="Please specify what you would like to search for on GitHub.",
                url="",
            )

        encoded = urllib.parse.quote_plus(clean_query)
        url = f"https://github.com/search?q={encoded}"

        try:
            logger.info("Performing GitHub search for: %r", clean_query)
            webbrowser.open(url)
            return SearchResult(
                success=True,
                message=f"Searching GitHub for '{clean_query}'.",
                url=url,
            )
        except Exception as exc:
            logger.error("Failed to launch GitHub search: %s", exc)
            return SearchResult(
                success=False,
                message=f"Could not perform GitHub search: {exc}",
                url=url,
            )

    def open_url(self, raw_url: str) -> SearchResult:
        """
        Validate and open a raw user-provided URL in the browser.

        Security Enforcement:
        - Only http:// and https:// URLs are allowed.
        - Rejects file://, javascript:, data:, and empty targets.
        """
        clean_url = raw_url.strip()
        if not clean_url:
            return SearchResult(
                success=False,
                message="Please specify a valid web address.",
                url="",
            )

        parsed = urllib.parse.urlparse(clean_url)

        # If a scheme was provided and it's not http/https, reject immediately
        if parsed.scheme and parsed.scheme.lower() not in SAFE_SCHEMES:
            logger.warning("Security alert: Rejected unsafe URL scheme: %r", clean_url)
            return SearchResult(
                success=False,
                message="For security, only HTTP and HTTPS web addresses are permitted.",
                url=clean_url,
            )

        # If no scheme was provided, default to https://
        if not parsed.scheme:
            clean_url = f"https://{clean_url}"
            parsed = urllib.parse.urlparse(clean_url)

        if parsed.scheme.lower() not in SAFE_SCHEMES:
            logger.warning("Security alert: Rejected unsafe URL scheme: %r", clean_url)
            return SearchResult(
                success=False,
                message="For security, only HTTP and HTTPS web addresses are permitted.",
                url=clean_url,
            )

        if not parsed.netloc:
            logger.warning("Rejected malformed URL (no network location): %r", clean_url)
            return SearchResult(
                success=False,
                message="That web address does not appear to be valid.",
                url=clean_url,
            )

        try:
            logger.info("Opening validated URL: %s", clean_url)
            webbrowser.open(clean_url)
            return SearchResult(
                success=True,
                message=f"Opening {parsed.netloc}.",
                url=clean_url,
            )
        except Exception as exc:
            logger.error("Failed to open URL %s: %s", clean_url, exc)
            return SearchResult(
                success=False,
                message=f"Could not open web address: {exc}",
                url=clean_url,
            )
