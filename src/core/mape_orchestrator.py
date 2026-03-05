from typing import Any, Dict, Protocol, runtime_checkable, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import logging
import time
import os

# Lazy import with fallback for GraphSAGE ML module
# This allows the module to load even if ML dependencies are missing
def _get_graphsage_loader():
    """Lazy loader for GraphSAGE with ML_STUB_MODE support."""
    is_production = os.getenv("ENVIRONMENT", "").lower() == "production"
    stub_mode = os.getenv("ML_STUB_MODE", "false").lower() == "true"
    
    try:
        from src.ml.graphsage_anomaly_detector_v3_enhanced import create_graphsage_v3_for_mapek
        return create_graphsage_v3_for_mapek
    except ImportError as e:
        if stub_mode:
            logging.getLogger(__name__).warning(
                "⚠️ GraphSAGE not available, using stub. "
                "Set ML_STUB_MODE=false and install ML dependencies for production."
            )
            return lambda: None
        elif is_production:
            raise RuntimeError(
                f"GraphSAGE ML module REQUIRED in production. "
                f"Install dependencies or set ML_STUB_MODE=true (not recommended for production). "
                f"Error: {e}"
            )
        else:
            logging.getLogger(__name__).warning(
                "⚠️ GraphSAGE not available, using stub. "
                "Set ML_STUB_MODE=false for production or install ML dependencies."
            )
            return lambda: None

# Load GraphSAGE lazily
_graphsage_loader = None

logger = logging.getLogger(__name__)


class HealingActionType(str, Enum):
    """Types of self-healing actions supported."""
    RE_ROUTE = "re-route"
    RESTART_SERVICE = "restart-service"
    SCALE_UP = "scale-up"
    SCALE_DOWN = "scale-down"
    SWITCH_PROTOCOL = "switch-protocol"
    CLEAR_CACHE = "clear-cache"
    QUARANTINE_NODE = "quarantine-node"
    FAILOVER = "failover"
    DEGRADE_SERVICE = "degrade-service"
    NONE = "none"



class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class HealingAction:
    """Represents a self-healing action to be executed."""
    action_type: HealingActionType
    target: str
    reason: str
    severity: AlertSeverity = AlertSeverity.WARNING
    params: Dict[str, Any] = field(default_factory=dict)
    estimated_impact: float = 0.0  # 0.0 - 1.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class SystemState:
    """Current system state for MAPE-K."""
    metrics: Dict[str, Any] = field(default_factory=dict)
    active_alerts: List[Dict[str, Any]] = field(default_factory=list)
    healing_actions: List[HealingAction] = field(default_factory=list)
    last_update: float = field(default_factory=time.time)
    is_healthy: bool = True


@runtime_checkable
class PrometheusClient(Protocol):
    async def query(self, query_params: Dict[str, str]) -> Dict[str, Any]: ...

@runtime_checkable
class MeshClient(Protocol):
    async def apply_routing(self, plan: Dict[str, Any]) -> None: ...

@runtime_checkable
class DAOClient(Protocol):
    async def log_event(self, event_type: str, event_data: Dict[str, Any]) -> None: ...

@runtime_checkable
class IPFSClient(Protocol):
    async def snapshot(self, name: str) -> None: ...


class CircuitBreaker:
    """
    Circuit breaker to prevent cascading failures during self-healing.
    Tracks action frequency and temporarily blocks actions if too many failures occur.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 60.0,
        half_open_max_calls: int = 3
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout_seconds
        self.half_open_max_calls = half_open_max_calls
        
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._state = "closed"  # closed, open, half-open
        self._half_open_calls = 0
        self._lock = asyncio.Lock()
    
    @property
    def is_open(self) -> bool:
        """Check if circuit breaker is open (blocking calls)."""
        if self._state == "closed":
            return False
        
        if self._state == "open":
            # Check if recovery timeout has passed
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                return False  # Will transition to half-open
            return True
        
        # half-open: allow limited calls
        return self._half_open_calls >= self.half_open_max_calls
    
    async def record_success(self) -> None:
        """Record a successful action execution."""
        async with self._lock:
            if self._state == "half-open":
                self._half_open_calls += 1
                if self._half_open_calls >= self.half_open_max_calls:
                    self._state = "closed"
                    self._failure_count = 0
                    self._half_open_calls = 0
                    logger.info("Circuit breaker: recovered to closed state")
            elif self._state == "closed":
                self._failure_count = 0
    
    async def record_failure(self) -> None:
        """Record a failed action execution."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            
            if self._state == "half-open":
                self._state = "open"
                self._half_open_calls = 0
                logger.warning("Circuit breaker: half-open -> open (failure)")
            elif self._state == "closed" and self._failure_count >= self.failure_threshold:
                self._state = "open"
                logger.warning(f"Circuit breaker: closed -> open (failures: {self._failure_count})")
    
    def get_state(self) -> str:
        """Get current circuit breaker state."""
        return self._state


class MAPEOrchestrator:
    """
    MAPE-K (Monitor, Analyze, Plan, Execute) Orchestrator for Mesh self-healing.
    
    This is the core engine that maintains network stability.
    Enforces a 'fail-closed' policy: will not run with mock components in production.
    
    Features:
    - Real-time metric monitoring
    - Intelligent healing action planning
    - Circuit breaker to prevent cascading failures
    - DAO audit logging
    - IPFS state snapshots
    """
    
    # Default thresholds for healing decisions
    DEFAULT_THRESHOLDS = {
        "latency_p95_ms": 87,
        "packet_loss_percent": 1.6,
        "cpu_threshold_percent": 80,
        "memory_threshold_percent": 85,
        "error_rate_threshold_percent": 5,
    }

    def __init__(
        self, 
        prometheus_client: PrometheusClient, 
        mesh_client: MeshClient, 
        dao_client: DAOClient, 
        ipfs_client: IPFSClient,
        thresholds: Optional[Dict[str, float]] = None,
        enable_circuit_breaker: Optional[bool] = None
    ):
        self.prometheus = prometheus_client
        self.mesh = mesh_client
        self.dao = dao_client
        self.ipfs = ipfs_client
        self.node_id = os.getenv("NODE_ID", "local_node")
        
        # Lazy load GraphSAGE with fallback support
        global _graphsage_loader
        if _graphsage_loader is None:
            _graphsage_loader = _get_graphsage_loader()
        self.graphsage = _graphsage_loader()
        
        # Configuration
        self.thresholds = {**self.DEFAULT_THRESHOLDS, **(thresholds or {})}
        self._running = False
        self._state = SystemState()
        
        # Circuit breaker - enable by default, force in production
        is_production = os.getenv("ENVIRONMENT", "").lower() == "production"
        if enable_circuit_breaker is None:
            enable_circuit_breaker = True
        self._circuit_breaker = CircuitBreaker() if enable_circuit_breaker else None
        
        if is_production and not enable_circuit_breaker:
            logger.warning("⚠️ Circuit breaker disabled in production!")
        
        # Metrics tracking
        self._total_healing_actions = 0
        self._successful_healing_actions = 0
        self._total_mttr_seconds = 0.0  # Mean Time To Recovery
        
        # Security manager for node isolation/quarantine
        self._init_security_manager()
        
        # Security check: ensure we are not using mocks in production
        is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"
        if is_production:
            # Import here to avoid circular imports - Mock is from unittest
            from unittest.mock import Mock
            
            clients = [
                ("Prometheus", self.prometheus), 
                ("Mesh", self.mesh), 
                ("DAO", self.dao), 
                ("IPFS", self.ipfs)
            ]
            for name, client in clients:
                # More reliable check: use isinstance instead of name inspection
                if isinstance(client, Mock):
                    logger.critical(f"❌ SECURITY BREACH: {name} is using a MOCK implementation in production!")
                    raise RuntimeError(f"Fail-closed: {name} mock detected in production environment.")
                # Additional check: verify client has required async methods
                if not hasattr(client, 'query') and not hasattr(client, 'apply_routing') and not hasattr(client, 'log_event'):
                    logger.warning(f"⚠️ {name} client missing expected methods - may be a stub")

        logger.info("✅ MAPEOrchestrator initialized with verified clients.")

    def _init_security_manager(self) -> None:
        """Initialize security manager for node isolation/quarantine."""
        try:
            from src.security.auto_isolation import AutoIsolationManager
            # Support current and legacy AutoIsolationManager constructor signatures.
            try:
                self.security_manager = AutoIsolationManager(node_id=self.node_id)
            except TypeError:
                self.security_manager = AutoIsolationManager()
            logger.info("✅ Security manager initialized for MAPE-K")
        except ImportError as e:
            logger.warning(f"⚠️ Security manager not available: {e}")
            self.security_manager = None

    @property
    def is_healthy(self) -> bool:
        """Check if orchestrator is healthy."""
        return self._state.is_healthy
    
    @property
    def circuit_breaker_state(self) -> str:
        """Get circuit breaker state."""
        return self._circuit_breaker.get_state() if self._circuit_breaker else "disabled"

    async def monitor_cycle(self) -> Dict[str, Any]:
        """
        Slot-based sync каждые 3.14 сек. Собирает метрики из Prometheus.
        """
        logger.debug("Начало цикла мониторинга...")
        metrics = await self.prometheus.query(
            {
                "latency_p95": f"<{self.thresholds['latency_p95_ms']}ms",
                "packet_loss": f"<{self.thresholds['packet_loss_percent']}%",
                "pqc_handshake_success": ">99%",
                "cpu_usage": f"<{self.thresholds['cpu_threshold_percent']}%",
                "memory_usage": f"<{self.thresholds['memory_threshold_percent']}%",
            }
        )
        
        # Update internal state
        self._state.metrics = metrics
        self._state.last_update = time.time()
        
        # Check health
        self._state.is_healthy = await self._check_health(metrics)
        
        logger.debug(f"Метрики получены: {metrics}")
        return metrics

    async def _check_health(self, metrics: Dict[str, Any]) -> bool:
        """Determine if system is healthy based on metrics."""
        latency = metrics.get("latency_p95_value", 0)
        packet_loss = metrics.get("packet_loss_value", 0)
        cpu = metrics.get("cpu_usage_value", 0)
        memory = metrics.get("memory_usage_value", 0)
        
        # Check against thresholds
        unhealthy = (
            latency > self.thresholds["latency_p95_ms"] or
            packet_loss > self.thresholds["packet_loss_percent"] or
            cpu > self.thresholds["cpu_threshold_percent"] or
            memory > self.thresholds["memory_threshold_percent"]
        )
        
        return not unhealthy

    async def analyze_cycle(self, metrics: Dict[str, Any]) -> List[HealingAction]:
        """
        Analyze metrics using GraphSAGE V3 and determine healing action plan.
        Returns list of healing actions to execute.
        """
        logger.debug("Начало цикла анализа (GraphSAGE)...")
        actions: List[HealingAction] = []
        
        # Check circuit breaker
        if self._circuit_breaker and self._circuit_breaker.is_open:
            logger.warning("Circuit breaker is open - blocking healing actions")
            return []
        
        # Prepare features for GraphSAGE
        node_features = {
            "latency": metrics.get("latency_p95_value", 50.0),
            "loss_rate": metrics.get("packet_loss_value", 0.0) / 100.0,
            "cpu_percent": metrics.get("cpu_usage_value", 0.0),
            "memory_percent": metrics.get("memory_usage_value", 0.0),
        }
        
        # 1. Check for Subscription/Billing Soft-lock
        try:
            from src.database import SessionLocal, User, MeshInstance
            db = SessionLocal()
            mesh = db.query(MeshInstance).filter(MeshInstance.id == "local_mesh").first() # Example mesh ID
            if mesh:
                user = db.query(User).filter(User.id == mesh.owner_id).first()
                if user and user.plan == "overdue":
                    logger.warning(f"⚠️ User {user.id} is OVERDUE. Triggering DEGRADE_SERVICE.")
                    actions.append(HealingAction(
                        action_type=HealingActionType.DEGRADE_SERVICE,
                        target="bandwidth",
                        reason="Subscription expired (overdue)",
                        severity=AlertSeverity.CRITICAL,
                        estimated_impact=1.0
                    ))
            db.close()
        except Exception as e:
            logger.error(f"Failed to check billing status in MAPE-K: {e}")

        
        # Call GraphSAGE enhanced prediction
        try:
            # Skip ML prediction if GraphSAGE is not available (stub mode)
            if self.graphsage is None:
                logger.debug("GraphSAGE not available, using fallback analysis")
                return await self._analyze_cycle_fallback(metrics)
            
            # We mock neighbors as empty list for the current node itself
            # In a full mesh deployment, this would be fetched from discovery
            prediction = self.graphsage.predict_enhanced(
                node_id="local_node",
                node_features=node_features,
                neighbors=[],
                update_baseline=True
            )
            
            if prediction.get("is_anomaly"):
                logger.warning(f"🚨 GraphSAGE Anomaly: {prediction.get('explanation')}")
                
                # Determine action based on ML explanation/recommendations
                explanation = prediction.get("explanation", "").lower()
                severity = AlertSeverity.CRITICAL if prediction.get("confidence", 0) > 0.8 else AlertSeverity.WARNING
                
                if "latency" in explanation or "packet loss" in explanation:
                    actions.append(HealingAction(
                        action_type=HealingActionType.RE_ROUTE,
                        target="mesh-routing",
                        reason=f"ML Anomaly (Score {prediction['anomaly_score']:.2f}): {prediction['explanation']}",
                        severity=severity,
                        estimated_impact=prediction.get("confidence", 0.5)
                    ))
                elif "cpu" in explanation or "memory" in explanation:
                    actions.append(HealingAction(
                        action_type=HealingActionType.CLEAR_CACHE,
                        target="node-resources",
                        reason=f"Resource Anomaly: {prediction['explanation']}",
                        severity=severity,
                        estimated_impact=0.4
                    ))
                else:
                    actions.append(HealingAction(
                        action_type=HealingActionType.RESTART_SERVICE,
                        target="system-components",
                        reason=f"Generic Anomaly Detected: {prediction['explanation']}",
                        severity=severity,
                        estimated_impact=0.6
                    ))
                    
        except Exception as e:
            logger.error(f"GraphSAGE prediction failed: {e}")
            # Fallback to static thresholds if ML fails
            return await self._analyze_cycle_fallback(metrics)
        
        # Update state
        self._state.healing_actions = actions
        
        logger.debug(f"План анализа (ML): {len(actions)} actions")
        return actions

    async def _analyze_cycle_fallback(self, metrics: Dict[str, Any]) -> List[HealingAction]:
        """Fallback static threshold analysis if ML fails."""
        actions: List[HealingAction] = []
        latency = metrics.get("latency_p95_value", 0)
        packet_loss = metrics.get("packet_loss_value", 0)
        cpu = metrics.get("cpu_usage_value", 0)
        memory = metrics.get("memory_usage_value", 0)
        error_rate = metrics.get("error_rate_percent", 0)

        # High latency
        if latency > self.thresholds["latency_p95_ms"]:
            severity = AlertSeverity.CRITICAL if latency > self.thresholds["latency_p95_ms"] * 1.5 else AlertSeverity.WARNING
            actions.append(HealingAction(
                action_type=HealingActionType.RE_ROUTE,
                target="mesh-routing",
                reason=f"High latency detected: {latency}ms (threshold: {self.thresholds['latency_p95_ms']}ms)",
                severity=severity,
                estimated_impact=min(1.0, latency / 200)
            ))
        
        # Packet loss
        if packet_loss > self.thresholds["packet_loss_percent"]:
            severity = AlertSeverity.CRITICAL if packet_loss > self.thresholds["packet_loss_percent"] * 2 else AlertSeverity.WARNING
            actions.append(HealingAction(
                action_type=HealingActionType.RE_ROUTE,
                target="mesh-routing",
                reason=f"High packet loss detected: {packet_loss}% (threshold: {self.thresholds['packet_loss_percent']}%)",
                severity=severity,
                estimated_impact=min(1.0, packet_loss / 10)
            ))
        
        # High CPU
        if cpu > self.thresholds["cpu_threshold_percent"]:
            actions.append(HealingAction(
                action_type=HealingActionType.SCALE_UP,
                target="compute-nodes",
                reason=f"High CPU usage: {cpu}% (threshold: {self.thresholds['cpu_threshold_percent']}%)",
                severity=AlertSeverity.WARNING,
                estimated_impact=0.3
            ))
        
        # High Memory
        if memory > self.thresholds["memory_threshold_percent"]:
            actions.append(HealingAction(
                action_type=HealingActionType.CLEAR_CACHE,
                target="redis-cache",
                reason=f"High memory usage: {memory}% (threshold: {self.thresholds['memory_threshold_percent']}%)",
                severity=AlertSeverity.WARNING,
                estimated_impact=0.2
            ))
        
        # High error rate
        if error_rate > self.thresholds["error_rate_threshold_percent"]:
            actions.append(HealingAction(
                action_type=HealingActionType.FAILOVER,
                target="service-primary",
                reason=f"High error rate: {error_rate}% (threshold: {self.thresholds['error_rate_threshold_percent']}%)",
                severity=AlertSeverity.CRITICAL,
                estimated_impact=0.8
            ))
            
        return actions


    async def execute_cycle(self, actions: List[HealingAction]):
        """
        Execute healing actions with circuit breaker protection.
        """
        if not actions:
            logger.debug("No actions to execute")
            return
        
        start_time = time.time()
        
        for action in actions:
            logger.info(f"🚀 Выполнение: {action.action_type.value} on {action.target} - {action.reason}")
            
            try:
                await self._execute_action(action)
                
                # Record success
                if self._circuit_breaker:
                    await self._circuit_breaker.record_success()
                
                self._successful_healing_actions += 1
                
                # Log to DAO
                await self._log_action(action, success=True)
                
            except Exception as e:
                logger.error(f"❌ Action failed: {action.action_type.value} - {e}")
                
                # Record failure
                if self._circuit_breaker:
                    await self._circuit_breaker.record_failure()
                
                # Log to DAO
                await self._log_action(action, success=False, error=str(e))
        
        # Calculate MTTR
        duration = time.time() - start_time
        self._total_mttr_seconds = (
            (self._total_mttr_seconds * (self._total_healing_actions - 1) + duration)
            / max(self._total_healing_actions, 1)
        )
        self._total_healing_actions += 1
        
        logger.debug(f"Цикл выполнения завершен за {duration:.2f}s.")

    async def _execute_action(self, action: HealingAction) -> None:
        """Execute a single healing action."""
        if action.action_type == HealingActionType.RE_ROUTE:
            await self.mesh.apply_routing({
                "algorithm": action.params.get("algorithm", "k-disjoint-spf"),
                "reason": action.reason
            })
        elif action.action_type == HealingActionType.CLEAR_CACHE:
            # Implement cache clearing
            logger.info(f"Clearing cache on {action.target}")
        elif action.action_type == HealingActionType.SCALE_UP:
            # Implement scale up
            logger.info(f"Scaling up {action.target}")
        elif action.action_type == HealingActionType.SCALE_DOWN:
            # Implement scale down
            logger.info(f"Scaling down {action.target}")
        elif action.action_type == HealingActionType.FAILOVER:
            # Implement failover
            logger.info(f"Failing over {action.target}")
        elif action.action_type == HealingActionType.QUARANTINE_NODE:
            # Implement node quarantine
            logger.info(f"Quarantining node {action.target}")
        elif action.action_type == HealingActionType.SWITCH_PROTOCOL:
            # Implement protocol switch
            logger.info(f"Switching protocol on {action.target}")
        elif action.action_type == HealingActionType.RESTART_SERVICE:
            # Implement service restart
            logger.info(f"Restarting service {action.target}")
        elif action.action_type == HealingActionType.QUARANTINE_NODE:
            # Implementation of Zero-Trust Quarantine
            logger.warning(f"🚨 ISOLATING COMPROMISED NODE: {action.target}")
            if self.security_manager:
                from src.security.auto_isolation import IsolationReason
                self.security_manager.isolate(
                    node_id=action.target, 
                    reason=IsolationReason.ANOMALY_DETECTED,
                    details=action.reason
                )
                logger.info(f"✅ Node {action.target} placed in XDP quarantine.")
            else:
                logger.error("Security manager not available for quarantine action.")
        elif action.action_type == HealingActionType.DEGRADE_SERVICE:

            # Implementation of Soft-lock via eBPF Rate Limiter (or Software Fallback)
            logger.warning(f"🚨 Applying Soft-lock (DEGRADE_SERVICE) on {action.target}")
            try:
                from src.network.ebpf.rate_limiter_manager import RateLimiterManager
                limiter = RateLimiterManager()
                limiter.apply_soft_lock()
                mode = "eBPF" if not limiter.is_using_software_fallback else "software"
                logger.info(f"✅ Rate limiting applied successfully via {mode}")
            except Exception as e:
                logger.error(f"⚠️ Failed to apply rate limiting (using fallback): {e}")
                # Soft-lock is best-effort - don't block healing flow
                # The system will still work, just without rate limiting


    async def _log_action(self, action: HealingAction, success: bool, error: str = None) -> None:
        """Log action to DAO for audit."""
        event_data = {
            "type": "healing_action",
            "action": action.action_type.value,
            "target": action.target,
            "reason": action.reason,
            "severity": action.severity.value,
            "success": success,
            "error": error,
            "timestamp": action.timestamp,
            "circuit_breaker_state": self.circuit_breaker_state
        }
        
        try:
            await self.dao.log_event("healing_action", event_data)
        except Exception as e:
            logger.error(f"Failed to log action to DAO: {e}")

    async def mape_k_loop(self, interval_seconds: float = 3.14):
        """
        Основной цикл MAPE-K.
        """
        logger.info(f"♻️ Запуск основного цикла MAPE-K (интервал: {interval_seconds}с)")
        self._running = True
        
        while self._running:
            try:
                metrics = await self.monitor_cycle()
                actions = await self.analyze_cycle(metrics)
                if actions:
                    await self.execute_cycle(actions)
                    
                    # Snapshot to IPFS after healing
                    await self._snapshot_state()
                    
            except Exception as e:
                logger.error(f"❌ Ошибка в цикле MAPE-K: {e}")
            
            await asyncio.sleep(interval_seconds)

    async def _snapshot_state(self) -> None:
        """Snapshot current state to IPFS."""
        try:
            snapshot_data = {
                "timestamp": time.time(),
                "state": {
                    "metrics": self._state.metrics,
                    "healing_actions_count": len(self._state.healing_actions),
                    "is_healthy": self._state.is_healthy
                },
                "circuit_breaker": self.circuit_breaker_state
            }
            await self.ipfs.snapshot(f"mape-state-{time.strftime('%Y%m%d%H%M%S')}")
            logger.debug("State snapshot saved to IPFS")
        except Exception as e:
            logger.error(f"Failed to snapshot state: {e}")

    async def stop(self) -> None:
        """Graceful shutdown of MAPE-K orchestrator."""
        logger.info("🛑 Остановка MAPE-K orchestrator...")
        self._running = False
        
        # Final snapshot
        await self._snapshot_state()
        
        logger.info("✅ MAPE-K orchestrator остановлен")

    def get_metrics(self) -> Dict[str, Any]:
        """Get orchestrator metrics."""
        return {
            "total_healing_actions": self._total_healing_actions,
            "successful_healing_actions": self._successful_healing_actions,
            "success_rate": (
                self._successful_healing_actions / max(self._total_healing_actions, 1)
            ),
            "avg_mttr_seconds": self._total_mttr_seconds,
            "circuit_breaker_state": self.circuit_breaker_state,
            "is_healthy": self._state.is_healthy,
            "last_update": self._state.last_update
        }
