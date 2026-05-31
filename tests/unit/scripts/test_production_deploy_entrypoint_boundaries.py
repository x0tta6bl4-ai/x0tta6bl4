import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_smoke_production_is_local_observation_not_deployment_readiness():
    text = _read("scripts/smoke_production.sh")

    assert "X0TTA6BL4_ALLOW_LOCAL_PRODUCTION_SMOKE" in text
    assert "LOCAL PRODUCTION-COMPOSE SMOKE: BLOCKED" in text
    assert "raw_output_retained=false" in text
    assert "MaaS Enterprise is ready for deployment." not in text
    assert "SMOKE TEST COMPLETED SUCCESSFULLY" not in text
    assert "not production deployment readiness proof" in text
    assert "docker-compose -f docker-compose.production.yml logs janitor" not in text


def test_smoke_production_blocks_before_docker_without_local_authorization():
    env = os.environ.copy()
    env.pop("X0TTA6BL4_ALLOW_LOCAL_PRODUCTION_SMOKE", None)

    result = subprocess.run(
        ["bash", str(ROOT / "scripts/smoke_production.sh")],
        check=False,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 2
    assert "LOCAL PRODUCTION-COMPOSE SMOKE: BLOCKED" in result.stdout
    assert "Building containers" not in result.stdout


def test_deploy_production_is_gated_before_live_cluster_changes():
    text = _read("scripts/deploy_production.sh")

    assert "scripts/ops/check_real_readiness.py" in text
    assert "REAL READINESS GATE: BLOCKED" in text
    assert "X0TTA6BL4_ALLOW_LIVE_DEPLOY=yes" in text
    assert "Deployment Completed Successfully" not in text
    assert "Deployment is ready" not in text
    assert "Deployment Command Sequence Completed" in text
    assert "not production readiness" in text


def test_production_toolkit_is_relative_ops_toolkit_with_claim_boundary():
    text = _read("scripts/production_toolkit.sh")

    assert 'PROJECT_ROOT="/mnt/AC74CC2974CBF3DC"' not in text
    assert 'ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"' in text
    assert "OPERATIONS TOOLKIT" in text
    assert "Claim boundary:" in text
    assert "Monitoring observation" in text
    assert "Gated deployment orchestration" in text
    assert "PRODUCTION TOOLKIT" not in text
