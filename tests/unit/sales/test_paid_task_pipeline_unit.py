from __future__ import annotations

from pathlib import Path

from src.sales.paid_task_pipeline import TASK_SOURCES, build_paid_task_pipeline


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


def test_paid_task_pipeline_has_goal_sources_and_claim_gate(tmp_path: Path) -> None:
    _write_pipeline_assets(tmp_path)

    pipeline = build_paid_task_pipeline(tmp_path)

    assert pipeline["schema"] == "x0tta6bl4.paid_task_pipeline.v1"
    assert pipeline["status"] == "pipeline_ready"
    assert "Find legitimate paid online tasks" in pipeline["goal"]
    assert pipeline["wallet"]["address"] == "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099"
    assert {source["source_id"] for source in pipeline["sources"]} == {
        "ghbounty",
        "gitwork",
        "algora",
        "github_paid_issue",
        "superteam_earn",
        "dework",
        "dorahacks",
    }
    assert len(pipeline["task_types"]) == 4
    assert pipeline["claim_gate"]["pipeline_claim_allowed"] is True
    assert pipeline["claim_gate"]["accepted_task_claim_allowed"] is False
    assert pipeline["claim_gate"]["funds_received_claim_allowed"] is False
    assert pipeline["claim_gate"]["settlement_finality_claim_allowed"] is False
    assert any("No CAPTCHA bypass" in item for item in pipeline["hard_no"])


def test_paid_task_pipeline_blocks_when_local_assets_are_missing(tmp_path: Path) -> None:
    pipeline = build_paid_task_pipeline(tmp_path)

    assert pipeline["status"] == "pipeline_blocked"


def test_paid_task_sources_have_human_gates_and_urls() -> None:
    for source in TASK_SOURCES:
        assert source.url.startswith("https://")
        assert source.human_gate
        assert source.allowed_ai_role
        assert source.source_basis
