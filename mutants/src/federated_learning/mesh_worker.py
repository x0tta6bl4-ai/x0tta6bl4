"""
FL Worker for Mesh Node Integration
===================================

FL Worker интегрируется с mesh узлом для участия в федеративном обучении.

Функции:
- Регистрация в FL Coordinator через mesh heartbeat
- Сбор метрик mesh для локального обучения
- Обучение локальной модели на метриках узла
- Отправка обновлений в Coordinator
- Получение глобальной модели обратно
"""
import asyncio
import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

from .protocol import ModelUpdate, ModelWeights, GlobalModel
from .coordinator import FederatedCoordinator

logger = logging.getLogger(__name__)


class WorkerStatus(Enum):
    """Status of FL Worker."""
    IDLE = "idle"
    REGISTERING = "registering"
    REGISTERED = "registered"
    TRAINING = "training"
    UPDATING = "updating"
    ERROR = "error"


@dataclass
class MeshMetrics:
    """Metrics collected from mesh node."""
    node_id: str
    timestamp: float
    
    # System metrics
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    
    # Mesh metrics
    peers_count: int = 0
    latency_ms: float = 0.0
    packet_loss_percent: float = 0.0
    throughput_mbps: float = 0.0
    
    # Security metrics
    zero_trust_success_rate: float = 1.0
    byzantine_detections: int = 0
    
    # Routing metrics
    routes_count: int = 0
    failover_count: int = 0
    
    def to_feature_vector(self) -> List[float]:
        """Convert metrics to feature vector for ML model."""
        return [
            self.cpu_percent / 100.0,
            self.memory_percent / 100.0,
            self.peers_count / 100.0,  # Normalize
            self.latency_ms / 1000.0,  # Normalize to seconds
            self.packet_loss_percent / 100.0,
            self.throughput_mbps / 1000.0,  # Normalize
            self.zero_trust_success_rate,
            self.byzantine_detections / 10.0,  # Normalize
            self.routes_count / 50.0,  # Normalize
            self.failover_count / 10.0  # Normalize
        ]


class FLMeshWorker:
    """
    FL Worker интегрированный с mesh узлом.
    
    Usage:
        worker = FLMeshWorker(
            node_id="node-01",
            coordinator=fl_coordinator,
            mesh_router=mesh_router
        )
        await worker.start()
        await worker.collect_and_train()
    """
    
    def __init__(
        self,
        node_id: str,
        coordinator: FederatedCoordinator,
        mesh_router=None,  # MeshRouter instance
        mesh_shield=None,  # MeshShield instance
        collect_interval: float = 10.0  # Collect metrics every 10 seconds
    ):
        self.node_id = node_id
        self.coordinator = coordinator
        self.mesh_router = mesh_router
        self.mesh_shield = mesh_shield
        
        self.status = WorkerStatus.IDLE
        self.collect_interval = collect_interval
        
        # Local model state
        self.local_model: Optional[GlobalModel] = None
        self.local_weights: Optional[ModelWeights] = None
        
        # Metrics history for training
        self.metrics_history: List[MeshMetrics] = []
        self.max_history = 1000  # Keep last 1000 metrics
        
        # Training state
        self.current_round: Optional[int] = None
        self.is_training = False
        
        # Capabilities
        self.capabilities = {
            "compute": 1.0,  # Will be updated from actual node
            "memory": 1.0,
            "network": 1.0
        }
        
        logger.info(f"FLMeshWorker initialized for {node_id}")
    
    async def start(self):
        """Start the FL Worker."""
        self.status = WorkerStatus.REGISTERING
        
        # Register with coordinator
        success = self.coordinator.register_node(
            self.node_id,
            capabilities=self.capabilities
        )
        
        if success:
            self.status = WorkerStatus.REGISTERED
            logger.info(f"✅ FL Worker {self.node_id} registered with coordinator")
            
            # Start background tasks
            asyncio.create_task(self._heartbeat_loop())
            asyncio.create_task(self._metrics_collection_loop())
        else:
            self.status = WorkerStatus.ERROR
            logger.error(f"❌ Failed to register FL Worker {self.node_id}")
    
    async def stop(self):
        """Stop the FL Worker."""
        self.status = WorkerStatus.IDLE
        self.coordinator.unregister_node(self.node_id)
        logger.info(f"FL Worker {self.node_id} stopped")
    
    async def _heartbeat_loop(self):
        """Send heartbeat to coordinator."""
        while self.status == WorkerStatus.REGISTERED:
            try:
                # Update heartbeat with current status
                status = {
                    "status": self.status.value,
                    "is_training": self.is_training,
                    "metrics_count": len(self.metrics_history)
                }
                self.coordinator.update_heartbeat(self.node_id, status)
                
                await asyncio.sleep(self.coordinator.config.heartbeat_interval)
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                await asyncio.sleep(5.0)
    
    async def _metrics_collection_loop(self):
        """Continuously collect metrics from mesh node."""
        while self.status == WorkerStatus.REGISTERED:
            try:
                metrics = await self._collect_metrics()
                if metrics:
                    self.metrics_history.append(metrics)
                    
                    # Trim history
                    if len(self.metrics_history) > self.max_history:
                        self.metrics_history = self.metrics_history[-self.max_history:]
                
                await asyncio.sleep(self.collect_interval)
            except Exception as e:
                logger.error(f"Metrics collection error: {e}")
                await asyncio.sleep(self.collect_interval)
    
    async def _collect_metrics(self) -> Optional[MeshMetrics]:
        """Collect metrics from mesh node."""
        try:
            # Get system metrics
            import psutil
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory_percent = psutil.virtual_memory().percent
        except ImportError:
            cpu_percent = 50.0
            memory_percent = 50.0
        
        # Get mesh metrics from router
        peers_count = 0
        latency_ms = 0.0
        packet_loss_percent = 0.0
        throughput_mbps = 0.0
        routes_count = 0
        failover_count = 0
        
        if self.mesh_router:
            stats = self.mesh_router.get_stats()
            peers_count = len(stats.get("peers", []))
            
            # Calculate average latency
            if peers_count > 0:
                latencies = [
                    p.get("latency", 0.0) for p in stats.get("peers", [])
                ]
                latency_ms = sum(latencies) / len(latencies) * 1000  # Convert to ms
            
            routes_count = stats.get("routes_cached", 0)
        
        # Get security metrics from shield
        zero_trust_success_rate = 1.0
        byzantine_detections = 0
        
        if self.mesh_shield:
            shield_metrics = self.mesh_shield.get_metrics()
            byzantine_detections = shield_metrics.get("quarantines", 0)
        
        metrics = MeshMetrics(
            node_id=self.node_id,
            timestamp=time.time(),
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            peers_count=peers_count,
            latency_ms=latency_ms,
            packet_loss_percent=packet_loss_percent,
            throughput_mbps=throughput_mbps,
            zero_trust_success_rate=zero_trust_success_rate,
            byzantine_detections=byzantine_detections,
            routes_count=routes_count,
            failover_count=failover_count
        )
        
        return metrics
    
    async def train_local_model(self, round_number: int) -> Optional[ModelUpdate]:
        """
        Train local model on collected metrics.
        
        Args:
            round_number: Current training round number
            
        Returns:
            ModelUpdate with trained weights
        """
        if len(self.metrics_history) < 10:
            logger.warning(f"Not enough metrics for training: {len(self.metrics_history)}")
            return None
        
        self.status = WorkerStatus.TRAINING
        self.is_training = True
        self.current_round = round_number
        
        try:
            # Convert metrics to feature vectors
            features = [m.to_feature_vector() for m in self.metrics_history[-100:]]  # Use last 100
            
            # Simple local training (in production, use actual ML model)
            # For now, we'll create a simple weight vector from features
            num_features = len(features[0])
            weights = []
            
            # Average feature values as "learned" weights
            for i in range(num_features):
                avg_value = sum(f[i] for f in features) / len(features)
                weights.append(avg_value)
            
            # Calculate loss (simplified)
            loss = sum(
                abs(f[i] - weights[i])
                for f in features
                for i in range(num_features)
            ) / (len(features) * num_features)
            
            # Create model weights
            model_weights = ModelWeights(
                weights=weights,
                num_samples=len(features)
            )
            
            # Create update
            update = ModelUpdate(
                node_id=self.node_id,
                round_number=round_number,
                weights=model_weights,
                loss=loss,
                num_samples=len(features),
                training_time=time.time() - self.metrics_history[-1].timestamp
            )
            
            self.local_weights = model_weights
            self.status = WorkerStatus.REGISTERED
            self.is_training = False
            
            logger.info(
                f"✅ Local training complete for {self.node_id}: "
                f"loss={loss:.4f}, samples={len(features)}"
            )
            
            return update
            
        except Exception as e:
            logger.error(f"Training error: {e}")
            self.status = WorkerStatus.ERROR
            self.is_training = False
            return None
    
    async def submit_update(self, update: ModelUpdate) -> bool:
        """Submit model update to coordinator."""
        try:
            self.status = WorkerStatus.UPDATING
            self.coordinator.submit_update(update)
            self.status = WorkerStatus.REGISTERED
            logger.info(f"✅ Update submitted for {self.node_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to submit update: {e}")
            self.status = WorkerStatus.ERROR
            return False
    
    def receive_global_model(self, global_model: GlobalModel):
        """Receive global model from coordinator."""
        self.local_model = global_model
        logger.info(f"✅ Received global model for round {global_model.round_number}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get worker status."""
        return {
            "node_id": self.node_id,
            "status": self.status.value,
            "is_training": self.is_training,
            "current_round": self.current_round,
            "metrics_count": len(self.metrics_history),
            "has_local_model": self.local_model is not None,
            "capabilities": self.capabilities
        }

