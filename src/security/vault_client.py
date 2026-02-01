"""
Production-grade Vault client with HA support.

This module provides a robust async Vault client with:
- Kubernetes authentication
- Automatic token refresh
- Secret caching with TTL
- Prometheus metrics
- Retry logic with exponential backoff
- Health monitoring

Compatible with hvac >= 2.0
"""

import asyncio
import logging
import os
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import hvac
from hvac.exceptions import InvalidPath, VaultError
from hvac.api.auth_methods import Kubernetes
import prometheus_client as prom

logger = logging.getLogger(__name__)

# Prometheus metrics
vault_auth_latency = prom.Histogram(
    'vault_auth_latency_seconds',
    'Vault authentication latency',
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0)
)
vault_secret_retrieve_latency = prom.Histogram(
    'vault_secret_retrieve_latency_seconds',
    'Secret retrieval latency',
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0)
)
vault_secret_write_latency = prom.Histogram(
    'vault_secret_write_latency_seconds',
    'Secret write latency',
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0)
)
vault_auth_failures = prom.Counter(
    'vault_auth_failures_total',
    'Total authentication failures',
    ['reason']
)
vault_secret_failures = prom.Counter(
    'vault_secret_failures_total',
    'Total secret operation failures',
    ['operation', 'reason']
)
vault_health = prom.Gauge(
    'vault_health_status',
    'Vault health status (1=healthy, 0=unhealthy)'
)
vault_cache_hits = prom.Counter(
    'vault_cache_hits_total',
    'Total cache hits'
)
vault_cache_misses = prom.Counter(
    'vault_cache_misses_total',
    'Total cache misses'
)


class VaultAuthError(Exception):
    """Raised when Vault authentication fails"""
    pass


class VaultSecretError(Exception):
    """Raised when secret retrieval fails"""
    pass


class VaultClient:
    """Production-grade Vault client with HA support.
    
    Features:
    - Async operations with proper locking
    - Kubernetes JWT authentication
    - Automatic token refresh (at 80% TTL)
    - In-memory secret caching with TTL
    - Exponential backoff retry logic
    - Prometheus metrics integration
    - Health check support
    
    Example:
        >>> client = VaultClient(
        ...     vault_addr="https://vault:8200",
        ...     k8s_role="proxy-api",
        ...     verify_ca="/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
        ... )
        >>> await client.connect()
        >>> secret = await client.get_secret("proxy/api-credentials")
        >>> await client.close()
    """
    
    def __init__(
        self,
        vault_addr: str,
        vault_namespace: Optional[str] = None,
        k8s_role: str = "proxy-api",
        k8s_jwt_path: str = "/var/run/secrets/kubernetes.io/serviceaccount/token",
        verify_ca: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        retry_backoff: float = 2.0,
        cache_ttl: int = 3600,
        token_refresh_threshold: float = 0.8,
    ):
        """
        Initialize Vault client.
        
        Args:
            vault_addr: Vault server address (e.g., "https://vault:8200")
            vault_namespace: Vault namespace (optional, for Vault Enterprise)
            k8s_role: Kubernetes role name configured in Vault
            k8s_jwt_path: Path to K8s service account token
            verify_ca: Path to CA certificate for TLS verification
            max_retries: Number of retry attempts for operations
            retry_delay: Initial delay between retries (seconds)
            retry_backoff: Backoff multiplier for retries
            cache_ttl: Cache TTL in seconds
            token_refresh_threshold: Refresh token at this percentage of TTL
        """
        self.vault_addr = vault_addr
        self.vault_namespace = vault_namespace
        self.k8s_role = k8s_role
        self.k8s_jwt_path = k8s_jwt_path
        self.verify_ca = verify_ca
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.retry_backoff = retry_backoff
        self.cache_ttl = cache_ttl
        self.token_refresh_threshold = token_refresh_threshold
        
        # Client initialization
        self.client: Optional[hvac.Client] = None
        self._k8s_auth: Optional[Kubernetes] = None
        self.token: Optional[str] = None
        self.token_expiry: Optional[datetime] = None
        self.token_ttl: Optional[int] = None
        
        # Secret cache: {path: {data: {...}, expiry: datetime}}
        self._secret_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_expiry: Dict[str, datetime] = {}
        
        # State management
        self._lock = asyncio.Lock()
        self._authenticated = False
        self._degraded = False
        
    async def connect(self) -> None:
        """Establish connection to Vault and authenticate.
        
        This method is idempotent - multiple calls are safe.
        """
        async with self._lock:
            if self.client is not None:
                logger.debug("Vault client already initialized")
                return
            
            try:
                # Create HTTP client with TLS verification
                client_kwargs = {
                    'url': self.vault_addr,
                    'namespace': self.vault_namespace,
                }
                if self.verify_ca:
                    client_kwargs['verify'] = self.verify_ca
                
                self.client = hvac.Client(**client_kwargs)
                self._k8s_auth = Kubernetes(self.client.adapter)
                
                # Authenticate using K8s auth
                await self._authenticate()
                self._authenticated = True
                self._degraded = False
                vault_health.set(1)
                logger.info("Successfully connected to Vault at %s", self.vault_addr)
                
            except Exception as e:
                vault_health.set(0)
                self._degraded = True
                logger.error("Failed to connect to Vault: %s", e)
                raise VaultAuthError(f"Connection failed: {e}")
    
    async def _authenticate(self) -> None:
        """Authenticate using Kubernetes service account.
        
        Uses hvac 2.0+ style authentication via Kubernetes auth method.
        """
        start_time = datetime.now()
        
        for attempt in range(self.max_retries):
            try:
                # Read K8s JWT token
                jwt = await self._read_jwt_token()
                
                # Authenticate using hvac 2.0+ style
                auth_response = self._k8s_auth.login(
                    role=self.k8s_role,
                    jwt=jwt,
                )
                
                # Extract token and TTL
                self.token = auth_response['auth']['client_token']
                self.token_ttl = auth_response['auth']['lease_duration']
                
                # Set expiry (refresh at threshold % of TTL)
                refresh_seconds = self.token_ttl * self.token_refresh_threshold
                self.token_expiry = datetime.now() + timedelta(seconds=refresh_seconds)
                
                # Update client token
                self.client.token = self.token
                
                # Record metrics
                latency = (datetime.now() - start_time).total_seconds()
                vault_auth_latency.observe(latency)
                
                logger.info(
                    "Vault authentication successful. "
                    "Token TTL: %ds, refresh at: %s",
                    self.token_ttl,
                    self.token_expiry.isoformat()
                )
                return
                
            except Exception as e:
                vault_auth_failures.labels(reason=type(e).__name__).inc()
                
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (self.retry_backoff ** attempt)
                    logger.warning(
                        "Auth attempt %d/%d failed: %s. "
                        "Retrying in %.1fs...",
                        attempt + 1,
                        self.max_retries,
                        e,
                        delay
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "All %d auth attempts failed",
                        self.max_retries
                    )
                    raise VaultAuthError(f"Authentication failed: {e}")
    
    async def _read_jwt_token(self) -> str:
        """Read K8s service account JWT token from filesystem.
        
        Returns:
            JWT token string
            
        Raises:
            VaultAuthError: If token file cannot be read
        """
        try:
            loop = asyncio.get_event_loop()
            jwt = await loop.run_in_executor(
                None, self._read_jwt_sync
            )
            return jwt
        except FileNotFoundError:
            raise VaultAuthError(
                f"JWT token not found at {self.k8s_jwt_path}. "
                "Ensure running in Kubernetes with service account mounted."
            )
        except Exception as e:
            raise VaultAuthError(f"Failed to read JWT token: {e}")
    
    def _read_jwt_sync(self) -> str:
        """Synchronous JWT file read (for executor)."""
        with open(self.k8s_jwt_path, 'r') as f:
            return f.read().strip()
    
    async def _ensure_authenticated(self) -> None:
        """Ensure we're authenticated and token is valid.
        
        Automatically refreshes token if approaching expiry.
        """
        if not self._authenticated or self.client is None:
            await self.connect()
            return
        
        # Refresh token if needed
        if self.token_expiry and datetime.now() >= self.token_expiry:
            logger.info("Token approaching expiry, refreshing...")
            # Clear cache on token refresh (policy might have changed)
            self._clear_cache()
            await self._authenticate()
    
    async def get_secret(
        self,
        secret_path: str,
        secret_key: Optional[str] = None,
        use_cache: bool = True,
    ) -> Any:
        """Retrieve secret from Vault.
        
        Args:
            secret_path: Path to secret (e.g., "proxy/api-credentials")
            secret_key: Specific key to retrieve (optional)
            use_cache: Whether to use cached value
            
        Returns:
            Secret value or dict of all secrets at path
            
        Raises:
            VaultSecretError: If secret cannot be retrieved
        """
        await self._ensure_authenticated()
        
        # Check cache first
        if use_cache:
            cached_value = self._get_from_cache(secret_path, secret_key)
            if cached_value is not None:
                vault_cache_hits.inc()
                logger.debug("Cache hit for secret: %s", secret_path)
                return cached_value
            vault_cache_misses.inc()
        
        start_time = datetime.now()
        
        for attempt in range(self.max_retries):
            try:
                # Read secret from Vault
                response = self.client.secrets.kv.v2.read_secret_version(
                    path=secret_path,
                )
                
                secrets_data = response['data']['data']
                
                # Cache result
                if use_cache:
                    self._cache_secret(secret_path, secrets_data)
                
                # Record metrics
                latency = (datetime.now() - start_time).total_seconds()
                vault_secret_retrieve_latency.observe(latency)
                
                logger.debug("Retrieved secret from %s", secret_path)
                
                # Return specific key or all secrets
                if secret_key:
                    value = secrets_data.get(secret_key)
                    if value is None:
                        raise VaultSecretError(
                            f"Key '{secret_key}' not found in secret at {secret_path}"
                        )
                    return value
                return secrets_data
                
            except InvalidPath:
                vault_secret_failures.labels(
                    operation="read",
                    reason="not_found"
                ).inc()
                logger.error("Secret not found at %s", secret_path)
                raise VaultSecretError(f"Secret not found: {secret_path}")
                
            except VaultError as e:
                vault_secret_failures.labels(
                    operation="read",
                    reason="vault_error"
                ).inc()
                
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (self.retry_backoff ** attempt)
                    logger.warning(
                        "Secret retrieval attempt %d/%d failed: %s. "
                        "Retrying in %.1fs...",
                        attempt + 1,
                        self.max_retries,
                        e,
                        delay
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "Failed to retrieve secret after %d attempts",
                        self.max_retries
                    )
                    raise VaultSecretError(f"Retrieval failed: {e}")
    
    async def put_secret(
        self,
        secret_path: str,
        secret_data: Dict[str, Any],
    ) -> None:
        """Store secret in Vault.
        
        Args:
            secret_path: Path where to store secret
            secret_data: Secret data to store
            
        Raises:
            VaultSecretError: If secret cannot be stored
        """
        await self._ensure_authenticated()
        
        start_time = datetime.now()
        
        try:
            self.client.secrets.kv.v2.create_or_update_secret(
                path=secret_path,
                secret=secret_data,
            )
            
            # Invalidate cache
            self._invalidate_cache(secret_path)
            
            # Record metrics
            latency = (datetime.now() - start_time).total_seconds()
            vault_secret_write_latency.observe(latency)
            
            logger.info("Stored secret at %s", secret_path)
            
        except VaultError as e:
            vault_secret_failures.labels(
                operation="write",
                reason="vault_error"
            ).inc()
            logger.error("Failed to store secret: %s", e)
            raise VaultSecretError(f"Put secret failed: {e}")
    
    async def delete_secret(self, secret_path: str) -> None:
        """Delete secret from Vault.
        
        Args:
            secret_path: Path to secret to delete
            
        Raises:
            VaultSecretError: If secret cannot be deleted
        """
        await self._ensure_authenticated()
        
        try:
            self.client.secrets.kv.v2.delete_secret_version(
                path=secret_path,
            )
            
            # Invalidate cache
            self._invalidate_cache(secret_path)
            
            logger.info("Deleted secret at %s", secret_path)
            
        except VaultError as e:
            vault_secret_failures.labels(
                operation="delete",
                reason="vault_error"
            ).inc()
            logger.error("Failed to delete secret: %s", e)
            raise VaultSecretError(f"Delete failed: {e}")
    
    async def list_secrets(self, path: str) -> list:
        """List secrets at a path.
        
        Args:
            path: Path to list (e.g., "proxy/")
            
        Returns:
            List of secret names
        """
        await self._ensure_authenticated()
        
        try:
            response = self.client.secrets.kv.v2.list_secrets(
                path=path,
            )
            return response['data']['keys']
        except VaultError as e:
            logger.error("Failed to list secrets at %s: %s", path, e)
            raise VaultSecretError(f"List failed: {e}")
    
    def _get_from_cache(
        self,
        secret_path: str,
        secret_key: Optional[str] = None
    ) -> Optional[Any]:
        """Get secret from cache if valid."""
        if secret_path not in self._secret_cache:
            return None
        
        cache_time = self._cache_expiry.get(secret_path)
        if cache_time is None or datetime.now() >= cache_time:
            # Cache expired
            self._invalidate_cache(secret_path)
            return None
        
        cached_data = self._secret_cache[secret_path]
        if secret_key:
            return cached_data.get(secret_key)
        return cached_data
    
    def _cache_secret(self, secret_path: str, secret_data: Dict[str, Any]) -> None:
        """Cache secret data."""
        self._secret_cache[secret_path] = secret_data
        self._cache_expiry[secret_path] = (
            datetime.now() + timedelta(seconds=self.cache_ttl)
        )
    
    def _invalidate_cache(self, secret_path: str) -> None:
        """Invalidate cached secret."""
        if secret_path in self._secret_cache:
            del self._secret_cache[secret_path]
        if secret_path in self._cache_expiry:
            del self._cache_expiry[secret_path]
    
    def _clear_cache(self) -> None:
        """Clear all cached secrets."""
        self._secret_cache.clear()
        self._cache_expiry.clear()
        logger.debug("Secret cache cleared")
    
    async def health_check(self) -> bool:
        """Check Vault health status.
        
        Returns:
            True if Vault is healthy and initialized
        """
        try:
            if self.client is None:
                return False
            
            # Use read_health_status for comprehensive health check
            health = self.client.sys.read_health_status(method='GET')
            is_healthy = (
                health.get("initialized", False) and 
                not health.get("sealed", True)
            )
            
            vault_health.set(1 if is_healthy else 0)
            self._degraded = not is_healthy
            
            return is_healthy
            
        except Exception as e:
            logger.warning("Health check failed: %s", e)
            vault_health.set(0)
            self._degraded = True
            return False
    
    @property
    def is_healthy(self) -> bool:
        """Quick health check without API call."""
        return self._authenticated and not self._degraded
    
    @property
    def is_degraded(self) -> bool:
        """Check if client is in degraded state."""
        return self._degraded
    
    @property
    def authenticated(self) -> bool:
        """Check if client is authenticated."""
        return self._authenticated
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            'cached_secrets': len(self._secret_cache),
            'cache_ttl_seconds': self.cache_ttl,
        }
    
    async def close(self) -> None:
        """Close Vault connection and cleanup resources."""
        async with self._lock:
            if self.client:
                try:
                    self.client.close()
                except Exception as e:
                    logger.warning("Error closing Vault client: %s", e)
                finally:
                    self.client = None
                    self._k8s_auth = None
                    self._authenticated = False
                    self._clear_cache()
                    logger.info("Vault connection closed")