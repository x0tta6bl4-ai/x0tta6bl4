"""Productized idea portfolio for x0tta6bl4.

This module turns the ten rough product ideas into a small, testable product
surface.  It does not claim the products are finished; it records what can be
packaged from the current repository and keeps strong claims blocked.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA = "x0tta6bl4.product_ideas.portfolio.v1"
IDEA_SCHEMA = "x0tta6bl4.product_ideas.idea.v1"
CLAIM_GATE_SCHEMA = "x0tta6bl4.product_ideas.claim_gate.v1"
CLAIM_BOUNDARY = (
    "Product idea portfolio only. It proves that a product surface is mapped to "
    "repo assets and a sellable MVP shape. It does not prove production "
    "readiness, live customer traffic, external DPI bypass, settlement finality, "
    "production SLOs, or field deployment."
)
STRONG_CLAIMS = (
    "production_readiness",
    "dataplane_delivery",
    "traffic_delivery",
    "customer_traffic",
    "dpi_bypass",
    "settlement_finality",
    "field_deployment",
)

ACTION_DEMO_COPY = {
    "product.refresh_ideas": "Refresh the product portfolio and show the proof boundary.",
    "readiness.open_gate": "Run the readiness gate and show PASS, FAIL, WARN, and blocked claims.",
    "identity.read_event_traces": "Read local service event traces without exposing secrets.",
    "identity.refresh_status": "Refresh service identity status and trust-boundary fields.",
    "mesh.refresh_runtime": "Refresh local mesh runtime status and degraded-mode signals.",
    "vpn.refresh_readiness": "Refresh VPN readiness and show what is locally observable.",
    "vpn.refresh_status": "Refresh VPN status and show transport health fields.",
    "provisioning.generate_setup": "Generate a local node setup package.",
    "node.approve": "Approve a pending pilot node.",
    "node.revoke": "Revoke a pilot node.",
    "node.readiness": "Read node readiness and local telemetry.",
    "node.heal": "Run or prepare a safe node-heal action with evidence boundaries.",
    "agent_health.run": "Run the health bot and show dry-run or safe-actuator evidence.",
}


@dataclass(frozen=True)
class ProductIdea:
    idea_id: str
    title: str
    simple_pitch: str
    buyer: str
    paid_offer: str
    first_mvp: str
    existing_repo_paths: tuple[str, ...]
    action_ids: tuple[str, ...]
    proof_focus: tuple[str, ...]
    blocked_claims: tuple[str, ...] = STRONG_CLAIMS


PRODUCT_IDEAS: tuple[ProductIdea, ...] = (
    ProductIdea(
        idea_id="agent_black_box",
        title="AI agent black box",
        simple_pitch="Audit log for autonomous agent actions.",
        buyer="Security teams, CTOs, regulated engineering teams.",
        paid_offer="Monthly audit dashboard for AI actions and proof boundaries.",
        first_mvp="Show action history, evidence ids, and what each action cannot prove.",
        existing_repo_paths=(
            "src/integration/spine.py",
            "src/services/service_event_trace.py",
            "src/api/cross_plane_claim_gate.py",
        ),
        action_ids=("readiness.open_gate", "identity.read_event_traces"),
        proof_focus=("action_evidence", "claim_boundary", "redaction"),
    ),
    ProductIdea(
        idea_id="sovereign_office",
        title="Sovereign office without cloud",
        simple_pitch="Local control plane, local access, local status.",
        buyer="Small teams that cannot depend on SaaS control planes.",
        paid_offer="Self-hosted team package with support.",
        first_mvp="Desktop control plane plus agent onboarding and local status views.",
        existing_repo_paths=(
            "src/core/app_desktop.py",
            "x0tta6bl4-app/src/App.tsx",
            "agent/scripts/install.sh",
        ),
        action_ids=("mesh.refresh_runtime", "provisioning.generate_setup"),
        proof_focus=("local_control_plane", "agent_onboarding", "offline_status"),
    ),
    ProductIdea(
        idea_id="crisis_internet_kit",
        title="Crisis internet in a box",
        simple_pitch="Portable kit for local mesh status and operator handoff.",
        buyer="Field teams, emergency operators, expeditions.",
        paid_offer="Hardware/software kit plus setup support.",
        first_mvp="One local server, two agents, one status screen, one runbook.",
        existing_repo_paths=(
            "deploy/on-prem/docker-compose.yml",
            "agent/scripts/install.sh",
            "docs/05-operations/REAL_READINESS_GATE.md",
        ),
        action_ids=("mesh.refresh_runtime", "vpn.refresh_readiness"),
        proof_focus=("offline_runbook", "local_mesh_observation", "operator_handoff"),
    ),
    ProductIdea(
        idea_id="devops_truth_detector",
        title="DevOps truth detector",
        simple_pitch="A screen that says what is proved and what is not.",
        buyer="CTOs, auditors, platform teams.",
        paid_offer="Readiness audit report and recurring evidence review.",
        first_mvp="Run readiness gates and show PASS, FAIL, WARN, and blocked claims.",
        existing_repo_paths=(
            "scripts/ops/check_real_readiness.py",
            "scripts/ops/check_commercial_mesh_platform_readiness.py",
            "scripts/ops/run_cross_plane_proof_gate.py",
        ),
        action_ids=("readiness.open_gate",),
        proof_focus=("readiness_gate", "blocked_claims", "audit_report"),
    ),
    ProductIdea(
        idea_id="remote_infra_caretaker",
        title="Remote infrastructure caretaker",
        simple_pitch="Local agent watches a node and reports safe fixes.",
        buyer="Small datacenters, remote sites, VPS operators.",
        paid_offer="Per-node monitoring and assisted recovery.",
        first_mvp="Heartbeat, node readiness, heal handoff, and post-action evidence.",
        existing_repo_paths=(
            "agent/main.go",
            "src/api/maas/endpoints/nodes.py",
            "src/self_healing/mape_k/manager.py",
        ),
        action_ids=("node.readiness", "node.heal", "agent_health.run"),
        proof_focus=("heartbeat", "safe_heal", "post_action_check"),
    ),
    ProductIdea(
        idea_id="abandoned_places_mesh",
        title="Mesh for hard places",
        simple_pitch="Local network view for places with weak internet.",
        buyer="Mines, ports, farms, construction, remote bases.",
        paid_offer="Site pilot plus monthly support.",
        first_mvp="Local mesh status, peer list, and degraded-mode signals.",
        existing_repo_paths=(
            "src/api/maas/endpoints/batman.py",
            "src/network/yggdrasil_client.py",
            "src/core/app_desktop.py",
        ),
        action_ids=("mesh.refresh_runtime", "vpn.refresh_status"),
        proof_focus=("peer_observation", "degraded_mode", "local_metrics"),
    ),
    ProductIdea(
        idea_id="paranoid_self_hosted_mesh",
        title="Paranoid self-hosted mesh",
        simple_pitch="A self-hosted secure access product with no SaaS control plane.",
        buyer="Privacy-heavy teams and isolated operators.",
        paid_offer="Self-hosted secure mesh access subscription.",
        first_mvp="Local controller, agent install, node approval, and local access checks.",
        existing_repo_paths=(
            "src/api/maas/endpoints/provisioning.py",
            "src/api/maas/endpoints/nodes.py",
            "agent/scripts/x0t-agent.service",
        ),
        action_ids=("provisioning.generate_setup", "node.approve", "node.revoke"),
        proof_focus=("local_controller", "node_approval", "key_boundary"),
    ),
    ProductIdea(
        idea_id="node_trust_passport",
        title="Node trust passport",
        simple_pitch="A readable card for what each node is trusted to do.",
        buyer="Security, compliance, infra owners.",
        paid_offer="Per-node trust inventory and compliance export.",
        first_mvp="Node identity, runtime credential status, claim gate, and evidence ids.",
        existing_repo_paths=(
            "src/api/maas/endpoints/nodes.py",
            "src/api/service_identity_status.py",
            "src/services/service_identity_registry.py",
        ),
        action_ids=("identity.refresh_status", "node.readiness"),
        proof_focus=("node_identity", "runtime_credential", "trust_boundary"),
    ),
    ProductIdea(
        idea_id="autonomous_network_repair",
        title="Autonomous network repair",
        simple_pitch="Safe self-healing that proves only what it checked.",
        buyer="Teams with expensive downtime.",
        paid_offer="Per-site recovery automation and support.",
        first_mvp="Detect issue, propose action, run safe actuator, verify local result.",
        existing_repo_paths=(
            "src/self_healing/mape_k/manager.py",
            "src/mesh/recovery_orchestrator.py",
            "scripts/ops/verify_maas_heal_api_post_action_dataplane_probe.py",
        ),
        action_ids=("node.heal", "agent_health.run"),
        proof_focus=("safe_actuator", "cooldown", "post_action_revalidation"),
    ),
    ProductIdea(
        idea_id="industrial_edge_commander",
        title="Industrial edge AI commander",
        simple_pitch="One operator screen for edge nodes, actions, and proof.",
        buyer="Factories, logistics, energy, industrial labs.",
        paid_offer="Pilot dashboard for industrial edge operators.",
        first_mvp="Action catalog, live snapshot, readiness gates, and operator controls.",
        existing_repo_paths=(
            "src/core/app_desktop.py",
            "x0tta6bl4-app/src/App.tsx",
            "src/core/app.py",
        ),
        action_ids=("mesh.refresh_runtime", "readiness.open_gate", "node.heal"),
        proof_focus=("operator_screen", "action_catalog", "human_confirmation"),
    ),
)


def _path_status(root: Path, paths: tuple[str, ...]) -> list[dict[str, Any]]:
    return [
        {
            "path": path,
            "exists": (root / path).exists(),
        }
        for path in paths
    ]


def _claim_gate(idea: ProductIdea, *, scaffold_ready: bool) -> dict[str, Any]:
    blockers = []
    if not scaffold_ready:
        blockers.append("mapped_repo_assets_missing")
    blockers.extend(f"{claim}_requires_dedicated_evidence" for claim in idea.blocked_claims)
    return {
        "schema": CLAIM_GATE_SCHEMA,
        "surface": f"product_ideas.{idea.idea_id}",
        "local_product_scaffold_claim_allowed": scaffold_ready,
        "sellable_mvp_shape_claim_allowed": scaffold_ready,
        "production_readiness_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "field_deployment_claim_allowed": False,
        "blocked_claim_ids": list(idea.blocked_claims),
        "blockers": blockers,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _demo_scenario(idea: ProductIdea) -> dict[str, Any]:
    steps = [
        {
            "step_id": "open_product_card",
            "operator_action": f"Open PRODUCT tab and select {idea.title}.",
            "proof": "The local app shows buyer, paid offer, first MVP, repo assets, and blocked claims.",
            "desktop_action_id": "product.refresh_ideas",
        }
    ]
    for action_id in idea.action_ids:
        steps.append(
            {
                "step_id": action_id.replace(".", "_"),
                "operator_action": ACTION_DEMO_COPY.get(
                    action_id,
                    f"Run {action_id} from the local action catalog.",
                ),
                "proof": f"Evidence focus: {', '.join(idea.proof_focus)}.",
                "desktop_action_id": action_id,
            }
        )
    steps.append(
        {
            "step_id": "check_claim_gate",
            "operator_action": "Read the claim gate before saying the product is production ready.",
            "proof": "Production, customer-traffic, settlement, DPI, and field-deployment claims stay blocked.",
            "desktop_action_id": "product.refresh_ideas",
        }
    )
    return {
        "scenario_id": f"{idea.idea_id}.demo.v1",
        "operator_goal": idea.first_mvp,
        "steps": steps,
        "acceptance_signal": (
            "A buyer can understand the paid offer, see the local evidence, "
            "and see which claims are not proven yet."
        ),
    }


def idea_to_dict(idea: ProductIdea, *, root: Path | None = None) -> dict[str, Any]:
    root = root or Path(".")
    assets = _path_status(root, idea.existing_repo_paths)
    scaffold_ready = all(item["exists"] for item in assets)
    return {
        "schema": IDEA_SCHEMA,
        "idea_id": idea.idea_id,
        "title": idea.title,
        "simple_pitch": idea.simple_pitch,
        "buyer": idea.buyer,
        "paid_offer": idea.paid_offer,
        "first_mvp": idea.first_mvp,
        "implementation_status": (
            "repo_scaffold_ready" if scaffold_ready else "repo_scaffold_blocked"
        ),
        "existing_repo_assets": assets,
        "desktop_action_ids": list(idea.action_ids),
        "proof_focus": list(idea.proof_focus),
        "demo_scenario": _demo_scenario(idea),
        "claim_gate": _claim_gate(idea, scaffold_ready=scaffold_ready),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def build_product_idea_portfolio(root: Path | str = ".") -> dict[str, Any]:
    root_path = Path(root)
    ideas = [idea_to_dict(idea, root=root_path) for idea in PRODUCT_IDEAS]
    ready_count = sum(1 for idea in ideas if idea["implementation_status"] == "repo_scaffold_ready")
    return {
        "schema": SCHEMA,
        "status": "portfolio_ready" if ready_count == len(ideas) else "portfolio_blocked",
        "ideas_total": len(ideas),
        "repo_scaffold_ready": ready_count,
        "repo_scaffold_blocked": len(ideas) - ready_count,
        "monetization_rule": (
            "Sell one narrow MVP first; keep the other ideas as packaged upsells."
        ),
        "first_offer": "Self-hosted secure mesh access with proof-based status.",
        "ideas": ideas,
        "claim_boundary": CLAIM_BOUNDARY,
        "claim_gate": {
            "schema": CLAIM_GATE_SCHEMA,
            "surface": "product_ideas.portfolio",
            "all_ideas_scaffolded": ready_count == len(ideas),
            "local_product_portfolio_claim_allowed": ready_count == len(ideas),
            "production_readiness_claim_allowed": False,
            "customer_traffic_claim_allowed": False,
            "settlement_finality_claim_allowed": False,
            "blocked_claim_ids": list(STRONG_CLAIMS),
            "claim_boundary": CLAIM_BOUNDARY,
        },
    }


def get_product_idea(idea_id: str, root: Path | str = ".") -> dict[str, Any] | None:
    normalized = idea_id.strip()
    for idea in PRODUCT_IDEAS:
        if idea.idea_id == normalized:
            return idea_to_dict(idea, root=Path(root))
    return None
