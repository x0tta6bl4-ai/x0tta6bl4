from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/build_paid_task_automation_plan.py"


def load_module():
    spec = importlib.util.spec_from_file_location("build_paid_task_automation_plan", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_pipeline_assets(root: Path) -> None:
    for relative_path in [
        "src/sales/product_ideas.py",
        "src/sales/pilot_package.py",
        "src/sales/wallet_payment_intake.py",
        "scripts/ops/build_productization_snapshot.py",
        "docs/commercial/PAYMENT_INTAKE.md",
    ]:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("asset\n", encoding="utf-8")


def test_paid_task_automation_plan_renders_goal_and_sources(tmp_path: Path) -> None:
    module = load_module()
    _write_pipeline_assets(tmp_path)

    plan = module.build_plan(tmp_path, generated_at_utc="2026-06-03T00:00:00Z")
    markdown = module.render_markdown(plan)

    assert plan["schema"] == module.SCHEMA
    assert plan["pipeline"]["status"] == "pipeline_ready"
    assert "x0tta6bl4 Paid Task Automation Plan" in markdown
    assert "GH Bounty" in markdown
    assert "Algora" in markdown
    assert "Superteam Earn" in markdown
    assert "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099" in markdown
    assert "collect_paid_task_listings.py" in markdown
    assert "score_paid_task_listings.py" in markdown
    assert "Funds received claim allowed: False" in markdown
    assert "No CAPTCHA bypass" in markdown


def test_paid_task_automation_plan_cli_writes_artifacts(tmp_path: Path) -> None:
    _write_pipeline_assets(tmp_path)
    output_md = tmp_path / "plan.md"
    output_json = tmp_path / "plan.json"

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
    assert summary["status"] == "pipeline_ready"
    assert summary["sources_total"] == 6
    assert summary["funds_received_claim_allowed"] is False
    assert output_md.exists()
    assert output_json.exists()
