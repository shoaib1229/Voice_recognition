"""
core/context.py
===============
Shared, mutable session state passed through the assistant pipeline.

A Context object is created once per assistant session and injected
into every command execution.  Commands may read prior state (e.g.
the last spoken response) but should not store persistent user data here.

Design note: this is intentionally lightweight.  Persistent storage
(history log, user preferences) belongs in the services layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Context:
    """Mutable session state for one Nova assistant session."""

    # --- Input mode ---
    # True  → voice mode (microphone + TTS)
    # False → text mode (stdin + stdout)
    voice_mode: bool = True

    # --- Loop control ---
    # Set to True by StopCommand / ExitCommand to break the main loop
    should_exit: bool = False
    # Set to True when the user asks Nova to stop listening temporarily
    listening_paused: bool = False

    # --- Last interaction ---
    last_input: Optional[str] = None
    last_command_name: Optional[str] = None
    last_response: Optional[str] = None
    last_success: bool = True

    # --- Session counters ---
    turn_count: int = 0
    error_count: int = 0

    # --- Future: wake-word support ---
    # When wake-word detection is added, the listener will set
    # wake_word_detected=True before passing control to the main loop.
    # The main loop will reset it after each interaction cycle.
    wake_word_detected: bool = False

    def reset_turn(self) -> None:
        """Called at the start of each new interaction turn."""
        self.last_input = None
        self.last_command_name = None
        self.last_response = None
        self.last_success = True

    def record_turn(
        self,
        user_input: str,
        command_name: Optional[str],
        response: str,
        success: bool,
    ) -> None:
        """Update state after a command has been processed."""
        self.last_input = user_input
        self.last_command_name = command_name
        self.last_response = response
        self.last_success = success
        self.turn_count += 1
        if not success:
            self.error_count += 1
