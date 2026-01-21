import logging
import time
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
from collections import deque

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    recovery_timeout_seconds: int = 60
    success_threshold: int = 2


class CircuitBreaker:
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.lock = threading.Lock()
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        with self.lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_recovery():
                    self.state = CircuitState.HALF_OPEN
                else:
                    raise Exception("Circuit breaker is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _on_success(self) -> None:
        with self.lock:
            self.failure_count = 0
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.success_count = 0
    
    def _on_failure(self) -> None:
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = datetime.utcnow()
            if self.failure_count >= self.config.failure_threshold:
                self.state = CircuitState.OPEN
            self.success_count = 0
    
    def _should_attempt_recovery(self) -> bool:
        if not self.last_failure_time:
            return True
        elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
        return elapsed >= self.config.recovery_timeout_seconds


class RetryStrategy:
    def __init__(self, max_retries: int = 3, base_delay_ms: int = 100):
        self.max_retries = max_retries
        self.base_delay_ms = base_delay_ms
    
    def execute(self, func: Callable, *args, **kwargs) -> Any:
        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception:
                if attempt == self.max_retries:
                    raise
                delay_ms = self.base_delay_ms * (2 ** attempt)
                time.sleep(delay_ms / 1000.0)


class BulkheadIsolation:
    def __init__(self, max_concurrent: int = 10):
        self.max_concurrent = max_concurrent
        self.semaphore = threading.Semaphore(max_concurrent)
        self.active_count = 0
        self.lock = threading.Lock()
    
    def execute(self, func: Callable, *args, **kwargs) -> Any:
        if not self.semaphore.acquire(blocking=False):
            raise Exception("Bulkhead limit exceeded")
        
        try:
            with self.lock:
                self.active_count += 1
            return func(*args, **kwargs)
        finally:
            with self.lock:
                self.active_count -= 1
            self.semaphore.release()


class FallbackHandler:
    def __init__(self):
        self.fallback_chains: Dict[str, List[Callable]] = {}
        self.lock = threading.Lock()
    
    def register_fallback(self, key: str, fallback_fn: Callable) -> None:
        with self.lock:
            if key not in self.fallback_chains:
                self.fallback_chains[key] = []
            self.fallback_chains[key].append(fallback_fn)
    
    def execute_with_fallback(self, key: str, primary_fn: Callable,
                             *args, **kwargs) -> Any:
        try:
            return primary_fn(*args, **kwargs)
        except Exception:
            with self.lock:
                fallbacks = self.fallback_chains.get(key, [])
            
            for fallback_fn in fallbacks:
                try:
                    return fallback_fn(*args, **kwargs)
                except:
                    continue
            
            raise


class ResilientExecutor:
    def __init__(self):
        self.circuit_breaker = CircuitBreaker(CircuitBreakerConfig())
        self.retry_strategy = RetryStrategy()
        self.bulkhead = BulkheadIsolation()
        self.fallback = FallbackHandler()
        self.execution_log: deque = deque(maxlen=1000)
        self.lock = threading.Lock()
    
    def execute(self, func: Callable, *args, **kwargs) -> Any:
        start = time.time()
        try:
            result = self.circuit_breaker.call(
                self._execute_with_retry,
                func, *args, **kwargs
            )
            self._log_execution(func.__name__, True, time.time() - start)
            return result
        except Exception as e:
            self._log_execution(func.__name__, False, time.time() - start, str(e))
            raise
    
    def _execute_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        return self.retry_strategy.execute(func, *args, **kwargs)
    
    def _log_execution(self, func_name: str, success: bool, 
                      duration_sec: float, error: str = None) -> None:
        with self.lock:
            self.execution_log.append({
                "function": func_name,
                "success": success,
                "duration_sec": duration_sec,
                "error": error,
                "timestamp": datetime.utcnow().isoformat()
            })


_executor = None

def get_resilient_executor() -> ResilientExecutor:
    global _executor
    if _executor is None:
        _executor = ResilientExecutor()
    return _executor


__all__ = [
    "CircuitState",
    "CircuitBreakerConfig",
    "CircuitBreaker",
    "RetryStrategy",
    "BulkheadIsolation",
    "FallbackHandler",
    "ResilientExecutor",
    "get_resilient_executor",
]
