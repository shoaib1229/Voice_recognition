"""
commands/weather_commands.py
============================
Weather command querying OpenWeather REST service.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from commands.base import BaseCommand, CommandResult
from core.context import Context
from services.weather_service import WeatherService
from utils.normalizer import normalize_intent


class WeatherCommand(BaseCommand):
    """Retrieves current weather conditions for a requested city."""

    name = "info.weather"
    aliases = [
        "weather in",
        "what is the weather in",
        "what's the weather in",
        "temperature in",
        "how is the weather in",
        "weather report for",
    ]
    priority = 15
    description = "Gets current weather for a city."

    def __init__(self, weather_service: Optional[WeatherService] = None) -> None:
        self.weather = weather_service or WeatherService()

    def matches(self, text: str) -> float:
        norm = normalize_intent(text)
        if "weather" in norm or "temperature" in norm:
            return 0.95
        return 0.0

    def extract_params(self, text: str) -> dict[str, Any]:
        norm = normalize_intent(text)
        for pattern in (
            r"(?:weather|temperature)\s+(?:in|for|at)\s+([a-zA-Z\s]+)",
            r"how\s+is\s+the\s+weather\s+in\s+([a-zA-Z\s]+)",
        ):
            match = re.search(pattern, norm)
            if match:
                city = match.group(1).strip()
                # Clean up punctuation
                city = re.sub(r"[^\w\s]", "", city).strip()
                return {"city": city}

        # Fallback: check if ends with city after "weather"
        parts = norm.split("weather")
        if len(parts) > 1 and parts[1].strip():
            candidate = parts[1].replace("in", "").replace("for", "").strip()
            if candidate:
                return {"city": candidate}

        return {}

    def execute(self, params: dict[str, Any], context: Context) -> CommandResult:
        city = params.get("city", "").strip()
        if not city:
            return CommandResult.fail(
                self.name,
                "Please specify which city you would like the weather for.",
                error="Missing city parameter",
            )

        weather_data, message = self.weather.get_weather(city)
        if weather_data is not None:
            return CommandResult.ok(
                self.name,
                message,
                data={
                    "city": weather_data.city,
                    "temp_c": weather_data.temperature_c,
                    "desc": weather_data.description,
                },
            )
        return CommandResult.fail(self.name, message, error=message)


def create_weather_commands(weather_service: Optional[WeatherService] = None) -> list[BaseCommand]:
    """Factory creating weather commands."""
    return [WeatherCommand(weather_service)]
