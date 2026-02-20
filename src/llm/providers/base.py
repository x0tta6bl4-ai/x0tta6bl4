"""
Base LLM Provider Interface
===========================

Abstract base class for all LLM providers in the x0tta6bl4 platform.
Defines the common interface for text generation, chat completion,
and embedding operations.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class ProviderStatus(Enum):
    """Status of an LLM provider."""
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"


@dataclass
class GenerationResult:
    """Result from a text generation request."""
    text: str
    model: str
    provider: str
    tokens_used: int = 0
    latency_ms: float = 0.0
    finish_reason: str = "stop"
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "text": self.text,
            "model": self.model,
            "provider": self.provider,
            "tokens_used": self.tokens_used,
            "latency_ms": self.latency_ms,
            "finish_reason": self.finish_reason,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ChatMessage:
    """A single chat message."""
    role: str  # "system", "user", "assistant"
    content: str
    name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API calls."""
        result = {"role": self.role, "content": self.content}
        if self.name:
            result["name"] = self.name
        return result


@dataclass
class EmbeddingResult:
    """Result from an embedding request."""
    embedding: List[float]
    model: str
    provider: str
    tokens_used: int = 0
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderConfig:
    """Configuration for an LLM provider."""
    name: str
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: str = "default"
    max_tokens: int = 512
    temperature: float = 0.7
    top_p: float = 0.9
    timeout_seconds: float = 30.0
    max_retries: int = 3
    extra_params: Dict[str, Any] = field(default_factory=dict)


class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    
    All providers must implement the core generation and chat methods.
    Embedding support is optional.
    """
    
    def __init__(self, config: ProviderConfig):
        self.config = config
        self._status = ProviderStatus.AVAILABLE
        self._last_error: Optional[str] = None
        self._request_count = 0
        self._total_tokens = 0
        self._total_latency_ms = 0.0
        
    @property
    def name(self) -> str:
        """Provider name."""
        return self.config.name
    
    @property
    def status(self) -> ProviderStatus:
        """Current provider status."""
        return self._status
    
    @property
    def is_available(self) -> bool:
        """Check if provider is available for requests."""
        return self._status == ProviderStatus.AVAILABLE
    
    @abstractmethod
    def generate(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        stop: Optional[List[str]] = None,
        **kwargs
    ) -> GenerationResult:
        """
        Generate text from a prompt.
        
        Args:
            prompt: Input text prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Top-p sampling parameter
            stop: Stop sequences
            **kwargs: Additional provider-specific parameters
            
        Returns:
            GenerationResult with generated text and metadata
        """
        pass
    
    @abstractmethod
    def chat(
        self,
        messages: List[ChatMessage],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> GenerationResult:
        """
        Generate a chat completion.
        
        Args:
            messages: List of chat messages
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Additional provider-specific parameters
            
        Returns:
            GenerationResult with generated text and metadata
        """
        pass
    
    @abstractmethod
    async def generate_async(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> GenerationResult:
        """Async version of generate."""
        pass
    
    @abstractmethod
    async def chat_async(
        self,
        messages: List[ChatMessage],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> GenerationResult:
        """Async version of chat."""
        pass
    
    def embed(
        self,
        text: Union[str, List[str]],
        **kwargs
    ) -> Union[EmbeddingResult, List[EmbeddingResult]]:
        """
        Generate embeddings for text.
        
        Args:
            text: Input text or list of texts
            **kwargs: Additional provider-specific parameters
            
        Returns:
            EmbeddingResult or list of EmbeddingResult
            
        Note:
            Not all providers support embeddings. Default implementation
            raises NotImplementedError.
        """
        raise NotImplementedError(f"{self.name} does not support embeddings")
    
    def stream_generate(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Stream generated text tokens.
        
        Note:
            Not all providers support streaming. Default implementation
            yields the complete response at once.
        """
        result = self.generate(prompt, max_tokens=max_tokens, **kwargs)
        yield result.text
    
    async def stream_generate_async(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """Async streaming generation."""
        result = await self.generate_async(prompt, max_tokens=max_tokens, **kwargs)
        yield result.text
    
    def health_check(self) -> bool:
        """
        Check if the provider is healthy and available.
        
        Returns:
            True if provider is healthy, False otherwise
        """
        try:
            # Simple generation test
            result = self.generate("test", max_tokens=5)
            self._status = ProviderStatus.AVAILABLE
            return True
        except Exception as e:
            self._status = ProviderStatus.ERROR
            self._last_error = str(e)
            logger.warning(f"Health check failed for {self.name}: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get provider statistics."""
        avg_latency = (
            self._total_latency_ms / self._request_count
            if self._request_count > 0
            else 0.0
        )
        return {
            "name": self.name,
            "status": self._status.value,
            "request_count": self._request_count,
            "total_tokens": self._total_tokens,
            "avg_latency_ms": avg_latency,
            "last_error": self._last_error,
        }
    
    def _record_request(
        self,
        tokens_used: int,
        latency_ms: float,
        success: bool = True
    ) -> None:
        """Record request statistics."""
        self._request_count += 1
        self._total_tokens += tokens_used
        self._total_latency_ms += latency_ms
        
    def _get_param(
        self,
        value: Optional[Any],
        default: Any,
        config_attr: Optional[str] = None
    ) -> Any:
        """Get parameter with fallback to config default."""
        if value is not None:
            return value
        if config_attr and hasattr(self.config, config_attr):
            return getattr(self.config, config_attr)
        return default
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name}, status={self._status.value})"


__all__ = [
    "ProviderStatus",
    "GenerationResult",
    "ChatMessage",
    "EmbeddingResult",
    "ProviderConfig",
    "BaseLLMProvider",
]
