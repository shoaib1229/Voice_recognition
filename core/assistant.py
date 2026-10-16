"""
core/assistant.py
=================
Central assistant orchestrator connecting input, normalization, deterministic
command routing, safe AI fallback, speech output, and session context.

Architecture Pipeline:
  User Input (Voice / Text)
       │
       ▼
  Text Normalizer (strips polite filler, canonicalizes intent)
       │
       ▼
  Exit / Safety Verification (rejects forbidden keywords)
       │
       ▼
  Deterministic Command Registry (Chrome, VS Code, WhatsApp, Web, Folders, System...)
       ├── Score >= 0.85  ──► Execute allowlisted local command directly
       ├── 0.50 <= Score < 0.85 ──► Ask for clarification
       │
       ▼ Score < 0.50 (No deterministic command match)
  Local rule-based response or clear unsupported-offline message
       │
       ▼
  Speaker (Voice output / Console print) & Context Logging
"""

from __future__ import annotations

import time
from typing import Optional

from ai.conversation import ConversationManager
from commands import build_default_command_registry
from commands.base import CommandResult
from commands.registry import CommandRegistry
from config.app_registry import FORBIDDEN_KEYWORDS
from config.settings import Settings, settings as global_settings
from core.context import Context
from core.listener import Listener
from core.local_fallback import LocalFallbackHandler
from core.speaker import Speaker
from services.app_launcher_service import AppLauncherService
from services.confirmation_service import ConfirmationService
from services.search_service import SearchService
from services.weather_service import WeatherService
from services.wikipedia_service import WikipediaService
from utils.helpers import contains_forbidden
from utils.logger import get_logger
from utils.normalizer import normalize_intent

logger = get_logger("nova.assistant")

EXIT_PHRASES = frozenset({
    "exit", "quit", "goodbye", "bye", "bye nova", "stop nova", "shut down", "shutdown",
})


class Assistant:
    """
    Nova's main assistant coordinator.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        voice_mode: bool = False,
        registry: Optional[CommandRegistry] = None,
        conversation: Optional[ConversationManager] = None,
        speaker: Optional[Speaker] = None,
        listener: Optional[Listener] = None,
        confirmation: Optional[ConfirmationService] = None,
        launcher: Optional[AppLauncherService] = None,
        search: Optional[SearchService] = None,
        weather: Optional[WeatherService] = None,
        wiki: Optional[WikipediaService] = None,
    ) -> None:
        self.settings = settings or global_settings
        self.voice_mode = voice_mode
        self.context = Context(voice_mode=self.voice_mode)

        # Services
        self.launcher = launcher or AppLauncherService(settings=self.settings)
        self.search = search or SearchService()
        self.weather = weather or WeatherService(settings=self.settings)
        self.wiki = wiki or WikipediaService()
        self.confirmation = confirmation or ConfirmationService()

        # Output & Input
        self.speaker = speaker or Speaker(settings=self.settings, voice_mode=self.voice_mode)
        self.listener: Optional[Listener] = None
        if self.voice_mode:
            self.listener = listener or Listener(settings=self.settings)

        # Local response layer
        self.conversation = conversation or ConversationManager()
        self.local_fallback = LocalFallbackHandler()

        # Command Registry
        self.registry = registry or build_default_command_registry(
            launcher=self.launcher,
            search=self.search,
            weather=self.weather,
            wiki=self.wiki,
            confirmation=self.confirmation,
        )

        logger.info(
            "Assistant core initialized with %d registered commands (voice_mode=%s).",
            len(self.registry),
            self.voice_mode,
        )

    def is_exit_command(self, text: str) -> bool:
        """Check if *text* corresponds to a registered termination command."""
        norm = normalize_intent(text)
        return norm in EXIT_PHRASES

    def process_input(self, raw_input: str) -> CommandResult:
        """
        Process a single user input turn through the routing pipeline.

        Returns:
            CommandResult: Structured result delivered to speaker and logged.
        """
        cleaned_input = raw_input.strip()
        if not cleaned_input:
            return CommandResult.ok("noop", "", data={"empty": True})

        norm_intent = normalize_intent(cleaned_input)

        # -------------------------------------------------------------
        # Step 1: Security check for dangerous keywords
        # -------------------------------------------------------------
        if contains_forbidden(norm_intent, FORBIDDEN_KEYWORDS):
            logger.warning("Blocked input containing forbidden keyword: %r", cleaned_input)
            msg = "That action is restricted for computer safety and cannot be executed."
            res = CommandResult.fail("security.forbidden", msg, error="Forbidden keyword detected")
            self.speaker.speak(msg)
            self.context.record_turn(cleaned_input, "security.forbidden", msg, False)
            return res

        # -------------------------------------------------------------
        # Step 2: Termination commands
        # -------------------------------------------------------------
        if self.is_exit_command(norm_intent):
            logger.info("Exit command received: %r", cleaned_input)
            self.context.should_exit = True
            msg = "Goodbye! Have a great day."
            res = CommandResult.ok("control.exit", msg, data={"exit": True})
            self.speaker.speak(msg)
            self.context.record_turn(cleaned_input, "control.exit", msg, True)
            return res

        # -------------------------------------------------------------
        # Step 3: Deterministic command routing first
        # -------------------------------------------------------------
        start_time = time.perf_counter()
        matches = self.registry.find(cleaned_input)

        if matches:
            top_match = matches[0]

            # High confidence threshold (>= 0.85) -> Execute allowlisted command
            if top_match.score >= 0.85:
                cmd = top_match.command
                logger.info("Matched deterministic command: %s (score=%.2f, priority=%d)", cmd.name, top_match.score, cmd.priority)
                params = cmd.extract_params(cleaned_input)
                result = cmd.execute(params, self.context)
                duration = time.perf_counter() - start_time
                logger.info("Command %s finished in %.3fs (success=%s)", cmd.name, duration, result.success)

                self.speaker.speak(result.spoken_response)
                self.context.record_turn(cleaned_input, cmd.name, result.spoken_response, result.success)
                return result

            # Ambiguous confidence (0.50 <= score < 0.85) -> Ask for clarification
            if top_match.score >= 0.50:
                cmd = top_match.command
                clarification = f"I heard '{cleaned_input}'. Did you mean to {cmd.description.lower()}?"
                logger.info("Ambiguous input (score=%.2f) matched %s; asking clarification", top_match.score, cmd.name)
                res = CommandResult.fail("router.ambiguous", clarification, error="Ambiguous input")
                self.speaker.speak(clarification)
                self.context.record_turn(cleaned_input, "router.ambiguous", clarification, False)
                return res

        # -------------------------------------------------------------
        # Step 4: Narrow deterministic small-talk fallback
        # -------------------------------------------------------------
        local_result = self.local_fallback.respond(cleaned_input)
        if local_result is not None:
            logger.info("Handled simple interaction locally: %s", local_result.command_name)
            self.speaker.speak(local_result.spoken_response)
            self.context.record_turn(cleaned_input, local_result.command_name, local_result.spoken_response, True)
            self.conversation.record_turn(cleaned_input, local_result.spoken_response)
            return local_result

        # -------------------------------------------------------------
        # Step 5: Local conversation patterns or a clear unsupported response
        # -------------------------------------------------------------
        logger.info("No registered command matched %r; responding with local rules", cleaned_input)
        return self._process_local_fallback(cleaned_input)

    # Backward-compatible aliases for tests and external callers
    is_exit_phrase = is_exit_command

    def process_turn(self, user_text: str) -> bool:
        """
        Process a single turn and return False if the session should terminate, True otherwise.
        """
        self.process_input(user_text)
        return not self.context.should_exit

    def _process_local_fallback(self, user_input: str) -> CommandResult:
        """Answer supported social patterns locally and decline unsupported questions honestly."""
        result = self.local_fallback.respond(user_input)
        if result is None:
            result = CommandResult.fail(
                "local.unsupported",
                "I can't answer that offline. I can help with supported desktop commands, web searches, weather, time, and date.",
                error="Request requires unsupported offline knowledge.",
                data={"source": "local_fallback", "ai_generated": False},
            )
        self.speaker.speak(result.spoken_response)
        self.context.record_turn(user_input, result.command_name, result.spoken_response, result.success)
        self.conversation.record_turn(user_input, result.spoken_response)
        return result

    def run_text_loop(self) -> None:
        """Run interactive CLI text mode."""
        print("Nova is ready. Type your command (or 'exit' to quit).\n")
        while not self.context.should_exit:
            try:
                user_text = input("You > ").strip()
                if not user_text:
                    continue
                self.process_input(user_text)
            except (KeyboardInterrupt, EOFError):
                print("\n")
                self.speaker.speak("Shutting down Nova. Goodbye!")
                break

    def run_voice_loop(self) -> None:
        """Run interactive speech recognition voice loop."""
        if self.listener is None or not self.listener.is_available():
            print("\n[WARNING] No functional microphone detected on this system.")
            print("Switching automatically to Text Mode fallback.\n")
            self.voice_mode = False
            self.speaker = Speaker(settings=self.settings, voice_mode=False)
            self.run_text_loop()
            return

        print("\nMicrophone active. Start speaking (or press Ctrl+C to stop)...\n")
        while not self.context.should_exit:
            try:
                print("[🎤 Listening...]")
                user_text = self.listener.listen()
                if not user_text:
                    continue

                print(f"You said: {user_text}")
                self.process_input(user_text)

            except KeyboardInterrupt:
                print("\n")
                self.speaker.speak("Shutting down Nova. Goodbye!")
                break

    def run(self) -> None:
        """Boot the interactive assistant loop."""
        mode_str = "Voice Mode (Microphone + TTS)" if self.voice_mode else "Text Mode (Keyboard CLI)"
        print("=" * 64)
        print("           NOVA — Modular Desktop Voice Assistant")
        print("=" * 64)
        print(f"Mode      : {mode_str}")
        print("Responses : Local rules and supported commands")
        print(f"Commands  : {len(self.registry)} registered allowlisted desktop/web commands")
        print("Exit      : Say or type 'exit', 'quit', or 'goodbye' to quit.")
        print("-" * 64)

        if self.voice_mode:
            self.run_voice_loop()
        else:
            self.run_text_loop()
