from __future__ import annotations

from pathlib import Path

from src.sales.product_ideas import (
    PRODUCT_IDEAS,
    STRONG_CLAIMS,
    build_product_idea_portfolio,
    get_product_idea,
)


def _touch_assets(root: Path) -> None:
    for idea in PRODUCT_IDEAS:
        for relative_path in idea.existing_repo_paths:
            path = root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("asset marker\n", encoding="utf-8")


def test_product_ideas_cover_all_ten_requested_concepts(tmp_path: Path) -> None:
    _touch_assets(tmp_path)

    portfolio = build_product_idea_portfolio(tmp_path)

    assert portfolio["schema"] == "x0tta6bl4.product_ideas.portfolio.v1"
    assert portfolio["ideas_total"] == 10
    assert portfolio["repo_scaffold_ready"] == 10
    assert portfolio["status"] == "portfolio_ready"
    idea_ids = {idea["idea_id"] for idea in portfolio["ideas"]}
    assert idea_ids == {
        "agent_black_box",
        "sovereign_office",
        "crisis_internet_kit",
        "devops_truth_detector",
        "remote_infra_caretaker",
        "abandoned_places_mesh",
        "paranoid_self_hosted_mesh",
        "node_trust_passport",
        "autonomous_network_repair",
        "industrial_edge_commander",
    }


def test_each_product_idea_has_paid_offer_and_blocks_strong_claims(tmp_path: Path) -> None:
    _touch_assets(tmp_path)

    portfolio = build_product_idea_portfolio(tmp_path)

    for idea in portfolio["ideas"]:
        assert idea["paid_offer"]
        assert idea["first_mvp"]
        assert idea["implementation_status"] == "repo_scaffold_ready"
        assert idea["claim_gate"]["local_product_scaffold_claim_allowed"] is True
        for claim_id in STRONG_CLAIMS:
            assert claim_id in idea["claim_gate"]["blocked_claim_ids"]
        assert idea["claim_gate"]["production_readiness_claim_allowed"] is False
        assert idea["claim_gate"]["customer_traffic_claim_allowed"] is False
        assert idea["claim_gate"]["settlement_finality_claim_allowed"] is False


def test_each_product_idea_has_demo_scenario(tmp_path: Path) -> None:
    _touch_assets(tmp_path)

    portfolio = build_product_idea_portfolio(tmp_path)

    for idea in portfolio["ideas"]:
        scenario = idea["demo_scenario"]
        steps = scenario["steps"]
        step_action_ids = {step["desktop_action_id"] for step in steps}
        assert scenario["scenario_id"] == f"{idea['idea_id']}.demo.v1"
        assert scenario["operator_goal"] == idea["first_mvp"]
        assert len(steps) >= 3
        assert steps[0]["step_id"] == "open_product_card"
        assert steps[-1]["step_id"] == "check_claim_gate"
        assert "product.refresh_ideas" in step_action_ids
        assert set(idea["desktop_action_ids"]).issubset(step_action_ids)
        assert scenario["acceptance_signal"]


def test_missing_repo_asset_blocks_idea_scaffold(tmp_path: Path) -> None:
    _touch_assets(tmp_path)
    missing_path = tmp_path / PRODUCT_IDEAS[0].existing_repo_paths[0]
    missing_path.unlink()

    idea = get_product_idea("agent_black_box", tmp_path)

    assert idea is not None
    assert idea["implementation_status"] == "repo_scaffold_blocked"
    assert idea["claim_gate"]["local_product_scaffold_claim_allowed"] is False
    assert "mapped_repo_assets_missing" in idea["claim_gate"]["blockers"]


def test_unknown_product_idea_returns_none() -> None:
    assert get_product_idea("not-a-product") is None
