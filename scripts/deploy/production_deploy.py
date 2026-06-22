#!/usr/bin/env python3
"""
Gated deployment command automation for x0tta6bl4.

Handles:
- Helm chart deployments
- Blue-green deployments
- Canary deployments
- Health validation
- Automated rollback
- Deployment verification
- GitOps integration
"""

import asyncio
import hashlib
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.integration.spine import SafeActuatorEvidenceMetadata

PRODUCTION_DEPLOY_CLAIM_BOUNDARY = (
    "This script can run Kubernetes/GitOps deployment commands. Successful "
    "command completion, rollout status, pod readiness, smoke tests, canary "
    "metric checks, or service selector patches do not prove live customer "
    "traffic, traffic shifting, external DPI bypass, settlement finality, "
    "production SLOs, or production readiness without separate current evidence."
)
PRODUCTION_DEPLOY_SAFE_ACTUATOR_CLAIM_BOUNDARY = (
    "Production deploy SafeActuator metadata proves only a locally authorized "
    "deployment command attempt, readiness-preflight check, rollout/status "
    "observation, smoke-test observation, or rollback command attempt. It is "
    "not proof of traffic shifting, live customer traffic, external DPI bypass, "
    "settlement finality, production SLOs, or production readiness."
)


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").lower() == "yes"


def bounded_output_metadata(text: str) -> Dict[str, Any]:
    """Describe command output without retaining raw stdout/stderr."""
    encoded = text.encode("utf-8", errors="replace")
    return {
        "bytes": len(encoded),
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "raw_output_retained": False,
    }


def command_result_metadata(result: subprocess.CompletedProcess[str]) -> Dict[str, Any]:
    return {
        "returncode": result.returncode,
        "stdout": bounded_output_metadata(result.stdout or ""),
        "stderr": bounded_output_metadata(result.stderr or ""),
    }


def _safe_actuator_evidence_metadata(
    *,
    action: str,
    live_action_authorized: bool = False,
    live_action_executed: bool = False,
    real_readiness_checked: bool = False,
    real_readiness_passed: bool | None = None,
    health_observed: bool = False,
    smoke_test_observed: bool = False,
) -> Dict[str, Any]:
    claim_gate = {
        "schema": "x0tta6bl4.ops.production_deploy.safe_actuator_claim_gate.v1",
        "action": action,
        "local_deployment_command_attempt_claim_allowed": bool(
            live_action_authorized
        ),
        "local_deployment_command_succeeded": bool(live_action_executed),
        "local_real_readiness_preflight_claim_allowed": bool(
            real_readiness_checked
        ),
        "local_real_readiness_preflight_passed": bool(real_readiness_passed),
        "local_health_observation_claim_allowed": bool(health_observed),
        "local_smoke_test_observation_claim_allowed": bool(smoke_test_observed),
        "traffic_shift_claim_allowed": False,
        "live_customer_traffic_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "external_dpi_bypass_confirmed": False,
        "external_settlement_finality_claim_allowed": False,
        "claim_boundary": PRODUCTION_DEPLOY_SAFE_ACTUATOR_CLAIM_BOUNDARY,
        "redacted": True,
    }
    return SafeActuatorEvidenceMetadata.from_value(
        {
            "claim_gate": claim_gate,
            "cross_plane_claim_gate": {
                "schema": "x0tta6bl4.ops.production_deploy.cross_plane_claim_gate.v1",
                "allowed": False,
                "requires_rollout_evidence_for_traffic_shift_claim": True,
                "requires_customer_traffic_evidence_for_customer_claim": True,
                "requires_slo_evidence_for_production_slo_claim": True,
                "requires_readiness_review_for_production_claim": True,
                "redacted": True,
            },
            "evidence": {
                "component": "scripts.deploy.production_deploy",
                "action": action,
                "live_action_authorized": bool(live_action_authorized),
                "live_action_executed": bool(live_action_executed),
                "real_readiness_checked": bool(real_readiness_checked),
                "real_readiness_passed": bool(real_readiness_passed),
                "health_observed": bool(health_observed),
                "smoke_test_observed": bool(smoke_test_observed),
                "raw_output_redacted": True,
            },
            "source_agents": ["production-deploy-script"],
            "claim_boundary": PRODUCTION_DEPLOY_SAFE_ACTUATOR_CLAIM_BOUNDARY,
            "redacted": True,
        }
    ).to_dict()


def deployment_claim_boundary_fields(
    *,
    action: str = "production_deploy_observation",
    live_action_authorized: bool = False,
    live_action_executed: bool = False,
    real_readiness_checked: bool = False,
    real_readiness_passed: bool | None = None,
    health_observed: bool = False,
    smoke_test_observed: bool = False,
) -> Dict[str, Any]:
    return {
        "production_readiness_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "live_customer_traffic_proven": False,
        "traffic_shift_claim_allowed": False,
        "external_dpi_bypass_confirmed": False,
        "settlement_finality_confirmed": False,
        "claim_boundary": PRODUCTION_DEPLOY_CLAIM_BOUNDARY,
        "safe_actuator_evidence_metadata": _safe_actuator_evidence_metadata(
            action=action,
            live_action_authorized=live_action_authorized,
            live_action_executed=live_action_executed,
            real_readiness_checked=real_readiness_checked,
            real_readiness_passed=real_readiness_passed,
            health_observed=health_observed,
            smoke_test_observed=smoke_test_observed,
        ),
    }


class DeploymentStrategy(Enum):
    """Deployment strategies"""

    ROLLING = "rolling"
    BLUE_GREEN = "blue_green"
    CANARY = "canary"


@dataclass
class DeploymentConfig:
    """Deployment command configuration with explicit live-action authorization."""

    deployment_name: str = "x0tta6bl4"
    namespace: str = "x0tta6bl4-prod"
    chart_path: str = "./helm/x0tta6bl4"
    values_file: str = "./helm/x0tta6bl4/values-production.yaml"

    strategy: DeploymentStrategy = DeploymentStrategy.ROLLING
    image_tag: str = os.getenv("IMAGE_TAG", "latest")
    registry: str = os.getenv("DOCKER_REGISTRY", "docker.io")

    enable_gitops: bool = os.getenv("ENABLE_GITOPS", "true").lower() == "true"
    argocd_app_name: str = os.getenv("ARGOCD_APP_NAME", "x0tta6bl4")

    health_check_timeout: int = 300
    health_check_interval: int = 5

    canary_weight_initial: int = 10
    canary_weight_increment: int = 20
    canary_weight_final: int = 100
    canary_increment_interval: int = 60
    allow_live_deploy: bool = field(
        default_factory=lambda: _env_flag("x0tta6bl4_ALLOW_LIVE_DEPLOY")
    )
    real_readiness_json: str = field(
        default_factory=lambda: str(PROJECT_ROOT / "REAL_READINESS_REPORT.json")
    )
    real_readiness_md: str = field(
        default_factory=lambda: str(PROJECT_ROOT / "REAL_READINESS_REPORT.md")
    )


class KubernetesDeployer:
    """Handle Kubernetes deployment operations"""

    def __init__(self, config: DeploymentConfig):
        self.config = config

    async def check_prerequisites(self) -> bool:
        """Check deployment prerequisites"""
        try:
            logger.info("Checking deployment prerequisites...")

            # Check kubectl
            result = subprocess.run(
                ["kubectl", "version", "--client"],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                logger.error("kubectl not found or not configured")
                return False

            # Check namespace
            result = subprocess.run(
                ["kubectl", "get", "namespace", self.config.namespace],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                logger.info(f"Creating namespace: {self.config.namespace}")
                subprocess.run(
                    ["kubectl", "create", "namespace", self.config.namespace],
                    check=True,
                )

            # Check required CRDs
            crds = ["ServiceMonitor", "PodDisruptionBudget"]
            for crd in crds:
                result = subprocess.run(
                    ["kubectl", "api-resources", "--api-group=", "-o", "name"],
                    capture_output=True, text=True,
                )
                if crd.lower() not in result.stdout.lower():
                    logger.warning(f"CRD not found: {crd}")

            logger.info("Prerequisites check passed")
            return True

        except Exception as e:
            logger.error(f"Prerequisites check failed: {e}")
            return False

    async def deploy_helm(self) -> bool:
        """Deploy using Helm"""
        try:
            logger.info(
                f"Deploying with Helm (strategy: {self.config.strategy.value})"
            )

            helm_cmd = [
                "helm", "upgrade", "--install",
                self.config.deployment_name, self.config.chart_path,
                "-n", self.config.namespace,
                "-f", self.config.values_file,
                "--set", f"image.tag={self.config.image_tag}",
                "--set", f"image.repository={self.config.registry}/{self.config.deployment_name}",
                "--timeout", "10m",
                "--wait",
                "--atomic",
            ]

            result = subprocess.run(
                helm_cmd, capture_output=True, text=True,
            )

            if result.returncode == 0:
                logger.info("Helm command completed")
                return True
            else:
                logger.error(
                    "Helm command failed: %s",
                    command_result_metadata(result),
                )
                return False

        except Exception as e:
            logger.error(f"Helm deployment error: {e}")
            return False

    async def wait_for_rollout(self) -> bool:
        """Wait for rollout to complete"""
        try:
            logger.info("Waiting for deployment rollout...")

            result = subprocess.run(
                [
                    "kubectl", "-n", self.config.namespace,
                    "rollout", "status",
                    f"deployment/{self.config.deployment_name}",
                    "--timeout=5m",
                ],
                capture_output=True, text=True,
            )

            if result.returncode == 0:
                logger.info("Deployment rollout status command completed")
                return True
            else:
                logger.error(
                    "Deployment rollout status failed: %s",
                    command_result_metadata(result),
                )
                return False

        except Exception as e:
            logger.error(f"Rollout wait error: {e}")
            return False

    async def get_pods(self) -> List[Dict[str, Any]]:
        """Get deployment pods"""
        try:
            result = subprocess.run(
                [
                    "kubectl", "-n", self.config.namespace,
                    "get", "pods",
                    "-l", f"app.kubernetes.io/name={self.config.deployment_name}",
                    "-o", "json",
                ],
                capture_output=True, text=True, check=True,
            )

            data = json.loads(result.stdout)
            return data.get("items", [])

        except Exception as e:
            logger.error(f"Failed to get pods: {e}")
            return []

    async def check_pod_health(self) -> Tuple[bool, int]:
        """Check pod health status"""
        try:
            pods = await self.get_pods()
            healthy_count = 0

            for pod in pods:
                status = pod.get("status", {})
                conditions = status.get("conditions", [])

                is_ready = any(
                    c.get("type") == "Ready" and c.get("status") == "True"
                    for c in conditions
                )

                if is_ready:
                    healthy_count += 1
                else:
                    pod_name = pod.get("metadata", {}).get("name", "unknown")
                    logger.warning(f"Pod not ready: {pod_name}")

            total_count = len(pods)
            logger.info(f"Pod health: {healthy_count}/{total_count} ready")

            return healthy_count > 0, healthy_count

        except Exception as e:
            logger.error(f"Pod health check failed: {e}")
            return False, 0


class HealthValidator:
    """Validate application health"""

    def __init__(self, config: DeploymentConfig, deployer: KubernetesDeployer):
        self.config = config
        self.deployer = deployer

    async def validate_deployment(self) -> bool:
        """Validate complete deployment health"""
        try:
            logger.info("Validating deployment health...")

            start_time = time.time()

            while time.time() - start_time < self.config.health_check_timeout:
                # Check pod health
                is_healthy, pod_count = await self.deployer.check_pod_health()

                if is_healthy:
                    logger.info("Deployment validation passed")
                    return True

                logger.info(f"Waiting for deployment ({pod_count} pods healthy)...")
                await asyncio.sleep(self.config.health_check_interval)

            logger.error("Deployment health check timeout")
            return False

        except Exception as e:
            logger.error(f"Health validation error: {e}")
            return False

    async def run_smoke_tests(self) -> bool:
        """Run smoke tests on deployment"""
        try:
            logger.info("Running smoke tests...")

            # Get a pod to test
            pods = await self.deployer.get_pods()
            if not pods:
                logger.error("No pods found for testing")
                return False

            pod_name = pods[0].get("metadata", {}).get("name", "")
            if not pod_name:
                logger.error("Could not get pod name")
                return False

            # Run health check inside pod
            result = subprocess.run(
                [
                    "kubectl", "-n", self.config.namespace,
                    "exec", pod_name, "--",
                    "curl", "-s", "http://localhost:8000/health/ready",
                ],
                capture_output=True, text=True,
            )

            if result.returncode == 0:
                logger.info("Smoke test command completed")
                return True
            else:
                logger.error("Smoke test failed: %s", command_result_metadata(result))
                return False

        except Exception as e:
            logger.error(f"Smoke test error: {e}")
            return False


class CanaryDeployment:
    """Handle canary deployment strategy"""

    def __init__(self, config: DeploymentConfig, deployer: KubernetesDeployer):
        self.config = config
        self.deployer = deployer

    async def deploy_canary(self) -> bool:
        """Execute canary command sequence without promoting traffic-proof claims."""
        try:
            logger.info("Starting canary deployment command sequence")
            logger.info("Claim boundary: %s", PRODUCTION_DEPLOY_CLAIM_BOUNDARY)

            # Deploy canary version with initial weight
            success = await self.deployer.deploy_helm()
            if not success:
                return False

            current_weight = self.config.canary_weight_initial

            while current_weight < self.config.canary_weight_final:
                logger.info(
                    "Requested canary weight: %s%%; traffic shift is not proven by this log",
                    current_weight,
                )

                # Validate current weight
                if not await self._validate_canary():
                    logger.error("Canary validation failed, rolling back")
                    return False

                # Increment weight
                current_weight += self.config.canary_weight_increment
                if current_weight > self.config.canary_weight_final:
                    current_weight = self.config.canary_weight_final

                # Wait before increasing weight
                logger.info(
                    f"Waiting {self.config.canary_increment_interval}s before requesting next weight..."
                )
                await asyncio.sleep(self.config.canary_increment_interval)

            logger.info("Canary command sequence completed")
            return True

        except Exception as e:
            logger.error(f"Canary deployment error: {e}")
            return False

    async def _validate_canary(self) -> bool:
        """Validate canary metrics"""
        try:
            pod_name = await self._get_pod_name()
            if not pod_name:
                logger.warning("No pod for canary validation")
                return False

            # Check error rates from metrics
            result = subprocess.run(
                [
                    "kubectl", "-n", self.config.namespace,
                    "exec", pod_name, "--",
                    "curl", "-s", "http://localhost:8000/metrics",
                ],
                capture_output=True, text=True,
            )

            # Basic validation - metrics endpoint responds
            if result.returncode == 0 and "http_requests_total" in result.stdout:
                logger.info("Canary metrics endpoint responded with expected shape")
                return True
            else:
                logger.warning(
                    "Canary metrics check inconclusive: %s",
                    command_result_metadata(result),
                )
                return False

        except Exception as e:
            logger.error(f"Canary validation error: {e}")
            return False

    async def _get_pod_name(self) -> str:
        """Get first pod name"""
        pods = await self.deployer.get_pods()
        return pods[0].get("metadata", {}).get("name", "") if pods else ""


class BlueGreenDeployment:
    """Handle blue-green deployment strategy"""

    def __init__(self, config: DeploymentConfig, deployer: KubernetesDeployer):
        self.config = config
        self.deployer = deployer

    async def deploy_blue_green(self) -> bool:
        """Execute blue-green command sequence without promoting traffic-proof claims."""
        try:
            logger.info("Starting blue-green deployment command sequence")
            logger.info("Claim boundary: %s", PRODUCTION_DEPLOY_CLAIM_BOUNDARY)

            # Deploy green version
            green_config = DeploymentConfig(**vars(self.config))
            green_config.deployment_name = f"{self.config.deployment_name}-green"
            green_deployer = KubernetesDeployer(green_config)

            logger.info("Deploying green version...")
            success = await green_deployer.deploy_helm()
            if not success:
                return False

            # Validate green
            is_healthy, _ = await green_deployer.check_pod_health()
            if not is_healthy:
                logger.error("Green deployment validation failed")
                return False

            logger.info("Green deployment local pod readiness observed")

            # Switch traffic to green
            logger.info("Requesting service selector switch to green...")
            await self._switch_traffic("green")

            # Monitor for issues
            await asyncio.sleep(30)

            logger.info("Blue-green command sequence completed")
            return True

        except Exception as e:
            logger.error(f"Blue-green deployment error: {e}")
            return False

    async def _switch_traffic(self, version: str) -> None:
        """Switch traffic between blue and green"""
        try:
            patch_json = json.dumps({"spec": {"selector": {"version": version}}})
            subprocess.run(
                [
                    "kubectl", "-n", self.config.namespace,
                    "patch", "service", self.config.deployment_name,
                    "-p", patch_json,
                ],
                check=True,
            )
            logger.info(f"Service selector patch command completed for {version}")

        except Exception as e:
            logger.error(f"Failed to switch traffic: {e}")


class GitOpsIntegration:
    """Integrate with GitOps (ArgoCD)"""

    def __init__(self, config: DeploymentConfig):
        self.config = config

    async def sync_application(self) -> bool:
        """Sync ArgoCD application"""
        try:
            if not self.config.enable_gitops:
                logger.info("GitOps disabled")
                return True

            logger.info("Syncing ArgoCD application...")

            result = subprocess.run(
                [
                    "argocd", "app", "sync", self.config.argocd_app_name,
                    "--prune",
                    "--self-heal",
                    "--timeout", "300",
                ],
                capture_output=True, text=True,
            )

            if result.returncode == 0:
                logger.info("GitOps sync successful")
                return True
            else:
                logger.error(f"GitOps sync failed: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"GitOps integration error: {e}")
            return False


class DeploymentOrchestrator:
    """Orchestrate complete deployment"""

    def __init__(self, config: Optional[DeploymentConfig] = None):
        self.config = config or DeploymentConfig()
        self.deployer = KubernetesDeployer(self.config)
        self.health_validator = HealthValidator(self.config, self.deployer)
        self.gitops = GitOpsIntegration(self.config)
        self.last_claim_gate: Dict[str, Any] = {}
        self._live_deploy_preflight_passed = False

    def require_live_deploy_preflight(self, action: str) -> bool:
        """Require explicit authorization and current evidence before live deploy."""
        self.last_claim_gate = {
            "action": action,
            "live_action_authorized": self.config.allow_live_deploy,
            "real_readiness_checked": False,
            "real_readiness_passed": False,
            **deployment_claim_boundary_fields(
                action=action,
                live_action_authorized=self.config.allow_live_deploy,
            ),
        }

        if not self.config.allow_live_deploy:
            logger.error("LIVE DEPLOY AUTHORIZATION: BLOCKED")
            logger.error(
                "Set x0tta6bl4_ALLOW_LIVE_DEPLOY=yes only after reviewing current evidence."
            )
            logger.error("Claim boundary: %s", PRODUCTION_DEPLOY_CLAIM_BOUNDARY)
            return False

        result = subprocess.run(
            [
                sys.executable,
                "scripts/ops/check_real_readiness.py",
                "--write-json",
                self.config.real_readiness_json,
                "--write-md",
                self.config.real_readiness_md,
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        self.last_claim_gate["real_readiness_checked"] = True
        self.last_claim_gate["real_readiness_result"] = command_result_metadata(result)
        self.last_claim_gate.update(
            deployment_claim_boundary_fields(
                action=action,
                live_action_authorized=True,
                real_readiness_checked=True,
                real_readiness_passed=result.returncode == 0,
            )
        )

        if result.returncode != 0:
            logger.error("REAL READINESS GATE: BLOCKED")
            logger.error("Report: %s", self.config.real_readiness_json)
            logger.error("Claim boundary: %s", PRODUCTION_DEPLOY_CLAIM_BOUNDARY)
            return False

        self.last_claim_gate["real_readiness_passed"] = True
        self._live_deploy_preflight_passed = True
        return True

    def require_live_action_authorization(self, action: str) -> bool:
        """Require explicit authorization for standalone live rollback-like actions."""
        self.last_claim_gate = {
            "action": action,
            "live_action_authorized": self.config.allow_live_deploy,
            "real_readiness_checked": False,
            "real_readiness_passed": None,
            **deployment_claim_boundary_fields(
                action=action,
                live_action_authorized=self.config.allow_live_deploy,
            ),
        }

        if not self.config.allow_live_deploy:
            logger.error("LIVE ACTION AUTHORIZATION: BLOCKED")
            logger.error("Set x0tta6bl4_ALLOW_LIVE_DEPLOY=yes before live cluster actions.")
            logger.error("Claim boundary: %s", PRODUCTION_DEPLOY_CLAIM_BOUNDARY)
            return False

        return True

    async def execute_deployment(self) -> bool:
        """Execute gated deployment command sequence."""
        try:
            logger.info("Starting gated deployment command sequence")
            logger.info(f"   Namespace: {self.config.namespace}")
            logger.info(f"   Strategy: {self.config.strategy.value}")
            logger.info(f"   Image tag: {self.config.image_tag}")
            logger.info("Claim boundary: %s", PRODUCTION_DEPLOY_CLAIM_BOUNDARY)

            if not self.require_live_deploy_preflight("deploy"):
                return False

            # Check prerequisites
            if not await self.deployer.check_prerequisites():
                return False

            # Choose strategy
            if self.config.strategy == DeploymentStrategy.CANARY:
                canary = CanaryDeployment(self.config, self.deployer)
                success = await canary.deploy_canary()

            elif self.config.strategy == DeploymentStrategy.BLUE_GREEN:
                bg = BlueGreenDeployment(self.config, self.deployer)
                success = await bg.deploy_blue_green()

            else:  # ROLLING
                success = await self.deployer.deploy_helm()

            if not success:
                logger.error("Deployment failed")
                return False

            # Wait for rollout
            if not await self.deployer.wait_for_rollout():
                return False

            # Validate health
            if not await self.health_validator.validate_deployment():
                logger.error("Health validation failed, rolling back")
                await self.rollback(preflight_checked=True)
                return False

            # Run smoke tests
            if not await self.health_validator.run_smoke_tests():
                logger.error("Smoke tests failed")
                await self.rollback(preflight_checked=True)
                return False

            # GitOps sync
            await self.gitops.sync_application()

            logger.info("Deployment command sequence completed")
            logger.info("Claim boundary: %s", PRODUCTION_DEPLOY_CLAIM_BOUNDARY)
            return True

        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            if self._live_deploy_preflight_passed:
                await self.rollback(preflight_checked=True)
            return False

    async def rollback(self, preflight_checked: bool = False) -> bool:
        """Run rollback command after explicit live-action authorization."""
        try:
            if not preflight_checked and not self.require_live_action_authorization(
                "rollback"
            ):
                return False

            logger.info("Rolling back deployment...")

            result = subprocess.run(
                [
                    "kubectl", "-n", self.config.namespace,
                    "rollout", "undo",
                    f"deployment/{self.config.deployment_name}",
                ],
                capture_output=True, text=True,
            )

            if result.returncode == 0:
                logger.info("Rollback command completed")
                return True
            else:
                logger.error("Rollback failed: %s", command_result_metadata(result))
                return False

        except Exception as e:
            logger.error(f"Rollback error: {e}")
            return False

    async def get_status(self) -> Dict[str, Any]:
        """Get deployment status"""
        try:
            pods = await self.deployer.get_pods()
            is_healthy, pod_count = await self.deployer.check_pod_health()

            return {
                "deployment": self.config.deployment_name,
                "namespace": self.config.namespace,
                "strategy": self.config.strategy.value,
                "image_tag": self.config.image_tag,
                "pods_total": len(pods),
                "pods_healthy": pod_count,
                "healthy": is_healthy,
                "timestamp": datetime.now().isoformat(),
                **deployment_claim_boundary_fields(
                    action="status",
                    health_observed=True,
                ),
            }

        except Exception as e:
            logger.error(f"Failed to get status: {e}")
            return {
                "healthy": False,
                "error_type": type(e).__name__,
                **deployment_claim_boundary_fields(action="status"),
            }


async def main():
    """CLI entry point"""
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if len(sys.argv) < 2:
        print("Usage: python production_deploy.py <command>")
        print(f"Claim boundary: {PRODUCTION_DEPLOY_CLAIM_BOUNDARY}")
        print("\nCommands:")
        print("  deploy          - Run gated rolling deployment command sequence")
        print("  deploy-canary   - Run gated canary command sequence")
        print("  deploy-bg       - Run gated blue-green command sequence")
        print("  rollback        - Run authorized rollback command")
        print("  status          - Show deployment observation status")
        sys.exit(1)

    config = DeploymentConfig()
    orchestrator = DeploymentOrchestrator(config)

    command = sys.argv[1]

    if command == "deploy":
        success = await orchestrator.execute_deployment()
        sys.exit(0 if success else 1)

    elif command == "deploy-canary":
        config.strategy = DeploymentStrategy.CANARY
        success = await orchestrator.execute_deployment()
        sys.exit(0 if success else 1)

    elif command == "deploy-bg":
        config.strategy = DeploymentStrategy.BLUE_GREEN
        success = await orchestrator.execute_deployment()
        sys.exit(0 if success else 1)

    elif command == "rollback":
        success = await orchestrator.rollback()
        sys.exit(0 if success else 1)

    elif command == "status":
        status = await orchestrator.get_status()
        print(json.dumps(status, indent=2))

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
