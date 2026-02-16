"""
PQC Performance Optimization
==============================

Optimizations for Post-Quantum Cryptography:
- Key caching for faster handshakes
- Batch processing for multiple peers
- eBPF acceleration (if available)
- Performance metrics and benchmarking
"""

import hashlib
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from src.security.post_quantum_liboqs import (LIBOQS_AVAILABLE, LibOQSBackend,
                                              PQKeyPair, PQMeshSecurityLibOQS)

logger = logging.getLogger(__name__)


@dataclass
class HandshakeMetrics:
    """Metrics for PQC handshake performance."""

    handshake_time_ms: float
    encapsulation_time_ms: float
    decapsulation_time_ms: float
    total_time_ms: float
    algorithm: str
    peer_id: str
    timestamp: float


class PQCKeyCache:
    """
    Cache for PQC keys to avoid regeneration.

    Caches:
    - Long-term keypairs (KEM, Signature)
    - Session keys for peers
    - Pre-computed encapsulations
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        """
        Initialize key cache.

        Args:
            max_size: Maximum number of cached entries
            ttl_seconds: Time-to-live for cached entries
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Tuple[PQKeyPair, float]] = {}
        self._session_keys: Dict[str, Tuple[bytes, float]] = {}
        self._lock = threading.RLock()

        logger.info(
            f"✅ PQC Key Cache initialized (max_size={max_size}, ttl={ttl_seconds}s)"
        )

    def get_or_generate_kem_keypair(
        self, key_id: str, backend: LibOQSBackend
    ) -> PQKeyPair:
        """
        Get cached KEM keypair or generate new one.

        Args:
            key_id: Unique identifier for keypair
            backend: LibOQS backend

        Returns:
            PQKeyPair
        """
        with self._lock:
            now = time.time()

            # Check cache
            if key_id in self._cache:
                keypair, cached_time = self._cache[key_id]
                if now - cached_time < self.ttl_seconds:
                    logger.debug(f"📦 Cache hit: KEM keypair {key_id}")
                    return keypair
                else:
                    # Expired, remove
                    del self._cache[key_id]

            # Generate new keypair
            logger.debug(f"🔑 Generating new KEM keypair: {key_id}")
            keypair = backend.generate_kem_keypair()

            # Cache it
            if len(self._cache) >= self.max_size:
                # Remove oldest entry
                oldest_key = min(self._cache.items(), key=lambda x: x[1][1])[0]
                del self._cache[oldest_key]

            self._cache[key_id] = (keypair, now)
            return keypair

    def get_or_generate_session_key(
        self, peer_id: str, public_key: bytes, backend: LibOQSBackend
    ) -> bytes:
        """
        Get cached session key or generate new one.

        Args:
            peer_id: Peer identifier
            public_key: Peer's public key
            backend: LibOQS backend

        Returns:
            Session key (shared secret)
        """
        with self._lock:
            now = time.time()
            cache_key = f"{peer_id}:{hashlib.sha256(public_key).hexdigest()[:16]}"

            # Check cache
            if cache_key in self._session_keys:
                session_key, cached_time = self._session_keys[cache_key]
                if now - cached_time < self.ttl_seconds:
                    logger.debug(f"📦 Cache hit: session key for {peer_id}")
                    return session_key
                else:
                    # Expired, remove
                    del self._session_keys[cache_key]

            # Generate new session key
            logger.debug(f"🔑 Generating new session key: {peer_id}")
            shared_secret, _ = backend.kem_encapsulate(public_key)

            # Cache it
            if len(self._session_keys) >= self.max_size:
                # Remove oldest entry
                oldest_key = min(self._session_keys.items(), key=lambda x: x[1][1])[0]
                del self._session_keys[oldest_key]

            self._session_keys[cache_key] = (shared_secret, now)
            return shared_secret

    def clear_expired(self):
        """Clear expired entries from cache."""
        with self._lock:
            now = time.time()

            # Clear expired keypairs
            expired_keys = [
                key_id
                for key_id, (_, cached_time) in self._cache.items()
                if now - cached_time >= self.ttl_seconds
            ]
            for key_id in expired_keys:
                del self._cache[key_id]

            # Clear expired session keys
            expired_sessions = [
                key
                for key, (_, cached_time) in self._session_keys.items()
                if now - cached_time >= self.ttl_seconds
            ]
            for key in expired_sessions:
                del self._session_keys[key]

            if expired_keys or expired_sessions:
                logger.debug(
                    f"🧹 Cleared {len(expired_keys)} keypairs and "
                    f"{len(expired_sessions)} session keys"
                )


class PQCPerformanceOptimizer:
    """
    Performance optimizer for PQC operations.

    Features:
    - Key caching
    - Batch processing
    - Performance metrics
    - eBPF acceleration (if available)
    """

    def __init__(
        self,
        kem_algorithm: str = "ML-KEM-768",
        sig_algorithm: str = "ML-DSA-65",
        enable_cache: bool = True,
        cache_size: int = 1000,
        cache_ttl: int = 3600,
    ):
        """
        Initialize PQC performance optimizer.

        Args:
            kem_algorithm: KEM algorithm
            sig_algorithm: Signature algorithm
            enable_cache: Enable key caching
            cache_size: Cache size
            cache_ttl: Cache TTL in seconds
        """
        if not LIBOQS_AVAILABLE:
            raise RuntimeError("liboqs-python required for PQC optimization")

        self.backend = LibOQSBackend(
            kem_algorithm=kem_algorithm, sig_algorithm=sig_algorithm
        )
        self.kem_algorithm = kem_algorithm
        self.sig_algorithm = sig_algorithm

        # Key cache
        self.cache = (
            PQCKeyCache(max_size=cache_size, ttl_seconds=cache_ttl)
            if enable_cache
            else None
        )

        # Performance metrics
        self.metrics: deque = deque(maxlen=1000)
        self._metrics_lock = threading.RLock()

        # eBPF acceleration (if available)
        self.ebpf_available = False
        self._init_ebpf()

        logger.info(
            f"✅ PQC Performance Optimizer initialized: "
            f"KEM={kem_algorithm}, SIG={sig_algorithm}, "
            f"Cache={'enabled' if enable_cache else 'disabled'}, "
            f"eBPF={'available' if self.ebpf_available else 'unavailable'}"
        )

    def _init_ebpf(self):
        """Initialize eBPF acceleration (if available)."""
        try:
            # Check if eBPF is available
            # In production, this would load actual eBPF programs
            # For now, we just check if the module exists
            import sys

            if "ebpf" in sys.modules or hasattr(
                sys.modules.get("src.network.ebpf", None), "XDPProgram"
            ):
                self.ebpf_available = True
                logger.info("✅ eBPF acceleration available")
            else:
                logger.debug("eBPF not available (optional)")
        except Exception as e:
            logger.debug(f"eBPF check failed: {e}")

    def optimized_handshake(
        self, peer_id: str, peer_public_key: bytes
    ) -> Tuple[bytes, HandshakeMetrics]:
        """
        Perform optimized PQC handshake with caching.

        Args:
            peer_id: Peer identifier
            peer_public_key: Peer's public KEM key

        Returns:
            (shared_secret, metrics)
        """
        start_time = time.time()

        # Encapsulation
        encap_start = time.time()
        if self.cache:
            shared_secret = self.cache.get_or_generate_session_key(
                peer_id, peer_public_key, self.backend
            )
        else:
            shared_secret, _ = self.backend.kem_encapsulate(peer_public_key)
        encap_time = (time.time() - encap_start) * 1000

        total_time = (time.time() - start_time) * 1000

        # Create metrics
        metrics = HandshakeMetrics(
            handshake_time_ms=total_time,
            encapsulation_time_ms=encap_time,
            decapsulation_time_ms=0.0,  # Not measured in one-way handshake
            total_time_ms=total_time,
            algorithm=self.kem_algorithm,
            peer_id=peer_id,
            timestamp=time.time(),
        )

        # Record metrics
        with self._metrics_lock:
            self.metrics.append(metrics)

        # Log if slow
        if total_time > 0.5:
            logger.warning(
                f"⚠️ Slow handshake: {total_time:.3f}ms (target: <0.5ms) "
                f"for {peer_id}"
            )
        else:
            logger.debug(f"✅ Fast handshake: {total_time:.3f}ms for {peer_id}")

        return shared_secret, metrics

    def batch_handshakes(
        self, peers: List[Tuple[str, bytes]]
    ) -> List[Tuple[str, bytes, HandshakeMetrics]]:
        """
        Perform batch handshakes for multiple peers.

        Args:
            peers: List of (peer_id, public_key) tuples

        Returns:
            List of (peer_id, shared_secret, metrics) tuples
        """
        start_time = time.time()
        results = []

        for peer_id, public_key in peers:
            shared_secret, metrics = self.optimized_handshake(peer_id, public_key)
            results.append((peer_id, shared_secret, metrics))

        total_time = (time.time() - start_time) * 1000
        avg_time = total_time / len(peers) if peers else 0

        logger.info(
            f"✅ Batch handshakes: {len(peers)} peers in {total_time:.3f}ms "
            f"(avg: {avg_time:.3f}ms per peer)"
        )

        return results

    def get_performance_stats(self) -> Dict[str, float]:
        """
        Get performance statistics.

        Returns:
            Dict with performance metrics
        """
        with self._metrics_lock:
            if not self.metrics:
                return {
                    "total_handshakes": 0,
                    "avg_handshake_time_ms": 0.0,
                    "min_handshake_time_ms": 0.0,
                    "max_handshake_time_ms": 0.0,
                    "p50_handshake_time_ms": 0.0,
                    "p95_handshake_time_ms": 0.0,
                    "p99_handshake_time_ms": 0.0,
                }

            times = [m.handshake_time_ms for m in self.metrics]
            sorted_times = sorted(times)
            n = len(sorted_times)

            return {
                "total_handshakes": n,
                "avg_handshake_time_ms": sum(times) / n,
                "min_handshake_time_ms": min(times),
                "max_handshake_time_ms": max(times),
                "p50_handshake_time_ms": sorted_times[n // 2],
                "p95_handshake_time_ms": sorted_times[int(n * 0.95)],
                "p99_handshake_time_ms": sorted_times[int(n * 0.99)],
            }

    def clear_cache(self):
        """Clear key cache."""
        if self.cache:
            self.cache._cache.clear()
            self.cache._session_keys.clear()
            logger.info("🧹 Key cache cleared")

    def cleanup(self):
        """Cleanup resources."""
        if self.cache:
            self.cache.clear_expired()
        logger.info("🧹 PQC optimizer cleanup completed")


# Enhanced PQMeshSecurity with performance optimization
class OptimizedPQMeshSecurity(PQMeshSecurityLibOQS):
    """
    Enhanced PQMeshSecurity with performance optimizations.

    Features:
    - Key caching
    - Batch processing
    - Performance metrics
    - eBPF acceleration (if available)
    """

    def __init__(
        self,
        node_id: str,
        kem_algorithm: str = "ML-KEM-768",
        sig_algorithm: str = "ML-DSA-65",
        enable_cache: bool = True,
    ):
        """
        Initialize optimized PQ mesh security.

        Args:
            node_id: Node identifier
            kem_algorithm: KEM algorithm
            sig_algorithm: Signature algorithm
            enable_cache: Enable key caching
        """
        super().__init__(node_id, kem_algorithm, sig_algorithm)

        # Performance optimizer
        self.optimizer = PQCPerformanceOptimizer(
            kem_algorithm=kem_algorithm,
            sig_algorithm=sig_algorithm,
            enable_cache=enable_cache,
        )

        logger.info(f"✅ Optimized PQ Mesh Security initialized for {node_id}")

    async def establish_secure_channel_optimized(
        self, peer_id: str, peer_public_keys: Dict
    ) -> Tuple[bytes, HandshakeMetrics]:
        """
        Establish secure channel with performance optimization.

        Args:
            peer_id: Peer identifier
            peer_public_keys: Peer's public keys

        Returns:
            (shared_secret, metrics)
        """
        peer_kem_key = bytes.fromhex(peer_public_keys["kem_public_key"])

        shared_secret, metrics = self.optimizer.optimized_handshake(
            peer_id, peer_kem_key
        )

        self._peer_keys[peer_id] = shared_secret

        logger.info(
            f"✅ Established optimized PQ-secure channel with {peer_id} "
            f"({metrics.handshake_time_ms:.3f}ms)"
        )

        return shared_secret, metrics

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        stats = self.optimizer.get_performance_stats()
        stats.update(
            {
                "ebpf_available": self.optimizer.ebpf_available,
                "cache_enabled": self.optimizer.cache is not None,
                "cache_size": (
                    len(self.optimizer.cache._cache) if self.optimizer.cache else 0
                ),
            }
        )
        return stats
