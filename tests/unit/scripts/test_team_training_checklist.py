import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]


def _load_module():
    path = ROOT / "scripts/team_training_checklist.py"
    spec = importlib.util.spec_from_file_location("team_training_checklist", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_training_docs(root: Path) -> None:
    docs = root / "docs/team"
    docs.mkdir(parents=True, exist_ok=True)
    for name in (
        "ON_CALL_RUNBOOK.md",
        "INCIDENT_RESPONSE_PLAN.md",
        "READINESS_CHECKLIST.md",
    ):
        (docs / name).write_text("# Local training doc\n", encoding="utf-8")


def test_team_training_report_is_documentation_only_not_production_ready(tmp_path):
    module = _load_module()
    _write_training_docs(tmp_path)
    module.project_root = tmp_path

    report = module.training_documentation_report()

    assert report["all_training_materials_present"] is True
    assert report["production_deployment_ready"] is False
    assert report["production_deployment_claim_allowed"] is False
    assert "does not prove team training was completed" in report["claim_boundary"]
    assert "production deployment readiness" in report["claim_boundary"]


def test_team_training_main_prints_claim_boundary_for_complete_docs(
    tmp_path,
    capsys,
):
    module = _load_module()
    _write_training_docs(tmp_path)
    module.project_root = tmp_path

    with pytest.raises(SystemExit) as exit_info:
        module.main()

    output = capsys.readouterr().out
    assert exit_info.value.code == 0
    assert "ALL TRAINING DOCUMENTATION PRESENT" in output
    assert "ALL DOCUMENTATION READY" not in output
    assert "Claim boundary:" in output
    assert "does not prove team training was completed" in output
    assert "production deployment readiness" in output


def test_team_training_source_does_not_claim_ready_for_production_deployment():
    text = (ROOT / "scripts/team_training_checklist.py").read_text(encoding="utf-8")

    assert "ready for production deployment" not in text.lower()
    assert "production_deployment_claim_allowed" in text
