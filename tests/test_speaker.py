"""
tests/test_speaker.py
=====================
Unit tests for Speaker with mock isolation (zero audio playback required).
Tests verify:
- Spoken text delivery in voice mode
- Text output in CLI mode
- Secret token redaction from output
- Graceful recovery when engine fails
- Stop method delegation
"""

import unittest
from unittest.mock import MagicMock, patch

from core.speaker import Speaker, prepare_speech_text


class TestSpeaker(unittest.TestCase):
    def setUp(self):
        self.mock_engine = MagicMock()
        self.speaker = Speaker(voice_mode=True, engine=self.mock_engine)

    def test_speak_in_voice_mode_calls_engine(self):
        self.speaker.speak("Hello from Nova.")
        self.mock_engine.say.assert_called_once_with("Hello from Nova.")
        self.mock_engine.runAndWait.assert_called_once()

    def test_speak_cleans_markdown_urls_and_code_for_tts(self):
        self.speaker.speak("## Result\nSee [the guide](https://example.com/path).\n```py\nprint('hi')\n```")
        spoken = self.mock_engine.say.call_args.args[0]
        self.assertIn("Result", spoken)
        self.assertIn("the guide", spoken)
        self.assertNotIn("https://", spoken)
        self.assertNotIn("/path", spoken)
        self.assertIn("included the code in the chat", spoken)
        self.assertNotIn("```", spoken)

    def test_long_speech_ends_at_sentence_and_points_to_full_chat_reply(self):
        text = "First sentence is complete. " + ("More words follow. " * 100)
        spoken = prepare_speech_text(text)

        self.assertLessEqual(len(spoken), 960)
        self.assertTrue(spoken.endswith("I’ve included the full response in the chat."))
        self.assertIn("First sentence is complete.", spoken)

    def test_speak_in_text_mode_does_not_call_engine(self):
        text_speaker = Speaker(voice_mode=False, engine=self.mock_engine)
        text_speaker.speak("Hello text mode.")
        self.mock_engine.say.assert_not_called()
        self.mock_engine.runAndWait.assert_not_called()

    def test_empty_string_does_nothing(self):
        self.speaker.speak("   ")
        self.mock_engine.say.assert_not_called()

    def test_secret_token_is_redacted(self):
        secret_text = "Here is your key: xpl_b99a7d819a17f0134d471327c90d610be32d3009"
        self.speaker.speak(secret_text)
        called_arg = self.mock_engine.say.call_args[0][0]
        self.assertNotIn("xpl_b99a7d819a17f0134d471327c90d610be32d3009", called_arg)
        self.assertIn("[REDACTED_KEY]", called_arg)

    def test_engine_runtime_failure_is_handled_gracefully(self):
        self.mock_engine.say.side_effect = RuntimeError("COM audio driver crashed")
        # Must not raise:
        self.speaker.speak("Testing driver failure.")
        self.mock_engine.stop.assert_called()

    def test_stop_delegates_to_engine(self):
        self.speaker.stop()
        self.mock_engine.stop.assert_called_once()


if __name__ == "__main__":
    unittest.main()
