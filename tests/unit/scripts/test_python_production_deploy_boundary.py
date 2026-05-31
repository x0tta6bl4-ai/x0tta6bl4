import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]


def _load_module():
    path = ROOT / "scripts/deploy/production_deploy.py"
    spec = importlib.util.spec_from_file_location("python_production_deploy", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_execute_deployment_blocks_before_kubectl_without_authorization(
    monkeypatch,
):
    module = _load_module()
    config = module.DeploymentConfig(allow_live_deploy=False)
    orchestrator = module.DeploymentOrchestrator(config)

    def _no_subprocess(*args, **kwargs):
        raise AssertionError("live subprocess should not run without authorization")

    async def _no_prereq():
        raise AssertionError("kubectl prerequisite check should not run")

    monkeypatch.setattr(module.subprocess, "run", _no_subprocess)
    orchestrator.deployer.check_prerequisites = _no_prereq

    result = await orchestrator.execute_deployment()

    assert result is False
    assert orchestrator.last_claim_gate["live_action_authorized"] is False
    assert orchestrator.last_claim_gate["real_readiness_checked"] is False
    assert orchestrator.last_claim_gate["production_readiness_claim_allowed"] is False


def test_live_deploy_preflight_redacts_real_readiness_output(monkeypatch):
    module = _load_module()
    config = module.DeploymentConfig(allow_live_deploy=True)
    orchestrator = module.DeploymentOrchestrator(config)

    def _fake_run(command, **kwargs):
        assert "scripts/ops/check_real_readiness.py" in command
        return module.subprocess.CompletedProcess(
            command,
            1,
            stdout="secret stdout",
            stderr="secret stderr",
        )

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    assert orchestrator.require_live_deploy_preflight("deploy") is False
    metadata = orchestrator.last_claim_gate["real_readiness_result"]
    assert metadata["returncode"] == 1
    assert metadata["stdout"]["raw_output_retained"] is False
    assert metadata["stderr"]["raw_output_retained"] is False
    assert "secret" not in str(metadata)


@pytest.mark.asyncio
async def test_status_is_observation_not_production_readiness():
    module = _load_module()
    orchestrator = module.DeploymentOrchestrator(module.DeploymentConfig())

    async def _pods():
        return [{"metadata": {"name": "pod-a"}}]

    async def _health():
        return True, 1

    orchestrator.deployer.get_pods = _pods
    orchestrator.deployer.check_pod_health = _health

    status = await orchestrator.get_status()

    assert status["healthy"] is True
    assert status["production_readiness_claim_allowed"] is False
    assert status["production_slo_claim_allowed"] is False
    assert status["live_customer_traffic_proven"] is False
    assert status["traffic_shift_claim_allowed"] is False
    assert "do not prove live customer traffic" in status["claim_boundary"]


@pytest.mark.asyncio
async def test_canary_validation_fails_closed_when_no_pod():
    module = _load_module()

    class FakeDeployer:
        async def get_pods(self):
            return []

    canary = module.CanaryDeployment(module.DeploymentConfig(), FakeDeployer())

    assert await canary._validate_canary() is False


@pytest.mark.asyncio
async def test_blue_green_uses_boolean_pod_health_not_tuple_truthiness(monkeypatch):
    module = _load_module()

    class FakeDeployer:
        async def deploy_helm(self):
            return True

        async def check_pod_health(self):
            return False, 0

    monkeypatch.setattr(module, "KubernetesDeployer", lambda config: FakeDeployer())
    deployment = module.BlueGreenDeployment(module.DeploymentConfig(), FakeDeployer())

    assert await deployment.deploy_blue_green() is False


def test_python_production_deploy_source_has_claim_gate():
    text = (ROOT / "scripts/deploy/production_deploy.py").read_text(
        encoding="utf-8"
    )

    assert "X0TTA6BL4_ALLOW_LIVE_DEPLOY" in text
    assert "scripts/ops/check_real_readiness.py" in text
    assert "production_readiness_claim_allowed" in text
    assert "Canary traffic:" not in text
    assert "Deployment completed successfully" not in text
    assert "Traffic switched to" not in text
