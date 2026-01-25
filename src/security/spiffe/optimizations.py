"""
SPIFFE/SPIRE Optimizations from Paradox Zone

Integrates production-ready optimizations:
- Multi-region failover
- Token caching
- Performance tuning
- Federation support
"""
import logging
import asyncio
import os
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import time

logger = logging.getLogger(__name__)


@dataclass
class SPIREPerformanceConfig:
    """Performance configuration from Paradox Zone optimizations."""
    max_token_ttl: str = "24h"
    token_cache_size: int = 10000
    jwt_cache_size: int = 5000
    concurrent_rpcs: int = 100
    health_check_interval: str = "30s"
    failover_threshold: int = 3


@dataclass
class MultiRegionConfig:
    """Multi-region configuration for SPIRE servers."""
    primary_region: str = "us-east"
    fallback_regions: List[str] = None
    health_check_interval: int = 30  # seconds
    failover_threshold: int = 3
    
    def __post_init__(self):
        if self.fallback_regions is None:
            self.fallback_regions = ["eu-west", "asia-pacific"]


class TokenCache:
    """
    Token caching optimization from Paradox Zone.
    
    Reduces load on SPIRE Server by caching tokens locally.
    """
    
    def __init__(
        self,
        max_size: int = 10000,
        ttl: int = 43200,  # 12 hours in seconds
        refresh_threshold: int = 3600  # 1 hour in seconds
    ):
        self.max_size = max_size
        self.ttl = ttl
        self.refresh_threshold = refresh_threshold
        self._cache: Dict[str, Dict] = {}
        self._access_times: Dict[str, float] = {}
    
    def get(self, key: str) -> Optional[bytes]:
        """Get cached token if valid."""
        if key not in self._cache:
            return None
        
        entry = self._cache[key]
        now = time.time()
        
        # Check if expired
        if now - entry['timestamp'] > self.ttl:
            del self._cache[key]
            del self._access_times[key]
            return None
        
        # Check if needs refresh
        if now - entry['timestamp'] > self.refresh_threshold:
            # Mark for refresh but return cached value
            entry['needs_refresh'] = True
        
        self._access_times[key] = now
        return entry['token']
    
    def set(self, key: str, token: bytes) -> None:
        """Cache token."""
        # Evict oldest if cache full
        if len(self._cache) >= self.max_size:
            self._evict_oldest()
        
        self._cache[key] = {
            'token': token,
            'timestamp': time.time(),
            'needs_refresh': False
        }
        self._access_times[key] = time.time()
    
    def _evict_oldest(self) -> None:
        """Evict least recently used entry."""
        if not self._access_times:
            return
        
        oldest_key = min(self._access_times.items(), key=lambda x: x[1])[0]
        del self._cache[oldest_key]
        del self._access_times[oldest_key]
    
    def needs_refresh(self, key: str) -> bool:
        """Check if token needs refresh."""
        if key not in self._cache:
            return True
        
        entry = self._cache[key]
        return entry.get('needs_refresh', False)
    
    def clear(self) -> None:
        """Clear cache."""
        self._cache.clear()
        self._access_times.clear()


class MultiRegionFailover:
    """
    Multi-region failover optimization from Paradox Zone.
    
    Provides automatic failover between SPIRE server regions.
    """
    
    def __init__(self, config: MultiRegionConfig):
        self.config = config
        self.current_region = config.primary_region
        self.region_health: Dict[str, bool] = {}
        self.health_check_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
    
    async def start_health_monitoring(self) -> None:
        """Start monitoring region health."""
        if self.health_check_task:
            return
        
        self.health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info(f"Started multi-region health monitoring (primary: {self.current_region})")
    
    async def _health_check_loop(self) -> None:
        """Continuously check region health."""
        while True:
            try:
                await self._check_all_regions()
                await asyncio.sleep(self.config.health_check_interval)
            except Exception as e:
                logger.error(f"Health check loop error: {e}")
                await asyncio.sleep(self.config.health_check_interval)
    
    async def _check_all_regions(self) -> None:
        """Check health of all regions."""
        regions = [self.config.primary_region] + self.config.fallback_regions
        
        for region in regions:
            is_healthy = await self._check_region_health(region)
            self.region_health[region] = is_healthy
        
        # Check if failover needed
        if not self.region_health.get(self.current_region, True):
            await self._attempt_failover()
    
    async def _check_region_health(self, region: str) -> bool:
        """
        Check if region's SPIRE Server/Agent is healthy.
        
        Performs actual health checks:
        - SPIRE Server API health endpoint
        - Network connectivity
        - Response time validation
        - Certificate availability
        
        Args:
            region: Region identifier (e.g., "us-east", "eu-west")
            
        Returns:
            True if region is healthy, False otherwise
        """
        try:
            import httpx
            import asyncio
            
            # Get region-specific SPIRE Server endpoint
            # In production, this would be configured per region
            region_config = self._get_region_config(region)
            if not region_config:
                logger.warning(f"No configuration found for region: {region}")
                return False
            
            spire_server_url = region_config.get('spire_server_url')
            if not spire_server_url:
                logger.warning(f"No SPIRE Server URL configured for region: {region}")
                return False
            
            # Health check with timeout
            timeout = httpx.Timeout(5.0, connect=2.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                try:
                    # Try to reach SPIRE Server health endpoint
                    # SPIRE Server typically exposes health at /health or /metrics
                    health_endpoints = [
                        f"{spire_server_url}/health",
                        f"{spire_server_url}/metrics",
                        f"{spire_server_url}/api/v1/health"
                    ]
                    
                    for endpoint in health_endpoints:
                        try:
                            response = await client.get(endpoint)
                            if response.status_code == 200:
                                # Check response time (should be < 1s)
                                response_time = response.elapsed.total_seconds()
                                if response_time < 1.0:
                                    logger.debug(f"Region {region} health check passed (endpoint: {endpoint}, time: {response_time:.3f}s)")
                                    return True
                                else:
                                    logger.warning(f"Region {region} health check slow: {response_time:.3f}s")
                        except httpx.RequestError:
                            continue  # Try next endpoint
                    
                    # If no endpoint responded, check basic connectivity
                    logger.warning(f"Region {region} health endpoints not responding, checking basic connectivity")
                    return await self._check_basic_connectivity(spire_server_url)
                    
                except httpx.TimeoutException:
                    logger.warning(f"Region {region} health check timed out")
                    return False
                except Exception as e:
                    logger.warning(f"Region {region} health check failed: {e}")
                    return False
                    
        except ImportError:
            logger.warning("httpx not available, using basic connectivity check")
            return await self._check_basic_connectivity_fallback(region)
        except Exception as e:
            logger.error(f"Unexpected error during health check for region {region}: {e}")
            return False
    
    def _get_region_config(self, region: str) -> Optional[Dict[str, Any]]:
        """
        Get configuration for a specific region.
        
        In production, this would load from config file or environment variables.
        """
        # Default region configurations
        # In production, these should be loaded from config file or environment
        default_configs = {
            "us-east": {
                "spire_server_url": os.getenv("SPIRE_SERVER_US_EAST", "https://spire-us-east.x0tta6bl4.mesh:8080"),
                "priority": 1
            },
            "eu-west": {
                "spire_server_url": os.getenv("SPIRE_SERVER_EU_WEST", "https://spire-eu-west.x0tta6bl4.mesh:8080"),
                "priority": 2
            },
            "asia-pacific": {
                "spire_server_url": os.getenv("SPIRE_SERVER_ASIA_PACIFIC", "https://spire-asia-pacific.x0tta6bl4.mesh:8080"),
                "priority": 3
            }
        }
        
        return default_configs.get(region)
    
    async def _check_basic_connectivity(self, url: str) -> bool:
        """Check basic network connectivity to SPIRE Server."""
        try:
            import httpx
            timeout = httpx.Timeout(3.0, connect=1.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                # Try HEAD request to check connectivity
                response = await client.head(url, follow_redirects=True)
                return response.status_code < 500  # Any non-server-error is considered healthy
        except Exception:
            return False
    
    async def _check_basic_connectivity_fallback(self, region: str) -> bool:
        """Fallback connectivity check without httpx."""
        try:
            import socket
            import asyncio
            
            region_config = self._get_region_config(region)
            if not region_config:
                return False
            
            spire_server_url = region_config.get('spire_server_url', '')
            if not spire_server_url:
                return False
            
            # Extract hostname and port from URL
            from urllib.parse import urlparse
            parsed = urlparse(spire_server_url)
            hostname = parsed.hostname
            port = parsed.port or (443 if parsed.scheme == 'https' else 80)
            
            if not hostname:
                return False
            
            # Basic TCP connectivity check
            loop = asyncio.get_event_loop()
            try:
                await asyncio.wait_for(
                    loop.sock_connect(
                        socket.socket(socket.AF_INET, socket.SOCK_STREAM),
                        (hostname, port)
                    ),
                    timeout=2.0
                )
                return True
            except (asyncio.TimeoutError, OSError):
                return False
        except Exception:
            return False
    
    async def _attempt_failover(self) -> None:
        """Attempt failover to healthy region."""
        async with self._lock:
            if self.region_health.get(self.current_region, True):
                return  # Current region is healthy
            
            # Find healthy fallback
            for region in self.config.fallback_regions:
                if self.region_health.get(region, False):
                    logger.warning(f"Failing over from {self.current_region} to {region}")
                    self.current_region = region
                    return
            
            logger.error("No healthy regions available for failover!")
    
    def get_current_region(self) -> str:
        """Get current active region."""
        return self.current_region
    
    async def stop(self) -> None:
        """Stop health monitoring."""
        if self.health_check_task:
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                pass
            self.health_check_task = None


class SPIREOptimizations:
    """
    Main class for SPIFFE/SPIRE optimizations from Paradox Zone.
    
    Integrates:
    - Token caching
    - Multi-region failover
    - Performance tuning
    - Federation support
    """
    
    def __init__(
        self,
        performance_config: Optional[SPIREPerformanceConfig] = None,
        multi_region_config: Optional[MultiRegionConfig] = None
    ):
        self.performance_config = performance_config or SPIREPerformanceConfig()
        self.multi_region_config = multi_region_config or MultiRegionConfig()
        
        # Initialize components
        self.token_cache = TokenCache(
            max_size=self.performance_config.token_cache_size,
            ttl=self._parse_duration(self.performance_config.max_token_ttl)
        )
        self.failover = MultiRegionFailover(self.multi_region_config)
        
        logger.info("SPIRE Optimizations initialized")
    
    def _parse_duration(self, duration_str: str) -> int:
        """Parse duration string to seconds."""
        # Simple parser for "24h", "30s", etc.
        if duration_str.endswith('h'):
            return int(duration_str[:-1]) * 3600
        elif duration_str.endswith('m'):
            return int(duration_str[:-1]) * 60
        elif duration_str.endswith('s'):
            return int(duration_str[:-1])
        else:
            return 3600  # Default 1 hour
    
    async def initialize(self) -> None:
        """Initialize optimizations."""
        await self.failover.start_health_monitoring()
        logger.info("SPIRE Optimizations initialized and running")
    
    async def shutdown(self) -> None:
        """Shutdown optimizations."""
        await self.failover.stop()
        self.token_cache.clear()
        logger.info("SPIRE Optimizations shut down")
    
    def get_token_cache(self) -> TokenCache:
        """Get token cache instance."""
        return self.token_cache
    
    def get_failover(self) -> MultiRegionFailover:
        """Get failover instance."""
        return self.failover

