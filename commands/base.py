"""
commands/base.py
================
BaseCommand ABC and CommandResult dataclass.

Every command in the Nova system implements BaseCommand.  This ensures:
- A consistent interface for the CommandRouter.
- Predictable, structured results from every execution.
- Independent testability (mock execute() in router tests).

Priority rules:
  Higher priority value wins when two commands match the same text.
  Application commands use priority=20.
  Web/search commands use priority=10.
  Utility/control commands use priority=5.
  Generic URL opener uses priority=1 (lowest) to avoid intercepting
  named-application commands.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from core.context import Context


# ---------------------------------------------------------------------------
# Command result
# ---------------------------------------------------------------------------

@dataclass
class CommandResult:
    """
    Structured result returned by every command execution.

    Attributes:
        success:         True if the command completed without error.
        spoken_response: The string that Nova will speak aloud.
        command_name:    Canonical command name (e.g. 'app.open_chrome').
        data:            Optional structured payload for future use (GUI, logging).
        error:           Human-readable error description if success is False.
    """
    success: bool
    spoken_response: str
    command_name: str
    data: Optional[dict[str, Any]] = None
    error: Optional[str] = None

    @classmethod
    def ok(cls, command_name: str, response: str,
           data: Optional[dict[str, Any]] = None) -> "CommandResult":
        """Convenience constructor for a successful result."""
        return cls(success=True, spoken_response=response,
                   command_name=command_name, data=data)

    @classmethod
    def fail(cls, command_name: str, response: str, error: str) -> "CommandResult":
        """Convenience constructor for a failed result."""
        return cls(success=False, spoken_response=response,
                   command_name=command_name, error=error)


# ---------------------------------------------------------------------------
# Special router-level results (not from commands)
# ---------------------------------------------------------------------------

def unknown_command_result(raw_text: str) -> CommandResult:
    """Returned by the router when no command matches."""
    return CommandResult.fail(
        command_name="router.unknown",
        response="I'm not sure what you meant. Say 'help' for a list of things I can do.",
        error=f"No command matched: {raw_text!r}",
    )


def ambiguous_command_result(raw_text: str, candidate: str) -> CommandResult:
    """Returned by the router when confidence is in the medium range."""
    return CommandResult.fail(
        command_name="router.ambiguous",
        response=f"I heard '{raw_text}'. Did you mean: {candidate}?",
        error=f"Low confidence match: {candidate!r}",
    )


# ---------------------------------------------------------------------------
# BaseCommand
# ---------------------------------------------------------------------------

class BaseCommand(ABC):
    """
    Abstract base class for all Nova commands.

    Subclasses must define:
        name        - canonical dotted name, e.g. 'app.open_chrome'
        aliases     - list of trigger phrases / keywords
        priority    - integer; higher wins on ambiguous match
        description - one-line human-readable description (for help)

    Subclasses must implement:
        execute(params, context) -> CommandResult
        matches(text) -> float  [optional override for custom scoring]
    """

    # --- Subclasses set these as class attributes ---
    name: str = ""
    aliases: list[str] = []
    priority: int = 10
    description: str = ""

    @abstractmethod
    def execute(self, params: dict[str, Any], context: Context) -> CommandResult:
        """
        Execute the command and return a structured result.

        Args:
            params:  Extracted parameters from the spoken text
                     (e.g. {'query': 'python tutorials', 'city': 'noida'}).
            context: Shared session state.

        Returns:
            CommandResult — must never raise.
        """

    def matches(self, text: str) -> float:
        """
        Return a confidence score in [0.0, 1.0] for *text*.

        Default implementation checks for keyword presence.
        Override in subclasses for custom matching logic.
        """
        from utils.helpers import keyword_score, normalize_text
        norm = normalize_text(text)
        scores = [keyword_score(norm, alias.lower().split()) for alias in self.aliases]
        return max(scores, default=0.0)

    def extract_params(self, text: str) -> dict[str, Any]:
        """
        Extract command-specific parameters from *text*.

        Default implementation returns an empty dict.
        Override in command subclasses as needed.
        """
        return {}

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} priority={self.priority}>"
