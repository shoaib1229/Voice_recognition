"""
tests/test_commands.py
======================
Unit tests for all Stage 5 modular commands using build_default_command_registry.
Tests verify:
- Deterministic routing for application commands and aliases (Chrome, VS Code, WhatsApp, etc.)
- Web search parameter extraction (Google, YouTube, GitHub)
- Folder shortcut execution
- System commands (Time, Date)
- Weather command city extraction
- Wikipedia command topic extraction
- WhatsApp chat workflow with confirmation approval and denial
- Unknown command fallback
"""

import unittest
from unittest.mock import MagicMock, patch

from commands import build_default_command_registry
from core.context import Context
from services.app_launcher_service import AppLauncherService, LaunchResult
from services.confirmation_service import ConfirmationService
from services.search_service import SearchService, SearchResult
from services.weather_service import WeatherService, WeatherData
from services.wikipedia_service import WikipediaService, WikipediaSummary


class TestCommands(unittest.TestCase):
    def setUp(self):
        self.mock_launcher = MagicMock(spec=AppLauncherService)
        self.mock_search = MagicMock(spec=SearchService)
        self.mock_weather = MagicMock(spec=WeatherService)
        self.mock_wiki = MagicMock(spec=WikipediaService)
        self.mock_confirmation = MagicMock(spec=ConfirmationService)

        self.registry = build_default_command_registry(
            launcher=self.mock_launcher,
            search=self.mock_search,
            weather=self.mock_weather,
            wiki=self.mock_wiki,
            confirmation=self.mock_confirmation,
        )
        self.context = Context(voice_mode=False)

    def test_open_chrome_variations(self):
        variations = [
            "open chrome",
            "launch chrome",
            "start chrome",
            "please open chrome",
            "open google chrome",
        ]
        self.mock_launcher.launch_app.return_value = LaunchResult(True, "Opening Google Chrome.", "chrome.exe")

        for phrase in variations:
            scored = self.registry.find(phrase)
            self.assertGreater(len(scored), 0, f"Failed to match: {phrase}")
            top_cmd = scored[0].command
            self.assertEqual(top_cmd.name, "app.open_chrome", f"Failed for phrase: {phrase}")

            res = top_cmd.execute({}, self.context)
            self.assertTrue(res.success)
            self.mock_launcher.launch_app.assert_called_with("chrome")

    def test_conversational_chrome_request_is_routed_to_allowlisted_app(self):
        scored = self.registry.find("Could you open Chrome for me?")
        self.assertTrue(scored)
        self.assertEqual(scored[0].command.name, "app.open_chrome")

    def test_open_vscode_variations(self):
        variations = [
            "open vs code",
            "launch vscode",
            "open code editor",
            "open visual studio code",
        ]
        self.mock_launcher.launch_app.return_value = LaunchResult(True, "Opening Visual Studio Code.", "code.exe")

        for phrase in variations:
            scored = self.registry.find(phrase)
            self.assertGreater(len(scored), 0, f"Failed to match: {phrase}")
            top_cmd = scored[0].command
            self.assertEqual(top_cmd.name, "app.open_vscode", f"Failed for phrase: {phrase}")

    def test_search_google_query_extraction(self):
        self.mock_search.search_google.return_value = SearchResult(True, "Searching Google.", "https://google.com")
        scored = self.registry.find("search google for python jobs")
        self.assertGreater(len(scored), 0)
        cmd = scored[0].command
        self.assertEqual(cmd.name, "web.search_google")

        params = cmd.extract_params("search google for python jobs")
        self.assertEqual(params.get("query"), "python jobs")

        res = cmd.execute(params, self.context)
        self.assertTrue(res.success)
        self.mock_search.search_google.assert_called_with("python jobs")

    def test_search_youtube_query_extraction(self):
        self.mock_search.search_youtube.return_value = SearchResult(True, "Searching YouTube.", "https://youtube.com")

        # Regression tests including exact prompt cases
        test_cases = [
            ("search youtube for dsa tutorials", "dsa tutorials"),
            ("find dsa tutorials on youtube", "dsa tutorials"),
            ("play relaxing music on youtube", "relaxing music"),
            ("Play Believer", "Believer"),
            ("Play song Believer on YouTube", "Believer"),
            ("Can you please open a song on YouTube?", "song"),
            ("Play Despacito", "Despacito"),
        ]

        for phrase, expected_query in test_cases:
            scored = self.registry.find(phrase)
            self.assertGreater(len(scored), 0, f"Failed to match {phrase}")
            cmd = scored[0].command
            self.assertEqual(cmd.name, "web.search_youtube", f"Wrong command for {phrase}")
            params = cmd.extract_params(phrase)
            self.assertEqual(params.get("query"), expected_query, f"Extracted query mismatch for {phrase}")

    def test_natural_youtube_search_keeps_the_full_topic(self):
        cmd = self.registry.find("Search YouTube for Python tutorials.")[0].command
        self.assertEqual(cmd.name, "web.search_youtube")
        self.assertEqual(cmd.extract_params("Search YouTube for Python tutorials."), {"query": "python tutorials"})

    def test_regression_play_believer(self):
        scored = self.registry.find("Play Believer")
        self.assertGreater(len(scored), 0)
        cmd = scored[0].command
        self.assertEqual(cmd.name, "web.search_youtube")
        params = cmd.extract_params("Play Believer")
        self.assertEqual(params.get("query"), "Believer")

    def test_regression_play_song_believer_on_youtube(self):
        scored = self.registry.find("Play song Believer on YouTube")
        self.assertGreater(len(scored), 0)
        cmd = scored[0].command
        self.assertEqual(cmd.name, "web.search_youtube")
        params = cmd.extract_params("Play song Believer on YouTube")
        self.assertEqual(params.get("query"), "Believer")
        # Ensure it does NOT extract "song believer"
        self.assertNotEqual(params.get("query").lower(), "song believer")

    def test_regression_can_you_please_open_a_song_on_youtube(self):
        scored = self.registry.find("Can you please open a song on YouTube?")
        self.assertGreater(len(scored), 0)
        cmd = scored[0].command
        self.assertEqual(cmd.name, "web.search_youtube")
        params = cmd.extract_params("Can you please open a song on YouTube?")
        self.assertEqual(params.get("query"), "song")

    def test_regression_play_despacito(self):
        scored = self.registry.find("Play Despacito")
        self.assertGreater(len(scored), 0)
        cmd = scored[0].command
        self.assertEqual(cmd.name, "web.search_youtube")
        params = cmd.extract_params("Play Despacito")
        self.assertEqual(params.get("query"), "Despacito")

    def test_open_folder_command(self):
        self.mock_launcher.open_folder.return_value = LaunchResult(True, "Opening Downloads.", "C:/Downloads")
        scored = self.registry.find("open downloads")
        self.assertGreater(len(scored), 0)
        cmd = scored[0].command
        self.assertEqual(cmd.name, "folder.downloads")

        res = cmd.execute({}, self.context)
        self.assertTrue(res.success)
        self.mock_launcher.open_folder.assert_called_with("downloads")

    def test_system_time_command(self):
        scored = self.registry.find("what time is it")
        self.assertGreater(len(scored), 0)
        cmd = scored[0].command
        self.assertEqual(cmd.name, "system.get_time")

        res = cmd.execute({}, self.context)
        self.assertTrue(res.success)
        self.assertIn("The current time is", res.spoken_response)

    def test_system_date_command(self):
        scored = self.registry.find("what is today's date")
        self.assertGreater(len(scored), 0)
        cmd = scored[0].command
        self.assertEqual(cmd.name, "system.get_date")

        res = cmd.execute({}, self.context)
        self.assertTrue(res.success)
        self.assertIn("Today is", res.spoken_response)

    def test_weather_command_city_extraction(self):
        self.mock_weather.get_weather.return_value = (
            WeatherData("Noida", 31.0, "clear", 60, 2.0, "Currently in Noida, 31C."),
            "Currently in Noida, 31C.",
        )
        scored = self.registry.find("what is the weather in noida")
        self.assertGreater(len(scored), 0)
        cmd = scored[0].command
        self.assertEqual(cmd.name, "info.weather")

        params = cmd.extract_params("what is the weather in noida")
        self.assertEqual(params.get("city"), "noida")

        res = cmd.execute(params, self.context)
        self.assertTrue(res.success)
        self.mock_weather.get_weather.assert_called_with("noida")

    def test_wikipedia_command_topic_extraction(self):
        self.mock_wiki.search_summary.return_value = (
            WikipediaSummary("Alan Turing", "Alan Turing was a mathematician.", "https://en.wikipedia.org/wiki/Alan_Turing"),
            "Alan Turing was a mathematician.",
        )
        scored = self.registry.find("who is alan turing")
        self.assertGreater(len(scored), 0)
        cmd = scored[0].command
        self.assertEqual(cmd.name, "info.wikipedia")

        params = cmd.extract_params("who is alan turing")
        self.assertEqual(params.get("topic"), "alan turing")

        res = cmd.execute(params, self.context)
        self.assertTrue(res.success)
        self.mock_wiki.search_summary.assert_called_with("alan turing")

    @patch("webbrowser.open")
    def test_whatsapp_chat_workflow_with_confirmation_denial(self, mock_webopen):
        # User denies confirmation
        self.mock_confirmation.confirm.return_value = False

        scored = self.registry.find("open whatsapp chat with Rahul")
        self.assertGreater(len(scored), 0)
        cmd = scored[0].command
        self.assertEqual(cmd.name, "app.whatsapp_chat")

        params = cmd.extract_params("open whatsapp chat with Rahul")
        self.assertEqual(params.get("contact").lower(), "rahul")

        res = cmd.execute(params, self.context)
        self.assertTrue(res.success)
        self.assertIn("cancelled", res.spoken_response)
        # Browser must NOT be opened when confirmation is denied
        mock_webopen.assert_not_called()

    @patch("webbrowser.open")
    def test_whatsapp_chat_workflow_with_confirmation_approval(self, mock_webopen):
        # User approves confirmation
        self.mock_confirmation.confirm.return_value = True

        cmd = [c.command for c in self.registry.find("open whatsapp chat with Rahul") if c.command.name == "app.whatsapp_chat"][0]
        params = cmd.extract_params("open whatsapp chat with Rahul")

        res = cmd.execute(params, self.context)
        self.assertTrue(res.success)
        self.assertIn("Opening WhatsApp chat with Rahul", res.spoken_response)
        mock_webopen.assert_called_once()

    @patch("webbrowser.open")
    def test_whatsapp_message_parsing_and_truthful_response(self, mock_webopen):
        self.mock_confirmation.confirm.return_value = True

        phrase = "send whatsapp message to Sarah saying see you soon"
        scored = self.registry.find(phrase)
        self.assertGreater(len(scored), 0)
        cmd = scored[0].command
        self.assertEqual(cmd.name, "app.whatsapp_chat")

        params = cmd.extract_params(phrase)
        self.assertEqual(params.get("contact").lower(), "sarah")
        self.assertEqual(params.get("message"), "see you soon")

        res = cmd.execute(params, self.context)
        self.assertTrue(res.success)
        # Verify Nova never claims the message was already sent!
        self.assertIn("Opening WhatsApp chat with Sarah with prefilled message", res.spoken_response)
        self.assertIn("Please click send in WhatsApp", res.spoken_response)
        self.assertNotIn("Message sent to", res.spoken_response)
        mock_webopen.assert_called_once()

    @patch("os.system")
    def test_shutdown_confirmation_denial(self, mock_system):
        self.mock_confirmation.confirm.return_value = False
        scored = self.registry.find("shutdown my computer")
        self.assertGreater(len(scored), 0)
        cmd = scored[0].command
        self.assertEqual(cmd.name, "system.shutdown")

        res = cmd.execute({}, self.context)
        self.assertTrue(res.success)
        self.assertIn("Shutdown cancelled", res.spoken_response)
        mock_system.assert_not_called()

    @patch("os.system")
    def test_shutdown_confirmation_approval(self, mock_system):
        self.mock_confirmation.confirm.return_value = True
        scored = self.registry.find("shutdown my laptop")
        self.assertGreater(len(scored), 0)
        cmd = scored[0].command
        self.assertEqual(cmd.name, "system.shutdown")

        res = cmd.execute({}, self.context)
        self.assertTrue(res.success)
        self.assertIn("Shutting down your computer in 15 seconds", res.spoken_response)
        mock_system.assert_called_once()
        self.assertIn("shutdown /s /t 15", mock_system.call_args[0][0])

    @patch("os.system")
    def test_restart_confirmation_denial_and_approval(self, mock_system):
        # 1. Deny
        self.mock_confirmation.confirm.return_value = False
        scored = self.registry.find("restart my computer")
        self.assertGreater(len(scored), 0)
        cmd = scored[0].command
        self.assertEqual(cmd.name, "system.restart")

        res_deny = cmd.execute({}, self.context)
        self.assertTrue(res_deny.success)
        self.assertIn("Restart cancelled", res_deny.spoken_response)
        mock_system.assert_not_called()

        # 2. Approve
        self.mock_confirmation.confirm.return_value = True
        res_ok = cmd.execute({}, self.context)
        self.assertTrue(res_ok.success)
        self.assertIn("Restarting your computer in 15 seconds", res_ok.spoken_response)
        mock_system.assert_called_once()
        self.assertIn("shutdown /r /t 15", mock_system.call_args[0][0])

    @patch("os.system")
    def test_cancel_shutdown_command(self, mock_system):
        scored = self.registry.find("cancel shutdown")
        self.assertGreater(len(scored), 0)
        cmd = scored[0].command
        self.assertEqual(cmd.name, "system.cancel_shutdown")

        res = cmd.execute({}, self.context)
        self.assertTrue(res.success)
        self.assertIn("cancelled", res.spoken_response)
        mock_system.assert_called_once_with("shutdown /a")

    def test_unknown_command_returns_empty_or_zero_score(self):
        scored = self.registry.find("xyz abc do a backflip")
        # Either no match or score 0
        top_matches = [s for s in scored if s.score > 0.5]
        self.assertEqual(len(top_matches), 0)


if __name__ == "__main__":
    unittest.main()
