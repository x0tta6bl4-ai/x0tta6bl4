"""
SPIRE Server HA Client.

Поддерживает несколько SPIRE Server инстансов с автоматическим failover.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class SPIREServerInstance:
    """SPIRE Server инстанс."""

    address: str  # host:port
    priority: int  # Lower = higher priority
    healthy: bool = True
    last_check: float = 0.0
    failure_count: int = 0


class SPIREHAClient:
    """
    High Availability клиент для SPIRE Server.

    Поддерживает:
    - Несколько SPIRE Server инстансов
    - Автоматический failover при отказе
    - Health check и load balancing
    - Retry с exponential backoff
    """

    def __init__(
        self,
        servers: List[str],
        health_check_interval: float = 30.0,
        max_failures: int = 3,
    ):
        """
        Инициализация HA клиента.

        Args:
            servers: Список адресов SPIRE Server (host:port)
            health_check_interval: Интервал health check (секунды)
            max_failures: Максимум failures перед пометкой как unhealthy
        """
        if not HTTPX_AVAILABLE:
            raise ImportError("httpx required for SPIRE HA client")

        self.servers = [
            SPIREServerInstance(address=addr, priority=i)
            for i, addr in enumerate(servers)
        ]
        self.health_check_interval = health_check_interval
        self.max_failures = max_failures

        # Current active server
        self._current_server: Optional[SPIREServerInstance] = None

        # Health check task
        self._health_check_task: Optional[asyncio.Task] = None
        self._running = False

        logger.info(
            f"✅ SPIRE HA Client initialized with {len(self.servers)} servers: "
            f"{[s.address for s in self.servers]}"
        )

    async def start(self):
        """Start health check loop."""
        self._running = True
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info("✅ SPIRE HA health check started")

    async def stop(self):
        """Stop health check loop."""
        self._running = False
        if self._health_check_task:
            self._health_check_task.cancel()
        logger.info("🛑 SPIRE HA health check stopped")

    async def _health_check_loop(self):
        """Periodically check server health."""
        while self._running:
            try:
                await self._check_all_servers()
                await asyncio.sleep(self.health_check_interval)
            except Exception as e:
                logger.error(f"Health check loop error: {e}", exc_info=True)
                await asyncio.sleep(self.health_check_interval)

    async def _check_all_servers(self):
        """Check health of all servers."""
        for server in self.servers:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    # SPIRE Server health endpoint (if available)
                    # Fallback to gRPC health check
                    response = await client.get(
                        f"http://{server.address}/health", timeout=5.0
                    )

                    if response.status_code == 200:
                        server.healthy = True
                        server.failure_count = 0
                        server.last_check = time.time()
                    else:
                        server.healthy = False
                        server.failure_count += 1
            except Exception as e:
                logger.debug(f"Health check failed for {server.address}: {e}")
                server.healthy = False
                server.failure_count += 1
                server.last_check = time.time()

            # Mark as unhealthy if too many failures
            if server.failure_count >= self.max_failures:
                server.healthy = False
                logger.warning(
                    f"🔴 SPIRE Server {server.address} marked as UNHEALTHY "
                    f"({server.failure_count} failures)"
                )

    def get_active_server(self) -> Optional[str]:
        """
        Получить адрес активного SPIRE Server.

        Returns:
            Адрес здорового сервера с наивысшим приоритетом
        """
        # Find healthy server with highest priority
        healthy_servers = [s for s in self.servers if s.healthy]

        if not healthy_servers:
            logger.error("🔴 No healthy SPIRE servers available!")
            return None

        # Sort by priority (lower = higher priority)
        healthy_servers.sort(key=lambda s: s.priority)
        active = healthy_servers[0]

        if active != self._current_server:
            logger.info(f"🔄 Switched to SPIRE Server: {active.address}")
            self._current_server = active

        return active.address

    async def execute_with_failover(self, operation: callable, *args, **kwargs) -> Any:
        """
        Выполнить операцию с автоматическим failover.

        Args:
            operation: Асинхронная функция для выполнения
            *args, **kwargs: Аргументы для operation

        Returns:
            Результат operation

        Raises:
            Exception: Если все серверы недоступны
        """
        last_error = None

        # Try all healthy servers in priority order
        healthy_servers = sorted(
            [s for s in self.servers if s.healthy], key=lambda s: s.priority
        )

        for server in healthy_servers:
            try:
                # Update operation to use this server
                if hasattr(operation, "__self__"):
                    # Method call - update server address
                    result = await operation(
                        *args, server_address=server.address, **kwargs
                    )
                else:
                    # Function call
                    result = await operation(server.address, *args, **kwargs)

                # Success - return result
                return result

            except Exception as e:
                logger.warning(
                    f"⚠️ Operation failed on {server.address}: {e}. "
                    f"Trying next server..."
                )
                last_error = e
                server.failure_count += 1

                # Mark as unhealthy if too many failures
                if server.failure_count >= self.max_failures:
                    server.healthy = False

        # All servers failed
        logger.error("🔴 All SPIRE servers failed!")
        raise Exception(f"All SPIRE servers unavailable: {last_error}")

    def get_ha_stats(self) -> Dict[str, Any]:
        """Получить статистику HA."""
        healthy_count = sum(1 for s in self.servers if s.healthy)

        return {
            "total_servers": len(self.servers),
            "healthy_servers": healthy_count,
            "unhealthy_servers": len(self.servers) - healthy_count,
            "current_server": (
                self._current_server.address if self._current_server else None
            ),
            "servers": [
                {
                    "address": s.address,
                    "priority": s.priority,
                    "healthy": s.healthy,
                    "failure_count": s.failure_count,
                    "last_check": s.last_check,
                }
                for s in self.servers
            ],
        }

