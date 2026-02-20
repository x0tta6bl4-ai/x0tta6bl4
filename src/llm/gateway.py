"""
LLM Gateway - Multi-Provider Orchestration
==========================================

Central gateway for managing multiple LLM providers with
automatic failover, load balancing, and intelligent routing.
"""

import asyncio
import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, Union

from src.llm.providers.base import (
    BaseLLMProvider,
    ChatMessage,
    EmbeddingResult,
    GenerationResult,
    ProviderConfig,
    ProviderStatus,
)
from src.llm.rate_limiter import (
    MultiProviderRateLimiter,
    RateLimitConfig,
    RateLimiter,
)
from src.llm.semantic_cache import CacheEntry, SemanticCache

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """Supported LLM providers."""
    LOCAL = "local"
    OLLAMA = "ollama"
    VLLM = "vllm"
    OPENAI = "openai"
    AZURE = "azure"
    CUSTOM = "custom"
    MOCK = "mock"


@dataclass
class LLMConfig:
    """Configuration for LLM Gateway."""
    default_provider: LLMProvider = LLMProvider.LOCAL
    enable_cache: bool = True
    cache_ttl_seconds: int = 3600
    cache_max_size: int = 1000
    enable_rate_limiting: bool = True
    requests_per_minute: int = 60
    tokens_per_minute: int = 100000
    failover_enabled: bool = True
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    timeout_seconds: float = 30.0
    load_balance_strategy: str = "round_robin"  # round_robin, least_latency, random


@dataclass
class ProviderMetrics:
    """Metrics for a single provider."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_tokens: int = 0
    total_latency_ms: float = 0.0
    last_request_time: Optional[datetime] = None
    last_error: Optional[str] = None
    
    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests
    
    @property
    def avg_latency_ms(self) -> float:
        if self.successful_requests == 0:
            return 0.0
        return self.total_latency_ms / self.successful_requests


class LLMGateway:
    """
    Multi-provider LLM Gateway.
    
    Features:
    - Multiple provider support (Local, Ollama, vLLM, OpenAI, etc.)
    - Automatic failover between providers
    - Load balancing strategies
    - Semantic caching
    - Rate limiting per provider
    - Request logging and metrics
    - Thread-safe operations
    """
    
    def __init__(self, config: Optional[LLMConfig] = None):
        """
        Initialize LLM Gateway.
        
        Args:
            config: Gateway configuration
        """
        self.config = config or LLMConfig()
        self._providers: Dict[str, BaseLLMProvider] = {}
        self._provider_order: List[str] = []
        self._metrics: Dict[str, ProviderMetrics] = defaultdict(ProviderMetrics)
        self._lock = threading.RLock()
        
        # Initialize cache
        self._cache: Optional[SemanticCache] = None
        if self.config.enable_cache:
            self._cache = SemanticCache(
                max_size=self.config.cache_max_size,
                ttl_seconds=self.config.cache_ttl_seconds,
            )
        
        # Initialize rate limiter
        self._rate_limiter: Optional[MultiProviderRateLimiter] = None
        if self.config.enable_rate_limiting:
            self._rate_limiter = MultiProviderRateLimiter()
        
        # Load balancing state
        self._current_provider_index = 0
        
    def register_provider(
        self,
        provider: BaseLLMProvider,
        set_default: bool = False,
        rate_limit_config: Optional[RateLimitConfig] = None,
    ) -> None:
        """
        Register an LLM provider.
        
        Args:
            provider: Provider instance
            set_default: Set as default provider
            rate_limit_config: Rate limit configuration for this provider
        """
        with self._lock:
            self._providers[provider.name] = provider
            if provider.name not in self._provider_order:
                self._provider_order.append(provider.name)
            
            if set_default or len(self._providers) == 1:
                try:
                    self.config.default_provider = LLMProvider(provider.name)
                except ValueError:
                    self.config.default_provider = LLMProvider.CUSTOM
            
            # Register with rate limiter
            if self._rate_limiter:
                self._rate_limiter.register(
                    provider.name,
                    rate_limit_config or RateLimitConfig(
                        requests_per_minute=self.config.requests_per_minute,
                        tokens_per_minute=self.config.tokens_per_minute,
                    )
                )
            
            logger.info(f"Registered LLM provider: {provider.name}")
    
    def unregister_provider(self, name: str) -> bool:
        """Remove a provider from the gateway."""
        with self._lock:
            if name in self._providers:
                del self._providers[name]
                self._provider_order.remove(name)
                return True
            return False
    
    def get_provider(self, name: Optional[str] = None) -> Optional[BaseLLMProvider]:
        """
        Get a provider by name or default.
        
        Args:
            name: Provider name, or None for default
            
        Returns:
            Provider instance or None if not found
        """
        with self._lock:
            if name:
                return self._providers.get(name)
            return self._providers.get(self.config.default_provider.value)
    
    def _select_provider(
        self,
        exclude: Optional[List[str]] = None,
    ) -> Optional[BaseLLMProvider]:
        """
        Select a provider based on load balancing strategy.
        
        Args:
            exclude: List of provider names to exclude
            
        Returns:
            Selected provider or None
        """
        exclude = exclude or []
        available = [
            name for name in self._provider_order
            if name not in exclude and 
            self._providers.get(name, BaseLLMProvider).is_available
        ]
        
        if not available:
            return None
        
        if self.config.load_balance_strategy == "round_robin":
            # Round-robin selection
            self._current_provider_index %= len(available)
            name = available[self._current_provider_index]
            self._current_provider_index += 1
            return self._providers[name]
        
        elif self.config.load_balance_strategy == "least_latency":
            # Select provider with lowest average latency
            best = min(
                available,
                key=lambda n: self._metrics[n].avg_latency_ms
            )
            return self._providers[best]
        
        else:  # random or default
            import random
            name = random.choice(available)
            return self._providers[name]
    
    def _record_success(
        self,
        provider_name: str,
        tokens: int,
        latency_ms: float,
    ) -> None:
        """Record successful request."""
        metrics = self._metrics[provider_name]
        metrics.total_requests += 1
        metrics.successful_requests += 1
        metrics.total_tokens += tokens
        metrics.total_latency_ms += latency_ms
        metrics.last_request_time = datetime.now(timezone.utc)
    
    def _record_failure(
        self,
        provider_name: str,
        error: str,
    ) -> None:
        """Record failed request."""
        metrics = self._metrics[provider_name]
        metrics.total_requests += 1
        metrics.failed_requests += 1
        metrics.last_error = error
        metrics.last_request_time = datetime.now(timezone.utc)
    
    def generate(
        self,
        prompt: str,
        provider: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        use_cache: bool = True,
        **kwargs: Any,
    ) -> GenerationResult:
        """
        Generate text from a prompt.
        
        Args:
            prompt: Input prompt
            provider: Specific provider to use
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            use_cache: Whether to use cache
            **kwargs: Additional parameters
            
        Returns:
            GenerationResult
        """
        # Check cache first
        if use_cache and self._cache:
            cached = self._cache.get(prompt, model=provider or "")
            if cached:
                return GenerationResult(
                    text=cached.response,
                    model=cached.model,
                    provider=cached.provider,
                    tokens_used=cached.tokens_used,
                    latency_ms=cached.latency_ms,
                    metadata={"cached": True, **cached.metadata},
                )
        
        # Try providers with failover
        tried: List[str] = []
        last_error: Optional[Exception] = None
        
        while True:
            # Select provider
            if provider and provider not in tried:
                selected = self._providers.get(provider)
            else:
                selected = self._select_provider(exclude=tried)
            
            if not selected:
                break
            
            tried.append(selected.name)
            
            # Check rate limit
            if self._rate_limiter:
                if not self._rate_limiter.acquire(
                    selected.name,
                    tokens=max_tokens or 100,
                    blocking=False,
                ):
                    continue
            
            # Make request
            start_time = time.time()
            try:
                result = selected.generate(
                    prompt=prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **kwargs,
                )
                
                latency_ms = (time.time() - start_time) * 1000
                self._record_success(selected.name, result.tokens_used, latency_ms)
                
                # Cache result — use provider arg (or "") as model key for consistent lookup
                if use_cache and self._cache:
                    self._cache.set(
                        query=prompt,
                        response=result.text,
                        model=provider or "",
                        provider=result.provider,
                        tokens_used=result.tokens_used,
                        latency_ms=latency_ms,
                        metadata={"actual_model": result.model},
                    )
                
                return result
                
            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000
                self._record_failure(selected.name, str(e))
                last_error = e
                logger.warning(f"Provider {selected.name} failed: {e}")
                
                if not self.config.failover_enabled:
                    raise
        
        # All providers failed
        if last_error:
            raise last_error
        raise RuntimeError("No LLM providers available")
    
    def chat(
        self,
        messages: List[ChatMessage],
        provider: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        use_cache: bool = True,
        **kwargs: Any,
    ) -> GenerationResult:
        """
        Generate a chat completion.
        
        Args:
            messages: List of chat messages
            provider: Specific provider to use
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            use_cache: Whether to use cache
            **kwargs: Additional parameters
            
        Returns:
            GenerationResult
        """
        # Create cache key from messages
        cache_key = "|".join(f"{m.role}:{m.content}" for m in messages)
        
        # Check cache
        if use_cache and self._cache:
            cached = self._cache.get(cache_key, model=provider or "")
            if cached:
                return GenerationResult(
                    text=cached.response,
                    model=cached.model,
                    provider=cached.provider,
                    tokens_used=cached.tokens_used,
                    latency_ms=cached.latency_ms,
                    metadata={"cached": True, **cached.metadata},
                )
        
        # Try providers with failover
        tried: List[str] = []
        last_error: Optional[Exception] = None
        
        while True:
            if provider and provider not in tried:
                selected = self._providers.get(provider)
            else:
                selected = self._select_provider(exclude=tried)
            
            if not selected:
                break
            
            tried.append(selected.name)
            
            if self._rate_limiter:
                if not self._rate_limiter.acquire(
                    selected.name,
                    tokens=max_tokens or 100,
                    blocking=False,
                ):
                    continue
            
            start_time = time.time()
            try:
                result = selected.chat(
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **kwargs,
                )
                
                latency_ms = (time.time() - start_time) * 1000
                self._record_success(selected.name, result.tokens_used, latency_ms)
                
                if use_cache and self._cache:
                    self._cache.set(
                        query=cache_key,
                        response=result.text,
                        model=result.model,
                        provider=result.provider,
                        tokens_used=result.tokens_used,
                        latency_ms=latency_ms,
                    )
                
                return result
                
            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000
                self._record_failure(selected.name, str(e))
                last_error = e
                logger.warning(f"Provider {selected.name} failed: {e}")
                
                if not self.config.failover_enabled:
                    raise
        
        if last_error:
            raise last_error
        raise RuntimeError("No LLM providers available")
    
    async def generate_async(
        self,
        prompt: str,
        provider: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs: Any,
    ) -> GenerationResult:
        """Async text generation."""
        selected = self._providers.get(provider) if provider else self._select_provider()
        
        if not selected:
            raise RuntimeError("No LLM providers available")
        
        start_time = time.time()
        try:
            result = await selected.generate_async(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs,
            )
            latency_ms = (time.time() - start_time) * 1000
            self._record_success(selected.name, result.tokens_used, latency_ms)
            return result
        except Exception as e:
            self._record_failure(selected.name, str(e))
            raise
    
    async def chat_async(
        self,
        messages: List[ChatMessage],
        provider: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs: Any,
    ) -> GenerationResult:
        """Async chat completion."""
        selected = self._providers.get(provider) if provider else self._select_provider()
        
        if not selected:
            raise RuntimeError("No LLM providers available")
        
        start_time = time.time()
        try:
            result = await selected.chat_async(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs,
            )
            latency_ms = (time.time() - start_time) * 1000
            self._record_success(selected.name, result.tokens_used, latency_ms)
            return result
        except Exception as e:
            self._record_failure(selected.name, str(e))
            raise
    
    def health_check(self) -> Dict[str, bool]:
        """Check health of all providers."""
        results = {}
        for name, provider in self._providers.items():
            try:
                results[name] = provider.health_check()
            except Exception as e:
                logger.warning(f"Health check failed for {name}: {e}")
                results[name] = False
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get gateway statistics."""
        with self._lock:
            provider_stats = {
                name: {
                    "status": provider.status.value,
                    **self._metrics[name].__dict__,
                    "success_rate": self._metrics[name].success_rate,
                    "avg_latency_ms": self._metrics[name].avg_latency_ms,
                }
                for name, provider in self._providers.items()
            }
            
            cache_stats = self._cache.get_stats() if self._cache else None
            rate_limit_stats = self._rate_limiter.get_all_stats() if self._rate_limiter else None
            
            return {
                "providers": provider_stats,
                "cache": cache_stats,
                "rate_limits": rate_limit_stats,
                "config": {
                    "default_provider": self.config.default_provider.value,
                    "failover_enabled": self.config.failover_enabled,
                    "load_balance_strategy": self.config.load_balance_strategy,
                },
            }
    
    def clear_cache(self) -> None:
        """Clear the response cache."""
        if self._cache:
            self._cache.clear()
    
    async def close(self) -> None:
        """Close all provider connections."""
        for provider in self._providers.values():
            if hasattr(provider, "close"):
                try:
                    await provider.close()
                except Exception as e:
                    logger.warning(f"Error closing provider {provider.name}: {e}")


# Factory function for easy gateway creation
def create_gateway(
    providers: Optional[List[Dict[str, Any]]] = None,
    config: Optional[LLMConfig] = None,
) -> LLMGateway:
    """
    Create and configure an LLM Gateway.
    
    Args:
        providers: List of provider configurations
        config: Gateway configuration
        
    Returns:
        Configured LLMGateway instance
    """
    from src.llm.providers.ollama import OllamaProvider
    from src.llm.providers.vllm import VLLMProvider
    from src.llm.providers.openai_compatible import OpenAICompatibleProvider
    
    gateway = LLMGateway(config)
    
    if providers:
        for p in providers:
            provider_type = p.get("type", "ollama")
            provider_config = ProviderConfig(
                name=p.get("name", provider_type),
                base_url=p.get("base_url"),
                api_key=p.get("api_key"),
                model=p.get("model", "default"),
            )
            
            if provider_type == "ollama":
                provider = OllamaProvider(provider_config)
            elif provider_type == "vllm":
                provider = VLLMProvider(provider_config)
            elif provider_type in ("openai", "azure", "custom"):
                provider = OpenAICompatibleProvider(provider_config)
            else:
                logger.warning(f"Unknown provider type: {provider_type}")
                continue
            
            gateway.register_provider(
                provider,
                set_default=p.get("default", False),
            )
    
    return gateway


__all__ = [
    "LLMProvider",
    "LLMConfig",
    "ProviderMetrics",
    "LLMGateway",
    "create_gateway",
]
