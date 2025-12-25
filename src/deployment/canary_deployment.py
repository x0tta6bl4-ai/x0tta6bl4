"""
Canary Deployment для x0tta6bl4.

Постепенный rollout новой версии:
- Canary: 1% трафика
- Gradual: 10% → 50% → 100%
- Автоматический rollback при проблемах
"""
import logging
import time
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class DeploymentStage(Enum):
    """Стадии deployment."""
    CANARY = "canary"  # 1% трафика
    GRADUAL_10 = "gradual_10"  # 10% трафика
    GRADUAL_50 = "gradual_50"  # 50% трафика
    FULL = "full"  # 100% трафика
    ROLLBACK = "rollback"  # Откат к предыдущей версии


@dataclass
class DeploymentConfig:
    """Конфигурация deployment."""
    canary_percentage: float = 1.0  # 1% трафика
    gradual_stages: List[float] = None  # [10.0, 50.0, 100.0]
    stage_duration: float = 3600.0  # 1 час на стадию
    health_check_interval: float = 60.0  # 1 минута
    rollback_threshold: float = 0.95  # 95% success rate для продолжения
    max_errors_per_minute: int = 10  # Максимум ошибок в минуту


@dataclass
class DeploymentMetrics:
    """Метрики deployment."""
    stage: DeploymentStage
    traffic_percentage: float
    requests_total: int = 0
    requests_success: int = 0
    requests_error: int = 0
    errors_per_minute: float = 0.0
    success_rate: float = 1.0
    start_time: float = 0.0
    duration: float = 0.0


class CanaryDeployment:
    """
    Canary Deployment Manager.
    
    Управляет постепенным rollout новой версии с автоматическим rollback.
    """
    
    def __init__(
        self,
        config: Optional[DeploymentConfig] = None,
        health_check_fn: Optional[Callable[[], bool]] = None,
        metrics_collector: Optional[Callable[[], Dict[str, Any]]] = None
    ):
        """
        Инициализация Canary Deployment.
        
        Args:
            config: Конфигурация deployment
            health_check_fn: Функция для health check
            metrics_collector: Функция для сбора метрик
        """
        self.config = config or DeploymentConfig()
        if self.config.gradual_stages is None:
            self.config.gradual_stages = [10.0, 50.0, 100.0]
        
        self.health_check_fn = health_check_fn
        self.metrics_collector = metrics_collector
        
        # Current stage
        self.current_stage = DeploymentStage.CANARY
        self.current_traffic_percentage = self.config.canary_percentage
        
        # Metrics
        self.metrics = DeploymentMetrics(
            stage=self.current_stage,
            traffic_percentage=self.current_traffic_percentage,
            start_time=time.time()
        )
        
        # Stage history
        self.stage_history: List[DeploymentMetrics] = []
        
        # Running state
        self._running = False
        self._rollback_triggered = False
        
        logger.info(
            f"✅ Canary Deployment initialized: "
            f"canary={self.config.canary_percentage}%, "
            f"stages={self.config.gradual_stages}%"
        )
    
    def start(self):
        """Start canary deployment."""
        self._running = True
        self.current_stage = DeploymentStage.CANARY
        self.current_traffic_percentage = self.config.canary_percentage
        self.metrics.start_time = time.time()
        
        logger.info(f"🚀 Canary deployment started: {self.current_traffic_percentage}% traffic")
    
    def stop(self):
        """Stop deployment."""
        self._running = False
        logger.info("🛑 Canary deployment stopped")
    
    def should_route_to_new_version(self) -> bool:
        """
        Определить, следует ли направлять трафик на новую версию.
        
        Returns:
            True если трафик должен идти на новую версию
        """
        if not self._running:
            return False
        
        if self._rollback_triggered:
            return False
        
        # Simple percentage-based routing
        import random
        return random.random() * 100 < self.current_traffic_percentage
    
    def record_request(self, success: bool):
        """Записать результат запроса."""
        self.metrics.requests_total += 1
        
        if success:
            self.metrics.requests_success += 1
        else:
            self.metrics.requests_error += 1
        
        # Update success rate
        if self.metrics.requests_total > 0:
            self.metrics.success_rate = (
                self.metrics.requests_success / self.metrics.requests_total
            )
        
        # Check if rollback needed
        self._check_rollback_conditions()
    
    def _check_rollback_conditions(self):
        """Проверить условия для rollback."""
        # Check success rate
        if self.metrics.success_rate < self.config.rollback_threshold:
            logger.error(
                f"🔴 Success rate below threshold: "
                f"{self.metrics.success_rate:.2%} < {self.config.rollback_threshold:.2%}"
            )
            self._trigger_rollback("low_success_rate")
            return
        
        # Check errors per minute
        if self.metrics.errors_per_minute > self.config.max_errors_per_minute:
            logger.error(
                f"🔴 Errors per minute too high: "
                f"{self.metrics.errors_per_minute:.1f} > {self.config.max_errors_per_minute}"
            )
            self._trigger_rollback("high_error_rate")
            return
        
        # Check health
        if self.health_check_fn and not self.health_check_fn():
            logger.error("🔴 Health check failed")
            self._trigger_rollback("health_check_failed")
            return
    
    def _trigger_rollback(self, reason: str):
        """Триггер rollback."""
        if self._rollback_triggered:
            return
        
        self._rollback_triggered = True
        self.current_stage = DeploymentStage.ROLLBACK
        self.current_traffic_percentage = 0.0
        
        logger.critical(f"🔴 ROLLBACK TRIGGERED: {reason}")
        # TODO: Integrate with deployment system to actually rollback
    
    def advance_stage(self) -> bool:
        """
        Перейти к следующей стадии deployment.
        
        Returns:
            True если стадия изменена, False если уже на последней стадии
        """
        if self._rollback_triggered:
            return False
        
        # Save current metrics
        self.metrics.duration = time.time() - self.metrics.start_time
        self.stage_history.append(self.metrics)
        
        # Advance to next stage
        if self.current_stage == DeploymentStage.CANARY:
            if self.config.gradual_stages:
                self.current_stage = DeploymentStage.GRADUAL_10
                self.current_traffic_percentage = self.config.gradual_stages[0]
                logger.info(f"📈 Advanced to {self.current_traffic_percentage}% traffic")
                return True
        
        elif self.current_stage == DeploymentStage.GRADUAL_10:
            if len(self.config.gradual_stages) > 1:
                self.current_stage = DeploymentStage.GRADUAL_50
                self.current_traffic_percentage = self.config.gradual_stages[1]
                logger.info(f"📈 Advanced to {self.current_traffic_percentage}% traffic")
                return True
        
        elif self.current_stage == DeploymentStage.GRADUAL_50:
            if len(self.config.gradual_stages) > 2:
                self.current_stage = DeploymentStage.FULL
                self.current_traffic_percentage = self.config.gradual_stages[2]
                logger.info(f"📈 Advanced to {self.current_traffic_percentage}% traffic (FULL)")
                return True
        
        # Already at full deployment
        return False
    
    def get_deployment_status(self) -> Dict[str, Any]:
        """Получить статус deployment."""
        return {
            "stage": self.current_stage.value,
            "traffic_percentage": self.current_traffic_percentage,
            "running": self._running,
            "rollback_triggered": self._rollback_triggered,
            "metrics": {
                "requests_total": self.metrics.requests_total,
                "requests_success": self.metrics.requests_success,
                "requests_error": self.metrics.requests_error,
                "success_rate": self.metrics.success_rate,
                "errors_per_minute": self.metrics.errors_per_minute,
                "duration_seconds": time.time() - self.metrics.start_time
            },
            "stage_history": [
                {
                    "stage": m.stage.value,
                    "traffic_percentage": m.traffic_percentage,
                    "success_rate": m.success_rate,
                    "duration": m.duration
                }
                for m in self.stage_history
            ]
        }

