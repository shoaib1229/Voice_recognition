"""
config/settings.py
==================
Loads environment variables from .env and exposes a typed, frozen
Settings dataclass.  Any module that needs configuration imports from
here — never from os.environ directly.

Usage:
    from config.settings import settings
    print(settings.TTS_RATE)
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Locate project root (or executable folder if packaged with PyInstaller)
if getattr(sys, "frozen", False):
    _PROJECT_ROOT = Path(sys.executable).resolve().parent
else:
    _PROJECT_ROOT = Path(__file__).resolve().parent.parent

_ENV_FILE = _PROJECT_ROOT / ".env"
if _ENV_FILE.exists():
    load_dotenv(dotenv_path=_ENV_FILE, override=False)
else:
    # Fallback to current working directory if .env is placed there
    load_dotenv(dotenv_path=Path.cwd() / ".env", override=False)


class ConfigurationError(RuntimeError):
    """Raised when a required configuration value is missing or invalid."""


def _require(key: str) -> str:
    """Return the value of *key* from the environment, raising if absent."""
    value = os.getenv(key, "").strip()
    if not value:
        raise ConfigurationError(
            f"Required environment variable '{key}' is not set. "
            f"Copy .env.example → .env and fill in your values."
        )
    return value


def _optional(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _int(key: str, default: int) -> int:
    raw = os.getenv(key, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        raise ConfigurationError(
            f"Environment variable '{key}' must be an integer, got: {raw!r}"
        )


def _float(key: str, default: float) -> float:
    raw = os.getenv(key, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        raise ConfigurationError(
            f"Environment variable '{key}' must be a float, got: {raw!r}"
        )


@dataclass(frozen=True)
class Settings:
    """Immutable, typed configuration for the Nova assistant."""

    # ---- External APIs ----
    OPENWEATHER_API_KEY: str

    # ---- Speech Recognition ----
    SPEECH_LANGUAGE: str
    SPEECH_TIMEOUT: int
    SPEECH_PHRASE_LIMIT: int

    # ---- Text-to-Speech ----
    TTS_RATE: int
    TTS_VOLUME: float

    # ---- Logging ----
    LOG_LEVEL: str
    LOG_FILE: str

    # ---- Optional application paths ----
    CHROME_PATH: str
    EDGE_PATH: str
    VSCODE_PATH: str
    WHATSAPP_PATH: str
    SPOTIFY_PATH: str

    # ---- Optional custom folders ----
    PROJECT_FOLDER: str

    # ---- Project root (injected, not from env) ----
    PROJECT_ROOT: Path

    # ---- Speech recognition service request timeout (optional for compatibility) ----
    SPEECH_RECOGNITION_TIMEOUT: int = 15

    # ---- Future: wake-word support (disabled by default) ----
    # WAKE_WORD: str = "nova"
    # WAKE_WORD_ENABLED: bool = False


def _build_settings() -> Settings:
    """Construct and return the Settings singleton."""
    return Settings(
        # External API keys are optional at startup and used only by their features.
        OPENWEATHER_API_KEY=_optional("OPENWEATHER_API_KEY"),

        # Speech
        SPEECH_LANGUAGE=_optional("SPEECH_LANGUAGE", "en-IN"),
        SPEECH_TIMEOUT=_int("SPEECH_TIMEOUT", 7),
        SPEECH_PHRASE_LIMIT=_int("SPEECH_PHRASE_LIMIT", 20),
        SPEECH_RECOGNITION_TIMEOUT=_int("SPEECH_RECOGNITION_TIMEOUT", 15),

        # TTS
        TTS_RATE=_int("TTS_RATE", 175),
        TTS_VOLUME=_float("TTS_VOLUME", 1.0),

        # Logging
        LOG_LEVEL=_optional("LOG_LEVEL", "INFO").upper(),
        LOG_FILE=_optional("LOG_FILE", "logs/assistant.log"),

        # App paths (blank = auto-detect)
        CHROME_PATH=_optional("CHROME_PATH"),
        EDGE_PATH=_optional("EDGE_PATH"),
        VSCODE_PATH=_optional("VSCODE_PATH"),
        WHATSAPP_PATH=_optional("WHATSAPP_PATH"),
        SPOTIFY_PATH=_optional("SPOTIFY_PATH"),

        # Custom folders
        PROJECT_FOLDER=_optional("PROJECT_FOLDER"),

        PROJECT_ROOT=_PROJECT_ROOT,
    )


# Module-level singleton — import this everywhere
settings: Settings = _build_settings()

