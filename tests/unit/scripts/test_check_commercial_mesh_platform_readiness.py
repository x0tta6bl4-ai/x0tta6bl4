from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/check_commercial_mesh_platform_readiness.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "check_commercial_mesh_platform_readiness",
        SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_ready_root(root: Path, module) -> None:
    for spec in module.REQUIREMENT_SPECS:
        for expected_file in spec.files:
            path = root / expected_file.path
            path.parent.mkdir(parents=True, exist_ok=True)
            existing = path.read_text(encoding="utf-8") if path.exists() else ""
            marker_body = "\n".join(expected_file.markers)
            path.write_text(existing + "\n" + marker_body + "\n", encoding="utf-8")


def test_static_commercial_mesh_platform_report_passes_when_markers_exist(
    tmp_path: Path,
) -> None:
    module = load_module()
    _write_ready_root(tmp_path, module)

    report = module.build_report(tmp_path)

    assert report["schema"] == module.SCHEMA
    assert report["ready"] is True
    assert report["decision"] == module.DECISION_READY
    assert report["summary"]["requirements_total"] == len(module.REQUIREMENT_SPECS)
    assert report["summary"]["passed"] == len(module.REQUIREMENT_SPECS)
    assert report["summary"]["failures"] == 0
    assert report["summary"]["static_only"] is True
    assert report["summary"]["starts_services"] is False
    assert report["summary"]["mutates_state"] is False
    assert report["summary"]["proves_production_readiness"] is False
    assert report["blockers"] == []


def test_static_commercial_mesh_platform_report_blocks_missing_marker(
    tmp_path: Path,
) -> None:
    module = load_module()
    _write_ready_root(tmp_path, module)
    roadmap = tmp_path / "ROADMAP.md"
    roadmap.write_text("Pre-Production\nRevenue readiness\n", encoding="utf-8")

    report = module.build_report(tmp_path)

    assert report["ready"] is False
    assert report["decision"] == module.DECISION_BLOCKED
    assert report["summary"]["failures"] == 1
    blockers = report["blockers"]
    assert len(blockers) == 1
    assert blockers[0]["requirement_id"] == "commercial_target_contract"
    assert "ROADMAP.md:missing_marker:Convert to paid pilots" in blockers[0]["missing"]
    assert "ROADMAP.md:missing_marker:MRR stabilization window" in blockers[0]["missing"]


def test_static_commercial_mesh_platform_report_blocks_missing_file(
    tmp_path: Path,
) -> None:
    module = load_module()
    _write_ready_root(tmp_path, module)
    (tmp_path / "agent/scripts/install.sh").unlink()

    report = module.build_report(tmp_path)

    assert report["ready"] is False
    blockers = [
        item
        for item in report["blockers"]
        if item["requirement_id"] == "device_agent_onboarding_contract"
    ]
    assert blockers
    assert "agent/scripts/install.sh:missing_file" in blockers[0]["missing"]


def test_static_commercial_mesh_platform_cli_writes_json(tmp_path: Path) -> None:
    module = load_module()
    _write_ready_root(tmp_path, module)
    output = tmp_path / "report.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--root",
            str(tmp_path),
            "--write-json",
            str(output),
            "--require-ready",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["ready"] is True
    assert report["decision"] == module.DECISION_READY
