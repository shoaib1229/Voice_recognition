"""
app.py
======
Main entry point for Nova — Desktop Voice Assistant.

Supports three interactive modes:
  python app.py --text   (Interactive keyboard CLI mode)
  python app.py --voice  (Microphone voice input + pyttsx3 speech output)
  python app.py --gui    (Modern CustomTkinter desktop GUI — default)

Usage:
  python app.py [--text | --voice | --gui]
"""

from __future__ import annotations

import argparse
import sys

from config.settings import settings
from core.assistant import Assistant
from utils.logger import setup_logging, get_logger

logger = get_logger("nova.app")

# Backward-compatible alias for existing tests
NovaApp = Assistant


def main() -> None:
    """CLI argument parsing and main entry point."""
    # Ensure stdout/stderr exist in frozen windowed mode to prevent NoneType crashes
    if sys.stdout is None:
        import io
        sys.stdout = io.StringIO()
    if sys.stderr is None:
        import io
        sys.stderr = io.StringIO()

    parser = argparse.ArgumentParser(
        description="Nova — Modular Desktop Voice Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--text",
        action="store_true",
        help="Run in interactive text mode",
    )
    group.add_argument(
        "--voice",
        action="store_true",
        help="Run in voice-controlled mode with microphone and TTS",
    )
    group.add_argument(
        "--gui",
        action="store_true",
        help="Run the modern desktop GUI (default)",
    )

    args = parser.parse_args()

    # Setup central logging infrastructure
    setup_logging(
        log_level=settings.LOG_LEVEL,
        log_file=settings.LOG_FILE,
        project_root=settings.PROJECT_ROOT,
    )

    if args.text:
        # CLI text mode
        assistant = Assistant(settings=settings, voice_mode=False)
        assistant.run()
    elif args.voice:
        # Voice mode
        assistant = Assistant(settings=settings, voice_mode=True)
        assistant.run()
    else:
        # GUI mode (default when no flag or --gui)
        from ui.app_window import launch_gui
        voice_enabled = True  # Spoken speech enabled by default (toggleable in GUI sidebar)
        launch_gui(settings=settings, voice_enabled=voice_enabled)


if __name__ == "__main__":
    main()
