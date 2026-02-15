#!/usr/bin/env python3
"""
PQC Verification Daemon for x0tta6bl4
Userspace offload for ML-DSA-65 signature verification.

This daemon:
1. Reads PQC verification events from eBPF ring buffer
2. Performs ML-DSA-65 signature verification using liboqs
3. Updates pqc_verified_sessions BPF map on success
4. Integrates with MAPE-K loop for anomaly reporting

Architecture:
    eBPF XDP (kernel) --[ring buffer]--> Daemon (userspace) --[BPF map]--> eBPF XDP

The XDP program sends unverified packets to userspace, daemon verifies,
and marks sessions as verified in BPF map for fast-path processing.
"""

import hashlib
import logging
import os
import signal
import struct
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Try to import BCC
try:
    from bcc import BPF

    BCC_AVAILABLE = True
except ImportError:
    BCC_AVAILABLE = False
    logger.warning("BCC not available - daemon will run in mock mode")

# Try to import liboqs
try:
    import oqs

    LIBOQS_AVAILABLE = True
except ImportError:
    LIBOQS_AVAILABLE = False
    logger.warning("liboqs not available - using mock verification")


@dataclass
class PQCVerificationEvent:
    """Event received from eBPF for PQC verification"""

    session_id: bytes  # 16 bytes
    signature: bytes  # Variable length ML-DSA-65 signature
    payload_hash: bytes  # SHA-256 of payload (32 bytes)
    pubkey_id: bytes  # 16 bytes - identifier for public key lookup
    timestamp: int  # Nanoseconds


@dataclass
class VerifiedSession:
    """A verified PQC session"""

    session_id: bytes
    expiration: int  # Unix timestamp
    verification_count: int = 0
    last_verified: float = 0


class PQCVerificationDaemon:
    """
    Userspace daemon for ML-DSA-65 signature verification.

    Offloads PQC verification from eBPF kernel space to userspace
    where liboqs can perform full CRYSTALS-Dilithium verification.
    """

    # Event format from eBPF ring buffer
    # struct pqc_event {
    #     __u8 session_id[16];
    #     __u8 signature[4627];  // ML-DSA-65 max signature size
    #     __u16 signature_len;
    #     __u8 payload_hash[32];
    #     __u8 pubkey_id[16];
    #     __u64 timestamp;
    # };
    EVENT_SIZE = 16 + 4627 + 2 + 32 + 16 + 8  # 4701 bytes

    # Session expiration time (1 hour in nanoseconds)
    SESSION_TTL_NS = 3600 * 1_000_000_000

    def __init__(
        self,
        bpf: Optional["BPF"] = None,  # Changed 'BPF' to string literal
        public_key_store: Optional[Dict[bytes, bytes]] = None,
        anomaly_callback: Optional[Callable[[str, Dict], None]] = None,
    ):
        """
        Initialize the PQC verification daemon.

        Args:
            bpf: BPF object with loaded XDP program (optional for testing)
            public_key_store: Dict mapping pubkey_id -> ML-DSA-65 public key
            anomaly_callback: Function to call on verification anomalies
        """
        self.bpf = bpf
        self.public_keys = public_key_store or {}
        self.anomaly_callback = anomaly_callback

        # Verified sessions cache
        self.verified_sessions: Dict[bytes, VerifiedSession] = {}

        # Statistics
        self.stats = {
            "events_received": 0,
            "verifications_success": 0,
            "verifications_failed": 0,
            "unknown_pubkey": 0,
            "expired_sessions": 0,
        }

        # ML-DSA-65 verifier
        if LIBOQS_AVAILABLE:
            self.sig = oqs.Signature("ML-DSA-65")
            logger.info("ML-DSA-65 verifier initialized via liboqs")
        else:
            self.sig = None
            logger.warning("Running in mock mode - no real PQC verification")

        # Thread pool for parallel verification
        self.executor = ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="pqc-verify"
        )

        # Shutdown flag
        self.running = False

        # BPF maps
        self.pqc_events_ringbuf = None
        self.pqc_verified_sessions_map = None

        if self.bpf:
            self._init_bpf_maps()

    def _init_bpf_maps(self):
        """Initialize BPF maps from loaded program"""
        try:
            self.pqc_events_ringbuf = self.bpf.get_table("pqc_events")
            self.pqc_verified_sessions_map = self.bpf.get_table("pqc_verified_sessions")
            logger.info("BPF maps initialized: pqc_events, pqc_verified_sessions")
        except KeyError as e:
            logger.warning(f"BPF map not found: {e}")

    def register_public_key(self, pubkey_id: bytes, public_key: bytes):
        """
        Register a peer's ML-DSA-65 public key.

        Args:
            pubkey_id: 16-byte identifier (e.g., hash of peer ID)
            public_key: ML-DSA-65 public key bytes
        """
        if len(pubkey_id) != 16:
            raise ValueError("pubkey_id must be 16 bytes")

        self.public_keys[pubkey_id] = public_key
        logger.info(f"Registered public key: {pubkey_id.hex()[:8]}...")

    def verify_signature(
        self, message: bytes, signature: bytes, public_key: bytes
    ) -> bool:
        """
        Verify ML-DSA-65 signature.

        Args:
            message: Message that was signed
            signature: ML-DSA-65 signature
            public_key: ML-DSA-65 public key

        Returns:
            True if signature is valid
        """
        if not LIBOQS_AVAILABLE or self.sig is None:
            # Mock verification - always succeed for testing
            logger.debug("Mock verification: accepting signature")
            return True

        try:
            is_valid = self.sig.verify(message, signature, public_key)
            return is_valid
        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return False

    def _process_event(self, cpu: int, data: bytes, size: int):
        """
        Process a single PQC verification event from ring buffer.

        Called by BCC's ring buffer callback mechanism.
        """
        self.stats["events_received"] += 1

        try:
            # Parse event
            event = self._parse_event(data)
            if event is None:
                return

            # Submit to thread pool for async verification
            self.executor.submit(self._verify_event, event)

        except Exception as e:
            logger.error(f"Error processing event: {e}")

    def _parse_event(self, data: bytes) -> Optional[PQCVerificationEvent]:
        """Parse raw event bytes into PQCVerificationEvent"""
        if len(data) < 16 + 2:  # Minimum: session_id + signature_len
            logger.warning(f"Event too short: {len(data)} bytes")
            return None

        try:
            # Unpack header
            session_id = data[0:16]

            # Signature length at offset 16 + 4627
            sig_len_offset = 16 + 4627
            signature_len = struct.unpack(
                "<H", data[sig_len_offset : sig_len_offset + 2]
            )[0]

            # Signature (variable length, max 4627)
            signature = data[16 : 16 + signature_len]

            # Payload hash (32 bytes after signature_len)
            hash_offset = sig_len_offset + 2
            payload_hash = data[hash_offset : hash_offset + 32]

            # Pubkey ID (16 bytes after payload_hash)
            pubkey_offset = hash_offset + 32
            pubkey_id = data[pubkey_offset : pubkey_offset + 16]

            # Timestamp (8 bytes at end)
            ts_offset = pubkey_offset + 16
            timestamp = struct.unpack("<Q", data[ts_offset : ts_offset + 8])[0]

            return PQCVerificationEvent(
                session_id=session_id,
                signature=signature,
                payload_hash=payload_hash,
                pubkey_id=pubkey_id,
                timestamp=timestamp,
            )

        except Exception as e:
            logger.error(f"Event parsing error: {e}")
            return None

    def _verify_event(self, event: PQCVerificationEvent):
        """
        Verify a PQC event and update BPF map on success.

        This runs in a thread pool worker.
        """
        session_id_hex = event.session_id.hex()
        pubkey_id_hex = event.pubkey_id.hex()

        logger.debug(
            f"Verifying session {session_id_hex[:8]}... pubkey {pubkey_id_hex[:8]}..."
        )

        # Look up public key
        public_key = self.public_keys.get(event.pubkey_id)
        if public_key is None:
            self.stats["unknown_pubkey"] += 1
            logger.warning(f"Unknown public key ID: {pubkey_id_hex}")

            # Report anomaly
            if self.anomaly_callback:
                self.anomaly_callback(
                    "unknown_pubkey",
                    {"session_id": session_id_hex, "pubkey_id": pubkey_id_hex},
                )
            return

        # Verify signature
        # The message that was signed is the payload hash
        is_valid = self.verify_signature(
            message=event.payload_hash, signature=event.signature, public_key=public_key
        )

        if is_valid:
            self.stats["verifications_success"] += 1
            logger.info(f"Signature verified for session {session_id_hex[:8]}...")

            # Update verified sessions cache
            expiration = time.time_ns() + self.SESSION_TTL_NS

            if event.session_id in self.verified_sessions:
                self.verified_sessions[event.session_id].verification_count += 1
                self.verified_sessions[event.session_id].last_verified = time.time()
            else:
                self.verified_sessions[event.session_id] = VerifiedSession(
                    session_id=event.session_id,
                    expiration=expiration,
                    verification_count=1,
                    last_verified=time.time(),
                )

            # Update BPF map
            self._update_bpf_verified_session(event.session_id, expiration)

        else:
            self.stats["verifications_failed"] += 1
            logger.warning(
                f"Signature verification FAILED for session {session_id_hex[:8]}..."
            )

            # Report anomaly
            if self.anomaly_callback:
                self.anomaly_callback(
                    "verification_failed",
                    {"session_id": session_id_hex, "pubkey_id": pubkey_id_hex},
                )

    def _update_bpf_verified_session(self, session_id: bytes, expiration: int):
        """Update BPF map with verified session"""
        if self.pqc_verified_sessions_map is None:
            logger.debug("BPF map not available, skipping update")
            return

        try:
            # Pack expiration as __u64
            exp_bytes = struct.pack("<Q", expiration)
            self.pqc_verified_sessions_map[session_id] = exp_bytes
            logger.debug(f"Updated BPF map for session {session_id.hex()[:8]}...")
        except Exception as e:
            logger.error(f"Failed to update BPF map: {e}")

    def cleanup_expired_sessions(self):
        """Remove expired sessions from cache and BPF map"""
        now = time.time_ns()
        expired = []

        for session_id, session in self.verified_sessions.items():
            if session.expiration < now:
                expired.append(session_id)

        for session_id in expired:
            del self.verified_sessions[session_id]

            # Remove from BPF map
            if self.pqc_verified_sessions_map:
                try:
                    del self.pqc_verified_sessions_map[session_id]
                except KeyError:
                    pass

        if expired:
            self.stats["expired_sessions"] += len(expired)
            logger.info(f"Cleaned up {len(expired)} expired sessions")

    def get_stats(self) -> Dict[str, int]:
        """Get daemon statistics"""
        return {
            **self.stats,
            "active_sessions": len(self.verified_sessions),
            "registered_pubkeys": len(self.public_keys),
        }

    def start(self):
        """Start the daemon's main loop"""
        if not BCC_AVAILABLE:
            logger.error("Cannot start daemon without BCC")
            return

        if self.pqc_events_ringbuf is None:
            logger.error("Ring buffer not initialized")
            return

        self.running = True
        logger.info("PQC Verification Daemon starting...")

        # Register ring buffer callback
        self.pqc_events_ringbuf.open_ring_buffer(self._process_event)

        # Cleanup thread
        cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        cleanup_thread.start()

        # Main event loop
        try:
            while self.running:
                self.pqc_events_ringbuf.ring_buffer_poll(timeout=1000)
        except KeyboardInterrupt:
            logger.info("Received interrupt, shutting down...")
        finally:
            self.stop()

    def _cleanup_loop(self):
        """Periodically clean up expired sessions"""
        while self.running:
            time.sleep(60)  # Every minute
            self.cleanup_expired_sessions()

    def stop(self):
        """Stop the daemon"""
        self.running = False
        self.executor.shutdown(wait=True)
        logger.info("PQC Verification Daemon stopped")
        logger.info(f"Final stats: {self.get_stats()}")


class MockPQCVerificationDaemon(PQCVerificationDaemon):
    """
    Mock daemon for testing without BCC/kernel support.

    Simulates the verification workflow for unit testing and development.
    """

    def __init__(self, **kwargs):
        # Remove bpf from kwargs if present
        kwargs.pop("bpf", None)
        super().__init__(bpf=None, **kwargs)

        self.pending_events = []
        self._mock_mode = True  # Force mock mode

    def verify_signature(
        self, message: bytes, signature: bytes, public_key: bytes
    ) -> bool:
        """Mock verification - always returns True"""
        logger.debug("Mock verification: accepting signature")
        return True

    def submit_event(self, event: PQCVerificationEvent):
        """Submit event for verification (test helper)"""
        self.pending_events.append(event)
        self._verify_event(event)

    def start(self):
        """Start in mock mode"""
        logger.info("Mock PQC Verification Daemon started")
        self.running = True

    def stop(self):
        """Stop mock daemon"""
        self.running = False
        logger.info(f"Mock daemon stopped. Stats: {self.get_stats()}")


def create_daemon_from_bpf(
    bpf: "BPF", pqc_gateway=None
) -> PQCVerificationDaemon:  # Changed 'BPF' to string literal
    """
    Factory function to create daemon from existing BPF object.

    Args:
        bpf: BPF object with loaded PQC XDP program
        pqc_gateway: Optional EBPFPQCGateway for public key registration

    Returns:
        Configured PQCVerificationDaemon
    """
    daemon = PQCVerificationDaemon(bpf=bpf)

    # Register public keys from gateway if available
    if pqc_gateway:
        for session_id, session in pqc_gateway.sessions.items():
            if session.dsa_public_key:
                # Use hash of peer_id as pubkey_id
                pubkey_id = hashlib.sha256(session.peer_id.encode()).digest()[:16]
                daemon.register_public_key(pubkey_id, session.dsa_public_key)

    return daemon


def main():
    """Main entry point for running daemon standalone"""
    import argparse

    parser = argparse.ArgumentParser(description="x0tta6bl4 PQC Verification Daemon")
    parser.add_argument("--interface", "-i", default="eth0", help="Network interface")
    parser.add_argument("--mock", action="store_true", help="Run in mock mode")
    parser.add_argument(
        "--stats-interval", type=int, default=30, help="Stats print interval"
    )

    args = parser.parse_args()

    if args.mock or not BCC_AVAILABLE:
        logger.info("Running in mock mode")
        daemon = MockPQCVerificationDaemon()

        # Add some test public keys
        test_pubkey_id = hashlib.sha256(b"test-peer").digest()[:16]
        daemon.register_public_key(test_pubkey_id, b"mock-public-key")

        daemon.start()

        # Simulate events for testing
        import secrets

        for i in range(5):
            event = PQCVerificationEvent(
                session_id=secrets.token_bytes(16),
                signature=secrets.token_bytes(100),  # Mock signature
                payload_hash=hashlib.sha256(f"test-payload-{i}".encode()).digest(),
                pubkey_id=test_pubkey_id,
                timestamp=time.time_ns(),
            )
            daemon.submit_event(event)
            time.sleep(0.5)

        print(f"Final stats: {daemon.get_stats()}")
        daemon.stop()

    else:
        # Real mode with BCC
        from .pqc_xdp_loader import PQCXDPLoader

        loader = PQCXDPLoader(interface=args.interface)
        daemon = create_daemon_from_bpf(loader.bpf, loader.pqc_gateway)

        # Setup signal handlers
        def signal_handler(sig, frame):
            daemon.stop()
            loader.cleanup()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Stats printer
        def stats_printer():
            while daemon.running:
                time.sleep(args.stats_interval)
                stats = daemon.get_stats()
                logger.info(f"Stats: {stats}")

        stats_thread = threading.Thread(target=stats_printer, daemon=True)
        stats_thread.start()

        # Run daemon
        daemon.start()


if __name__ == "__main__":
    main()
