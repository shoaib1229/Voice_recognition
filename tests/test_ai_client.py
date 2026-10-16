"""Regression guard ensuring no remote chat client remains available."""

import unittest

import ai.client as client_module


class TestRetiredChatClient(unittest.TestCase):
    def test_client_module_has_no_provider_client_or_request_function(self):
        self.assertFalse(hasattr(client_module, "AstraClient"))
        self.assertFalse(hasattr(client_module, "OpenAI"))
        self.assertFalse(hasattr(client_module, "chat_completion"))


if __name__ == "__main__":
    unittest.main()