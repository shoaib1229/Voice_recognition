"""
commands/folder_commands.py
===========================
Commands for opening allowlisted user folder shortcuts.
"""

from __future__ import annotations

from typing import Any, Optional

from commands.base import BaseCommand, CommandResult
from core.context import Context
from services.app_launcher_service import AppLauncherService
from utils.normalizer import normalize_intent


class OpenFolderCommand(BaseCommand):
    """Opens a specific allowlisted directory shortcut in the file explorer."""

    def __init__(
        self,
        folder_key: str,
        aliases: list[str],
        description: str,
        launcher_service: Optional[AppLauncherService] = None,
    ) -> None:
        self.name = f"folder.{folder_key}"
        self.folder_key = folder_key
        self.aliases = aliases
        self.priority = 15
        self.description = description
        self.launcher = launcher_service or AppLauncherService()

    def matches(self, text: str) -> float:
        norm = normalize_intent(text)
        for alias in self.aliases:
            if norm == alias or norm.startswith(alias + " "):
                return 1.0
            if alias in norm:
                return 0.85
        return 0.0

    def execute(self, params: dict[str, Any], context: Context) -> CommandResult:
        result = self.launcher.open_folder(self.folder_key)
        if result.success:
            return CommandResult.ok(self.name, result.message, data={"path": result.target})
        return CommandResult.fail(self.name, result.message, error=result.message)


def create_folder_commands(launcher: Optional[AppLauncherService] = None) -> list[BaseCommand]:
    """Factory creating all standard folder commands."""
    svc = launcher or AppLauncherService()
    return [
        OpenFolderCommand(
            "downloads",
            ["open downloads", "open my downloads", "show downloads", "go to downloads"],
            "Opens the Downloads folder.",
            svc,
        ),
        OpenFolderCommand(
            "documents",
            ["open documents", "open my documents", "show documents", "go to documents"],
            "Opens the Documents folder.",
            svc,
        ),
        OpenFolderCommand(
            "desktop",
            ["open desktop", "show desktop", "go to desktop"],
            "Opens the Desktop folder.",
            svc,
        ),
        OpenFolderCommand(
            "pictures",
            ["open pictures", "open photos", "open my pictures", "show pictures"],
            "Opens the Pictures folder.",
            svc,
        ),
        OpenFolderCommand(
            "project",
            ["open project folder", "open my project folder", "open my project", "open project"],
            "Opens the configured project workspace directory.",
            svc,
        ),
    ]
