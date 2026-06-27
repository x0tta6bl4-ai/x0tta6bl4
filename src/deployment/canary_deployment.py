"""
Canary Deployment для x0tta6bl4.

Постепенный rollout новой версии:
- Canary: 1% трафика
- Gradual: 10% → 50% → 100%
- Автоматический rollback при проблемах

Features:
- Helm integration для Kubernetes deployments
- Integration с основными deployment скриптами
- Автоматический мониторинг и продвижение стадий
- Prometheus metrics integration
- CI/CD integration (GitLab, GitHub Actions, Jenkins, etc.)
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import subprocess
from src.core.security.subprocess_validator import safe_run
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from src.coordination.events import EventBus, EventType
from src.integration.spine import SafeActuatorEvidenceMetadata

logger = logging.getLogger(__name__)

CANARY_DEPLOYMENT_CLAIM_BOUNDARY = (
    "Canary deployment status records local rollout intent, local metrics, and "
    "authorized command/API attempts only. It does not prove traffic shifting, "
    "live customer traffic, external DPI bypass, settlement finality, production "
    "SLOs, or production readiness without separate current evidence."
)

CANARY_DEPLOYMENT_SAFE_ACTUATOR_CLAIM_BOUNDARY = (
    "Canary deployment evidence metadata proves only a local gated rollout, "
    "traffic-weight update, rollback command/API attempt, or bounded metrics "
    "observation. It is not proof of traffic shifting, live customer traffic, "
    "external DPI bypass, settlement finality, production SLOs, or production "
    "readiness."
)


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").lower() == "yes"


def _bounded_output_metadata(text: str) -> Dict[str, Any]:
    encoded = text.encode("utf-8", errors="replace")
    return {
        "bytes": len(encoded),
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "raw_output_retained": False,
    }


def _safe_actuator_evidence_metadata(
    *,
    action: str,
    live_action_authorized: bool,
    live_action_executed: bool,
    command_metadata: Optional[Dict[str, Any]] = None,
    metrics_observed: bool = False,
    rollback_recommended: bool = False,
) -> Dict[str, Any]:
    claim_gate = {
        "schema": "x0tta6bl4.deployment.canary.safe_actuator_claim_gate.v1",
        "action": action,
        "safe_actuator_result_recorded": True,
        "local_canary_rollout_attempt_claim_allowed": bool(live_action_authorized),
        "local_canary_rollout_action_succeeded": bool(live_action_executed),
        "local_canary_metrics_observation_claim_allowed": bool(metrics_observed),
        "local_rollback_recommendation_claim_allowed": bool(rollback_recommended),
        "traffic_shift_claim_allowed": False,
        "live_customer_traffic_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "external_dpi_bypass_confirmed": False,
        "external_settlement_finality_claim_allowed": False,
        "claim_boundary": CANARY_DEPLOYMENT_SAFE_ACTUATOR_CLAIM_BOUNDARY,
        "redacted": True,
    }
    return SafeActuatorEvidenceMetadata.from_value(
        {
            "claim_gate": claim_gate,
            "cross_plane_claim_gate": {
                "schema": "x0tta6bl4.deployment.canary.cross_plane_claim_gate.v1",
                "allowed": False,
                "requires_runtime_rollout_evidence_for_traffic_shift_claim": True,
                "requires_customer_traffic_evidence_for_customer_claim": True,
                "requires_slo_evidence_for_production_slo_claim": True,
                "requires_readiness_review_for_production_claim": True,
                "redacted": True,
            },
            "evidence": {
                "component": "deployment.canary",
                "action": action,
                "resource": f"deployment:canary:{action}",
                "command_metadata_present": command_metadata is not None,
                "metrics_observed": bool(metrics_observed),
                "rollback_recommended": bool(rollback_recommended),
                "raw_context_values_redacted": True,
                "raw_command_output_redacted": True,
            },
            "source_agents": ["canary-deployment"],
            "claim_boundary": CANARY_DEPLOYMENT_SAFE_ACTUATOR_CLAIM_BOUNDARY,
            "redacted": True,
        }
    ).to_dict()


def _claim_boundary_fields(
    *,
    action: str = "canary_claim_boundary",
    live_action_authorized: bool = False,
    live_action_executed: bool = False,
    command_metadata: Optional[Dict[str, Any]] = None,
    metrics_observed: bool = False,
    rollback_recommended: bool = False,
) -> Dict[str, Any]:
    return {
        "traffic_shift_claim_allowed": False,
        "live_customer_traffic_proven": False,
        "production_readiness_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "external_dpi_bypass_confirmed": False,
        "settlement_finality_confirmed": False,
        "claim_boundary": CANARY_DEPLOYMENT_CLAIM_BOUNDARY,
        "safe_actuator_evidence_metadata": _safe_actuator_evidence_metadata(
            action=action,
            live_action_authorized=live_action_authorized,
            live_action_executed=live_action_executed,
            command_metadata=command_metadata,
            metrics_observed=metrics_observed,
            rollback_recommended=rollback_recommended,
        ),
    }


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
    allow_live_actions: Optional[bool] = None


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
        metrics_collector: Optional[Callable[[], Dict[str, Any]]] = None,
        event_bus: Optional[EventBus] = None,
        source_agent: str = "canary-deployment",
        node_id: str = "canary-deployment",
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
        self.event_bus = event_bus
        self.source_agent = source_agent
        self.node_id = node_id
        self.allow_live_actions = (
            _env_flag("X0TTA6BL4_ALLOW_CANARY_LIVE_ACTIONS")
            if self.config.allow_live_actions is None
            else self.config.allow_live_actions
        )

        # Current stage
        self.current_stage = DeploymentStage.CANARY
        self.current_traffic_percentage = self.config.canary_percentage

        # Metrics
        self.metrics = DeploymentMetrics(
            stage=self.current_stage,
            traffic_percentage=self.current_traffic_percentage,
            start_time=time.time(),
        )

        # Stage history
        self.stage_history: List[DeploymentMetrics] = []
        self.last_live_action_result: Optional[Dict[str, Any]] = None
        self.last_rollback_result: Optional[Dict[str, Any]] = None

        # Running state
        self._running = False
        self._rollback_triggered = False

        # Deployment integration
        self.helm_release_name = os.getenv("HELM_RELEASE_NAME", "x0tta6bl4")
        self.helm_namespace = os.getenv("HELM_NAMESPACE", "default")
        self.helm_chart_path = os.getenv("HELM_CHART_PATH", "./helm/x0tta6bl4")

        # Monitoring integration
        self.prometheus_url = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
        self.monitoring_task: Optional[asyncio.Task] = None

        logger.info(
            f"✅ Canary Deployment initialized: "
            f"canary={self.config.canary_percentage}%, "
            f"stages={self.config.gradual_stages}%, "
            f"helm_release={self.helm_release_name}, "
            f"live_actions_authorized={self.allow_live_actions}"
        )

    def _publish_live_action_result(
        self,
        result: Dict[str, Any],
        *,
        event_type: Optional[EventType] = None,
        stage: Optional[str] = None,
    ) -> Optional[str]:
        if self.event_bus is None:
            return None
        action = str(result.get("action") or "canary_action")
        success = bool(result.get("live_action_executed"))
        selected_type = event_type or (
            EventType.PIPELINE_STAGE_END if success else EventType.TASK_FAILED
        )
        selected_stage = stage or ("actuator_completed" if success else "actuator_failed")
        payload = {
            "component": "deployment.canary",
            "stage": selected_stage,
            "operation": action,
            "resource": f"deployment:canary:{action}",
            "node_id": self.node_id,
            "context": {
                "live_action_authorized": bool(result.get("live_action_authorized")),
                "command_metadata_present": result.get("command_metadata") is not None,
                "rollback_recommended": bool(result.get("rollback_recommended")),
                "raw_context_values_redacted": True,
            },
            "success": success,
            "simulated": False,
            "safe_actuator": True,
            "safe_actuator_evidence_metadata": result.get(
                "safe_actuator_evidence_metadata",
                _safe_actuator_evidence_metadata(
                    action=action,
                    live_action_authorized=bool(result.get("live_action_authorized")),
                    live_action_executed=success,
                    rollback_recommended=bool(result.get("rollback_recommended")),
                ),
            ),
            "traffic_shift_claim_allowed": False,
            "live_customer_traffic_proven": False,
            "production_readiness_claim_allowed": False,
            "production_slo_claim_allowed": False,
            "claim_boundary": CANARY_DEPLOYMENT_CLAIM_BOUNDARY,
            "redacted": True,
        }
        try:
            event = self.event_bus.publish(
                selected_type,
                self.source_agent,
                payload,
                priority=7,
            )
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish canary deployment event: %s", exc)
            return None

    def _live_action_blocked_result(
        self,
        action: str,
        *,
        rollback_recommended: bool = False,
    ) -> Dict[str, Any]:
        return {
            "action": action,
            "live_action_authorized": False,
            "live_action_executed": False,
            "blocked_by": "X0TTA6BL4_ALLOW_CANARY_LIVE_ACTIONS",
            **_claim_boundary_fields(
                action=action,
                rollback_recommended=rollback_recommended,
            ),
        }

    def _record_live_action_blocked(self, action: str) -> Dict[str, Any]:
        result = self._live_action_blocked_result(action)
        self.last_live_action_result = result
        self._publish_live_action_result(
            result,
            event_type=EventType.TASK_BLOCKED,
            stage="live_action_blocked",
        )
        logger.warning(
            "Canary live action blocked: %s. Set "
            "X0TTA6BL4_ALLOW_CANARY_LIVE_ACTIONS=yes only after current rollout "
            "evidence has been reviewed.",
            action,
        )
        return result

    def _command_result_metadata(self, result: subprocess.CompletedProcess) -> Dict[str, Any]:
        return {
            "returncode": result.returncode,
            "stdout_metadata": _bounded_output_metadata(result.stdout or ""),
            "stderr_metadata": _bounded_output_metadata(result.stderr or ""),
        }

    def _is_helm_deployment(self) -> bool:
        """Return whether Helm metadata is configured; this is not live proof."""
        return bool(self.helm_release_name and self.helm_chart_path)

    def _deploy_canary_version(self, new_version: str) -> bool:
        """Request canary version deployment only when live actions are authorized."""
        if not self.allow_live_actions:
            self._record_live_action_blocked("deploy_canary_version")
            return False

        result = safe_run(
            [
                "helm",
                "upgrade",
                self.helm_release_name,
                self.helm_chart_path,
                "--namespace",
                self.helm_namespace,
                "--set",
                f"image.tag={new_version}",
                "--set",
                f"canary.weight={self.current_traffic_percentage}",
                "--wait",
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
        command_metadata = self._command_result_metadata(result)
        self.last_live_action_result = {
            "action": "deploy_canary_version",
            "live_action_authorized": True,
            "live_action_executed": result.returncode == 0,
            "command_metadata": command_metadata,
            **_claim_boundary_fields(
                action="deploy_canary_version",
                live_action_authorized=True,
                live_action_executed=result.returncode == 0,
                command_metadata=command_metadata,
            ),
        }
        self._publish_live_action_result(self.last_live_action_result)
        if result.returncode == 0:
            logger.info("✅ Canary version deployment command completed")
            return True
        logger.warning(
            "Canary version deployment command failed: %s",
            self.last_live_action_result["command_metadata"],
        )
        return False

    def _update_helm_traffic_percentage(self) -> bool:
        """Request Helm traffic-weight update only when live actions are authorized."""
        if not self.allow_live_actions:
            self._record_live_action_blocked("update_helm_traffic_percentage")
            return False

        result = safe_run(
            [
                "helm",
                "upgrade",
                self.helm_release_name,
                self.helm_chart_path,
                "--namespace",
                self.helm_namespace,
                "--reuse-values",
                "--set",
                f"canary.weight={self.current_traffic_percentage}",
                "--wait",
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
        command_metadata = self._command_result_metadata(result)
        self.last_live_action_result = {
            "action": "update_helm_traffic_percentage",
            "live_action_authorized": True,
            "live_action_executed": result.returncode == 0,
            "command_metadata": command_metadata,
            **_claim_boundary_fields(
                action="update_helm_traffic_percentage",
                live_action_authorized=True,
                live_action_executed=result.returncode == 0,
                command_metadata=command_metadata,
            ),
        }
        self._publish_live_action_result(self.last_live_action_result)
        if result.returncode == 0:
            logger.info("✅ Helm canary traffic-weight command completed")
            return True
        logger.warning(
            "Helm canary traffic-weight command failed: %s",
            self.last_live_action_result["command_metadata"],
        )
        return False

    def _helm_rollback(self) -> bool:
        """Request Helm rollback only when live actions are authorized."""
        if not self.allow_live_actions:
            self._record_live_action_blocked("helm_rollback")
            return False

        result = safe_run(
            [
                "helm",
                "rollback",
                self.helm_release_name,
                "--namespace",
                self.helm_namespace,
                "--wait",
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
        command_metadata = self._command_result_metadata(result)
        self.last_live_action_result = {
            "action": "helm_rollback",
            "live_action_authorized": True,
            "live_action_executed": result.returncode == 0,
            "command_metadata": command_metadata,
            **_claim_boundary_fields(
                action="helm_rollback",
                live_action_authorized=True,
                live_action_executed=result.returncode == 0,
                command_metadata=command_metadata,
                rollback_recommended=True,
            ),
        }
        self._publish_live_action_result(self.last_live_action_result)
        if result.returncode == 0:
            logger.info("✅ Helm rollback command completed")
            return True
        logger.warning(
            "Helm rollback command failed: %s",
            self.last_live_action_result["command_metadata"],
        )
        return False

    def start(self, new_version: Optional[str] = None):
        """
        Start canary deployment.

        Args:
            new_version: Version tag for new deployment (e.g., "3.4.1")
        """
        self._running = True
        self.current_stage = DeploymentStage.CANARY
        self.current_traffic_percentage = self.config.canary_percentage
        self.metrics.start_time = time.time()

        logger.info(
            f"🚀 Canary deployment started: {self.current_traffic_percentage}% traffic"
        )

        # Deploy canary version if specified
        if new_version:
            self._deploy_canary_version(new_version)

        # Start monitoring task
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                self.monitoring_task = asyncio.create_task(self._monitor_deployment())
            else:
                loop.run_until_complete(self._monitor_deployment())
        except RuntimeError:
            # No event loop, will be started manually
            pass

    async def _monitor_deployment(self):
        """Monitor local canary metrics without promoting them to production proof."""
        while self._running and not self._rollback_triggered:
            if self.metrics_collector:
                try:
                    observed = self.metrics_collector()
                    self.metrics.requests_total = int(
                        observed.get("requests_total", self.metrics.requests_total)
                    )
                    self.metrics.requests_success = int(
                        observed.get("requests_success", self.metrics.requests_success)
                    )
                    self.metrics.requests_error = int(
                        observed.get("requests_error", self.metrics.requests_error)
                    )
                    self.metrics.errors_per_minute = float(
                        observed.get("errors_per_minute", self.metrics.errors_per_minute)
                    )
                    if self.metrics.requests_total > 0:
                        self.metrics.success_rate = (
                            self.metrics.requests_success / self.metrics.requests_total
                        )
                except Exception as exc:
                    logger.warning(
                        "Canary metrics collection failed with redacted error type: %s",
                        type(exc).__name__,
                    )

            self._check_rollback_conditions()
            await asyncio.sleep(self.config.health_check_interval)

    def stop(self):
        """Stop deployment."""
        self._running = False

        # Stop monitoring task
        if self.monitoring_task and not self.monitoring_task.done():
            self.monitoring_task.cancel()

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

        if not self.allow_live_actions:
            self.last_rollback_result = {
                "rollback_recommended": True,
                "rollback_executed": False,
                "rollback_reason": reason,
                **self._live_action_blocked_result(
                    "rollback",
                    rollback_recommended=True,
                ),
            }
            self.last_live_action_result = self.last_rollback_result
            logger.warning(
                "Rollback recommendation recorded; no live rollback command was "
                "executed because X0TTA6BL4_ALLOW_CANARY_LIVE_ACTIONS is not yes."
            )
            return

        # Integrated rollback with deployment system
        rollback_success = False

        try:
            # Try Helm rollback first (if using Helm)
            if self._is_helm_deployment():
                rollback_success = self._helm_rollback()

            # Try Kubernetes rollback (if in K8s environment)
            if not rollback_success:
                if os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount"):
                    deployment_name = os.getenv(
                        "K8S_DEPLOYMENT_NAME", self.helm_release_name
                    )
                    namespace = os.getenv("K8S_NAMESPACE", self.helm_namespace)

                    result = safe_run(
                        [
                            "kubectl",
                            "rollout",
                            "undo",
                            f"deployment/{deployment_name}",
                            "-n",
                            namespace,
                        ],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    kubectl_undo_metadata = self._command_result_metadata(result)
                    if result.returncode == 0:
                        logger.info(
                            f"✅ Kubernetes rollback initiated for {deployment_name}"
                        )
                        rollback_success = True

                        # Wait for rollout to complete
                        result = safe_run(
                            [
                                "kubectl",
                                "rollout",
                                "status",
                                f"deployment/{deployment_name}",
                                "-n",
                                namespace,
                                "--timeout=60s",
                            ],
                            capture_output=True,
                            text=True,
                            timeout=65,
                        )
                        kubectl_status_metadata = self._command_result_metadata(result)
                        if result.returncode == 0:
                            logger.info("✅ Kubernetes rollback status command completed")
                        else:
                            logger.warning(
                                "Kubernetes rollback status check failed: %s",
                                kubectl_status_metadata,
                            )
                    else:
                        logger.warning(
                            "Kubernetes rollback command failed: %s",
                            kubectl_undo_metadata,
                        )

            # Try Docker Compose rollback if K8s failed or not available
            if not rollback_success:
                rollback_success = self._docker_compose_rollback()

            # Try CI/CD integration (GitLab/GitHub Actions/Jenkins/CircleCI)
            if not rollback_success:
                rollback_success = self._trigger_cicd_rollback()

        except FileNotFoundError:
            # kubectl not available, try Docker Compose
            rollback_success = self._docker_compose_rollback()
        except Exception as e:
            logger.error(
                "Rollback failed with redacted error type: %s", type(e).__name__
            )

        # Final fallback: scale down canary
        if not rollback_success:
            logger.warning(
                "All rollback methods failed, scaling down canary as fallback"
            )
            rollback_success = self._scale_down_canary()

        self.last_rollback_result = {
            "rollback_recommended": True,
            "rollback_executed": bool(rollback_success),
            "rollback_reason": reason,
            "live_action_authorized": True,
            "live_action_executed": bool(rollback_success),
            **_claim_boundary_fields(
                action="rollback",
                live_action_authorized=True,
                live_action_executed=bool(rollback_success),
                rollback_recommended=True,
            ),
        }

    def _docker_compose_rollback(self) -> bool:
        """Rollback using Docker Compose."""
        if not self.allow_live_actions:
            self._record_live_action_blocked("docker_compose_rollback")
            return False

        try:
            from src.core.security.subprocess_validator import safe_run
            import subprocess

            result = safe_run(
                [
                    "docker",
                    "compose",
                    "-f",
                    "staging/docker-compose.staging.yml",
                    "rollback",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            command_metadata = self._command_result_metadata(result)
            self.last_live_action_result = {
                "action": "docker_compose_rollback",
                "live_action_authorized": True,
                "live_action_executed": result.returncode == 0,
                "command_metadata": command_metadata,
                **_claim_boundary_fields(
                    action="docker_compose_rollback",
                    live_action_authorized=True,
                    live_action_executed=result.returncode == 0,
                    command_metadata=command_metadata,
                    rollback_recommended=True,
                ),
            }
            if result.returncode == 0:
                logger.info("✅ Docker Compose rollback command completed")
                return True
            else:
                logger.warning("Docker Compose rollback failed: %s", command_metadata)
        except Exception as e:
            logger.error(
                "Docker Compose rollback failed with redacted error type: %s",
                type(e).__name__,
            )
        return False

    def _scale_down_canary(self) -> bool:
        """Scale down canary deployment as fallback."""
        if not self.allow_live_actions:
            self._record_live_action_blocked("scale_down_canary")
            return False

        try:
            from src.core.security.subprocess_validator import safe_run
            import subprocess

            # Scale canary to 0 replicas
            result = safe_run(
                ["kubectl", "scale", "deployment/x0tta6bl4-canary", "--replicas=0"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            command_metadata = self._command_result_metadata(result)
            self.last_live_action_result = {
                "action": "scale_down_canary",
                "live_action_authorized": True,
                "live_action_executed": result.returncode == 0,
                "command_metadata": command_metadata,
                **_claim_boundary_fields(
                    action="scale_down_canary",
                    live_action_authorized=True,
                    live_action_executed=result.returncode == 0,
                    command_metadata=command_metadata,
                    rollback_recommended=True,
                ),
            }
            if result.returncode == 0:
                logger.info("✅ Canary scale-down command completed")
                return True
            logger.warning("Canary scale-down command failed: %s", command_metadata)
        except Exception as e:
            logger.error(
                "Canary scale-down failed with redacted error type: %s",
                type(e).__name__,
            )
        return False

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

        # Create new metrics for next stage
        old_stage = self.current_stage

        # Advance to next stage
        if self.current_stage == DeploymentStage.CANARY:
            if self.config.gradual_stages:
                self.current_stage = DeploymentStage.GRADUAL_10
                self.current_traffic_percentage = self.config.gradual_stages[0]
                logger.info(
                    f"📈 Advanced to {self.current_traffic_percentage}% traffic"
                )

        elif self.current_stage == DeploymentStage.GRADUAL_10:
            if len(self.config.gradual_stages) > 1:
                self.current_stage = DeploymentStage.GRADUAL_50
                self.current_traffic_percentage = self.config.gradual_stages[1]
                logger.info(
                    f"📈 Advanced to {self.current_traffic_percentage}% traffic"
                )

        elif self.current_stage == DeploymentStage.GRADUAL_50:
            if len(self.config.gradual_stages) > 2:
                self.current_stage = DeploymentStage.FULL
                self.current_traffic_percentage = self.config.gradual_stages[2]
                logger.info(
                    f"📈 Advanced to {self.current_traffic_percentage}% traffic (FULL)"
                )

        # If stage changed, update deployment
        if self.current_stage != old_stage:
            # Update Helm traffic percentage if using Helm
            if self._is_helm_deployment():
                self._update_helm_traffic_percentage()

            # Reset metrics for new stage
            self.metrics = DeploymentMetrics(
                stage=self.current_stage,
                traffic_percentage=self.current_traffic_percentage,
                start_time=time.time(),
            )
            return True

        # Already at full deployment
        return False

    def get_deployment_status(self) -> Dict[str, Any]:
        """Получить статус deployment."""
        status = {
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
                "duration_seconds": time.time() - self.metrics.start_time,
            },
            "stage_history": [
                {
                    "stage": m.stage.value,
                    "traffic_percentage": m.traffic_percentage,
                    "success_rate": m.success_rate,
                    "duration": m.duration,
                }
                for m in self.stage_history
            ],
            "integration": {
                "helm_enabled": self._is_helm_deployment(),
                "helm_release": (
                    self.helm_release_name if self._is_helm_deployment() else None
                ),
                "prometheus_enabled": bool(self.prometheus_url),
                "monitoring_active": self.monitoring_task is not None
                and not self.monitoring_task.done(),
                "live_actions_authorized": self.allow_live_actions,
            },
            "last_live_action_result": self.last_live_action_result,
            "last_rollback_result": self.last_rollback_result,
            **_claim_boundary_fields(
                action="get_deployment_status",
                metrics_observed=self.metrics.requests_total > 0,
                rollback_recommended=self._rollback_triggered,
            ),
        }
        return status

    def _trigger_cicd_rollback(self) -> bool:
        """
        Trigger rollback via CI/CD system APIs.

        Supports:
        - GitLab CI/CD
        - GitHub Actions
        - Jenkins
        - CircleCI
        - Azure DevOps

        Returns:
            True if rollback was triggered successfully
        """
        import os

        if not self.allow_live_actions:
            self._record_live_action_blocked("cicd_rollback")
            return False

        ci_system = os.getenv("CI_SYSTEM", "").lower()

        # GitLab CI/CD
        if ci_system == "gitlab" or "GITLAB_CI" in os.environ:
            try:
                project_id = os.getenv("CI_PROJECT_ID")
                pipeline_id = os.getenv("CI_PIPELINE_ID")
                gitlab_token = os.getenv("GITLAB_TOKEN") or os.getenv("CI_JOB_TOKEN")

                if project_id and pipeline_id and gitlab_token:
                    import httpx

                    # Cancel current pipeline and trigger rollback pipeline
                    url = f"https://gitlab.com/api/v4/projects/{project_id}/pipelines/{pipeline_id}/cancel"
                    headers = {"PRIVATE-TOKEN": gitlab_token}

                    response = httpx.post(url, headers=headers, timeout=10)
                    if response.status_code == 200:
                        logger.info(f"✅ GitLab pipeline {pipeline_id} cancelled")

                        # Trigger rollback pipeline
                        rollback_url = (
                            f"https://gitlab.com/api/v4/projects/{project_id}/pipeline"
                        )
                        rollback_data = {
                            "ref": "main",
                            "variables": [{"key": "ROLLBACK", "value": "true"}],
                        }
                        rollback_response = httpx.post(
                            rollback_url,
                            headers=headers,
                            json=rollback_data,
                            timeout=10,
                        )
                        if rollback_response.status_code == 201:
                            logger.info("✅ GitLab rollback pipeline triggered")
                            self.last_live_action_result = {
                                "action": "cicd_rollback",
                                "provider": "gitlab",
                                "live_action_authorized": True,
                                "live_action_executed": True,
                                "cancel_status_code": response.status_code,
                                "rollback_status_code": rollback_response.status_code,
                                **_claim_boundary_fields(
                                    action="cicd_rollback",
                                    live_action_authorized=True,
                                    live_action_executed=True,
                                    rollback_recommended=True,
                                ),
                            }
                            return True
            except Exception as e:
                logger.warning(
                    "GitLab rollback failed with redacted error type: %s",
                    type(e).__name__,
                )

        # GitHub Actions
        elif ci_system == "github" or "GITHUB_ACTIONS" in os.environ:
            try:
                repo = os.getenv("GITHUB_REPOSITORY")
                github_token = os.getenv("GITHUB_TOKEN")
                workflow_id = os.getenv("GITHUB_WORKFLOW_ID", "rollback.yml")

                if repo and github_token:
                    import httpx

                    # Trigger rollback workflow
                    url = f"https://api.github.com/repos/{repo}/actions/workflows/{workflow_id}/dispatches"
                    headers = {
                        "Authorization": f"token {github_token}",
                        "Accept": "application/vnd.github.v3+json",
                    }
                    data = {"ref": "main", "inputs": {"rollback": "true"}}

                    response = httpx.post(url, headers=headers, json=data, timeout=10)
                    if response.status_code == 204:
                        logger.info(
                            f"✅ GitHub Actions rollback workflow triggered for {repo}"
                        )
                        self.last_live_action_result = {
                            "action": "cicd_rollback",
                            "provider": "github",
                            "live_action_authorized": True,
                            "live_action_executed": True,
                            "rollback_status_code": response.status_code,
                            **_claim_boundary_fields(
                                action="cicd_rollback",
                                live_action_authorized=True,
                                live_action_executed=True,
                                rollback_recommended=True,
                            ),
                        }
                        return True
            except Exception as e:
                logger.warning(
                    "GitHub Actions rollback failed with redacted error type: %s",
                    type(e).__name__,
                )

        # Jenkins
        elif ci_system == "jenkins" or "JENKINS_URL" in os.environ:
            try:
                jenkins_url = os.getenv("JENKINS_URL")
                jenkins_user = os.getenv("JENKINS_USER")
                jenkins_token = os.getenv("JENKINS_TOKEN")
                job_name = os.getenv("JENKINS_JOB_NAME", "x0tta6bl4-rollback")

                if jenkins_url and jenkins_user and jenkins_token:
                    import base64

                    import httpx

                    auth = base64.b64encode(
                        f"{jenkins_user}:{jenkins_token}".encode()
                    ).decode()
                    url = f"{jenkins_url}/job/{job_name}/buildWithParameters"
                    headers = {"Authorization": f"Basic {auth}"}
                    params = {"ROLLBACK": "true"}

                    response = httpx.post(
                        url, headers=headers, params=params, timeout=10
                    )
                    if response.status_code in [200, 201]:
                        logger.info(f"✅ Jenkins rollback job triggered: {job_name}")
                        self.last_live_action_result = {
                            "action": "cicd_rollback",
                            "provider": "jenkins",
                            "live_action_authorized": True,
                            "live_action_executed": True,
                            "rollback_status_code": response.status_code,
                            **_claim_boundary_fields(
                                action="cicd_rollback",
                                live_action_authorized=True,
                                live_action_executed=True,
                                rollback_recommended=True,
                            ),
                        }
                        return True
            except Exception as e:
                logger.warning(
                    "Jenkins rollback failed with redacted error type: %s",
                    type(e).__name__,
                )

        # CircleCI
        elif ci_system == "circleci" or "CIRCLECI" in os.environ:
            try:
                circle_token = os.getenv("CIRCLE_TOKEN")
                project_slug = os.getenv("CIRCLE_PROJECT_SLUG")

                if circle_token and project_slug:
                    import httpx

                    url = f"https://circleci.com/api/v2/project/{project_slug}/pipeline"
                    headers = {"Circle-Token": circle_token}
                    data = {"branch": "main", "parameters": {"rollback": True}}

                    response = httpx.post(url, headers=headers, json=data, timeout=10)
                    if response.status_code == 201:
                        logger.info(
                            f"✅ CircleCI rollback pipeline triggered for {project_slug}"
                        )
                        self.last_live_action_result = {
                            "action": "cicd_rollback",
                            "provider": "circleci",
                            "live_action_authorized": True,
                            "live_action_executed": True,
                            "rollback_status_code": response.status_code,
                            **_claim_boundary_fields(
                                action="cicd_rollback",
                                live_action_authorized=True,
                                live_action_executed=True,
                                rollback_recommended=True,
                            ),
                        }
                        return True
            except Exception as e:
                logger.warning(
                    "CircleCI rollback failed with redacted error type: %s",
                    type(e).__name__,
                )

        # Azure DevOps
        elif ci_system == "azure" or "AZURE_DEVOPS" in os.environ:
            try:
                org = os.getenv("AZURE_DEVOPS_ORG")
                project = os.getenv("AZURE_DEVOPS_PROJECT")
                pat = os.getenv("AZURE_DEVOPS_PAT")
                pipeline_id = os.getenv("AZURE_PIPELINE_ID")

                if org and project and pat and pipeline_id:
                    import base64

                    import httpx

                    auth = base64.b64encode(f":{pat}".encode()).decode()
                    url = f"https://dev.azure.com/{org}/{project}/_apis/pipelines/{pipeline_id}/runs"
                    headers = {
                        "Authorization": f"Basic {auth}",
                        "Content-Type": "application/json",
                    }
                    data = {"resources": {}, "templateParameters": {"rollback": "true"}}

                    response = httpx.post(url, headers=headers, json=data, timeout=10)
                    if response.status_code == 200:
                        logger.info("✅ Azure DevOps rollback pipeline triggered")
                        self.last_live_action_result = {
                            "action": "cicd_rollback",
                            "provider": "azure",
                            "live_action_authorized": True,
                            "live_action_executed": True,
                            "rollback_status_code": response.status_code,
                            **_claim_boundary_fields(
                                action="cicd_rollback",
                                live_action_authorized=True,
                                live_action_executed=True,
                                rollback_recommended=True,
                            ),
                        }
                        return True
            except Exception as e:
                logger.warning(
                    "Azure DevOps rollback failed with redacted error type: %s",
                    type(e).__name__,
                )

        return False

