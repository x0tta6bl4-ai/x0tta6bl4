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
from __future__ import annotations

import asyncio
import logging
import signal
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.core.thinking.agent_thinking import AgentThinkingCoach
from src.coordination.events import EventBus, EventType, get_event_bus
from src.network.proxy_auth_middleware import (ProxyAuthMiddleware,
                                               create_auth_middleware)
from src.network.proxy_config_manager import (Environment, ProxyConfigManager,
                                              ProxyInfrastructureConfig)
from src.network.proxy_control_plane import ProxyControlPlane
from src.network.proxy_metrics_collector import (ProxyMetricsCollector,
                                                 create_default_collector)
from src.network.proxy_selection_algorithm import (ProxySelectionAlgorithm,
                                                   SelectionStrategy)
from src.network.reputation_scoring import ReputationScoringSystem
from src.network.residential_proxy_manager import ResidentialProxyManager
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)

_SERVICE_AGENT = "proxy-orchestrator"
_SERVICE_LAYER = "network_proxy_orchestrator_observed_state"
PROXY_ORCHESTRATOR_CLAIM_BOUNDARY = (
    "Local proxy orchestrator observed-state evidence only. It records component "
    "readiness and aggregate proxy/request counts without copying proxy IDs, "
    "provider configuration, credentials, targets, or traffic payloads. It does "
    "not prove external proxy reachability or customer traffic delivery."
)


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
        self,
        config_path: Optional[str] = None,
        environment: Optional[str] = None,
        event_bus: Optional[EventBus] = None,
        event_project_root: Optional[str] = None,
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
        self.event_bus = event_bus
        self.event_project_root = event_project_root
        self.status = OrchestratorStatus(state="initializing")
        self.thinking_coach = AgentThinkingCoach(
            agent_id=_SERVICE_AGENT,
            role="ops",
            capabilities=("monitoring", "zero-trust"),
            extra_techniques=("mape_k", "weighted_decision_matrix"),
        )
        self.last_thinking_context: Dict[str, Any] = {}

        self._shutdown_event = asyncio.Event()
        self._tasks: List[asyncio.Task] = []

    def _event_bus_or_none(self) -> Optional[EventBus]:
        if self.event_bus is not None:
            return self.event_bus
        if self.event_project_root is None:
            return None
        try:
            self.event_bus = get_event_bus(self.event_project_root)
            return self.event_bus
        except Exception as exc:
            logger.error("Failed to initialize proxy-orchestrator EventBus: %s", exc)
            return None

    def _component_readiness_summary(self) -> Dict[str, int]:
        ready_values = [
            value
            for value in self.status.components_ready.values()
            if isinstance(value, bool)
        ]
        ready = sum(1 for value in ready_values if value)
        total = len(ready_values)
        return {
            "total": total,
            "ready": ready,
            "not_ready": total - ready,
        }

    def _service_identity_presence(self) -> Dict[str, bool]:
        identity = service_event_identity(service_name=_SERVICE_AGENT)
        return {field: bool(value) for field, value in identity.items()}

    def _refresh_proxy_status_counts(self) -> None:
        if not self.proxy_manager:
            return

        self.status.active_proxies = len(self.proxy_manager.proxies)
        from src.network.residential_proxy_manager import ProxyStatus

        self.status.healthy_proxies = sum(
            1 for p in self.proxy_manager.proxies if p.status == ProxyStatus.HEALTHY
        )

    def _status_evidence_payload(
        self,
        *,
        operation: str,
        duration_ms: float,
    ) -> Dict[str, Any]:
        return {
            "component": "network.proxy_orchestrator",
            "operation": operation,
            "service_name": _SERVICE_AGENT,
            "layer": _SERVICE_LAYER,
            "status": self.status.state,
            "success": self.status.state not in {"failed"},
            "duration_ms": round(float(duration_ms), 3),
            "service_identity_present": self._service_identity_presence(),
            "components": self._component_readiness_summary(),
            "proxies": {
                "active": int(self.status.active_proxies),
                "healthy": int(self.status.healthy_proxies),
            },
            "requests": {
                "total": int(self.status.total_requests),
                "errors": int(self.status.error_count),
            },
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
            "raw_identifiers_redacted": True,
            "claim_boundary": PROXY_ORCHESTRATOR_CLAIM_BOUNDARY,
        }

    def _publish_status_evidence(
        self,
        *,
        operation: str,
        duration_ms: float,
    ) -> Optional[str]:
        bus = self._event_bus_or_none()
        if bus is None:
            return None
        payload = self._status_evidence_payload(
            operation=operation,
            duration_ms=duration_ms,
        )
        try:
            event = bus.publish(
                EventType.PIPELINE_STAGE_END,
                _SERVICE_AGENT,
                payload,
                priority=4,
            )
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish proxy-orchestrator evidence: %s", exc)
            return None

    async def initialize(self):
        """Initialize all components in dependency order."""
        logger.info("Initializing proxy orchestrator...")
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "proxy_orchestrator_initialize",
                "goal": "Initialize proxy infrastructure components in dependency order.",
                "constraints": {
                    "environment": self.environment,
                    "event_project_root_configured": self.event_project_root is not None,
                    "preserve_component_order": True,
                },
            }
        )

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
            self.metrics_collector = create_default_collector(
                event_bus=self.event_bus,
                event_project_root=self.event_project_root,
            )
            if config.metrics.enabled:
                await self.metrics_collector.start()
            self.status.components_ready["metrics"] = True

            # 3. Reputation Scoring System
            logger.info("Initializing reputation system...")
            self.reputation_system = ReputationScoringSystem(
                event_bus=self.event_bus,
                event_project_root=self.event_project_root,
            )
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
                event_bus=self.event_bus,
                event_project_root=self.event_project_root,
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
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "proxy_orchestrator_config_change",
                "goal": "Apply proxy configuration changes without leaking provider details.",
                "constraints": {
                    "selection_strategy": str(
                        getattr(config.selection, "strategy", "unchanged")
                    ),
                    "raw_provider_ids_redacted": True,
                },
            }
        )

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
        started = time.perf_counter()
        if self.status.started_at:
            self.status.uptime_seconds = (
                datetime.utcnow() - self.status.started_at
            ).total_seconds()

        self._refresh_proxy_status_counts()
        self._publish_status_evidence(
            operation="update_status",
            duration_ms=(time.perf_counter() - started) * 1000,
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
        started = time.perf_counter()
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "proxy_orchestrator_health_report",
                "goal": "Build a redacted observed-state proxy health report.",
                "constraints": {
                    "payload_redacted": True,
                    "claim_boundary": PROXY_ORCHESTRATOR_CLAIM_BOUNDARY,
                },
            }
        )

        if self.proxy_manager:
            self._refresh_proxy_status_counts()

        report = {"orchestrator": self.status.to_dict(), "components": {}}

        if self.proxy_manager:
            report["proxies"] = {
                "total": len(self.proxy_manager.proxies),
                "by_status": {},
            }
            from src.network.residential_proxy_manager import ProxyStatus

            for status in ProxyStatus:
                count = sum(1 for p in self.proxy_manager.proxies if p.status == status)
                report["proxies"]["by_status"][status.value] = count

        if self.reputation_system:
            report["reputation"] = self.reputation_system.export_stats()

        evidence_event_id = self._publish_status_evidence(
            operation="get_health_report",
            duration_ms=(time.perf_counter() - started) * 1000,
        )
        report["evidence"] = {
            "event_id": evidence_event_id,
            "source_agent": _SERVICE_AGENT if evidence_event_id else None,
            "layer": _SERVICE_LAYER if evidence_event_id else None,
            "payload_redacted": True,
            "claim_boundary": PROXY_ORCHESTRATOR_CLAIM_BOUNDARY,
        }
        return report


async def main():
    """Main entry point for running the orchestrator."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    orchestrator = ProxyOrchestrator(event_project_root=".")

    try:
        await orchestrator.initialize()
        await orchestrator.run()
    except Exception as e:
        logger.error(f"Orchestrator failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())

