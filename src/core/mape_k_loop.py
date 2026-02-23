# src/core/mape_k_loop.py
import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List

from ..dao.ipfs_logger import DAOAuditLogger
from ..mesh.network_manager import MeshNetworkManager
from ..monitoring.prometheus_client import PrometheusExporter
from ..security.zero_trust import ZeroTrustValidator
from .consciousness import ConsciousnessEngine, ConsciousnessMetrics

# Configure logging
logging.basicConfig(level=logging.INFO)

# Optional imports with graceful fallback
try:
    from src.monitoring.opentelemetry_tracing import get_mapek_spans
except ImportError:
    get_mapek_spans = None

try:
    from src.database import SessionLocal, MeshNode
    DATABASE_AVAILABLE = True
except ImportError:
    SessionLocal = None
    MeshNode = None
    DATABASE_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class MAPEKState:
    """State container for MAPE-K loop"""

    metrics: ConsciousnessMetrics
    directives: Dict[str, Any]
    actions_taken: List[str]
    timestamp: float


class MAPEKLoop:
    """
    Implements the Monitor-Analyze-Plan-Execute-Knowledge loop
    integrated with Consciousness Engine.

    Philosophy: The system continuously observes itself (Monitor),
    evaluates its harmony state (Analyze), decides on actions (Plan),
    executes self-healing (Execute), and learns from experience (Knowledge).
    """

    def __init__(
        self,
        consciousness_engine: ConsciousnessEngine,
        mesh_manager: MeshNetworkManager,
        prometheus: PrometheusExporter,
        zero_trust: ZeroTrustValidator,
        dao_logger: DAOAuditLogger = None,
        action_dispatcher=None,
        parl_controller=None,
        fl_integration=None,
    ):
        self.consciousness = consciousness_engine
        self.mesh = mesh_manager
        self.prometheus = prometheus
        self.zero_trust = zero_trust
        self.dao_logger = dao_logger
        self.action_dispatcher = action_dispatcher
        self.parl_controller = parl_controller  # Swarm Integration
        self.fl_integration = fl_integration  # FL integration compatibility

        self.running = False
        self.loop_interval = 60  # Dynamic, adjusted by consciousness state
        self.state_history: List[MAPEKState] = []

        # Thought Generation Control
        self.cycle_count = 0
        self.thought_frequency = 10  # Generate thought every 10 cycles (~10 mins)

    async def start(self, fl_integration: bool = False):
        """Start the autonomic loop."""
        self.running = True
        logger.info("🌀 MAPEKLoop started")

        if fl_integration and self.fl_integration:
            logger.info("🧠 Federated Learning integration active in MAPE-K")

        while self.running:
            try:
                await self._execute_cycle()
                await asyncio.sleep(self.loop_interval)
            except Exception as e:
                logger.error(f"MAPE-K cycle error: {e}", exc_info=True)
                await asyncio.sleep(10)  # Brief pause before retry

    async def stop(self):
        """Stop the MAPE-K loop"""
        self.running = False
        logger.info("MAPE-K loop stopped")

    async def _execute_cycle(self):
        """Execute one complete MAPE-K cycle with tracing."""
        cycle_start = time.time()
        mapek_spans = get_mapek_spans() if get_mapek_spans is not None else None
        node_id = "local-node" # Fallback if mesh manager not ready

        # ===== MONITOR =====
        if mapek_spans:
            with mapek_spans.monitor_phase(node_id):
                raw_metrics = await self._monitor()
        else:
            raw_metrics = await self._monitor()

        # ===== ANALYZE =====
        if mapek_spans:
            with mapek_spans.analyze_phase(node_id):
                consciousness_metrics = await self._analyze(raw_metrics)
        else:
            consciousness_metrics = await self._analyze(raw_metrics)

        # ===== PLAN =====
        if mapek_spans:
            with mapek_spans.plan_phase(node_id):
                directives = self._plan(consciousness_metrics)
        else:
            directives = self._plan(consciousness_metrics)

        # ===== EXECUTE =====
        if mapek_spans:
            with mapek_spans.execute_phase(node_id):
                actions_taken = await self._execute(directives)
        else:
            actions_taken = await self._execute(directives)

        # ===== KNOWLEDGE =====
        if mapek_spans:
            with mapek_spans.knowledge_phase(node_id):
                await self._knowledge(
                    consciousness_metrics, directives, actions_taken, raw_metrics
                )
        else:
            await self._knowledge(
                consciousness_metrics, directives, actions_taken, raw_metrics
            )

        cycle_duration = time.time() - cycle_start
        self.cycle_count += 1

        log_msg = (
            f"φ-cycle {self.cycle_count} complete: {consciousness_metrics.state.value} "
            f"(φ={consciousness_metrics.phi_ratio:.3f}, "
            f"duration={cycle_duration:.2f}s)"
        )
        logger.info(log_msg)

        # Automated Thought Generation (Optimization: Run infrequently)
        if self.cycle_count % self.thought_frequency == 0:
            try:
                # Use a specific logger for thoughts to separate them
                thought = self.consciousness.get_system_thought(consciousness_metrics)
                logger.info(f"🧠 SYSTEM THOUGHT: {thought}")
            except Exception as e:
                logger.warning(f"Failed to generate system thought: {e}")

        # Adjust loop interval based on consciousness state
        self.loop_interval = directives.get("monitoring_interval_sec", 60)

    async def _monitor(self) -> Dict[str, float]:
        """
        MONITOR phase: Collect system metrics and sync with DAO
        """
        metrics = {}

        # 0. Sync with DAO Governance
        if DATABASE_AVAILABLE and SessionLocal is not None:
            try:
                from src.services.dao_enforcement import dao_enforcer
                with SessionLocal() as db:
                    dao_enforcer.sync_config_with_dao(db)
            except Exception as e:
                logger.debug(f"DAO sync failed: {e}")

        # System resources
        try:
            import psutil

            metrics["cpu_percent"] = psutil.cpu_percent(interval=0.1)
            metrics["memory_percent"] = psutil.virtual_memory().percent
        except ImportError:
            metrics["cpu_percent"] = 50.0
            metrics["memory_percent"] = 50.0

        # Mesh network metrics
        mesh_stats = await self.mesh.get_statistics()
        metrics["mesh_connectivity"] = mesh_stats.get("active_peers", 0)
        metrics["latency_ms"] = mesh_stats.get("avg_latency_ms", 100)
        metrics["packet_loss"] = mesh_stats.get("packet_loss_percent", 0)
        metrics["mttr_minutes"] = mesh_stats.get("mttr_minutes", 5.0)

        # Security metrics
        zt_stats = self.zero_trust.get_validation_stats()
        metrics["zero_trust_success_rate"] = zt_stats.get("success_rate", 0.95)

        # DB Metrics: Offline nodes & Premium (rented) nodes
        if DATABASE_AVAILABLE and SessionLocal is not None:
            try:
                with SessionLocal() as db:
                    metrics["offline_nodes"] = db.query(MeshNode).filter(
                        MeshNode.status == "offline"
                    ).count()
                    
                    # Trust Engine Integration
                    from src.security.trust_engine import TrustEvaluator
                    trust_eval = TrustEvaluator(db)
                    
                    # Check all online nodes for trust issues
                    online_nodes = db.query(MeshNode).filter(MeshNode.status != "offline").all()
                    low_trust_count = 0
                    for node in online_nodes:
                        score = trust_eval.calculate_node_trust(node.id)
                        if score < 0.6:
                            low_trust_count += 1
                            logger.warning(f"🛡️ Node {node.id} has LOW TRUST ({score:.2f}). Planning re-attestation.")
                    
                    metrics["low_trust_nodes"] = float(low_trust_count)
                    
                    # Premium nodes count (rented in Marketplace)
                    from src.database import MarketplaceListing
                    premium_nodes = db.query(MarketplaceListing).filter(
                        MarketplaceListing.status == "rented"
                    ).all()
                    metrics["premium_nodes_online"] = sum(1 for n in premium_nodes if n.status == "rented")
                    
                    # If any premium node is offline, set high priority alert
                    for p_node in premium_nodes:
                        node_record = db.query(MeshNode).filter(MeshNode.id == p_node.node_id).first()
                        if node_record and node_record.status == "offline":
                            metrics["premium_node_failure"] = 1.0
                            logger.critical(f"🚨 Premium node {p_node.node_id} is OFFLINE! SLA breach imminent.")
            except Exception as e:
                logger.warning(f"Failed to query premium nodes: {e}")
                metrics["offline_nodes"] = 0
        else:
            metrics["offline_nodes"] = 0

        return metrics

    async def _analyze(self, raw_metrics: Dict[str, float]) -> ConsciousnessMetrics:
        """
        ANALYZE phase: Evaluate consciousness state using Swarm Intelligence & ML
        """
        swarm_risk_penalty = 0.0
        ml_anomaly_risk = 0.0

        # 1. Neural Anomaly Detection
        try:
            from src.ml.anomaly import AnomalyDetectionSystem
            import numpy as np
            detector_system = AnomalyDetectionSystem()
            # Vectorize metrics
            metric_vector = np.array([v for v in raw_metrics.values() if isinstance(v, (int, float))])
            anomaly, confidence = await detector_system.check_component("mesh_core", metric_vector)
            if anomaly:
                ml_anomaly_risk = confidence
                logger.warning(f"🧠 ML: Anomaly detected with confidence {confidence:.2f}")
        except Exception as e:
            logger.debug(f"ML analysis failed: {e}")

        # 2. Swarm Intelligence Analysis
        if self.parl_controller:
            try:
                # Define analysis tasks
                tasks = [
                    {
                        "task_id": "analyze_security_logs",
                        "task_type": "security_analysis",
                        "priority": 10,
                        "payload": {"metrics": raw_metrics},
                    },
                    {
                        "task_id": "analyze_performance_trends",
                        "task_type": "performance_analysis",
                        "priority": 5,
                        "payload": {"metrics": raw_metrics},
                    },
                    {
                        "task_id": "predict_resource_usage",
                        "task_type": "oracle_prediction",
                        "priority": 5,
                        "payload": {"metrics": raw_metrics},
                    },
                ]

                # Execute in parallel
                results = await self.parl_controller.execute_parallel(tasks)

                # Aggregate risks
                for res in results:
                    if not res.get("success"):
                        continue

                    inner = res.get("result", {})
                    risk = inner.get("risk_score", 0.0)
                    if risk > 0:
                        swarm_risk_penalty = max(swarm_risk_penalty, risk)

                if swarm_risk_penalty > 0:
                    logger.info(
                        f"🐝 Swarm detection: Risk penalty {swarm_risk_penalty:.2f} applied"
                    )

            except Exception as e:
                logger.error(f"Swarm analysis failed: {e}")

        return self.consciousness.get_consciousness_metrics(
            raw_metrics, swarm_risk_penalty=swarm_risk_penalty
        )

    def _plan(self, metrics: ConsciousnessMetrics) -> Dict[str, Any]:
        """
        PLAN phase: Generate operational directives
        """
        directives = self.consciousness.get_operational_directive(metrics)

        raw = getattr(metrics, "raw_metrics", {}) or {}

        # SLA Policy: If premium nodes are failing, override to AGGRESSIVE HEALING
        if raw.get("premium_node_failure", 0.0) > 0:
            directives["enable_aggressive_healing"] = True
            directives["message"] = "🚨 Emergency: Premium node failure detected. Overriding to AGGRESSIVE HEALING."
            logger.info("⚖️ Plan: SLA Policy override triggered (Aggressive Healing enabled)")

        # Trust Policy: If low trust nodes detected, trigger re-attestation
        if raw.get("low_trust_nodes", 0.0) > 0:
            directives["audit_required"] = True
            logger.info("🛡️ Plan: Low trust nodes detected. Scheduling mandatory re-attestation.")

        # Add trend analysis for proactive planning
        trend = self.consciousness.get_trend_analysis()
        directives["trend"] = trend

        # If degrading trend in CONTEMPLATIVE state, prepare for MYSTICAL
        if metrics.state.value == "CONTEMPLATIVE" and trend.get("trend") == "degrading":
            directives["preemptive_healing"] = True
            logger.warning("⚠️  Degrading trend detected, preparing preemptive healing")

        return directives

    async def _execute(self, directives: Dict[str, Any]) -> List[str]:
        """
        EXECUTE phase: Take action based on directives
        """
        actions = []

        # Route preference adjustment
        route_pref = directives.get("route_preference", "balanced")
        if await self.mesh.set_route_preference(route_pref):
            actions.append(f"route_preference={route_pref}")

        # Mesh Optimization Enforcement
        try:
            from src.mesh.yggdrasil_optimizer import get_optimizer
            from src.mesh.action_enforcer import mesh_action_enforcer
            report = get_optimizer().optimize_routes()
            if report.get("recommendations"):
                mesh_action_enforcer.enforce_recommendations(report["recommendations"])
                actions.append(f"mesh_optimization={len(report['recommendations'])}_actions")
        except Exception as e:
            logger.debug(f"Mesh optimization enforcement failed: {e}")

        # Aggressive healing if needed
        if directives.get("enable_aggressive_healing", False):
            healed = await self.mesh.trigger_aggressive_healing()
            actions.append(f"aggressive_healing={healed}_nodes")

        # Preemptive healing
        if directives.get("preemptive_healing", False):
            await self.mesh.trigger_preemptive_checks()
            actions.append("preemptive_healing_initiated")

        # Scaling actions
        scaling = directives.get("scaling_action", "none")
        if scaling != "none":
            await self._handle_scaling(scaling)
            actions.append(f"scaling={scaling}")

        # DAO governance actions (dispatched via ActionDispatcher)
        dao_actions = directives.get("dao_actions", [])
        if dao_actions and self.action_dispatcher is not None:
            for dao_action in dao_actions:
                result = self.action_dispatcher.dispatch(dao_action)
                status = "OK" if result.success else "FAIL"
                actions.append(f"dao:{result.action_type}={status}")
                if not result.success:
                    logger.warning(
                        f"DAO action failed: {result.action_type} — {result.detail}"
                    )

        return actions

    async def _knowledge(
        self,
        metrics: ConsciousnessMetrics,
        directives: Dict[str, Any],
        actions: List[str],
        raw_metrics: Dict[str, float] = None,
    ):  # Added raw_metrics
        """
        KNOWLEDGE phase: Store learnings and update models
        """
        # Export Consciousness metrics to Prometheus
        prom_metrics = metrics.to_prometheus_format()
        for metric_name, value in prom_metrics.items():
            self.prometheus.set_gauge(metric_name, value)

        # Export Raw metrics to Prometheus for observability
        if raw_metrics:
            for metric_name, value in raw_metrics.items():
                # Prefix to avoid collision if needed, or just mapped directly
                # Using mapped names for clarity
                # mapped_name = f"mesh_{metric_name}" if metric_name not in ['mesh_connectivity', 'mesh_latency_ms'] else metric_name

                # Custom mapping for specific keys if needed
                if metric_name == "latency_ms":
                    self.prometheus.set_gauge("mesh_latency_ms", value)
                elif metric_name == "cpu_percent":
                    self.prometheus.set_gauge("system_cpu_percent", value)
                elif metric_name == "memory_percent":
                    self.prometheus.set_gauge("system_memory_percent", value)
                elif metric_name == "packet_loss":
                    self.prometheus.set_gauge("mesh_packet_loss_percent", value)
                else:
                    self.prometheus.set_gauge(metric_name, value)

        # Store state for historical analysis
        state = MAPEKState(
            metrics=metrics,
            directives=directives,
            actions_taken=actions,
            timestamp=time.time(),
        )
        self.state_history.append(state)

        # Trim history to prevent memory bloat (keep last 10,000 states)
        if len(self.state_history) > 10000:
            self.state_history = self.state_history[-10000:]

        # Log message from consciousness
        message = directives.get("message", "")
        if message:
            logger.info(f"💭 Consciousness: {message}")

        # Trigger DAO logging for critical events
        if metrics.state.value in ["EUPHORIC", "MYSTICAL"]:
            await self._log_to_dao(state)

    async def _handle_scaling(self, action: str):
        """Handle scaling actions"""
        if action == "optimize":
            # Scale down idle resources
            logger.info("🔧 Optimizing resource allocation")
        elif action == "emergency_scale":
            # Emergency scale-up
            logger.critical("🚨 Emergency scaling initiated")

    async def _log_to_dao(self, state: MAPEKState):
        """Log significant events to DAO audit trail"""
        if self.dao_logger:
            event_data = {
                "state": state.metrics.state.value,
                "phi_ratio": state.metrics.phi_ratio,
                "directives": state.directives,
                "actions_taken": state.actions_taken,
                "timestamp": state.timestamp,
            }
            try:
                cid = await self.dao_logger.log_consciousness_event(event_data)
                logger.info(f"📜 DAO audit logged: {cid}")
            except Exception as e:
                logger.error(f"Failed to log to DAO: {e}")
        else:
            logger.info(
                f"📜 DAO audit (simulation): {state.metrics.state.value} state recorded"
            )
