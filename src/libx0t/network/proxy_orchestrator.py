"""
Orchestrator for Residential Proxy Infrastructure.

Integrates all components:
- Configuration management
- Proxy manager with health monitoring
- Selection algorithm with ML scoring
- Reputation scoring
- Metrics collection
- Authentication/authorization
- Control plane API

Provides unified lifecycle management and graceful operations.
"""

import asyncio
import logging
import signal
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from .proxy_auth_middleware import ProxyAuthMiddleware, create_auth_middleware
from .proxy_config_manager import (
    Environment,
    ProxyConfigManager,
    ProxyInfrastructureConfig,
)
from .proxy_control_plane import ProxyControlPlane
from .proxy_metrics_collector import ProxyMetricsCollector, create_default_collector
from .proxy_selection_algorithm import ProxySelectionAlgorithm, SelectionStrategy
from .reputation_scoring import ReputationScoringSystem
from .residential_proxy_manager import ProxyStatus, ResidentialProxyManager

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorStatus:
    """Current status of the proxy orchestrator."""

    state: str  # initializing, running, degraded, stopping, stopped
    started_at: Optional[datetime] = None
    uptime_seconds: float = 0.0
    components_ready: Dict[str, bool] = None
    active_proxies: int = 0
    healthy_proxies: int = 0
    total_requests: int = 0
    error_count: int = 0

    def __post_init__(self):
        if self.components_ready is None:
            self.components_ready = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "uptime_seconds": self.uptime_seconds,
            "components_ready": self.components_ready,
            "proxies": {"active": self.active_proxies, "healthy": self.healthy_proxies},
            "requests": {"total": self.total_requests, "errors": self.error_count},
        }


class ProxyOrchestrator:
    """
    Central orchestrator for the entire proxy infrastructure.

    Manages component lifecycle, provides unified API, and handles
    graceful startup/shutdown with dependency ordering.
    """

    def __init__(
        self, config_path: Optional[str] = None, environment: Optional[str] = None
    ):
        self.config_manager: Optional[ProxyConfigManager] = None
        self.proxy_manager: Optional[ResidentialProxyManager] = None
        self.selection_algorithm: Optional[ProxySelectionAlgorithm] = None
        self.reputation_system: Optional[ReputationScoringSystem] = None
        self.metrics_collector: Optional[ProxyMetricsCollector] = None
        self.auth_middleware: Optional[ProxyAuthMiddleware] = None
        self.control_plane: Optional[ProxyControlPlane] = None

        self.config_path = config_path
        self.environment = environment
        self.status = OrchestratorStatus(state="initializing")

        self._shutdown_event = asyncio.Event()
        self._tasks: List[asyncio.Task] = []

    async def initialize(self):
        """Initialize all components in dependency order."""
        logger.info("Initializing proxy orchestrator...")

        try:
            # 1. Configuration Manager (foundation)
            logger.info("Initializing configuration manager...")
            self.config_manager = ProxyConfigManager(
                config_path=self.config_path,
                environment=Environment(self.environment) if self.environment else None,
            )
            await self.config_manager.start()
            config = self.config_manager.config
            self.status.components_ready["config"] = True

            # 2. Metrics Collector (needed by other components)
            logger.info("Initializing metrics collector...")
            self.metrics_collector = create_default_collector()
            if config.metrics.enabled:
                await self.metrics_collector.start()
            self.status.components_ready["metrics"] = True

            # 3. Reputation Scoring System
            logger.info("Initializing reputation system...")
            self.reputation_system = ReputationScoringSystem()
            self.status.components_ready["reputation"] = True

            # 4. Selection Algorithm
            logger.info("Initializing selection algorithm...")
            self.selection_algorithm = ProxySelectionAlgorithm(
                default_strategy=SelectionStrategy(config.selection.strategy),
                latency_weight=config.selection.latency_weight,
                success_weight=config.selection.success_weight,
                stability_weight=config.selection.stability_weight,
                geographic_weight=config.selection.geographic_weight,
            )
            self.status.components_ready["selection"] = True

            # 5. Proxy Manager (depends on config)
            logger.info("Initializing proxy manager...")
            self.proxy_manager = ResidentialProxyManager(
                health_check_interval=config.health_check.interval_seconds,
                max_failures=config.health_check.unhealthy_threshold,
            )

            # Load proxies from config
            proxies = self.config_manager.get_provider_proxies()
            for proxy in proxies:
                self.proxy_manager.add_proxy(proxy)

            await self.proxy_manager.start()
            self.status.components_ready["proxy_manager"] = True

            # 6. Auth Middleware
            logger.info("Initializing authentication middleware...")
            self.auth_middleware = create_auth_middleware(
                require_auth=config.security.api_key_required,
                requests_per_minute=config.security.rate_limit_requests_per_minute,
                jwt_secret=config.security.jwt_secret,
            )
            self.status.components_ready["auth"] = True

            # 7. Control Plane API (depends on all above)
            logger.info("Initializing control plane API...")
            self.control_plane = ProxyControlPlane(
                proxy_manager=self.proxy_manager,
                host=config.control_plane_host,
                port=config.control_plane_port,
            )

            # Add auth middleware to control plane
            # Note: This would require modifying control plane to accept middleware
            # For now, we assume it's integrated at the app level

            await self.control_plane.start()
            self.status.components_ready["control_plane"] = True

            # Setup config change handler
            self.config_manager.on_change(self._on_config_change)

            self.status.state = "running"
            self.status.started_at = datetime.utcnow()
            logger.info("Proxy orchestrator initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize orchestrator: {e}")
            self.status.state = "failed"
            raise

    async def _on_config_change(self, config: ProxyInfrastructureConfig):
        """Handle configuration changes."""
        logger.info("Configuration changed, applying updates...")

        # Update selection algorithm weights
        if self.selection_algorithm:
            self.selection_algorithm.latency_weight = config.selection.latency_weight
            self.selection_algorithm.success_weight = config.selection.success_weight
            self.selection_algorithm.stability_weight = (
                config.selection.stability_weight
            )
            self.selection_algorithm.geographic_weight = (
                config.selection.geographic_weight
            )

        # Reload proxy pool if providers changed
        if self.proxy_manager:
            current_ids = {p.id for p in self.proxy_manager.proxies}
            new_proxies = self.config_manager.get_provider_proxies()
            new_ids = {p.id for p in new_proxies}

            # Remove old proxies
            for proxy in list(self.proxy_manager.proxies):
                if proxy.id not in new_ids:
                    self.proxy_manager.proxies.remove(proxy)
                    logger.info(f"Removed proxy: {proxy.id}")

            # Add new proxies
            for proxy in new_proxies:
                if proxy.id not in current_ids:
                    self.proxy_manager.add_proxy(proxy)
                    logger.info(f"Added proxy: {proxy.id}")

        logger.info("Configuration updates applied")

    async def run(self):
        """Run the orchestrator until shutdown signal."""
        logger.info("Proxy orchestrator running")

        # Setup signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._signal_handler)

        # Status update loop
        while not self._shutdown_event.is_set():
            try:
                await self._update_status()
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=10.0)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Status update error: {e}")
                await asyncio.sleep(5)

        await self.shutdown()

    def _signal_handler(self):
        """Handle shutdown signals."""
        logger.info("Shutdown signal received")
        self._shutdown_event.set()

    async def _update_status(self):
        """Update orchestrator status."""
        if self.status.started_at:
            self.status.uptime_seconds = (
                datetime.utcnow() - self.status.started_at
            ).total_seconds()

        if self.proxy_manager:
            self.status.active_proxies = len(self.proxy_manager.proxies)

            self.status.healthy_proxies = sum(
                1 for p in self.proxy_manager.proxies if p.status == ProxyStatus.HEALTHY
            )

    async def shutdown(self):
        """Graceful shutdown of all components."""
        logger.info("Shutting down proxy orchestrator...")
        self.status.state = "stopping"

        # Shutdown in reverse dependency order
        shutdown_order = [
            ("control_plane", self.control_plane),
            ("proxy_manager", self.proxy_manager),
            ("metrics", self.metrics_collector),
            ("config", self.config_manager),
        ]

        for name, component in shutdown_order:
            if component:
                try:
                    logger.info(f"Shutting down {name}...")
                    await component.stop()
                    self.status.components_ready[name] = False
                except Exception as e:
                    logger.error(f"Error shutting down {name}: {e}")

        self.status.state = "stopped"
        logger.info("Proxy orchestrator shutdown complete")

    def get_status(self) -> OrchestratorStatus:
        """Get current orchestrator status."""
        return self.status

    async def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of all metrics."""
        if not self.metrics_collector:
            return {"error": "Metrics collector not initialized"}

        return self.metrics_collector.get_global_metrics()

    async def get_health_report(self) -> Dict[str, Any]:
        """Get comprehensive health report."""
        report = {"orchestrator": self.status.to_dict(), "components": {}}

        if self.proxy_manager:
            report["proxies"] = {
                "total": len(self.proxy_manager.proxies),
                "by_status": {},
            }

            for status in ProxyStatus:
                count = sum(1 for p in self.proxy_manager.proxies if p.status == status)
                report["proxies"]["by_status"][status.value] = count

        if self.reputation_system:
            report["reputation"] = self.reputation_system.export_stats()

        return report


async def main():
    """Main entry point for running the orchestrator."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    orchestrator = ProxyOrchestrator()

    try:
        await orchestrator.initialize()
        await orchestrator.run()
    except Exception as e:
        logger.error(f"Orchestrator failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
