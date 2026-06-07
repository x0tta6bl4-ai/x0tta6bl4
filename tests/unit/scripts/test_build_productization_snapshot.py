from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

from src.sales.product_ideas import PRODUCT_IDEAS
from src.sales.economic_layer_readiness import ECONOMIC_LAYER_PATH_SPECS


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/build_productization_snapshot.py"
READINESS_SCRIPT = ROOT / "scripts/ops/check_commercial_mesh_platform_readiness.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_ready_root(root: Path) -> None:
    readiness = load_module(READINESS_SCRIPT, "check_commercial_mesh_platform_readiness_for_snapshot_test")
    for spec in readiness.REQUIREMENT_SPECS:
        for expected_file in spec.files:
            path = root / expected_file.path
            path.parent.mkdir(parents=True, exist_ok=True)
            existing = path.read_text(encoding="utf-8") if path.exists() else ""
            path.write_text(existing + "\n" + "\n".join(expected_file.markers) + "\n", encoding="utf-8")
    for idea in PRODUCT_IDEAS:
        for relative_path in idea.existing_repo_paths:
            path = root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_text("product asset\n", encoding="utf-8")
    for path_spec in ECONOMIC_LAYER_PATH_SPECS:
        for expected_file in path_spec.expected_files:
            path = root / expected_file.path
            path.parent.mkdir(parents=True, exist_ok=True)
            existing = path.read_text(encoding="utf-8") if path.exists() else ""
            path.write_text(existing + "\n" + "\n".join(expected_file.markers) + "\n", encoding="utf-8")


def test_productization_snapshot_combines_product_and_readiness(tmp_path: Path) -> None:
    module = load_module(SCRIPT, "build_productization_snapshot")
    _write_ready_root(tmp_path)

    snapshot = module.build_snapshot(tmp_path, generated_at_utc="2026-06-02T00:00:00Z")
    markdown = module.render_markdown(snapshot)

    assert snapshot["schema"] == module.SCHEMA
    assert snapshot["summary"]["ideas_total"] == 10
    assert snapshot["summary"]["repo_scaffold_ready"] == 10
    assert snapshot["summary"]["first_pilot_status"] == "pilot_package_ready"
    assert snapshot["summary"]["payment_intake_status"] == "payment_intake_ready"
    assert snapshot["summary"]["paid_task_pipeline_status"] == "pipeline_ready"
    assert snapshot["summary"]["paid_task_sources_total"] == 6
    assert snapshot["summary"]["economic_layer_status"] == "economic_layer_local_evidence_ready"
    assert snapshot["summary"]["economic_layer_paths_total"] == 4
    assert snapshot["summary"]["economic_layer_live_revenue_ready"] is False
    assert snapshot["summary"]["x0t_chain_submission_code_path_present"] is True
    assert snapshot["summary"]["payment_wallet"] == "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099"
    assert snapshot["summary"]["commercial_readiness_ready"] is True
    assert snapshot["summary"]["funds_received_claim_allowed"] is False
    assert snapshot["summary"]["production_readiness_claim_allowed"] is False
    assert "x0tta6bl4 Productization Snapshot" in markdown
    assert "Self-hosted secure mesh access pilot" in markdown
    assert "Payment wallet: 0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099" in markdown
    assert "Paid task pipeline status: pipeline_ready" in markdown
    assert "Economic layer status: economic_layer_local_evidence_ready" in markdown
    assert "Funds received claim allowed: False" in markdown
    assert "Production readiness claim allowed: False" in markdown


def test_productization_snapshot_cli_writes_outputs(tmp_path: Path) -> None:
    _write_ready_root(tmp_path)
    output_json = tmp_path / "snapshot.json"
    output_md = tmp_path / "snapshot.md"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--root",
            str(tmp_path),
            "--write-json",
            str(output_json),
            "--write-md",
            str(output_md),
        ],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )

    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["summary"]["ideas_total"] == 10
    assert output_json.exists()
    assert output_md.exists()
    snapshot = json.loads(output_json.read_text(encoding="utf-8"))
    assert snapshot["commercial_readiness"]["ready"] is True
    assert snapshot["economic_layer"]["summary"]["live_revenue_ready"] is False
    assert snapshot["payment_export"]["payment_intake"]["claim_gate"]["funds_received_claim_allowed"] is False
    assert snapshot["paid_task_plan"]["pipeline"]["claim_gate"]["funds_received_claim_allowed"] is False
