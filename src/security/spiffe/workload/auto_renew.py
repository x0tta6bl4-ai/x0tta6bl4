"""
SPIFFE Auto-Renew Service

Provides automatic credential renewal for SPIFFE SVIDs (X.509 and JWT).
Monitors SVID expiration and automatically fetches new credentials before expiry.

Features:
- Automatic X.509 SVID renewal
- Automatic JWT SVID renewal (per audience)
- Configurable renewal threshold
- Background task management
- Error handling and retry logic
- Integration with WorkloadAPIClient
"""

import asyncio
import logging
import time
from typing import Optional, Dict, List, Set, Callable, TYPE_CHECKING, Any
from datetime import datetime, timedelta
from dataclasses import dataclass

from prometheus_client import Gauge, Counter

logger = logging.getLogger(__name__)

# Type hints only - avoid circular import with api_client.py
if TYPE_CHECKING:
    from src.security.spiffe.workload.api_client import (
        WorkloadAPIClient,
        X509SVID,
        JWTSVID
    )

# Prometheus Metrics
SVID_X509_EXPIRY_TIMESTAMP = Gauge(
    'spiffe_svid_x509_expiry_timestamp_seconds',
    'Unix timestamp of the X.509 SVID expiration.'
)
SVID_JWT_EXPIRY_TIMESTAMP = Gauge(
    'spiffe_svid_jwt_expiry_timestamp_seconds',
    'Unix timestamp of the JWT SVID expiration.',
    ['audience']
)
AUTO_RENEW_SUCCESS_TOTAL = Counter(
    'spiffe_auto_renew_success_total',
    'Total number of successful SVID auto-renewal operations.',
    ['svid_type']
)
AUTO_RENEW_FAILURE_TOTAL = Counter(
    'spiffe_auto_renew_failure_total',
    'Total number of failed SVID auto-renewal operations.',
    ['svid_type']
)

# Runtime import check (deferred to avoid circular import)
SPIFFE_CLIENT_AVAILABLE = False

def _check_spiffe_client() -> bool:
    """Check if SPIFFE client is available (deferred import)."""
    global SPIFFE_CLIENT_AVAILABLE
    try:
        from src.security.spiffe.workload.api_client import WorkloadAPIClient
        SPIFFE_CLIENT_AVAILABLE = True
        return True
    except ImportError:
        logger.warning("⚠️ SPIFFE WorkloadAPIClient not available")
        return False


@dataclass
class AutoRenewConfig:
    """Configuration for auto-renewal service."""
    renewal_threshold: float = 0.5  # Renew at 50% of TTL (default: 12h for 24h cert)
    check_interval: float = 300.0  # Check every 5 minutes
    min_ttl: float = 3600.0  # Minimum TTL to consider (1 hour)
    max_retries: int = 3  # Max retries on failure
    retry_delay: float = 60.0  # Delay between retries (1 minute)
    enabled: bool = True  # Enable/disable auto-renewal


class SPIFFEAutoRenew:
    """
    Automatic credential renewal service for SPIFFE SVIDs.
    
    Monitors X.509 and JWT SVIDs and automatically renews them before expiry.
    Runs as a background async task.
    
    Example:
        >>> client = WorkloadAPIClient()
        >>> auto_renew = SPIFFEAutoRenew(client)
        >>> await auto_renew.start()
        >>> # ... credentials are automatically renewed ...
        >>> await auto_renew.stop()
    """
    
    def __init__(
        self,
        client: "WorkloadAPIClient",
        config: Optional[AutoRenewConfig] = None
    ):
        """
        Initialize auto-renewal service.
        
        Args:
            client: WorkloadAPIClient instance
            config: Auto-renewal configuration (uses defaults if None)
        """
        if not SPIFFE_CLIENT_AVAILABLE:
            raise ImportError("SPIFFE WorkloadAPIClient not available")
        
        self.client = client
        self.config = config or AutoRenewConfig()
        
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
        # Track JWT audiences that need renewal
        self._jwt_audiences: Set[tuple] = set()
        
        # Callbacks for renewal events
        self._on_x509_renewed: Optional[Callable[["X509SVID"], None]] = None
        self._on_jwt_renewed: Optional[Callable[["JWTSVID"], None]] = None
        self._on_renewal_failed: Optional[Callable[[str, Exception], None]] = None
        
        logger.info("✅ SPIFFE Auto-Renew service initialized")
    
    def register_jwt_audience(self, audience: List[str]):
        """
        Register a JWT audience for auto-renewal.
        
        Args:
            audience: List of JWT audience strings
        """
        audience_key = tuple(sorted(audience))
        self._jwt_audiences.add(audience_key)
        logger.debug(f"Registered JWT audience for auto-renewal: {audience}")
    
    def unregister_jwt_audience(self, audience: List[str]):
        """
        Unregister a JWT audience from auto-renewal.
        
        Args:
            audience: List of JWT audience strings
        """
        audience_key = tuple(sorted(audience))
        self._jwt_audiences.discard(audience_key)
        logger.debug(f"Unregistered JWT audience: {audience}")
    
    def set_on_x509_renewed(self, callback: Callable[["X509SVID"], None]):
        """Set callback for X.509 SVID renewal events."""
        self._on_x509_renewed = callback
    
    def set_on_jwt_renewed(self, callback: Callable[["JWTSVID"], None]):
        """Set callback for JWT SVID renewal events."""
        self._on_jwt_renewed = callback
    
    def set_on_renewal_failed(self, callback: Callable[[str, Exception], None]):
        """Set callback for renewal failure events."""
        self._on_renewal_failed = callback
    
    async def start(self):
        """
        Start auto-renewal service.
        
        Runs as a background task that periodically checks SVID expiration
        and renews credentials as needed.
        """
        if self._running:
            logger.warning("Auto-renewal service already running")
            return
        
        if not self.config.enabled:
            logger.info("Auto-renewal is disabled in config")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._renewal_loop())
        logger.info("✅ SPIFFE Auto-Renew service started")
    
    async def stop(self):
        """Stop auto-renewal service."""
        if not self._running:
            return
        
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("✅ SPIFFE Auto-Renew service stopped")
    
    async def _renewal_loop(self):
        """Main renewal loop that runs in background."""
        while self._running:
            try:
                # Check X.509 SVID
                await self._check_and_renew_x509()
                
                # Check JWT SVIDs
                await self._check_and_renew_jwts()
                
                # Wait before next check
                await asyncio.sleep(self.config.check_interval)
                
            except asyncio.CancelledError:
                logger.info("Auto-renewal loop cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Error in renewal loop: {e}")
                await asyncio.sleep(self.config.retry_delay)
    
    async def _check_and_renew_x509(self):
        """Check X.509 SVID expiration and renew if needed."""
        try:
            current_svid = self.client.current_svid
            
            if not current_svid:
                # No SVID yet, fetch initial one
                logger.debug("No X.509 SVID cached, fetching initial SVID")
                new_svid = await self._renew_x509_with_retry() # Use retry mechanism for initial fetch
                if new_svid:
                    logger.info("✅ Initial X.509 SVID fetched")
                    SVID_X509_EXPIRY_TIMESTAMP.set(new_svid.expiry.timestamp())
                    AUTO_RENEW_SUCCESS_TOTAL.labels(svid_type='x509').inc()
                    if self._on_x509_renewed:
                        self._on_x509_renewed(new_svid)
                else:
                    logger.error("❌ Failed to fetch initial X.509 SVID")
                    AUTO_RENEW_FAILURE_TOTAL.labels(svid_type='x509').inc()
                    if self._on_renewal_failed:
                        self._on_renewal_failed("x509", Exception("Initial fetch failed"))
                return
            
            # Check if renewal is needed
            if self._needs_renewal(current_svid):
                logger.info(
                    f"🔄 X.509 SVID needs renewal "
                    f"(expires: {current_svid.expiry.isoformat()})"
                )
                
                # Attempt renewal with retries
                new_svid = await self._renew_x509_with_retry()
                
                if new_svid:
                    logger.info(
                        f"✅ X.509 SVID renewed successfully "
                        f"(new expiry: {new_svid.expiry.isoformat()})"
                    )
                    SVID_X509_EXPIRY_TIMESTAMP.set(new_svid.expiry.timestamp())
                    AUTO_RENEW_SUCCESS_TOTAL.labels(svid_type='x509').inc()
                    if self._on_x509_renewed:
                        self._on_x509_renewed(new_svid)
                else:
                    logger.error("❌ Failed to renew X.509 SVID after retries")
                    AUTO_RENEW_FAILURE_TOTAL.labels(svid_type='x509').inc()
                    if self._on_renewal_failed:
                        self._on_renewal_failed("x509", Exception("Renewal failed after retries"))
            else:
                # Calculate time until renewal
                time_until_renewal = self._time_until_renewal(current_svid)
                logger.debug(
                    f"X.509 SVID still valid "
                    f"(expires: {current_svid.expiry.isoformat()}, "
                    f"renewal in: {time_until_renewal:.0f}s)"
                )
                SVID_X509_EXPIRY_TIMESTAMP.set(current_svid.expiry.timestamp()) # Ensure metric is always updated
                
        except Exception as e:
            logger.error(f"❌ Error checking X.509 SVID: {e}")
            AUTO_RENEW_FAILURE_TOTAL.labels(svid_type='x509').inc()
            if self._on_renewal_failed:
                self._on_renewal_failed("x509", e)

    
    async def _check_and_renew_jwts(self):
        """Check JWT SVID expiration and renew if needed."""
        for audience_key in list(self._jwt_audiences):
            try:
                audience = list(audience_key)
                audience_str = ",".join(audience)
                
                # Get cached JWT if available
                cached_jwt = self.client._jwt_cache.get(audience_key)
                
                if not cached_jwt or cached_jwt.is_expired():
                    # No JWT or expired, fetch new one
                    logger.debug(f"Fetching JWT SVID for audience: {audience}")
                    new_jwt = await self._renew_jwt_with_retry(audience) # Use retry mechanism for initial fetch
                    if new_jwt:
                        logger.info(f"✅ JWT SVID fetched for audience: {audience}")
                        SVID_JWT_EXPIRY_TIMESTAMP.labels(audience=audience_str).set(new_jwt.expiry.timestamp())
                        AUTO_RENEW_SUCCESS_TOTAL.labels(svid_type='jwt').inc()
                        if self._on_jwt_renewed:
                            self._on_jwt_renewed(new_jwt)
                    else:
                        logger.error(f"❌ Failed to fetch initial JWT SVID for audience: {audience}")
                        AUTO_RENEW_FAILURE_TOTAL.labels(svid_type='jwt').inc()
                        if self._on_renewal_failed:
                            self._on_renewal_failed(f"jwt:{audience_str}", Exception("Initial fetch failed"))
                    continue
                
                # Check if renewal is needed
                if self._needs_renewal(cached_jwt):
                    logger.info(
                        f"🔄 JWT SVID needs renewal for audience {audience} "
                        f"(expires: {cached_jwt.expiry.isoformat()})"
                    )
                    
                    # Attempt renewal with retries
                    new_jwt = await self._renew_jwt_with_retry(audience)
                    
                    if new_jwt:
                        logger.info(
                            f"✅ JWT SVID renewed for audience {audience} "
                            f"(new expiry: {new_jwt.expiry.isoformat()})"
                        )
                        SVID_JWT_EXPIRY_TIMESTAMP.labels(audience=audience_str).set(new_jwt.expiry.timestamp())
                        AUTO_RENEW_SUCCESS_TOTAL.labels(svid_type='jwt').inc()
                        if self._on_jwt_renewed:
                            self._on_jwt_renewed(new_jwt)
                    else:
                        logger.error(f"❌ Failed to renew JWT SVID for audience {audience}")
                        AUTO_RENEW_FAILURE_TOTAL.labels(svid_type='jwt').inc()
                        if self._on_renewal_failed:
                            self._on_renewal_failed(f"jwt:{audience_str}", Exception("Renewal failed"))
                else:
                    time_until_renewal = self._time_until_renewal(cached_jwt)
                    logger.debug(
                        f"JWT SVID still valid for audience {audience} "
                        f"(renewal in: {time_until_renewal:.0f}s)"
                    )
                    SVID_JWT_EXPIRY_TIMESTAMP.labels(audience=audience_str).set(cached_jwt.expiry.timestamp()) # Ensure metric is always updated
                    
            except Exception as e:
                logger.error(f"❌ Error checking JWT SVID for audience {audience_key}: {e}")
                AUTO_RENEW_FAILURE_TOTAL.labels(svid_type='jwt').inc()
                if self._on_renewal_failed:
                    self._on_renewal_failed(f"jwt:{audience_key}", e)
    
    def _needs_renewal(self, svid) -> bool:
        """
        Check if SVID needs renewal based on threshold.
        
        Args:
            svid: X509SVID or JWTSVID instance
        
        Returns:
            True if renewal is needed
        """
        if svid.is_expired():
            return True
        
        # Calculate time until expiry
        now = datetime.utcnow()
        time_until_expiry = (svid.expiry - now).total_seconds()
        
        # Estimate TTL (default to 24 hours if not available)
        # For SPIFFE, typical TTL is 24 hours
        estimated_ttl = 86400.0  # 24 hours in seconds
        
        # Calculate threshold time
        threshold_time = estimated_ttl * self.config.renewal_threshold
        
        # Renew if time until expiry is less than threshold
        return time_until_expiry < threshold_time
    
    def _time_until_renewal(self, svid) -> float:
        """
        Calculate time until renewal is needed.
        
        Args:
            svid: X509SVID or JWTSVID instance
        
        Returns:
            Time in seconds until renewal is needed
        """
        if svid.is_expired():
            return 0.0
        
        now = datetime.utcnow()
        time_until_expiry = (svid.expiry - now).total_seconds()
        
        # Estimate TTL
        estimated_ttl = 86400.0  # 24 hours
        threshold_time = estimated_ttl * self.config.renewal_threshold
        
        # Time until renewal = time until expiry - threshold
        return max(0.0, time_until_expiry - threshold_time)
    
    async def _renew_x509_with_retry(self) -> Optional["X509SVID"]:
        """Renew X.509 SVID with retry logic."""
        for attempt in range(self.config.max_retries):
            try:
                # Run in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                new_svid = await loop.run_in_executor(
                    None,
                    self.client.fetch_x509_svid
                )
                return new_svid
            except Exception as e:
                logger.warning(
                    f"X.509 renewal attempt {attempt + 1}/{self.config.max_retries} failed: {e}"
                )
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay)
                else:
                    logger.error(f"All X.509 renewal attempts failed")
        
        return None
    
    async def _renew_jwt_with_retry(self, audience: List[str]) -> Optional["JWTSVID"]:
        """Renew JWT SVID with retry logic."""
        for attempt in range(self.config.max_retries):
            try:
                # Run in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                new_jwt = await loop.run_in_executor(
                    None,
                    lambda: self.client.fetch_jwt_svid(audience)
                )
                return new_jwt
            except Exception as e:
                logger.warning(
                    f"JWT renewal attempt {attempt + 1}/{self.config.max_retries} "
                    f"for audience {audience} failed: {e}"
                )
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay)
                else:
                    logger.error(f"All JWT renewal attempts failed for audience {audience}")
        
        return None
    
    def is_running(self) -> bool:
        """Check if auto-renewal service is running."""
        return self._running


def create_auto_renew(
    client: "WorkloadAPIClient",
    renewal_threshold: float = 0.5,
    check_interval: float = 300.0
) -> SPIFFEAutoRenew:
    """
    Factory function to create auto-renewal service.
    
    Args:
        client: WorkloadAPIClient instance
        renewal_threshold: Renew at this fraction of TTL (default: 0.5 = 50%)
        check_interval: Check interval in seconds (default: 300 = 5 minutes)
    
    Returns:
        SPIFFEAutoRenew instance
    """
    config = AutoRenewConfig(
        renewal_threshold=renewal_threshold,
        check_interval=check_interval
    )
    return SPIFFEAutoRenew(client, config)

