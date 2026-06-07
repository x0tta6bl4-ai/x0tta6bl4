from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

from src.sales.product_ideas import PRODUCT_IDEAS


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/export_product_idea_portfolio.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "export_product_idea_portfolio",
        SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_scaffold_assets(root: Path) -> None:
    for idea in PRODUCT_IDEAS:
        for relative_path in idea.existing_repo_paths:
            path = root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("scaffold\n", encoding="utf-8")


def test_product_idea_export_builds_markdown_and_json(tmp_path: Path) -> None:
    module = load_module()
    _write_scaffold_assets(tmp_path)

    export = module.build_export(tmp_path, generated_at_utc="2026-06-02T00:00:00Z")
    markdown = module.render_markdown(export)

    assert export["schema"] == module.SCHEMA
    assert export["portfolio"]["ideas_total"] == 10
    assert export["portfolio"]["repo_scaffold_ready"] == 10
    assert export["pilot_package"]["offer_name"] == "Self-hosted secure mesh access pilot"
    assert "x0tta6bl4 Product Idea Portfolio" in markdown
    assert "First Paid Pilot" in markdown
    assert "Self-hosted secure mesh access pilot" in markdown
    assert "AI agent black box" in markdown
    assert "Industrial edge AI commander" in markdown
    assert "Demo scenario: agent_black_box.demo.v1" in markdown
    assert "check_claim_gate" in markdown
    assert "Production readiness claim allowed: False" in markdown
    assert "does not prove production readiness" in markdown


def test_product_idea_export_cli_writes_artifacts(tmp_path: Path) -> None:
    _write_scaffold_assets(tmp_path)
    output_md = tmp_path / "portfolio.md"
    output_json = tmp_path / "portfolio.json"

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
    assert summary["ideas_total"] == 10
    assert summary["status"] == "portfolio_ready"
    assert output_md.exists()
    assert output_json.exists()
    report = json.loads(output_json.read_text(encoding="utf-8"))
    assert report["portfolio"]["claim_gate"]["production_readiness_claim_allowed"] is False
    assert report["pilot_package"]["target_idea_id"] == "paranoid_self_hosted_mesh"
    assert report["pilot_package"]["claim_gate"]["customer_traffic_claim_allowed"] is False
