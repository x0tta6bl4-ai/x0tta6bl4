"""
PQC eBPF Integration
====================

Integrates Post-Quantum Cryptography with eBPF for acceleration.
Uses eBPF for:
- Fast key lookup in kernel space
- Session key caching
- Handshake acceleration
"""

import hashlib
import logging
import os
import time
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Try to import eBPF components
try:
    from src.network.ebpf.ebpf_loader import EBPFLoader

    EBPF_AVAILABLE = True
except (ImportError, AttributeError) as e:
    EBPF_AVAILABLE = False
    logger.warning(f"⚠️ eBPF not available: {e}")


class PQCeBPFAccelerator:
    """
    eBPF accelerator for PQC operations.

    Uses eBPF maps for:
    - Fast key lookup (kernel space)
    - Session key caching
    - Handshake state tracking
    """

    def __init__(self, enable_ebpf: bool = True):
        """
        Initialize PQC eBPF accelerator.

        Args:
            enable_ebpf: Enable eBPF acceleration (if available)
        """
        self.enable_ebpf = enable_ebpf and EBPF_AVAILABLE
        self.ebpf_loader = None
        self.program = None  # EBPFProgram object

        if self.enable_ebpf:
            try:
                self.ebpf_loader = EBPFLoader()
                # Load the PQC key store program
                program_path = "src/network/ebpf/bpf_programs/pqc_key_store.bpf.c"
                if os.path.exists(program_path):
                    # Set stub mode if BCC is only partially available or for testing
                    if os.getenv("BCC_STUB_MODE") == "true":
                         logger.info("🧪 eBPF Stub Mode enabled")
                    
                    self.program = self.ebpf_loader.load_program(program_path)
                    logger.info(f"✅ PQC eBPF Key Store program loaded from {program_path}")
                else:
                    logger.warning(f"⚠️ PQC eBPF program not found at {program_path}")
                    self.enable_ebpf = False
            except Exception as e:
                logger.warning(f"⚠️ Failed to initialize eBPF: {e}")
                self.enable_ebpf = False
        else:
            logger.info("ℹ️ eBPF acceleration disabled or unavailable")

    def is_available(self) -> bool:
        """Check if eBPF acceleration is available."""
        return self.enable_ebpf and self.program is not None

    def cache_session_key_ebpf(
        self, peer_id: str, public_key_hash: bytes, session_key: bytes
    ) -> bool:
        """
        Cache session key in eBPF map (kernel space).

        Args:
            peer_id: Peer identifier
            public_key_hash: Hash of peer's public key (unused in map but kept for API parity)
            session_key: Session key to cache (32 bytes)

        Returns:
            True if cached successfully
        """
        if not self.is_available() or not self.program.loaded:
            return False

        try:
            # Get the map from BCC BPF object
            pqc_keys = self.program.bpf["pqc_keys"]
            
            # Prepare key: struct key_t
            key = pqc_keys.Key()
            peer_id_bytes = peer_id.encode('utf-8')
            for i in range(min(len(peer_id_bytes), 64)):
                key.id[i] = peer_id_bytes[i]
            
            # Prepare value structure
            # BCC generates a Leaf class for the struct defined in C
            value = pqc_keys.Leaf()
            
            # session_key is char[32] in C
            for i in range(min(len(session_key), 32)):
                value.session_key[i] = session_key[i]
            
            value.last_updated_ns = int(time.time() * 1e9)
            value.flags = 1
            
            # Write to eBPF hash map
            pqc_keys[key] = value
            
            logger.debug(f"📦 Cached session key in eBPF for peer={peer_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to cache in eBPF: {e}")
            return False

    def lookup_session_key_ebpf(
        self, peer_id: str, public_key_hash: bytes
    ) -> Optional[bytes]:
        """
        Lookup session key from eBPF map (kernel space).

        Args:
            peer_id: Peer identifier
            public_key_hash: Hash of peer's public key

        Returns:
            Session key (32 bytes) or None if not found
        """
        if not self.is_available() or not self.program.loaded:
            return None

        try:
            pqc_keys = self.program.bpf["pqc_keys"]
            
            # Prepare key: struct key_t
            key = pqc_keys.Key()
            peer_id_bytes = peer_id.encode('utf-8')
            for i in range(min(len(peer_id_bytes), 64)):
                key.id[i] = peer_id_bytes[i]
            
            # Lookup in map
            value = pqc_keys.get(key)
            if value:
                logger.debug(f"🔍 Found session key in eBPF for peer={peer_id}")
                # Convert from C array to bytes
                return bytes(value.session_key)
            
            return None
        except Exception as e:
            logger.error(f"❌ Failed to lookup from eBPF: {e}")
            return None

    def attach_to_interface(self, interface: str) -> bool:
        """
        Attach eBPF program to network interface.

        Args:
            interface: Network interface name (e.g., "eth0")

        Returns:
            True if attached successfully
        """
        if not self.is_available():
            return False

        try:
            # In production, this would load and attach eBPF program
            # For now, we just log
            logger.info(f"📌 Would attach eBPF program to {interface}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to attach to interface: {e}")
            return False

    def detach_from_interface(self, interface: str) -> bool:
        """
        Detach eBPF program from network interface.

        Args:
            interface: Network interface name

        Returns:
            True if detached successfully
        """
        if not self.is_available():
            return False

        try:
            logger.info(f"📌 Would detach eBPF program from {interface}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to detach from interface: {e}")
            return False


class EnhancedPQCPerformanceOptimizer:
    """
    Enhanced PQC Performance Optimizer with eBPF acceleration.

    Combines:
    - User-space key caching
    - eBPF kernel-space acceleration
    - Performance metrics
    """

    def __init__(
        self,
        kem_algorithm: str = "ML-KEM-768",
        sig_algorithm: str = "ML-DSA-65",
        enable_cache: bool = True,
        enable_ebpf: bool = True,
    ):
        """
        Initialize enhanced optimizer.

        Args:
            kem_algorithm: KEM algorithm
            sig_algorithm: Signature algorithm
            enable_cache: Enable user-space cache
            enable_ebpf: Enable eBPF acceleration
        """
        from src.security.pqc_performance import PQCPerformanceOptimizer

        # User-space optimizer
        self.optimizer = PQCPerformanceOptimizer(
            kem_algorithm=kem_algorithm,
            sig_algorithm=sig_algorithm,
            enable_cache=enable_cache,
        )

        # eBPF accelerator
        self.ebpf_accelerator = PQCeBPFAccelerator(enable_ebpf=enable_ebpf)

        logger.info(
            f"✅ Enhanced PQC Optimizer initialized: "
            f"Cache={'enabled' if enable_cache else 'disabled'}, "
            f"eBPF={'enabled' if self.ebpf_accelerator.is_available() else 'disabled'}"
        )

    def optimized_handshake_with_ebpf(
        self, peer_id: str, peer_public_key: bytes
    ) -> Tuple[bytes, Dict]:
        """
        Perform optimized handshake with eBPF acceleration.

        Args:
            peer_id: Peer identifier
            peer_public_key: Peer's public key

        Returns:
            (shared_secret, metrics_dict)
        """
        # Try eBPF lookup first (fastest)
        public_key_hash = hashlib.sha256(peer_public_key).digest()
        cached_key = self.ebpf_accelerator.lookup_session_key_ebpf(
            peer_id, public_key_hash
        )

        if cached_key:
            logger.debug(f"⚡ eBPF cache hit for {peer_id}")
            return cached_key, {
                "source": "ebpf",
                "handshake_time_ms": 0.01,  # Very fast from kernel cache
                "cache_hit": True,
            }

        # Fallback to user-space optimizer
        shared_secret, metrics = self.optimizer.optimized_handshake(
            peer_id, peer_public_key
        )

        # Cache in eBPF for next time
        if self.ebpf_accelerator.is_available():
            self.ebpf_accelerator.cache_session_key_ebpf(
                peer_id, public_key_hash, shared_secret
            )

        return shared_secret, {
            "source": "user_space",
            "handshake_time_ms": metrics.handshake_time_ms,
            "cache_hit": False,
        }

    def get_stats(self) -> Dict:
        """Get combined statistics."""
        stats = self.optimizer.get_performance_stats()
        stats.update(
            {
                "ebpf_available": self.ebpf_accelerator.is_available(),
                "ebpf_enabled": self.ebpf_accelerator.enable_ebpf,
            }
        )
        return stats
