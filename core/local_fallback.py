"""Deterministic local responses for conversational input Nova cannot route."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from commands.base import CommandResult
from utils.normalizer import normalize_intent


class LocalFallbackHandler:
    """Answer common social turns and be explicit when a question needs a model."""

    _GREETINGS = {
        "hi", "hello", "hey", "hello nova", "hi nova", "hey nova",
        "good morning", "good afternoon", "good evening",
    }
    _THANKS = {
        "thanks", "thank you", "thanks nova", "thank you nova",
        "thanks a lot", "thank you so much", "i appreciate it", "much appreciated",
    }
    _HELP = {
        "help", "how help", "how help me", "what do", "what help with",
        "what help me with", "what things do", "what kind of things do",
        "what can you do", "what can you help me with",
    }
    _JOKES = {"tell me a joke", "say a joke", "make me laugh", "tell a joke"}

    def respond(self, text: str) -> Optional[CommandResult]:
        """Return a local response or an honest unsupported response."""
        normalized = normalize_intent(text)
        normalized = re.sub(r"[^\w\s']", "", normalized).strip()

        if normalized in self._GREETINGS or normalized in {
            "how are you", "how are you nova", "hi how are you", "hello how are you", "hey how are you",
        }:
            return self._result("local.greeting", "Hi! I'm Nova, ready to help. What would you like to do?")
        if normalized in self._THANKS:
            return self._result("local.thanks", "You're welcome. Let me know what you'd like to do next.")
        if normalized in self._HELP:
            return self._result(
                "local.help",
                "I can open supported apps and folders, search Google, YouTube, or Wikipedia, "
                "check weather, and report the time or date. Ask me to open or search for something.",
            )
        if normalized in {"what is your name", "who are you", "who is nova"}:
            return self._result("local.identity", "I'm Nova, your desktop voice assistant.")
        if normalized in {"what time is it", "tell me the time"}:
            now = datetime.now().astimezone()
            return self._result("local.time", f"The current time is {now.strftime('%I:%M %p').lstrip('0')}.")
        if normalized in {"what is the date", "what is today's date", "tell me the date"}:
            now = datetime.now().astimezone()
            return self._result("local.date", f"Today is {now.strftime('%A, %B')} {now.day}, {now.year}.")
        if normalized in self._JOKES:
            return self._result("local.joke", "Why did the computer go to the doctor? It had a virus.")
        return CommandResult(
            success=False,
            command_name="local.unsupported",
            spoken_response="I can't answer that offline. I can help with supported desktop commands, web searches, weather, time, and date.",
            error="Request requires unsupported offline knowledge.",
            data={"source": "local_fallback", "ai_generated": False},
        )

    @staticmethod
    def _result(command_name: str, response: str) -> CommandResult:
        return CommandResult.ok(
            command_name,
            response,
            data={"source": "local_fallback", "ai_generated": False},
        )
