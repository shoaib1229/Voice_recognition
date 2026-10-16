"""
commands/__init__.py
====================
Command package initialization and registration aggregator.
"""

from __future__ import annotations

from typing import Optional

from commands.application_commands import create_application_commands
from commands.folder_commands import create_folder_commands
from commands.registry import CommandRegistry
from commands.system_commands import create_system_commands
from commands.utility_commands import create_utility_commands
from commands.weather_commands import create_weather_commands
from commands.web_commands import create_web_commands
from commands.wikipedia_commands import create_wikipedia_commands
from services.app_launcher_service import AppLauncherService
from services.confirmation_service import ConfirmationService
from services.search_service import SearchService
from services.weather_service import WeatherService
from services.wikipedia_service import WikipediaService


def build_default_command_registry(
    launcher: Optional[AppLauncherService] = None,
    search: Optional[SearchService] = None,
    weather: Optional[WeatherService] = None,
    wiki: Optional[WikipediaService] = None,
    confirmation: Optional[ConfirmationService] = None,
) -> CommandRegistry:
    """
    Construct and populate a CommandRegistry with all registered Nova commands.
    """
    registry = CommandRegistry()

    # 1. Application commands (Chrome, VS Code, Notepad, WhatsApp, Spotify, Calc...)
    for cmd in create_application_commands(launcher, confirmation):
        registry.register(cmd)

    # 2. Web commands (Google, YouTube, GitHub, shortcuts, URLs)
    for cmd in create_web_commands(search):
        registry.register(cmd)

    # 3. Folder commands (Downloads, Documents, Desktop, Pictures, Project)
    for cmd in create_folder_commands(launcher):
        registry.register(cmd)

    # 4. System commands (Time, Date, Power)
    for cmd in create_system_commands(confirmation):
        registry.register(cmd)

    # 5. Utility commands (Help, Exit, Clear History)
    for cmd in create_utility_commands():
        registry.register(cmd)

    # 6. Weather command (OpenWeather API)
    for cmd in create_weather_commands(weather):
        registry.register(cmd)

    # 7. Wikipedia command (Wikipedia REST API)
    for cmd in create_wikipedia_commands(wiki):
        registry.register(cmd)

    return registry
