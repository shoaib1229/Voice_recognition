"""
ui/app_window.py
================
Modern desktop GUI for Nova — AI Voice Assistant.

Built with CustomTkinter for a polished dark-theme look, featuring:
  - Left sidebar with navigation, status, and recent command history.
  - Central conversation area with distinct user/assistant message bubbles.
  - Bottom input bar with text entry, send button, and microphone control.
  - Visible status indicator for Idle, Listening, Processing, Speaking, AI Unavailable.
  - Thread-safe background processing for mic capture, API calls, and TTS.

Integration:
  Uses the existing core/assistant.py orchestrator.
  All business logic, command routing, and security stay in the assistant core.
  The GUI only handles presentation and user interaction events.
"""

from __future__ import annotations

import datetime
import queue
import threading
import time
import tkinter as tk
from typing import Any, Callable, Optional

import customtkinter as ctk

from commands.base import CommandResult
from config.settings import Settings, settings as global_settings
from core.assistant import Assistant
from core.speaker import Speaker, prepare_speech_text
from utils.logger import get_logger

logger = get_logger("nova.gui")

# ─── Design Tokens ──────────────────────────────────────────────────────
# Dark theme with restrained purple accents
_BG_DARK = "#0D0D1A"          # Main background
_BG_SIDEBAR = "#12122B"       # Sidebar background
_BG_CHAT = "#111126"          # Conversation area
_BG_INPUT = "#1A1A3E"         # Input bar background
_BG_USER_BUBBLE = "#2D1F6B"   # User message bubble
_BG_NOVA_BUBBLE = "#1B1B40"   # Nova message bubble
_ACCENT = "#7C3AED"           # Primary purple accent
_ACCENT_HOVER = "#6D28D9"     # Hover state
_ACCENT_LIGHT = "#A78BFA"     # Light accent for highlights
_TEXT_PRIMARY = "#E8E8F0"      # Primary text
_TEXT_SECONDARY = "#9CA3AF"    # Secondary / muted text
_TEXT_DIM = "#6B7280"          # Dimmed text
_BORDER = "#2A2A50"            # Subtle border
_SUCCESS = "#34D399"           # Green for success
_WARNING = "#FBBF24"           # Amber for warning
_ERROR = "#F87171"             # Red for error
_MIC_ACTIVE = "#EF4444"       # Red pulsing mic indicator

# Status colors
_STATUS_COLORS = {
    "idle": _SUCCESS,
    "listening": _MIC_ACTIVE,
    "processing": _ACCENT_LIGHT,
    "speaking": _ACCENT,
    "ai_unavailable": _WARNING,
    "error": _ERROR,
}

# ─── Silent Speaker ─────────────────────────────────────────────────────
# The GUI manages its own display; suppress Speaker's console print and
# TTS so we control when/where text appears.

class _GUISpeaker(Speaker):
    """A speaker subclass that suppresses console printing in GUI mode.
    Voice synthesis is still performed when voice_mode is True.
    The GUI reads responses from CommandResult, not from print()."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        voice_mode: bool = False,
        engine: Any = None,
        status_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        # Create and use the Windows SAPI engine on the same persistent thread.
        # Initializing it on Tk's thread and calling runAndWait from a fresh
        # command thread on every turn can break COM-backed voices after turn 1.
        super().__init__(settings=settings, voice_mode=False, engine=engine)
        self._voice_mode = voice_mode
        self._status_callback = status_callback
        self._tts_queue: queue.Queue[Any] = queue.Queue()
        self._tts_thread: Optional[threading.Thread] = None
        self._tts_thread_lock = threading.Lock()
        self._tts_loop_started = False
        self._tts_sequence = 0
        self._active_tts: Optional[dict[str, Any]] = None
        self._tts_stop_requested = threading.Event()

    def speak(self, text: str) -> None:
        """In GUI mode, only do TTS if voice_mode is on; never print to console."""
        if not text or not text.strip():
            return
        sanitized = prepare_speech_text(text)
        logger.info("Assistant response received by GUI speaker (characters=%d).", len(sanitized))
        if not self._voice_mode:
            logger.info("Speech skipped because Voice Speech is disabled.")
            return

        self._ensure_tts_worker()
        finished = threading.Event()
        self._tts_queue.put((sanitized, finished))
        logger.info("Speech queued (pending=%d).", self._tts_queue.qsize())
        # This is called from the assistant's background worker, never Tk's
        # event thread. Waiting prevents overlapping speech and keeps the mic
        # paused until the current reply has actually finished.
        finished.wait()

    def _ensure_tts_worker(self) -> None:
        with self._tts_thread_lock:
            if self._tts_thread is not None and self._tts_thread.is_alive():
                return
            self._tts_thread = threading.Thread(
                target=self._run_tts_queue,
                daemon=True,
                name="nova-tts",
            )
            self._tts_thread.start()
            logger.info("TTS worker started (thread=%s).", self._tts_thread.name)

    def _notify_speech_status(self, status: str) -> None:
        if self._status_callback is None:
            return
        try:
            self._status_callback(status)
        except Exception:
            logger.exception("Unable to publish TTS status %r to the GUI.", status)

    def _run_tts_queue(self) -> None:
        """Own the TTS engine on one thread and serialize every utterance."""
        logger.info("TTS worker queue loop is running.")
        while True:
            item = self._tts_queue.get()
            if item is None:
                self._close_tts_engine()
                return
            text, finished = item
            if text is None:
                self._tts_stop_requested.set()
                finished.set()
                continue
            self._notify_speech_status("speaking")
            try:
                if self._engine is None:
                    self._init_engine()
                if self._engine is None:
                    logger.error("Speech playback failed: no TTS engine is available after initialization.")
                    continue
                if not self._tts_loop_started:
                    self._engine.connect("finished-utterance", self._on_tts_finished)
                    self._engine.startLoop(False)
                    self._tts_loop_started = True
                    logger.info("TTS engine initialized on its owner worker thread with a persistent external event loop.")
                self._tts_sequence += 1
                utterance_name = f"nova-utterance-{self._tts_sequence}"
                playback = {
                    "name": utterance_name,
                    "finished": threading.Event(),
                    "completed": False,
                }
                self._active_tts = playback
                logger.info("Speech playback started (utterance=%s, characters=%d).", utterance_name, len(text))
                self._engine.say(text, name=utterance_name)
                deadline = time.monotonic() + max(30.0, len(text) / 8.0 + 20.0)
                while not playback["finished"].is_set():
                    if self._tts_stop_requested.is_set():
                        self._tts_stop_requested.clear()
                        self._engine.stop()
                    if time.monotonic() >= deadline:
                        raise TimeoutError("TTS engine did not signal utterance completion before the playback timeout")
                    self._engine.iterate()
                    playback["finished"].wait(0.01)
                if playback["completed"]:
                    logger.info("Speech playback completed (utterance=%s).", utterance_name)
                else:
                    logger.warning("Speech playback ended before completion (utterance=%s).", utterance_name)
            except Exception:
                logger.exception("Speech playback failed; the worker will continue and reinitialize for the next response.")
                self._close_tts_engine()
            finally:
                self._active_tts = None
                self._notify_speech_status("processing")
                finished.set()

    def _on_tts_finished(self, name: Optional[str] = None, completed: bool = True, **_kwargs: Any) -> None:
        """Receive SAPI completion events on the engine-owning worker thread."""
        playback = self._active_tts
        if playback is None or (name is not None and name != playback["name"]):
            return
        playback["completed"] = bool(completed)
        playback["finished"].set()

    def _close_tts_engine(self) -> None:
        """Release a failed engine on its owner thread so a later turn can reinitialize it."""
        engine = self._engine
        self._engine = None
        self._engine_initialized = False
        if engine is None:
            self._tts_loop_started = False
            return
        try:
            engine.stop()
        except Exception:
            logger.exception("TTS engine stop failed while recovering.")
        if self._tts_loop_started:
            try:
                engine.endLoop()
            except Exception:
                logger.exception("TTS event loop shutdown failed while recovering.")
        self._tts_loop_started = False

    def stop(self) -> None:
        """Stop current playback and close the worker-owned engine on shutdown."""
        if self._tts_thread is not None and self._tts_thread.is_alive():
            if self._active_tts is not None:
                self._tts_stop_requested.set()
            self._tts_queue.put(None)
        else:
            super().stop()


# ─── Chat Message Frame ─────────────────────────────────────────────────

class _ChatBubble(ctk.CTkFrame):
    """A single chat message bubble (user or assistant)."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        sender: str,
        text: str,
        timestamp: str,
        is_user: bool = True,
        is_error: bool = False,
        **kwargs: Any,
    ) -> None:
        bg_color = _BG_USER_BUBBLE if is_user else _BG_NOVA_BUBBLE
        if is_error:
            bg_color = "#2D1520"
        super().__init__(parent, fg_color=bg_color, corner_radius=14, **kwargs)

        # Alignment
        anchor = "e" if is_user else "w"
        self.pack(fill="x", padx=(60 if is_user else 16, 16 if is_user else 60), pady=(4, 4), anchor=anchor)

        # Sender label
        sender_color = _ACCENT_LIGHT if is_user else _SUCCESS
        if is_error:
            sender_color = _ERROR
        sender_label = ctk.CTkLabel(
            self,
            text=sender,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=sender_color,
            anchor="w",
        )
        sender_label.pack(fill="x", padx=14, pady=(10, 0))

        # Message text
        msg_label = ctk.CTkLabel(
            self,
            text=text,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=_TEXT_PRIMARY if not is_error else _ERROR,
            anchor="w",
            justify="left",
            wraplength=500,
        )
        msg_label.pack(fill="x", padx=14, pady=(4, 4))

        # Timestamp
        time_label = ctk.CTkLabel(
            self,
            text=timestamp,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=_TEXT_DIM,
            anchor="e",
        )
        time_label.pack(fill="x", padx=14, pady=(0, 8))


# ─── History Item ────────────────────────────────────────────────────────

class _HistoryItem(ctk.CTkFrame):
    """A compact recent-command entry for the sidebar."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        command_text: str,
        command_name: str,
        success: bool = True,
        on_click: Optional[Callable[[], None]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(parent, fg_color="transparent", cursor="hand2", **kwargs)
        self.pack(fill="x", padx=8, pady=2)

        indicator = "●" if success else "○"
        color = _SUCCESS if success else _ERROR

        label = ctk.CTkLabel(
            self,
            text=f"  {indicator}  {command_text[:32]}",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=color,
            anchor="w",
        )
        label.pack(fill="x", padx=4, pady=2)

        sub_label = ctk.CTkLabel(
            self,
            text=f"      {command_name}",
            font=ctk.CTkFont(family="Segoe UI", size=9),
            text_color=_TEXT_DIM,
            anchor="w",
        )
        sub_label.pack(fill="x", padx=4, pady=(0, 2))

        if on_click:
            self.bind("<Button-1>", lambda e: on_click())
            label.bind("<Button-1>", lambda e: on_click())


# ═══════════════════════════════════════════════════════════════════════
#  MAIN APPLICATION WINDOW
# ═══════════════════════════════════════════════════════════════════════

class NovaGUI(ctk.CTk):
    """
    Main desktop GUI for Nova — AI Voice Assistant.

    Creates and owns an Assistant instance, delegates all command
    routing and AI interaction to it, and only handles presentation.
    """

    # Window geometry
    _DEFAULT_WIDTH = 1100
    _DEFAULT_HEIGHT = 720
    _MIN_WIDTH = 850
    _MIN_HEIGHT = 550

    def __init__(self, settings: Optional[Settings] = None, voice_enabled: bool = False) -> None:
        super().__init__()

        self._settings = settings or global_settings
        self._voice_enabled = voice_enabled

        # ── Thread-safe result queue ──
        self._result_queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self._processing = False
        self._mic_active = False
        self._mic_thread: Optional[threading.Thread] = None
        self._mic_stop_event = threading.Event()
        # Spoken output and hands-free listening start together when launched
        # in voice mode. The microphone is still paused while Nova speaks.
        self._auto_listen = bool(voice_enabled)
        self._history_items: list[dict[str, Any]] = []

        # ── Build the Assistant (reusing all existing modules) ──
        self._speaker = _GUISpeaker(
            settings=self._settings,
            voice_mode=voice_enabled,
            status_callback=lambda status: self._result_queue.put(
                {"type": "status", "status": status}
            ),
        )
        self._assistant = Assistant(
            settings=self._settings,
            voice_mode=False,  # We handle voice I/O ourselves
            speaker=self._speaker,
        )

        # ── Window configuration ──
        self.title("Nova — AI Voice Assistant")
        self.geometry(f"{self._DEFAULT_WIDTH}x{self._DEFAULT_HEIGHT}")
        self.minsize(self._MIN_WIDTH, self._MIN_HEIGHT)
        self.configure(fg_color=_BG_DARK)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # ── Icon (try to set, no-op if missing) ──
        try:
            self.iconbitmap(default="")
        except Exception:
            pass

        # ── Build UI ──
        self._build_layout()
        self._set_status("idle")
        self._show_welcome_message()

        # ── Poll the result queue for thread-safe widget updates ──
        self._poll_results()

        # Start capture only after the window and its controls are ready.
        if self._auto_listen:
            self._auto_listen_switch.select()
            self.after(700, self._start_microphone)

        # ── Clean shutdown ──
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        logger.info(
            "Nova GUI initialized (%dx%d, voice_enabled=%s, commands=%d).",
            self._DEFAULT_WIDTH, self._DEFAULT_HEIGHT,
            self._voice_enabled, len(self._assistant.registry),
        )

    # ═══════════════════════════════════════════════════════════════════
    #  LAYOUT
    # ═══════════════════════════════════════════════════════════════════

    def _build_layout(self) -> None:
        """Construct the three-column layout: sidebar | chat | (input bar at bottom)."""
        # Grid weights
        self.grid_columnconfigure(0, weight=0, minsize=240)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main_area()

    def _build_sidebar(self) -> None:
        """Left sidebar with logo, status, navigation, and recent history."""
        sidebar = ctk.CTkFrame(self, fg_color=_BG_SIDEBAR, corner_radius=0, width=240)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)

        # ── Logo / Title ──
        logo_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        logo_frame.pack(fill="x", padx=16, pady=(24, 8))

        # Nova icon circle
        icon_canvas = tk.Canvas(logo_frame, width=44, height=44, bg=_BG_SIDEBAR, highlightthickness=0)
        icon_canvas.pack(side="left", padx=(0, 10))
        icon_canvas.create_oval(2, 2, 42, 42, fill=_ACCENT, outline=_ACCENT_LIGHT, width=2)
        icon_canvas.create_text(22, 22, text="N", fill="white", font=("Segoe UI", 18, "bold"))

        title_frame = ctk.CTkFrame(logo_frame, fg_color="transparent")
        title_frame.pack(side="left", fill="x")

        ctk.CTkLabel(
            title_frame,
            text="Nova",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=_TEXT_PRIMARY,
            anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_frame,
            text="AI Voice Assistant",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=_TEXT_SECONDARY,
            anchor="w",
        ).pack(anchor="w")

        # ── Status indicator ──
        self._status_frame = ctk.CTkFrame(sidebar, fg_color=_BG_DARK, corner_radius=10, height=36)
        self._status_frame.pack(fill="x", padx=16, pady=(12, 8))

        status_inner = ctk.CTkFrame(self._status_frame, fg_color="transparent")
        status_inner.pack(fill="x", padx=12, pady=8)

        self._status_dot = tk.Canvas(status_inner, width=10, height=10, bg=_BG_DARK, highlightthickness=0)
        self._status_dot.pack(side="left", padx=(0, 8))
        self._status_dot_id = self._status_dot.create_oval(1, 1, 9, 9, fill=_SUCCESS, outline="")

        self._status_label = ctk.CTkLabel(
            status_inner,
            text="Idle",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=_TEXT_PRIMARY,
            anchor="w",
        )
        self._status_label.pack(side="left")

        # ── Info box ──
        info_frame = ctk.CTkFrame(sidebar, fg_color=_BG_DARK, corner_radius=10)
        info_frame.pack(fill="x", padx=16, pady=(8, 8))

        cmd_count = len(self._assistant.registry)

        # Row 1: Engine
        r1 = ctk.CTkFrame(info_frame, fg_color="transparent")
        r1.pack(fill="x", padx=12, pady=3)
        ctk.CTkLabel(r1, text="Engine", font=ctk.CTkFont(family="Segoe UI", size=10), text_color=_TEXT_DIM, anchor="w", width=70).pack(side="left")
        ctk.CTkLabel(r1, text="Nova AI", font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), text_color=_TEXT_SECONDARY, anchor="w").pack(side="left")

        # Row 2: Commands
        r2 = ctk.CTkFrame(info_frame, fg_color="transparent")
        r2.pack(fill="x", padx=12, pady=3)
        ctk.CTkLabel(r2, text="Commands", font=ctk.CTkFont(family="Segoe UI", size=10), text_color=_TEXT_DIM, anchor="w", width=70).pack(side="left")
        ctk.CTkLabel(r2, text=str(cmd_count), font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), text_color=_TEXT_SECONDARY, anchor="w").pack(side="left")

        # Row 3: Voice
        r3 = ctk.CTkFrame(info_frame, fg_color="transparent")
        r3.pack(fill="x", padx=12, pady=3)
        ctk.CTkLabel(r3, text="Voice", font=ctk.CTkFont(family="Segoe UI", size=10), text_color=_TEXT_DIM, anchor="w", width=70).pack(side="left")
        self._voice_status_val = ctk.CTkLabel(
            r3,
            text="Active" if self._voice_enabled else "Muted",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=_SUCCESS if self._voice_enabled else _TEXT_SECONDARY,
            anchor="w",
        )
        self._voice_status_val.pack(side="left")

        # ── Divider ──
        ctk.CTkFrame(sidebar, fg_color=_BORDER, height=1).pack(fill="x", padx=16, pady=(12, 8))

        # ── Recent Commands heading ──
        ctk.CTkLabel(
            sidebar,
            text="RECENT COMMANDS",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=_TEXT_DIM,
            anchor="w",
        ).pack(fill="x", padx=20, pady=(4, 4))

        # Scrollable history list
        self._history_scroll = ctk.CTkScrollableFrame(
            sidebar, fg_color="transparent", corner_radius=0,
            scrollbar_button_color=_BORDER, scrollbar_button_hover_color=_ACCENT,
        )
        self._history_scroll.pack(fill="both", expand=True, padx=4, pady=(0, 8))

        # ── Voice & Continuous Listening Controls ──
        btn_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=(0, 12))

        self._voice_switch = ctk.CTkSwitch(
            btn_frame,
            text="🔊 Voice Speech",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=_TEXT_SECONDARY,
            progress_color=_ACCENT,
            command=self._on_voice_switch_toggled,
        )
        if self._voice_enabled:
            self._voice_switch.select()
        self._voice_switch.pack(fill="x", pady=(0, 6))

        self._auto_listen_switch = ctk.CTkSwitch(
            btn_frame,
            text="🔁 Continuous Mic",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=_TEXT_SECONDARY,
            progress_color=_SUCCESS,
            command=self._on_auto_listen_toggled,
        )
        self._auto_listen_switch.pack(fill="x", pady=(0, 8))

        self._clear_btn = ctk.CTkButton(
            btn_frame,
            text="🗑  Clear Chat",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color=_BG_INPUT,
            hover_color=_ACCENT_HOVER,
            text_color=_TEXT_SECONDARY,
            corner_radius=8,
            height=34,
            command=self._clear_conversation,
        )
        self._clear_btn.pack(fill="x", pady=(0, 4))

    def _build_main_area(self) -> None:
        """Central chat area and bottom input bar."""
        main = ctk.CTkFrame(self, fg_color=_BG_CHAT, corner_radius=0)
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_rowconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=0)
        main.grid_columnconfigure(0, weight=1)

        # ── Chat scroll area ──
        self._chat_scroll = ctk.CTkScrollableFrame(
            main,
            fg_color=_BG_CHAT,
            corner_radius=0,
            scrollbar_button_color=_BORDER,
            scrollbar_button_hover_color=_ACCENT,
        )
        self._chat_scroll.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)

        # ── Input bar ──
        input_bar = ctk.CTkFrame(main, fg_color=_BG_INPUT, corner_radius=0, height=72)
        input_bar.grid(row=1, column=0, sticky="ew")
        input_bar.grid_columnconfigure(1, weight=1)

        # Mic button
        self._mic_btn = ctk.CTkButton(
            input_bar,
            text="🎤",
            font=ctk.CTkFont(size=18),
            fg_color=_BG_SIDEBAR,
            hover_color=_ACCENT_HOVER,
            text_color=_TEXT_SECONDARY,
            width=44,
            height=44,
            corner_radius=22,
            command=self._toggle_microphone,
        )
        self._mic_btn.grid(row=0, column=0, padx=(16, 8), pady=14)

        # Text entry
        self._text_entry = ctk.CTkEntry(
            input_bar,
            placeholder_text="Type a command or ask Nova anything...",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            fg_color=_BG_DARK,
            text_color=_TEXT_PRIMARY,
            placeholder_text_color=_TEXT_DIM,
            border_color=_BORDER,
            border_width=1,
            corner_radius=12,
            height=44,
        )
        self._text_entry.grid(row=0, column=1, padx=8, pady=14, sticky="ew")
        self._text_entry.bind("<Return>", self._on_enter_pressed)

        # Send button
        self._send_btn = ctk.CTkButton(
            input_bar,
            text="Send  ➤",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color=_ACCENT,
            hover_color=_ACCENT_HOVER,
            text_color="white",
            width=100,
            height=44,
            corner_radius=12,
            command=self._on_send_clicked,
        )
        self._send_btn.grid(row=0, column=2, padx=(8, 16), pady=14)

    # ═══════════════════════════════════════════════════════════════════
    #  STATUS MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════

    def _set_status(self, status: str, detail: str = "") -> None:
        """Update the sidebar status indicator."""
        labels = {
            "idle": "Idle — Ready",
            "listening": "🎤 Listening...",
            "processing": "⚙ Processing...",
            "speaking": "🔊 Speaking...",
            "ai_unavailable": "⚠ AI Unavailable",
            "error": "✕ Error",
        }
        color = _STATUS_COLORS.get(status, _TEXT_DIM)
        text = labels.get(status, status.title())
        if detail:
            text = f"{text} — {detail}"

        self._status_dot.itemconfigure(self._status_dot_id, fill=color)
        self._status_label.configure(text=text, text_color=color)

    # ═══════════════════════════════════════════════════════════════════
    #  CHAT DISPLAY
    # ═══════════════════════════════════════════════════════════════════

    def _timestamp(self) -> str:
        return datetime.datetime.now().strftime("%I:%M %p").lstrip("0")

    def _add_user_message(self, text: str) -> None:
        """Add a user message bubble to the conversation."""
        _ChatBubble(
            self._chat_scroll,
            sender="You",
            text=text,
            timestamp=self._timestamp(),
            is_user=True,
        )
        self._scroll_to_bottom()

    def _add_nova_message(self, text: str, is_error: bool = False) -> None:
        """Add a Nova response bubble to the conversation."""
        _ChatBubble(
            self._chat_scroll,
            sender="Nova",
            text=text,
            timestamp=self._timestamp(),
            is_user=False,
            is_error=is_error,
        )
        self._scroll_to_bottom()

    def _scroll_to_bottom(self) -> None:
        """Scroll the chat to the latest message."""
        self._chat_scroll.update_idletasks()
        try:
            self._chat_scroll._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    def _show_welcome_message(self) -> None:
        """Display a welcome message when the GUI starts."""
        welcome = (
            "Hi, I’m Nova, your personal assistant. I’m ready to listen and talk with you. "
            "You can speak naturally, ask follow-up questions, or ask me to help with a task.\n\n"
            "Try saying:\n"
            "  •  \"Open Chrome\"   •  \"What time is it?\"\n"
            "  •  \"Search YouTube for Python tutorials\"\n"
            "  •  \"What's the weather in Noida?\"\n"
            "  •  \"Open Downloads folder\"\n\n"
            "I can chat, explain things, help plan or write, and carry out supported computer commands. "
            "I’ll tell you clearly when I need more information or when an action needs your confirmation."
        )
        _ChatBubble(
            self._chat_scroll,
            sender="Nova",
            text=welcome,
            timestamp=self._timestamp(),
            is_user=False,
        )

    def _clear_conversation(self) -> None:
        """Clear all chat messages and history."""
        for widget in self._chat_scroll.winfo_children():
            widget.destroy()
        self._history_items.clear()
        for widget in self._history_scroll.winfo_children():
            widget.destroy()
        self._assistant.conversation.reset()
        self._show_welcome_message()
        self._set_status("idle")
        logger.info("Conversation cleared by user.")

    # ═══════════════════════════════════════════════════════════════════
    #  SIDEBAR HISTORY
    # ═══════════════════════════════════════════════════════════════════

    def _add_history_entry(self, user_text: str, command_name: str, success: bool) -> None:
        """Add a recent command entry to the sidebar."""
        self._history_items.append({
            "text": user_text,
            "command": command_name,
            "success": success,
        })
        # Keep only last 20 entries
        if len(self._history_items) > 20:
            self._history_items = self._history_items[-20:]
            # Rebuild sidebar history
            for w in self._history_scroll.winfo_children():
                w.destroy()
            for item in self._history_items:
                _HistoryItem(
                    self._history_scroll,
                    command_text=item["text"],
                    command_name=item["command"],
                    success=item["success"],
                )
        else:
            _HistoryItem(
                self._history_scroll,
                command_text=user_text,
                command_name=command_name,
                success=success,
            )

    # ═══════════════════════════════════════════════════════════════════
    #  INPUT HANDLING
    # ═══════════════════════════════════════════════════════════════════

    def _on_enter_pressed(self, event: Any = None) -> None:
        """Handle Enter key in the text entry."""
        self._submit_text()

    def _on_send_clicked(self) -> None:
        """Handle Send button click."""
        self._submit_text()

    def _submit_text(self) -> None:
        """Submit the current text entry to the assistant."""
        text = self._text_entry.get().strip()
        if not text or self._processing:
            return

        self._text_entry.delete(0, "end")
        self._add_user_message(text)
        self._process_command(text)

    def _process_command(self, text: str, from_voice: bool = False) -> None:
        """Process a command in a background thread."""
        if self._processing:
            return

        # A user can type while the microphone worker is finishing its turn.
        # Signal it to stop before starting AI/TTS work; the worker is joined
        # implicitly by _start_microphone's alive-thread guard.
        if self._mic_active and not from_voice:
            logger.info("Continuous Mic paused while a typed assistant turn is processed.")
            self._mic_stop_event.set()
        elif from_voice:
            logger.info("Continuous Mic paused for the recognized assistant turn and speech playback.")
        self._processing = True
        self._set_status("processing")
        self._send_btn.configure(state="disabled", fg_color=_TEXT_DIM)
        self._text_entry.configure(state="disabled")

        def _worker() -> None:
            try:
                result = self._assistant.process_input(text)
                self._result_queue.put({
                    "type": "command_result",
                    "text": text,
                    "result": result,
                })
            except Exception as exc:
                logger.error("Unexpected error processing '%s': %s", text, exc)
                self._result_queue.put({
                    "type": "error",
                    "text": text,
                    "error": str(exc),
                })

        thread = threading.Thread(target=_worker, daemon=True, name="nova-process")
        thread.start()

    def _poll_results(self) -> None:
        """Poll the result queue and update GUI widgets on the main thread."""
        try:
            while True:
                msg = self._result_queue.get_nowait()
                msg_type = msg.get("type")

                if msg_type == "command_result":
                    result: CommandResult = msg["result"]
                    user_text = msg["text"]
                    is_error = not result.success

                    self._add_nova_message(result.spoken_response, is_error=is_error)
                    self._add_history_entry(user_text, result.command_name, result.success)

                    # Update status based on result
                    if result.command_name == "control.exit":
                        self._set_status("idle", "Session ended")
                        self.after(1500, self._on_close)
                    elif "quota" in result.command_name or "account" in result.command_name:
                        self._set_status("ai_unavailable")
                    elif is_error:
                        self._set_status("error")
                        self.after(3000, lambda: self._set_status("idle"))
                    else:
                        self._set_status("idle")

                elif msg_type == "mic_result":
                    recognized = msg.get("text", "")
                    if recognized:
                        self._add_user_message(recognized)
                        self._process_command(recognized, from_voice=True)
                    else:
                        self._set_status("idle")

                elif msg_type == "mic_empty":
                    reason = msg.get("reason", "timeout")
                    if reason in {"network", "device", "unavailable", "error"}:
                        self._auto_listen = False
                        self._auto_listen_switch.deselect()
                        guidance = {
                            "network": "Speech recognition could not reach Google. Check your internet connection and try the mic again.",
                            "device": "The microphone stopped responding. Check Windows microphone permissions and your selected input device, then try again.",
                            "unavailable": "No microphone is available. Connect one and check Windows Settings > Privacy & security > Microphone.",
                            "error": "Voice input ran into a problem. Check the microphone and try again.",
                        }[reason]
                        self._add_nova_message(guidance, is_error=True)
                        self._set_status("error", "Voice input stopped")
                    elif self._auto_listen and not self._processing:
                        self.after(200, self._start_microphone)
                    else:
                        detail = "No speech detected" if reason == "timeout" else "Speech not understood"
                        self._set_status("idle", detail)

                elif msg_type == "status":
                    self._set_status(msg.get("status", "idle"))

                elif msg_type == "mic_worker_done":
                    self._mic_btn.configure(
                        fg_color=_BG_SIDEBAR,
                        text_color=_TEXT_SECONDARY,
                        text="🎤",
                    )
                    if self._auto_listen and not self._processing:
                        self.after(200, self._start_microphone)

                elif msg_type == "mic_status":
                    status = msg.get("status", "idle")
                    self._set_status(status)

                elif msg_type == "error":
                    error_msg = msg.get("error", "Unknown error")
                    self._add_nova_message(
                        f"An error occurred: {error_msg}",
                        is_error=True,
                    )
                    self._set_status("error")
                    self.after(3000, lambda: self._set_status("idle"))

                # Re-enable input
                if msg_type in ("command_result", "error"):
                    self._processing = False
                    self._send_btn.configure(state="normal", fg_color=_ACCENT)
                    self._text_entry.configure(state="normal")
                    self._text_entry.focus_set()

                    # If Continuous Auto-Listen is active, automatically resume listening after spoken response
                    if self._auto_listen:
                        logger.info("Continuous Mic resuming after assistant response playback completed.")
                        self.after(800, self._start_microphone)

        except queue.Empty:
            pass
        finally:
            # Schedule next poll (60ms interval for responsive feel)
            self.after(60, self._poll_results)

    # ═══════════════════════════════════════════════════════════════════
    #  MICROPHONE & VOICE CONTROLS
    # ═══════════════════════════════════════════════════════════════════

    def _on_voice_switch_toggled(self) -> None:
        """Toggle text-to-speech spoken audio output."""
        self._voice_enabled = bool(self._voice_switch.get())
        self._speaker._voice_mode = self._voice_enabled
        if hasattr(self, "_voice_status_val"):
            self._voice_status_val.configure(
                text="Active" if self._voice_enabled else "Muted",
                text_color=_SUCCESS if self._voice_enabled else _TEXT_SECONDARY,
            )
        logger.info("Voice speech mode set to %s", self._voice_enabled)

    def _on_auto_listen_toggled(self) -> None:
        """Toggle continuous voice listening loop."""
        self._auto_listen = bool(self._auto_listen_switch.get())
        logger.info("Auto-listen continuous mode set to %s", self._auto_listen)
        if self._auto_listen and not self._mic_active and not self._processing:
            self._start_microphone()
        elif not self._auto_listen and self._mic_active:
            self._stop_microphone()

    def _toggle_microphone(self) -> None:
        """Start or stop microphone listening."""
        if self._mic_active:
            self._stop_microphone()
        else:
            self._start_microphone()

    def _start_microphone(self) -> None:
        """Start listening for voice input in a background thread."""
        if self._mic_active or self._processing:
            return
        # SpeechRecognition capture/transcription is blocking. Never start a
        # second worker until the previous one has completely released audio.
        if self._mic_thread is not None and self._mic_thread.is_alive():
            return

        # Lazy-init listener on the assistant if needed
        if self._assistant.listener is None:
            from core.listener import Listener
            self._assistant.listener = Listener(settings=self._settings)

        if not self._assistant.listener.is_available():
            self._auto_listen = False
            if hasattr(self, "_auto_listen_switch"):
                self._auto_listen_switch.deselect()
            self._add_nova_message(
                "No microphone is available. Connect one and check Windows Settings > Privacy & security > Microphone, then try again.",
                is_error=True,
            )
            self._set_status("error", "Microphone unavailable")
            return

        self._mic_active = True
        self._mic_stop_event.clear()
        self._mic_btn.configure(fg_color=_MIC_ACTIVE, text_color="white", text="⏹")
        self._set_status("listening")
        logger.info("Microphone listening started (continuous=%s).", self._auto_listen)

        def _mic_worker() -> None:
            try:
                recognized = self._assistant.listener.listen()
                if self._mic_stop_event.is_set():
                    return

                if recognized:
                    self._result_queue.put({"type": "mic_result", "text": recognized})
                else:
                    reason = getattr(self._assistant.listener, "last_error", None) or "timeout"
                    self._result_queue.put({"type": "mic_empty", "reason": reason})

            except Exception as exc:
                logger.error("Microphone error: %s", exc)
                self._result_queue.put({
                    "type": "mic_empty",
                    "reason": "error",
                })
            finally:
                self._mic_active = False
                self._result_queue.put({"type": "mic_worker_done"})

        self._mic_thread = threading.Thread(target=_mic_worker, daemon=True, name="nova-mic")
        self._mic_thread.start()

    def _stop_microphone(self) -> None:
        """Signal the microphone listener to stop."""
        self._mic_stop_event.set()
        self._mic_btn.configure(fg_color=_BG_SIDEBAR, text_color=_TEXT_SECONDARY, text="🎤")
        self._set_status("idle")

    # ═══════════════════════════════════════════════════════════════════
    #  SHUTDOWN
    # ═══════════════════════════════════════════════════════════════════

    def _on_close(self) -> None:
        """Clean shutdown of the application."""
        logger.info("Nova GUI shutting down.")
        self._mic_stop_event.set()
        self._mic_active = False
        try:
            self._speaker.stop()
        except Exception:
            pass
        self.destroy()

    # ═══════════════════════════════════════════════════════════════════
    #  PUBLIC API (for testing)
    # ═══════════════════════════════════════════════════════════════════

    @property
    def assistant(self) -> Assistant:
        """Access the underlying assistant instance."""
        return self._assistant

    @property
    def is_processing(self) -> bool:
        """Whether a command is currently being processed."""
        return self._processing

    @property
    def is_mic_active(self) -> bool:
        """Whether the microphone is currently active."""
        return self._mic_active

    def submit_text_programmatic(self, text: str) -> None:
        """Submit text as if the user typed it. For testing."""
        self._text_entry.delete(0, "end")
        self._text_entry.insert(0, text)
        self._submit_text()


def launch_gui(settings: Optional[Settings] = None, voice_enabled: bool = True) -> None:
    """Create and run the Nova GUI application."""
    app = NovaGUI(settings=settings, voice_enabled=voice_enabled)
    app.mainloop()
