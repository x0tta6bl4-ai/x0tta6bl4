"""
Ollama provider stub.

Provides the standard provider interface without requiring optional
runtime dependencies during import-time.
"""

from __future__ import annotations

from time import perf_counter
from typing import List, Optional

from src.llm.providers.base import (
    BaseLLMProvider,
    ChatMessage,
    GenerationResult,
    ProviderConfig,
)


class OllamaProvider(BaseLLMProvider):
    def __init__(self, config: Optional[ProviderConfig] = None):
        super().__init__(config or ProviderConfig(name="ollama"))

    def generate(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        stop: Optional[List[str]] = None,
        **kwargs,
    ) -> GenerationResult:
        start = perf_counter()
        text = f"[ollama:{self.config.model}] {prompt}"
        latency_ms = (perf_counter() - start) * 1000.0
        self._record_request(tokens_used=0, latency_ms=latency_ms, success=True)
        return GenerationResult(
            text=text,
            model=self.config.model,
            provider=self.name,
            tokens_used=0,
            latency_ms=latency_ms,
            finish_reason="stop",
            metadata={"stub": True},
        )

    def chat(
        self,
        messages: List[ChatMessage],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs,
    ) -> GenerationResult:
        prompt = " ".join(m.content for m in messages if m.role == "user") or "..."
        return self.generate(prompt, max_tokens=max_tokens, temperature=temperature, **kwargs)

    async def generate_async(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs,
    ) -> GenerationResult:
        return self.generate(prompt, max_tokens=max_tokens, temperature=temperature, **kwargs)

    async def chat_async(
        self,
        messages: List[ChatMessage],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs,
    ) -> GenerationResult:
        return self.chat(messages, max_tokens=max_tokens, temperature=temperature, **kwargs)


__all__ = ["OllamaProvider"]

