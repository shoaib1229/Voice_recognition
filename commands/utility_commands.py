"""
commands/utility_commands.py
============================
General utility and control commands (help, exit, clear history).
"""

from __future__ import annotations

from typing import Any, Optional

from commands.base import BaseCommand, CommandResult
from core.context import Context
from utils.normalizer import normalize_intent


class HelpCommand(BaseCommand):
    """Provides a spoken summary of capabilities and lists available commands."""

    name = "control.help"
    aliases = [
        "help",
        "what can you do",
        "list commands",
        "commands",
        "help me",
    ]
    priority = 10
    description = "Lists available commands and features."

    def matches(self, text: str) -> float:
        norm = normalize_intent(text)
        for alias in self.aliases:
            if norm == alias or alias in norm:
                return 1.0
        return 0.0

    def execute(self, params: dict[str, Any], context: Context) -> CommandResult:
        summary = (
            "I can launch applications like Chrome, VS Code, Notepad, Calculator, WhatsApp, and Spotify; "
            "search Google and YouTube; open your Downloads or Documents folders; "
            "tell you the time, date, and weather; or look up topics on Wikipedia. "
            "What would you like to do?"
        )
        return CommandResult.ok(self.name, summary)


class ExitCommand(BaseCommand):
    """Signals the assistant loop to stop and terminate."""

    name = "control.exit"
    aliases = [
        "exit",
        "quit",
        "goodbye",
        "bye nova",
        "bye",
        "shut down",
        "stop nova",
    ]
    priority = 10
    description = "Exits Nova."

    def matches(self, text: str) -> float:
        norm = normalize_intent(text)
        for alias in self.aliases:
            if norm == alias or norm.startswith(alias + " "):
                return 1.0
        return 0.0

    def execute(self, params: dict[str, Any], context: Context) -> CommandResult:
        context.should_exit = True
        return CommandResult.ok(self.name, "Goodbye! Have a great day.", data={"exit": True})


class ClearHistoryCommand(BaseCommand):
    """Clears conversational memory."""

    name = "control.clear_history"
    aliases = [
        "clear history",
        "reset conversation",
        "clear conversation",
        "forget conversation",
    ]
    priority = 10
    description = "Clears previous conversational memory."

    def matches(self, text: str) -> float:
        norm = normalize_intent(text)
        for alias in self.aliases:
            if alias in norm or norm == alias:
                return 1.0
        return 0.0

    def execute(self, params: dict[str, Any], context: Context) -> CommandResult:
        context.reset_turn()
        return CommandResult.ok(self.name, "I have cleared our conversation history.", data={"reset": True})


def create_utility_commands() -> list[BaseCommand]:
    """Factory creating all control and utility commands."""
    return [
        HelpCommand(),
        ExitCommand(),
        ClearHistoryCommand(),
    ]
