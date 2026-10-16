"""
config/app_registry.py
======================
Central allowlist for every application, website, and folder that
Nova is permitted to open.  This is the ONLY place where real paths,
URLs, and allowed names are defined.

Design rules:
- Raw speech strings are NEVER passed to subprocess or os.startfile.
- AppLauncherService resolves a registry *key* to an action.
- Any key not present in this registry is rejected before execution.
- Each entry specifies multiple candidate paths so Nova can find the
  application on different Windows installations without needing a
  configured path in .env.

Path resolution order for desktop applications:
  1. Custom path from .env (e.g. CHROME_PATH)
  2. Known Windows installation directories (Program Files etc.)
  3. PATH detection (shutil.which)
  4. Web fallback URL (if defined)
  5. Error — application not available
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AppEntry:
    """Allowlisted desktop application."""
    # Human-readable display name
    display_name: str
    # Executable filename (e.g. "chrome.exe")
    executable: str
    # Ordered list of known Windows installation paths to probe
    known_paths: tuple[str, ...] = field(default_factory=tuple)
    # URL to open if the desktop application is not found (may be None)
    web_fallback: Optional[str] = None


@dataclass(frozen=True)
class SiteEntry:
    """Allowlisted website shortcut."""
    display_name: str
    url: str


@dataclass(frozen=True)
class FolderEntry:
    """Allowlisted folder shortcut."""
    display_name: str
    # Path may contain environment-variable placeholders, e.g. %USERPROFILE%
    path_template: str


# ---------------------------------------------------------------------------
# Application allowlist
# ---------------------------------------------------------------------------

ALLOWED_APPS: dict[str, AppEntry] = {
    "chrome": AppEntry(
        display_name="Google Chrome",
        executable="chrome.exe",
        known_paths=(
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ),
        web_fallback="https://www.google.com",
    ),
    "edge": AppEntry(
        display_name="Microsoft Edge",
        executable="msedge.exe",
        known_paths=(
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ),
        web_fallback=None,
    ),
    "vscode": AppEntry(
        display_name="Visual Studio Code",
        executable="code.exe",
        known_paths=(
            r"C:\Users\{username}\AppData\Local\Programs\Microsoft VS Code\Code.exe",
            r"C:\Program Files\Microsoft VS Code\Code.exe",
        ),
        web_fallback=None,
    ),
    "notepad": AppEntry(
        display_name="Notepad",
        executable="notepad.exe",
        known_paths=(
            r"C:\Windows\System32\notepad.exe",
            r"C:\Windows\notepad.exe",
        ),
        web_fallback=None,
    ),
    "calculator": AppEntry(
        display_name="Calculator",
        executable="calc.exe",
        known_paths=(
            r"C:\Windows\System32\calc.exe",
        ),
        web_fallback=None,
    ),
    "explorer": AppEntry(
        display_name="File Explorer",
        executable="explorer.exe",
        known_paths=(
            r"C:\Windows\explorer.exe",
        ),
        web_fallback=None,
    ),
    "whatsapp": AppEntry(
        display_name="WhatsApp",
        executable="WhatsApp.exe",
        known_paths=(
            r"C:\Users\{username}\AppData\Local\WhatsApp\WhatsApp.exe",
            r"C:\Program Files\WindowsApps\WhatsApp.exe",
        ),
        web_fallback="https://web.whatsapp.com",
    ),
    "spotify": AppEntry(
        display_name="Spotify",
        executable="Spotify.exe",
        known_paths=(
            r"C:\Users\{username}\AppData\Roaming\Spotify\Spotify.exe",
        ),
        web_fallback="https://open.spotify.com",
    ),
}

# ---------------------------------------------------------------------------
# Website shortcut allowlist
# ---------------------------------------------------------------------------

ALLOWED_SITES: dict[str, SiteEntry] = {
    "youtube":      SiteEntry("YouTube",       "https://www.youtube.com"),
    "github":       SiteEntry("GitHub",        "https://www.github.com"),
    "gmail":        SiteEntry("Gmail",         "https://mail.google.com"),
    "linkedin":     SiteEntry("LinkedIn",      "https://www.linkedin.com"),
    "google":       SiteEntry("Google",        "https://www.google.com"),
    "whatsapp_web": SiteEntry("WhatsApp Web",  "https://web.whatsapp.com"),
    "chatgpt":      SiteEntry("ChatGPT",       "https://chatgpt.com"),
    "stackoverflow":SiteEntry("Stack Overflow","https://stackoverflow.com"),
}

# ---------------------------------------------------------------------------
# Folder allowlist
# ---------------------------------------------------------------------------
# %USERPROFILE% and other Windows env-vars are expanded at runtime.
ALLOWED_FOLDERS: dict[str, FolderEntry] = {
    "downloads": FolderEntry("Downloads", r"%USERPROFILE%\Downloads"),
    "documents": FolderEntry("Documents", r"%USERPROFILE%\Documents"),
    "desktop":   FolderEntry("Desktop",   r"%USERPROFILE%\Desktop"),
    "pictures":  FolderEntry("Pictures",  r"%USERPROFILE%\Pictures"),
    "music":     FolderEntry("Music",     r"%USERPROFILE%\Music"),
    # "project" is populated at runtime from settings.PROJECT_FOLDER
}

# ---------------------------------------------------------------------------
# Destructive / dangerous actions — permanently excluded
# ---------------------------------------------------------------------------
# These strings will never appear in any allowlist and must never be
# passed to subprocess, even if speech recognition produces them.
FORBIDDEN_KEYWORDS: frozenset[str] = frozenset({
    "delete", "remove", "format",
    "rm", "del", "rmdir", "rd", "wipe", "kill", "terminate",
    "registry", "regedit", "powershell", "bash",
})
