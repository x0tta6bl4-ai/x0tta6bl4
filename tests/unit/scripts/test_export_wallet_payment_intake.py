from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

from src.sales.pilot_package import PRIMARY_IDEA_ID
from src.sales.product_ideas import PRODUCT_IDEAS


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/export_wallet_payment_intake.py"


def load_module():
    spec = importlib.util.spec_from_file_location("export_wallet_payment_intake", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_primary_assets(root: Path) -> None:
    primary = next(idea for idea in PRODUCT_IDEAS if idea.idea_id == PRIMARY_IDEA_ID)
    for relative_path in primary.existing_repo_paths:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("asset\n", encoding="utf-8")


def test_wallet_payment_intake_export_builds_markdown(tmp_path: Path) -> None:
    module = load_module()
    _write_primary_assets(tmp_path)

    export = module.build_export(tmp_path, generated_at_utc="2026-06-03T00:00:00Z")
    markdown = module.render_markdown(export)

    assert export["schema"] == module.SCHEMA
    assert export["payment_intake"]["status"] == "payment_intake_ready"
    assert "x0tta6bl4 Payment Intake" in markdown
    assert "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099" in markdown
    assert "Payment reference: X0T-PILOT-6017E099" in markdown
    assert "Pilot deposit: USD 500" in markdown
    assert "Funds received claim allowed: False" in markdown
    assert "Settlement finality claim allowed: False" in markdown


def test_wallet_payment_intake_export_cli_writes_artifacts(tmp_path: Path) -> None:
    _write_primary_assets(tmp_path)
    output_md = tmp_path / "payment.md"
    output_json = tmp_path / "payment.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--root",
            str(tmp_path),
            "--write-md",
            str(output_md),
            "--write-json",
            str(output_json),
        ],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )

    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["status"] == "payment_intake_ready"
    assert summary["wallet"] == "0x6017...e099"
    assert summary["funds_received_claim_allowed"] is False
    assert output_md.exists()
    assert output_json.exists()
    report = json.loads(output_json.read_text(encoding="utf-8"))
    assert report["payment_intake"]["claim_gate"]["funds_received_claim_allowed"] is False
