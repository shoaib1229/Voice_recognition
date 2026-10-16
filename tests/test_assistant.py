"""Integration checks for local command routing and honest offline replies."""

import unittest
from unittest.mock import MagicMock

from ai.conversation import ConversationManager
from core.assistant import Assistant
from services.app_launcher_service import AppLauncherService, LaunchResult
from services.confirmation_service import ConfirmationService
from services.search_service import SearchService, SearchResult
from services.weather_service import WeatherService
from services.wikipedia_service import WikipediaService


class TestAssistantIntegration(unittest.TestCase):
    def setUp(self):
        self.launcher = MagicMock(spec=AppLauncherService)
        self.search = MagicMock(spec=SearchService)
        self.weather = MagicMock(spec=WeatherService)
        self.wiki = MagicMock(spec=WikipediaService)
        self.confirmation = MagicMock(spec=ConfirmationService)
        self.speaker = MagicMock()
        self.assistant = Assistant(
            launcher=self.launcher, search=self.search, weather=self.weather,
            wiki=self.wiki, confirmation=self.confirmation, speaker=self.speaker,
        )

    def test_supported_commands_remain_registry_routed(self):
        self.launcher.launch_app.return_value = LaunchResult(True, "Opening Chrome.", "chrome.exe")
        result = self.assistant.process_input("Open Chrome")
        self.assertEqual(result.command_name, "app.open_chrome")
        self.launcher.launch_app.assert_called_with("chrome")

    def test_web_search_remains_available(self):
        self.search.search_youtube.return_value = SearchResult(True, "Searching YouTube.", "https://youtube.com")
        result = self.assistant.process_input("Search YouTube for DSA tutorials")
        self.assertEqual(result.command_name, "web.search_youtube")
        self.search.search_youtube.assert_called_with("dsa tutorials")

    def test_time_and_date_remain_available(self):
        self.assertEqual(self.assistant.process_input("What time is it?").command_name, "system.get_time")
        self.assertEqual(self.assistant.process_input("What is today's date?").command_name, "system.get_date")

    def test_local_patterns_and_history(self):
        greeting = self.assistant.process_input("Hi, how are you?")
        thanks = self.assistant.process_input("Thank you!")
        self.assertEqual(greeting.command_name, "local.greeting")
        self.assertEqual(thanks.command_name, "local.thanks")
        self.assertEqual(self.assistant.conversation.history_length, 4)
        self.assertEqual(self.speaker.speak.call_count, 2)

    def test_unsupported_question_is_declined_honestly(self):
        result = self.assistant.process_input("Explain quantum computing")
        self.assertFalse(result.success)
        self.assertEqual(result.command_name, "local.unsupported")
        self.assertIn("can't answer that offline", result.spoken_response)
        self.assertIn("offline", result.error)

    def test_weather_failure_does_not_become_a_guessed_answer(self):
        self.weather.get_weather.return_value = (None, "Weather service is unavailable.")
        result = self.assistant.process_input("What is the weather in Delhi?")
        self.assertFalse(result.success)
        self.assertEqual(result.command_name, "info.weather")
        self.assertEqual(result.spoken_response, "Weather service is unavailable.")

    def test_wikipedia_failure_does_not_become_a_guessed_answer(self):
        self.wiki.search_summary.return_value = (None, "Wikipedia service is unavailable.")
        result = self.assistant.process_input("Who is Alan Turing?")
        self.assertFalse(result.success)
        self.assertEqual(result.command_name, "info.wikipedia")
        self.assertEqual(result.spoken_response, "Wikipedia service is unavailable.")

    def test_forbidden_actions_stay_blocked(self):
        result = self.assistant.process_input("Please format my hard drive")
        self.assertFalse(result.success)
        self.assertEqual(result.command_name, "security.forbidden")
        self.launcher.launch_app.assert_not_called()

    def test_exit_command_terminates_session(self):
        result = self.assistant.process_input("Goodbye Nova")
        self.assertTrue(result.success)
        self.assertTrue(self.assistant.context.should_exit)
        self.assertEqual(result.command_name, "control.exit")


if __name__ == "__main__":
    unittest.main()