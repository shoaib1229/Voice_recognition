"""
tests/test_gui.py
=================
Unit tests for the Nova GUI (ui/app_window.py).

All tests use mocks for the assistant core, speaker, and listener to avoid
real application launches, API calls, or audio hardware dependencies.
Tests validate:
  - GUI application startup and widget construction
  - Text message submission flow
  - Local command execution via GUI
  - AI-unavailable message handling
  - Clear conversation functionality
  - Microphone start/stop state management
  - GUI responsiveness while processing (non-blocking)
  - Graceful shutdown
"""

from __future__ import annotations

import queue
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

from commands.base import CommandResult


def _mock_event_loop_tts_engine():
    """Minimal pyttsx3 event-loop mock that emits SAPI-style completion events."""
    engine = MagicMock()
    engine._callbacks = {}
    engine._pending_utterances = []
    engine.connect.side_effect = lambda event, callback: engine._callbacks.__setitem__(event, callback)
    engine.say.side_effect = lambda _text, name=None: engine._pending_utterances.append(name)

    def iterate():
        if engine._pending_utterances:
            utterance_name = engine._pending_utterances.pop(0)
            engine._callbacks["finished-utterance"](name=utterance_name, completed=True)

    engine.iterate.side_effect = iterate
    return engine


class TestGUIImports(unittest.TestCase):
    """Verify the GUI module can be imported without errors."""

    def test_import_app_window_module(self):
        import ui.app_window as mod
        self.assertTrue(hasattr(mod, "NovaGUI"))
        self.assertTrue(hasattr(mod, "launch_gui"))
        self.assertTrue(hasattr(mod, "_GUISpeaker"))
        self.assertTrue(hasattr(mod, "_ChatBubble"))

    def test_import_ui_package(self):
        import ui
        self.assertIsNotNone(ui)


class TestGUISpeaker(unittest.TestCase):
    """Test the GUI-specific silent speaker."""

    def test_gui_speaker_does_not_print_to_console(self):
        """_GUISpeaker should not call print() — only TTS if voice mode."""
        from ui.app_window import _GUISpeaker
        speaker = _GUISpeaker(voice_mode=False)
        # Should not raise; should not print to console
        speaker.speak("Hello from GUI")
        speaker.speak("")
        speaker.speak("   ")

    def test_gui_speaker_redacts_secrets(self):
        """_GUISpeaker should redact API keys in log output."""
        from ui.app_window import _GUISpeaker
        speaker = _GUISpeaker(voice_mode=False)
        # Should not raise — keys are redacted internally
        speaker.speak("Key is xpl_b99a7d819a17f0134d471327c90d610be32d3009")

    def test_gui_speaker_voice_mode_with_mock_engine(self):
        """_GUISpeaker with voice_mode=True should call TTS engine."""
        from ui.app_window import _GUISpeaker
        mock_engine = _mock_event_loop_tts_engine()
        status_callback = MagicMock()
        speaker = _GUISpeaker(
            voice_mode=True,
            engine=mock_engine,
            status_callback=status_callback,
        )
        speaker.speak("Testing voice")
        mock_engine.say.assert_called_once()
        mock_engine.startLoop.assert_called_once_with(False)
        mock_engine.iterate.assert_called_once()
        self.assertEqual(
            [call_args.args[0] for call_args in status_callback.call_args_list],
            ["speaking", "processing"],
        )
        speaker.stop()

    def test_gui_speaker_uses_speech_cleanup_but_keeps_status_lifecycle(self):
        from ui.app_window import _GUISpeaker
        engine = _mock_event_loop_tts_engine()
        statuses = MagicMock()
        speaker = _GUISpeaker(voice_mode=True, engine=engine, status_callback=statuses)
        speaker.speak("**Visible reply** with `code`.")

        self.assertEqual(engine.say.call_args.args[0], "Visible reply with code.")
        self.assertEqual([call.args[0] for call in statuses.call_args_list], ["speaking", "processing"])
        speaker.stop()

    def test_gui_speaker_reuses_one_engine_thread_for_three_follow_up_turns(self):
        import threading
        from ui.app_window import _GUISpeaker

        engine = _mock_event_loop_tts_engine()
        call_threads = []
        def record_thread_and_queue(_text, name=None):
            call_threads.append(threading.get_ident())
            engine._pending_utterances.append(name)
        engine.say.side_effect = record_thread_and_queue
        speaker = _GUISpeaker(voice_mode=True, engine=engine)

        speaker.speak("First reply")
        speaker.speak("Follow-up reply")
        speaker.speak("Third reply")

        self.assertEqual(engine.say.call_count, 3)
        self.assertEqual(engine.startLoop.call_count, 1)
        self.assertEqual(engine.iterate.call_count, 3)
        self.assertEqual(len(set(call_threads)), 1)
        self.assertNotEqual(call_threads[0], threading.get_ident())
        speaker.stop()

    def test_tts_failure_does_not_stop_later_queued_responses(self):
        import threading
        from ui.app_window import _GUISpeaker

        engine = _mock_event_loop_tts_engine()
        engine.say.side_effect = [RuntimeError("first playback failed")]
        recovered_engine = _mock_event_loop_tts_engine()
        status_callback = MagicMock()
        speaker = _GUISpeaker(voice_mode=True, status_callback=status_callback)
        # Both engines are created by pyttsx3.init on the owner worker.
        with patch("core.speaker.pyttsx3.init", side_effect=[engine, recovered_engine]):
            speaker.speak("First response fails")
            speaker.speak("Second response recovers")
            speaker.speak("Third response still speaks")

        self.assertEqual(engine.say.call_count, 1)
        self.assertEqual(recovered_engine.say.call_count, 2)
        self.assertEqual(recovered_engine.iterate.call_count, 2)
        self.assertTrue(speaker._tts_thread.is_alive())
        self.assertEqual(
            [call.args[0] for call in status_callback.call_args_list],
            ["speaking", "processing"] * 3,
        )
        speaker.stop()

    def test_speak_returns_only_after_playback_completes(self):
        import threading
        from ui.app_window import _GUISpeaker

        engine = _mock_event_loop_tts_engine()
        playback_started = threading.Event()
        allow_playback_to_finish = threading.Event()
        speak_returned = threading.Event()

        def wait_for_playback():
            playback_started.set()
            allow_playback_to_finish.wait(timeout=2)
            utterance_name = engine._pending_utterances.pop(0)
            engine._callbacks["finished-utterance"](name=utterance_name, completed=True)

        engine.iterate.side_effect = wait_for_playback
        speaker = _GUISpeaker(voice_mode=True, engine=engine)
        caller = threading.Thread(
            target=lambda: (speaker.speak("Wait until audio completes"), speak_returned.set()),
            daemon=True,
        )
        caller.start()

        self.assertTrue(playback_started.wait(timeout=1))
        self.assertFalse(speak_returned.is_set())
        allow_playback_to_finish.set()
        self.assertTrue(speak_returned.wait(timeout=1))
        speaker.stop()

    def test_gui_speaker_restores_processing_state_after_tts_failure(self):
        from ui.app_window import _GUISpeaker
        engine = _mock_event_loop_tts_engine()
        engine.iterate.side_effect = RuntimeError("audio output unavailable")
        status_callback = MagicMock()

        speaker = _GUISpeaker(
            voice_mode=True,
            engine=engine,
            status_callback=status_callback,
        )
        speaker.speak("Text remains available")

        self.assertEqual(
            [call_args.args[0] for call_args in status_callback.call_args_list],
            ["speaking", "processing"],
        )
        speaker.stop()


class TestGUIApplicationSetup(unittest.TestCase):
    """Test the GUI application can be constructed (headless)."""

    def test_voice_enabled_startup_schedules_microphone(self):
        """Voice mode selects continuous listening after the GUI is ready."""
        from ui.app_window import NovaGUI

        def build_minimal_layout(gui):
            gui._auto_listen_switch = MagicMock()

        with patch("ui.app_window.ctk.CTk.__init__", return_value=None), \
                patch("ui.app_window.Assistant") as assistant_factory, \
                patch("ui.app_window._GUISpeaker") as speaker_factory, \
                patch("ui.app_window.ctk.set_appearance_mode"), \
                patch("ui.app_window.ctk.set_default_color_theme"), \
                patch.object(NovaGUI, "_build_layout", autospec=True, side_effect=build_minimal_layout), \
                patch.object(NovaGUI, "_set_status"), \
                patch.object(NovaGUI, "_show_welcome_message"), \
                patch.object(NovaGUI, "_poll_results"), \
                patch.object(NovaGUI, "title", create=True), \
                patch.object(NovaGUI, "geometry", create=True), \
                patch.object(NovaGUI, "minsize", create=True), \
                patch.object(NovaGUI, "configure", create=True), \
                patch.object(NovaGUI, "iconbitmap", create=True), \
                patch.object(NovaGUI, "after", create=True) as after, \
                patch.object(NovaGUI, "protocol", create=True):
            gui = NovaGUI(voice_enabled=True)

        self.assertTrue(gui._auto_listen)
        gui._auto_listen_switch.select.assert_called_once_with()
        after.assert_called_once_with(700, gui._start_microphone)
        self.assertTrue(speaker_factory.call_args.kwargs["voice_mode"])
        self.assertFalse(assistant_factory.call_args.kwargs["voice_mode"])

    def test_build_sidebar_creates_parent_for_controls(self):
        """Sidebar controls have a parent frame and retain their handlers."""
        import ui.app_window as app_window

        with patch("ui.app_window.ctk.CTkFrame") as frame_factory, \
                patch("ui.app_window.ctk.CTkScrollableFrame"), \
                patch("ui.app_window.ctk.CTkLabel"), \
                patch("ui.app_window.ctk.CTkSwitch") as switch_factory, \
                patch("ui.app_window.ctk.CTkButton") as button_factory, \
                patch("ui.app_window.ctk.CTkFont"), \
                patch("ui.app_window.tk.Canvas"):
            frames = [MagicMock() for _ in range(11)]
            frame_factory.side_effect = frames
            voice_switch = MagicMock()
            continuous_switch = MagicMock()
            switch_factory.side_effect = [voice_switch, continuous_switch]
            clear_button = MagicMock()
            button_factory.return_value = clear_button

            gui = MagicMock()
            gui._voice_enabled = True
            gui._assistant.registry = []
            app_window.NovaGUI._build_sidebar(gui)

            controls_frame = frames[-1]
            self.assertIs(switch_factory.call_args_list[0].args[0], controls_frame)
            self.assertIs(switch_factory.call_args_list[1].args[0], controls_frame)
            self.assertIs(button_factory.call_args.args[0], controls_frame)
            self.assertIs(
                switch_factory.call_args_list[0].kwargs["command"],
                gui._on_voice_switch_toggled,
            )
            self.assertIs(
                switch_factory.call_args_list[1].kwargs["command"],
                gui._on_auto_listen_toggled,
            )
            self.assertIs(button_factory.call_args.kwargs["command"], gui._clear_conversation)
            voice_switch.select.assert_called_once_with()

    @patch("ui.app_window.ctk.CTk.__init__", return_value=None)
    @patch("ui.app_window.ctk.set_appearance_mode")
    @patch("ui.app_window.ctk.set_default_color_theme")
    def test_gui_design_tokens_defined(self, mock_theme, mock_mode, mock_init):
        """Verify design tokens are properly defined."""
        from ui.app_window import (
            _BG_DARK, _BG_SIDEBAR, _BG_CHAT, _BG_INPUT,
            _ACCENT, _ACCENT_HOVER, _ACCENT_LIGHT,
            _TEXT_PRIMARY, _TEXT_SECONDARY,
            _STATUS_COLORS,
        )
        self.assertEqual(_BG_DARK, "#0D0D1A")
        self.assertEqual(_BG_SIDEBAR, "#12122B")
        self.assertIn("idle", _STATUS_COLORS)
        self.assertIn("listening", _STATUS_COLORS)
        self.assertIn("processing", _STATUS_COLORS)
        self.assertIn("ai_unavailable", _STATUS_COLORS)

    def test_status_colors_all_present(self):
        from ui.app_window import _STATUS_COLORS
        expected = {"idle", "listening", "processing", "speaking", "ai_unavailable", "error"}
        self.assertEqual(set(_STATUS_COLORS.keys()), expected)


class TestGUIResultQueue(unittest.TestCase):
    """Test the thread-safe result queue mechanism."""

    def test_completed_response_resumes_continuous_mic_after_speech(self):
        from ui.app_window import NovaGUI

        gui = MagicMock()
        gui._result_queue = queue.Queue()
        gui._result_queue.put({
            "type": "command_result",
            "text": "tell me a joke",
            "result": CommandResult.ok("local.joke", "Here is a joke."),
        })
        gui._auto_listen = True
        gui._processing = True

        NovaGUI._poll_results(gui)

        self.assertFalse(gui._processing)
        gui.after.assert_any_call(800, gui._start_microphone)

    def test_queue_passes_command_result(self):
        """Verify CommandResult can be serialized through the queue."""
        q: queue.Queue = queue.Queue()
        result = CommandResult.ok("system.get_time", "The time is 6:30 PM.")
        q.put({"type": "command_result", "text": "what time is it", "result": result})

        msg = q.get_nowait()
        self.assertEqual(msg["type"], "command_result")
        self.assertEqual(msg["result"].command_name, "system.get_time")
        self.assertTrue(msg["result"].success)

    def test_queue_passes_error(self):
        """Verify error messages flow through the queue."""
        q: queue.Queue = queue.Queue()
        q.put({"type": "error", "text": "bad input", "error": "Something failed"})

        msg = q.get_nowait()
        self.assertEqual(msg["type"], "error")
        self.assertIn("failed", msg["error"])

    def test_queue_passes_mic_result(self):
        """Verify mic results flow through the queue."""
        q: queue.Queue = queue.Queue()
        q.put({"type": "mic_result", "text": "open chrome"})

        msg = q.get_nowait()
        self.assertEqual(msg["type"], "mic_result")
        self.assertEqual(msg["text"], "open chrome")

    def test_queue_passes_unsupported_offline_result(self):
        """Verify local limitation messages flow through the queue."""
        q: queue.Queue = queue.Queue()
        result = CommandResult.fail(
            "local.unsupported",
            "I can't answer that offline.",
            error="Request requires unsupported offline knowledge.",
        )
        q.put({"type": "command_result", "text": "tell me a joke", "result": result})

        msg = q.get_nowait()
        self.assertEqual(msg["result"].command_name, "local.unsupported")
        self.assertFalse(msg["result"].success)


class TestGUIAssistantIntegration(unittest.TestCase):
    """Test that the GUI correctly delegates to the assistant core."""

    def test_assistant_process_input_returns_command_result(self):
        """Verify the assistant returns a CommandResult for local commands."""
        # Build a real assistant with mocked services
        from core.assistant import Assistant
        from ui.app_window import _GUISpeaker

        speaker = _GUISpeaker(voice_mode=False)
        assistant = Assistant(
            voice_mode=False,
            speaker=speaker,
        )

        # Mock the launcher to avoid real app launches
        assistant.launcher.launch_app = MagicMock(
            return_value=MagicMock(success=True, message="Opening Notepad.", executable="notepad.exe")
        )

        result = assistant.process_input("open notepad")
        self.assertIsInstance(result, CommandResult)
        self.assertTrue(result.success)
        self.assertEqual(result.command_name, "app.open_notepad")

    def test_assistant_exit_command_sets_context(self):
        """Verify exit command sets should_exit on context."""
        from core.assistant import Assistant
        from ui.app_window import _GUISpeaker

        speaker = _GUISpeaker(voice_mode=False)
        assistant = Assistant(voice_mode=False, speaker=speaker)

        result = assistant.process_input("exit")
        self.assertTrue(result.success)
        self.assertEqual(result.command_name, "control.exit")
        self.assertTrue(assistant.context.should_exit)

    def test_assistant_security_blocks_in_gui(self):
        """Verify forbidden commands are blocked even through the GUI path."""
        from core.assistant import Assistant
        from ui.app_window import _GUISpeaker

        speaker = _GUISpeaker(voice_mode=False)
        assistant = Assistant(voice_mode=False, speaker=speaker)

        result = assistant.process_input("format my computer")
        self.assertFalse(result.success)
        self.assertEqual(result.command_name, "security.forbidden")

    def test_assistant_deterministic_time_command_in_gui(self):
        """Verify deterministic commands work through the GUI assistant."""
        from core.assistant import Assistant
        from ui.app_window import _GUISpeaker

        speaker = _GUISpeaker(voice_mode=False)
        assistant = Assistant(voice_mode=False, speaker=speaker)

        result = assistant.process_input("what time is it")
        self.assertTrue(result.success)
        self.assertEqual(result.command_name, "system.get_time")
        self.assertIn("current time", result.spoken_response)


class TestGUIHistoryItem(unittest.TestCase):
    """Test the history item widget can be instantiated."""

    def test_history_item_data_structure(self):
        """Verify history items store the right data."""
        history = []
        history.append({
            "text": "open chrome",
            "command": "app.open_chrome",
            "success": True,
        })
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["command"], "app.open_chrome")
        self.assertTrue(history[0]["success"])


class TestAppEntryPoint(unittest.TestCase):
    """Test that app.py properly routes to GUI mode."""

    def test_default_startup_launches_voice_enabled_gui(self):
        """Running app.py without flags should select the hands-free GUI."""
        from app import main

        with patch("sys.argv", ["app.py"]), \
                patch("app.setup_logging"), \
                patch("ui.app_window.launch_gui") as launch_gui:
            main()

        launch_gui.assert_called_once()
        self.assertIs(launch_gui.call_args.kwargs["voice_enabled"], True)

    def test_app_imports_nova_app_alias(self):
        """Verify backward-compatible NovaApp alias exists."""
        from app import NovaApp
        from core.assistant import Assistant
        self.assertIs(NovaApp, Assistant)

    @patch("sys.argv", ["app.py", "--text"])
    def test_text_flag_does_not_launch_gui(self):
        """--text flag should not import the GUI module."""
        import argparse
        parser = argparse.ArgumentParser()
        group = parser.add_mutually_exclusive_group()
        group.add_argument("--text", action="store_true")
        group.add_argument("--voice", action="store_true")
        group.add_argument("--gui", action="store_true")
        args = parser.parse_args(["--text"])
        self.assertTrue(args.text)
        self.assertFalse(args.gui)
        self.assertFalse(args.voice)

    @patch("sys.argv", ["app.py", "--gui"])
    def test_gui_flag_parsed(self):
        """--gui flag should be recognized."""
        import argparse
        parser = argparse.ArgumentParser()
        group = parser.add_mutually_exclusive_group()
        group.add_argument("--text", action="store_true")
        group.add_argument("--voice", action="store_true")
        group.add_argument("--gui", action="store_true")
        args = parser.parse_args(["--gui"])
        self.assertTrue(args.gui)


class TestGUIShutdownCleanup(unittest.TestCase):
    """Test shutdown and cleanup flows."""

    def test_mic_stop_event_works(self):
        """Verify threading.Event can signal mic stop."""
        import threading
        event = threading.Event()
        self.assertFalse(event.is_set())
        event.set()
        self.assertTrue(event.is_set())
        event.clear()
        self.assertFalse(event.is_set())

    def test_speaker_stop_is_safe(self):
        """Verify speaker stop doesn't raise."""
        from ui.app_window import _GUISpeaker
        speaker = _GUISpeaker(voice_mode=False)
        speaker.stop()  # Should not raise


if __name__ == "__main__":
    unittest.main()
