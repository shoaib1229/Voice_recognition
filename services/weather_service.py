"""
services/weather_service.py
===========================
REST API client for OpenWeatherMap.

Security Rules:
- API key is loaded via constructor or settings (never hardcoded).
- Enforces explicit HTTP timeouts (5 seconds).
- Safely parses JSON payloads and handles 404/401/timeout/network errors.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import requests

from config.settings import Settings, settings as global_settings
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class WeatherData:
    """Structured weather information for spoken response and UI display."""
    city: str
    temperature_c: float
    description: str
    humidity_percent: int
    wind_speed_mps: float
    spoken_summary: str


class WeatherService:
    """
    Fetches real-time weather reports from OpenWeatherMap REST API.
    """

    def __init__(self, settings: Optional[Settings] = None, timeout: float = 5.0) -> None:
        self._settings = settings or global_settings
        self.timeout = timeout
        self.api_key = (self._settings.OPENWEATHER_API_KEY or "").strip()

    def get_weather(self, city: str) -> tuple[Optional[WeatherData], str]:
        """
        Fetch weather for *city*.

        Returns:
            Tuple of (WeatherData | None, user_message: str).
        """
        clean_city = city.strip()
        if not clean_city:
            return None, "Please specify a city name to get the weather."

        if not self.api_key or self.api_key == "your_openweather_api_key_here":
            logger.info("Weather requested but OPENWEATHER_API_KEY is not configured.")
            return None, (
                "Weather reports require an OpenWeather API key. "
                "Please configure OPENWEATHER_API_KEY in your .env file."
            )

        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "q": clean_city,
            "appid": self.api_key,
            "units": "metric",
        }

        try:
            logger.debug("Requesting weather for city: %r", clean_city)
            response = requests.get(url, params=params, timeout=self.timeout)

            if response.status_code == 404:
                return None, f"I couldn't find weather information for '{clean_city}'. Please check the city name."

            if response.status_code == 401:
                logger.warning("OpenWeatherMap rejected API key.")
                return None, "The configured OpenWeather API key was rejected."

            response.raise_for_status()
            data = response.json()

            # Parse fields defensively
            city_name = data.get("name", clean_city.title())
            main = data.get("main", {})
            temp = round(float(main.get("temp", 0.0)), 1)
            humidity = int(main.get("humidity", 0))

            weather_list = data.get("weather", [])
            desc = weather_list[0].get("description", "clear skies") if weather_list else "clear skies"
            wind = float(data.get("wind", {}).get("speed", 0.0))

            spoken = (
                f"Currently in {city_name}, it is {temp} degrees Celsius with {desc} "
                f"and {humidity} percent humidity."
            )

            result = WeatherData(
                city=city_name,
                temperature_c=temp,
                description=desc,
                humidity_percent=humidity,
                wind_speed_mps=wind,
                spoken_summary=spoken,
            )
            return result, spoken

        except requests.Timeout:
            logger.warning("Weather API request timed out for city: %r", clean_city)
            return None, "The weather service took too long to respond. Please try again."

        except requests.RequestException as exc:
            logger.error("Network error calling weather API: %s", exc)
            return None, "Could not connect to the weather service. Please check your internet connection."

        except Exception as exc:
            logger.error("Unexpected error parsing weather data: %s", exc)
            return None, "An error occurred while retrieving weather information."
