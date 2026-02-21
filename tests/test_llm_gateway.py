"""
Tests for LLM Gateway Module
============================

Unit tests for multi-provider LLM gateway, semantic cache,
rate limiter, and consciousness integration.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, AsyncMock
import time

from src.llm.gateway import (
    LLMGateway,
    LLMConfig,
    LLMProvider,
    ProviderMetrics,
    create_gateway,
)
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
)
from src.llm.consciousness_integration import (
    ConsciousnessLLMIntegration,
    SystemAnalysis,
    HealingDecision,
)


class TestSemanticCache:
    """Tests for SemanticCache."""
    
    def test_cache_basic_operations(self):
        """Test basic cache set and get."""
        cache = SemanticCache(max_size=100, ttl_seconds=3600)
        
        # Set entry
        cache.set(
            query="What is the system status?",
            response="System is healthy",
            model="test-model",
            provider="test",
        )
        
        # Get entry — must pass same model as used in set (model is part of cache key)
        entry = cache.get("What is the system status?", model="test-model")
        assert entry is not None
        assert entry.response == "System is healthy"
        assert entry.model == "test-model"
        
    def test_cache_miss(self):
        """Test cache miss for unknown query."""
        cache = SemanticCache()
        
        entry = cache.get("Unknown query")
        assert entry is None
        
    def test_cache_expiration(self):
        """Test cache entry expiration."""
        cache = SemanticCache(ttl_seconds=1)  # 1 second TTL
        
        cache.set("test query", "test response")
        
        # Should be present immediately
        entry = cache.get("test query")
        assert entry is not None
        
        # Wait for expiration
        time.sleep(1.5)
        
        # Should be expired
        entry = cache.get("test query")
        assert entry is None
        
    def test_cache_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        cache = SemanticCache(max_size=3)
        
        cache.set("query1", "response1")
        cache.set("query2", "response2")
        cache.set("query3", "response3")
        cache.set("query4", "response4")  # Should evict query1
        
        assert cache.get("query1") is None
        assert cache.get("query2") is not None
        assert cache.get("query3") is not None
        assert cache.get("query4") is not None
        
    def test_cache_stats(self):
        """Test cache statistics."""
        cache = SemanticCache()
        
        cache.set("query1", "response1")
        cache.get("query1")  # Hit
        cache.get("unknown")  # Miss
        
        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 1
        
    def test_cache_clear(self):
        """Test cache clearing."""
        cache = SemanticCache()
        
        cache.set("query1", "response1")
        cache.set("query2", "response2")
        
        cache.clear()
        
        assert cache.get("query1") is None
        assert cache.get("query2") is None


class TestRateLimiter:
    """Tests for RateLimiter."""
    
    def test_token_bucket_acquire(self):
        """Test token bucket rate limiting."""
        config = RateLimitConfig(
            requests_per_minute=60,
            tokens_per_minute=1000,
            burst_size=5,
            strategy=RateLimitStrategy.TOKEN_BUCKET,
        )
        limiter = RateLimiter(config)
        
        # Should be able to acquire within burst
        for _ in range(5):
            assert limiter.acquire(tokens=10, blocking=False) is True
        
        # Should be limited after burst
        assert limiter.acquire(tokens=10, blocking=False) is False
        
    def test_rate_limiter_stats(self):
        """Test rate limiter statistics."""
        limiter = RateLimiter()
        
        limiter.acquire(tokens=100, blocking=False)
        limiter.acquire(tokens=200, blocking=False)
        
        stats = limiter.get_stats()
        assert stats["total_requests"] == 2
        assert stats["total_tokens"] == 300
        
    def test_rate_limiter_reset(self):
        """Test rate limiter reset."""
        limiter = RateLimiter()
        
        # Consume some tokens
        limiter.acquire(tokens=1000, blocking=False)
        
        limiter.reset()
        
        stats = limiter.get_stats()
        assert stats["total_requests"] == 0


class TestMultiProviderRateLimiter:
    """Tests for MultiProviderRateLimiter."""
    
    def test_multi_provider_registration(self):
        """Test registering multiple providers."""
        limiter = MultiProviderRateLimiter()
        
        limiter.register("ollama", RateLimitConfig(requests_per_minute=30))
        limiter.register("openai", RateLimitConfig(requests_per_minute=60))
        
        stats = limiter.get_all_stats()
        assert "ollama" in stats
        assert "openai" in stats
        
    def test_multi_provider_acquire(self):
        """Test acquiring from different providers."""
        limiter = MultiProviderRateLimiter()
        limiter.register("test", RateLimitConfig(burst_size=2))
        
        assert limiter.acquire("test", blocking=False) is True
        assert limiter.acquire("test", blocking=False) is True
        assert limiter.acquire("test", blocking=False) is False


class MockProvider(BaseLLMProvider):
    """Mock provider for testing."""
    
    def __init__(self, name: str = "mock", should_fail: bool = False):
        config = ProviderConfig(name=name, model="mock-model")
        super().__init__(config)
        self.should_fail = should_fail
        self.call_count = 0
        
    def generate(self, prompt, max_tokens=None, temperature=None, top_p=None, stop=None, **kwargs):
        self.call_count += 1
        if self.should_fail:
            raise RuntimeError("Mock provider error")
        return GenerationResult(
            text=f"Response to: {prompt[:50]}",
            model="mock-model",
            provider=self.name,
            tokens_used=100,
            latency_ms=50.0,
        )
    
    def chat(self, messages, max_tokens=None, temperature=None, **kwargs):
        self.call_count += 1
        if self.should_fail:
            raise RuntimeError("Mock provider error")
        return GenerationResult(
            text="Chat response",
            model="mock-model",
            provider=self.name,
            tokens_used=50,
            latency_ms=30.0,
        )
    
    async def generate_async(self, prompt, max_tokens=None, temperature=None, **kwargs):
        return self.generate(prompt, max_tokens, temperature, **kwargs)
    
    async def chat_async(self, messages, max_tokens=None, temperature=None, **kwargs):
        return self.chat(messages, max_tokens, temperature, **kwargs)


class TestLLMGateway:
    """Tests for LLMGateway."""
    
    def test_gateway_provider_registration(self):
        """Test provider registration."""
        gateway = LLMGateway()
        provider = MockProvider("test-provider")
        
        gateway.register_provider(provider)
        
        assert gateway.get_provider("test-provider") is not None
        
    def test_gateway_generate(self):
        """Test text generation through gateway."""
        gateway = LLMGateway()
        provider = MockProvider()
        gateway.register_provider(provider, set_default=True)
        
        result = gateway.generate("Test prompt")
        
        assert result.text == "Response to: Test prompt"
        assert result.provider == "mock"
        
    def test_gateway_chat(self):
        """Test chat completion through gateway."""
        gateway = LLMGateway()
        provider = MockProvider()
        gateway.register_provider(provider, set_default=True)
        
        messages = [
            ChatMessage(role="user", content="Hello")
        ]
        
        result = gateway.chat(messages)
        
        assert result.text == "Chat response"
        
    def test_gateway_failover(self):
        """Test failover between providers."""
        config = LLMConfig(failover_enabled=True)
        gateway = LLMGateway(config)
        
        # First provider will fail
        failing_provider = MockProvider("failing", should_fail=True)
        working_provider = MockProvider("working")
        
        gateway.register_provider(failing_provider)
        gateway.register_provider(working_provider)
        
        result = gateway.generate("Test")
        
        # Should have failed over to working provider
        assert result.provider == "working"
        
    def test_gateway_caching(self):
        """Test response caching."""
        config = LLMConfig(enable_cache=True)
        gateway = LLMGateway(config)
        provider = MockProvider()
        gateway.register_provider(provider, set_default=True)
        
        # First call
        result1 = gateway.generate("Same prompt", use_cache=True)
        
        # Second call should use cache
        result2 = gateway.generate("Same prompt", use_cache=True)
        
        assert result1.text == result2.text
        assert provider.call_count == 1  # Only one actual call
        
    def test_gateway_stats(self):
        """Test gateway statistics."""
        gateway = LLMGateway()
        provider = MockProvider()
        gateway.register_provider(provider, set_default=True)
        
        gateway.generate("Test 1")
        gateway.generate("Test 2")
        
        stats = gateway.get_stats()
        
        assert "providers" in stats
        assert "mock" in stats["providers"]
        assert stats["providers"]["mock"]["total_requests"] == 2


class TestConsciousnessIntegration:
    """Tests for ConsciousnessLLMIntegration."""
    
    def test_system_analysis_parsing(self):
        """Test parsing of system analysis response."""
        integration = ConsciousnessLLMIntegration()
        
        # Test JSON parsing
        json_response = '''{
            "summary": "System is healthy",
            "anomalies": ["High CPU"],
            "recommendations": ["Scale up"],
            "confidence": 0.85,
            "reasoning": "CPU usage is elevated"
        }'''
        
        analysis = integration._parse_analysis(json_response)
        
        assert analysis.summary == "System is healthy"
        assert "High CPU" in analysis.anomalies
        assert analysis.confidence == 0.85
        
    def test_healing_decision_parsing(self):
        """Test parsing of healing decision response."""
        integration = ConsciousnessLLMIntegration()
        
        json_response = '''{
            "action": "restart_service",
            "target": "api-server",
            "parameters": {"timeout": 30},
            "reasoning": "Service is unresponsive",
            "expected_outcome": "Service restored",
            "risk_level": "low",
            "confidence": 0.9
        }'''
        
        decision = integration._parse_decision(json_response)
        
        assert decision.action == "restart_service"
        assert decision.target == "api-server"
        assert decision.risk_level == "low"
        
    def test_metrics_formatting(self):
        """Test metrics formatting for LLM."""
        integration = ConsciousnessLLMIntegration()
        
        metrics = {
            "cpu_percent": 45.5,
            "memory_percent": 60.2,
            "latency_ms": 85.0,
        }
        
        formatted = integration._format_metrics(metrics)
        
        assert "cpu_percent: 45.5000" in formatted
        assert "memory_percent: 60.2000" in formatted
        
    def test_trend_calculation(self):
        """Test trend calculation from historical metrics."""
        integration = ConsciousnessLLMIntegration()
        
        historical = [
            {"cpu": 30, "memory": 50},
            {"cpu": 40, "memory": 55},
            {"cpu": 50, "memory": 60},
            {"cpu": 60, "memory": 65},
        ]
        
        trends = integration._calculate_trends(historical)
        
        assert "cpu" in trends
        assert trends["cpu"]["trend"] == "increasing"


class TestCacheEntry:
    """Tests for CacheEntry dataclass."""
    
    def test_cache_entry_creation(self):
        """Test cache entry creation."""
        entry = CacheEntry(
            query="test query",
            response="test response",
            model="test-model",
            provider="test-provider",
        )
        
        assert entry.query == "test query"
        assert entry.response == "test response"
        assert entry.access_count == 0
        
    def test_cache_entry_serialization(self):
        """Test cache entry serialization."""
        entry = CacheEntry(
            query="test",
            response="response",
            model="model",
            provider="provider",
            tokens_used=100,
        )
        
        data = entry.to_dict()
        
        assert data["query"] == "test"
        assert data["tokens_used"] == 100
        
        # Test deserialization
        restored = CacheEntry.from_dict(data)
        assert restored.query == entry.query


class TestGenerationResult:
    """Tests for GenerationResult dataclass."""
    
    def test_generation_result_creation(self):
        """Test generation result creation."""
        result = GenerationResult(
            text="Generated text",
            model="test-model",
            provider="test-provider",
            tokens_used=50,
            latency_ms=100.0,
        )
        
        assert result.text == "Generated text"
        assert result.tokens_used == 50
        
    def test_generation_result_to_dict(self):
        """Test generation result serialization."""
        result = GenerationResult(
            text="Test",
            model="model",
            provider="provider",
        )
        
        data = result.to_dict()
        
        assert data["text"] == "Test"
        assert "timestamp" in data


class TestChatMessage:
    """Tests for ChatMessage dataclass."""
    
    def test_chat_message_creation(self):
        """Test chat message creation."""
        msg = ChatMessage(role="user", content="Hello")
        
        assert msg.role == "user"
        assert msg.content == "Hello"
        
    def test_chat_message_to_dict(self):
        """Test chat message serialization."""
        msg = ChatMessage(role="assistant", content="Hi there", name="bot")
        
        data = msg.to_dict()
        
        assert data["role"] == "assistant"
        assert data["content"] == "Hi there"
        assert data["name"] == "bot"


# Integration tests
class TestIntegration:
    """Integration tests for LLM module."""
    
    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """Test complete workflow from gateway to integration."""
        # Create gateway with mock provider
        gateway = LLMGateway(LLMConfig(enable_cache=True))
        provider = MockProvider()
        gateway.register_provider(provider, set_default=True)
        
        # Create integration
        integration = ConsciousnessLLMIntegration(gateway=gateway)
        
        # Generate system thought
        metrics = {
            "cpu_percent": 45.0,
            "memory_percent": 60.0,
            "latency_ms": 85.0,
        }
        
        thought = integration.generate_system_thought(
            metrics=metrics,
            consciousness_state="HARMONIC",
            phi_ratio=1.2,
            harmony_index=0.85,
        )
        
        assert thought is not None
        assert len(thought) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
