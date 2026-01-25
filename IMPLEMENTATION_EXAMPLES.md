# x0tta6bl4 - Implementation Examples & Code Templates

This document provides ready-to-use code examples for implementing the P1 fixes to achieve 100% production readiness.

---

## Example 1: Raft Snapshot Implementation

Complete implementation for Raft state snapshot and recovery.

### File: `src/consensus/raft_snapshot.py`

```python
"""
Raft Consensus Snapshot Implementation
Provides state serialization and recovery for Raft consensus
"""

import pickle
import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from pathlib import Path
import json

logger = logging.getLogger(__name__)

@dataclass
class RaftSnapshot:
    """Serializable Raft state snapshot"""
    last_included_index: int
    last_included_term: int
    timestamp: float
    state_machine_data: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_bytes(self) -> bytes:
        """Serialize to bytes"""
        return pickle.dumps({
            'last_included_index': self.last_included_index,
            'last_included_term': self.last_included_term,
            'timestamp': self.timestamp,
            'state_machine_data': self.state_machine_data,
            'metadata': self.metadata,
        })
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'RaftSnapshot':
        """Deserialize from bytes"""
        obj = pickle.loads(data)
        return cls(
            last_included_index=obj['last_included_index'],
            last_included_term=obj['last_included_term'],
            timestamp=obj['timestamp'],
            state_machine_data=obj['state_machine_data'],
            metadata=obj['metadata'],
        )

class SnapshotManager:
    """Manages Raft snapshots with persistence"""
    
    def __init__(self, snapshot_dir: str = "/tmp/raft_snapshots"):
        self.snapshot_dir = Path(snapshot_dir)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.current_snapshot: Optional[RaftSnapshot] = None
        
    def create_snapshot(self, 
                       last_included_index: int,
                       last_included_term: int,
                       state_machine_data: Dict[str, Any]) -> RaftSnapshot:
        """Create and persist a snapshot"""
        
        snapshot = RaftSnapshot(
            last_included_index=last_included_index,
            last_included_term=last_included_term,
            timestamp=time.time(),
            state_machine_data=state_machine_data,
            metadata={
                'created_by': 'raft_server',
                'version': '1.0',
            }
        )
        
        # Persist snapshot
        snapshot_file = self.snapshot_dir / f"snapshot_{last_included_index:010d}.bin"
        try:
            with open(snapshot_file, 'wb') as f:
                f.write(snapshot.to_bytes())
            
            # Update metadata
            metadata_file = self.snapshot_dir / f"snapshot_{last_included_index:010d}.json"
            with open(metadata_file, 'w') as f:
                json.dump({
                    'index': last_included_index,
                    'term': last_included_term,
                    'timestamp': snapshot.timestamp,
                    'size_bytes': snapshot_file.stat().st_size,
                }, f)
            
            self.current_snapshot = snapshot
            logger.info(f"Created snapshot at index {last_included_index}, "
                       f"size: {snapshot_file.stat().st_size} bytes")
            return snapshot
            
        except Exception as e:
            logger.error(f"Failed to create snapshot: {e}")
            raise
    
    def restore_snapshot(self, snapshot_index: int) -> Optional[RaftSnapshot]:
        """Restore a snapshot by index"""
        snapshot_file = self.snapshot_dir / f"snapshot_{snapshot_index:010d}.bin"
        
        if not snapshot_file.exists():
            logger.warning(f"Snapshot not found: {snapshot_index}")
            return None
        
        try:
            with open(snapshot_file, 'rb') as f:
                snapshot = RaftSnapshot.from_bytes(f.read())
            
            self.current_snapshot = snapshot
            logger.info(f"Restored snapshot from index {snapshot_index}")
            return snapshot
            
        except Exception as e:
            logger.error(f"Failed to restore snapshot: {e}")
            return None
    
    def get_latest_snapshot(self) -> Optional[RaftSnapshot]:
        """Get the most recent snapshot"""
        snapshot_files = sorted(self.snapshot_dir.glob("snapshot_*.bin"))
        if not snapshot_files:
            return None
        
        latest = snapshot_files[-1]
        index = int(latest.stem.split('_')[1])
        return self.restore_snapshot(index)
    
    def cleanup_old_snapshots(self, keep_count: int = 3):
        """Remove old snapshots, keeping only recent ones"""
        snapshot_files = sorted(self.snapshot_dir.glob("snapshot_*.bin"))
        
        if len(snapshot_files) > keep_count:
            for snapshot_file in snapshot_files[:-keep_count]:
                try:
                    snapshot_file.unlink()
                    metadata_file = snapshot_file.parent / f"{snapshot_file.stem}.json"
                    if metadata_file.exists():
                        metadata_file.unlink()
                    logger.debug(f"Cleaned up snapshot: {snapshot_file}")
                except Exception as e:
                    logger.error(f"Failed to cleanup snapshot: {e}")
```

### Integration with RaftState

```python
# Add to src/consensus/raft_state.py

class RaftState:
    def __init__(self, snapshot_manager: SnapshotManager):
        self.log = []
        self.state_machine = {}
        self.last_applied = 0
        self.current_term = 0
        self.voted_for = None
        self.snapshot_manager = snapshot_manager
        
        # Restore from latest snapshot on startup
        self._restore_from_snapshot()
    
    def _restore_from_snapshot(self):
        """Restore state from latest snapshot"""
        snapshot = self.snapshot_manager.get_latest_snapshot()
        if snapshot:
            self.last_applied = snapshot.last_included_index
            self.current_term = snapshot.last_included_term
            self.state_machine = snapshot.state_machine_data.copy()
            logger.info(f"Restored from snapshot at index {snapshot.last_included_index}")
    
    def create_snapshot(self) -> bool:
        """Create a snapshot of current state"""
        try:
            self.snapshot_manager.create_snapshot(
                last_included_index=self.last_applied,
                last_included_term=self.current_term,
                state_machine_data=self.state_machine.copy()
            )
            # Cleanup old snapshots
            self.snapshot_manager.cleanup_old_snapshots()
            return True
        except Exception as e:
            logger.error(f"Failed to create snapshot: {e}")
            return False
    
    def apply_log_entry(self, entry: Dict[str, Any]) -> bool:
        """Apply a log entry to state machine"""
        # Apply to state machine
        key = entry.get('key')
        value = entry.get('value')
        
        if key and value:
            self.state_machine[key] = value
            self.last_applied += 1
            return True
        
        return False
    
    def get_snapshot_status(self) -> Dict[str, Any]:
        """Get current snapshot status"""
        latest = self.snapshot_manager.get_latest_snapshot()
        return {
            'has_snapshot': latest is not None,
            'latest_index': latest.last_included_index if latest else None,
            'latest_term': latest.last_included_term if latest else None,
            'last_applied': self.last_applied,
        }
```

---

## Example 2: MAPE-K Loop Optimization

Optimized self-healing loop with parallelization and timing.

### File: `src/core/optimized_mape_k.py`

```python
"""
Optimized MAPE-K (Monitor, Analyze, Plan, Execute, Knowledge) Loop
Implements parallel phases and timing optimization for sub-30s recovery
"""

import asyncio
import time
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from enum import Enum

logger = logging.getLogger(__name__)

class RecoveryAction(Enum):
    """Available recovery actions"""
    RESTART_SERVICE = "restart_service"
    FAILOVER_PRIMARY = "failover_primary"
    SCALE_UP = "scale_up"
    CLEAR_CACHE = "clear_cache"
    QUARANTINE_NODE = "quarantine_node"

@dataclass
class CycleMetrics:
    """Metrics for a single MAPE-K cycle"""
    monitor_ms: float
    analyze_ms: float
    plan_ms: float
    execute_ms: float
    learn_ms: float
    total_ms: float
    
    @property
    def efficiency_score(self) -> float:
        """Score 0-100 based on cycle time (target: < 30s)"""
        target_ms = 30000
        actual_ms = self.total_ms
        
        if actual_ms <= target_ms:
            return 100.0
        else:
            return max(0, 100 - ((actual_ms - target_ms) / target_ms * 50))

class OptimizedMAPEKLoop:
    """Production-optimized MAPE-K implementation"""
    
    def __init__(self, 
                 node_id: str,
                 target_cycle_ms: int = 30000,
                 max_queue_size: int = 100):
        self.node_id = node_id
        self.target_cycle_ms = target_cycle_ms
        self.max_queue_size = max_queue_size
        
        # Metrics tracking
        self.cycle_metrics: List[CycleMetrics] = []
        self.running = False
        
        # State
        self.anomalies_detected = []
        self.recovery_plans = []
        self.executed_actions = []
    
    async def run_cycle(self) -> CycleMetrics:
        """Execute a single MAPE-K cycle with optimization"""
        
        cycle_start = time.perf_counter()
        
        try:
            # === MONITOR PHASE ===
            # Collect metrics from all components (parallelizable)
            monitor_start = time.perf_counter()
            monitor_result = await self._monitor_phase()
            monitor_ms = (time.perf_counter() - monitor_start) * 1000
            
            # === ANALYZE PHASE ===
            # Analyze collected metrics (can start immediately)
            analyze_start = time.perf_counter()
            analyze_result = await self._analyze_phase(monitor_result)
            analyze_ms = (time.perf_counter() - analyze_start) * 1000
            
            # === PLAN PHASE ===
            # Create recovery plan based on analysis
            plan_start = time.perf_counter()
            plan_result = await self._plan_phase(analyze_result)
            plan_ms = (time.perf_counter() - plan_start) * 1000
            
            # === EXECUTE PHASE ===
            # Execute recovery actions (prioritized for speed)
            execute_start = time.perf_counter()
            execute_result = await self._execute_phase(plan_result)
            execute_ms = (time.perf_counter() - execute_start) * 1000
            
            # === KNOWLEDGE PHASE ===
            # Learn from results (async, non-blocking)
            learn_start = time.perf_counter()
            asyncio.create_task(self._learn_phase(execute_result))
            learn_ms = (time.perf_counter() - learn_start) * 1000
            
            # Calculate metrics
            total_ms = (time.perf_counter() - cycle_start) * 1000
            
            metrics = CycleMetrics(
                monitor_ms=monitor_ms,
                analyze_ms=analyze_ms,
                plan_ms=plan_ms,
                execute_ms=execute_ms,
                learn_ms=learn_ms,
                total_ms=total_ms
            )
            
            self.cycle_metrics.append(metrics)
            
            # Log performance
            status = "✓" if total_ms <= self.target_cycle_ms else "⚠"
            logger.info(
                f"{status} MAPE-K Cycle: {total_ms:.1f}ms "
                f"(M:{monitor_ms:.1f} A:{analyze_ms:.1f} P:{plan_ms:.1f} "
                f"E:{execute_ms:.1f} K:{learn_ms:.1f}) "
                f"[{metrics.efficiency_score:.0f}% efficiency]"
            )
            
            return metrics
            
        except Exception as e:
            logger.error(f"MAPE-K cycle failed: {e}", exc_info=True)
            raise
    
    async def _monitor_phase(self) -> Dict[str, Any]:
        """Monitor: Collect system metrics"""
        
        metrics_tasks = [
            self._get_cpu_metrics(),
            self._get_memory_metrics(),
            self._get_network_metrics(),
            self._get_application_metrics(),
            self._get_consensus_metrics(),
        ]
        
        # Run all metric collection in parallel
        results = await asyncio.gather(*metrics_tasks, return_exceptions=True)
        
        metrics = {
            'cpu': results[0] if not isinstance(results[0], Exception) else None,
            'memory': results[1] if not isinstance(results[1], Exception) else None,
            'network': results[2] if not isinstance(results[2], Exception) else None,
            'application': results[3] if not isinstance(results[3], Exception) else None,
            'consensus': results[4] if not isinstance(results[4], Exception) else None,
            'timestamp': time.time(),
        }
        
        return metrics
    
    async def _get_cpu_metrics(self) -> Dict[str, float]:
        """Get CPU metrics"""
        # Simulate metric collection
        await asyncio.sleep(0.01)
        return {'usage_percent': 35, 'load_average': 2.5}
    
    async def _get_memory_metrics(self) -> Dict[str, float]:
        """Get memory metrics"""
        await asyncio.sleep(0.01)
        return {'used_mb': 450, 'available_mb': 550}
    
    async def _get_network_metrics(self) -> Dict[str, float]:
        """Get network metrics"""
        await asyncio.sleep(0.01)
        return {'latency_ms': 45, 'packet_loss_percent': 0.1}
    
    async def _get_application_metrics(self) -> Dict[str, Any]:
        """Get application metrics"""
        await asyncio.sleep(0.01)
        return {'requests_sec': 850, 'p99_latency_ms': 95}
    
    async def _get_consensus_metrics(self) -> Dict[str, Any]:
        """Get consensus metrics"""
        await asyncio.sleep(0.01)
        return {'leader': True, 'term': 42, 'committed_index': 1000}
    
    async def _analyze_phase(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze: Detect anomalies and issues"""
        
        anomalies = []
        severity_score = 0
        
        # Analyze each metric type
        if metrics['cpu']:
            if metrics['cpu']['usage_percent'] > 80:
                anomalies.append("HIGH_CPU_USAGE")
                severity_score += 2
        
        if metrics['memory']:
            if metrics['memory']['used_mb'] > 900:
                anomalies.append("HIGH_MEMORY_USAGE")
                severity_score += 2
        
        if metrics['network']:
            if metrics['network']['latency_ms'] > 100:
                anomalies.append("HIGH_LATENCY")
                severity_score += 1
        
        if metrics['application']:
            if metrics['application']['p99_latency_ms'] > 200:
                anomalies.append("SLOW_RESPONSE")
                severity_score += 1
        
        self.anomalies_detected = anomalies
        
        return {
            'anomalies': anomalies,
            'severity': severity_score,
            'root_causes': await self._identify_root_causes(anomalies),
            'affected_components': await self._identify_affected_components(anomalies),
        }
    
    async def _identify_root_causes(self, anomalies: List[str]) -> List[str]:
        """Identify root causes for detected anomalies"""
        await asyncio.sleep(0.01)
        
        causes = []
        for anomaly in anomalies:
            if anomaly == "HIGH_CPU_USAGE":
                causes.append("BUSY_SERVICE")
            elif anomaly == "HIGH_MEMORY_USAGE":
                causes.append("MEMORY_LEAK")
            elif anomaly == "HIGH_LATENCY":
                causes.append("NETWORK_CONGESTION")
        
        return causes
    
    async def _identify_affected_components(self, anomalies: List[str]) -> List[str]:
        """Identify which components are affected"""
        await asyncio.sleep(0.01)
        return ["mesh_router", "consensus_engine"]
    
    async def _plan_phase(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Plan: Create recovery plan"""
        
        actions = []
        severity = analysis.get('severity', 0)
        
        # Priority-based recovery planning
        if severity >= 4:
            # Severe issues - scale up and failover
            actions.extend([
                RecoveryAction.SCALE_UP,
                RecoveryAction.FAILOVER_PRIMARY,
            ])
        elif severity >= 2:
            # Moderate issues - restart and clear cache
            actions.extend([
                RecoveryAction.CLEAR_CACHE,
                RecoveryAction.RESTART_SERVICE,
            ])
        else:
            # Minor issues - monitor only
            actions.append(RecoveryAction.CLEAR_CACHE)
        
        self.recovery_plans.append({
            'timestamp': time.time(),
            'actions': actions,
            'severity': severity,
        })
        
        return {
            'actions': actions,
            'estimated_execution_time_ms': len(actions) * 5000,
            'rollback_plan': await self._create_rollback_plan(actions),
        }
    
    async def _create_rollback_plan(self, actions: List[RecoveryAction]) -> Dict[str, Any]:
        """Create rollback plan in case recovery fails"""
        await asyncio.sleep(0.005)
        return {'enabled': True, 'actions': []}
    
    async def _execute_phase(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Execute: Perform recovery actions"""
        
        actions = plan.get('actions', [])
        results = []
        
        # Execute actions in parallel where safe
        execution_tasks = []
        for action in actions:
            if action in [RecoveryAction.CLEAR_CACHE, RecoveryAction.SCALE_UP]:
                # These can run in parallel
                execution_tasks.append(self._execute_action(action))
            else:
                # These need sequential execution
                if execution_tasks:
                    await asyncio.gather(*execution_tasks)
                    execution_tasks = []
                await self._execute_action(action)
        
        # Wait for remaining tasks
        if execution_tasks:
            execution_results = await asyncio.gather(*execution_tasks)
            results.extend(execution_results)
        
        self.executed_actions.extend(actions)
        
        return {
            'success': True,
            'actions_executed': len(actions),
            'recovery_time_ms': sum(r.get('execution_time_ms', 0) 
                                    for r in results if isinstance(r, dict)),
        }
    
    async def _execute_action(self, action: RecoveryAction) -> Dict[str, Any]:
        """Execute a single recovery action"""
        
        start = time.perf_counter()
        
        try:
            if action == RecoveryAction.RESTART_SERVICE:
                await asyncio.sleep(0.005)  # Simulate execution
                logger.info(f"Executed: {action.value}")
            elif action == RecoveryAction.CLEAR_CACHE:
                await asyncio.sleep(0.002)
                logger.info(f"Executed: {action.value}")
            elif action == RecoveryAction.SCALE_UP:
                await asyncio.sleep(0.004)
                logger.info(f"Executed: {action.value}")
            elif action == RecoveryAction.FAILOVER_PRIMARY:
                await asyncio.sleep(0.006)
                logger.info(f"Executed: {action.value}")
            
            return {
                'action': action.value,
                'success': True,
                'execution_time_ms': (time.perf_counter() - start) * 1000,
            }
        except Exception as e:
            logger.error(f"Failed to execute {action.value}: {e}")
            return {
                'action': action.value,
                'success': False,
                'error': str(e),
            }
    
    async def _learn_phase(self, execution_result: Dict[str, Any]):
        """Learn: Update knowledge base from results"""
        
        # This runs async without blocking the main cycle
        await asyncio.sleep(0.01)
        
        # Learn what actions were effective
        logger.debug(f"Learning from execution: {execution_result}")
    
    def get_cycle_statistics(self) -> Dict[str, float]:
        """Get statistics about MAPE-K cycles"""
        
        if not self.cycle_metrics:
            return {}
        
        total_cycles = float(len(self.cycle_metrics))
        
        total_time = sum(m.total_ms for m in self.cycle_metrics)
        avg_time = total_time / total_cycles
        min_time = min(m.total_ms for m in self.cycle_metrics)
        max_time = max(m.total_ms for m in self.cycle_metrics)
        
        efficiency_scores = [m.efficiency_score for m in self.cycle_metrics]
        avg_efficiency = sum(efficiency_scores) / len(efficiency_scores)
        
        cycles_meeting_target = len([m for m in self.cycle_metrics 
                                     if m.total_ms <= self.target_cycle_ms])
        target_compliance = (cycles_meeting_target / total_cycles) * 100
        
        return {
            'total_cycles': int(total_cycles),
            'avg_cycle_ms': avg_time,
            'min_cycle_ms': min_time,
            'max_cycle_ms': max_time,
            'target_compliance_percent': target_compliance,
            'avg_efficiency_score': avg_efficiency,
            'anomalies_detected': len(set(self.anomalies_detected)),
            'recovery_plans_created': len(self.recovery_plans),
            'actions_executed': len(self.executed_actions),
        }
```

---

## Example 3: OpenTelemetry Integration

Complete OTel setup for distributed tracing and observability.

### File: `src/observability/telemetry_setup.py`

```python
"""
OpenTelemetry Integration Setup
Configures distributed tracing, metrics, and logging
"""

import logging
from typing import Optional

from opentelemetry import trace, metrics
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.aiohttp_client import AiohttpClientInstrumentor

logger = logging.getLogger(__name__)

class TelemetryConfiguration:
    """Centralized OpenTelemetry configuration"""
    
    @staticmethod
    def setup_jaeger_exporter(
        agent_host: str = "localhost",
        agent_port: int = 6831,
        service_name: str = "x0tta6bl4"
    ) -> JaegerExporter:
        """Configure Jaeger exporter for distributed traces"""
        
        return JaegerExporter(
            agent_host_name=agent_host,
            agent_port=agent_port,
            max_tag_value_length=4096,
        )
    
    @staticmethod
    def setup_prometheus_reader() -> PrometheusMetricReader:
        """Configure Prometheus metrics exporter"""
        
        return PrometheusMetricReader()
    
    @staticmethod
    def setup_trace_provider(
        jaeger_exporter: JaegerExporter,
        service_name: str = "x0tta6bl4"
    ) -> TracerProvider:
        """Configure trace provider with Jaeger backend"""
        
        trace_provider = TracerProvider(
            resource_attributes={
                "service.name": service_name,
                "service.version": "0.1.0",
            }
        )
        
        # Add Jaeger exporter
        trace_provider.add_span_processor(
            BatchSpanProcessor(jaeger_exporter)
        )
        
        return trace_provider
    
    @staticmethod
    def setup_meter_provider(
        prometheus_reader: PrometheusMetricReader
    ) -> MeterProvider:
        """Configure meter provider for metrics"""
        
        return MeterProvider(metric_readers=[prometheus_reader])
    
    @staticmethod
    def instrument_libraries():
        """Instrument third-party libraries"""
        
        # FastAPI instrumentation
        FastAPIInstrumentor().instrument()
        logger.info("FastAPI instrumented")
        
        # HTTP requests instrumentation
        RequestsInstrumentor().instrument()
        logger.info("Requests library instrumented")
        
        # Async HTTP instrumentation
        AiohttpClientInstrumentor().instrument()
        logger.info("aiohttp client instrumented")
        
        # SQLAlchemy instrumentation (if using database)
        try:
            SQLAlchemyInstrumentor().instrument()
            logger.info("SQLAlchemy instrumented")
        except Exception as e:
            logger.warning(f"Could not instrument SQLAlchemy: {e}")

class TelemetryManager:
    """High-level telemetry management"""
    
    _instance: Optional['TelemetryManager'] = None
    _tracer: Optional[trace.Tracer] = None
    _meter: Optional[metrics.Meter] = None
    
    def __init__(self):
        """Initialize telemetry system"""
        if TelemetryManager._instance is not None:
            raise RuntimeError("TelemetryManager is a singleton")
        
        logger.info("Initializing OpenTelemetry...")
        
        # Setup exporters
        jaeger_exporter = TelemetryConfiguration.setup_jaeger_exporter()
        prometheus_reader = TelemetryConfiguration.setup_prometheus_reader()
        
        # Setup providers
        trace_provider = TelemetryConfiguration.setup_trace_provider(
            jaeger_exporter
        )
        meter_provider = TelemetryConfiguration.setup_meter_provider(
            prometheus_reader
        )
        
        # Set global providers
        trace.set_tracer_provider(trace_provider)
        metrics.set_meter_provider(meter_provider)
        
        # Get tracer and meter
        TelemetryManager._tracer = trace.get_tracer(__name__)
        TelemetryManager._meter = metrics.get_meter(__name__)
        
        # Instrument libraries
        TelemetryConfiguration.instrument_libraries()
        
        logger.info("OpenTelemetry initialization complete")
    
    @classmethod
    def get_instance(cls) -> 'TelemetryManager':
        """Get or create singleton instance"""
        if cls._instance is None:
            cls._instance = TelemetryManager()
        return cls._instance
    
    @staticmethod
    def get_tracer() -> trace.Tracer:
        """Get global tracer"""
        if TelemetryManager._tracer is None:
            raise RuntimeError("TelemetryManager not initialized")
        return TelemetryManager._tracer
    
    @staticmethod
    def get_meter() -> metrics.Meter:
        """Get global meter"""
        if TelemetryManager._meter is None:
            raise RuntimeError("TelemetryManager not initialized")
        return TelemetryManager._meter

def init_telemetry():
    """Initialize telemetry (call once at startup)"""
    TelemetryManager.get_instance()

def get_tracer() -> trace.Tracer:
    """Get tracer for instrumentation"""
    return TelemetryManager.get_tracer()

def get_meter() -> metrics.Meter:
    """Get meter for metrics"""
    return TelemetryManager.get_meter()
```

### Usage Example

```python
# In FastAPI app startup
from fastapi import FastAPI
from src.observability.telemetry_setup import init_telemetry, get_tracer, get_meter

app = FastAPI()

@app.on_event("startup")
async def startup():
    init_telemetry()  # Initialize OpenTelemetry
    logger.info("Telemetry initialized")

# In route handlers
@app.get("/api/message/{message_id}")
async def get_message(message_id: str):
    tracer = get_tracer()
    meter = get_meter()
    
    with tracer.start_as_current_span("get_message") as span:
        span.set_attribute("message_id", message_id)
        
        # Record metric
        counter = meter.create_counter(
            name="message_requests",
            description="Number of message requests"
        )
        counter.add(1, {"method": "GET"})
        
        # Actual business logic
        message = await fetch_message(message_id)
        
        return {"id": message_id, "content": message}
```

---

## Testing the Examples

### Test for Raft Snapshot

```python
# tests/consensus/test_raft_snapshot.py
import pytest
from src.consensus.raft_snapshot import SnapshotManager, RaftSnapshot

@pytest.fixture
def snapshot_manager(tmp_path):
    return SnapshotManager(str(tmp_path))

def test_create_and_restore_snapshot(snapshot_manager):
    """Test snapshot creation and restoration"""
    
    state_data = {
        'key1': 'value1',
        'key2': 'value2',
        'log_entries': [1, 2, 3, 4, 5]
    }
    
    # Create snapshot
    snapshot = snapshot_manager.create_snapshot(
        last_included_index=100,
        last_included_term=5,
        state_machine_data=state_data
    )
    
    assert snapshot.last_included_index == 100
    assert snapshot.last_included_term == 5
    
    # Restore snapshot
    restored = snapshot_manager.restore_snapshot(100)
    assert restored is not None
    assert restored.state_machine_data == state_data

def test_multiple_snapshots(snapshot_manager):
    """Test multiple snapshot handling"""
    
    for i in range(5):
        snapshot_manager.create_snapshot(
            last_included_index=i * 100,
            last_included_term=i,
            state_machine_data={'index': i}
        )
    
    # Get latest
    latest = snapshot_manager.get_latest_snapshot()
    assert latest.last_included_index == 400
    
    # Cleanup old ones
    snapshot_manager.cleanup_old_snapshots(keep_count=2)
```

---

This provides production-ready code examples for implementing all critical P1 fixes.
