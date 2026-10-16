"""Tests for local conversation bookkeeping and rule-based responses."""

import unittest

from ai.conversation import ConversationManager
from ai.intent_parser import IntentParser
from core.local_fallback import LocalFallbackHandler


class TestConversationHistory(unittest.TestCase):
    def test_local_history_is_bounded_and_resettable(self):
        history = ConversationManager(max_history=2)
        history.record_turn("hi", "hello")
        history.record_turn("thanks", "welcome")
        history.record_turn("help", "commands")
        self.assertEqual(history.history_length, 4)
        self.assertEqual(len(history._history), 2)
        history.clear()
        self.assertEqual(history.history_length, 0)

    def test_intent_parser_never_invents_or_executes_actions(self):
        parsed = IntentParser().parse("open Chrome")
        self.assertFalse(parsed.is_action)
        self.assertIsNone(parsed.action_id)
        self.assertIsNone(parsed.conversational_reply)


class TestLocalFallback(unittest.TestCase):
    def setUp(self):
        self.handler = LocalFallbackHandler()

    def test_greetings_identity_help_and_canned_conversation(self):
        self.assertEqual(self.handler.respond("hello nova").command_name, "local.greeting")
        self.assertEqual(self.handler.respond("who are you").command_name, "local.identity")
        self.assertEqual(self.handler.respond("what can you do?").command_name, "local.help")
        self.assertEqual(self.handler.respond("tell me a joke").command_name, "local.joke")

    def test_time_and_date_are_available_locally(self):
        self.assertIn("current time is", self.handler.respond("tell me the time").spoken_response)
        self.assertIn("Today is", self.handler.respond("tell me the date").spoken_response)

    def test_unknown_question_is_declined_without_guessing(self):
        result = self.handler.respond("Who discovered penicillin?")
        self.assertFalse(result.success)
        self.assertEqual(result.command_name, "local.unsupported")
        self.assertIn("can't answer that offline", result.spoken_response)
        self.assertFalse(result.data["ai_generated"])


if __name__ == "__main__":
    unittest.main()