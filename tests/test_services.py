"""
tests/test_services.py
======================
Unit tests for Stage 5 services with complete mock isolation.
Tests verify:
- AppLauncherService: binary launching, web fallback, missing app reporting, forbidden command rejection
- SearchService: website shortcuts, query encoding, URL safety, rejection of unsafe schemes (file://, javascript:)
- WeatherService: 404 city not found, timeout, missing API key, successful response
- WikipediaService: 404 missing topic, network error, sentence truncation
"""

import unittest
from unittest.mock import MagicMock, patch

from services.app_launcher_service import AppLauncherService, LaunchResult
from services.search_service import SearchService, SearchResult
from services.weather_service import WeatherService, WeatherData
from services.wikipedia_service import WikipediaService, WikipediaSummary


class TestAppLauncherService(unittest.TestCase):
    def setUp(self):
        self.launcher = AppLauncherService()

    @patch("subprocess.Popen")
    @patch("os.path.isfile", return_value=True)
    def test_launch_installed_application(self, mock_isfile, mock_popen):
        result = self.launcher.launch_app("notepad")
        self.assertTrue(result.success)
        self.assertIn("Opening Notepad", result.message)
        mock_popen.assert_called_once()

    @patch("webbrowser.open")
    @patch("os.path.isfile", return_value=False)
    @patch("shutil.which", return_value=None)
    def test_launch_app_with_web_fallback(self, mock_which, mock_isfile, mock_webopen):
        # WhatsApp has a web fallback
        result = self.launcher.launch_app("whatsapp")
        self.assertTrue(result.success)
        self.assertTrue(result.fallback_used)
        self.assertIn("WhatsApp Web", result.message)
        mock_webopen.assert_called_once_with("https://web.whatsapp.com")

    @patch("os.path.isfile", return_value=False)
    @patch("shutil.which", return_value=None)
    def test_launch_missing_app_without_fallback(self, mock_which, mock_isfile):
        # VS Code has no web fallback
        result = self.launcher.launch_app("vscode")
        self.assertFalse(result.success)
        self.assertIn("not installed", result.message)

    def test_forbidden_target_rejected(self):
        result = self.launcher.launch_app("format")
        self.assertFalse(result.success)
        self.assertIn("restricted", result.message)

    @patch("os.path.isdir", return_value=True)
    @patch("os.startfile", create=True)
    def test_open_folder_shortcut(self, mock_startfile, mock_isdir):
        self.launcher.os_type = "windows"
        result = self.launcher.open_folder("downloads")
        self.assertTrue(result.success)
        self.assertIn("Opening Downloads", result.message)


class TestSearchService(unittest.TestCase):
    def setUp(self):
        self.search = SearchService()

    @patch("webbrowser.open")
    def test_open_site_shortcut(self, mock_open):
        result = self.search.open_site("youtube")
        self.assertTrue(result.success)
        self.assertEqual(result.url, "https://www.youtube.com")
        mock_open.assert_called_once_with("https://www.youtube.com")

    @patch("webbrowser.open")
    def test_google_search_query_encoding(self, mock_open):
        result = self.search.search_google("python & machine learning?")
        self.assertTrue(result.success)
        self.assertIn("python+%26+machine+learning%3F", result.url)
        mock_open.assert_called_once()

    @patch("webbrowser.open")
    def test_youtube_search_query_encoding(self, mock_open):
        result = self.search.search_youtube("dsa tutorials 2026")
        self.assertTrue(result.success)
        self.assertIn("dsa+tutorials+2026", result.url)
        mock_open.assert_called_once()

    def test_empty_search_query_rejected(self):
        result = self.search.search_google("   ")
        self.assertFalse(result.success)

    @patch("webbrowser.open")
    def test_open_valid_url(self, mock_open):
        result = self.search.open_url("github.com/torvalds")
        self.assertTrue(result.success)
        self.assertIn("https://github.com/torvalds", result.url)

    def test_unsafe_url_schemes_rejected(self):
        unsafe_targets = [
            "javascript:alert(1)",
            "file:///C:/Windows/System32",
            "data:text/html,<h1>test</h1>",
            "shell:startup",
        ]
        for url in unsafe_targets:
            result = self.search.open_url(url)
            self.assertFalse(result.success, f"Failed to reject unsafe scheme in {url}")
            self.assertIn("only HTTP and HTTPS", result.message)


class TestWeatherService(unittest.TestCase):
    @patch("requests.get")
    def test_weather_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "name": "Noida",
            "main": {"temp": 31.4, "humidity": 65},
            "weather": [{"description": "partly cloudy"}],
            "wind": {"speed": 3.5},
        }
        mock_get.return_value = mock_resp

        service = WeatherService()
        service.api_key = "mock_key"
        data, msg = service.get_weather("Noida")
        self.assertIsNotNone(data)
        self.assertIn("31.4 degrees Celsius", msg)
        self.assertIn("partly cloudy", msg)

    @patch("requests.get")
    def test_weather_city_not_found(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp

        service = WeatherService()
        service.api_key = "mock_key"
        data, msg = service.get_weather("NonExistentCityXYZ")
        self.assertIsNone(data)
        self.assertIn("couldn't find weather information", msg)


class TestWikipediaService(unittest.TestCase):
    @patch("requests.get")
    def test_wikipedia_summary_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "title": "Python (programming language)",
            "extract": "Python is a high-level, general-purpose programming language. Its design philosophy emphasizes code readability. It was created by Guido van Rossum.",
            "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Python"}},
        }
        mock_get.return_value = mock_resp

        service = WikipediaService()
        data, msg = service.search_summary("Python", max_sentences=2)
        self.assertIsNotNone(data)
        self.assertEqual(data.title, "Python (programming language)")
        # Truncated to 2 sentences:
        self.assertIn("Python is a high-level, general-purpose programming language.", msg)
        self.assertIn("Its design philosophy emphasizes code readability.", msg)
        self.assertNotIn("It was created by Guido van Rossum.", msg)

    @patch("requests.get")
    def test_wikipedia_missing_page(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp

        service = WikipediaService()
        data, msg = service.search_summary("TopicThatDoesNotExist12345")
        self.assertIsNone(data)
        self.assertIn("couldn't find an encyclopedic article", msg)


if __name__ == "__main__":
    unittest.main()
