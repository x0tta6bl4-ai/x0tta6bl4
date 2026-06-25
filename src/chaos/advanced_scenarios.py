"""
Advanced Chaos Engineering Scenarios

Extended chaos testing scenarios beyond basic node failures and partitions.
"""

import asyncio
import hashlib
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from src.core.thinking.agent_thinking import AgentThinkingCoach

logger = logging.getLogger(__name__)


def _safe_hash(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def _safe_count_bucket(value: int) -> str:
    if value <= 0:
        return "0"
    if value <= 3:
        return "1-3"
    if value <= 10:
        return "4-10"
    if value <= 100:
        return "11-100"
    return "100+"


def _safe_number_band(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "non_numeric"
    if value < 0:
        return "negative"
    if value == 0:
        return "0"
    if value <= 1:
        return "0-1"
    if value <= 10:
        return "1-10"
    if value <= 100:
        return "10-100"
    return "100+"


class AdvancedScenarioType(Enum):
    """Advanced chaos scenario types"""

    CASCADE_FAILURE = "cascade_failure"  # Cascading failures
    BYZANTINE_BEHAVIOR = "byzantine_behavior"  # Byzantine node behavior
    NETWORK_STORM = "network_storm"  # Network traffic storm
    RESOURCE_EXHAUSTION = "resource_exhaustion"  # CPU/Memory exhaustion
    CLOCK_SKEW = "clock_skew"  # Clock synchronization issues
    PARTIAL_PARTITION = "partial_partition"  # Partial network partition
    BANDWIDTH_THROTTLING = "bandwidth_throttling"  # Bandwidth limitations
    PACKET_REORDERING = "packet_reordering"  # Packet reordering simulation


@dataclass
class AdvancedChaosExperiment:
    """Advanced chaos experiment configuration"""

    scenario_type: AdvancedScenarioType
    duration: int  # seconds
    target_nodes: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    start_time: Optional[datetime] = None
    status: str = "pending"


class AdvancedChaosController:
    """
    Advanced Chaos Engineering Controller.

    Provides extended chaos scenarios for comprehensive testing:
    - Cascading failures
    - Byzantine behavior
    - Network storms
    - Resource exhaustion
    - Clock skew
    - Partial partitions
    """

    def __init__(self):
        self.active_experiments: Dict[str, AdvancedChaosExperiment] = {}
        self.thinking_coach = AgentThinkingCoach(
            agent_id="advanced-chaos-controller",
            role="healing",
            capabilities=("ops", "quality", "monitoring"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "advanced_chaos_controller_init",
                "goal": "Initialize advanced chaos scenarios safely",
                "signals": {"active_experiment_count_bucket": "0"},
                "safety_boundary": (
                    "Keep target node ids, scenario parameter values, behavior labels, "
                    "and exception messages out of thinking context."
                ),
            }
        )
        logger.info("Advanced Chaos Controller initialized")

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "redact_target_nodes": True,
                    "redact_parameter_values": True,
                    "redact_behavior_labels": True,
                    "redact_error_messages": True,
                    "preserve_scenario_decision": True,
                },
                "safety_boundary": "Use hashes, counts, scenario names, and value bands.",
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    async def run_cascade_failure(
        self,
        initial_node: str,
        propagation_probability: float = 0.3,
        max_depth: int = 5,
        duration: int = 60,
    ) -> Dict[str, Any]:
        """
        Simulate cascading failure starting from an initial node.

        Args:
            initial_node: Node to fail initially
            propagation_probability: Probability of failure propagation
            max_depth: Maximum cascade depth
            duration: Duration of experiment

        Returns:
            Experiment results
        """
        logger.info(
            f"Running cascade failure scenario: "
            f"initial={initial_node}, prob={propagation_probability}, depth={max_depth}"
        )

        failed_nodes = [initial_node]
        depth = 0

        try:
            from src.chaos.mesh_integration import MeshChaosIntegration

            mesh_chaos = MeshChaosIntegration()

            # Fail initial node
            await mesh_chaos.simulate_node_failure(initial_node, duration=5)

            # Propagate failures
            while depth < max_depth and failed_nodes:
                new_failures = []

                for node in failed_nodes:
                    # Get neighbors (simplified - would query mesh network)
                    neighbors = []  # Would be populated from mesh network

                    for neighbor in neighbors:
                        if random.random() < propagation_probability:
                            if (
                                neighbor not in failed_nodes
                                and neighbor not in new_failures
                            ):
                                new_failures.append(neighbor)
                                await mesh_chaos.simulate_node_failure(
                                    neighbor, duration=5
                                )

                if not new_failures:
                    break

                failed_nodes.extend(new_failures)
                depth += 1

                await asyncio.sleep(2)  # Wait between cascade waves

            result = {
                "scenario": "cascade_failure",
                "initial_node": initial_node,
                "total_failed": len(failed_nodes),
                "cascade_depth": depth,
                "failed_nodes": failed_nodes,
                "duration": duration,
            }
            self._record_thinking(
                "advanced_chaos_cascade_failure",
                "Complete cascade failure scenario safely",
                {
                    "initial_node_hash": _safe_hash(initial_node),
                    "propagation_probability_band": _safe_number_band(
                        propagation_probability
                    ),
                    "max_depth_bucket": _safe_count_bucket(max_depth),
                    "failed_node_count_bucket": _safe_count_bucket(len(failed_nodes)),
                    "cascade_depth_bucket": _safe_count_bucket(depth),
                    "duration_bucket": _safe_count_bucket(duration),
                },
            )
            return result
        except Exception as e:
            self._record_thinking(
                "advanced_chaos_cascade_failure",
                "Record cascade failure scenario error",
                {"initial_node_hash": _safe_hash(initial_node), "error_type": type(e).__name__},
            )
            logger.error(f"Cascade failure simulation error: {e}")
            return {"error": str(e)}

    async def run_byzantine_behavior(
        self,
        target_nodes: List[str],
        behavior_type: str = "malicious_routing",
        duration: int = 60,
    ) -> Dict[str, Any]:
        """
        Simulate Byzantine (malicious) node behavior.

        Behavior types:
        - malicious_routing: Incorrect routing information
        - packet_dropping: Selectively drop packets
        - message_delay: Delay messages
        - false_consensus: Provide false consensus votes

        Args:
            target_nodes: Nodes to exhibit Byzantine behavior
            behavior_type: Type of Byzantine behavior
            duration: Duration of experiment

        Returns:
            Experiment results
        """
        logger.info(f"Running Byzantine behavior: {behavior_type} on {target_nodes}")

        try:
            # In production, would integrate with mesh network to inject Byzantine behavior
            # For now, simulate the behavior

            for node in target_nodes:
                logger.warning(
                    f"Node {node} exhibiting Byzantine behavior: {behavior_type}"
                )
                # Future: Actual Byzantine behavior injection

            await asyncio.sleep(duration)

            result = {
                "scenario": "byzantine_behavior",
                "target_nodes": target_nodes,
                "behavior_type": behavior_type,
                "duration": duration,
            }
            self._record_thinking(
                "advanced_chaos_byzantine_behavior",
                "Complete Byzantine behavior scenario safely",
                {
                    "target_count_bucket": _safe_count_bucket(len(target_nodes)),
                    "target_hashes": [_safe_hash(node) for node in target_nodes[:5]],
                    "behavior_hash": _safe_hash(behavior_type),
                    "duration_bucket": _safe_count_bucket(duration),
                },
            )
            return result
        except Exception as e:
            self._record_thinking(
                "advanced_chaos_byzantine_behavior",
                "Record Byzantine behavior scenario error",
                {"error_type": type(e).__name__},
            )
            logger.error(f"Byzantine behavior simulation error: {e}")
            return {"error": str(e)}

    async def run_network_storm(
        self,
        target_nodes: List[str],
        packet_rate: int = 10000,  # packets per second
        duration: int = 30,
    ) -> Dict[str, Any]:
        """
        Simulate network traffic storm.

        Args:
            target_nodes: Nodes to flood with traffic
            packet_rate: Packets per second
            duration: Duration of storm

        Returns:
            Experiment results
        """
        logger.info(f"Running network storm: {packet_rate} pps for {duration}s")

        try:
            # In production, would use packet generator (e.g., pktgen, scapy)
            # For now, simulate high load

            for node in target_nodes:
                logger.warning(f"Node {node} under network storm: {packet_rate} pps")
                # Future: Actual packet generation

            await asyncio.sleep(duration)

            result = {
                "scenario": "network_storm",
                "target_nodes": target_nodes,
                "packet_rate": packet_rate,
                "duration": duration,
                "total_packets": packet_rate * duration,
            }
            self._record_thinking(
                "advanced_chaos_network_storm",
                "Complete network storm scenario safely",
                {
                    "target_count_bucket": _safe_count_bucket(len(target_nodes)),
                    "packet_rate_band": _safe_number_band(packet_rate),
                    "duration_bucket": _safe_count_bucket(duration),
                    "total_packets_band": _safe_number_band(packet_rate * duration),
                },
            )
            return result
        except Exception as e:
            self._record_thinking(
                "advanced_chaos_network_storm",
                "Record network storm scenario error",
                {"error_type": type(e).__name__},
            )
            logger.error(f"Network storm simulation error: {e}")
            return {"error": str(e)}

    async def run_resource_exhaustion(
        self,
        target_nodes: List[str],
        resource_type: str = "cpu",  # cpu, memory, disk, network
        utilization: float = 0.95,  # Target utilization
        duration: int = 60,
    ) -> Dict[str, Any]:
        """
        Simulate resource exhaustion.

        Args:
            target_nodes: Nodes to exhaust resources
            resource_type: Type of resource (cpu, memory, disk, network)
            utilization: Target utilization (0.0-1.0)
            duration: Duration of exhaustion

        Returns:
            Experiment results
        """
        logger.info(
            f"Running resource exhaustion: "
            f"{resource_type} at {utilization*100:.0f}% for {duration}s"
        )

        try:
            # In production, would use stress-ng or similar
            # For now, simulate resource exhaustion

            for node in target_nodes:
                logger.warning(
                    f"Node {node} resource exhaustion: "
                    f"{resource_type} at {utilization*100:.0f}%"
                )
                # Future: Actual resource exhaustion

            await asyncio.sleep(duration)

            result = {
                "scenario": "resource_exhaustion",
                "target_nodes": target_nodes,
                "resource_type": resource_type,
                "utilization": utilization,
                "duration": duration,
            }
            self._record_thinking(
                "advanced_chaos_resource_exhaustion",
                "Complete resource exhaustion scenario safely",
                {
                    "target_count_bucket": _safe_count_bucket(len(target_nodes)),
                    "resource_hash": _safe_hash(resource_type),
                    "utilization_band": _safe_number_band(utilization),
                    "duration_bucket": _safe_count_bucket(duration),
                },
            )
            return result
        except Exception as e:
            self._record_thinking(
                "advanced_chaos_resource_exhaustion",
                "Record resource exhaustion scenario error",
                {"error_type": type(e).__name__},
            )
            logger.error(f"Resource exhaustion simulation error: {e}")
            return {"error": str(e)}

    async def run_clock_skew(
        self,
        target_nodes: List[str],
        skew_seconds: float = 5.0,  # Clock skew in seconds
        duration: int = 60,
    ) -> Dict[str, Any]:
        """
        Simulate clock synchronization issues.

        Args:
            target_nodes: Nodes with clock skew
            skew_seconds: Amount of clock skew
            duration: Duration of experiment

        Returns:
            Experiment results
        """
        logger.info(f"Running clock skew: {skew_seconds}s for {duration}s")

        try:
            # In production, would manipulate system clock or NTP
            # For now, simulate clock skew

            for node in target_nodes:
                logger.warning(f"Node {node} clock skew: {skew_seconds}s")
                # Future: Actual clock manipulation

            await asyncio.sleep(duration)

            result = {
                "scenario": "clock_skew",
                "target_nodes": target_nodes,
                "skew_seconds": skew_seconds,
                "duration": duration,
            }
            self._record_thinking(
                "advanced_chaos_clock_skew",
                "Complete clock skew scenario safely",
                {
                    "target_count_bucket": _safe_count_bucket(len(target_nodes)),
                    "skew_band": _safe_number_band(skew_seconds),
                    "duration_bucket": _safe_count_bucket(duration),
                },
            )
            return result
        except Exception as e:
            self._record_thinking(
                "advanced_chaos_clock_skew",
                "Record clock skew scenario error",
                {"error_type": type(e).__name__},
            )
            logger.error(f"Clock skew simulation error: {e}")
            return {"error": str(e)}


def create_advanced_chaos_controller() -> AdvancedChaosController:
    """Create an advanced chaos controller."""
    return AdvancedChaosController()
