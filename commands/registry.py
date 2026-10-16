"""
commands/registry.py
====================
CommandRegistry — the central registry of all registered Nova commands.

How it works:
1. Each command module (application_commands.py, web_commands.py, etc.)
   calls registry.register(SomeCommand()) during import.
2. The assistant calls CommandRouter which queries the registry via find().
3. find() returns commands ranked by (score DESC, priority DESC).
4. The router applies confidence thresholds and calls execute().

Priority tie-breaking ensures:
  - "open chrome" → app.open_chrome (priority=20) beats web.open_url (priority=1)
  - Specific named commands always beat generic catch-all commands.
"""

from __future__ import annotations

from typing import Optional

from commands.base import BaseCommand
from utils.logger import get_logger

logger = get_logger(__name__)


class ScoredCommand:
    """A command paired with its match score for a specific input."""

    __slots__ = ("command", "score")

    def __init__(self, command: BaseCommand, score: float) -> None:
        self.command = command
        self.score = score

    def __repr__(self) -> str:
        return f"<ScoredCommand name={self.command.name!r} score={self.score:.2f}>"


class CommandRegistry:
    """
    Registry of all registered BaseCommand instances.

    Usage:
        registry = CommandRegistry()
        registry.register(OpenChromeCommand())
        results = registry.find("open chrome")
    """

    def __init__(self) -> None:
        self._commands: list[BaseCommand] = []

    def register(self, command: BaseCommand) -> None:
        """Add *command* to the registry."""
        if not command.name:
            raise ValueError(f"Command {command!r} must have a non-empty name.")
        self._commands.append(command)
        logger.debug("Registered command: %s (priority=%d)", command.name, command.priority)

    def find(self, text: str) -> list[ScoredCommand]:
        """
        Return all commands with a non-zero match score for *text*,
        sorted by (score DESC, priority DESC).

        The router applies confidence thresholds to the returned list.
        """
        scored: list[ScoredCommand] = []
        for cmd in self._commands:
            score = cmd.matches(text)
            if score > 0.0:
                scored.append(ScoredCommand(cmd, score))

        scored.sort(key=lambda s: (s.score, s.command.priority), reverse=True)
        return scored

    def list_commands(self) -> list[dict]:
        """Return a list of command metadata dicts (for the help command)."""
        return [
            {
                "name": cmd.name,
                "description": cmd.description,
                "aliases": cmd.aliases,
                "priority": cmd.priority,
            }
            for cmd in sorted(self._commands, key=lambda c: c.name)
        ]

    def __len__(self) -> int:
        return len(self._commands)
