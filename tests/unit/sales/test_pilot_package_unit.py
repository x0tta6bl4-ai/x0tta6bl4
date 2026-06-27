from __future__ import annotations

from pathlib import Path

from src.sales.pilot_package import PRIMARY_IDEA_ID, build_pilot_package
from src.sales.product_ideas import PRODUCT_IDEAS, STRONG_CLAIMS


def _write_primary_assets(root: Path) -> None:
    primary = next(idea for idea in PRODUCT_IDEAS if idea.idea_id == PRIMARY_IDEA_ID)
    for relative_path in primary.existing_repo_paths:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("asset\n", encoding="utf-8")


def test_first_paid_pilot_package_is_claim_bounded(tmp_path: Path) -> None:
    _write_primary_assets(tmp_path)

    package = build_pilot_package(tmp_path)

    assert package["schema"] == "x0tta6bl4.product_ideas.pilot_package.v1"
    assert package["status"] == "pilot_package_ready"
    assert package["target_idea_id"] == "paranoid_self_hosted_mesh"
    assert package["offer_name"] == "Self-hosted secure mesh access pilot"
    assert len(package["paid_scope"]) >= 5
    assert {step["desktop_action_id"] for step in package["demo_steps"]} >= {
        "product.refresh_ideas",
        "provisioning.generate_setup",
        "node.approve",
        "node.readiness",
        "node.revoke",
    }
    claim_gate = package["claim_gate"]
    assert claim_gate["pilot_package_claim_allowed"] is True
    assert claim_gate["production_readiness_claim_allowed"] is False
    assert claim_gate["customer_traffic_claim_allowed"] is False
    assert claim_gate["settlement_finality_claim_allowed"] is False
    assert set(claim_gate["blocked_claim_ids"]) == set(STRONG_CLAIMS)


def test_first_paid_pilot_blocks_when_primary_assets_are_missing(tmp_path: Path) -> None:
    package = build_pilot_package(tmp_path)

    assert package["status"] == "pilot_package_blocked"
    assert package["claim_gate"]["pilot_package_claim_allowed"] is False
    assert "primary_offer_repo_assets_missing" in package["claim_gate"]["blockers"]
