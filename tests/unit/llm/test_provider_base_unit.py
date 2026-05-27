from __future__ import annotations

import pytest

from src.llm.providers.base import (
    BaseLLMProvider,
    GenerationResult,
    ProviderCapabilityError,
    ProviderConfig,
)
from src.llm.providers.openai_compatible import OpenAICompatibleProvider


class _Provider(BaseLLMProvider):
    def generate(self, prompt, max_tokens=None, temperature=None, top_p=None, stop=None, **kwargs):
        return GenerationResult(text="ok", model="m", provider=self.name)

    def chat(self, messages, max_tokens=None, temperature=None, **kwargs):
        return GenerationResult(text="ok", model="m", provider=self.name)

    async def generate_async(self, prompt, max_tokens=None, temperature=None, **kwargs):
        return self.generate(prompt, max_tokens=max_tokens, temperature=temperature, **kwargs)

    async def chat_async(self, messages, max_tokens=None, temperature=None, **kwargs):
        return self.chat(messages, max_tokens=max_tokens, temperature=temperature, **kwargs)


def test_base_provider_reports_embedding_capability_explicitly():
    provider = _Provider(ProviderConfig(name="plain", model="m"))

    assert provider.supports_embeddings() is False
    with pytest.raises(ProviderCapabilityError, match="does not support embeddings"):
        provider.embed("hello")


def test_openai_compatible_provider_reports_embedding_support():
    provider = OpenAICompatibleProvider(
        ProviderConfig(name="openai-compatible", base_url="http://localhost", model="m")
    )

    assert provider.supports_embeddings() is True


def test_provider_capability_error_is_exported_from_package():
    from src.llm.providers import ProviderCapabilityError as providers_error
    from src.llm import ProviderCapabilityError as package_error

    assert providers_error is ProviderCapabilityError
    assert package_error is ProviderCapabilityError
