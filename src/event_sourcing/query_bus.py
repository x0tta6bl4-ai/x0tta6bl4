"""
Query Bus - CQRS query handling infrastructure.

Provides query dispatch, caching, and handler registration
for the Query side of CQRS.
"""

import asyncio
import hashlib
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, Generic, List, Optional, Type, TypeVar

logger = logging.getLogger(__name__)

TQuery = TypeVar('TQuery', bound='Query')
TResult = TypeVar('TResult')


@dataclass
class Query:
    """Base class for all queries."""
    query_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    query_type: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    options: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.query_type:
            self.query_type = self.__class__.__name__
    
    def get_cache_key(self) -> str:
        """Generate cache key for this query."""
        data = {
            "query_type": self.query_type,
            **{k: v for k, v in self.__dict__.items() if k not in ("query_id", "timestamp", "metadata")}
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()


@dataclass
class QueryResult(Generic[TResult]):
    """Result of query execution."""
    success: bool
    result: Optional[TResult] = None
    error: Optional[str] = None
    from_cache: bool = False
    execution_time_ms: float = 0.0
    total_count: Optional[int] = None  # For paginated results


class QueryHandler(ABC, Generic[TQuery, TResult]):
    """Abstract base class for query handlers."""
    
    @abstractmethod
    async def handle(self, query: TQuery) -> QueryResult[TResult]:
        """Handle the query and return result."""
        pass


class QueryCache:
    """Cache for query results."""
    
    def __init__(self, default_ttl_seconds: float = 60.0):
        self._cache: Dict[str, tuple] = {}  # key -> (result, timestamp, ttl)
        self.default_ttl_seconds = default_ttl_seconds
        self._stats = {"hits": 0, "misses": 0}
    
    def get(self, key: str) -> Optional[QueryResult]:
        """Get cached result if valid."""
        if key in self._cache:
            result, timestamp, ttl = self._cache[key]
            age = (datetime.utcnow() - timestamp).total_seconds()
            if age < ttl:
                self._stats["hits"] += 1
                result.from_cache = True
                return result
            else:
                del self._cache[key]
        
        self._stats["misses"] += 1
        return None
    
    def set(
        self,
        key: str,
        result: QueryResult,
        ttl_seconds: Optional[float] = None
    ) -> None:
        """Cache a result."""
        self._cache[key] = (
            result,
            datetime.utcnow(),
            ttl_seconds or self.default_ttl_seconds
        )
    
    def invalidate(self, key: str) -> bool:
        """Invalidate a cached result."""
        if key in self._cache:
            del self._cache[key]
            return True
        return False
    
    def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching pattern."""
        import fnmatch
        keys_to_delete = [
            k for k in self._cache.keys()
            if fnmatch.fnmatch(k, pattern)
        ]
        for key in keys_to_delete:
            del self._cache[key]
        return len(keys_to_delete)
    
    def clear(self) -> None:
        """Clear all cached results."""
        self._cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total if total > 0 else 0
        return {
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "hit_rate": hit_rate,
            "cached_queries": len(self._cache),
        }


class QueryMiddleware:
    """Middleware for query processing."""
    
    async def before_execute(self, query: Query) -> Optional[QueryResult]:
        """Called before query execution. Return result to short-circuit."""
        return None
    
    async def after_execute(
        self,
        query: Query,
        result: QueryResult
    ) -> QueryResult:
        """Called after query execution. Can modify result."""
        return result


class CachingMiddleware(QueryMiddleware):
    """Middleware that caches query results."""
    
    def __init__(self, cache: Optional[QueryCache] = None):
        self.cache = cache or QueryCache()
        self._ttl_overrides: Dict[str, float] = {}
    
    def set_ttl(self, query_type: str, ttl_seconds: float) -> None:
        """Set TTL for a specific query type."""
        self._ttl_overrides[query_type] = ttl_seconds
    
    async def before_execute(self, query: Query) -> Optional[QueryResult]:
        cache_key = query.get_cache_key()
        cached = self.cache.get(cache_key)
        if cached:
            logger.debug(f"Cache hit for query {query.query_id}")
            return cached
        return None
    
    async def after_execute(
        self,
        query: Query,
        result: QueryResult
    ) -> QueryResult:
        if result.success and not result.from_cache:
            cache_key = query.get_cache_key()
            ttl = self._ttl_overrides.get(query.query_type)
            self.cache.set(cache_key, result, ttl)
            logger.debug(f"Cached result for query {query.query_id}")
        return result


class LoggingMiddleware(QueryMiddleware):
    """Middleware that logs query execution."""
    
    async def before_execute(self, query: Query) -> Optional[QueryResult]:
        logger.info(f"Executing query: {query.query_type} [{query.query_id}]")
        return None
    
    async def after_execute(
        self,
        query: Query,
        result: QueryResult
    ) -> QueryResult:
        status = "succeeded" if result.success else "failed"
        cache_status = " (cached)" if result.from_cache else ""
        logger.info(
            f"Query {query.query_type} [{query.query_id}] {status}{cache_status} "
            f"in {result.execution_time_ms:.2f}ms"
        )
        return result


class RateLimitMiddleware(QueryMiddleware):
    """Middleware that rate limits queries."""
    
    def __init__(self, max_queries_per_second: float = 100.0):
        self.max_qps = max_queries_per_second
        self._query_times: List[float] = []
        self._lock = asyncio.Lock()
    
    async def before_execute(self, query: Query) -> Optional[QueryResult]:
        async with self._lock:
            now = time.time()
            
            # Clean old entries
            self._query_times = [
                t for t in self._query_times
                if now - t < 1.0
            ]
            
            # Check rate
            if len(self._query_times) >= self.max_qps:
                return QueryResult(
                    success=False,
                    error="Rate limit exceeded"
                )
            
            self._query_times.append(now)
            return None


class QueryBus:
    """
    Query bus for CQRS query dispatch.
    
    Features:
    - Query handler registration
    - Middleware support
    - Result caching
    - Async query execution
    """
    
    def __init__(self, enable_cache: bool = True):
        self._handlers: Dict[str, QueryHandler] = {}
        self._middlewares: List[QueryMiddleware] = []
        self._query_types: Dict[str, Type[Query]] = {}
        
        # Add caching middleware if enabled
        if enable_cache:
            self._cache = QueryCache()
            self._caching_middleware = CachingMiddleware(self._cache)
            self._middlewares.append(self._caching_middleware)
        else:
            self._cache = None
            self._caching_middleware = None
    
    def register_handler(
        self,
        query_type: Type[TQuery],
        handler: QueryHandler[TQuery, TResult]
    ) -> None:
        """Register a handler for a query type."""
        type_name = query_type.__name__
        self._handlers[type_name] = handler
        self._query_types[type_name] = query_type
        logger.debug(f"Registered handler for query: {type_name}")
    
    def unregister_handler(self, query_type: Type[Query]) -> None:
        """Unregister a handler."""
        type_name = query_type.__name__
        self._handlers.pop(type_name, None)
        self._query_types.pop(type_name, None)
    
    def add_middleware(self, middleware: QueryMiddleware) -> None:
        """Add middleware to the pipeline."""
        self._middlewares.append(middleware)
    
    def remove_middleware(self, middleware: QueryMiddleware) -> None:
        """Remove middleware from the pipeline."""
        if middleware in self._middlewares:
            self._middlewares.remove(middleware)
    
    async def execute(self, query: Query) -> QueryResult:
        """Execute a query through the pipeline."""
        start_time = time.time()
        
        # Ensure query type is set
        if not query.query_type:
            query.query_type = query.__class__.__name__
        
        # Run before middleware
        for middleware in self._middlewares:
            result = await middleware.before_execute(query)
            if result is not None:
                result.execution_time_ms = (time.time() - start_time) * 1000
                return result
        
        # Get handler
        handler = self._handlers.get(query.query_type)
        if not handler:
            result = QueryResult(
                success=False,
                error=f"No handler registered for query: {query.query_type}"
            )
            result.execution_time_ms = (time.time() - start_time) * 1000
            return await self._run_after_middleware(query, result)
        
        # Execute
        try:
            result = await handler.handle(query)
            result.execution_time_ms = (time.time() - start_time) * 1000
            return await self._run_after_middleware(query, result)
            
        except Exception as e:
            result = QueryResult(
                success=False,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )
            return await self._run_after_middleware(query, result)
    
    async def _run_after_middleware(
        self,
        query: Query,
        result: QueryResult
    ) -> QueryResult:
        """Run after middleware."""
        for middleware in self._middlewares:
            result = await middleware.after_execute(query, result)
        return result
    
    def invalidate_cache(
        self,
        query: Optional[Query] = None,
        *,
        query_type: Optional[str] = None,
        all: bool = False,
    ) -> int:
        """Invalidate query cache and return number of invalidated entries."""
        if not self._cache:
            return 0

        if all:
            count = len(self._cache._cache)
            self._cache.clear()
            return count

        if query is not None:
            return 1 if self._cache.invalidate(query.get_cache_key()) else 0

        if query_type:
            # Query cache keys are hashed and do not expose query_type; safest is full clear.
            count = len(self._cache._cache)
            self._cache.clear()
            return count

        count = len(self._cache._cache)
        self._cache.clear()
        return count
    
    def invalidate_cache_pattern(self, pattern: str) -> int:
        """Invalidate cache entries matching pattern."""
        if self._cache:
            return self._cache.invalidate_pattern(pattern)
        return 0
    
    def get_cache_stats(self) -> Optional[Dict[str, Any]]:
        """Get cache statistics."""
        if self._cache:
            return self._cache.get_stats()
        return None
    
    def set_query_ttl(self, query_type: str, ttl_seconds: float) -> None:
        """Set cache TTL for a query type."""
        if self._caching_middleware:
            self._caching_middleware.set_ttl(query_type, ttl_seconds)
    
    def get_registered_queries(self) -> List[str]:
        """Get list of registered query types."""
        return list(self._handlers.keys())
    
    def has_handler(self, query_type: str) -> bool:
        """Check if a handler is registered."""
        return query_type in self._handlers


# Decorator for registering handlers
def query_handler(query_type: Type[Query]):
    """Decorator to register a function as a query handler."""
    def decorator(func: Callable):
        class FunctionHandler(QueryHandler):
            async def handle(self, query: Query):
                try:
                    if asyncio.iscoroutinefunction(func):
                        result = await func(query)
                    else:
                        result = func(query)
                    return QueryResult(success=True, result=result)
                except Exception as e:
                    return QueryResult(success=False, error=str(e))
        
        handler = FunctionHandler()
        func._query_handler = (query_type, handler)
        return func
    
    return decorator


# Common queries
@dataclass
class GetAggregateQuery(Query):
    """Query to get an aggregate by ID."""
    aggregate_id: str = ""
    include_history: bool = False


@dataclass
class ListAggregatesQuery(Query):
    """Query to list aggregates."""
    aggregate_type: Optional[str] = None
    page: int = 1
    page_size: int = 20
    sort_by: str = "created_at"
    sort_order: str = "desc"
    filters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchQuery(Query):
    """Full-text search query."""
    search_term: str = ""
    fields: List[str] = field(default_factory=list)
    limit: int = 10


@dataclass
class CountQuery(Query):
    """Query to count aggregates."""
    aggregate_type: Optional[str] = None
    filters: Dict[str, Any] = field(default_factory=dict)
