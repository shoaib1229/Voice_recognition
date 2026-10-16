"""Route and response checks for Nova's separate browser application."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from pydantic import ValidationError

import webapp



def call(coroutine):
    """Run async route bodies that are intentionally await-free."""
    try:
        coroutine.send(None)
    except StopIteration as result:
        return result.value
    raise AssertionError("Route handler unexpectedly performed asynchronous I/O")


def test_health_endpoint():
    assert isinstance(webapp.app, FastAPI)
    assert any(route.path == "/api/health" for route in webapp.app.routes)
    assert call(webapp.health()) == {"status": "ok", "assistant": "Nova"}


def test_chat_supported_and_unsupported_responses():
    assert any(route.path == "/api/chat" for route in webapp.app.routes)
    response = call(webapp.chat(webapp.ChatRequest(message="hello nova")))
    assert "Hi! I'm Nova" in response.reply

    response = call(webapp.chat(webapp.ChatRequest(message="explain quantum gravity")))
    assert "can't answer that offline" in response.reply


def test_web_capabilities_are_informational_only():
    help_response = call(webapp.chat(webapp.ChatRequest(message="what can you do?")))
    assert "look up weather and Wikipedia" in help_response.reply
    assert "control your computer" in help_response.reply

    search_response = call(webapp.chat(webapp.ChatRequest(message="search google for Nova assistant")))
    assert search_response.links[0]["url"].startswith("https://www.google.com/search?")
    assert "q=Nova+assistant" in search_response.links[0]["url"]

    os_command_response = call(webapp.chat(webapp.ChatRequest(message="open notepad")))
    assert "can't answer that offline" in os_command_response.reply


def test_chat_rejects_blank_and_invalid_input():
    response = call(webapp.chat(webapp.ChatRequest(message="   ")))
    assert response.status_code == 422
    assert "must not be blank" in response.body.decode()

    with pytest.raises(ValidationError):
        webapp.ChatRequest(message=12)
    with pytest.raises(ValidationError):
        webapp.ChatRequest(message="x" * (webapp.MAX_MESSAGE_LENGTH + 1))


def test_chat_hides_internal_errors(monkeypatch):
    def explode(_message):
        raise RuntimeError("sensitive internal detail")

    monkeypatch.setattr(webapp, "_reply", explode)
    response = call(webapp.chat(webapp.ChatRequest(message="hello")))
    assert response.status_code == 503
    assert "sensitive internal detail" not in response.body.decode()
    assert "could not process" in response.body.decode().lower()
