"""Unit tests for src.llm.providers.openai_compatible."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import requests

from src.llm.providers.base import ChatMessage, ProviderConfig, ProviderStatus
from src.llm.providers.openai_compatible import OpenAICompatibleProvider


def _fake_response(payload, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return resp


def test_generate_success_populates_metadata_and_stats():
    provider = OpenAICompatibleProvider(
        ProviderConfig(name="openai", base_url="http://api", model="m")
    )
    session = MagicMock()
    session.post.return_value = _fake_response(
        {
            "id": "cmp-1",
            "model": "m",
            "created": 1,
            "choices": [{"text": "hello", "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
        }
    )
    provider._session = session

    out = provider.generate("prompt", stop=["x"], presence_penalty=0.1)
    assert out.text == "hello"
    assert out.tokens_used == 5
    assert out.metadata["id"] == "cmp-1"
    assert provider.get_stats()["total_tokens"] == 5


def test_generate_connection_error_sets_unavailable_status():
    provider = OpenAICompatibleProvider(ProviderConfig(name="openai"))
    session = MagicMock()
    session.post.side_effect = requests.exceptions.ConnectionError("no route")
    provider._session = session

    with pytest.raises(ConnectionError):
        provider.generate("prompt")
    assert provider.status == ProviderStatus.UNAVAILABLE


def test_chat_success_and_tool_calls_metadata():
    provider = OpenAICompatibleProvider(ProviderConfig(name="openai", base_url="http://api", model="m"))
    session = MagicMock()
    session.post.return_value = _fake_response(
        {
            "id": "chat-1",
            "model": "m",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": "ok",
                        "tool_calls": [{"id": "t1"}],
                    },
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }
    )
    provider._session = session

    out = provider.chat([ChatMessage(role="user", content="hi")], tools=[{"name": "x"}])
    assert out.text == "ok"
    assert out.metadata["tool_calls"] == [{"id": "t1"}]
    assert out.tokens_used == 2


def test_embed_returns_single_or_list_and_health_models():
    provider = OpenAICompatibleProvider(ProviderConfig(name="openai", base_url="http://api", model="m"))
    session = MagicMock()
    session.post.return_value = _fake_response(
        {
            "model": "embed-m",
            "data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3]}],
            "usage": {"total_tokens": 4},
        }
    )
    session.get.side_effect = [
        _fake_response({"data": [{"id": "m1"}]}, status_code=200),  # health_check
        _fake_response({"data": [{"id": "m1"}, {"id": "m2"}]}, status_code=200),  # list_models
    ]
    provider._session = session

    one = provider.embed("hello")
    many = provider.embed(["a", "b"])
    assert one.embedding == [0.1, 0.2]
    assert len(many) == 2
    assert provider.health_check() is True
    assert provider.status == ProviderStatus.AVAILABLE
    assert provider.list_models() == [{"id": "m1"}, {"id": "m2"}]
