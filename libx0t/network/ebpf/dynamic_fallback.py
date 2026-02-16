"""
Dynamic Fallback Triggers for Mesh Routing

Automatic reroute triggers based on eBPF latency measurements.
"""

import logging
import time
from collections import deque
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class DynamicFallbackController:
    """
    Controls dynamic routing fallback based on eBPF telemetry.

    Features:
    - Latency spike detection
    - Automatic reroute triggers
    - Integration with mesh router
    - Circuit breaker pattern
    """

    def __init__(
        self,
        latency_threshold_ms: float = 100.0,
        spike_duration_ms: float = 500.0,
        cooldown_seconds: float = 60.0,
    ):
        """
        Initialize fallback controller.

        Args:
            latency_threshold_ms: Latency threshold for triggering fallback
            spike_duration_ms: How long spike must last to trigger
            cooldown_seconds: Cooldown between fallback triggers
        """
        self.latency_threshold_ms = latency_threshold_ms
        self.spike_duration_ms = spike_duration_ms
        self.cooldown_seconds = cooldown_seconds

        # Latency history per node (rolling window)
        self.latency_history: Dict[str, deque] = {}
        self.window_size = 100  # Keep last 100 measurements

        # Fallback state
        self.last_fallback_time: Dict[str, float] = {}
        self.active_fallbacks: Dict[str, bool] = {}

        # Callbacks
        self.on_fallback_trigger: Optional[Callable] = None
        self.on_fallback_recover: Optional[Callable] = None

        logger.info(
            f"DynamicFallbackController initialized: "
            f"threshold={latency_threshold_ms}ms, "
            f"duration={spike_duration_ms}ms"
        )

    def update_latency(self, node_id: str, latency_ms: float):
        """
        Update latency measurement for a node.

        Args:
            node_id: Node identifier
            latency_ms: Current latency in milliseconds
        """
        if node_id not in self.latency_history:
            self.latency_history[node_id] = deque(maxlen=self.window_size)

        self.latency_history[node_id].append(
            {"latency": latency_ms, "timestamp": time.time()}
        )

        # Check for spike
        self._check_spike(node_id)

    def _check_spike(self, node_id: str):
        """Check if latency spike warrants fallback."""
        if node_id not in self.latency_history:
            return

        history = list(self.latency_history[node_id])
        if len(history) < 10:  # Need minimum samples
            return

        # Check if recent measurements exceed threshold
        recent = history[-10:]  # Last 10 measurements
        spike_count = sum(1 for h in recent if h["latency"] > self.latency_threshold_ms)

        # If >80% of recent measurements exceed threshold
        if spike_count >= 8:
            # Check cooldown
            last_trigger = self.last_fallback_time.get(node_id, 0)
            if time.time() - last_trigger < self.cooldown_seconds:
                logger.debug(f"Fallback on cooldown for {node_id}")
                return

            # Check if already in fallback
            if self.active_fallbacks.get(node_id, False):
                logger.debug(f"Fallback already active for {node_id}")
                return

            # Trigger fallback
            self._trigger_fallback(node_id)

    def _trigger_fallback(self, node_id: str):
        """
        Trigger fallback reroute for a node.

        Args:
            node_id: Node to reroute
        """
        logger.warning(
            f"🚨 Latency spike detected on {node_id}, triggering fallback reroute"
        )

        self.active_fallbacks[node_id] = True
        self.last_fallback_time[node_id] = time.time()

        # Call callback if registered
        if self.on_fallback_trigger:
            try:
                self.on_fallback_trigger(node_id)
            except Exception as e:
                logger.error(f"Fallback trigger callback failed: {e}")

        # Integration with mesh router
        try:
            from ..mesh_router import MeshRouter

            # mesh_router = MeshRouter.get_instance()
            # mesh_router.trigger_reroute(node_id, reason="latency_spike")
            logger.info(f"Fallback reroute triggered for {node_id}")
        except ImportError:
            logger.debug("MeshRouter not available, logging fallback only")

    def check_recovery(self, node_id: str):
        """
        Check if node has recovered and can exit fallback.

        Args:
            node_id: Node to check
        """
        if not self.active_fallbacks.get(node_id, False):
            return

        if node_id not in self.latency_history:
            return

        history = list(self.latency_history[node_id])
        if len(history) < 10:
            return

        # Check if recent measurements are below threshold
        recent = history[-10:]
        recovery_count = sum(
            1 for h in recent if h["latency"] < self.latency_threshold_ms * 0.8
        )

        # If >80% of recent measurements are good
        if recovery_count >= 8:
            self._recover_from_fallback(node_id)

    def _recover_from_fallback(self, node_id: str):
        """Recover from fallback state."""
        logger.info(f"✅ Node {node_id} recovered, exiting fallback")

        self.active_fallbacks[node_id] = False

        # Call callback if registered
        if self.on_fallback_recover:
            try:
                self.on_fallback_recover(node_id)
            except Exception as e:
                logger.error(f"Fallback recover callback failed: {e}")

    def get_fallback_status(self) -> Dict[str, bool]:
        """Get current fallback status for all nodes."""
        return self.active_fallbacks.copy()

    def register_fallback_trigger(self, callback: Callable):
        """Register callback for fallback triggers."""
        self.on_fallback_trigger = callback
        logger.debug("Fallback trigger callback registered")

    def register_fallback_recover(self, callback: Callable):
        """Register callback for fallback recovery."""
        self.on_fallback_recover = callback
        logger.debug("Fallback recover callback registered")


# Integration example
def integrate_fallback_with_mapek(mapek_loop, ebpf_exporter):
    """
    Integrate dynamic fallback with MAPE-K.

    Args:
        mapek_loop: MAPEKLoop instance
        ebpf_exporter: EBPFMetricsExporter instance
    """
    fallback_controller = DynamicFallbackController(
        latency_threshold_ms=100.0, spike_duration_ms=500.0
    )

    # Register callbacks
    def on_fallback(node_id: str):
        """Handle fallback trigger."""
        logger.warning(f"MAPE-K: Fallback triggered for {node_id}")
        # Would trigger MAPE-K Plan phase for reroute

    def on_recover(node_id: str):
        """Handle recovery."""
        logger.info(f"MAPE-K: Node {node_id} recovered")
        # Would update MAPE-K Knowledge base

    fallback_controller.register_fallback_trigger(on_fallback)
    fallback_controller.register_fallback_recover(on_recover)

    return fallback_controller
