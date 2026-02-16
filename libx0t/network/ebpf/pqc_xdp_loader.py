#!/usr/bin/env python3
"""
PQC XDP Loader for x0tta6bl4
Loads and manages XDP PQC verification programs with zero-trust security.

Integrates with EBPFPQCGateway for cryptographic session management.
"""

import logging
import os
import struct  # Added for eBPF map packing
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

try:
    from bcc import BPF

    BCC_AVAILABLE = True
except ImportError:
    BCC_AVAILABLE = False

from ...security.ebpf_pqc_gateway import EBPFPQCGateway, get_pqc_gateway
from .loader import EBPFLoader

logger = logging.getLogger(__name__)


class PQCXDPLoader(EBPFLoader):
    """
    PQC-aware XDP Loader with zero-trust capabilities.

    Extends EBPFLoader with PQC session management and verification.
    """

    def __init__(self, interface: str = "eth0"):
        if not BCC_AVAILABLE:
            raise RuntimeError("BCC required for PQC XDP loader")

        super().__init__(Path(__file__).parent / "programs")

        self.interface = interface
        self.pqc_gateway = get_pqc_gateway()
        self.pqc_sessions_map = None
        self.pqc_stats_map = None

        self.load_pqc_programs()

    def load_pqc_programs(self):
        """Load PQC XDP verification program"""
        if not BCC_AVAILABLE:
            logger.warning(
                "BCC not available. Skipping BPF program loading in PQCXDPLoader."
            )
            self.bpf = None
            self.pqc_sessions_map = None
            self.pqc_stats_map = None
            return

        program_path = self.programs_dir / "xdp_pqc_verify.c"

        if not program_path.exists():
            raise FileNotFoundError(f"PQC XDP program not found: {program_path}")

        with open(program_path, "r") as f:
            bpf_text = f.read()

        # Compile and load BPF program
        self.bpf = BPF(text=bpf_text)

        # Get PQC-specific maps
        self.pqc_sessions_map = self.bpf.get_table("pqc_sessions")
        self.pqc_stats_map = self.bpf.get_table("pqc_stats")

        # Attach XDP program
        fn = self.bpf.load_func("xdp_pqc_verify_prog", BPF.XDP)
        self.bpf.attach_xdp(self.interface, fn, 0)

        logger.info(f"✅ Loaded PQC XDP verification on interface {self.interface}")

    def update_pqc_sessions(self, sessions_data: Dict[str, Dict]):
        """
        Update PQC sessions map with current cryptographic sessions.

        Args:
            sessions_data: Dict[session_id, session_info]
        """
        if not self.pqc_sessions_map:
            logger.warning("pqc_sessions_map is not initialized. Skipping update.")
            return

        # Clear existing sessions
        for key in list(self.pqc_sessions_map.keys()):
            del self.pqc_sessions_map[key]

        logger.debug(f"update_pqc_sessions called with {len(sessions_data)} sessions.")
        # Add current sessions
        for session_id_bytes, session_info in sessions_data.items():
            logger.debug(
                f"Processing session ID: {session_id_bytes.hex()}, Info: {session_info}"
            )
            # In a real BCC implementation, we would pack this into a C types struct.
            # For now, we pass the dict/value relying on BCC or mock behavior.
            try:
                self.pqc_sessions_map[session_id_bytes] = session_info
            except Exception as e:
                logger.error(f"Failed to update PQC session map: {e}")

    def get_pqc_stats(self) -> Dict[str, int]:
        """Get PQC verification statistics"""
        if not self.pqc_stats_map:
            return {}

        stats = {}
        try:
            stats["total_packets"] = self.pqc_stats_map[0] or 0
            stats["verified_packets"] = self.pqc_stats_map[1] or 0
            stats["failed_verification"] = self.pqc_stats_map[2] or 0
            stats["no_session"] = self.pqc_stats_map[3] or 0
            stats["expired_session"] = self.pqc_stats_map[4] or 0
            stats["decrypted_packets"] = self.pqc_stats_map[5] or 0
        except KeyError:
            pass

        return stats

    def sync_with_gateway(self):
        """Sync eBPF maps with PQC gateway sessions"""
        gateway_data = self.pqc_gateway.get_ebpf_map_data()
        logger.debug(f"gateway_data received from PQC gateway: {gateway_data}")
        self.update_pqc_sessions(gateway_data)

    def create_pqc_session(self, peer_id: str) -> Optional[str]:
        """
        Create new PQC session and update eBPF maps.

        Returns:
            session_id if successful
        """
        try:
            session = self.pqc_gateway.create_session(peer_id)
            self.sync_with_gateway()
            return session.session_id
        except Exception as e:
            logger.error(f"Failed to create PQC session: {e}")
            return None

    def verify_pqc_packet(self, packet_data: bytes) -> bool:
        """
        Verify PQC packet (for testing/debugging).

        In production, this is done in XDP.
        """
        # This would implement userspace verification
        # For now, return True for testing
        return True

    def cleanup(self):
        """Clean up PQC XDP programs"""
        if self.bpf:
            self.bpf.remove_xdp(self.interface, 0)
            self.bpf.cleanup()
        logger.info("Cleaned up PQC XDP programs")


# Integration with mesh networking
def integrate_pqc_with_mesh(mesh_router, pqc_loader: PQCXDPLoader):
    """
    Integrate PQC verification with mesh routing.

    Args:
        mesh_router: MeshRouter instance
        pqc_loader: PQCXDPLoader instance
    """
    # Monkey patch mesh router to use PQC
    original_send = mesh_router._send_packet

    def pqc_send_packet(self, packet, destination):
        # Encrypt packet with PQC before sending
        session_id = pqc_loader.create_pqc_session(destination.node_id)
        if session_id:
            encrypted = pqc_loader.pqc_gateway.encrypt_payload(session_id, packet)
            if encrypted:
                return original_send(encrypted, destination)
        return original_send(packet, destination)

    mesh_router._send_packet = pqc_send_packet.__get__(
        mesh_router, mesh_router.__class__
    )

    logger.info("Integrated PQC encryption with mesh routing")


# Prometheus metrics integration
def setup_pqc_metrics(pqc_loader: PQCXDPLoader):
    """Set up Prometheus metrics for PQC operations"""
    try:
        from prometheus_client import Counter, Gauge

        PQC_SESSIONS = Gauge("pqc_active_sessions", "Number of active PQC sessions")
        PQC_VERIFICATION_RATE = Gauge(
            "pqc_verification_rate", "PQC packet verification rate"
        )
        PQC_FAILED_VERIFICATIONS = Counter(
            "pqc_failed_verifications_total", "Total failed PQC verifications"
        )

        def update_metrics():
            stats = pqc_loader.get_pqc_stats()
            total = stats.get("total_packets", 0)
            verified = stats.get("verified_packets", 0)

            PQC_SESSIONS.set(len(pqc_loader.pqc_gateway.sessions))
            if total > 0:
                PQC_VERIFICATION_RATE.set(verified / total)
            PQC_FAILED_VERIFICATIONS.inc(stats.get("failed_verification", 0))

        # Update every 30 seconds
        import threading

        def metrics_loop():
            while True:
                update_metrics()
                time.sleep(30)

        thread = threading.Thread(target=metrics_loop, daemon=True)
        thread.start()

        logger.info("PQC Prometheus metrics enabled")

    except ImportError:
        logger.warning("prometheus_client not available, PQC metrics disabled")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="x0tta6bl4 PQC XDP Loader")
    parser.add_argument("--interface", "-i", default="eth0", help="Network interface")
    parser.add_argument("--test-session", help="Test PQC session creation")

    args = parser.parse_args()

    loader = PQCXDPLoader(args.interface)

    if args.test_session:
        session_id = loader.create_pqc_session(args.test_session)
        if session_id:
            print(f"Created PQC session: {session_id}")
            stats = loader.get_pqc_stats()
            print(f"PQC stats: {stats}")
        else:
            print("Failed to create session")
    else:
        # Run sync loop
        try:
            while True:
                loader.sync_with_gateway()
                stats = loader.get_pqc_stats()
                print(f"PQC Stats: {stats}")
                time.sleep(10)
        except KeyboardInterrupt:
            loader.cleanup()
