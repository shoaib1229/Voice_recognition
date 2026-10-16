"""Small local conversation history used by the GUI clear-history control."""

from __future__ import annotations


class ConversationManager:
    """Stores recent local turns without sending them to a model or service."""

    def __init__(self, max_history: int = 10) -> None:
        self.max_history = max(1, max_history)
        self._history: list[tuple[str, str]] = []

    @property
    def history_length(self) -> int:
        return len(self._history) * 2

    def record_turn(self, user_text: str, reply: str) -> None:
        self._history.append((user_text, reply))
        self._history = self._history[-self.max_history:]

    def reset(self) -> None:
        self._history.clear()

    clear = reset