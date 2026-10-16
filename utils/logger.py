"""
utils/logger.py
===============
Centralised logging configuration for Nova.

All modules obtain their logger via:
    from utils.logger import get_logger
    logger = get_logger(__name__)

Features:
- Rotating file handler (max 5 MB × 3 backups)
- Console handler
- Structured format: timestamp | level | module | message
- Log directory is created automatically
- API-key-shaped strings are scrubbed from messages
"""

from __future__ import annotations

import logging
import os
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

# ---------------------------------------------------------------------------
# API-key scrubber — prevent accidental secrets in log files
# ---------------------------------------------------------------------------
_KEY_PATTERN = re.compile(
    r"""(?xi)
    (api[_-]?key|apikey|secret|token|password|passwd|pwd)
    \s*[=:]\s*
    (['"]?)(\S+?)\2
    (?=\s|$|[,;\}])
    """,
    re.IGNORECASE,
)


_RAW_SECRET_PATTERN = re.compile(
    r"\b(?:AIza[0-9A-Za-z-_]{35}|sk-[a-zA-Z0-9]{20,}|xpl_[a-zA-Z0-9]{20,}|[a-fA-F0-9]{32})\b",
    re.IGNORECASE,
)


class _ScrubFilter(logging.Filter):
    """Remove likely API keys / secrets from log records before writing."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        if isinstance(record.msg, str):
            record.msg = _KEY_PATTERN.sub(r"\1=***REDACTED***", record.msg)
            record.msg = _RAW_SECRET_PATTERN.sub("***REDACTED***", record.msg)
        return True


# ---------------------------------------------------------------------------
# Format
# ---------------------------------------------------------------------------
_FMT = "%(asctime)s  %(levelname)-8s  [%(name)-20s]  %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"

# ---------------------------------------------------------------------------
# Internal registry so we don't configure the root logger twice
# ---------------------------------------------------------------------------
_configured = False


def _configure_root(log_level: str, log_file: str, project_root: Path) -> None:
    global _configured
    if _configured:
        return
    _configured = True

    # Resolve log file path relative to project root
    log_path = (project_root / log_file).resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    level = getattr(logging, log_level.upper(), logging.INFO)

    formatter = logging.Formatter(_FMT, datefmt=_DATE_FMT)
    scrub = _ScrubFilter()

    # --- File handler ---
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(scrub)

    # --- Console handler ---
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(scrub)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(file_handler)
    root.addHandler(console_handler)


def setup_logging(log_level: str = "INFO", log_file: str = "logs/assistant.log",
                  project_root: Path | None = None) -> None:
    """
    Call once at application startup (from app.py).
    Subsequent calls to get_logger() will use the configured handlers.
    """
    if project_root is None:
        project_root = Path(__file__).resolve().parent.parent
    _configure_root(log_level, log_file, project_root)


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger.  Call setup_logging() at least once before use.
    Falls back to a basic config if setup_logging() was never called.
    """
    if not _configured:
        logging.basicConfig(level=logging.INFO, format=_FMT, datefmt=_DATE_FMT)
    return logging.getLogger(name)
