"""
vLLM LLM Provider
=================

Provider for vLLM high-performance inference server.
Supports OpenAI-compatible API with enhanced throughput.
"""

import logging
import time
from typing import Any, Dict, List, Optional, Union

import aiohttp
import requests

from src.llm.providers.base import (
    BaseLLMProvider,
    ChatMessage,
    EmbeddingResult,
    GenerationResult,
    ProviderConfig,
    ProviderStatus,
)

logger = logging.getLogger(__name__)


class VLLMProvider(BaseLLMProvider):
    """
    LLM Provider for vLLM inference server.
    
    vLLM provides:
    - High-throughput inference
    - PagedAttention for efficient memory usage
    - OpenAI-compatible API
    - Streaming support
    """
    
    DEFAULT_BASE_URL = "http://localhost:8000"
    DEFAULT_MODEL = "default"
    
    def __init__(self, config: Optional[ProviderConfig] = None, **kwargs: Any):
        if config is None:
            config = ProviderConfig(
                name="vllm",
                base_url=self.DEFAULT_BASE_URL,
                model=self.DEFAULT_MODEL,
            )
        
        if "base_url" in kwargs:
            config.base_url = kwargs["base_url"]
        if "model" in kwargs:
            config.model = kwargs["model"]
        if "api_key" in kwargs:
            config.api_key = kwargs["api_key"]
            
        super().__init__(config)
        self._session: Optional[requests.Session] = None
        self._async_session: Optional[aiohttp.ClientSession] = None
        
    def _get_session(self) -> requests.Session:
        """Get or create HTTP session."""
        if self._session is None:
            self._session = requests.Session()
            headers = {"Content-Type": "application/json"}
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"
            self._session.headers.update(headers)
        return self._session
    
    async def _get_async_session(self) -> aiohttp.ClientSession:
        """Get or create async HTTP session."""
        if self._async_session is None or self._async_session.closed:
            headers = {"Content-Type": "application/json"}
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"
            self._async_session = aiohttp.ClientSession(headers=headers)
        return self._async_session
    
    def _build_url(self, endpoint: str) -> str:
        """Build full URL for API endpoint."""
        base = self.config.base_url or self.DEFAULT_BASE_URL
        return f"{base.rstrip('/')}{endpoint}"
    
    def generate(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        stop: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> GenerationResult:
        """Generate text using vLLM OpenAI-compatible API."""
        start_time = time.time()
        
        payload: Dict[str, Any] = {
            "model": self.config.model,
            "prompt": prompt,
            "max_tokens": self._get_param(max_tokens, self.config.max_tokens),
            "temperature": self._get_param(temperature, self.config.temperature),
            "top_p": self._get_param(top_p, self.config.top_p),
        }
        
        if stop:
            payload["stop"] = stop
            
        # vLLM-specific parameters
        if "top_k" in kwargs:
            payload["top_k"] = kwargs["top_k"]
        if "repetition_penalty" in kwargs:
            payload["repetition_penalty"] = kwargs["repetition_penalty"]
        if "best_of" in kwargs:
            payload["best_of"] = kwargs["best_of"]
            
        try:
            session = self._get_session()
            response = session.post(
                self._build_url("/v1/completions"),
                json=payload,
                timeout=self.config.timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
            
            latency_ms = (time.time() - start_time) * 1000
            
            choices = data.get("choices", [])
            if not choices:
                raise ValueError("No choices returned from vLLM")
                
            text = choices[0].get("text", "")
            usage = data.get("usage", {})
            tokens_used = usage.get("total_tokens", 0)
            
            self._record_request(tokens_used, latency_ms)
            
            return GenerationResult(
                text=text,
                model=data.get("model", self.config.model),
                provider=self.name,
                tokens_used=tokens_used,
                latency_ms=latency_ms,
                finish_reason=choices[0].get("finish_reason", "stop"),
                metadata={
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "id": data.get("id"),
                },
            )
            
        except requests.exceptions.ConnectionError as e:
            self._status = ProviderStatus.UNAVAILABLE
            self._last_error = str(e)
            raise ConnectionError(f"vLLM server not reachable: {e}")
        except requests.exceptions.HTTPError as e:
            self._status = ProviderStatus.ERROR
            self._last_error = str(e)
            raise RuntimeError(f"vLLM API error: {e}")
            
    def chat(
        self,
        messages: List[ChatMessage],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs: Any,
    ) -> GenerationResult:
        """Generate chat completion using vLLM OpenAI-compatible API."""
        start_time = time.time()
        
        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": [m.to_dict() for m in messages],
            "max_tokens": self._get_param(max_tokens, self.config.max_tokens),
            "temperature": self._get_param(temperature, self.config.temperature),
        }
        
        try:
            session = self._get_session()
            response = session.post(
                self._build_url("/v1/chat/completions"),
                json=payload,
                timeout=self.config.timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
            
            latency_ms = (time.time() - start_time) * 1000
            
            choices = data.get("choices", [])
            if not choices:
                raise ValueError("No choices returned from vLLM")
                
            message = choices[0].get("message", {})
            text = message.get("content", "")
            usage = data.get("usage", {})
            tokens_used = usage.get("total_tokens", 0)
            
            self._record_request(tokens_used, latency_ms)
            
            return GenerationResult(
                text=text,
                model=data.get("model", self.config.model),
                provider=self.name,
                tokens_used=tokens_used,
                latency_ms=latency_ms,
                finish_reason=choices[0].get("finish_reason", "stop"),
                metadata={
                    "role": message.get("role"),
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                },
            )
            
        except requests.exceptions.HTTPError as e:
            self._status = ProviderStatus.ERROR
            self._last_error = str(e)
            raise RuntimeError(f"vLLM chat API error: {e}")
            
    async def generate_async(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs: Any,
    ) -> GenerationResult:
        """Async text generation."""
        start_time = time.time()
        
        payload: Dict[str, Any] = {
            "model": self.config.model,
            "prompt": prompt,
            "max_tokens": self._get_param(max_tokens, self.config.max_tokens),
            "temperature": self._get_param(temperature, self.config.temperature),
        }
        
        try:
            session = await self._get_async_session()
            async with session.post(
                self._build_url("/v1/completions"),
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout_seconds),
            ) as response:
                response.raise_for_status()
                data = await response.json()
                
                latency_ms = (time.time() - start_time) * 1000
                choices = data.get("choices", [])
                text = choices[0].get("text", "") if choices else ""
                usage = data.get("usage", {})
                tokens_used = usage.get("total_tokens", 0)
                
                self._record_request(tokens_used, latency_ms)
                
                return GenerationResult(
                    text=text,
                    model=data.get("model", self.config.model),
                    provider=self.name,
                    tokens_used=tokens_used,
                    latency_ms=latency_ms,
                )
                
        except aiohttp.ClientError as e:
            self._status = ProviderStatus.ERROR
            self._last_error = str(e)
            raise RuntimeError(f"vLLM async request failed: {e}")
            
    async def chat_async(
        self,
        messages: List[ChatMessage],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs: Any,
    ) -> GenerationResult:
        """Async chat completion."""
        start_time = time.time()
        
        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": [m.to_dict() for m in messages],
            "max_tokens": self._get_param(max_tokens, self.config.max_tokens),
            "temperature": self._get_param(temperature, self.config.temperature),
        }
        
        try:
            session = await self._get_async_session()
            async with session.post(
                self._build_url("/v1/chat/completions"),
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout_seconds),
            ) as response:
                response.raise_for_status()
                data = await response.json()
                
                latency_ms = (time.time() - start_time) * 1000
                choices = data.get("choices", [])
                message = choices[0].get("message", {}) if choices else {}
                text = message.get("content", "")
                usage = data.get("usage", {})
                tokens_used = usage.get("total_tokens", 0)
                
                self._record_request(tokens_used, latency_ms)
                
                return GenerationResult(
                    text=text,
                    model=data.get("model", self.config.model),
                    provider=self.name,
                    tokens_used=tokens_used,
                    latency_ms=latency_ms,
                )
                
        except aiohttp.ClientError as e:
            self._status = ProviderStatus.ERROR
            self._last_error = str(e)
            raise RuntimeError(f"vLLM async chat failed: {e}")
            
    def health_check(self) -> bool:
        """Check if vLLM server is running."""
        try:
            session = self._get_session()
            response = session.get(
                self._build_url("/health"),
                timeout=5.0,
            )
            if response.status_code == 200:
                self._status = ProviderStatus.AVAILABLE
                return True
            return False
        except Exception as e:
            self._status = ProviderStatus.UNAVAILABLE
            self._last_error = str(e)
            logger.warning(f"vLLM health check failed: {e}")
            return False
            
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the loaded model."""
        try:
            session = self._get_session()
            response = session.get(
                self._build_url("/v1/models"),
                timeout=10.0,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get vLLM model info: {e}")
            return {}
            
    async def close(self) -> None:
        """Close HTTP sessions."""
        if self._async_session and not self._async_session.closed:
            await self._async_session.close()
        if self._session:
            self._session.close()


__all__ = ["VLLMProvider"]
