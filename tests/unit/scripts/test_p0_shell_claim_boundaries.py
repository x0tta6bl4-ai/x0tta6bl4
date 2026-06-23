from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_p0_validation_checklist_delegates_production_claim_to_real_readiness():
    text = _read("scripts/p0_validation_checklist.sh")

    assert "scripts/ops/check_real_readiness.py" in text
    assert "REAL READINESS GATE: BLOCKED" in text
    assert "System is ready for production deployment" not in text
    assert "((passed_tests++))" not in text
    assert "((failed_tests++))" not in text
    assert "((warning_tests++))" not in text
    assert "((total_tests++))" not in text


def test_validate_p0_components_delegates_production_claim_to_real_readiness():
    text = _read("scripts/validate_p0_components.sh")

    assert "scripts/ops/check_real_readiness.py" in text
    assert "REAL READINESS GATE: BLOCKED" in text
    assert "P0 Components are ready for production validation" not in text


def test_deploy_simple_is_preparation_not_production_readiness_claim():
    text = _read("scripts/deploy_simple.sh")

    assert "PRODUCTION DEPLOYMENT" not in text
    assert "Deployment Status: ✅ READY" not in text
    assert "check_real_readiness.py" in text
    assert "not production readiness proof" in text


def test_execute_launch_delegates_production_claim_to_real_readiness():
    text = _read("scripts/execute_launch.sh")

    assert 'PROJECT_ROOT="/mnt/AC74CC2974CBF3DC"' not in text
    assert "READY FOR PRODUCTION DEPLOYMENT" not in text
    assert "scripts/ops/check_real_readiness.py" in text
    assert "REAL READINESS GATE: BLOCKED" in text
    assert "not enough for a production deployment claim" in text


def test_validate_kubernetes_deployment_is_local_manifest_preflight_only():
    text = _read("scripts/validate_kubernetes_deployment.sh")

    assert "Tests deployment manifests, health checks, and production readiness" not in text
    assert "Local Kubernetes manifest validation" in text
    assert "This is not production readiness proof." in text
    assert "does not prove live cluster rollout" in text
    assert "scripts/ops/check_real_readiness.py" in text
    assert "Kubernetes deployment validation complete" not in text


def test_run_production_validation_is_local_preflight_not_readiness_proof():
    text = _read("scripts/run_production_validation.sh")

    assert "Complete production validation suite" not in text
    assert "Running Complete Production Validation Suite" not in text
    assert "Production Validation Suite Complete" not in text
    assert "local production-claim preflight" in text
    assert "fail-closed real-readiness gate" in text
    assert "does not prove live customer traffic" in text
    assert "Production readiness still requires a passing real-readiness gate" in text
