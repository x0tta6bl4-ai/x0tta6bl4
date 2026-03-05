# 🤖 Auto-Healer Agent - x0tta6bl4
"""
Auto-Healer Agent - автоматическое восстановление сервисов.
Интегрируется с MAPE-K loop и RecoveryActionExecutor.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from src.self_healing.mape_k import SelfHealingManager
from src.self_healing.recovery_actions import (
    CircuitBreaker,
    RateLimiter,
    RecoveryActionExecutor,
    RecoveryActionType,
    RecoveryResult,
)

logger = logging.getLogger(__name__)


class HealingStatus(Enum):
    """Статус восстановления."""
    IDLE = "idle"
    DETECTING = "detecting"
    HEALING = "healing"
    RECOVERED = "recovered"
    FAILED = "failed"


class HealingAction(Enum):
    """Действия по восстановлению."""
    RESTART_SERVICE = "restart_service"
    SWITCH_ROUTE = "switch_route"
    CLEAR_CACHE = "clear_cache"
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    FAILOVER = "failover"
    QUARANTINE_NODE = "quarantine_node"
    SWITCH_PROTOCOL = "switch_protocol"
    EXECUTE_SCRIPT = "execute_script"


@dataclass
class HealingIncident:
    """Инцидент, требующий восстановления."""
    id: str
    issue: str
    detected_at: datetime
    action_taken: Optional[str] = None
    status: HealingStatus = HealingStatus.IDLE
    success: Optional[bool] = None
    mttr_seconds: Optional[float] = None
    details: dict = field(default_factory=dict)


@dataclass
class HealingMetrics:
    """Метрики для принятия решений о восстановлении."""
    cpu_percent: float
    memory_percent: float
    packet_loss_percent: float
    latency_ms: float
    error_rate: float
    healthy_nodes: int
    total_nodes: int


class AutoHealerAgent:
    """
    Auto-Healer Agent для x0tta6bl4.
    
    Автоматически восстанавливает сервисы при обнаружении проблем.
    Использует MAPE-K loop для анализа и выбора стратегии восстановления.
    """
    
    def __init__(self, config: Optional[dict] = None):
        """
        Инициализация Auto-Healer Agent.
        
        Args:
            config: Конфигурация агента
        """
        self.config = config or self._default_config()
        
        # MAPE-K self-healing manager
        self.mape_k = SelfHealingManager()
        
        # Recovery action executor
        self.recovery_executor = RecoveryActionExecutor()
        
        # Circuit breaker и rate limiter
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=self.config.get("circuit_breaker_threshold", 5),
            timeout=self.config.get("circuit_breaker_timeout_seconds", 60),
        )
        self.rate_limiter = RateLimiter(
            max_actions=self.config.get("max_actions_per_minute", 10),
            window_seconds=60,
        )
        
        # State
        self.status = HealingStatus.IDLE
        self.current_incident: Optional[HealingIncident] = None
        self.incident_history: list[HealingIncident] = []
        
        # Thresholds
        self.cpu_threshold = self.config.get("cpu_threshold", 90.0)
        self.memory_threshold = self.config.get("memory_threshold", 85.0)
        self.packet_loss_threshold = self.config.get("packet_loss_threshold", 5.0)
        
        logger.info("Auto-Healer Agent initialized")
    
    def _default_config(self) -> dict:
        """Дефолтная конфигурация."""
        return {
            "enabled": True,
            "cpu_threshold": 90.0,
            "memory_threshold": 85.0,
            "packet_loss_threshold": 5.0,
            "circuit_breaker_threshold": 5,
            "circuit_breaker_timeout_seconds": 60,
            "max_actions_per_minute": 10,
            "auto_heal_enabled": True,
            "max_retries": 3,
        }
    
    async def start(self) -> None:
        """Запуск Auto-Healer Agent."""
        logger.info("Auto-Healer Agent started")
        self.status = HealingStatus.IDLE
        
        while self.config.get("enabled", True):
            try:
                # Check circuit breaker
                if self.circuit_breaker.state.state == "open":
                    logger.warning("Circuit breaker is OPEN, skipping healing cycle")
                    await asyncio.sleep(10)
                    continue
                
                # Check rate limiter
                if not self.rate_limiter.allow():
                    logger.warning("Rate limit exceeded, skipping healing cycle")
                    await asyncio.sleep(10)
                    continue
                
                # Run healing cycle
                await self._healing_cycle()
                
                await asyncio.sleep(self.config.get("check_interval_seconds", 30))
            except Exception as e:
                logger.error(f"Error in healing cycle: {e}")
                await asyncio.sleep(5)
    
    async def stop(self) -> None:
        """Остановка Auto-Healer Agent."""
        self.config["enabled"] = False
        logger.info("Auto-Healer Agent stopped")
    
    async def _healing_cycle(self) -> None:
        """Один цикл проверки и восстановления."""
        # Get current metrics
        metrics = await self._collect_metrics()
        
        # Run MAPE-K cycle
        self.mape_k.run_cycle(metrics)
        
        # Check if healing is needed
        if self._needs_healing(metrics):
            self.status = HealingStatus.HEALING
            await self._perform_healing(metrics)
        else:
            self.status = HealingStatus.IDLE
    
    async def _collect_metrics(self) -> dict:
        """Сбор метрик системы."""
        # В реальной реализации здесь был бы сбор метрик из разных источников
        # Для демонстрации возвращаем mock данные
        
        return {
            "cpu_percent": 0.0,  # Will be populated from real system
            "memory_percent": 0.0,
            "packet_loss_percent": 0.0,
            "latency_ms": 0.0,
            "error_rate": 0.0,
            "node_id": "auto-healer",
        }
    
    def _needs_healing(self, metrics: dict) -> bool:
        """Определение необходимости восстановления."""
        cpu = metrics.get("cpu_percent", 0)
        memory = metrics.get("memory_percent", 0)
        packet_loss = metrics.get("packet_loss_percent", 0)
        
        return (
            cpu > self.cpu_threshold
            or memory > self.memory_threshold
            or packet_loss > self.packet_loss_threshold
        )
    
    async def _perform_healing(self, metrics: dict) -> None:
        """Выполнение восстановления."""
        start_time = datetime.utcnow()
        
        # Create incident
        incident = HealingIncident(
            id=f"incident-{int(start_time.timestamp())}",
            issue=self._diagnose_issue(metrics),
            detected_at=start_time,
            status=HealingStatus.HEALING,
        )
        self.current_incident = incident
        
        # Determine action based on issue
        action = self._determine_action(incident.issue)
        
        try:
            # Execute recovery action
            result = await self._execute_recovery_action(action, metrics)
            
            # Update incident
            incident.action_taken = action
            incident.status = HealingStatus.RECOVERED if result.success else HealingStatus.FAILED
            incident.success = result.success
            incident.mttr_seconds = (datetime.utcnow() - start_time).total_seconds()
            incident.details = {
                "action": action,
                "result": result.__dict__,
            }
            
            # Update circuit breaker
            if result.success:
                self.circuit_breaker._on_success()
            else:
                self.circuit_breaker._on_failure()
            
            logger.info(
                f"Healing completed: {incident.issue} -> {action}, "
                f"success={result.success}, mttr={incident.mttr_seconds:.2f}s"
            )
            
        except Exception as e:
            incident.status = HealingStatus.FAILED
            incident.success = False
            incident.details = {"error": str(e)}
            self.circuit_breaker._on_failure()
            logger.error(f"Healing failed: {e}")
        
        # Save to history
        self.incident_history.append(incident)
        self.current_incident = None
        
        # Keep only last 1000 incidents
        if len(self.incident_history) > 1000:
            self.incident_history = self.incident_history[-1000:]
    
    def _diagnose_issue(self, metrics: dict) -> str:
        """Диагностика проблемы на основе метрик."""
        cpu = metrics.get("cpu_percent", 0)
        memory = metrics.get("memory_percent", 0)
        packet_loss = metrics.get("packet_loss_percent", 0)
        
        if cpu > self.cpu_threshold:
            return "High CPU"
        elif memory > self.memory_threshold:
            return "High Memory"
        elif packet_loss > self.packet_loss_threshold:
            return "Network Loss"
        else:
            return "Unknown"
    
    def _determine_action(self, issue: str) -> str:
        """Определение действия для проблемы."""
        action_map = {
            "High CPU": "Restart service",
            "High Memory": "Clear cache",
            "Network Loss": "Switch route",
            "Predicted Peak": "Scale up",
        }
        
        return action_map.get(issue, "No action needed")
    
    async def _execute_recovery_action(self, action: str, context: dict) -> RecoveryResult:
        """Выполнение действия восстановления."""
        action_type = self._parse_action_type(action)
        
        # Build context
        ctx = {
            "service_name": context.get("service_name", "x0tta6bl4"),
            "node_id": context.get("node_id", "default"),
        }
        
        # Execute via recovery executor
        success = self.recovery_executor.execute(action, ctx)
        
        return RecoveryResult(
            success=success,
            action_type=action_type,
            duration_seconds=0.0,
        )
    
    def _parse_action_type(self, action: str) -> RecoveryActionType:
        """Парсинг типа действия."""
        action_lower = action.lower()
        
        if "restart" in action_lower:
            return RecoveryActionType.RESTART_SERVICE
        elif "route" in action_lower or "switch" in action_lower:
            return RecoveryActionType.SWITCH_ROUTE
        elif "cache" in action_lower:
            return RecoveryActionType.CLEAR_CACHE
        elif "scale up" in action_lower:
            return RecoveryActionType.SCALE_UP
        elif "scale down" in action_lower:
            return RecoveryActionType.SCALE_DOWN
        elif "failover" in action_lower:
            return RecoveryActionType.FAILOVER
        elif "quarantine" in action_lower:
            return RecoveryActionType.QUARANTINE_NODE
        elif "protocol" in action_lower:
            return RecoveryActionType.SWITCH_PROTOCOL
        else:
            return RecoveryActionType.NO_ACTION
    
    async def heal_now(self, issue: str, context: Optional[dict] = None) -> bool:
        """
        Принудительный запуск восстановления для указанной проблемы.
        
        Args:
            issue: Описание проблемы
            context: Дополнительный контекст
            
        Returns:
            True если восстановление успешно
        """
        logger.info(f"Manual healing triggered for: {issue}")
        
        context = context or {}
        action = self._determine_action(issue)
        
        if action == "No action needed":
            return True
        
        result = await self._execute_recovery_action(action, context)
        return result.success
    
    async def get_status(self) -> dict:
        """Получение текущего статуса."""
        return {
            "status": self.status.value,
            "current_incident": (
                {
                    "id": self.current_incident.id,
                    "issue": self.current_incident.issue,
                    "status": self.current_incident.status.value,
                    "action": self.current_incident.action_taken,
                }
                if self.current_incident
                else None
            ),
            "circuit_breaker": {
                "state": self.circuit_breaker.state.state,
                "failures": self.circuit_breaker.state.failures,
            },
            "recent_incidents": [
                {
                    "id": i.id,
                    "issue": i.issue,
                    "status": i.status.value,
                    "success": i.success,
                    "mttr_seconds": i.mttr_seconds,
                }
                for i in self.incident_history[-10:]
            ],
            "stats": {
                "total_incidents": len(self.incident_history),
                "successful_heals": sum(1 for i in self.incident_history if i.success),
                "failed_heals": sum(1 for i in self.incident_history if i.success is False),
            },
        }
    
    def update_thresholds(
        self,
        cpu_threshold: Optional[float] = None,
        memory_threshold: Optional[float] = None,
        packet_loss_threshold: Optional[float] = None,
    ) -> None:
        """Обновление пороговых значений."""
        if cpu_threshold is not None:
            self.cpu_threshold = cpu_threshold
        if memory_threshold is not None:
            self.memory_threshold = memory_threshold
        if packet_loss_threshold is not None:
            self.packet_loss_threshold = packet_loss_threshold
        
        logger.info(
            f"Thresholds updated: CPU={self.cpu_threshold}, "
            f"Memory={self.memory_threshold}, PacketLoss={self.packet_loss_threshold}"
        )


# Синглтон экземпляр
_auto_healer_instance: Optional[AutoHealerAgent] = None


async def get_auto_healer() -> AutoHealerAgent:
    """Получение синглтона Auto-Healer Agent."""
    global _auto_healer_instance
    if _auto_healer_instance is None:
        _auto_healer_instance = AutoHealerAgent()
    return _auto_healer_instance
