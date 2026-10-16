"""Same-origin FastAPI web interface for Nova.

The web API deliberately exposes informational chat only. It never routes
requests through the desktop command registry or executes operating-system
actions.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import requests

from core.local_fallback import LocalFallbackHandler
from config.settings import settings
from services.wikipedia_service import WikipediaService

logger = logging.getLogger("nova.web")
WEB_DIR = Path(__file__).resolve().parent / "web"
MAX_MESSAGE_LENGTH = 1000
local_fallback = LocalFallbackHandler()
wikipedia_service = WikipediaService()

app = FastAPI(title="Nova", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


class SecurityHeadersMiddleware:
    """Add browser safety headers without changing request handling."""

    def __init__(self, downstream):
        self.downstream = downstream

    async def __call__(self, scope, receive, send):
        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend([
                    (b"content-security-policy", b"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"),
                    (b"x-content-type-options", b"nosniff"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"x-frame-options", b"DENY"),
                ])
                message["headers"] = headers
            await send(message)

        await self.downstream(scope, receive, send_with_headers)


app.add_middleware(SecurityHeadersMiddleware)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)


class ChatResponse(BaseModel):
    reply: str
    links: list[dict[str, str]] = Field(default_factory=list)


@app.get("/", include_in_schema=False)
async def home():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/api/health")
async def health():
    return {"status": "ok", "assistant": "Nova"}


def _clean_message(message: str) -> str:
    return " ".join(message.strip().split())


def _weather_reply(city: str) -> str:
    """Fetch optional weather without logging request URLs or secret parameters."""
    clean_city = city.strip()
    api_key = settings.OPENWEATHER_API_KEY.strip()
    if not clean_city:
        return "Please specify a city name to get the weather."
    if not api_key or api_key == "your_openweather_api_key_here":
        return "Live weather needs OPENWEATHER_API_KEY configured on the server. Other Nova features work without it."
    try:
        response = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"q": clean_city, "appid": api_key, "units": "metric"},
            timeout=5,
        )
        if response.status_code == 404:
            return f"I couldn't find weather information for '{clean_city}'. Please check the city name."
        if response.status_code == 401:
            return "The configured weather service key was rejected."
        response.raise_for_status()
        data = response.json()
        city_name = data.get("name", clean_city.title())
        temperature = round(float(data.get("main", {}).get("temp", 0.0)), 1)
        humidity = int(data.get("main", {}).get("humidity", 0))
        weather = data.get("weather", [])
        description = weather[0].get("description", "clear skies") if weather else "clear skies"
        return f"Currently in {city_name}, it is {temperature} degrees Celsius with {description} and {humidity} percent humidity."
    except requests.Timeout:
        return "The weather service took too long to respond. Please try again."
    except requests.RequestException:
        logger.warning("Weather lookup failed (%s)", "network error")
        return "Could not connect to the weather service. Please check your internet connection."
    except (KeyError, TypeError, ValueError):
        logger.warning("Weather response could not be parsed")
        return "An error occurred while retrieving weather information."


def _reply(message: str) -> ChatResponse:
    normalized = re.sub(r"[^\w\s']", "", message.lower()).strip()

    if normalized in {
        "help", "what can you do", "what can you help me with", "what do you do",
        "how can you help", "what can nova do",
    }:
        return ChatResponse(
            reply="I can chat about simple everyday patterns, tell the local time or date, look up weather and Wikipedia summaries, and give you web search links. I can't control your computer or answer general questions offline."
        )

    if normalized in {"what time is it", "tell me the time", "time"}:
        return ChatResponse(reply=f"The current time is {datetime.now().astimezone().strftime('%I:%M %p').lstrip('0')}.")
    if normalized in {"what is the date", "what is today's date", "today's date", "date"}:
        now = datetime.now().astimezone()
        return ChatResponse(reply=f"Today is {now.strftime('%A, %B')} {now.day}, {now.year}.")

    weather_match = re.fullmatch(r"(?:what is )?(?:the )?weather(?: like)?(?: in| for)\s+(.+)", message, re.IGNORECASE)
    if weather_match:
        return ChatResponse(reply=_weather_reply(weather_match.group(1)))

    wiki_match = re.fullmatch(r"(?:wikipedia|wiki|look up|tell me about)\s+(.+)", message, re.IGNORECASE)
    if wiki_match:
        summary, reply = wikipedia_service.search_summary(wiki_match.group(1))
        links = ([{"label": summary.title, "url": summary.page_url}] if summary and summary.page_url else [])
        return ChatResponse(reply=reply, links=links)

    search_match = re.fullmatch(r"(?:search(?: the web| google)? for|web search)\s+(.+)", message, re.IGNORECASE)
    if search_match:
        query = search_match.group(1).strip()
        if query:
            url = "https://www.google.com/search?q=" + quote_plus(query)
            return ChatResponse(reply=f"Here is a web search for {query}.", links=[{"label": "Open search results", "url": url}])

    result = local_fallback.respond(message)
    if result and result.success:
        return ChatResponse(reply=result.spoken_response)
    return ChatResponse(
        reply="I can't answer that offline. I can help with greetings, help, time, date, weather, Wikipedia lookups, and web searches."
    )


@app.post("/api/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest):
    message = _clean_message(payload.message)
    if not message:
        return JSONResponse(status_code=422, content={"detail": "Message must not be blank."})
    try:
        return _reply(message)
    except Exception as exc:
        # Keep internals and user content out of responses and logs.
        logger.error("Chat handler failed (%s)", type(exc).__name__)
        return JSONResponse(status_code=503, content={"detail": "Nova could not process that request right now. Please try again."})

