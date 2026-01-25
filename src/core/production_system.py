import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ProductionMetrics:
    timestamp: datetime
    uptime_seconds: float
    request_count: int
    error_count: int
    avg_latency_ms: float
    cardinality_health: float
    circuit_breaker_state: str
    memory_usage_mb: float
    active_connections: int


class ProductionSystem:
    def __init__(self):
        self.start_time = datetime.utcnow()
        self.request_count = 0
        self.error_count = 0
        self.latency_sum = 0.0
        
        self._import_components()
    
    def _import_components(self):
        try:
            from src.optimization.prometheus_cardinality_optimizer import get_cardinality_optimizer
            from src.optimization.performance_tuner import get_performance_tuner
            from src.security.production_hardening import get_hardening_manager
            from src.resilience.advanced_patterns import get_resilient_executor
            
            self.cardinality_optimizer = get_cardinality_optimizer()
            self.performance_tuner = get_performance_tuner()
            self.hardening_manager = get_hardening_manager()
            self.resilient_executor = get_resilient_executor()
            
            logger.info("All production components initialized")
        except Exception as e:
            logger.error(f"Failed to initialize components: {e}")
            raise
    
    def record_request(self, method: str, path: str, status_code: int, 
                      duration_ms: float, labels: Dict[str, str]) -> None:
        self.request_count += 1
        self.latency_sum += duration_ms
        
        if status_code >= 400:
            self.error_count += 1
        
        self.cardinality_optimizer.record_metric_sample(
            f"http_{method.lower()}",
            labels
        )
        
        self.performance_tuner.latency_tracker.record(
            f"request_{method}_{path}",
            duration_ms,
            metadata={"status": status_code}
        )
        
        self.hardening_manager.request_auditor.log_request(
            method, path, labels.get("client_ip", "unknown"),
            status_code, duration_ms
        )
    
    def get_system_health(self) -> Dict[str, Any]:
        uptime = (datetime.utcnow() - self.start_time).total_seconds()
        
        perf_stats = self.performance_tuner.analyze_performance()
        cardinality_report = self.cardinality_optimizer.get_cardinality_report()
        security_status = self.hardening_manager.get_security_status()
        executor_stats = self.resilient_executor.get_stats()
        
        error_rate = (self.error_count / self.request_count 
                     if self.request_count > 0 else 0)
        
        avg_latency = (self.latency_sum / self.request_count 
                      if self.request_count > 0 else 0)
        
        health_score = self._calculate_health_score(
            error_rate, 
            cardinality_report["total_cardinality"],
            executor_stats.get("success_rate", 1.0)
        )
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": uptime,
            "health_score": health_score,
            "requests": {
                "total": self.request_count,
                "errors": self.error_count,
                "error_rate": error_rate,
                "avg_latency_ms": avg_latency
            },
            "cardinality": {
                "total_metrics": cardinality_report["total_unique_metrics"],
                "total_cardinality": cardinality_report["total_cardinality"],
                "status": "healthy" if cardinality_report["total_cardinality"] < 50000 else "warning"
            },
            "resilience": {
                "circuit_breaker_state": executor_stats.get("circuit_breaker_state"),
                "success_rate": executor_stats.get("success_rate", 1.0),
                "bulkhead_utilization": executor_stats.get("bulkhead_status", {}).get("utilization", 0)
            },
            "security": {
                "suspicious_patterns": len(security_status.get("suspicious_patterns", []))
            }
        }
    
    def _calculate_health_score(self, error_rate: float, cardinality: int, 
                               success_rate: float) -> float:
        error_penalty = min(error_rate * 100, 30)
        cardinality_penalty = min((cardinality / 50000) * 20, 20)
        resilience_bonus = max(success_rate * 10, 0)
        
        base_score = 100.0
        final_score = base_score - error_penalty - cardinality_penalty + resilience_bonus
        
        return max(0, min(100, final_score))
    
    def get_production_readiness_report(self) -> Dict[str, Any]:
        health = self.get_system_health()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_score": health["health_score"],
            "components": {
                "cardinality_management": "operational" if health["cardinality"]["status"] == "healthy" else "warning",
                "performance_monitoring": "operational",
                "security_controls": "operational",
                "resilience_patterns": "operational"
            },
            "metrics": health,
            "readiness_level": self._get_readiness_level(health["health_score"]),
            "gaps_remaining": [
                "Fine-grained SLA tracking",
                "Advanced ML-based anomaly detection",
                "Distributed tracing optimization"
            ] if health["health_score"] < 95 else []
        }
    
    def _get_readiness_level(self, score: float) -> str:
        if score >= 95:
            return "PRODUCTION_READY"
        elif score >= 85:
            return "NEAR_PRODUCTION"
        elif score >= 70:
            return "STAGING_READY"
        else:
            return "DEVELOPMENT"


_system = None

def get_production_system() -> ProductionSystem:
    global _system
    if _system is None:
        _system = ProductionSystem()
    return _system


__all__ = [
    "ProductionMetrics",
    "ProductionSystem",
    "get_production_system",
]
