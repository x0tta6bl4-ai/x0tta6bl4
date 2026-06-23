from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
RUNNER = ROOT / "scripts/ops/run_synthetic_dpi_smoke.py"


def _load():
    spec = importlib.util.spec_from_file_location(
        "run_synthetic_dpi_smoke_test",
        RUNNER,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_report_is_local_only_and_claim_bounded(tmp_path: Path) -> None:
    module = _load()

    report = module.build_report(output_path=tmp_path / "synthetic-dpi.json")
    rendered = json.dumps(report, sort_keys=True)

    assert report["status"] == "SYNTHETIC_TEST_ONLY"
    assert report["result_summary"]["decision"] == "SYNTHETIC_SMOKE_PASS"
    assert report["result_summary"]["mechanics_verified"] is True
    assert report["claim_boundary"]["external_dpi_tested"] is False
    assert report["claim_boundary"]["production_ready"] is False
    assert report["claim_boundary"]["durable_censorship_bypass_confirmed"] is False
    assert report["measurements"]["baseline"]["http_status"] == 451
    assert report["measurements"]["treatment"]["http_status"] == 200
    assert "127.0.0.1" in report["measurements"]["baseline_url"]
    assert "127.0.0.1" in report["measurements"]["treatment_url"]
    assert "192.0.2.1" not in rendered
    assert "external-dpi-proof-missing" in rendered


def test_cli_writes_machine_readable_report(tmp_path: Path) -> None:
    output = tmp_path / "synthetic-dpi-smoke.json"

    result = subprocess.run(
        [sys.executable, str(RUNNER), "--output", str(output), "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    report = json.loads(result.stdout)
    saved_report = json.loads(output.read_text(encoding="utf-8"))
    assert result.stderr == ""
    assert saved_report == report
    assert report["status"] == "SYNTHETIC_TEST_ONLY"
    assert report["claim_boundary"]["external_dpi_tested"] is False
