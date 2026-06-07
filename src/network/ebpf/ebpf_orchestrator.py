"""
EBPF Orchestrator - единая точка управления eBPF подсистемой.

Объединяет все компоненты eBPF в единую архитектуру для упрощения развертывания,
мониторинга и управления.
"""

import asyncio
import hashlib
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from src.core.agent_thinking import AgentThinkingCoach
from src.network.ebpf.bcc_probes import MeshNetworkProbes
from src.network.ebpf.cilium_integration import CiliumLikeIntegration
from src.network.ebpf.dynamic_fallback import DynamicFallbackController
from src.network.ebpf.loader import EBPFLoader
from src.network.ebpf.mape_k_integration import EBPFMAPEKIntegration
from src.network.ebpf.metrics_exporter import EBPFMetricsExporter
from src.network.ebpf.ringbuf_reader import RingBufferReader

logger = logging.getLogger(__name__)


def _hash_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    return hashlib.sha256(str(value).encode("utf-8", errors="replace")).hexdigest()


class OrchestratorStatus(Enum):
    """Статус оркестратора."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class OrchestratorConfig:
    """Конфигурация для EBPFOrchestrator."""

    interface: str = "eth0"
    enable_metrics: bool = True
    enable_cilium: bool = True
    enable_fallback: bool = True
    enable_probes: bool = True
    enable_mapek: bool = True
    metrics_port: int = 9090
    metrics_path: str = "/metrics"
    ring_buffer_size: int = 4096
    health_check_interval: float = 5.0  # секунды


class EBPFOrchestrator:
    """Единая точка управления eBPF подсистемой."""

    def __init__(self, config: Optional[OrchestratorConfig] = None):
        """
        Инициализация eBPFOrchestrator.

        Args:
            config: Конфигурация для оркестратора. Если не предоставлена, используется конфигурация по умолчанию.
        """
        self.config = config or OrchestratorConfig()
        self.status = OrchestratorStatus.STOPPED
        self._lock = asyncio.Lock()
        self._health_check_task: Optional[asyncio.Task] = None
        self.thinking_coach = AgentThinkingCoach(
            agent_id="ebpf-async-orchestrator",
            role="coordinator",
            capabilities=("security", "zero-trust", "monitoring"),
            extra_techniques=("mape_k", "reverse_planning", "chaos_driven_design"),
        )
        self._last_thinking_context: Optional[Dict[str, Any]] = None

        # Инициализация компонентов
        self.loader = EBPFLoader()
        self.probes = MeshNetworkProbes(self.config.interface)
        self.metrics = EBPFMetricsExporter(
            port=self.config.metrics_port, path=self.config.metrics_path
        )
        self.cilium = CiliumLikeIntegration(self.config.interface)
        self.fallback = DynamicFallbackController()
        self.mapek = EBPFMAPEKIntegration(self.metrics)
        self.ring_buffer = RingBufferReader(buffer_size=self.config.ring_buffer_size)

        self._components = [
            ("loader", self.loader),
            ("probes", self.probes),
            ("metrics", self.metrics),
            ("cilium", self.cilium),
            ("fallback", self.fallback),
            ("mapek", self.mapek),
            ("ring_buffer", self.ring_buffer),
        ]

    def _record_thinking_context(
        self,
        *,
        operation: str,
        goal: str,
        constraints: Dict[str, Any],
    ) -> Dict[str, Any]:
        safe_task = {
            "task_type": "ebpf_async_orchestration",
            "goal": goal,
            "constraints": {
                "operation": operation,
                "redacted": True,
                **constraints,
            },
            "safety_boundary": (
                "Coordinate async eBPF components with redacted selectors; do "
                "not expose interface names, program paths, component errors, "
                "or raw program names."
            ),
        }
        self._last_thinking_context = self.thinking_coach.prepare_task(safe_task)
        return self._last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        """Expose async orchestration thinking state without task secrets."""

        return {
            **self.thinking_coach.status(),
            "last_context": self._last_thinking_context,
        }

    async def start(self) -> None:
        """Запуск всех компонентов eBPF подсистемы."""
        if self.status == OrchestratorStatus.RUNNING:
            logger.warning("Orchestrator already running")
            return

        async with self._lock:
            if self.status == OrchestratorStatus.RUNNING:
                return

            self._record_thinking_context(
                operation="start",
                goal="start async eBPF component graph",
                constraints={
                    "interface_hash": _hash_value(self.config.interface),
                    "interface_redacted": True,
                    "component_count": len(self._components),
                    "health_check_interval": self.config.health_check_interval,
                },
            )
            self.status = OrchestratorStatus.STARTING
            logger.info("Starting eBPF orchestrator")

            try:
                # Запуск компонентов в порядке зависимостей
                component_order = [
                    "loader",
                    "ring_buffer",
                    "probes",
                    "metrics",
                    "cilium",
                    "fallback",
                    "mapek",
                ]

                for component_name in component_order:
                    component = next(
                        c[1] for c in self._components if c[0] == component_name
                    )
                    logger.debug(f"Starting {component_name}")
                    await self._start_component(component)

                # Load and attach DPI evasion XDP program
                try:
                    logger.info("Initializing XDP Pulse Program for DPI Evasion...")
                    prog_path = "src/network/ebpf/x0tta6bl4_pulse.o"
                    import os
                    if os.path.exists(prog_path):
                        await self.load_program("x0tta6bl4_pulse", prog_path)
                        await self.attach_program("x0tta6bl4_pulse", self.config.interface)
                        logger.info("✅ XDP Pulse Program active.")
                    else:
                        logger.warning(f"XDP object file not found at {prog_path}. Run 'clang -O2 -target bpf -c ...' to compile.")
                except Exception as e:
                    logger.error(f"Failed to load XDP Pulse: {e}")

                # Запуск health checks
                if self.config.health_check_interval > 0:
                    self._health_check_task = asyncio.create_task(
                        self._health_check_loop()
                    )

                self.status = OrchestratorStatus.RUNNING
                logger.info("eBPF orchestrator started successfully")

            except Exception as e:
                logger.error(f"Failed to start eBPF orchestrator: {e}")
                self.status = OrchestratorStatus.ERROR
                await self._stop_components()
                raise

    async def stop(self) -> None:
        """Корректное завершение всех компонентов eBPF подсистемы."""
        if self.status != OrchestratorStatus.RUNNING:
            logger.warning("Orchestrator not running")
            return

        async with self._lock:
            if self.status != OrchestratorStatus.RUNNING:
                return

            self._record_thinking_context(
                operation="stop",
                goal="stop async eBPF component graph",
                constraints={
                    "status_before": self.status.value,
                    "component_count": len(self._components),
                },
            )
            self.status = OrchestratorStatus.STOPPING
            logger.info("Stopping eBPF orchestrator")

            try:
                # Остановка health checks
                if self._health_check_task:
                    self._health_check_task.cancel()
                    try:
                        await self._health_check_task
                    except asyncio.CancelledError:
                        pass

                # Остановка компонентов в обратном порядке зависимостей
                component_order = [
                    "mapek",
                    "fallback",
                    "cilium",
                    "metrics",
                    "probes",
                    "ring_buffer",
                    "loader",
                ]

                for component_name in component_order:
                    component = next(
                        c[1] for c in self._components if c[0] == component_name
                    )
                    logger.debug(f"Stopping {component_name}")
                    await self._stop_component(component)

                self.status = OrchestratorStatus.STOPPED
                logger.info("eBPF orchestrator stopped successfully")

            except Exception as e:
                logger.error(f"Failed to stop eBPF orchestrator: {e}")
                self.status = OrchestratorStatus.ERROR
                raise

    async def _start_component(self, component: Any) -> None:
        """Запуск одного компонента."""
        if hasattr(component, "start"):
            await component.start()
        elif hasattr(component, "initialize"):
            await component.initialize()

    async def _stop_component(self, component: Any) -> None:
        """Остановка одного компонента."""
        if hasattr(component, "stop"):
            await component.stop()
        elif hasattr(component, "shutdown"):
            await component.shutdown()

    async def _health_check_loop(self) -> None:
        """Цикл проверки здоровья компонентов."""
        try:
            while self.status == OrchestratorStatus.RUNNING:
                await asyncio.sleep(self.config.health_check_interval)
                await self._check_components_health()
        except asyncio.CancelledError:
            logger.debug("Health check loop cancelled")
        except Exception as e:
            logger.error(f"Health check loop error: {e}")

    async def _check_components_health(self) -> None:
        """Проверка здоровья всех компонентов."""
        self._record_thinking_context(
            operation="check_components_health",
            goal="check async eBPF component health",
            constraints={
                "read_only": True,
                "component_count": len(self._components),
                "status": self.status.value,
            },
        )
        for name, component in self._components:
            if hasattr(component, "is_healthy"):
                try:
                    is_healthy = await component.is_healthy()
                    if not is_healthy:
                        logger.warning(f"Component {name} is unhealthy")
                        await self._handle_unhealthy_component(name, component)
                except Exception as e:
                    logger.error(f"Error checking health of component {name}: {e}")
                    await self._handle_unhealthy_component(name, component)

    async def _handle_unhealthy_component(self, name: str, component: Any) -> None:
        """Обработка неработающего компонента."""
        logger.error(f"Component {name} is unhealthy, attempting to restart")
        try:
            await self._stop_component(component)
            await self._start_component(component)
            logger.info(f"Component {name} restarted successfully")
        except Exception as e:
            logger.error(f"Failed to restart component {name}: {e}")
            self.status = OrchestratorStatus.ERROR

    def get_status(self) -> Dict[str, Any]:
        """
        Получить статус всех подсистем.

        Returns:
            Словарь с информацией о состоянии каждой подсистемы.
        """
        self._record_thinking_context(
            operation="get_status",
            goal="read async eBPF component status",
            constraints={
                "read_only": True,
                "status": self.status.value,
                "component_count": len(self._components),
            },
        )
        status = {"orchestrator_status": self.status.value, "components": {}}

        for name, component in self._components:
            comp_status = {"status": "unknown"}
            if hasattr(component, "get_status"):
                try:
                    comp_status = component.get_status()
                except Exception as e:
                    logger.error(f"Error getting status from {name}: {e}")
                    comp_status = {"status": "error", "error": str(e)}
            status["components"][name] = comp_status

        return status

    def list_loaded_programs(self) -> Dict[str, Any]:
        """
        Получить список загруженных eBPF программ.

        Returns:
            Словарь с информацией о загруженных программах.
        """
        return self.loader.list_loaded_programs()

    def get_stats(self) -> Dict[str, Any]:
        """
        Получить статистику из всех активных компонентов.

        Returns:
            Словарь со статистикой компонентов.
        """
        self._record_thinking_context(
            operation="get_stats",
            goal="read async eBPF component stats",
            constraints={
                "read_only": True,
                "component_count": len(self._components),
            },
        )
        stats = {}

        for name, component in self._components:
            if hasattr(component, "get_stats"):
                try:
                    stats[name] = component.get_stats()
                except Exception as e:
                    logger.error(f"Error getting stats from {name}: {e}")
                    stats[name] = {"error": str(e)}

        return stats

    def get_flows(self) -> Dict[str, Any]:
        """
        Получить информацию о сетевых потоках (Hubble-like).

        Returns:
            Словарь с информацией о сетевых потоках.
        """
        return self.cilium.get_flow_metrics()

    async def load_program(
        self, program_name: str, program_path: str, **kwargs
    ) -> Dict[str, Any]:
        """
        Загрузить eBPF программу.

        Args:
            program_name: Имя программы.
            program_path: Путь к файлу с программой.
            **kwargs: Дополнительные аргументы для загрузчика.

        Returns:
            Словарь с результатами загрузки.
        """
        self._record_thinking_context(
            operation="load_program",
            goal="load eBPF program through async orchestrator",
            constraints={
                "program_name_hash": _hash_value(program_name),
                "program_path_hash": _hash_value(program_path),
                "program_name_redacted": True,
                "program_path_redacted": True,
            },
        )
        try:
            result = await self.loader.load_program(
                program_name, program_path, **kwargs
            )
            logger.info(f"Program {program_name} loaded successfully")
            return result
        except Exception as e:
            logger.error(f"Failed to load program {program_name}: {e}")
            return {"success": False, "error": str(e)}

    async def unload_program(self, program_name: str) -> Dict[str, Any]:
        """
        Отгрузить eBPF программу.

        Args:
            program_name: Имя программы для отгрузки.

        Returns:
            Словарь с результатами отгрузки.
        """
        self._record_thinking_context(
            operation="unload_program",
            goal="unload eBPF program through async orchestrator",
            constraints={
                "program_name_hash": _hash_value(program_name),
                "program_name_redacted": True,
            },
        )
        try:
            result = await self.loader.unload_program(program_name)
            logger.info(f"Program {program_name} unloaded successfully")
            return result
        except Exception as e:
            logger.error(f"Failed to unload program {program_name}: {e}")
            return {"success": False, "error": str(e)}

    async def attach_program(
        self, program_name: str, interface: str = None
    ) -> Dict[str, Any]:
        """
        Подключить eBPF программу к интерфейсу.

        Args:
            program_name: Имя программы.
            interface: Интерфейс для подключения. Если не предоставлен, используется интерфейс из конфигурации.

        Returns:
            Словарь с результатами подключения.
        """
        iface = interface or self.config.interface
        self._record_thinking_context(
            operation="attach_program",
            goal="attach eBPF program through async orchestrator",
            constraints={
                "program_name_hash": _hash_value(program_name),
                "interface_hash": _hash_value(iface),
                "program_name_redacted": True,
                "interface_redacted": True,
            },
        )
        try:
            result = await self.loader.attach_program(program_name, iface)
            logger.info(f"Program {program_name} attached successfully")
            return result
        except Exception as e:
            logger.error(f"Failed to attach program {program_name}: {e}")
            return {"success": False, "error": str(e)}

    async def detach_program(
        self, program_name: str, interface: str = None
    ) -> Dict[str, Any]:
        """
        Отключить eBPF программу от интерфейса.

        Args:
            program_name: Имя программы.
            interface: Интерфейс для отключения. Если не предоставлен, используется интерфейс из конфигурации.

        Returns:
            Словарь с результатами отключения.
        """
        iface = interface or self.config.interface
        self._record_thinking_context(
            operation="detach_program",
            goal="detach eBPF program through async orchestrator",
            constraints={
                "program_name_hash": _hash_value(program_name),
                "interface_hash": _hash_value(iface),
                "program_name_redacted": True,
                "interface_redacted": True,
            },
        )
        try:
            result = await self.loader.detach_program(program_name, iface)
            logger.info(f"Program {program_name} detached successfully")
            return result
        except Exception as e:
            logger.error(f"Failed to detach program {program_name}: {e}")
            return {"success": False, "error": str(e)}

    async def __aenter__(self):
        """Вход в контекстный менеджер - запуск оркестратора."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Выход из контекстного менеджера - остановка оркестратора."""
        await self.stop()


# Пример использования
async def main():
    """Пример использования EBPFOrchestrator."""
    # Настройка логирования
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Создание конфигурации
    config = OrchestratorConfig(
        interface="eth0",
        enable_metrics=True,
        enable_cilium=True,
        enable_fallback=True,
        metrics_port=9091,
    )

    # Создание и запуск оркестратора
    async with EBPFOrchestrator(config) as orchestrator:
        # Получение статуса
        status = orchestrator.get_status()
        logger.debug(f"Orchestrator status: {status}")

        # Вывод списка загруженных программ
        programs = orchestrator.list_loaded_programs()
        logger.debug(f"Loaded programs: {programs}")

        # Вывод статистики
        stats = orchestrator.get_stats()
        logger.debug(f"Stats: {stats}")

        # Запуск в течение 60 секунд
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
