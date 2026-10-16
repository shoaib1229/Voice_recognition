"""
commands/application_commands.py
================================
Modular commands for launching allowlisted desktop applications.

Priority: 20 (High priority — takes precedence over generic URL/open commands).
"""

from __future__ import annotations

import re
from typing import Any, Optional

from commands.base import BaseCommand, CommandResult
from config.app_registry import ALLOWED_APPS
from core.context import Context
from services.app_launcher_service import AppLauncherService
from services.confirmation_service import ConfirmationService
from utils.helpers import normalize_text
from utils.normalizer import normalize_intent


class OpenApplicationCommand(BaseCommand):
    """
    Command to launch a specific desktop application by key.
    """

    def __init__(
        self,
        app_key: str,
        aliases: list[str],
        description: str,
        launcher_service: Optional[AppLauncherService] = None,
    ) -> None:
        self.name = f"app.open_{app_key}"
        self.app_key = app_key
        self.aliases = aliases
        self.priority = 20
        self.description = description
        self.launcher = launcher_service or AppLauncherService()

    def matches(self, text: str) -> float:
        norm = normalize_intent(text)
        # Defer to WhatsAppChatCommand if contact or chat is mentioned
        if self.app_key == "whatsapp" and ("chat" in norm or "message" in norm):
            return 0.0

        for alias in self.aliases:
            if norm == alias or norm.startswith(alias + " "):
                return 1.0
            if alias in norm:
                return 0.9
        return 0.0

    def execute(self, params: dict[str, Any], context: Context) -> CommandResult:
        result = self.launcher.launch_app(self.app_key)
        if result.success:
            return CommandResult.ok(
                command_name=self.name,
                response=result.message,
                data={"target": result.target, "fallback_used": result.fallback_used},
            )
        return CommandResult.fail(
            command_name=self.name,
            response=result.message,
            error=result.message,
        )


class WhatsAppChatCommand(BaseCommand):
    """
    Opens a WhatsApp chat or composes a message for a given contact or phone number.
    """

    name = "app.whatsapp_chat"
    aliases = [
        "whatsapp chat with",
        "open whatsapp chat with",
        "send whatsapp message to",
        "send message on whatsapp to",
        "message on whatsapp to",
        "send message to",
        "chat with on whatsapp",
    ]
    priority = 25
    description = "Opens a WhatsApp conversation or composes a message."

    def __init__(
        self,
        confirmation_service: Optional[ConfirmationService] = None,
        launcher_service: Optional[AppLauncherService] = None,
    ) -> None:
        self.confirmation = confirmation_service or ConfirmationService()
        self.launcher = launcher_service or AppLauncherService()

    def matches(self, text: str) -> float:
        norm = normalize_intent(text)
        if "whatsapp" in norm and ("chat" in norm or "message" in norm or "send" in norm):
            return 1.0
        for alias in self.aliases:
            if alias in norm:
                return 0.95
        return 0.0

    def extract_params(self, text: str) -> dict[str, Any]:
        norm = normalize_intent(text)
        contact = ""
        message = ""

        # Check for message delimiters like " saying ", " that ", ": ", " with text "
        for splitter in (" saying ", " that ", ": ", " with text ", " with message "):
            if splitter in norm:
                parts = norm.split(splitter, 1)
                norm_contact_part = parts[0]
                message = parts[1].strip()
                norm = norm_contact_part
                break

        # If not split yet, check " message <text>" where "message" acts as a delimiter after the contact
        if not message and " message " in norm:
            parts = norm.split(" message ", 1)
            norm = parts[0]
            message = parts[1].strip()

        for alias in self.aliases:
            if alias in norm:
                idx = norm.find(alias) + len(alias)
                contact = norm[idx:].strip()
                break

        # Handle "message <contact> on whatsapp"
        if not contact:
            m = re.search(r"\bmessage\s+(.+?)\s+on\s+whatsapp\b", norm)
            if m:
                contact = m.group(1).strip()

        if not contact:
            m = re.search(r"\bchat\s+with\s+(.+?)\s+on\s+whatsapp\b", norm)
            if m:
                contact = m.group(1).strip()

        if not contact and not message:
            contact = norm.replace("whatsapp", "").replace("send", "").replace("message", "").replace("chat", "").replace("with", "").strip()

        # Clean contact of extra prepositions
        contact = re.sub(r"^(?:to|with)\s+", "", contact).strip()
        contact = re.sub(r"[^\w\s+]", "", contact).strip()
        return {"contact": contact, "message": message}

    def execute(self, params: dict[str, Any], context: Context) -> CommandResult:
        import urllib.parse
        import webbrowser

        contact = params.get("contact", "").strip()
        message = params.get("message", "").strip()

        if not contact and not message:
            return CommandResult.fail(
                self.name,
                "Please specify a contact name or message for WhatsApp.",
                error="Missing contact and message parameters",
            )

        # Format display name cleanly
        display_contact = contact.title() if contact and not contact.isdigit() else (contact or "your chat")

        # Obtain confirmation if needed
        action_desc = f"Open WhatsApp to prepare message for '{display_contact}': '{message}'" if message else f"Open WhatsApp chat with '{display_contact}'"
        confirmed = self.confirmation.confirm(action_desc)

        if not confirmed:
            return CommandResult.ok(
                self.name,
                f"Action cancelled. I will not open WhatsApp chat with {display_contact}.",
                data={"cancelled": True},
            )

        # Build URL
        digits = re.sub(r"[^\d]", "", contact)
        if digits and len(digits) >= 10:
            if message:
                encoded_msg = urllib.parse.quote(message)
                chat_url = f"https://wa.me/{digits}?text={encoded_msg}"
            else:
                chat_url = f"https://wa.me/{digits}"
        else:
            if message:
                encoded_msg = urllib.parse.quote(message)
                chat_url = f"https://web.whatsapp.com/send?text={encoded_msg}"
            else:
                chat_url = "https://web.whatsapp.com"

        webbrowser.open(chat_url)

        # Truthful output: Opening WhatsApp, but never claiming it was delivered
        if message:
            msg = f"Opening WhatsApp chat with {display_contact} with prefilled message '{message}'. Please click send in WhatsApp to deliver it."
        else:
            msg = f"Opening WhatsApp chat with {display_contact}."

        return CommandResult.ok(
            self.name,
            msg,
            data={"contact": display_contact, "message": message, "url": chat_url},
        )


def create_application_commands(
    launcher: Optional[AppLauncherService] = None,
    confirmation: Optional[ConfirmationService] = None,
) -> list[BaseCommand]:
    """Factory creating all standard desktop application commands."""
    svc = launcher or AppLauncherService()
    conf = confirmation or ConfirmationService()
    return [
        OpenApplicationCommand(
            "chrome",
            ["open chrome", "launch chrome", "start chrome", "open google chrome", "launch google chrome"],
            "Launches Google Chrome browser.",
            svc,
        ),
        OpenApplicationCommand(
            "edge",
            ["open edge", "launch edge", "start edge", "open microsoft edge", "launch microsoft edge"],
            "Launches Microsoft Edge browser.",
            svc,
        ),
        OpenApplicationCommand(
            "vscode",
            ["open vs code", "launch vs code", "open visual studio code", "launch visual studio code", "open vscode", "launch vscode", "open code editor"],
            "Launches Visual Studio Code.",
            svc,
        ),
        OpenApplicationCommand(
            "notepad",
            ["open notepad", "launch notepad", "start notepad", "open text editor"],
            "Launches Notepad text editor.",
            svc,
        ),
        OpenApplicationCommand(
            "calculator",
            ["open calculator", "launch calculator", "open calc", "start calculator"],
            "Launches Calculator.",
            svc,
        ),
        OpenApplicationCommand(
            "explorer",
            ["open file explorer", "open explorer", "open files", "open my computer"],
            "Launches File Explorer.",
            svc,
        ),
        OpenApplicationCommand(
            "whatsapp",
            ["open whatsapp", "launch whatsapp", "start whatsapp"],
            "Launches WhatsApp Desktop or WhatsApp Web.",
            svc,
        ),
        OpenApplicationCommand(
            "spotify",
            ["open spotify", "launch spotify", "start spotify"],
            "Launches Spotify Desktop or Spotify Web.",
            svc,
        ),
        WhatsAppChatCommand(confirmation_service=conf, launcher_service=svc),
    ]
