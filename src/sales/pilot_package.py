"""First paid pilot package for the x0tta6bl4 product portfolio."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.sales.product_ideas import CLAIM_BOUNDARY, STRONG_CLAIMS, get_product_idea


SCHEMA = "x0tta6bl4.product_ideas.pilot_package.v1"
CLAIM_GATE_SCHEMA = "x0tta6bl4.product_ideas.pilot_claim_gate.v1"
PRIMARY_IDEA_ID = "paranoid_self_hosted_mesh"
OFFER_NAME = "Self-hosted secure mesh access pilot"


def _assets_ready(idea: dict[str, Any]) -> bool:
    assets = idea.get("existing_repo_assets", [])
    return isinstance(assets, list) and all(bool(item.get("exists")) for item in assets)


def _claim_gate(*, pilot_ready: bool) -> dict[str, Any]:
    blockers = []
    if not pilot_ready:
        blockers.append("primary_offer_repo_assets_missing")
    blockers.extend(f"{claim}_requires_pilot_evidence" for claim in STRONG_CLAIMS)
    return {
        "schema": CLAIM_GATE_SCHEMA,
        "surface": "product_ideas.first_paid_pilot",
        "pilot_package_claim_allowed": pilot_ready,
        "production_readiness_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "field_deployment_claim_allowed": False,
        "blocked_claim_ids": list(STRONG_CLAIMS),
        "blockers": blockers,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def build_pilot_package(root: Path | str = ".") -> dict[str, Any]:
    idea = get_product_idea(PRIMARY_IDEA_ID, root)
    if idea is None:
        raise RuntimeError(f"Primary product idea is missing: {PRIMARY_IDEA_ID}")

    pilot_ready = _assets_ready(idea)
    return {
        "schema": SCHEMA,
        "status": "pilot_package_ready" if pilot_ready else "pilot_package_blocked",
        "offer_name": OFFER_NAME,
        "target_idea_id": PRIMARY_IDEA_ID,
        "plain_offer": (
            "A local controller for secure mesh access: install the controller, "
            "onboard nodes, approve or revoke access, and show proof-bounded status."
        ),
        "buyer": idea["buyer"],
        "paid_scope": [
            "Local controller setup.",
            "Agent install package for a small pilot node set.",
            "Node approval, revoke, and readiness walkthrough.",
            "Operator dashboard walkthrough.",
            "Readiness and claim-boundary report.",
        ],
        "demo_steps": [
            {
                "step_id": "show_product_portfolio",
                "operator_action": "Open PRODUCT tab or GET /api/v1/product/ideas.",
                "proof": "The ten product ideas and blocked claims are visible.",
                "desktop_action_id": "product.refresh_ideas",
            },
            {
                "step_id": "generate_node_setup",
                "operator_action": "Generate setup for one pilot node.",
                "proof": "A local setup package is returned by the control plane.",
                "desktop_action_id": "provisioning.generate_setup",
            },
            {
                "step_id": "approve_node",
                "operator_action": "Approve the pending pilot node.",
                "proof": "The node approval action is accepted by the control plane.",
                "desktop_action_id": "node.approve",
            },
            {
                "step_id": "read_node_status",
                "operator_action": "Read node readiness and local telemetry.",
                "proof": "The operator sees local readiness evidence and missing-proof boundaries.",
                "desktop_action_id": "node.readiness",
            },
            {
                "step_id": "revoke_node",
                "operator_action": "Revoke the pilot node.",
                "proof": "The control plane records the access removal action.",
                "desktop_action_id": "node.revoke",
            },
        ],
        "acceptance_criteria": [
            "Buyer can open the local controller without a SaaS control plane.",
            "Operator can generate a node setup package locally.",
            "Operator can approve and revoke a node from the same screen.",
            "Operator can see which claims are proved and which are blocked.",
            "No production, customer-traffic, or settlement claim is made without evidence.",
        ],
        "upsell_idea_ids": [
            "agent_black_box",
            "node_trust_passport",
            "remote_infra_caretaker",
            "autonomous_network_repair",
            "industrial_edge_commander",
        ],
        "existing_repo_assets": idea["existing_repo_assets"],
        "claim_gate": _claim_gate(pilot_ready=pilot_ready),
        "claim_boundary": CLAIM_BOUNDARY,
    }
