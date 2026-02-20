"""
LLM Module for x0tta6bl4 MaaS Platform
======================================

Multi-provider LLM Gateway with semantic caching, rate limiting,
and seamless integration with ConsciousnessEngine and MAPE-K loop.

Supported Providers:
- Local (llama-cpp-python)
- Ollama
- vLLM
- OpenAI-compatible APIs

Features:
- Multi-provider failover and load balancing
- Semantic caching for response deduplication
- Token bucket and sliding window rate limiting
- ConsciousnessEngine integration for self-healing decisions
- MAPE-K loop integration for autonomous operations
"""

from src.llm.local_llm import LocalLLM, LLAMA_AVAILABLE
from src.llm.gateway import LLMGateway, LLMProvider, LLMConfig, create_gateway
from src.llm.semantic_cache import SemanticCache, CacheEntry
from src.llm.rate_limiter import (
    RateLimiter,
    RateLimitConfig,
    RateLimitStrategy,
    MultiProviderRateLimiter,
)
from src.llm.providers.base import (
    BaseLLMProvider,
    ProviderConfig,
    ProviderStatus,
    GenerationResult,
    ChatMessage,
    EmbeddingResult,
)
from src.llm.providers.ollama import OllamaProvider
from src.llm.providers.vllm import VLLMProvider
from src.llm.providers.openai_compatible import OpenAICompatibleProvider
from src.llm.consciousness_integration import (
    ConsciousnessLLMIntegration,
    SystemAnalysis,
    HealingDecision,
    create_consciousness_integration,
)

__all__ = [
    # Gateway
    "LLMGateway",
    "LLMProvider",
    "LLMConfig",
    "create_gateway",
    # Local LLM
    "LocalLLM",
    "LLAMA_AVAILABLE",
    # Semantic Cache
    "SemanticCache",
    "CacheEntry",
    # Rate Limiter
    "RateLimiter",
    "RateLimitConfig",
    "RateLimitStrategy",
    "MultiProviderRateLimiter",
    # Providers
    "BaseLLMProvider",
    "ProviderConfig",
    "ProviderStatus",
    "GenerationResult",
    "ChatMessage",
    "EmbeddingResult",
    "OllamaProvider",
    "VLLMProvider",
    "OpenAICompatibleProvider",
    # Consciousness Integration
    "ConsciousnessLLMIntegration",
    "SystemAnalysis",
    "HealingDecision",
    "create_consciousness_integration",
]
