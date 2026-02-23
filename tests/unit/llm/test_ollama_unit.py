"""Unit tests for src.llm.providers.ollama."""

from __future__ import annotations

import pytest

from src.llm.providers.base import ChatMessage, ProviderConfig
from src.llm.providers.ollama import OllamaProvider


def test_generate_returns_stub_payload_and_updates_stats():
    provider = OllamaProvider(ProviderConfig(name="ollama", model="tiny"))

    result = provider.generate("hello world")
    assert result.text == "[ollama:tiny] hello world"
    assert result.model == "tiny"
    assert result.provider == "ollama"
    assert result.finish_reason == "stop"
    assert result.metadata["stub"] is True
    assert result.latency_ms >= 0.0

    stats = provider.get_stats()
    assert stats["request_count"] == 1
    assert stats["total_tokens"] == 0
    assert stats["avg_latency_ms"] >= 0.0


def test_chat_uses_only_user_messages():
    provider = OllamaProvider(ProviderConfig(name="ollama", model="stub"))
    messages = [
        ChatMessage(role="system", content="rules"),
        ChatMessage(role="user", content="first"),
        ChatMessage(role="assistant", content="ack"),
        ChatMessage(role="user", content="second"),
    ]

    result = provider.chat(messages)
    assert result.text == "[ollama:stub] first second"


@pytest.mark.asyncio
async def test_async_methods_delegate_to_sync():
    provider = OllamaProvider(ProviderConfig(name="ollama", model="stub"))
    gen = await provider.generate_async("async prompt")
    assert gen.text == "[ollama:stub] async prompt"

    chat = await provider.chat_async([ChatMessage(role="user", content="ping")])
    assert chat.text == "[ollama:stub] ping"

    stats = provider.get_stats()
    assert stats["request_count"] == 2
