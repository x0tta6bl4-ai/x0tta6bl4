import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]


def _load_module():
    path = ROOT / "scripts/production_deployment_prep.py"
    spec = importlib.util.spec_from_file_location("production_deployment_prep", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_local_prerequisites(root: Path) -> None:
    (root / "baseline_metrics.json").write_text("{}\n", encoding="utf-8")
    for relative in (
        "docs/team/ON_CALL_RUNBOOK.md",
        "docs/team/INCIDENT_RESPONSE_PLAN.md",
        "docs/team/READINESS_CHECKLIST.md",
        "LAUNCH_READINESS_REPORT.md",
        "PRE_DEPLOYMENT_PLAN.md",
        "scripts/security_audit_checklist.py",
        "scripts/performance_baseline.py",
        "scripts/staging_deployment.py",
        "scripts/run_load_test.py",
        "scripts/run_staging_validation.sh",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# local prerequisite\n", encoding="utf-8")


def test_deployment_prep_report_is_local_prerequisites_not_production_ready(
    monkeypatch,
    tmp_path,
):
    module = _load_module()
    _write_local_prerequisites(tmp_path)
    module.project_root = tmp_path
    monkeypatch.setattr(
        module,
        "run_security_audit",
        lambda: (True, "✅ Security audit passed"),
    )

    report = module.deployment_preparation_report()

    assert report["local_prerequisites_passed"] is True
    assert report["production_deployment_ready"] is False
    assert report["production_deployment_claim_allowed"] is False
    assert "does not prove release approval" in report["claim_boundary"]
    assert "production deployment readiness" in report["claim_boundary"]


def test_deployment_prep_main_prints_claim_boundary_for_complete_local_checks(
    monkeypatch,
    tmp_path,
    capsys,
):
    module = _load_module()
    _write_local_prerequisites(tmp_path)
    module.project_root = tmp_path
    monkeypatch.setattr(
        module,
        "run_security_audit",
        lambda: (True, "✅ Security audit passed"),
    )

    with pytest.raises(SystemExit) as exit_info:
        module.main()

    output = capsys.readouterr().out
    assert exit_info.value.code == 0
    assert "DEPLOYMENT PREPARATION: LOCAL CHECKS PASSED" in output
    assert "PRODUCTION DEPLOYMENT: READY" not in output
    assert "Ready for production deployment" not in output
    assert "Claim boundary:" in output
    assert "production deployment readiness" in output


def test_deployment_prep_source_does_not_claim_ready_for_production_deployment():
    text = (ROOT / "scripts/production_deployment_prep.py").read_text(
        encoding="utf-8"
    )

    assert "ready for production deployment" not in text.lower()
    assert "production_deployment_claim_allowed" in text
