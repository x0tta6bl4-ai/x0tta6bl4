# src/core/mape_k_loop.py
import asyncio
import time
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from .consciousness import ConsciousnessEngine, ConsciousnessMetrics
from ..monitoring.prometheus_client import PrometheusExporter
from ..mesh.network_manager import MeshNetworkManager
from ..security.zero_trust import ZeroTrustValidator
from ..dao.ipfs_logger import DAOAuditLogger

@dataclass
class MAPEKState:
    """State container for MAPE-K loop"""
    metrics: ConsciousnessMetrics
    directives: Dict[str, any]
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
    
    def __init__(self,
                 consciousness_engine: ConsciousnessEngine,
                 mesh_manager: MeshNetworkManager,
                 prometheus: PrometheusExporter,
                 zero_trust: ZeroTrustValidator,
                 dao_logger: DAOAuditLogger = None): # Added dao_logger with default None for backward compatibility
        self.consciousness = consciousness_engine
        self.mesh = mesh_manager
        self.prometheus = prometheus
        self.zero_trust = zero_trust
        self.dao_logger = dao_logger
        
        self.running = False
        self.loop_interval = 60  # Dynamic, adjusted by consciousness state
        self.state_history: List[MAPEKState] = []
        
    async def start(self):
        """Start the MAPE-K loop"""
        self.running = True
        logger.info("🌀 MAPE-K loop started with Consciousness integration")
        
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
        """Execute one complete MAPE-K cycle"""
        cycle_start = time.time()
        
        # ===== MONITOR =====
        raw_metrics = await self._monitor()
        
        # ===== ANALYZE =====
        consciousness_metrics = self._analyze(raw_metrics)
        
        # ===== PLAN =====
        directives = self._plan(consciousness_metrics)
        
        # ===== EXECUTE =====
        actions_taken = await self._execute(directives)
        
        # ===== KNOWLEDGE =====
        await self._knowledge(consciousness_metrics, directives, actions_taken, raw_metrics)
        
        cycle_duration = time.time() - cycle_start
        logger.info(
            f"φ-cycle complete: {consciousness_metrics.state.value} "
            f"(φ={consciousness_metrics.phi_ratio:.3f}, "
            f"duration={cycle_duration:.2f}s)"
        )
        
        # Adjust loop interval based on consciousness state
        self.loop_interval = directives.get('monitoring_interval_sec', 60)
    
    async def _monitor(self) -> Dict[str, float]:
        """
        MONITOR phase: Collect system metrics
        """
        metrics = {}
        
        # System resources
        try:
            import psutil
            metrics['cpu_percent'] = psutil.cpu_percent(interval=0.1)
            metrics['memory_percent'] = psutil.virtual_memory().percent
        except ImportError:
            metrics['cpu_percent'] = 50.0
            metrics['memory_percent'] = 50.0
        
        # Mesh network metrics
        mesh_stats = await self.mesh.get_statistics()
        metrics['mesh_connectivity'] = mesh_stats.get('active_peers', 0)
        metrics['latency_ms'] = mesh_stats.get('avg_latency_ms', 100)
        metrics['packet_loss'] = mesh_stats.get('packet_loss_percent', 0)
        metrics['mttr_minutes'] = mesh_stats.get('mttr_minutes', 5.0)
        
        # Security metrics
        zt_stats = self.zero_trust.get_validation_stats()
        metrics['zero_trust_success_rate'] = zt_stats.get('success_rate', 0.95)
        
        return metrics
    
    def _analyze(self, raw_metrics: Dict[str, float]) -> ConsciousnessMetrics:
        """
        ANALYZE phase: Evaluate consciousness state
        """
        return self.consciousness.get_consciousness_metrics(raw_metrics)
    
    def _plan(self, metrics: ConsciousnessMetrics) -> Dict[str, any]:
        """
        PLAN phase: Generate operational directives
        """
        directives = self.consciousness.get_operational_directive(metrics)
        
        # Add trend analysis for proactive planning
        trend = self.consciousness.get_trend_analysis()
        directives['trend'] = trend
        
        # If degrading trend in CONTEMPLATIVE state, prepare for MYSTICAL
        if (metrics.state.value == 'CONTEMPLATIVE' and 
            trend.get('trend') == 'degrading'):
            directives['preemptive_healing'] = True
            logger.warning("⚠️  Degrading trend detected, preparing preemptive healing")
        
        return directives
    
    async def _execute(self, directives: Dict[str, any]) -> List[str]:
        """
        EXECUTE phase: Take action based on directives
        """
        actions = []
        
        # Route preference adjustment
        route_pref = directives.get('route_preference', 'balanced')
        if await self.mesh.set_route_preference(route_pref):
            actions.append(f"route_preference={route_pref}")
        
        # Aggressive healing if needed
        if directives.get('enable_aggressive_healing', False):
            healed = await self.mesh.trigger_aggressive_healing()
            actions.append(f"aggressive_healing={healed}_nodes")
        
        # Preemptive healing
        if directives.get('preemptive_healing', False):
            await self.mesh.trigger_preemptive_checks()
            actions.append("preemptive_healing_initiated")
        
        # Scaling actions
        scaling = directives.get('scaling_action', 'none')
        if scaling != 'none':
            await self._handle_scaling(scaling)
            actions.append(f"scaling={scaling}")
        
        return actions
    
    async def _knowledge(self, 
                        metrics: ConsciousnessMetrics,
                        directives: Dict[str, any],
                        actions: List[str],
                        raw_metrics: Dict[str, float] = None): # Added raw_metrics
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
                mapped_name = f"mesh_{metric_name}" if metric_name not in ['mesh_connectivity', 'mesh_latency_ms'] else metric_name
                
                # Custom mapping for specific keys if needed
                if metric_name == 'latency_ms':
                    self.prometheus.set_gauge('mesh_latency_ms', value)
                elif metric_name == 'cpu_percent':
                    self.prometheus.set_gauge('system_cpu_percent', value)
                elif metric_name == 'memory_percent':
                    self.prometheus.set_gauge('system_memory_percent', value)
                elif metric_name == 'packet_loss':
                    self.prometheus.set_gauge('mesh_packet_loss_percent', value)
                else:
                    self.prometheus.set_gauge(metric_name, value)
        
        # Store state for historical analysis
        state = MAPEKState(
            metrics=metrics,
            directives=directives,
            actions_taken=actions,
            timestamp=time.time()
        )
        self.state_history.append(state)
        
        # Trim history to prevent memory bloat (keep last 10,000 states)
        if len(self.state_history) > 10000:
            self.state_history = self.state_history[-10000:]
        
        # Log message from consciousness
        message = directives.get('message', '')
        if message:
            logger.info(f"💭 Consciousness: {message}")
        
        # Trigger DAO logging for critical events
        if metrics.state.value in ['EUPHORIC', 'MYSTICAL']:
            await self._log_to_dao(state)
    
    async def _handle_scaling(self, action: str):
        """Handle scaling actions"""
        if action == 'optimize':
            # Scale down idle resources
            logger.info("🔧 Optimizing resource allocation")
        elif action == 'emergency_scale':
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
                "timestamp": state.timestamp
            }
            try:
                cid = await self.dao_logger.log_consciousness_event(event_data)
                logger.info(f"📜 DAO audit logged: {cid}")
            except Exception as e:
                logger.error(f"Failed to log to DAO: {e}")
        else:
            logger.info(f"📜 DAO audit (simulation): {state.metrics.state.value} state recorded")
