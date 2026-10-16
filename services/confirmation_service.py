"""
services/confirmation_service.py
================================
ConfirmationService abstraction for guarding sensitive or externally-visible actions.

Purpose:
- Ensures destructive actions (e.g. file deletion, system shutdown) or
  externally-visible actions (e.g. sending a WhatsApp message or email)
  cannot occur without explicit, verified user consent.
- Provides a unified confirmation interface that works seamlessly across:
    1. CLI / Text mode (interactive terminal prompt)
    2. Voice mode (spoken prompt + listened confirmation)
    3. GUI mode (modal dialog prompt)
    4. Headless / Automated test mode (mockable callback or default rejection)

Security Rules:
- The default response is ALWAYS False (deny).
- Timeout or empty input defaults to False (deny).
- Actions requiring confirmation are logged to the audit log.
"""

from __future__ import annotations

from typing import Callable, Optional

from utils.logger import get_logger

logger = get_logger(__name__)


class ConfirmationService:
    """
    Manages user confirmation workflows for sensitive or high-impact actions.

    Usage:
        service = ConfirmationService()
        if service.confirm("Send WhatsApp message to Rahul saying 'I will be late'"):
            # proceed with sending
        else:
            # action cancelled
    """

    def __init__(
        self,
        prompt_handler: Optional[Callable[[str], bool]] = None,
        auto_confirm_for_testing: bool = False,
    ) -> None:
        """
        Args:
            prompt_handler: Optional custom callback that takes `action_description: str`
                            and returns `bool`. If None, falls back to standard CLI input.
            auto_confirm_for_testing: If True, automatically confirms all requests.
                                     MUST ONLY be used in automated tests.
        """
        self._prompt_handler = prompt_handler
        self._auto_confirm = auto_confirm_for_testing

    def set_prompt_handler(self, handler: Optional[Callable[[str], bool]]) -> None:
        """Configure a custom prompt handler (e.g., for GUI or voice integration)."""
        self._prompt_handler = handler

    def confirm(self, action_description: str) -> bool:
        """
        Request explicit user confirmation for *action_description*.

        Returns:
            True if the user confirmed; False if denied, timed out, or cancelled.
        """
        logger.info("Confirmation requested for action: %s", action_description)

        if self._auto_confirm:
            logger.warning("Auto-confirm active (test mode). Action '%s' automatically approved.", action_description)
            return True

        if self._prompt_handler is not None:
            try:
                result = bool(self._prompt_handler(action_description))
                logger.info("Custom prompt handler returned: %s for '%s'", result, action_description)
                return result
            except Exception as exc:
                logger.error("Error in custom confirmation handler for '%s': %s", action_description, exc)
                return False

        # Default fallback: interactive CLI prompt
        return self._cli_prompt(action_description)

    def _cli_prompt(self, action_description: str) -> bool:
        """Standard CLI confirmation prompt with safe defaults."""
        try:
            print(f"\n[SECURITY CONFIRMATION REQUIRED]")
            print(f"Action: {action_description}")
            response = input("Do you confirm this action? [y/N]: ").strip().lower()
            confirmed = response in ("y", "yes")
            if confirmed:
                logger.info("User confirmed action: %s", action_description)
            else:
                logger.info("User denied or cancelled action: %s", action_description)
            return confirmed
        except (KeyboardInterrupt, EOFError):
            print("\nAction cancelled.")
            logger.warning("Confirmation prompt aborted by user signal for: %s", action_description)
            return False
        except Exception as exc:
            logger.error("Unexpected error in CLI confirmation prompt: %s", exc)
            return False
