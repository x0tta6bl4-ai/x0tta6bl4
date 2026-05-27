from pathlib import Path

from src.integration.source_runtime_surface import build_report, main


def _write(path: Path, text: str = "print('ok')\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_source_runtime_surface_reports_missing_sources(tmp_path):
    _write(tmp_path / "scripts/ops/present.py")

    report = build_report(tmp_path, ["scripts/ops/present.py", "scripts/ops/missing.py"])

    assert report["schema_version"].endswith("v3-repo-generated")
    assert "source-restored" not in report["schema_version"]
    assert report["status"] == "VERIFIED HERE"
    assert report["ok"] is True
    assert report["ready"] is False
    assert report["decision"] == "SOURCE_RUNTIME_SURFACE_BLOCKED_ON_MISSING_SOURCES"
    assert report["summary"]["critical_scripts_total"] == 2
    assert report["summary"]["critical_sources_present"] == 1
    assert report["summary"]["critical_sources_missing"] == 1
    assert report["goal_can_be_marked_complete"] is False


def test_source_runtime_surface_ready_when_sources_exist(tmp_path):
    _write(tmp_path / "scripts/ops/a.py")
    _write(tmp_path / "scripts/ops/b.py")

    report = build_report(tmp_path, ["scripts/ops/a.py", "scripts/ops/b.py"])

    assert report["ready"] is True
    assert report["decision"] == "SOURCE_RUNTIME_SURFACE_READY"
    assert report["summary"]["critical_source_backed"] == 2


def test_source_runtime_surface_cli_writes_default_report(tmp_path):
    for rel in [
        "scripts/ops/scaffold_x0t_external_settlement_evidence.py",
        "scripts/ops/verify_x0t_external_settlement_evidence.py",
        "scripts/ops/verify_x0t_external_settlement_live_rpc.py",
        "scripts/ops/run_x0t_external_settlement_operator_handoff.py",
        "scripts/ops/prefill_integration_spine_scaffold_from_retained_raw_evidence.py",
        "scripts/ops/run_integration_spine_production_input_return_acceptance.py",
        "scripts/ops/stage_integration_spine_production_input_bundle.py",
        "scripts/ops/scan_integration_spine_operator_bundle_secrets.py",
        "scripts/ops/run_integration_spine_production_input_pipeline.py",
        "scripts/ops/run_integration_spine_completion_gate.py",
        "scripts/ops/run_integration_spine_production_final_review.py",
        "scripts/ops/audit_integration_spine_objective_coverage.py",
    ]:
        _write(tmp_path / rel)

    exit_code = main(["--root", str(tmp_path), "--output-json", str(tmp_path / "surface.json"), "--require-ready"])

    assert exit_code == 0
