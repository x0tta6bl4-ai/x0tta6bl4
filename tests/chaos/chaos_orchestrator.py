"""
Chaos Engineering Framework for x0tta6bl4

Implements distributed chaos injection and recovery metrics collection.

Chaos Layers:
1. Network Chaos - Partition, latency, packet loss
2. Node Chaos - Crash, restart, degradation
3. Byzantine Chaos - Invalid beacons, bad updates
4. Crypto Chaos - Signature/verification failures
5. Combined Chaos - Multiple simultaneous failures
"""

import logging
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class ChaosScenarioType(Enum):
    """Chaos scenario types"""

    NETWORK_PARTITION = "network_partition"
    LATENCY_INJECTION = "latency_injection"
    PACKET_LOSS = "packet_loss"
    MESSAGE_REORDERING = "message_reordering"
    NODE_CRASH = "node_crash"
    NODE_DEGRADATION = "node_degradation"
    CASCADING_FAILURES = "cascading_failures"
    BYZANTINE_BEACON = "byzantine_beacon"
    BYZANTINE_UPDATE = "byzantine_update"
    IDENTITY_SPOOFING = "identity_spoofing"
    CRYPTO_SIGNATURE_FAILURE = "crypto_signature_failure"
    CRYPTO_VERIFICATION_FAILURE = "crypto_verification_failure"
    KEY_ROTATION_STRESS = "key_rotation_stress"
    KEM_FAILURE = "kem_failure"
    COMBINED_STRESS = "combined_stress"


@dataclass
class ChaosScenario:
    """Base chaos scenario definition"""

    scenario_type: ChaosScenarioType
    start_time: float = field(default_factory=time.time)
    duration: float = 30.0
    intensity: float = 0.5  # 0-1 severity
    target_nodes: Set[str] = field(default_factory=set)
    description: str = ""


@dataclass
class NetworkChaosScenario(ChaosScenario):
    """Network layer chaos scenario"""

    partition_percentage: float = 0.5  # % of nodes to partition
    latency_ms: float = 0.0  # milliseconds to add
    packet_loss_rate: float = 0.0  # 0-1 loss rate


@dataclass
class NodeChaosScenario(ChaosScenario):
    """Node layer chaos scenario"""

    failure_rate: float = 0.1  # % of nodes to fail
    degradation_factor: float = 1.0  # Processing slowdown
    cascade_depth: int = 1  # How many failures to cascade


@dataclass
class ByzantineChaosScenario(ChaosScenario):
    """Byzantine behavior chaos scenario"""

    byzantine_percentage: float = 0.3  # % of nodes acting Byzantine
    attack_type: str = "gradient_corruption"  # Type of attack


@dataclass
class CryptoChaosScenario(ChaosScenario):
    """Cryptographic operation failure scenario"""

    failure_type: str = "signature_failure"
    retry_allowed: bool = True
    fallback_enabled: bool = True


@dataclass
class RecoveryMetrics:
    """Recovery behavior metrics"""

    scenario_type: ChaosScenarioType
    detection_time: float = 0.0  # Seconds to detect failure
    recovery_time: float = 0.0  # Seconds to full recovery
    data_loss: int = 0  # Bytes lost
    messages_dropped: int = 0
    cascade_depth: int = 0  # How many nodes affected
    self_healing_triggered: bool = False
    recovery_success: bool = False
    timestamp: float = field(default_factory=time.time)


@dataclass
class ChaosTestResult:
    """Complete chaos test result"""

    test_name: str
    start_time: str
    end_time: str
    duration_seconds: float
    scenarios_executed: int
    scenarios_passed: int
    scenarios_failed: int
    total_recovery_time: float
    total_data_loss: int
    recovery_metrics: List[RecoveryMetrics] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def calculate_pass_rate(self) -> float:
        """Calculate scenario pass rate"""
        if self.scenarios_executed == 0:
            return 0.0
        return (self.scenarios_passed / self.scenarios_executed) * 100

    def generate_report(self) -> Dict[str, Any]:
        """Generate chaos test report"""
        return {
            "metadata": {
                "test_name": self.test_name,
                "start_time": self.start_time,
                "end_time": self.end_time,
                "duration_seconds": self.duration_seconds,
                "timestamp": datetime.utcnow().isoformat(),
            },
            "summary": {
                "scenarios_executed": self.scenarios_executed,
                "scenarios_passed": self.scenarios_passed,
                "scenarios_failed": self.scenarios_failed,
                "pass_rate_percent": self.calculate_pass_rate(),
                "total_recovery_time": self.total_recovery_time,
                "total_data_loss_bytes": self.total_data_loss,
            },
            "recovery_metrics": [
                {
                    "scenario_type": m.scenario_type.value,
                    "detection_time_seconds": m.detection_time,
                    "recovery_time_seconds": m.recovery_time,
                    "data_loss_bytes": m.data_loss,
                    "messages_dropped": m.messages_dropped,
                    "cascade_depth": m.cascade_depth,
                    "self_healing_triggered": m.self_healing_triggered,
                    "recovery_success": m.recovery_success,
                }
                for m in self.recovery_metrics
            ],
            "errors": self.errors,
        }


class NetworkFailureInjector:
    """Inject network layer failures"""

    def __init__(self):
        self.partitioned_nodes: Set[str] = set()
        self.latency_map: Dict[str, float] = {}
        self.packet_loss_map: Dict[str, float] = {}

    def partition_nodes(self, nodes: List[str], percentage: float = 0.5) -> None:
        """Partition nodes from mesh"""
        num_to_partition = max(1, int(len(nodes) * percentage))
        self.partitioned_nodes = set(random.sample(nodes, num_to_partition))
        logger.info(
            f"Partitioned {len(self.partitioned_nodes)} nodes: {self.partitioned_nodes}"
        )

    def inject_latency(self, nodes: List[str], latency_ms: float) -> None:
        """Add latency to node communications"""
        for node in nodes:
            self.latency_map[node] = latency_ms / 1000.0
        logger.info(f"Injected {latency_ms}ms latency to {len(nodes)} nodes")

    def inject_packet_loss(self, nodes: List[str], loss_rate: float) -> None:
        """Inject packet loss"""
        for node in nodes:
            self.packet_loss_map[node] = loss_rate
        logger.info(f"Injected {loss_rate*100}% packet loss to {len(nodes)} nodes")

    def check_partition(self, node_id: str) -> bool:
        """Check if node is partitioned"""
        return node_id in self.partitioned_nodes

    def get_latency(self, node_id: str) -> float:
        """Get latency for node"""
        return self.latency_map.get(node_id, 0.0)

    def should_drop_packet(self, node_id: str) -> bool:
        """Determine if packet should be dropped"""
        if node_id not in self.packet_loss_map:
            return False
        return random.random() < self.packet_loss_map[node_id]

    def clear_failures(self) -> None:
        """Clear all injected failures"""
        self.partitioned_nodes.clear()
        self.latency_map.clear()
        self.packet_loss_map.clear()


class NodeFailureInjector:
    """Inject node layer failures"""

    def __init__(self):
        self.failed_nodes: Set[str] = set()
        self.degraded_nodes: Dict[str, float] = {}
        self.node_status: Dict[str, str] = {}  # "healthy", "failed", "degraded"

    def crash_node(self, node_id: str) -> None:
        """Crash a node"""
        self.failed_nodes.add(node_id)
        self.node_status[node_id] = "failed"
        logger.info(f"Crashed node {node_id}")

    def crash_multiple(self, nodes: List[str], count: int) -> None:
        """Crash multiple nodes"""
        to_crash = random.sample(nodes, min(count, len(nodes)))
        for node in to_crash:
            self.crash_node(node)

    def degrade_node(self, node_id: str, slowdown_factor: float) -> None:
        """Degrade node performance (slowdown)"""
        self.degraded_nodes[node_id] = slowdown_factor
        self.node_status[node_id] = "degraded"
        logger.info(f"Degraded node {node_id} with {slowdown_factor}x slowdown")

    def recover_node(self, node_id: str) -> None:
        """Recover a failed node"""
        self.failed_nodes.discard(node_id)
        self.degraded_nodes.pop(node_id, None)
        self.node_status[node_id] = "healthy"
        logger.info(f"Recovered node {node_id}")

    def is_failed(self, node_id: str) -> bool:
        """Check if node is failed"""
        return node_id in self.failed_nodes

    def get_processing_time(self, node_id: str, base_time: float) -> float:
        """Get adjusted processing time for degraded node"""
        if node_id in self.degraded_nodes:
            return base_time * self.degraded_nodes[node_id]
        return base_time

    def clear_failures(self) -> None:
        """Clear all node failures"""
        self.failed_nodes.clear()
        self.degraded_nodes.clear()
        self.node_status.clear()


class ByzantineInjector:
    """Inject Byzantine node behavior"""

    def __init__(self):
        self.byzantine_nodes: Set[str] = set()
        self.byzantine_attack_type: Dict[str, str] = {}

    def activate_byzantine_nodes(
        self,
        nodes: List[str],
        percentage: float = 0.3,
        attack_type: str = "gradient_corruption",
    ) -> None:
        """Activate Byzantine behavior in nodes"""
        num_byzantine = max(1, int(len(nodes) * percentage))
        self.byzantine_nodes = set(random.sample(nodes, num_byzantine))
        for node in self.byzantine_nodes:
            self.byzantine_attack_type[node] = attack_type
        logger.info(
            f"Activated {len(self.byzantine_nodes)} Byzantine nodes ({attack_type})"
        )

    def corrupt_beacon(self, beacon: Dict[str, Any], node_id: str) -> Dict[str, Any]:
        """Corrupt beacon from Byzantine node"""
        if node_id not in self.byzantine_nodes:
            return beacon

        # Create invalid signature
        corrupted = beacon.copy()
        corrupted["signature"] = b"invalid_signature_xyz"
        corrupted["is_byzantine"] = True
        return corrupted

    def corrupt_gradient(self, gradient: np.ndarray, node_id: str) -> np.ndarray:
        """Corrupt gradient update from Byzantine node"""
        if node_id not in self.byzantine_nodes:
            return gradient

        # Large random gradient to poison aggregation
        return np.random.randn(*gradient.shape) * 100.0

    def is_byzantine(self, node_id: str) -> bool:
        """Check if node is Byzantine"""
        return node_id in self.byzantine_nodes

    def get_attack_type(self, node_id: str) -> str:
        """Get Byzantine attack type"""
        return self.byzantine_attack_type.get(node_id, "unknown")

    def clear_byzantine(self) -> None:
        """Clear Byzantine nodes"""
        self.byzantine_nodes.clear()
        self.byzantine_attack_type.clear()


class CryptoFailureInjector:
    """Inject cryptographic operation failures"""

    def __init__(self):
        self.failing_operations: Dict[str, List[str]] = {
            "signature": [],
            "verification": [],
            "kem": [],
        }
        self.failure_count: Dict[str, int] = {
            "signature": 0,
            "verification": 0,
            "kem": 0,
        }

    def inject_signature_failure(self, node_ids: List[str]) -> None:
        """Inject signature operation failures"""
        self.failing_operations["signature"].extend(node_ids)
        logger.info(f"Injected signature failures for {len(node_ids)} nodes")

    def inject_verification_failure(self, node_ids: List[str]) -> None:
        """Inject signature verification failures"""
        self.failing_operations["verification"].extend(node_ids)
        logger.info(f"Injected verification failures for {len(node_ids)} nodes")

    def inject_kem_failure(self, node_ids: List[str]) -> None:
        """Inject KEM operation failures"""
        self.failing_operations["kem"].extend(node_ids)
        logger.info(f"Injected KEM failures for {len(node_ids)} nodes")

    def should_fail_signature(self, node_id: str) -> bool:
        """Check if signature should fail"""
        if node_id in self.failing_operations["signature"]:
            self.failure_count["signature"] += 1
            return True
        return False

    def should_fail_verification(self, node_id: str) -> bool:
        """Check if verification should fail"""
        if node_id in self.failing_operations["verification"]:
            self.failure_count["verification"] += 1
            return True
        return False

    def should_fail_kem(self, node_id: str) -> bool:
        """Check if KEM should fail"""
        if node_id in self.failing_operations["kem"]:
            self.failure_count["kem"] += 1
            return True
        return False

    def clear_failures(self) -> None:
        """Clear all crypto failures"""
        self.failing_operations["signature"].clear()
        self.failing_operations["verification"].clear()
        self.failing_operations["kem"].clear()
        self.failure_count["signature"] = 0
        self.failure_count["verification"] = 0
        self.failure_count["kem"] = 0


class RecoveryMonitor:
    """Monitor and measure recovery metrics"""

    def __init__(self):
        self.failure_events: List[Dict[str, Any]] = []
        self.detection_times: Dict[ChaosScenarioType, List[float]] = {}
        self.recovery_times: Dict[ChaosScenarioType, List[float]] = {}

    def record_failure(
        self, scenario_type: ChaosScenarioType, node_ids: List[str], timestamp: float
    ) -> None:
        """Record a failure event"""
        self.failure_events.append(
            {
                "scenario_type": scenario_type,
                "node_ids": node_ids,
                "timestamp": timestamp,
            }
        )

    def record_detection(
        self, scenario_type: ChaosScenarioType, detection_time: float
    ) -> None:
        """Record failure detection time"""
        if scenario_type not in self.detection_times:
            self.detection_times[scenario_type] = []
        self.detection_times[scenario_type].append(detection_time)

    def record_recovery(
        self, scenario_type: ChaosScenarioType, recovery_time: float
    ) -> None:
        """Record recovery time"""
        if scenario_type not in self.recovery_times:
            self.recovery_times[scenario_type] = []
        self.recovery_times[scenario_type].append(recovery_time)

    def get_average_detection_time(self, scenario_type: ChaosScenarioType) -> float:
        """Get average detection time for scenario type"""
        times = self.detection_times.get(scenario_type, [])
        if not times:
            return 0.0
        return sum(times) / len(times)

    def get_average_recovery_time(self, scenario_type: ChaosScenarioType) -> float:
        """Get average recovery time for scenario type"""
        times = self.recovery_times.get(scenario_type, [])
        if not times:
            return 0.0
        return sum(times) / len(times)


class ChaosOrchestrator:
    """Master orchestrator for chaos injection and coordination"""

    def __init__(self, node_count: int = 100):
        self.node_count = node_count
        self.all_nodes = [f"node-{i}" for i in range(node_count)]

        # Injectors
        self.network_injector = NetworkFailureInjector()
        self.node_injector = NodeFailureInjector()
        self.byzantine_injector = ByzantineInjector()
        self.crypto_injector = CryptoFailureInjector()

        # Monitoring
        self.recovery_monitor = RecoveryMonitor()

        # State
        self.active_scenarios: List[ChaosScenario] = []
        self.start_time = None

    def inject_network_partition(
        self, percentage: float = 0.5, duration: float = 30.0
    ) -> ChaosScenario:
        """Inject network partition"""
        scenario = NetworkChaosScenario(
            scenario_type=ChaosScenarioType.NETWORK_PARTITION,
            duration=duration,
            intensity=percentage,
            partition_percentage=percentage,
        )
        self.network_injector.partition_nodes(self.all_nodes, percentage)
        self.active_scenarios.append(scenario)
        return scenario

    def inject_latency(
        self, latency_ms: float, percentage: float = 1.0, duration: float = 30.0
    ) -> ChaosScenario:
        """Inject latency"""
        scenario = NetworkChaosScenario(
            scenario_type=ChaosScenarioType.LATENCY_INJECTION,
            duration=duration,
            latency_ms=latency_ms,
            intensity=latency_ms / 1000.0,
        )
        num_nodes = max(1, int(len(self.all_nodes) * percentage))
        target_nodes = random.sample(self.all_nodes, num_nodes)
        self.network_injector.inject_latency(target_nodes, latency_ms)
        scenario.target_nodes = set(target_nodes)
        self.active_scenarios.append(scenario)
        return scenario

    def inject_packet_loss(
        self, loss_rate: float, percentage: float = 1.0, duration: float = 30.0
    ) -> ChaosScenario:
        """Inject packet loss"""
        scenario = NetworkChaosScenario(
            scenario_type=ChaosScenarioType.PACKET_LOSS,
            duration=duration,
            intensity=loss_rate,
            packet_loss_rate=loss_rate,
        )
        num_nodes = max(1, int(len(self.all_nodes) * percentage))
        target_nodes = random.sample(self.all_nodes, num_nodes)
        self.network_injector.inject_packet_loss(target_nodes, loss_rate)
        scenario.target_nodes = set(target_nodes)
        self.active_scenarios.append(scenario)
        return scenario

    def inject_node_crashes(
        self, count: int = 5, duration: float = 30.0
    ) -> ChaosScenario:
        """Inject node crashes"""
        scenario = NodeChaosScenario(
            scenario_type=ChaosScenarioType.NODE_CRASH,
            duration=duration,
            failure_rate=count / len(self.all_nodes),
            intensity=count / len(self.all_nodes),
        )
        self.node_injector.crash_multiple(self.all_nodes, count)
        self.active_scenarios.append(scenario)
        return scenario

    def inject_node_degradation(
        self,
        slowdown_factor: float = 10.0,
        percentage: float = 0.5,
        duration: float = 30.0,
    ) -> ChaosScenario:
        """Inject node performance degradation"""
        scenario = NodeChaosScenario(
            scenario_type=ChaosScenarioType.NODE_DEGRADATION,
            duration=duration,
            degradation_factor=slowdown_factor,
            intensity=percentage,
        )
        num_nodes = max(1, int(len(self.all_nodes) * percentage))
        target_nodes = random.sample(self.all_nodes, num_nodes)
        for node in target_nodes:
            self.node_injector.degrade_node(node, slowdown_factor)
        scenario.target_nodes = set(target_nodes)
        self.active_scenarios.append(scenario)
        return scenario

    def inject_byzantine_nodes(
        self,
        percentage: float = 0.3,
        attack_type: str = "gradient_corruption",
        duration: float = 30.0,
    ) -> ChaosScenario:
        """Inject Byzantine nodes"""
        scenario = ByzantineChaosScenario(
            scenario_type=ChaosScenarioType.BYZANTINE_UPDATE,
            duration=duration,
            byzantine_percentage=percentage,
            attack_type=attack_type,
            intensity=percentage,
        )
        self.byzantine_injector.activate_byzantine_nodes(
            self.all_nodes, percentage, attack_type
        )
        scenario.target_nodes = self.byzantine_injector.byzantine_nodes
        self.active_scenarios.append(scenario)
        return scenario

    def inject_crypto_failures(
        self,
        failure_type: str = "signature_failure",
        percentage: float = 0.5,
        duration: float = 30.0,
    ) -> ChaosScenario:
        """Inject cryptographic operation failures"""
        scenario = CryptoChaosScenario(
            scenario_type=ChaosScenarioType.CRYPTO_SIGNATURE_FAILURE,
            duration=duration,
            failure_type=failure_type,
            intensity=percentage,
        )
        num_nodes = max(1, int(len(self.all_nodes) * percentage))
        target_nodes = random.sample(self.all_nodes, num_nodes)

        if failure_type == "signature_failure":
            self.crypto_injector.inject_signature_failure(target_nodes)
        elif failure_type == "verification_failure":
            self.crypto_injector.inject_verification_failure(target_nodes)
        elif failure_type == "kem_failure":
            self.crypto_injector.inject_kem_failure(target_nodes)

        scenario.target_nodes = set(target_nodes)
        self.active_scenarios.append(scenario)
        return scenario

    def clear_all_chaos(self) -> None:
        """Clear all injected chaos"""
        self.network_injector.clear_failures()
        self.node_injector.clear_failures()
        self.byzantine_injector.clear_byzantine()
        self.crypto_injector.clear_failures()
        self.active_scenarios.clear()
        logger.info("Cleared all chaos injections")

    def is_network_partitioned(self, node_id: str) -> bool:
        """Check if node is partitioned"""
        return self.network_injector.check_partition(node_id)

    def get_network_latency(self, node_id: str) -> float:
        """Get network latency for node"""
        return self.network_injector.get_latency(node_id)

    def should_drop_network_packet(self, node_id: str) -> bool:
        """Check if packet should be dropped"""
        return self.network_injector.should_drop_packet(node_id)

    def is_node_failed(self, node_id: str) -> bool:
        """Check if node is failed"""
        return self.node_injector.is_failed(node_id)

    def get_node_processing_time(self, node_id: str, base_time: float) -> float:
        """Get adjusted processing time for node"""
        return self.node_injector.get_processing_time(node_id, base_time)

    def is_byzantine_node(self, node_id: str) -> bool:
        """Check if node is Byzantine"""
        return self.byzantine_injector.is_byzantine(node_id)

    def get_byzantine_attack_type(self, node_id: str) -> str:
        """Get Byzantine attack type"""
        return self.byzantine_injector.get_attack_type(node_id)

    def get_active_scenario_count(self) -> int:
        """Get number of active chaos scenarios"""
        return len(self.active_scenarios)

    def get_chaos_metrics(self) -> Dict[str, Any]:
        """Get current chaos metrics"""
        return {
            "active_scenarios": len(self.active_scenarios),
            "partitioned_nodes": len(self.network_injector.partitioned_nodes),
            "failed_nodes": len(self.node_injector.failed_nodes),
            "degraded_nodes": len(self.node_injector.degraded_nodes),
            "byzantine_nodes": len(self.byzantine_injector.byzantine_nodes),
            "signature_failures": self.crypto_injector.failure_count["signature"],
            "verification_failures": self.crypto_injector.failure_count["verification"],
            "kem_failures": self.crypto_injector.failure_count["kem"],
        }
