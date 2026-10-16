"""Tests for the text/voice application turn loop."""

import unittest
from unittest.mock import MagicMock

from app import NovaApp


class TestAppFlow(unittest.TestCase):
    def setUp(self):
        self.app = NovaApp(voice_mode=False)
        self.app.speaker = MagicMock()

    def test_exit_phrase_detection(self):
        for phrase in ("exit", "quit", "goodbye", "bye", "please exit"):
            self.assertTrue(self.app.is_exit_phrase(phrase))
        self.assertFalse(self.app.is_exit_phrase("what is the weather"))

    def test_process_turn_exit_stops_loop(self):
        self.assertFalse(self.app.process_turn("exit"))
        self.app.speaker.speak.assert_called_with("Goodbye! Have a great day.")

    def test_process_turn_uses_local_social_response(self):
        self.assertTrue(self.app.process_turn("hello nova"))
        self.app.speaker.speak.assert_called_once()
        self.assertIn("ready to help", self.app.speaker.speak.call_args.args[0])

    def test_process_turn_declines_unknown_questions(self):
        self.assertTrue(self.app.process_turn("Who discovered penicillin?"))
        self.assertIn("can't answer that offline", self.app.speaker.speak.call_args.args[0])

    def test_empty_input_returns_true_without_speech(self):
        self.assertTrue(self.app.process_turn("   "))
        self.app.speaker.speak.assert_not_called()


if __name__ == "__main__":
    unittest.main()