#!/usr/bin/env python3
"""
Rate Limiter Manager for x0tta6bl4 mesh network.

Provides both eBPF-based and software fallback rate limiting.
eBPF is used when available (requires root + BCC), otherwise
a Python-based token bucket implementation is used.
"""
import ctypes
import logging
import threading
import time
from typing import Any, Dict, Mapping, Optional

logger = logging.getLogger(__name__)

# Try to import Prometheus client (optional)
try:
    from prometheus_client import Counter

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    Counter = None  # type: ignore


class _NoopCounter:
    """Fallback counter when prometheus_client is unavailable."""

    def inc(self, amount: float = 1.0) -> None:
        return


def _build_counter(name: str, description: str):
    """Create a Prometheus counter with graceful fallback."""
    if not PROMETHEUS_AVAILABLE or Counter is None:
        return _NoopCounter()
    try:
        return Counter(name, description)
    except Exception as exc:
        logger.debug("Prometheus counter %s unavailable: %s", name, exc)
        return _NoopCounter()


PQC_PEER_SESSION_KEYS_SYNCED_TOTAL = _build_counter(
    "pqc_peer_session_keys_synced_total",
    "Total peer session keys synced into eBPF/software rate limiter state",
)
PQC_PEER_SESSION_KEY_MISS_TOTAL = _build_counter(
    "pqc_peer_session_key_miss_total",
    "Total packets denied due to missing peer PQC session key",
)

# Try to import BCC for eBPF support
try:
    from bcc import BPF
    BCC_AVAILABLE = True
except ImportError:
    BCC_AVAILABLE = False
    logger.warning("BCC not available - using software fallback rate limiter")


class SoftwareRateLimiter:
    """
    Software-based token bucket rate limiter.
    
    Provides equivalent functionality to eBPF rate limiter when
    eBPF is not available (no root, BCC not installed, etc).
    
    Uses token bucket algorithm:
    - Tokens are added at a constant rate (bytes_per_sec)
    - Packets consume tokens equal to their size
    - If insufficient tokens, packet is "dropped" (simulated)
    """
    
    def __init__(self):
        self._lock = threading.Lock()
        self._tokens: float = 0.0
        self._last_time: float = time.time()
        self._bytes_per_sec: int = 0  # 0 = unlimited
        self._dropped_packets: int = 0
        self._total_packets: int = 0
    
    def set_limit(self, bytes_per_sec: int) -> None:
        """Set bandwidth limit. 0 = unlimited."""
        with self._lock:
            self._bytes_per_sec = bytes_per_sec
            # Start with full bucket
            if bytes_per_sec > 0:
                self._tokens = float(bytes_per_sec)
            else:
                self._tokens = float('inf')
            self._last_time = time.time()
        
        limit_kbps = bytes_per_sec * 8 / 1024 if bytes_per_sec > 0 else float('inf')
        logger.info(f"Software rate limit set to {bytes_per_sec} bytes/sec ({limit_kbps:.1f} Kbps)")
    
    def apply_soft_lock(self) -> None:
        """Apply soft-lock: limit to 64 Kbps."""
        # 64 Kbps = 64 * 1024 / 8 = 8192 bytes/sec
        self.set_limit(64 * 1024 // 8)
    
    def check_and_consume(self, packet_size: int) -> bool:
        """
        Check if packet can be sent and consume tokens if allowed.
        
        Returns:
            True if packet allowed (tokens consumed)
            False if packet would be dropped (rate limit exceeded)
        """
        with self._lock:
            self._total_packets += 1
            
            if self._bytes_per_sec == 0:
                # Unlimited
                return True
            
            # Add tokens based on elapsed time
            now = time.time()
            elapsed = now - self._last_time
            self._last_time = now
            
            # Add tokens: rate * elapsed_time
            self._tokens += self._bytes_per_sec * elapsed
            
            # Cap tokens at max bucket size
            if self._tokens > self._bytes_per_sec:
                self._tokens = float(self._bytes_per_sec)
            
            # Check if we have enough tokens
            if self._tokens >= packet_size:
                self._tokens -= packet_size
                return True
            else:
                self._dropped_packets += 1
                return False
    
    def get_stats(self) -> dict:
        """Get rate limiter statistics."""
        with self._lock:
            drop_rate = self._dropped_packets / max(self._total_packets, 1)
            return {
                "bytes_per_sec": self._bytes_per_sec,
                "current_tokens": self._tokens,
                "total_packets": self._total_packets,
                "dropped_packets": self._dropped_packets,
                "drop_rate": drop_rate,
                "mode": "software"
            }


class RateLimiterManager:
    """
    Rate Limiter Manager with eBPF fallback to software implementation.
    
    Attempts to use eBPF for high-performance rate limiting, falls back
    to software implementation when eBPF is unavailable.
    """
    
    def __init__(self, interface: str = "singbox_tun"):
        self.interface = interface
        self.bpf: Optional[BPF] = None
        self._software_limiter: Optional[SoftwareRateLimiter] = None
        self._using_software_fallback: bool = False
        self._peer_session_keys: Dict[str, bytes] = {}
        self._pqc_session_map_writes: int = 0
        
        self._init_eBPF_or_fallback()

    def _ensure_pqc_state(self) -> None:
        """
        Backward-compatible lazy init for tests that bypass __init__ via __new__.
        """
        if not hasattr(self, "_peer_session_keys"):
            self._peer_session_keys = {}
        if not hasattr(self, "_pqc_session_map_writes"):
            self._pqc_session_map_writes = 0

    @staticmethod
    def _normalize_session_key(raw_key: Any) -> Optional[bytes]:
        """Normalize incoming session key representation to bytes."""
        if isinstance(raw_key, (bytes, bytearray, memoryview)):
            key_bytes = bytes(raw_key)
        elif isinstance(raw_key, str):
            cleaned = raw_key[2:] if raw_key.startswith("0x") else raw_key
            try:
                key_bytes = bytes.fromhex(cleaned)
            except ValueError:
                return None
        else:
            return None

        # 16 bytes minimum to support fast-path MAC/session key use-cases.
        if len(key_bytes) < 16:
            return None
        return key_bytes
    
    def _init_eBPF_or_fallback(self) -> None:
        """Initialize eBPF or fall back to software implementation."""
        if not BCC_AVAILABLE:
            logger.warning("BCC not available, using software rate limiter")
            self._enable_software_fallback()
            return
            
        try:
            # Check if we have root privileges
            import os
            if os.geteuid() != 0:
                logger.warning("Not running as root, using software rate limiter")
                self._enable_software_fallback()
                return
                
            with open("src/network/ebpf/rate_limiter.c", "r") as f:
                self.bpf = BPF(text=f.read())
            
            # Attach to egress using TC (Traffic Control)
            self.fn = self.bpf.load_func("handle_egress", BPF.SCHED_CLS)
            logger.info(f"eBPF Rate Limiter loaded for {self.interface}")
            
        except PermissionError as e:
            logger.warning(f"Permission denied for eBPF, using software fallback: {e}")
            self._enable_software_fallback()
        except FileNotFoundError as e:
            logger.warning(f"eBPF program file not found, using software fallback: {e}")
            self._enable_software_fallback()
        except Exception as e:
            logger.warning(f"Failed to load eBPF Rate Limiter: {e}, using software fallback")
            self._enable_software_fallback()
    
    def _enable_software_fallback(self) -> None:
        """Enable software rate limiter fallback."""
        self._using_software_fallback = True
        self._software_limiter = SoftwareRateLimiter()
        logger.info("Software rate limiter fallback enabled")

    def sync_peer_session_keys(self, peer_session_keys: Mapping[str, Any]) -> int:
        """
        Sync peer session keys from PQC KEM state (e.g. /mesh/kem/session).

        Args:
            peer_session_keys: Mapping peer_id -> session key bytes (or hex string)

        Returns:
            Number of accepted peer session keys.
        """
        self._ensure_pqc_state()
        normalized: Dict[str, bytes] = {}
        for peer_id, raw_key in peer_session_keys.items():
            key_bytes = self._normalize_session_key(raw_key)
            if key_bytes is None:
                logger.warning("Skipping invalid session key for peer %s", peer_id)
                continue
            normalized[str(peer_id)] = key_bytes

        self._peer_session_keys = normalized
        writes = len(normalized)
        self._pqc_session_map_writes += writes
        if writes:
            PQC_PEER_SESSION_KEYS_SYNCED_TOTAL.inc(writes)

        logger.info(
            "Synced %d peer PQC session keys into rate limiter state (mode=%s)",
            writes,
            "software" if self._using_software_fallback else "ebpf",
        )
        return writes

    def has_peer_session_key(self, peer_id: str) -> bool:
        """Check whether a peer has an active PQC session key."""
        self._ensure_pqc_state()
        return peer_id in self._peer_session_keys

    def get_peer_session_key(self, peer_id: str) -> Optional[bytes]:
        """Return peer session key bytes if present."""
        self._ensure_pqc_state()
        return self._peer_session_keys.get(peer_id)
    
    @property
    def is_using_software_fallback(self) -> bool:
        """Check if using software fallback."""
        return self._using_software_fallback
    
    def set_limit(self, bytes_per_sec: int) -> None:
        """
        Set bandwidth limit. 0 = unlimited.
        
        Args:
            bytes_per_sec: Maximum bytes per second (0 = unlimited)
        """
        if self._using_software_fallback:
            if self._software_limiter:
                self._software_limiter.set_limit(bytes_per_sec)
            return
            
        if not self.bpf:
            logger.warning("eBPF not initialized, enabling software fallback")
            self._enable_software_fallback()
            if self._software_limiter:
                self._software_limiter.set_limit(bytes_per_sec)
            return
        
        # eBPF implementation
        config_map = self.bpf["limit_config"]
        key = ctypes.c_uint32(0)
        
        class Config(ctypes.Structure):
            _fields_ = [
                ("max_bytes_per_sec", ctypes.c_uint64),
                ("last_time", ctypes.c_uint64),
                ("tokens", ctypes.c_uint64)
            ]
        
        cfg = Config()
        cfg.max_bytes_per_sec = ctypes.c_uint64(bytes_per_sec)
        cfg.last_time = ctypes.c_uint64(time.time_ns())
        cfg.tokens = ctypes.c_uint64(bytes_per_sec)  # Start with full bucket
        
        config_map[key] = cfg
        
        limit_kb = bytes_per_sec / 1024 if bytes_per_sec > 0 else float('inf')
        logger.info(f"✅ Bandwidth limit for {self.interface} set to {limit_kb:.1f} KB/s")
    
    def apply_soft_lock(self) -> None:
        """
        Apply soft-lock: degrade service to 64 Kbps.
        
        This is used when subscription is overdue - limits bandwidth
        to encourage renewal while allowing basic connectivity.
        """
        # 64 Kbps = 64 * 1024 / 8 = 8192 bytes/sec
        # NOT: 64 * 1024 // 8 * 1024 (which equals 8 MB/s)
        soft_limit = 64 * 1024 // 8  # = 8192 bytes/sec
        self.set_limit(soft_limit)
        logger.warning(f"🚨 Soft-lock applied: limited to {soft_limit} bytes/sec (64 Kbps)")
    
    def get_stats(self) -> dict:
        """Get rate limiter statistics."""
        self._ensure_pqc_state()
        if self._using_software_fallback and self._software_limiter:
            stats = self._software_limiter.get_stats()
        else:
            stats = {
                "mode": "ebpf",
                "interface": self.interface,
                "initialized": self.bpf is not None,
            }

        stats.update(
            {
                "peer_session_keys_loaded": len(self._peer_session_keys),
                "pqc_session_map_writes": self._pqc_session_map_writes,
            }
        )
        return stats
    
    def check_rate_limit(
        self,
        packet_size: int = 64,
        peer_id: Optional[str] = None,
        require_pqc_session: bool = False,
    ) -> bool:
        """
        Check if packet would be rate limited (software mode only).
        
        In eBPF mode, this check is done by the kernel.
        In software mode, this allows pre-check before sending.
        
        Args:
            packet_size: Size of packet in bytes
            peer_id: Optional peer identifier for PQC session-key lookup
            require_pqc_session: If True, deny packets without peer session key
            
        Returns:
            True if packet allowed, False if would be dropped
        """
        if require_pqc_session:
            self._ensure_pqc_state()
            if not peer_id or not self.has_peer_session_key(peer_id):
                PQC_PEER_SESSION_KEY_MISS_TOTAL.inc()
                logger.warning(
                    "Dropping packet due to missing PQC session key (peer_id=%s)",
                    peer_id,
                )
                return False

        if self._using_software_fallback and self._software_limiter:
            return self._software_limiter.check_and_consume(packet_size)
        
        # eBPF mode: kernel handles this
        return True
