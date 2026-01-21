"""
MLOps Integration Module

Model versioning, performance monitoring, retraining pipelines, and model registry.
Manages ML lifecycle in production.
"""

import asyncio
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
import json
import hashlib
from datetime import datetime
import numpy as np


@dataclass
class ModelMetadata:
    """Model metadata"""
    name: str
    version: str
    model_type: str  # "rag", "lora", "anomaly", "decision"
    created_at: str
    updated_at: str
    framework: str = "custom"
    parameters_count: int = 0
    input_dims: List[int] = field(default_factory=list)
    output_dims: List[int] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    description: str = ""


@dataclass
class ModelPerformance:
    """Model performance metrics"""
    model_version: str
    timestamp: str
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    latency_ms: float = 0.0
    inference_count: int = 0
    error_count: int = 0
    custom_metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class RetrainingJob:
    """Retraining job specification"""
    job_id: str
    model_name: str
    trigger_reason: str  # "performance_degradation", "scheduled", "data_drift"
    training_config: Dict[str, Any]
    status: str = "pending"  # pending, running, completed, failed
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)


class ModelRegistry:
    """Central model registry"""
    
    def __init__(self):
        """Initialize registry"""
        self.models: Dict[str, Dict[str, Any]] = {}  # {name: {versions}}
        self.model_history: List[ModelMetadata] = []
        self.performance_log: List[ModelPerformance] = []
    
    def register_model(self, metadata: ModelMetadata, model_obj: Any = None) -> None:
        """
        Register new model version
        
        Args:
            metadata: Model metadata
            model_obj: Model object (optional)
        """
        if metadata.name not in self.models:
            self.models[metadata.name] = {}
        
        model_entry = {
            "metadata": metadata,
            "object": model_obj,
            "registered_at": datetime.now().isoformat(),
            "hash": self._compute_hash(model_obj)
        }
        
        self.models[metadata.name][metadata.version] = model_entry
        self.model_history.append(metadata)
    
    def _compute_hash(self, obj: Any) -> str:
        """Compute model hash for integrity"""
        try:
            obj_str = str(obj)
            return hashlib.sha256(obj_str.encode()).hexdigest()[:16]
        except:
            return "unknown"
    
    def get_model(self, name: str, version: Optional[str] = None) -> Optional[Any]:
        """
        Get model by name and version
        
        Args:
            name: Model name
            version: Version (latest if None)
            
        Returns:
            Model object or None
        """
        if name not in self.models:
            return None
        
        versions = self.models[name]
        if not versions:
            return None
        
        if version is None:
            # Get latest version
            latest_version = max(versions.keys())
            version = latest_version
        
        if version in versions:
            return versions[version]["object"]
        
        return None
    
    async def log_performance(self, perf: ModelPerformance) -> None:
        """Log model performance metrics"""
        self.performance_log.append(perf)
    
    def get_model_versions(self, name: str) -> List[str]:
        """Get all versions of a model"""
        if name in self.models:
            return list(self.models[name].keys())
        return []
    
    def get_performance_history(
        self,
        model_name: str,
        metric: str = "accuracy",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get performance history for metric"""
        history = [
            {
                "timestamp": p.timestamp,
                "version": p.model_version,
                "value": getattr(p, metric, None)
            }
            for p in self.performance_log
            if model_name in p.model_version
        ]
        
        return history[-limit:]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics"""
        total_versions = sum(len(v) for v in self.models.values())
        
        return {
            "models_count": len(self.models),
            "total_versions": total_versions,
            "performance_records": len(self.performance_log),
            "registered_models": list(self.models.keys()),
            "timestamp": datetime.now().isoformat()
        }


class PerformanceMonitor:
    """Continuous performance monitoring"""
    
    def __init__(self, registry: ModelRegistry):
        """
        Initialize monitor
        
        Args:
            registry: Model registry
        """
        self.registry = registry
        self.thresholds: Dict[str, float] = {
            "accuracy": 0.7,
            "latency_ms": 100.0,
            "error_rate": 0.1
        }
        self.alerts: List[Dict[str, Any]] = []
    
    async def update_metrics(
        self,
        model_name: str,
        version: str,
        predictions: List[Dict[str, float]]
    ) -> Optional[Dict[str, Any]]:
        """
        Update performance metrics
        
        Args:
            model_name: Model name
            version: Model version
            predictions: List of predictions with scores
            
        Returns:
            Alert if threshold exceeded
        """
        if not predictions:
            return None
        
        scores = [p.get("score", 0.0) for p in predictions]
        errors = [1 - p.get("score", 0.0) for p in predictions]
        
        accuracy = float(np.mean(scores)) if scores else 0.0
        error_rate = float(np.mean(errors)) if errors else 0.0
        
        perf = ModelPerformance(
            model_version=f"{model_name}:{version}",
            timestamp=datetime.now().isoformat(),
            accuracy=accuracy,
            error_count=int(sum(1 for e in errors if e > 0.5)),
            inference_count=len(predictions)
        )
        
        await self.registry.log_performance(perf)
        
        # Check thresholds
        alert = None
        
        if accuracy < self.thresholds["accuracy"]:
            alert = {
                "type": "accuracy_degradation",
                "model": model_name,
                "version": version,
                "current": accuracy,
                "threshold": self.thresholds["accuracy"],
                "severity": "high" if accuracy < 0.5 else "medium",
                "timestamp": datetime.now().isoformat()
            }
            self.alerts.append(alert)
        
        if error_rate > self.thresholds["error_rate"]:
            alert = {
                "type": "error_rate_high",
                "model": model_name,
                "version": version,
                "current": error_rate,
                "threshold": self.thresholds["error_rate"],
                "severity": "high",
                "timestamp": datetime.now().isoformat()
            }
            self.alerts.append(alert)
        
        return alert
    
    def set_threshold(self, metric: str, value: float) -> None:
        """Set performance threshold"""
        self.thresholds[metric] = value
    
    def get_recent_alerts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent alerts"""
        return self.alerts[-limit:]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get monitoring statistics"""
        return {
            "thresholds": self.thresholds,
            "total_alerts": len(self.alerts),
            "recent_alerts": len([a for a in self.alerts if a.get("severity") == "high"]),
            "timestamp": datetime.now().isoformat()
        }


class RetrainingOrchestrator:
    """Orchestrates model retraining pipelines"""
    
    def __init__(
        self,
        registry: ModelRegistry,
        monitor: PerformanceMonitor
    ):
        """
        Initialize orchestrator
        
        Args:
            registry: Model registry
            monitor: Performance monitor
        """
        self.registry = registry
        self.monitor = monitor
        self.jobs: Dict[str, RetrainingJob] = {}
        self.completed_jobs: List[RetrainingJob] = []
    
    async def trigger_retraining(
        self,
        model_name: str,
        trigger_reason: str,
        training_config: Dict[str, Any]
    ) -> str:
        """
        Trigger retraining job
        
        Args:
            model_name: Model to retrain
            trigger_reason: Reason for retraining
            training_config: Training configuration
            
        Returns:
            Job ID
        """
        job_id = f"{model_name}_retrain_{datetime.now().timestamp()}"
        
        job = RetrainingJob(
            job_id=job_id,
            model_name=model_name,
            trigger_reason=trigger_reason,
            training_config=training_config,
            status="pending"
        )
        
        self.jobs[job_id] = job
        
        # Start job asynchronously
        asyncio.create_task(self._execute_retraining(job))
        
        return job_id
    
    async def _execute_retraining(self, job: RetrainingJob) -> None:
        """Execute retraining job"""
        job.status = "running"
        job.start_time = datetime.now().isoformat()
        
        try:
            # Simulate training
            await asyncio.sleep(0.5)
            
            # Update job metrics
            job.metrics = {
                "epochs": job.training_config.get("epochs", 10),
                "final_accuracy": 0.88 + np.random.random() * 0.1,
                "training_time_s": 45.2,
                "samples_used": 1000
            }
            
            job.status = "completed"
        
        except Exception as e:
            job.status = "failed"
            job.metrics["error"] = str(e)
        
        finally:
            job.end_time = datetime.now().isoformat()
            self.completed_jobs.append(job)
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status"""
        if job_id in self.jobs:
            job = self.jobs[job_id]
            return {
                "job_id": job.job_id,
                "model": job.model_name,
                "status": job.status,
                "reason": job.trigger_reason,
                "start_time": job.start_time,
                "end_time": job.end_time,
                "metrics": job.metrics
            }
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get orchestrator statistics"""
        return {
            "active_jobs": sum(1 for j in self.jobs.values() if j.status == "running"),
            "completed_jobs": len(self.completed_jobs),
            "failed_jobs": sum(1 for j in self.completed_jobs if j.status == "failed"),
            "total_jobs": len(self.jobs) + len(self.completed_jobs),
            "timestamp": datetime.now().isoformat()
        }


class MLOpsManager:
    """Main MLOps management system"""
    
    def __init__(self):
        """Initialize MLOps manager"""
        self.registry = ModelRegistry()
        self.monitor = PerformanceMonitor(self.registry)
        self.orchestrator = RetrainingOrchestrator(self.registry, self.monitor)
    
    async def register_trained_model(
        self,
        name: str,
        version: str,
        model_type: str,
        model_obj: Any = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Register trained model"""
        meta = ModelMetadata(
            name=name,
            version=version,
            model_type=model_type,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            **metadata or {}
        )
        
        self.registry.register_model(meta, model_obj)
    
    async def check_model_health(self, model_name: str) -> Dict[str, Any]:
        """Check model health"""
        versions = self.registry.get_model_versions(model_name)
        
        if not versions:
            return {"error": f"Model {model_name} not found"}
        
        latest_version = max(versions)
        history = self.registry.get_performance_history(model_name, limit=50)
        
        if not history:
            return {"status": "no_data", "model": model_name}
        
        accuracies = [h["value"] for h in history if h["value"] is not None]
        
        return {
            "model": model_name,
            "latest_version": latest_version,
            "status": "healthy" if accuracies and min(accuracies) > 0.7 else "warning",
            "current_accuracy": accuracies[-1] if accuracies else None,
            "avg_accuracy": float(np.mean(accuracies)) if accuracies else 0.0,
            "min_accuracy": float(np.min(accuracies)) if accuracies else 0.0,
            "trend": "improving" if len(accuracies) > 1 and accuracies[-1] > accuracies[0] else "stable"
        }
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get overall MLOps statistics"""
        return {
            "registry": self.registry.get_stats(),
            "monitor": self.monitor.get_stats(),
            "orchestrator": self.orchestrator.get_stats(),
            "timestamp": datetime.now().isoformat()
        }


# Example usage
async def example_mlops_workflow():
    """Example MLOps workflow"""
    manager = MLOpsManager()
    
    # Register model
    await manager.register_trained_model(
        name="anomaly_detector",
        version="1.0.0",
        model_type="anomaly",
        metadata={"framework": "pytorch", "parameters_count": 15000}
    )
    
    # Simulate predictions
    predictions = [
        {"score": 0.92},
        {"score": 0.88},
        {"score": 0.85},
    ]
    
    alert = await manager.monitor.update_metrics(
        "anomaly_detector",
        "1.0.0",
        predictions
    )
    
    # Check model health
    health = await manager.check_model_health("anomaly_detector")
    print(f"Model health: {health}")
    
    return manager


if __name__ == "__main__":
    manager = MLOpsManager()
    print("MLOps Manager initialized")
