"""
MLOps Integration Module

Model versioning, performance monitoring, retraining pipelines, and model registry.
Manages ML lifecycle in production.
"""

import asyncio
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

from src.core.thinking.agent_thinking import AgentThinkingCoach


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
    if value <= 1000:
        return "100-1000"
    return "1000+"


def _safe_mapping_summary(values: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    mapping = values or {}
    return {
        "key_count_bucket": _safe_count_bucket(len(mapping)),
        "key_hashes": sorted(_safe_hash(key) for key in mapping.keys()),
        "value_type_counts": {
            type(value).__name__: sum(
                1
                for item in mapping.values()
                if type(item).__name__ == type(value).__name__
            )
            for value in mapping.values()
        },
    }


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
        self.thinking_coach = AgentThinkingCoach(
            agent_id="ml-model-registry",
            role="development",
            capabilities=("quality", "ops"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "ml_model_registry_init",
                "goal": "Initialize model registry without raw model metadata",
                "signals": {
                    "model_count_bucket": "0",
                    "performance_record_count_bucket": "0",
                },
                "safety_boundary": (
                    "Keep model names, versions, descriptions, tags, and model "
                    "object representations out of thinking context."
                ),
            }
        )

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
                    "redact_model_names": True,
                    "redact_versions": True,
                    "redact_model_objects": True,
                    "redact_descriptions": True,
                    "preserve_registry_decision": True,
                },
                "safety_boundary": "Use hashes, counts, model types, and metric bands.",
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

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
            "hash": self._compute_hash(model_obj),
        }

        self.models[metadata.name][metadata.version] = model_entry
        self.model_history.append(metadata)
        self._record_thinking(
            "ml_model_registered",
            "Register model version safely",
            {
                "model_hash": _safe_hash(metadata.name),
                "version_hash": _safe_hash(metadata.version),
                "model_type": metadata.model_type,
                "framework_hash": _safe_hash(metadata.framework),
                "tag_count_bucket": _safe_count_bucket(len(metadata.tags)),
                "has_description": bool(metadata.description),
                "model_count_bucket": _safe_count_bucket(len(self.models)),
                "version_count_bucket": _safe_count_bucket(
                    len(self.models[metadata.name])
                ),
            },
        )

    def _compute_hash(self, obj: Any) -> str:
        """Compute model hash for integrity"""
        try:
            obj_str = str(obj)
            return hashlib.sha256(obj_str.encode()).hexdigest()[:16]
        except Exception:
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
            self._record_thinking(
                "ml_model_lookup",
                "Report missing model lookup",
                {
                    "model_hash": _safe_hash(name),
                    "version_hash": _safe_hash(version) if version else None,
                    "found": False,
                },
            )
            return None

        versions = self.models[name]
        if not versions:
            return None

        if version is None:
            # Get latest version
            latest_version = max(versions.keys())
            version = latest_version

        if version in versions:
            self._record_thinking(
                "ml_model_lookup",
                "Resolve model lookup",
                {
                    "model_hash": _safe_hash(name),
                    "version_hash": _safe_hash(version),
                    "found": True,
                    "version_count_bucket": _safe_count_bucket(len(versions)),
                },
            )
            return versions[version]["object"]

        self._record_thinking(
            "ml_model_lookup",
            "Report missing model version lookup",
            {
                "model_hash": _safe_hash(name),
                "version_hash": _safe_hash(version),
                "found": False,
                "version_count_bucket": _safe_count_bucket(len(versions)),
            },
        )
        return None

    async def log_performance(self, perf: ModelPerformance) -> None:
        """Log model performance metrics"""
        self.performance_log.append(perf)
        self._record_thinking(
            "ml_model_performance_logged",
            "Log model performance safely",
            {
                "model_version_hash": _safe_hash(perf.model_version),
                "accuracy_band": _safe_number_band(perf.accuracy),
                "latency_band": _safe_number_band(perf.latency_ms),
                "error_count_bucket": _safe_count_bucket(perf.error_count),
                "inference_count_bucket": _safe_count_bucket(perf.inference_count),
                "custom_metric_count_bucket": _safe_count_bucket(
                    len(perf.custom_metrics)
                ),
            },
        )

    def get_model_versions(self, name: str) -> List[str]:
        """Get all versions of a model"""
        if name in self.models:
            return list(self.models[name].keys())
        return []

    def get_performance_history(
        self, model_name: str, metric: str = "accuracy", limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get performance history for metric"""
        history = [
            {
                "timestamp": p.timestamp,
                "version": p.model_version,
                "value": getattr(p, metric, None),
            }
            for p in self.performance_log
            if model_name in p.model_version
        ]

        return history[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics"""
        total_versions = sum(len(v) for v in self.models.values())

        stats = {
            "models_count": len(self.models),
            "total_versions": total_versions,
            "performance_records": len(self.performance_log),
            "registered_models": list(self.models.keys()),
            "timestamp": datetime.now().isoformat(),
        }
        self._record_thinking(
            "ml_model_registry_stats",
            "Summarize model registry safely",
            {
                "model_count_bucket": _safe_count_bucket(len(self.models)),
                "version_count_bucket": _safe_count_bucket(total_versions),
                "performance_record_count_bucket": _safe_count_bucket(
                    len(self.performance_log)
                ),
            },
        )
        return stats

    def get_all_models(self) -> List[ModelMetadata]:
        """Backward-compatible accessor for all registered model metadata."""
        return list(self.model_history)


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
            "error_rate": 0.1,
        }
        self.alerts: List[Dict[str, Any]] = []
        self.thinking_coach = AgentThinkingCoach(
            agent_id="ml-performance-monitor",
            role="monitoring",
            capabilities=("quality", "ops"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "ml_performance_monitor_init",
                "goal": "Initialize model performance monitoring safely",
                "signals": {
                    "threshold_count_bucket": _safe_count_bucket(len(self.thresholds)),
                    "alert_count_bucket": "0",
                },
                "safety_boundary": (
                    "Keep model names, versions, prediction payloads, and raw "
                    "custom metrics out of thinking context."
                ),
            }
        )

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
                    "redact_model_names": True,
                    "redact_versions": True,
                    "redact_prediction_payloads": True,
                    "preserve_alert_decision": True,
                },
                "safety_boundary": "Use hashes, counts, metric bands, and severities.",
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    async def update_metrics(
        self, model_name: str, version: str, predictions: List[Dict[str, float]]
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
            self._record_thinking(
                "ml_performance_update",
                "Skip performance update without predictions",
                {
                    "model_hash": _safe_hash(model_name),
                    "version_hash": _safe_hash(version),
                    "prediction_count_bucket": "0",
                },
            )
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
            inference_count=len(predictions),
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
                "timestamp": datetime.now().isoformat(),
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
                "timestamp": datetime.now().isoformat(),
            }
            self.alerts.append(alert)

        self._record_thinking(
            "ml_performance_update",
            "Update model metrics and evaluate thresholds",
            {
                "model_hash": _safe_hash(model_name),
                "version_hash": _safe_hash(version),
                "prediction_count_bucket": _safe_count_bucket(len(predictions)),
                "accuracy_band": _safe_number_band(accuracy),
                "error_rate_band": _safe_number_band(error_rate),
                "alert_created": alert is not None,
                "alert_type_hash": _safe_hash(alert["type"]) if alert else None,
                "alert_severity": alert["severity"] if alert else None,
            },
        )
        return alert

    def set_threshold(self, metric: str, value: float) -> None:
        """Set performance threshold"""
        self.thresholds[metric] = value
        self._record_thinking(
            "ml_performance_threshold_set",
            "Set model performance threshold",
            {
                "metric_hash": _safe_hash(metric),
                "value_band": _safe_number_band(value),
                "threshold_count_bucket": _safe_count_bucket(len(self.thresholds)),
            },
        )

    def get_recent_alerts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent alerts"""
        return self.alerts[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """Get monitoring statistics"""
        stats = {
            "thresholds": self.thresholds,
            "total_alerts": len(self.alerts),
            "recent_alerts": len(
                [a for a in self.alerts if a.get("severity") == "high"]
            ),
            "timestamp": datetime.now().isoformat(),
        }
        self._record_thinking(
            "ml_performance_monitor_stats",
            "Summarize model performance monitor safely",
            {
                "threshold_count_bucket": _safe_count_bucket(len(self.thresholds)),
                "total_alerts_bucket": _safe_count_bucket(len(self.alerts)),
                "high_alerts_bucket": _safe_count_bucket(stats["recent_alerts"]),
            },
        )
        return stats


class RetrainingOrchestrator:
    """Orchestrates model retraining pipelines"""

    def __init__(self, registry: ModelRegistry, monitor: PerformanceMonitor):
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
        self.thinking_coach = AgentThinkingCoach(
            agent_id="ml-retraining-orchestrator",
            role="coordinator",
            capabilities=("quality", "ops"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "ml_retraining_orchestrator_init",
                "goal": "Initialize retraining orchestration safely",
                "signals": {"job_count_bucket": "0", "completed_job_count_bucket": "0"},
                "safety_boundary": (
                    "Keep model names, job ids, training configs, and error messages "
                    "out of thinking context."
                ),
            }
        )

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
                    "redact_model_names": True,
                    "redact_job_ids": True,
                    "redact_training_config": True,
                    "redact_error_messages": True,
                    "preserve_job_state": True,
                },
                "safety_boundary": "Use hashes, counts, statuses, and metric bands.",
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    async def trigger_retraining(
        self, model_name: str, trigger_reason: str, training_config: Dict[str, Any]
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
            status="pending",
        )

        self.jobs[job_id] = job

        self._record_thinking(
            "ml_retraining_triggered",
            "Create retraining job safely",
            {
                "model_hash": _safe_hash(model_name),
                "job_hash": _safe_hash(job_id),
                "trigger_reason_hash": _safe_hash(trigger_reason),
                "training_config": _safe_mapping_summary(training_config),
                "active_job_count_bucket": _safe_count_bucket(len(self.jobs)),
            },
        )

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
                "samples_used": 1000,
            }

            job.status = "completed"
            self._record_thinking(
                "ml_retraining_completed",
                "Complete retraining job safely",
                {
                    "model_hash": _safe_hash(job.model_name),
                    "job_hash": _safe_hash(job.job_id),
                    "status": job.status,
                    "metrics": _safe_mapping_summary(job.metrics),
                },
            )

        except Exception as e:
            job.status = "failed"
            job.metrics["error"] = str(e)
            self._record_thinking(
                "ml_retraining_failed",
                "Record retraining job failure",
                {
                    "model_hash": _safe_hash(job.model_name),
                    "job_hash": _safe_hash(job.job_id),
                    "status": job.status,
                    "error_type": type(e).__name__,
                },
            )

        finally:
            job.end_time = datetime.now().isoformat()
            self.completed_jobs.append(job)

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status"""
        if job_id in self.jobs:
            job = self.jobs[job_id]
            status = {
                "job_id": job.job_id,
                "model": job.model_name,
                "status": job.status,
                "reason": job.trigger_reason,
                "start_time": job.start_time,
                "end_time": job.end_time,
                "metrics": job.metrics,
            }
            self._record_thinking(
                "ml_retraining_job_status",
                "Read retraining job status safely",
                {
                    "job_hash": _safe_hash(job_id),
                    "model_hash": _safe_hash(job.model_name),
                    "status": job.status,
                    "metrics": _safe_mapping_summary(job.metrics),
                },
            )
            return status
        self._record_thinking(
            "ml_retraining_job_status",
            "Report missing retraining job status",
            {"job_hash": _safe_hash(job_id), "found": False},
        )
        return None

    def get_stats(self) -> Dict[str, Any]:
        """Get orchestrator statistics"""
        stats = {
            "active_jobs": sum(1 for j in self.jobs.values() if j.status == "running"),
            "completed_jobs": len(self.completed_jobs),
            "failed_jobs": sum(1 for j in self.completed_jobs if j.status == "failed"),
            "total_jobs": len(self.jobs) + len(self.completed_jobs),
            "timestamp": datetime.now().isoformat(),
        }
        self._record_thinking(
            "ml_retraining_orchestrator_stats",
            "Summarize retraining orchestrator safely",
            {
                "active_jobs_bucket": _safe_count_bucket(stats["active_jobs"]),
                "completed_jobs_bucket": _safe_count_bucket(stats["completed_jobs"]),
                "failed_jobs_bucket": _safe_count_bucket(stats["failed_jobs"]),
                "total_jobs_bucket": _safe_count_bucket(stats["total_jobs"]),
            },
        )
        return stats


class MLOpsManager:
    """Main MLOps management system"""

    def __init__(self):
        """Initialize MLOps manager"""
        self.registry = ModelRegistry()
        self.monitor = PerformanceMonitor(self.registry)
        self.orchestrator = RetrainingOrchestrator(self.registry, self.monitor)
        self.thinking_coach = AgentThinkingCoach(
            agent_id="mlops-manager",
            role="coordinator",
            capabilities=("quality", "ops", "monitoring"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "mlops_manager_init",
                "goal": "Initialize MLOps lifecycle decisions safely",
                "signals": {
                    "registry_ready": True,
                    "monitor_ready": True,
                    "orchestrator_ready": True,
                },
                "safety_boundary": (
                    "Keep model names, versions, metadata, training configs, and "
                    "model objects out of thinking context."
                ),
            }
        )

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
                    "redact_model_names": True,
                    "redact_versions": True,
                    "redact_metadata": True,
                    "redact_model_objects": True,
                    "preserve_lifecycle_decision": True,
                },
                "safety_boundary": "Use hashes, counts, model types, and health bands.",
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
            "registry": self.registry.get_thinking_status(),
            "monitor": self.monitor.get_thinking_status(),
            "orchestrator": self.orchestrator.get_thinking_status(),
        }

    async def register_trained_model(
        self,
        name: str,
        version: str,
        model_type: str,
        model_obj: Any = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register trained model"""
        meta = ModelMetadata(
            name=name,
            version=version,
            model_type=model_type,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            **metadata or {},
        )

        self.registry.register_model(meta, model_obj)
        self._record_thinking(
            "mlops_model_registered",
            "Register trained model through MLOps manager",
            {
                "model_hash": _safe_hash(name),
                "version_hash": _safe_hash(version),
                "model_type": model_type,
                "metadata": _safe_mapping_summary(metadata),
            },
        )

    async def check_model_health(self, model_name: str) -> Dict[str, Any]:
        """Check model health"""
        versions = self.registry.get_model_versions(model_name)

        if not versions:
            self._record_thinking(
                "mlops_model_health",
                "Report missing model health target",
                {"model_hash": _safe_hash(model_name), "found": False},
            )
            return {"error": f"Model {model_name} not found"}

        latest_version = max(versions)
        history = self.registry.get_performance_history(model_name, limit=50)

        if not history:
            self._record_thinking(
                "mlops_model_health",
                "Report model health without performance data",
                {
                    "model_hash": _safe_hash(model_name),
                    "latest_version_hash": _safe_hash(latest_version),
                    "history_count_bucket": "0",
                },
            )
            return {"status": "no_data", "model": model_name}

        accuracies = [h["value"] for h in history if h["value"] is not None]

        health = {
            "model": model_name,
            "latest_version": latest_version,
            "status": "healthy" if accuracies and min(accuracies) > 0.7 else "warning",
            "current_accuracy": accuracies[-1] if accuracies else None,
            "avg_accuracy": float(np.mean(accuracies)) if accuracies else 0.0,
            "min_accuracy": float(np.min(accuracies)) if accuracies else 0.0,
            "trend": (
                "improving"
                if len(accuracies) > 1 and accuracies[-1] > accuracies[0]
                else "stable"
            ),
        }
        self._record_thinking(
            "mlops_model_health",
            "Evaluate model health from performance history",
            {
                "model_hash": _safe_hash(model_name),
                "latest_version_hash": _safe_hash(latest_version),
                "history_count_bucket": _safe_count_bucket(len(history)),
                "accuracy_count_bucket": _safe_count_bucket(len(accuracies)),
                "status": health["status"],
                "current_accuracy_band": _safe_number_band(health["current_accuracy"]),
            },
        )
        return health

    def get_system_stats(self) -> Dict[str, Any]:
        """Get overall MLOps statistics"""
        stats = {
            "registry": self.registry.get_stats(),
            "monitor": self.monitor.get_stats(),
            "orchestrator": self.orchestrator.get_stats(),
            "timestamp": datetime.now().isoformat(),
        }
        self._record_thinking(
            "mlops_system_stats",
            "Summarize MLOps system safely",
            {
                "registry_model_count_bucket": _safe_count_bucket(
                    stats["registry"]["models_count"]
                ),
                "monitor_alert_count_bucket": _safe_count_bucket(
                    stats["monitor"]["total_alerts"]
                ),
                "orchestrator_job_count_bucket": _safe_count_bucket(
                    stats["orchestrator"]["total_jobs"]
                ),
            },
        )
        return stats


# Example usage
async def example_mlops_workflow():
    """Example MLOps workflow"""
    manager = MLOpsManager()

    # Register model
    await manager.register_trained_model(
        name="anomaly_detector",
        version="1.0.0",
        model_type="anomaly",
        metadata={"framework": "pytorch", "parameters_count": 15000},
    )

    # Simulate predictions
    predictions = [
        {"score": 0.92},
        {"score": 0.88},
        {"score": 0.85},
    ]

    await manager.monitor.update_metrics(
        "anomaly_detector", "1.0.0", predictions
    )

    # Check model health
    health = await manager.check_model_health("anomaly_detector")
    print(f"Model health: {health}")

    return manager


if __name__ == "__main__":
    manager = MLOpsManager()
    print("MLOps Manager initialized")
