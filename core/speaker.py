"""
core/speaker.py
===============
Text-to-speech abstraction using pyttsx3.

Features:
- Encapsulates pyttsx3 speech synthesis.
- Loads configurable speech rate and volume from config/settings.py.
- Supports voice mode (spoken audio) and text fallback mode (console print).
- Recovers gracefully from speech engine initialization and COM/audio driver failures.
- Never prints or speaks API keys or sensitive data.
- Dependency-injected design allows 100% mock testing without real audio hardware.
"""

from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import urlsplit

import pyttsx3

from config.settings import Settings, settings as global_settings
from utils.logger import get_logger

logger = get_logger(__name__)

# Pattern to prevent accidental leakage of sensitive tokens in spoken output
_SECRET_PATTERN = re.compile(
    r"\b(?:AIza[0-9A-Za-z-_]{35}|sk-[a-zA-Z0-9]{20,}|xpl_[a-zA-Z0-9]{20,}|[a-fA-F0-9]{32})\b",
    re.IGNORECASE,
)
_CODE_BLOCK_PATTERN = re.compile(r"```[^\n]*\n[\s\S]*?```", re.MULTILINE)
_MARKDOWN_LINK_PATTERN = re.compile(r"!?\[([^\]]+)\]\([^)]+\)")
_URL_PATTERN = re.compile(r"https?://[^\s)]+", re.IGNORECASE)


def prepare_speech_text(text: str, max_chars: int = 900) -> str:
    """Make response text easier to speak without changing the visible reply."""
    speech = _SECRET_PATTERN.sub("[REDACTED_KEY]", text.strip())
    if not speech:
        return ""
    speech = _CODE_BLOCK_PATTERN.sub("I’ve included the code in the chat.", speech)
    speech = _MARKDOWN_LINK_PATTERN.sub(r"\1", speech)
    speech = _URL_PATTERN.sub(lambda match: urlsplit(match.group(0)).hostname or "a link", speech)
    speech = re.sub(r"`([^`]*)`", r"\1", speech)
    speech = re.sub(r"^\s{0,3}#{1,6}\s*", "", speech, flags=re.MULTILINE)
    speech = re.sub(r"^\s*[-*+]\s+", "", speech, flags=re.MULTILINE)
    speech = re.sub(r"^\s*\d+[.)]\s+", "", speech, flags=re.MULTILINE)
    speech = re.sub(r"(?<!\w)[*_~]|[*_~](?!\w)", "", speech)
    speech = re.sub(r"\s+", " ", speech).strip()
    if len(speech) > max_chars:
        boundary = max(speech.rfind(mark, 0, max_chars + 1) for mark in (". ", "? ", "! "))
        end = boundary + 1 if boundary >= max_chars // 2 else speech.rfind(" ", 0, max_chars)
        if end < 1:
            end = max_chars
        speech = speech[:end].rstrip(" ,;:") + ". I’ve included the full response in the chat."
    return speech


class Speaker:
    """
    Text-to-speech output abstraction for Nova.

    Usage:
        speaker = Speaker()
        speaker.speak("Hello! How can I assist you today?")
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        voice_mode: bool = True,
        engine: Optional[Any] = None,
    ) -> None:
        """
        Initialize the Speaker.

        Args:
            settings: Optional Settings instance (defaults to global settings).
            voice_mode: If True, uses pyttsx3 audio; if False, prints text only.
            engine: Optional pre-configured pyttsx3 Engine instance (for unit testing).
        """
        self._settings = settings or global_settings
        self._voice_mode = voice_mode
        self._rate = getattr(self._settings, "TTS_RATE", 175)
        self._volume = getattr(self._settings, "TTS_VOLUME", 1.0)

        self._engine: Optional[Any] = engine
        self._engine_initialized: bool = engine is not None

        if self._voice_mode and self._engine is None:
            self._init_engine()

        logger.debug(
            "Speaker initialized (voice_mode=%s, rate=%d, volume=%.2f, engine_ready=%s)",
            self._voice_mode,
            self._rate,
            self._volume,
            self.is_voice_ready(),
        )

    def _init_engine(self) -> None:
        """Initialize the pyttsx3 engine safely."""
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", self._rate)
            engine.setProperty("volume", self._volume)
            self._engine = engine
            self._engine_initialized = True
            logger.info("pyttsx3 TTS engine initialized successfully.")
        except Exception as exc:
            logger.warning("pyttsx3 engine initialization failed (falling back to text output): %s", exc)
            self._engine = None
            self._engine_initialized = False

    def is_voice_ready(self) -> bool:
        """Return True if TTS engine is active and ready."""
        return self._voice_mode and self._engine is not None

    def speak(self, text: str) -> None:
        """
        Output text either as spoken voice (voice mode) or printed text (text mode).

        Never raises: Catches all engine driver/COM errors and falls back to print.
        """
        if not text or not text.strip():
            return

        cleaned_text = text.strip()
        # Redact any accidental tokens from spoken output
        sanitized_text = _SECRET_PATTERN.sub("[REDACTED_KEY]", cleaned_text)

        # In all modes, display the speech text in console (if stdout available)
        try:
            print(f"\nNova: {sanitized_text}")
        except Exception:
            pass
        logger.info("Spoken response delivered: %s", sanitized_text[:80])

        if not self._voice_mode:
            return

        # Attempt voice synthesis if engine is available
        if self._engine is not None:
            try:
                self._engine.say(prepare_speech_text(sanitized_text))
                self._engine.runAndWait()
            except Exception as exc:
                logger.error("Error during pyttsx3 speech synthesis: %s", exc)
                # Ensure the engine is reset if a COM error occurred
                try:
                    self._engine.stop()
                except Exception:
                    pass

    def stop(self) -> None:
        """Stop any currently ongoing speech playback."""
        if self._engine is not None:
            try:
                self._engine.stop()
                logger.debug("Speech synthesis stopped.")
            except Exception as exc:
                logger.debug("Error while stopping TTS engine: %s", exc)
