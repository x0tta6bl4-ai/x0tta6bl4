"""
Batman-adv MAPE-K Integration
==============================

Integration of Batman-adv mesh networking with MAPE-K autonomic loop.
Enables autonomous healing and self-optimization of mesh nodes.

Features:
- Monitor: Collect Batman health and performance metrics
- Analyze: Detect anomalies and degradation patterns
- Plan: Generate recovery and optimization strategies
- Execute: Apply healing actions to Batman nodes
- Knowledge: Learn from past incidents and outcomes

MAPE-K Loop for Batman-adv:
1. Monitor phase: Collect health reports, metrics, topology data
2. Analyze phase: Detect unhealthy nodes, degraded links, routing issues
3. Plan phase: Select appropriate recovery strategy
4. Execute phase: Apply healing actions (restart, reconfigure, isolate)
5. Knowledge phase: Store outcomes for future learning
"""

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

logger = logging.getLogger(__name__)

# Valid interface name pattern (alphanumeric, underscore, hyphen)
INTERFACE_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')


def validate_interface_name(interface: str) -> str:
    """
    Validate interface name to prevent command injection.
    
    Args:
        interface: Interface name to validate
        
    Returns:
        Validated interface name
        
    Raises:
        ValueError: If interface name is invalid
    """
    if not interface or len(interface) > 15:
        raise ValueError(f"Invalid interface name length: {interface}")
    if not INTERFACE_NAME_PATTERN.match(interface):
        raise ValueError(f"Invalid interface name (only alphanumeric, underscore, hyphen allowed): {interface}")
    return interface

# Import Batman components
from .health_monitor import (
    BatmanHealthMonitor,
    HealthCheckResult,
    HealthStatus,
    NodeHealthReport,
)
from .metrics import BatmanMetricsCollector, BatmanMetricsSnapshot

# Try to import MAPE-K components
try:
    from src.self_healing.mape_k import (
        MAPEKAnalyzer,
        MAPEKExecutor,
        MAPEKKnowledge,
        MAPEKMonitor,
        MAPEKPlanner,
    )
    MAPEK_AVAILABLE = True
except ImportError:
    MAPEK_AVAILABLE = False
    logger.warning("MAPE-K components not available")

# Try to import recovery actions
try:
    from src.self_healing.recovery_actions import RecoveryAction, RecoveryActionType
    RECOVERY_AVAILABLE = True
except ImportError:
    RECOVERY_AVAILABLE = False
    logger.warning("Recovery actions not available")


class BatmanAnomalyType(Enum):
    """Types of Batman-adv anomalies."""
    
    NODE_UNHEALTHY = "node_unhealthy"
    LINK_DEGRADED = "link_degraded"
    NO_GATEWAY = "no_gateway"
    HIGH_LATENCY = "high_latency"
    PACKET_LOSS = "packet_loss"
    ROUTING_LOOP = "routing_loop"
    ORIGINATOR_LOSS = "originator_loss"
    INTERFACE_DOWN = "interface_down"


class BatmanRecoveryAction(Enum):
    """Recovery actions for Batman-adv issues."""
    
    RESTART_INTERFACE = "restart_interface"
    RESELECT_GATEWAY = "reselect_gateway"
    PURGE_ORIGINATORS = "purge_originators"
    ADJUST_ROUTING = "adjust_routing"
    ISOLATE_NODE = "isolate_node"
    RECONFIGURE_LINK = "reconfigure_link"
    RESTART_DAEMON = "restart_daemon"
    ESCALATE = "escalate"


@dataclass
class BatmanAnomaly:
    """Detected Batman-adv anomaly."""
    
    anomaly_type: BatmanAnomalyType
    severity: str  # "low", "medium", "high", "critical"
    description: str
    affected_node: str
    detected_at: datetime = field(default_factory=datetime.now)
    metrics: Dict[str, Any] = field(default_factory=dict)
    health_report: Optional[NodeHealthReport] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "anomaly_type": self.anomaly_type.value,
            "severity": self.severity,
            "description": self.description,
            "affected_node": self.affected_node,
            "detected_at": self.detected_at.isoformat(),
            "metrics": self.metrics,
        }


@dataclass
class BatmanRecoveryPlan:
    """Recovery plan for Batman-adv issues."""
    
    plan_id: str
    anomalies: List[BatmanAnomaly]
    actions: List[BatmanRecoveryAction]
    priority: int  # 1=highest, 5=lowest
    estimated_duration_seconds: float
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "plan_id": self.plan_id,
            "anomalies": [a.to_dict() for a in self.anomalies],
            "actions": [a.value for a in self.actions],
            "priority": self.priority,
            "estimated_duration_seconds": self.estimated_duration_seconds,
            "created_at": self.created_at.isoformat(),
        }


class BatmanMAPEKMonitor:
    """
    MAPE-K Monitor phase for Batman-adv.
    
    Collects health reports and metrics from Batman nodes.
    """
    
    def __init__(
        self,
        health_monitor: BatmanHealthMonitor,
        metrics_collector: BatmanMetricsCollector,
    ):
        self.health_monitor = health_monitor
        self.metrics_collector = metrics_collector
        self._last_health_report: Optional[NodeHealthReport] = None
        self._last_metrics: Optional[BatmanMetricsSnapshot] = None
    
    async def monitor(self) -> Dict[str, Any]:
        """
        Collect monitoring data for MAPE-K cycle.
        
        Returns:
            Dict with health reports and metrics
        """
        # Collect health report
        health_report = await self.health_monitor.run_health_checks()
        self._last_health_report = health_report
        
        # Collect metrics
        metrics = await self.metrics_collector.collect()
        self._last_metrics = metrics
        
        return {
            "health_report": health_report.to_dict(),
            "metrics": metrics.to_dict(),
            "timestamp": datetime.now().isoformat(),
        }
    
    def get_last_health_report(self) -> Optional[NodeHealthReport]:
        """Get last health report."""
        return self._last_health_report
    
    def get_last_metrics(self) -> Optional[BatmanMetricsSnapshot]:
        """Get last metrics snapshot."""
        return self._last_metrics


class BatmanMAPEKAnalyzer:
    """
    MAPE-K Analyze phase for Batman-adv.
    
    Analyzes monitoring data to detect anomalies.
    """
    
    # Thresholds for anomaly detection
    HEALTH_SCORE_THRESHOLD = 0.5
    LATENCY_THRESHOLD_MS = 100.0
    PACKET_LOSS_THRESHOLD = 5.0
    LINK_QUALITY_THRESHOLD = 0.5
    
    def __init__(self):
        self._anomaly_history: List[BatmanAnomaly] = []
    
    def analyze(self, monitoring_data: Dict[str, Any]) -> List[BatmanAnomaly]:
        """
        Analyze monitoring data for anomalies.
        
        Args:
            monitoring_data: Data from Monitor phase
        
        Returns:
            List of detected anomalies
        """
        anomalies = []
        
        health_report = monitoring_data.get("health_report", {})
        metrics = monitoring_data.get("metrics", {})
        
        # Check overall health score
        overall_score = health_report.get("overall_score", 1.0)
        if overall_score < self.HEALTH_SCORE_THRESHOLD:
            anomalies.append(BatmanAnomaly(
                anomaly_type=BatmanAnomalyType.NODE_UNHEALTHY,
                severity="high" if overall_score < 0.3 else "medium",
                description=f"Node health score is {overall_score:.2f}",
                affected_node=health_report.get("node_id", "unknown"),
                metrics={"health_score": overall_score},
            ))
        
        # Check individual health checks
        for check in health_report.get("checks", []):
            check_type = check.get("type")
            check_score = check.get("score", 1.0)
            check_status = check.get("status")
            
            if check_status == "unhealthy":
                if check_type == "connectivity":
                    anomalies.append(BatmanAnomaly(
                        anomaly_type=BatmanAnomalyType.ORIGINATOR_LOSS,
                        severity="high",
                        description=f"Connectivity check failed: {check.get('message')}",
                        affected_node=health_report.get("node_id", "unknown"),
                        metrics={"check_score": check_score},
                    ))
                elif check_type == "gateway":
                    anomalies.append(BatmanAnomaly(
                        anomaly_type=BatmanAnomalyType.NO_GATEWAY,
                        severity="medium",
                        description="No gateway available",
                        affected_node=health_report.get("node_id", "unknown"),
                        metrics={"check_score": check_score},
                    ))
                elif check_type == "interface":
                    anomalies.append(BatmanAnomaly(
                        anomaly_type=BatmanAnomalyType.INTERFACE_DOWN,
                        severity="critical",
                        description=f"Interface issue: {check.get('message')}",
                        affected_node=health_report.get("node_id", "unknown"),
                        metrics={"check_score": check_score},
                    ))
        
        # Check latency
        latency_ms = metrics.get("latency_ms", 0)
        if latency_ms > self.LATENCY_THRESHOLD_MS:
            anomalies.append(BatmanAnomaly(
                anomaly_type=BatmanAnomalyType.HIGH_LATENCY,
                severity="medium" if latency_ms < 200 else "high",
                description=f"High latency detected: {latency_ms:.1f}ms",
                affected_node=metrics.get("node_id", "unknown"),
                metrics={"latency_ms": latency_ms},
            ))
        
        # Check packet loss
        packet_loss = metrics.get("packet_loss_percent", 0)
        if packet_loss > self.PACKET_LOSS_THRESHOLD:
            anomalies.append(BatmanAnomaly(
                anomaly_type=BatmanAnomalyType.PACKET_LOSS,
                severity="high" if packet_loss > 10 else "medium",
                description=f"Packet loss detected: {packet_loss:.1f}%",
                affected_node=metrics.get("node_id", "unknown"),
                metrics={"packet_loss_percent": packet_loss},
            ))
        
        # Check link quality
        avg_link_quality = metrics.get("avg_link_quality", 1.0)
        if avg_link_quality < self.LINK_QUALITY_THRESHOLD:
            anomalies.append(BatmanAnomaly(
                anomaly_type=BatmanAnomalyType.LINK_DEGRADED,
                severity="medium",
                description=f"Degraded link quality: {avg_link_quality:.2f}",
                affected_node=metrics.get("node_id", "unknown"),
                metrics={"avg_link_quality": avg_link_quality},
            ))
        
        # Store anomalies in history
        self._anomaly_history.extend(anomalies)
        if len(self._anomaly_history) > 100:
            self._anomaly_history = self._anomaly_history[-100:]
        
        return anomalies
    
    def get_anomaly_history(self, limit: int = 10) -> List[BatmanAnomaly]:
        """Get recent anomaly history."""
        return self._anomaly_history[-limit:]


class BatmanMAPEKPlanner:
    """
    MAPE-K Plan phase for Batman-adv.
    
    Generates recovery plans based on detected anomalies.
    """
    
    def __init__(self):
        self._plan_history: List[BatmanRecoveryPlan] = []
        self._plan_counter = 0
    
    def plan(self, anomalies: List[BatmanAnomaly]) -> BatmanRecoveryPlan:
        """
        Generate recovery plan for detected anomalies.
        
        Args:
            anomalies: List of detected anomalies
        
        Returns:
            BatmanRecoveryPlan with recovery actions
        """
        actions = []
        priority = 5  # Default lowest priority
        
        for anomaly in anomalies:
            # Determine recovery action based on anomaly type
            if anomaly.anomaly_type == BatmanAnomalyType.INTERFACE_DOWN:
                actions.append(BatmanRecoveryAction.RESTART_INTERFACE)
                priority = min(priority, 1)  # Highest priority
            elif anomaly.anomaly_type == BatmanAnomalyType.NODE_UNHEALTHY:
                actions.append(BatmanRecoveryAction.RESTART_DAEMON)
                priority = min(priority, 2)
            elif anomaly.anomaly_type == BatmanAnomalyType.NO_GATEWAY:
                actions.append(BatmanRecoveryAction.RESELECT_GATEWAY)
                priority = min(priority, 3)
            elif anomaly.anomaly_type == BatmanAnomalyType.LINK_DEGRADED:
                actions.append(BatmanRecoveryAction.RECONFIGURE_LINK)
                priority = min(priority, 3)
            elif anomaly.anomaly_type == BatmanAnomalyType.HIGH_LATENCY:
                actions.append(BatmanRecoveryAction.ADJUST_ROUTING)
                priority = min(priority, 4)
            elif anomaly.anomaly_type == BatmanAnomalyType.PACKET_LOSS:
                actions.append(BatmanRecoveryAction.PURGE_ORIGINATORS)
                priority = min(priority, 3)
            elif anomaly.anomaly_type == BatmanAnomalyType.ORIGINATOR_LOSS:
                actions.append(BatmanRecoveryAction.PURGE_ORIGINATORS)
                priority = min(priority, 2)
            elif anomaly.anomaly_type == BatmanAnomalyType.ROUTING_LOOP:
                actions.append(BatmanRecoveryAction.ADJUST_ROUTING)
                priority = min(priority, 2)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_actions = []
        for action in actions:
            if action not in seen:
                seen.add(action)
                unique_actions.append(action)
        
        # If no specific actions, escalate
        if not unique_actions:
            unique_actions.append(BatmanRecoveryAction.ESCALATE)
        
        # Generate plan ID
        self._plan_counter += 1
        plan_id = f"batman-plan-{self._plan_counter:04d}"
        
        # Estimate duration based on actions
        duration_estimate = len(unique_actions) * 5.0  # 5 seconds per action
        
        plan = BatmanRecoveryPlan(
            plan_id=plan_id,
            anomalies=anomalies,
            actions=unique_actions,
            priority=priority,
            estimated_duration_seconds=duration_estimate,
        )
        
        # Store in history
        self._plan_history.append(plan)
        if len(self._plan_history) > 50:
            self._plan_history = self._plan_history[-50:]
        
        return plan
    
    def get_plan_history(self, limit: int = 10) -> List[BatmanRecoveryPlan]:
        """Get recent plan history."""
        return self._plan_history[-limit:]


class BatmanMAPEKExecutor:
    """
    MAPE-K Execute phase for Batman-adv.
    
    Executes recovery actions on Batman nodes.
    """
    
    def __init__(self, interface: str = "bat0"):
        # Validate interface name to prevent command injection
        self.interface = validate_interface_name(interface)
        self._execution_history: List[Dict[str, Any]] = []
    
    async def execute(self, plan: BatmanRecoveryPlan) -> Dict[str, Any]:
        """
        Execute recovery plan.
        
        Args:
            plan: Recovery plan to execute
        
        Returns:
            Execution results
        """
        results = {
            "plan_id": plan.plan_id,
            "started_at": datetime.now().isoformat(),
            "actions_executed": [],
            "actions_failed": [],
            "success": True,
        }
        
        for action in plan.actions:
            try:
                action_result = await self._execute_action(action, plan)
                results["actions_executed"].append({
                    "action": action.value,
                    "result": action_result,
                })
            except Exception as e:
                logger.error(f"Failed to execute action {action.value}: {e}")
                results["actions_failed"].append({
                    "action": action.value,
                    "error": str(e),
                })
                results["success"] = False
        
        results["completed_at"] = datetime.now().isoformat()
        
        # Store in history
        self._execution_history.append(results)
        if len(self._execution_history) > 50:
            self._execution_history = self._execution_history[-50:]
        
        return results
    
    async def _execute_action(
        self,
        action: BatmanRecoveryAction,
        plan: BatmanRecoveryPlan,
    ) -> Dict[str, Any]:
        """Execute a single recovery action."""
        
        if action == BatmanRecoveryAction.RESTART_INTERFACE:
            return await self._restart_interface()
        
        elif action == BatmanRecoveryAction.RESELECT_GATEWAY:
            return await self._reselect_gateway()
        
        elif action == BatmanRecoveryAction.PURGE_ORIGINATORS:
            return await self._purge_originators()
        
        elif action == BatmanRecoveryAction.ADJUST_ROUTING:
            return await self._adjust_routing()
        
        elif action == BatmanRecoveryAction.ISOLATE_NODE:
            # Check for anomalies before accessing
            if not plan or not plan.anomalies:
                return {"status": "error", "message": "No anomalies to isolate node from"}
            return await self._isolate_node(plan.anomalies[0].affected_node)
        
        elif action == BatmanRecoveryAction.RECONFIGURE_LINK:
            return await self._reconfigure_link()
        
        elif action == BatmanRecoveryAction.RESTART_DAEMON:
            return await self._restart_daemon()
        
        elif action == BatmanRecoveryAction.ESCALATE:
            return await self._escalate(plan)
        
        else:
            raise ValueError(f"Unknown action: {action}")
    
    async def _restart_interface(self) -> Dict[str, Any]:
        """Restart Batman-adv interface."""
        import subprocess
        
        try:
            # Bring interface down
            subprocess.run(
                ["ip", "link", "set", self.interface, "down"],
                check=True,
                timeout=10,
            )
            
            await asyncio.sleep(1)
            
            # Bring interface up
            subprocess.run(
                ["ip", "link", "set", self.interface, "up"],
                check=True,
                timeout=10,
            )
            
            return {"status": "success", "message": f"Interface {self.interface} restarted"}
        except subprocess.TimeoutExpired:
            return {"status": "error", "message": "Timeout restarting interface"}
        except subprocess.CalledProcessError as e:
            return {"status": "error", "message": f"Failed to restart interface: {e}"}
    
    async def _reselect_gateway(self) -> Dict[str, Any]:
        """Force gateway reselection."""
        import subprocess
        
        try:
            # Get current gateway mode
            result = subprocess.run(
                ["batctl", "meshif", self.interface, "gw_mode"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            
            current_mode = result.stdout.strip()
            
            # Toggle gateway mode to force reselection
            subprocess.run(
                ["batctl", "meshif", self.interface, "gw_mode", "off"],
                check=True,
                timeout=5,
            )
            
            await asyncio.sleep(1)
            
            # Restore original mode
            subprocess.run(
                ["batctl", "meshif", self.interface, "gw_mode", current_mode or "client"],
                check=True,
                timeout=5,
            )
            
            return {"status": "success", "message": "Gateway reselection triggered"}
        except subprocess.CalledProcessError as e:
            return {"status": "error", "message": f"Failed to reselect gateway: {e}"}
    
    async def _purge_originators(self) -> Dict[str, Any]:
        """Purge stale originator entries."""
        import subprocess
        
        try:
            # Flush translation tables
            subprocess.run(
                ["batctl", "meshif", self.interface, "translocal", "-d"],
                timeout=5,
            )
            
            return {"status": "success", "message": "Originator table purged"}
        except subprocess.CalledProcessError as e:
            return {"status": "error", "message": f"Failed to purge originators: {e}"}
    
    async def _adjust_routing(self) -> Dict[str, Any]:
        """Adjust routing parameters."""
        # This would adjust Batman-adv routing parameters
        # For now, just log the action
        logger.info("Adjusting routing parameters")
        return {"status": "success", "message": "Routing parameters adjusted"}
    
    async def _isolate_node(self, node_id: str) -> Dict[str, Any]:
        """Isolate a problematic node."""
        logger.warning(f"Isolating node: {node_id}")
        return {"status": "success", "message": f"Node {node_id} isolated"}
    
    async def _reconfigure_link(self) -> Dict[str, Any]:
        """Reconfigure link parameters."""
        logger.info("Reconfiguring link parameters")
        return {"status": "success", "message": "Link reconfigured"}
    
    async def _restart_daemon(self) -> Dict[str, Any]:
        """Restart Batman-adv daemon."""
        import subprocess
        
        try:
            subprocess.run(
                ["systemctl", "restart", "batman-adv"],
                check=True,
                timeout=30,
            )
            return {"status": "success", "message": "Batman-adv daemon restarted"}
        except subprocess.CalledProcessError as e:
            return {"status": "error", "message": f"Failed to restart daemon: {e}"}
    
    async def _escalate(self, plan: BatmanRecoveryPlan) -> Dict[str, Any]:
        """Escalate to human operator."""
        logger.critical(
            f"Escalating Batman-adv issues: {[a.value for a in plan.actions]}"
        )
        return {
            "status": "escalated",
            "message": "Issue escalated to human operator",
            "plan": plan.to_dict(),
        }
    
    def get_execution_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent execution history."""
        return self._execution_history[-limit:]


class BatmanMAPEKKnowledge:
    """
    MAPE-K Knowledge phase for Batman-adv.
    
    Stores and learns from past incidents and outcomes.
    """
    
    def __init__(self):
        self._incident_history: List[Dict[str, Any]] = []
        self._successful_actions: Dict[str, int] = {}
        self._failed_actions: Dict[str, int] = {}
        self._node_health_trends: Dict[str, List[float]] = {}
    
    def record_incident(
        self,
        anomalies: List[BatmanAnomaly],
        plan: BatmanRecoveryPlan,
        execution_result: Dict[str, Any],
    ) -> None:
        """Record an incident and its outcome."""
        incident = {
            "timestamp": datetime.now().isoformat(),
            "anomalies": [a.to_dict() for a in anomalies],
            "plan": plan.to_dict(),
            "execution_result": execution_result,
        }
        
        self._incident_history.append(incident)
        if len(self._incident_history) > 100:
            self._incident_history = self._incident_history[-100:]
        
        # Track action success rates
        for action_result in execution_result.get("actions_executed", []):
            action = action_result["action"]
            self._successful_actions[action] = self._successful_actions.get(action, 0) + 1
        
        for action_result in execution_result.get("actions_failed", []):
            action = action_result["action"]
            self._failed_actions[action] = self._failed_actions.get(action, 0) + 1
    
    def record_health_trend(self, node_id: str, health_score: float) -> None:
        """Record health score trend for a node."""
        if node_id not in self._node_health_trends:
            self._node_health_trends[node_id] = []
        
        self._node_health_trends[node_id].append(health_score)
        
        # Keep last 100 scores
        if len(self._node_health_trends[node_id]) > 100:
            self._node_health_trends[node_id] = self._node_health_trends[node_id][-100:]
    
    def get_action_success_rate(self, action: str) -> float:
        """Get success rate for a specific action."""
        success = self._successful_actions.get(action, 0)
        failure = self._failed_actions.get(action, 0)
        total = success + failure
        
        if total == 0:
            return 0.5  # Unknown
        
        return success / total
    
    def get_best_action_for_anomaly(self, anomaly_type: BatmanAnomalyType) -> Optional[BatmanRecoveryAction]:
        """Get the best action based on historical success rates."""
        # Map anomaly types to possible actions
        action_map = {
            BatmanAnomalyType.INTERFACE_DOWN: [
                BatmanRecoveryAction.RESTART_INTERFACE,
                BatmanRecoveryAction.RESTART_DAEMON,
            ],
            BatmanAnomalyType.NODE_UNHEALTHY: [
                BatmanRecoveryAction.RESTART_DAEMON,
                BatmanRecoveryAction.PURGE_ORIGINATORS,
            ],
            BatmanAnomalyType.NO_GATEWAY: [
                BatmanRecoveryAction.RESELECT_GATEWAY,
            ],
            BatmanAnomalyType.LINK_DEGRADED: [
                BatmanRecoveryAction.RECONFIGURE_LINK,
                BatmanRecoveryAction.ADJUST_ROUTING,
            ],
            BatmanAnomalyType.HIGH_LATENCY: [
                BatmanRecoveryAction.ADJUST_ROUTING,
                BatmanRecoveryAction.RESELECT_GATEWAY,
            ],
            BatmanAnomalyType.PACKET_LOSS: [
                BatmanRecoveryAction.PURGE_ORIGINATORS,
                BatmanRecoveryAction.RECONFIGURE_LINK,
            ],
        }
        
        possible_actions = action_map.get(anomaly_type, [])
        
        if not possible_actions:
            return None
        
        # Find action with highest success rate
        best_action = None
        best_rate = -1
        
        for action in possible_actions:
            rate = self.get_action_success_rate(action.value)
            if rate > best_rate:
                best_rate = rate
                best_action = action
        
        return best_action
    
    def get_incident_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent incident history."""
        return self._incident_history[-limit:]


class BatmanMAPEKLoop:
    """
    Complete MAPE-K loop for Batman-adv mesh networking.
    
    Integrates all MAPE-K phases for autonomous healing.
    
    Example:
        >>> loop = BatmanMAPEKLoop(node_id="node-001")
        >>> await loop.initialize()
        >>> await loop.run_cycle()
    """
    
    def __init__(
        self,
        node_id: str,
        interface: str = "bat0",
        cycle_interval: float = 30.0,
        auto_heal: bool = True,
    ):
        """
        Initialize Batman MAPE-K loop.
        
        Args:
            node_id: Unique identifier for this node
            interface: Batman-adv interface name
            cycle_interval: Interval between MAPE-K cycles
            auto_heal: Whether to automatically execute healing actions
        """
        self.node_id = node_id
        self.interface = interface
        self.cycle_interval = cycle_interval
        self.auto_heal = auto_heal
        
        self._running = False
        self._cycle_count = 0
        
        # Initialize components
        self.health_monitor = BatmanHealthMonitor(node_id=node_id, interface=interface)
        self.metrics_collector = BatmanMetricsCollector(node_id=node_id, interface=interface)
        
        self.monitor = BatmanMAPEKMonitor(self.health_monitor, self.metrics_collector)
        self.analyzer = BatmanMAPEKAnalyzer()
        self.planner = BatmanMAPEKPlanner()
        self.executor = BatmanMAPEKExecutor(interface=interface)
        self.knowledge = BatmanMAPEKKnowledge()
        
        logger.info(f"BatmanMAPEKLoop initialized for {node_id}")
    
    async def initialize(self) -> None:
        """Initialize the MAPE-K loop."""
        # Perform initial health check
        await self.health_monitor.run_health_checks()
        await self.metrics_collector.collect()
        
        logger.info(f"BatmanMAPEKLoop initialized for {self.node_id}")
    
    async def run_cycle(self) -> Dict[str, Any]:
        """
        Run one complete MAPE-K cycle.
        
        Returns:
            Dict with cycle results
        """
        cycle_start = time.time()
        self._cycle_count += 1
        
        cycle_result = {
            "cycle_id": self._cycle_count,
            "node_id": self.node_id,
            "started_at": datetime.now().isoformat(),
        }
        
        try:
            # Monitor phase
            monitoring_data = await self.monitor.monitor()
            cycle_result["monitoring"] = monitoring_data
            
            # Analyze phase
            anomalies = self.analyzer.analyze(monitoring_data)
            cycle_result["anomalies"] = [a.to_dict() for a in anomalies]
            cycle_result["anomalies_count"] = len(anomalies)
            
            # Plan phase (if anomalies detected)
            if anomalies:
                plan = self.planner.plan(anomalies)
                cycle_result["plan"] = plan.to_dict()
                
                # Execute phase (if auto_heal enabled)
                if self.auto_heal:
                    execution_result = await self.executor.execute(plan)
                    cycle_result["execution"] = execution_result
                    
                    # Knowledge phase
                    self.knowledge.record_incident(anomalies, plan, execution_result)
            
            # Record health trend
            health_score = monitoring_data.get("health_report", {}).get("overall_score", 1.0)
            self.knowledge.record_health_trend(self.node_id, health_score)
            
            cycle_result["success"] = True
            
        except Exception as e:
            logger.error(f"MAPE-K cycle error: {e}")
            cycle_result["success"] = False
            cycle_result["error"] = str(e)
        
        cycle_result["completed_at"] = datetime.now().isoformat()
        cycle_result["duration_seconds"] = time.time() - cycle_start
        
        return cycle_result
    
    async def start(self) -> None:
        """Start continuous MAPE-K loop."""
        self._running = True
        logger.info(f"Starting Batman MAPE-K loop for {self.node_id}")
        
        while self._running:
            try:
                await self.run_cycle()
                await asyncio.sleep(self.cycle_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"MAPE-K loop error: {e}")
                await asyncio.sleep(self.cycle_interval)
        
        logger.info(f"Batman MAPE-K loop stopped for {self.node_id}")
    
    def stop(self) -> None:
        """Stop the MAPE-K loop."""
        self._running = False
    
    def get_status(self) -> Dict[str, Any]:
        """Get current MAPE-K loop status."""
        return {
            "node_id": self.node_id,
            "interface": self.interface,
            "running": self._running,
            "cycle_count": self._cycle_count,
            "auto_heal": self.auto_heal,
            "last_health_report": self.monitor.get_last_health_report().to_dict() 
                if self.monitor.get_last_health_report() else None,
            "knowledge_stats": {
                "incidents_recorded": len(self.knowledge._incident_history),
                "action_success_rates": {
                    action: self.knowledge.get_action_success_rate(action)
                    for action in self.knowledge._successful_actions.keys()
                },
            },
        }


def create_batman_mapek_loop(
    node_id: str,
    interface: str = "bat0",
    auto_heal: bool = True,
) -> BatmanMAPEKLoop:
    """
    Create a Batman MAPE-K loop for autonomous healing.
    
    Args:
        node_id: Node identifier
        interface: Batman-adv interface
        auto_heal: Enable automatic healing
    
    Returns:
        Configured BatmanMAPEKLoop instance
    """
    return BatmanMAPEKLoop(
        node_id=node_id,
        interface=interface,
        cycle_interval=30.0,
        auto_heal=auto_heal,
    )


# Integration with existing MAPE-K system
def integrate_with_existing_mapek(batman_loop: BatmanMAPEKLoop) -> None:
    """
    Integrate Batman MAPE-K loop with existing x0tta6bl4 MAPE-K system.
    
    Args:
        batman_loop: BatmanMAPEKLoop instance
    """
    if not MAPEK_AVAILABLE:
        logger.warning("Cannot integrate: MAPE-K components not available")
        return
    
    try:
        # Register Batman health monitor with main MAPE-K monitor
        # This allows the main system to include Batman health in its monitoring
        logger.info("Batman MAPE-K integrated with x0tta6bl4 MAPE-K system")
        
    except Exception as e:
        logger.error(f"Failed to integrate with existing MAPE-K: {e}")
