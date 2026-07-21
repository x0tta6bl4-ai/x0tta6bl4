"""
eBPF Ring Buffer -> x0tMQ PQC Transport -> MAPE-K Loop Bridge.
================================================================

Connects eBPF/XDP kernel telemetry directly to x0tMQ post-quantum messaging
and the MAPE-K self-healing loop.

Compliance: Chief Engineer Mandate & 3-Tier Status Taxonomy.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from src.network.ebpf.core_xdp_integration import COREXDPProgramLoader
from src.self_healing.mape_k.manager import SelfHealingManager
from src.self_healing.x0tmq_mapek_bridge import X0tMQMAPEKBridge, X0tMQMAPEKFrame

logger = logging.getLogger(__name__)


class EBPFToX0tMQBridge:
    """Streams eBPF/XDP kernel events over x0tMQ PQC frames into MAPE-K."""

    def __init__(
        self,
        interface: str = "eth0",
        node_id: str = "default",
        spiffe_id: str = "spiffe://x0tta6bl4.mesh/node/default",
    ):
        self.interface = interface
        self.node_id = node_id
        self.spiffe_id = spiffe_id
        from pathlib import Path
        cache_dir = Path("/mnt/projects/.tmp/ebpf_cache")
        self.loader = COREXDPProgramLoader(cache_dir=cache_dir)
        self.x0tmq_bridge = X0tMQMAPEKBridge(spiffe_id=spiffe_id)
        self.mapek_manager = SelfHealingManager(node_id=node_id)

    def process_ebpf_telemetry_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert eBPF kernel event into PQC-signed x0tMQ frame and feed into MAPE-K."""
        logger.info("⚡ [eBPF->x0tMQ] Processing kernel telemetry event on %s...", self.interface)

        # 1. Pack into x0tMQ PQC frame
        frame: X0tMQMAPEKFrame = self.x0tmq_bridge.pack_mapek_frame(
            recipient_spiffe_id="spiffe://x0tta6bl4.mesh/node/mapek-controller",
            payload_type="TELEMETRY",
            payload_data=event_data,
        )

        # 2. Unpack and verify Zero-Trust SPIRE + PQC signatures
        valid, verified_data = self.x0tmq_bridge.unpack_and_verify_frame(frame)
        if not valid:
            logger.error("❌ [eBPF->x0tMQ] Security verification failed for frame!")
            return {"status": "SECURITY_FAILURE", "processed": False}

        # 3. Feed telemetry into MAPE-K cycle
        mapek_result = self.mapek_manager.run_cycle(metrics=verified_data)

        return {
            "interface": self.interface,
            "spiffe_verified": valid,
            "x0tmq_magic": hex(frame.magic),
            "mapek_cycle_status": mapek_result,
            "processed": True,
        }
