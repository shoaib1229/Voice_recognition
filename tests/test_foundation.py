"""
tests/test_foundation.py
========================
Verification tests for Stage 2 foundation components:
- Configuration (settings)
- App Registry & Security allowlists
- Helpers & Intent Normalization
- Command Registry & BaseCommand
- ConfirmationService
- Logging infrastructure
- Session Context
"""

import logging
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from config.settings import settings, Settings, _build_settings
from config.app_registry import ALLOWED_APPS, ALLOWED_SITES, ALLOWED_FOLDERS, FORBIDDEN_KEYWORDS
from utils.helpers import normalize_text, keyword_score, contains_forbidden, extract_after
from utils.normalizer import normalize_intent
from commands.base import BaseCommand, CommandResult, unknown_command_result
from commands.registry import CommandRegistry
from services.confirmation_service import ConfirmationService
from core.context import Context


class TestFoundationSettings(unittest.TestCase):
    def test_settings_loaded(self):
        self.assertIsInstance(settings, Settings)
        self.assertTrue(hasattr(settings, "OPENWEATHER_API_KEY"))
        for removed in ("AI_PROVIDER", "OPENAI_API_KEY", "GEMINI_API_KEY", "EXPLABS_API_KEY"):
            self.assertFalse(hasattr(settings, removed))
        self.assertIsInstance(settings.PROJECT_ROOT, Path)

    def test_build_settings_ignores_removed_provider_variables(self):
        with patch.dict(os.environ, {"AI_PROVIDER": "openai", "OPENAI_API_KEY": "dummy"}, clear=False):
            configured = _build_settings()
        self.assertFalse(hasattr(configured, "AI_PROVIDER"))
        self.assertFalse(hasattr(configured, "OPENAI_API_KEY"))


class TestAppRegistryAndSecurity(unittest.TestCase):
    def test_allowlists_not_empty(self):
        self.assertIn("chrome", ALLOWED_APPS)
        self.assertIn("whatsapp", ALLOWED_APPS)
        self.assertIn("vscode", ALLOWED_APPS)
        self.assertIn("youtube", ALLOWED_SITES)
        self.assertIn("downloads", ALLOWED_FOLDERS)

    def test_forbidden_keywords(self):
        self.assertIn("format", FORBIDDEN_KEYWORDS)
        self.assertIn("delete", FORBIDDEN_KEYWORDS)
        self.assertTrue(contains_forbidden("please format now", FORBIDDEN_KEYWORDS))
        self.assertFalse(contains_forbidden("open chrome", FORBIDDEN_KEYWORDS))


class TestHelpersAndNormalizer(unittest.TestCase):
    def test_normalize_text(self):
        self.assertEqual(normalize_text("  Open Chrome!  "), "open chrome")

    def test_normalize_intent_strips_polite(self):
        self.assertEqual(normalize_intent("please open chrome for me"), "open chrome")
        self.assertEqual(normalize_intent("can you launch vs code"), "open vs code")

    def test_keyword_score(self):
        score = keyword_score("open google chrome", ["open", "chrome"])
        self.assertEqual(score, 1.0)


class TestCommandRegistry(unittest.TestCase):
    def test_registry_registration_and_scoring(self):
        class DummyCommand(BaseCommand):
            name = "dummy.test"
            aliases = ["test this", "dummy test"]
            priority = 10
            description = "A dummy test command"

            def execute(self, params, context):
                return CommandResult.ok(self.name, "Test executed")

        registry = CommandRegistry()
        cmd = DummyCommand()
        registry.register(cmd)
        results = registry.find("dummy test")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0].command.name, "dummy.test")


class TestConfirmationService(unittest.TestCase):
    def test_auto_confirm_mode(self):
        service = ConfirmationService(auto_confirm_for_testing=True)
        self.assertTrue(service.confirm("delete temporary cache"))

    def test_custom_handler_confirmed(self):
        service = ConfirmationService(prompt_handler=lambda action: True)
        self.assertTrue(service.confirm("send message"))

    def test_custom_handler_denied(self):
        service = ConfirmationService(prompt_handler=lambda action: False)
        self.assertFalse(service.confirm("send message"))

    def test_custom_handler_exception_safe(self):
        def buggy_handler(action):
            raise RuntimeError("UI crashed")

        service = ConfirmationService(prompt_handler=buggy_handler)
        # Should gracefully fail to False (deny)
        self.assertFalse(service.confirm("dangerous action"))


class TestContext(unittest.TestCase):
    def test_context_recording(self):
        ctx = Context(voice_mode=False)
        self.assertEqual(ctx.turn_count, 0)
        ctx.record_turn("open chrome", "app.open_chrome", "Opening Chrome.", True)
        self.assertEqual(ctx.turn_count, 1)
        self.assertEqual(ctx.last_command_name, "app.open_chrome")


if __name__ == "__main__":
    unittest.main()
