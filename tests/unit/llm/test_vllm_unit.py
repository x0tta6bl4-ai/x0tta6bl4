"""Unit tests for src.llm.providers.vllm."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import requests

from src.llm.providers.base import ChatMessage, ProviderConfig, ProviderStatus
from src.llm.providers.vllm import VLLMProvider


def _fake_response(payload, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return resp


def test_generate_success_and_vllm_specific_payload():
    provider = VLLMProvider(ProviderConfig(name="vllm", base_url="http://v", model="m"))
    session = MagicMock()
    session.post.return_value = _fake_response(
        {
            "id": "cmp-v1",
            "model": "m",
            "choices": [{"text": "v out", "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        }
    )
    provider._session = session

    out = provider.generate("prompt", top_k=10, repetition_penalty=1.1, best_of=2)
    assert out.text == "v out"
    assert out.tokens_used == 3
    assert out.metadata["id"] == "cmp-v1"
    assert provider.get_stats()["total_tokens"] == 3


def test_generate_connection_error_sets_unavailable():
    provider = VLLMProvider(ProviderConfig(name="vllm"))
    session = MagicMock()
    session.post.side_effect = requests.exceptions.ConnectionError("down")
    provider._session = session

    with pytest.raises(ConnectionError):
        provider.generate("x")
    assert provider.status == ProviderStatus.UNAVAILABLE


def test_chat_success():
    provider = VLLMProvider(ProviderConfig(name="vllm", base_url="http://v", model="m"))
    session = MagicMock()
    session.post.return_value = _fake_response(
        {
            "model": "m",
            "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": "ok"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }
    )
    provider._session = session

    out = provider.chat([ChatMessage(role="user", content="hi")])
    assert out.text == "ok"
    assert out.tokens_used == 2


def test_health_and_model_info():
    provider = VLLMProvider(ProviderConfig(name="vllm", base_url="http://v", model="m"))
    session = MagicMock()
    session.get.side_effect = [
        _fake_response({}, status_code=200),  # health
        _fake_response({"data": [{"id": "m"}]}, status_code=200),  # model info
    ]
    provider._session = session

    assert provider.health_check() is True
    assert provider.status == ProviderStatus.AVAILABLE
    assert provider.get_model_info() == {"data": [{"id": "m"}]}
