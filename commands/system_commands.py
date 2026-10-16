"""
commands/system_commands.py
===========================
System utility commands (date, time).
"""

from __future__ import annotations

import datetime
from typing import Any, Optional

from commands.base import BaseCommand, CommandResult
from core.context import Context
from services.confirmation_service import ConfirmationService
from utils.normalizer import normalize_intent


class GetTimeCommand(BaseCommand):
    """Speaks the current local time."""

    name = "system.get_time"
    aliases = [
        "what time is it",
        "current time",
        "tell me the time",
        "what is the time",
        "time please",
    ]
    priority = 10
    description = "Tells the current time."

    def matches(self, text: str) -> float:
        norm = normalize_intent(text)
        for alias in self.aliases:
            if alias in norm or norm == alias:
                return 1.0
        return 0.0

    def execute(self, params: dict[str, Any], context: Context) -> CommandResult:
        now = datetime.datetime.now()
        # Formatted cleanly: e.g. "5:45 PM"
        formatted_time = now.strftime("%I:%M %p").lstrip("0")
        message = f"The current time is {formatted_time}."
        return CommandResult.ok(self.name, message, data={"time": formatted_time})


class GetDateCommand(BaseCommand):
    """Speaks the current date."""

    name = "system.get_date"
    aliases = [
        "what is today's date",
        "what is the date",
        "what date is it",
        "today's date",
        "what day is it",
        "current date",
    ]
    priority = 10
    description = "Tells today's date."

    def matches(self, text: str) -> float:
        norm = normalize_intent(text)
        for alias in self.aliases:
            if alias in norm or norm == alias:
                return 1.0
        return 0.0

    def execute(self, params: dict[str, Any], context: Context) -> CommandResult:
        now = datetime.datetime.now()
        # Formatted cleanly: e.g. "Saturday, October 10, 2026"
        formatted_date = now.strftime("%A, %B %d, %Y")
        message = f"Today is {formatted_date}."
        return CommandResult.ok(self.name, message, data={"date": formatted_date})


class ShutdownLaptopCommand(BaseCommand):
    """Schedules a safe computer shutdown with cancel window."""

    name = "system.shutdown"
    aliases = [
        "shutdown my laptop",
        "shut down my laptop",
        "shutdown my computer",
        "shut down my computer",
        "shutdown computer",
        "shut down computer",
        "turn off my laptop",
        "turn off my computer",
        "turn off computer",
        "shutdown pc",
        "shut down pc",
    ]
    priority = 25
    description = "Safely shuts down the laptop or computer."

    def __init__(self, confirmation_service: Optional[ConfirmationService] = None) -> None:
        self.confirmation = confirmation_service or ConfirmationService()

    def matches(self, text: str) -> float:
        norm = normalize_intent(text)
        if "cancel" in norm or "abort" in norm:
            return 0.0
        for alias in self.aliases:
            if alias in norm or norm == alias:
                return 1.0
        if "shutdown" in norm or "shut down" in norm or "turn off" in norm:
            return 0.9
        return 0.0

    def execute(self, params: dict[str, Any], context: Context) -> CommandResult:
        import os
        confirmed = self.confirmation.confirm("Shut down your computer")
        if not confirmed:
            return CommandResult.ok(
                self.name,
                "Shutdown cancelled. Your computer will stay on.",
                data={"cancelled": True},
            )

        try:
            # Schedule Windows shutdown in 15 seconds to allow safe cancellation
            os.system("shutdown /s /t 15 /c \"Nova is shutting down your PC. Say 'cancel shutdown' to stop.\"")
            msg = "Shutting down your computer in 15 seconds. Say 'cancel shutdown' if you want to abort."
            return CommandResult.ok(self.name, msg, data={"action": "shutdown", "timer_s": 15})
        except Exception as exc:
            return CommandResult.fail(self.name, f"Could not initiate shutdown: {exc}", error=str(exc))


class RestartLaptopCommand(BaseCommand):
    """Schedules a computer restart with cancel window."""

    name = "system.restart"
    aliases = [
        "restart my laptop",
        "reboot my laptop",
        "restart my computer",
        "reboot my computer",
        "restart pc",
        "reboot pc",
        "restart computer",
    ]
    priority = 25
    description = "Restarts the laptop or computer."

    def __init__(self, confirmation_service: Optional[ConfirmationService] = None) -> None:
        self.confirmation = confirmation_service or ConfirmationService()

    def matches(self, text: str) -> float:
        norm = normalize_intent(text)
        if "cancel" in norm or "abort" in norm:
            return 0.0
        for alias in self.aliases:
            if alias in norm or norm == alias:
                return 1.0
        if "restart" in norm or "reboot" in norm:
            return 0.9
        return 0.0

    def execute(self, params: dict[str, Any], context: Context) -> CommandResult:
        import os
        confirmed = self.confirmation.confirm("Restart your computer")
        if not confirmed:
            return CommandResult.ok(
                self.name,
                "Restart cancelled. Your computer will stay running.",
                data={"cancelled": True},
            )

        try:
            os.system("shutdown /r /t 15 /c \"Nova is restarting your PC. Say 'cancel shutdown' to stop.\"")
            msg = "Restarting your computer in 15 seconds. Say 'cancel shutdown' if you want to abort."
            return CommandResult.ok(self.name, msg, data={"action": "restart", "timer_s": 15})
        except Exception as exc:
            return CommandResult.fail(self.name, f"Could not initiate restart: {exc}", error=str(exc))


class CancelShutdownCommand(BaseCommand):
    """Cancels a pending shutdown or restart."""

    name = "system.cancel_shutdown"
    aliases = [
        "cancel shutdown",
        "abort shutdown",
        "stop shutdown",
        "cancel restart",
        "abort restart",
    ]
    priority = 30
    description = "Cancels a scheduled shutdown or restart."

    def matches(self, text: str) -> float:
        norm = normalize_intent(text)
        for alias in self.aliases:
            if alias in norm or norm == alias:
                return 1.0
        return 0.0

    def execute(self, params: dict[str, Any], context: Context) -> CommandResult:
        import os
        try:
            os.system("shutdown /a")
            msg = "Scheduled shutdown or restart has been cancelled."
            return CommandResult.ok(self.name, msg, data={"action": "cancel_shutdown"})
        except Exception as exc:
            return CommandResult.fail(self.name, f"Could not cancel shutdown: {exc}", error=str(exc))


class LockScreenCommand(BaseCommand):
    """Locks the Windows desktop workstation."""

    name = "system.lock"
    aliases = [
        "lock my laptop",
        "lock laptop",
        "lock my computer",
        "lock computer",
        "lock screen",
        "lock pc",
    ]
    priority = 25
    description = "Locks the computer screen."

    def matches(self, text: str) -> float:
        norm = normalize_intent(text)
        for alias in self.aliases:
            if alias in norm or norm == alias:
                return 1.0
        return 0.0

    def execute(self, params: dict[str, Any], context: Context) -> CommandResult:
        import ctypes
        try:
            ctypes.windll.user32.LockWorkStation()
            msg = "Locking your screen."
            return CommandResult.ok(self.name, msg, data={"action": "lock"})
        except Exception as exc:
            return CommandResult.fail(self.name, f"Could not lock workstation: {exc}", error=str(exc))


def create_system_commands(
    confirmation: Optional[ConfirmationService] = None,
) -> list[BaseCommand]:
    """Factory creating system utility and power commands."""
    conf = confirmation or ConfirmationService()
    return [
        GetTimeCommand(),
        GetDateCommand(),
        ShutdownLaptopCommand(confirmation_service=conf),
        RestartLaptopCommand(confirmation_service=conf),
        CancelShutdownCommand(),
        LockScreenCommand(),
    ]

