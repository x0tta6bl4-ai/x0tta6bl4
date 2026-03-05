# 🤖 AI Agents Orchestrator - x0tta6bl4
"""
Orchestrator for AI Agents - координирует работу всех агентов.

SECURITY: Rate limiting is enforced to prevent agent spam/abuse.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

from src.agents.monitoring import (
    Alert,
    HealthMonitorAgent,
    get_health_monitor,
)
from src.agents.logging import (
    LogAnalyzerAgent,
    get_log_analyzer,
)
from src.agents.healing import (
    AutoHealerAgent,
    get_auto_healer,
)
from src.agents.development import (
    SpecToCodeAgent,
    DocumentationAgent,
    get_spec_to_code_agent,
    get_documentation_agent,
)

logger = logging.getLogger(__name__)


@dataclass
class AgentStatus:
    """Статус всех агентов."""
    health_monitor: bool = False
    log_analyzer: bool = False
    auto_healer: bool = False
    spec_to_code: bool = False
    documentation: bool = False
    last_sync: Optional[datetime] = None


class AgentOrchestrator:
    """
    Orchestrator для AI Agents x0tta6bl4.
    
    Координирует работу всех агентов:
    - Health Monitor → Auto-Healer (alerts)
    - Log Analyzer → Auto-Healer (issues)
    - Development Agents (on-demand)
    """
    
    def __init__(self, config: Optional[dict] = None):
        """
        Инициализация Orchestrator.
        
        Args:
            config: Конфигурация
        """
        self.config = config or self._default_config()
        
        # Agents
        self.health_monitor: Optional[HealthMonitorAgent] = None
        self.log_analyzer: Optional[LogAnalyzerAgent] = None
        self.auto_healer: Optional[AutoHealerAgent] = None
        self.spec_to_code: Optional[SpecToCodeAgent] = None
        self.documentation: Optional[DocumentationAgent] = None
        
        # Status
        self.status = AgentStatus()
        
        # Running state
        self.is_running = False
        
        # Rate limiting for agent actions
        self._action_timestamps: dict[str, list[float]] = {}
        self._rate_limit_actions_per_minute = config.get("rate_limit_per_minute", 60)
        self._rate_limit_window_seconds = config.get("rate_limit_window", 60)
        
        logger.info("Agent Orchestrator initialized")
    
    def _default_config(self) -> dict:
        """Дефолтная конфигурация."""
        return {
            "enable_health_monitor": True,
            "enable_log_analyzer": True,
            "enable_auto_healer": True,
            "health_check_interval": 30,
            "log_analysis_interval": 60,
            "sync_interval": 300,
            "rate_limit_per_minute": 60,
            "rate_limit_window": 60,
        }
    
    def _check_rate_limit(self, action_type: str) -> bool:
        """
        Check if action is within rate limit.
        
        Args:
            action_type: Type of action to check
            
        Returns:
            True if allowed, False if rate limited
        """
        now = time.time()
        window_start = now - self._rate_limit_window_seconds
        
        # Get or initialize timestamps for this action type
        if action_type not in self._action_timestamps:
            self._action_timestamps[action_type] = []
        
        # Filter to only recent timestamps
        self._action_timestamps[action_type] = [
            ts for ts in self._action_timestamps[action_type]
            if ts > window_start
        ]
        
        # Check if under limit
        if len(self._action_timestamps[action_type]) >= self._rate_limit_actions_per_minute:
            logger.warning(f"Rate limit exceeded for action: {action_type}")
            return False
        
        # Add current timestamp
        self._action_timestamps[action_type].append(now)
        return True
    
    async def execute_action(self, action_type: str, action_fn, *args, **kwargs) -> Any:
        """
        Execute action with rate limiting.
        
        Args:
            action_type: Type of action for rate limiting
            action_fn: Async function to execute
            *args, **kwargs: Arguments to pass to action_fn
            
        Returns:
            Result of action_fn or None if rate limited
        """
        if not self._check_rate_limit(action_type):
            logger.warning(f"Action {action_type} rate limited, skipping")
            return None
        
        try:
            return await action_fn(*args, **kwargs)
        except Exception as e:
            logger.error(f"Action {action_type} failed: {e}")
            raise
    
    async def initialize(self) -> None:
        """Инициализация всех агентов."""
        logger.info("Initializing AI Agents...")
        
        # Initialize Health Monitor
        if self.config.get("enable_health_monitor", True):
            self.health_monitor = await get_health_monitor()
            self.health_monitor.register_alert_callback(self._on_health_alert)
            self.status.health_monitor = True
            logger.info("✅ Health Monitor initialized")
        
        # Initialize Log Analyzer
        if self.config.get("enable_log_analyzer", True):
            self.log_analyzer = await get_log_analyzer()
            self.status.log_analyzer = True
            logger.info("✅ Log Analyzer initialized")
        
        # Initialize Auto-Healer
        if self.config.get("enable_auto_healer", True):
            self.auto_healer = await get_auto_healer()
            self.status.auto_healer = True
            logger.info("✅ Auto-Healer initialized")
        
        # Initialize Development Agents
        self.spec_to_code = get_spec_to_code_agent()
        self.documentation = get_documentation_agent()
        self.status.spec_to_code = True
        self.status.documentation = True
        logger.info("✅ Development Agents initialized")
        
        self.status.last_sync = datetime.utcnow()
        logger.info("✅ All AI Agents initialized successfully")
    
    async def start(self) -> None:
        """Запуск всех агентов."""
        await self.initialize()
        
        self.is_running = True
        logger.info("🚀 Agent Orchestrator started")
        
        # Start background tasks
        tasks = []
        
        if self.health_monitor:
            tasks.append(asyncio.create_task(self.health_monitor.start()))
        
        if self.auto_healer:
            tasks.append(asyncio.create_task(self.auto_healer.start()))
        
        # Wait for all tasks
        if tasks:
            await asyncio.gather(*tasks)
    
    async def stop(self) -> None:
        """Остановка всех агентов."""
        self.is_running = False
        
        if self.health_monitor:
            await self.health_monitor.stop()
        
        if self.auto_healer:
            await self.auto_healer.stop()
        
        logger.info("🛑 Agent Orchestrator stopped")
    
    async def _on_health_alert(self, alert: Alert) -> None:
        """
        Callback для алертов от Health Monitor.
        
        Args:
            alert: Алерт
        """
        logger.warning(f"📢 Health Alert: {alert.severity.value} - {alert.message}")
        
        # Forward to Auto-Healer if enabled
        if self.auto_healer and alert.severity.value in ("warning", "critical"):
            # Trigger healing based on alert
            await self.auto_healer.heal_now(
                issue=f"Health Alert: {alert.service_name}",
                context={
                    "alert_id": alert.id,
                    "service_name": alert.service_name,
                    "severity": alert.severity.value,
                }
            )
    
    async def analyze_logs(self, logs: list[str]) -> dict:
        """
        Анализ логов через Log Analyzer.
        
        Args:
            logs: Список строк логов
            
        Returns:
            Результаты анализа
        """
        if not self.log_analyzer:
            return {"error": "Log Analyzer not initialized"}
        
        return await self.log_analyzer.analyze_logs(logs)
    
    async def generate_code(self, spec) -> Any:
        """
        Генерация кода через Spec-to-Code Agent.
        
        Args:
            spec: Спецификация
            
        Returns:
            Сгенерированный код
        """
        if not self.spec_to_code:
            return {"error": "Spec-to-Code not initialized"}
        
        return await self.spec_to_code.generate(spec)
    
    async def generate_docs(self, source_path: str) -> Any:
        """
        Генерация документации через Documentation Agent.
        
        Args:
            source_path: Путь к исходному коду
            
        Returns:
            Сгенерированная документация
        """
        if not self.documentation:
            return {"error": "Documentation Agent not initialized"}
        
        return await self.documentation.generate_api_docs(source_path)
    
    async def get_status(self) -> dict:
        """Получение статуса всех агентов."""
        status = {
            "is_running": self.is_running,
            "agents": {
                "health_monitor": self.status.health_monitor,
                "log_analyzer": self.status.log_analyzer,
                "auto_healer": self.status.auto_healer,
                "spec_to_code": self.status.spec_to_code,
                "documentation": self.status.documentation,
            },
            "last_sync": self.status.last_sync.isoformat() if self.status.last_sync else None,
        }
        
        # Add agent-specific status
        if self.health_monitor:
            status["health_monitor_status"] = await self.health_monitor.get_health_status()
        
        if self.auto_healer:
            status["auto_healer_status"] = await self.auto_healer.get_status()
        
        if self.log_analyzer:
            status["log_analyzer_status"] = await self.log_analyzer.get_current_status()
        
        return status


# Синглтон экземпляр
_orchestrator_instance: Optional[AgentOrchestrator] = None


async def get_orchestrator() -> AgentOrchestrator:
    """Получение синглтона Orchestrator."""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = AgentOrchestrator()
    return _orchestrator_instance
