"""
services/app_launcher_service.py
================================
Safe desktop application and folder launcher service.

Security Architecture:
- Enforces strict allowlist lookups against config/app_registry.py.
- NEVER uses shell=True or executes arbitrary shell strings.
- Only executes resolved, verified binaries from an allowlist.
- Provides fallback to web versions (e.g. WhatsApp Web, Spotify Web)
  when desktop executables are not installed.
"""

from __future__ import annotations

import getpass
import os
import platform
import shutil
import subprocess
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from config.app_registry import (
    ALLOWED_APPS,
    ALLOWED_FOLDERS,
    AppEntry,
    FolderEntry,
    FORBIDDEN_KEYWORDS,
)
from config.settings import Settings, settings as global_settings
from utils.helpers import contains_forbidden
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class LaunchResult:
    """Structured result returned by application and folder launching operations."""
    success: bool
    message: str
    target: str
    fallback_used: bool = False


class AppLauncherService:
    """
    Safely resolves and launches allowlisted desktop applications and folder shortcuts.
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self._settings = settings or global_settings
        self.os_type = platform.system().lower()  # 'windows', 'linux', 'darwin'

    def resolve_app_path(self, app_key: str, entry: AppEntry) -> Optional[str]:
        """
        Resolve the real filesystem path for an application.
        Order of precedence:
          1. Explicit path in settings (.env override)
          2. Known Windows filesystem installation paths
          3. System PATH detection (shutil.which)
        """
        # 1. Check configured setting override
        setting_map = {
            "chrome": self._settings.CHROME_PATH,
            "edge": self._settings.EDGE_PATH,
            "vscode": self._settings.VSCODE_PATH,
            "whatsapp": self._settings.WHATSAPP_PATH,
            "spotify": self._settings.SPOTIFY_PATH,
        }
        custom_path = setting_map.get(app_key, "").strip()
        if custom_path and os.path.isfile(custom_path):
            logger.debug("Resolved %s from custom setting: %s", app_key, custom_path)
            return custom_path

        # 2. Check known Windows filesystem paths
        username = getpass.getuser()
        for template in entry.known_paths:
            try:
                expanded = template.format(username=username)
                expanded = os.path.expandvars(expanded)
                if os.path.isfile(expanded):
                    logger.debug("Resolved %s from known path: %s", app_key, expanded)
                    return expanded
            except Exception as exc:
                logger.debug("Error checking known path template %r: %s", template, exc)

        # 3. Check system PATH via shutil.which
        which_path = shutil.which(entry.executable)
        if which_path and os.path.isfile(which_path):
            logger.debug("Resolved %s from system PATH: %s", app_key, which_path)
            return which_path

        return None

    def launch_app(self, app_key: str) -> LaunchResult:
        """
        Launch an allowlisted application by its registry key.

        Args:
            app_key: Canonical application key (e.g. 'chrome', 'whatsapp', 'vscode').

        Returns:
            LaunchResult describing success, failure, or web fallback.
        """
        clean_key = app_key.strip().lower()

        # Security check: Forbidden keywords
        if contains_forbidden(clean_key, FORBIDDEN_KEYWORDS):
            logger.warning("Security alert: Attempted launch of forbidden target: %r", clean_key)
            return LaunchResult(
                success=False,
                message=f"Action '{clean_key}' is restricted and cannot be executed.",
                target=clean_key,
            )

        if clean_key not in ALLOWED_APPS:
            logger.info("Application not in allowlist: %r", clean_key)
            return LaunchResult(
                success=False,
                message=f"I don't have '{clean_key}' in my registered applications list.",
                target=clean_key,
            )

        entry = ALLOWED_APPS[clean_key]
        resolved_path = self.resolve_app_path(clean_key, entry)

        if resolved_path:
            try:
                logger.info("Launching desktop application: %s (%s)", entry.display_name, resolved_path)
                # Launch detached without shell=True to avoid hanging or shell injection
                creationflags = 0
                if self.os_type == "windows":
                    creationflags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

                subprocess.Popen(
                    [resolved_path],
                    creationflags=creationflags,
                    close_fds=True,
                )
                return LaunchResult(
                    success=True,
                    message=f"Opening {entry.display_name}.",
                    target=resolved_path,
                )
            except Exception as exc:
                logger.error("Failed to spawn process for %s: %s", entry.display_name, exc)
                return LaunchResult(
                    success=False,
                    message=f"Could not open {entry.display_name}: {exc}",
                    target=resolved_path,
                )

        # If desktop binary is missing, test web fallback
        if entry.web_fallback:
            logger.info("Desktop binary for %s missing; launching web fallback: %s", entry.display_name, entry.web_fallback)
            try:
                webbrowser.open(entry.web_fallback)
                return LaunchResult(
                    success=True,
                    message=f"{entry.display_name} desktop app is not installed. Opening {entry.display_name} Web instead.",
                    target=entry.web_fallback,
                    fallback_used=True,
                )
            except Exception as exc:
                logger.error("Web fallback failed for %s: %s", entry.display_name, exc)
                return LaunchResult(
                    success=False,
                    message=f"Could not open {entry.display_name} Web: {exc}",
                    target=entry.web_fallback,
                )

        # No binary and no fallback
        logger.warning("Application %s is not installed and has no web fallback.", entry.display_name)
        return LaunchResult(
            success=False,
            message=f"{entry.display_name} is not installed or could not be found on this computer.",
            target=clean_key,
        )

    def open_folder(self, folder_key: str) -> LaunchResult:
        """
        Open an allowlisted folder shortcut in the system file manager.

        Args:
            folder_key: Canonical folder key (e.g. 'downloads', 'documents', 'desktop', 'project').
        """
        clean_key = folder_key.strip().lower()

        # Handle custom project folder
        if clean_key == "project":
            project_path = self._settings.PROJECT_FOLDER
            if not project_path or not os.path.isdir(project_path):
                return LaunchResult(
                    success=False,
                    message="Project folder is not configured. Set PROJECT_FOLDER in .env.",
                    target="project",
                )
            resolved_dir = project_path
            display_name = "Project Folder"
        else:
            if clean_key not in ALLOWED_FOLDERS:
                return LaunchResult(
                    success=False,
                    message=f"I don't have '{clean_key}' in my allowed folders list.",
                    target=clean_key,
                )
            entry = ALLOWED_FOLDERS[clean_key]
            display_name = entry.display_name
            resolved_dir = os.path.expandvars(entry.path_template)

        if not os.path.isdir(resolved_dir):
            return LaunchResult(
                success=False,
                message=f"The {display_name} folder does not exist at {resolved_dir}.",
                target=resolved_dir,
            )

        try:
            logger.info("Opening folder: %s (%s)", display_name, resolved_dir)
            if self.os_type == "windows":
                os.startfile(resolved_dir)
            elif self.os_type == "darwin":
                subprocess.Popen(["open", resolved_dir])
            else:
                subprocess.Popen(["xdg-open", resolved_dir])

            return LaunchResult(
                success=True,
                message=f"Opening {display_name}.",
                target=resolved_dir,
            )
        except Exception as exc:
            logger.error("Failed to open folder %s: %s", display_name, exc)
            return LaunchResult(
                success=False,
                message=f"Could not open {display_name}: {exc}",
                target=resolved_dir,
            )
