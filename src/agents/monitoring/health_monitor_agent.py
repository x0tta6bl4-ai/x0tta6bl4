# 🤖 Health Monitor Agent - x0tta6bl4
"""
Health Monitor Agent - 24/7 мониторинг системы с автоматическими алертами.
Интегрируется с Prometheus, анализирует метрики и обнаруживает аномалии.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Статус здоровья сервиса."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class AlertSeverity(Enum):
    """Уровень серьёзности алерта."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class HealthCheckResult:
    """Результат проверки здоровья."""
    service_name: str
    status: HealthStatus
    timestamp: datetime
    response_time_ms: float
    details: dict = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class Alert:
    """Алерт, сгенерированный агентом."""
    id: str
    severity: AlertSeverity
    service_name: str
    message: str
    timestamp: datetime
    metadata: dict = field(default_factory=dict)
    resolved: bool = False


class HealthMonitorAgent:
    """
    Health Monitor Agent для x0tta6bl4.
    
    Обеспечивает 24/7 мониторинг с автоматическими алертами.
    Использует MAPE-K loop для анализа и планирования действий.
    """
    
    def __init__(self, config: Optional[dict] = None):
        """
        Инициализация Health Monitor Agent.
        
        Args:
            config: Конфигурация агента
        """
        self.config = config or self._default_config()
        
        # Services для мониторинга
        self.services: dict[str, str] = self.config.get("services", {})
        
        # Health check history
        self.health_history: list[HealthCheckResult] = []
        self.max_history = self.config.get("max_history", 1000)
        
        # Alerts
        self.active_alerts: list[Alert] = []
        self.alert_callbacks: list[callable] = []
        
        # Monitoring state
        self.is_running = False
        self.last_check_time: Optional[datetime] = None
        
        # Thresholds
        self.response_time_threshold_ms = self.config.get("response_time_threshold_ms", 1000)
        self.unhealthy_threshold = self.config.get("unhealthy_threshold", 3)
        
        logger.info("Health Monitor Agent initialized")
    
    def _default_config(self) -> dict:
        """Дефолтная конфигурация."""
        return {
            "check_interval_seconds": 30,
            "response_time_threshold_ms": 1000,
            "unhealthy_threshold": 3,
            "max_history": 1000,
            "services": {
                "api": "http://localhost:8080/health",
                "database": "http://localhost:5432/health",
                "mesh": "http://localhost:9090/health",
                "prometheus": "http://localhost:9090/-/healthy",
            },
            "alert_cooldown_seconds": 300,
        }
    
    async def start(self) -> None:
        """Запуск мониторинга."""
        self.is_running = True
        logger.info("Health Monitor Agent started")
        
        while self.is_running:
            try:
                await self._monitoring_cycle()
                await asyncio.sleep(self.config["check_interval_seconds"])
            except Exception as e:
                logger.error(f"Error in monitoring cycle: {e}")
                await asyncio.sleep(5)
    
    async def stop(self) -> None:
        """Остановка мониторинга."""
        self.is_running = False
        logger.info("Health Monitor Agent stopped")
    
    async def _monitoring_cycle(self) -> None:
        """Один цикл мониторинга всех сервисов."""
        self.last_check_time = datetime.utcnow()
        
        # Параллельная проверка всех сервисов
        tasks = [
            self._check_service(name, url)
            for name, url in self.services.items()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Обработка результатов
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Health check failed: {result}")
            elif result:
                await self._process_health_result(result)
    
    async def _check_service(self, name: str, url: str) -> Optional[HealthCheckResult]:
        """
        Проверка здоровья одного сервиса.
        
        Args:
            name: Имя сервиса
            url: URL для проверки
            
        Returns:
            HealthCheckResult или None при ошибке
        """
        start_time = time.time()
        
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    response_time_ms = (time.time() - start_time) * 1000
                    
                    if response.status == 200:
                        status = HealthStatus.HEALTHY
                    elif response.status < 500:
                        status = HealthStatus.DEGRADED
                    else:
                        status = HealthStatus.UNHEALTHY
                    
                    return HealthCheckResult(
                        service_name=name,
                        status=status,
                        timestamp=datetime.utcnow(),
                        response_time_ms=response_time_ms,
                        details={"status_code": response.status},
                    )
        except asyncio.TimeoutError:
            return HealthCheckResult(
                service_name=name,
                status=HealthStatus.UNHEALTHY,
                timestamp=datetime.utcnow(),
                response_time_ms=(time.time() - start_time) * 1000,
                error="Timeout",
            )
        except Exception as e:
            return HealthCheckResult(
                service_name=name,
                status=HealthStatus.UNHEALTHY,
                timestamp=datetime.utcnow(),
                response_time_ms=(time.time() - start_time) * 1000,
                error=str(e),
            )
    
    async def _process_health_result(self, result: HealthCheckResult) -> None:
        """
        Обработка результата проверки здоровья.
        
        Args:
            result: Результат проверки
        """
        # Сохранение в историю
        self.health_history.append(result)
        if len(self.health_history) > self.max_history:
            self.health_history.pop(0)
        
        # Проверка порогов
        if result.response_time_ms > self.response_time_threshold_ms:
            await self._create_alert(
                severity=AlertSeverity.WARNING,
                service_name=result.service_name,
                message=f"High response time: {result.response_time_ms:.0f}ms",
                metadata={"response_time_ms": result.response_time_ms},
            )
        
        if result.status == HealthStatus.UNHEALTHY:
            await self._create_alert(
                severity=AlertSeverity.CRITICAL,
                service_name=result.service_name,
                message=f"Service unhealthy: {result.error or 'Unknown error'}",
                metadata={"status": result.status.value, "error": result.error},
            )
    
    async def _analyze_with_mape_k(self) -> None:
        """Анализ через MAPE-K loop (упрощённая версия)."""
        # Подготовка данных для анализа
        {
            "health_history": self._get_recent_health_summary(),
            "active_alerts": len(self.active_alerts),
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        # Простой анализ паттернов
        recent = self.health_history[-100:]
        if not recent:
            return
            
        # Проверка на деградацию
        by_service: dict[str, list] = {}
        for r in recent:
            if r.service_name not in by_service:
                by_service[r.service_name] = []
            by_service[r.service_name].append(r)
        
        for service, results in by_service.items():
            if len(results) < 3:
                continue
            
            # Проверяем тренд response time
            avg_recent = sum(r.response_time_ms for r in results[-3:]) / 3
            avg_older = sum(r.response_time_ms for r in results[:-3]) / max(1, len(results) - 3)
            
            if avg_recent > avg_older * 1.5:
                await self._create_alert(
                    severity=AlertSeverity.WARNING,
                    service_name=service,
                    message=f"Response time degradation: {avg_recent:.0f}ms vs {avg_older:.0f}ms",
                    metadata={"recent_avg": avg_recent, "older_avg": avg_older},
                )
    
    def _get_recent_health_summary(self) -> dict:
        """Получение сводки по недавним проверкам."""
        if not self.health_history:
            return {}
        
        recent = self.health_history[-100:]
        by_service: dict[str, list] = {}
        
        for result in recent:
            if result.service_name not in by_service:
                by_service[result.service_name] = []
            by_service[result.service_name].append(result)
        
        summary = {}
        for service, results in by_service.items():
            healthy_count = sum(1 for r in results if r.status == HealthStatus.HEALTHY)
            avg_response = sum(r.response_time_ms for r in results) / len(results)
            summary[service] = {
                "healthy_ratio": healthy_count / len(results),
                "avg_response_time_ms": avg_response,
            }
        
        return summary
    
    async def _create_alert(
        self,
        severity: AlertSeverity,
        service_name: str,
        message: str,
        metadata: dict,
    ) -> None:
        """
        Создание алерта.
        
        Args:
            severity: Уровень серьёзности
            service_name: Имя сервиса
            message: Сообщение
            metadata: Дополнительные данные
        """
        # Проверка cooldown
        for alert in self.active_alerts:
            if (
                alert.service_name == service_name
                and alert.severity == severity
                and (datetime.utcnow() - alert.timestamp).total_seconds()
                < self.config["alert_cooldown_seconds"]
            ):
                return  # Too soon for another alert
        
        alert = Alert(
            id=f"alert-{datetime.utcnow().timestamp()}",
            severity=severity,
            service_name=service_name,
            message=message,
            timestamp=datetime.utcnow(),
            metadata=metadata,
        )
        
        self.active_alerts.append(alert)
        logger.warning(f"Alert created: {alert.severity.value} - {alert.message}")
        
        # Уведомление подписчиков
        for callback in self.alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert)
                else:
                    callback(alert)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")
    
    def register_alert_callback(self, callback: callable) -> None:
        """Регистрация callback для алертов."""
        self.alert_callbacks.append(callback)
    
    async def get_health_status(self) -> dict:
        """Получение текущего статуса здоровья."""
        return {
            "is_running": self.is_running,
            "last_check": self.last_check_time.isoformat() if self.last_check_time else None,
            "services": self._get_recent_health_summary(),
            "active_alerts": len(self.active_alerts),
            "alert_details": [
                {
                    "id": a.id,
                    "severity": a.severity.value,
                    "service": a.service_name,
                    "message": a.message,
                    "timestamp": a.timestamp.isoformat(),
                }
                for a in self.active_alerts[-10:]
            ],
        }
    
    async def resolve_alert(self, alert_id: str) -> bool:
        """Разрешение алерта."""
        for alert in self.active_alerts:
            if alert.id == alert_id:
                alert.resolved = True
                self.active_alerts.remove(alert)
                logger.info(f"Alert resolved: {alert_id}")
                return True
        return False
    
    def add_service(self, name: str, url: str) -> None:
        """Добавление сервиса для мониторинга."""
        self.services[name] = url
        logger.info(f"Added service for monitoring: {name} -> {url}")
    
    def remove_service(self, name: str) -> None:
        """Удаление сервиса из мониторинга."""
        if name in self.services:
            del self.services[name]
            logger.info(f"Removed service from monitoring: {name}")


# Синглтон экземпляр
_health_monitor_instance: Optional[HealthMonitorAgent] = None


async def get_health_monitor() -> HealthMonitorAgent:
    """Получение синглтона Health Monitor Agent."""
    global _health_monitor_instance
    if _health_monitor_instance is None:
        _health_monitor_instance = HealthMonitorAgent()
    return _health_monitor_instance
