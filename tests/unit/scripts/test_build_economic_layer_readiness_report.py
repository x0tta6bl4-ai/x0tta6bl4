from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

from src.sales.economic_layer_readiness import ECONOMIC_LAYER_PATH_SPECS


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/build_economic_layer_readiness_report.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_expected_files(root: Path) -> None:
    for path_spec in ECONOMIC_LAYER_PATH_SPECS:
        for expected_file in path_spec.expected_files:
            path = root / expected_file.path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("\n".join(expected_file.markers) + "\n", encoding="utf-8")


def test_economic_layer_readiness_report_renders_markdown(tmp_path: Path) -> None:
    module = load_module(SCRIPT, "build_economic_layer_readiness_report")
    _write_expected_files(tmp_path)

    envelope = module.build_report(tmp_path, generated_at_utc="2026-06-03T00:00:00Z")
    markdown = module.render_markdown(envelope)

    assert envelope["schema"] == "x0tta6bl4.economic_layer_readiness.v1"
    assert envelope["report"]["status"] == "economic_layer_local_evidence_ready"
    assert "x0tta6bl4 Economic Layer Readiness" in markdown
    assert "Share-to-Earn DePIN relay accounting" in markdown
    assert "Funds received claim allowed: False" in markdown


def test_economic_layer_readiness_cli_writes_outputs(tmp_path: Path) -> None:
    _write_expected_files(tmp_path)
    output_json = tmp_path / "economic.json"
    output_md = tmp_path / "economic.md"

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
    assert summary["status"] == "economic_layer_local_evidence_ready"
    assert summary["funds_received_claim_allowed"] is False
    assert output_json.exists()
    assert output_md.exists()
    envelope = json.loads(output_json.read_text(encoding="utf-8"))
    assert envelope["report"]["summary"]["live_revenue_ready"] is False
