"""
tests/test_listener.py
======================
Unit tests for Listener with mock isolation (zero audio hardware required).
Tests verify:
- Speech recognition success
- Silence / timeout handling
- Unintelligible speech handling
- Network error handling
- Missing microphone hardware handling
- Ambient noise calibration
"""

import unittest
from unittest.mock import MagicMock, patch

import speech_recognition as sr

from core.listener import Listener


class TestListener(unittest.TestCase):
    def setUp(self):
        self.mock_recognizer = MagicMock(spec=sr.Recognizer)
        self.mock_microphone = MagicMock(spec=sr.Microphone)
        # Setup context manager on microphone
        self.mock_microphone.__enter__.return_value = self.mock_microphone
        self.mock_microphone.__exit__.return_value = None

        self.listener = Listener(
            recognizer=self.mock_recognizer,
            microphone=self.mock_microphone,
        )

    def test_successful_speech_recognition(self):
        self.mock_recognizer.listen.return_value = "mock_audio_data"
        self.mock_recognizer.recognize_google.return_value = "open chrome"

        result = self.listener.listen()
        self.assertEqual(result, "open chrome")
        self.mock_recognizer.listen.assert_called_once()
        self.mock_recognizer.recognize_google.assert_called_once_with("mock_audio_data", language=self.listener.language)
        self.mock_recognizer.listen.assert_called_once_with(
            self.mock_microphone,
            timeout=self.listener.timeout,
            phrase_time_limit=self.listener.phrase_time_limit,
        )

    def test_capture_calibrates_once_and_uses_listening_tuning(self):
        self.mock_recognizer.listen.return_value = "mock_audio_data"
        self.mock_recognizer.recognize_google.return_value = "hello"

        self.listener.listen()
        self.listener.listen()

        self.assertEqual(self.mock_recognizer.adjust_for_ambient_noise.call_count, 1)
        self.mock_recognizer.adjust_for_ambient_noise.assert_called_once_with(
            self.mock_microphone, duration=0.8
        )
        self.assertEqual(self.mock_recognizer.pause_threshold, 1.2)
        self.assertEqual(self.mock_recognizer.non_speaking_duration, 0.6)
        self.assertEqual(self.mock_recognizer.operation_timeout, self.listener.recognition_timeout)

    def test_blank_transcription_is_reported_as_unrecognized(self):
        self.mock_recognizer.listen.return_value = "mock_audio_data"
        self.mock_recognizer.recognize_google.return_value = "  "

        self.assertIsNone(self.listener.listen())
        self.assertEqual(self.listener.last_error, "unrecognized")

    def test_silence_timeout_returns_none(self):
        self.mock_recognizer.listen.side_effect = sr.WaitTimeoutError("Timed out")
        result = self.listener.listen()
        self.assertIsNone(result)
        self.assertEqual(self.listener.last_error, "timeout")

    def test_unintelligible_speech_returns_none(self):
        self.mock_recognizer.listen.return_value = "mock_audio_data"
        self.mock_recognizer.recognize_google.side_effect = sr.UnknownValueError()
        result = self.listener.listen()
        self.assertIsNone(result)
        self.assertEqual(self.listener.last_error, "unrecognized")

    def test_network_request_error_returns_none(self):
        self.mock_recognizer.listen.return_value = "mock_audio_data"
        self.mock_recognizer.recognize_google.side_effect = sr.RequestError("Connection failed")
        result = self.listener.listen()
        self.assertIsNone(result)
        self.assertEqual(self.listener.last_error, "network")

    def test_audio_device_error_returns_none(self):
        self.mock_recognizer.listen.side_effect = OSError("Device disconnected")
        result = self.listener.listen()
        self.assertIsNone(result)
        self.assertEqual(self.listener.last_error, "device")

    def test_success_clears_previous_error(self):
        self.listener.last_error = "network"
        self.mock_recognizer.listen.return_value = "mock_audio_data"
        self.mock_recognizer.recognize_google.return_value = "hello nova"

        self.assertEqual(self.listener.listen(), "hello nova")
        self.assertIsNone(self.listener.last_error)

    def test_missing_microphone_hardware_returns_none(self):
        with patch("speech_recognition.Microphone", side_effect=OSError("No default input device")):
            listener_no_mic = Listener(microphone=None)
            result = listener_no_mic.listen()
            self.assertIsNone(result)
            self.assertFalse(listener_no_mic.is_available())


if __name__ == "__main__":
    unittest.main()
