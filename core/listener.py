"""
core/listener.py
================
Microphone listener abstraction using SpeechRecognition and PyAudio.

Features:
- Encapsulates audio capture and Google Speech Recognition.
- Configurable language, timeout, and phrase time limit from settings.
- Gracefully handles missing microphone hardware, silence, unintelligible audio,
  and network service dropouts.
- Never crashes the calling loop on individual audio recognition failures.
- Dependency-injected design allows 100% mock testing without real audio hardware.
"""

from __future__ import annotations

from typing import Any, Optional

import speech_recognition as sr

from config.settings import Settings, settings as global_settings
from utils.logger import get_logger

logger = get_logger(__name__)


class ListenerError(RuntimeError):
    """Raised for unrecoverable listener configuration failures."""


class Listener:
    """
    Microphone listener abstraction for Nova.

    Usage:
        listener = Listener()
        phrase = listener.listen()
        if phrase:
            print("Recognized:", phrase)
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        recognizer: Optional[sr.Recognizer] = None,
        microphone: Optional[sr.Microphone] = None,
    ) -> None:
        """
        Initialize the microphone listener.

        Args:
            settings: Optional Settings instance (defaults to global settings).
            recognizer: Optional pre-configured sr.Recognizer instance (for testing).
            microphone: Optional pre-configured sr.Microphone instance (for testing).
        """
        self._settings = settings or global_settings
        self.language = self._settings.SPEECH_LANGUAGE or "en-IN"
        self.timeout = self._settings.SPEECH_TIMEOUT or 5
        self.phrase_time_limit = self._settings.SPEECH_PHRASE_LIMIT or 10
        self.recognition_timeout = getattr(self._settings, "SPEECH_RECOGNITION_TIMEOUT", 15) or 15

        self._recognizer = recognizer or sr.Recognizer()
        self._recognizer.dynamic_energy_threshold = True
        # Let speakers pause naturally between clauses without ending the turn
        # too early. The default phrase cap is long enough for normal sentences.
        self._recognizer.pause_threshold = 1.2
        self._recognizer.energy_threshold = 300
        self._recognizer.non_speaking_duration = 0.6
        self._recognizer.operation_timeout = self.recognition_timeout

        self._microphone = microphone
        self._mic_initialized = microphone is not None
        self._ambient_adjusted = False
        # Kept separate from the return value so the GUI can distinguish a
        # normal silence timeout from a microphone or speech-service failure.
        self.last_error: Optional[str] = None

        logger.debug(
            "Listener initialized (language=%s, timeout=%ds, phrase_limit=%ds)",
            self.language,
            self.timeout,
            self.phrase_time_limit,
        )

    def _ensure_microphone(self) -> Optional[sr.Microphone]:
        """Lazy-initialize and validate the microphone hardware."""
        if self._microphone is not None:
            return self._microphone

        try:
            mic = sr.Microphone()
            self._microphone = mic
            self._mic_initialized = True
            logger.info("Microphone hardware interface initialized successfully.")
            return mic
        except Exception as exc:
            logger.warning("Microphone hardware unavailable: %s", exc)
            self._microphone = None
            self._mic_initialized = False
            return None

    def is_available(self) -> bool:
        """Return True if an audio input device is accessible."""
        try:
            return self._ensure_microphone() is not None
        except Exception:
            return False

    def listen(self) -> Optional[str]:
        """
        Capture audio from the microphone and return recognized text.

        Returns:
            The recognized speech as a clean string, or None if:
            - No speech was detected before timeout
            - Speech was unintelligible
            - The STT network request failed
            - No microphone is connected
        """
        mic = self._ensure_microphone()
        if mic is None:
            logger.warning("Listen aborted: No microphone device available.")
            self.last_error = "unavailable"
            return None

        self.last_error = None
        try:
            with mic as source:
                # Adjust for ambient room noise once on first capture
                if not self._ambient_adjusted:
                    try:
                        logger.debug("Calibrating microphone for ambient room noise...")
                        self._recognizer.adjust_for_ambient_noise(source, duration=0.8)
                        self._ambient_adjusted = True
                    except Exception as exc:
                        logger.debug("Ambient noise calibration skipped: %s", exc)

                logger.debug("Listening for speech (timeout=%ds)...", self.timeout)
                audio = self._recognizer.listen(
                    source,
                    timeout=self.timeout,
                    phrase_time_limit=self.phrase_time_limit,
                )

            logger.debug("Audio captured. Sending to speech recognition service...")
            raw_text = self._recognizer.recognize_google(audio, language=self.language)
            recognized = str(raw_text).strip()

            if recognized:
                logger.info("Speech successfully recognized: %r", recognized)
                return recognized
            self.last_error = "unrecognized"
            return None

        except sr.WaitTimeoutError:
            logger.debug("No speech detected within %ds timeout.", self.timeout)
            self.last_error = "timeout"
            return None

        except sr.UnknownValueError:
            logger.info("Audio detected but speech was not intelligible.")
            self.last_error = "unrecognized"
            return None

        except sr.RequestError as exc:
            logger.warning("Speech recognition network service error: %s", exc)
            self.last_error = "network"
            return None

        except OSError as exc:
            logger.error("Audio device I/O error during listening: %s", exc)
            self.last_error = "device"
            return None

        except Exception as exc:
            logger.error("Unexpected error during speech recognition: %s", exc)
            self.last_error = "error"
            return None
