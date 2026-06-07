#!/usr/bin/env python3
"""Static commercial mesh-platform readiness gate.

This gate checks whether the current repository has a coherent product wiring
for the stated x0tta6bl4 target: app/API control plane, device agents,
marketplace, billing, and explicit evidence boundaries. It is intentionally
read-only and static. Passing this gate does not prove live production traffic.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence


SCHEMA = "x0tta6bl4.commercial_mesh_platform_readiness.v1"
DECISION_READY = "COMMERCIAL_MESH_PLATFORM_STATIC_CONTRACT_READY"
DECISION_BLOCKED = "COMMERCIAL_MESH_PLATFORM_STATIC_CONTRACT_BLOCKED"
DEFAULT_OUTPUT_JSON = ".tmp/validation-shards/commercial-mesh-platform-readiness-current.json"
DEFAULT_OUTPUT_MD = ".tmp/validation-shards/commercial-mesh-platform-readiness-current.md"

CLAIM_BOUNDARY = (
    "This verifier proves static repository wiring for a commercial "
    "Mesh-as-a-Service platform only. It does not start services, execute an "
    "agent install, create marketplace transactions, charge customers, prove "
    "dataplane delivery, prove customer traffic, prove settlement finality, "
    "prove external DPI bypass, prove production SLOs, or prove production "
    "readiness."
)

STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"


@dataclass(frozen=True)
class FileExpectation:
    path: str
    markers: tuple[str, ...]


@dataclass(frozen=True)
class RequirementSpec:
    requirement_id: str
    details: str
    files: tuple[FileExpectation, ...]


@dataclass(frozen=True)
class RequirementCheck:
    requirement_id: str
    status: str
    details: str
    evidence: str
    missing: tuple[str, ...]


REQUIREMENT_SPECS: tuple[RequirementSpec, ...] = (
    RequirementSpec(
        requirement_id="commercial_target_contract",
        details=(
            "Canonical plans define the product target as Mesh-as-a-Service "
            "with paid-pilot/revenue readiness, while keeping production go-live gated."
        ),
        files=(
            FileExpectation(
                "plans/MAAS_PIVOT_EXECUTION_TODO.md",
                (
                    "Mesh-as-a-Service",
                    "Control Plane + Headless Data Plane Agent",
                    "$10K MRR pilots",
                    "production go-live is gated",
                ),
            ),
            FileExpectation(
                "ROADMAP.md",
                (
                    "Pre-Production",
                    "Revenue readiness",
                    "Convert to paid pilots",
                    "MRR stabilization window",
                ),
            ),
        ),
    ),
    RequirementSpec(
        requirement_id="app_api_control_plane_contract",
        details=(
            "Native/web app and Core APIs expose the shared control-plane surfaces "
            "needed to operate mesh, marketplace, billing, provisioning, and actions."
        ),
        files=(
            FileExpectation(
                "x0tta6bl4-app/src/App.tsx",
                (
                    "/api/v1/platform/live-snapshot",
                    "/api/v1/actions/execute",
                    "/api/v1/maas/marketplace/list",
                    "/api/v1/maas/marketplace/rent/",
                    "/api/v1/maas/billing/billing/pay",
                    "/api/v1/maas/provisioning/generate-setup",
                    "/nodes/${encodeURIComponent(meshId)}/nodes/${encodeURIComponent(nodeId)}/approve",
                    "/nodes/${encodeURIComponent(meshId)}/nodes/${encodeURIComponent(nodeId)}/revoke",
                    "/nodes/${encodeURIComponent(meshId)}/nodes/${encodeURIComponent(nodeId)}/heal",
                ),
            ),
            FileExpectation(
                "src/core/app_desktop.py",
                (
                    "ACTION_CATALOG",
                    "@app.get(\"/api/v1/platform/live-snapshot\")",
                    "@app.get(\"/api/v1/actions\")",
                    "@app.post(\"/api/v1/actions/execute\")",
                    "LOCAL_OBSERVATION_CLAIM_BOUNDARY",
                ),
            ),
            FileExpectation(
                "src/core/app.py",
                (
                    "/api/v1/platform/live-snapshot",
                    "cross_plane_claim_gate",
                    "_fast_fail_closed_cross_plane_claim_gate",
                ),
            ),
            FileExpectation(
                "x0tta6bl4-app/PLATFORM_BUILDS.md",
                (
                    "full-core-first",
                    "GET /api/v1/platform/live-snapshot",
                    "POST /api/v1/actions/execute",
                    "Payment, signing, proposal creation",
                ),
            ),
        ),
    ),
    RequirementSpec(
        requirement_id="device_agent_onboarding_contract",
        details=(
            "A headless data-plane agent can be installed on devices and is wired "
            "to MaaS node registration, heartbeat, runtime credential, and node actions."
        ),
        files=(
            FileExpectation(
                "agent/main.go",
                (
                    "Headless Mesh Agent",
                    "registerAndHeartbeat",
                    "api.NewClient",
                    "x0t-agent",
                    "heartbeat",
                ),
            ),
            FileExpectation(
                "agent/internal/api/client.go",
                (
                    "Register registers this agent with the Control Plane",
                    "/api/v1/maas/%s/nodes/register",
                    "/api/v1/maas/%s/nodes/%s/heartbeat",
                    "/api/v1/maas/%s/nodes/%s/runtime-credential/rotate",
                    "/api/v1/maas/%s/nodes/%s/runtime-identity/bind-jwt-svid",
                ),
            ),
            FileExpectation(
                "agent/scripts/install.sh",
                (
                    "x0tta6bl4 Mesh Agent Installer",
                    "--token",
                    'cp "agent/bin/x0t-agent"',
                    "ExecStart=/usr/local/bin/x0t-agent",
                    "systemctl enable",
                    "systemctl restart",
                ),
            ),
            FileExpectation(
                "agent/scripts/x0t-agent.service",
                (
                    "Description=x0tta6bl4 Mesh Agent (Data Plane)",
                    "ExecStart=/usr/local/bin/x0t-agent",
                    "NoNewPrivileges=true",
                    "ReadWritePaths=/var/lib/x0t /etc/x0t",
                ),
            ),
            FileExpectation(
                "src/api/maas/endpoints/nodes.py",
                (
                    "@router.post(\"/{mesh_id}/nodes/register\"",
                    "@router.post(\"/{mesh_id}/nodes/{node_id}/approve\")",
                    "@router.post(\"/{mesh_id}/nodes/{node_id}/revoke\")",
                    "/{mesh_id}/nodes/{node_id}/runtime-credential/rotate",
                    "/{mesh_id}/nodes/{node_id}/heartbeat",
                    "@router.post(\"/{mesh_id}/nodes/{node_id}/heal\")",
                    "@router.get(\"/{mesh_id}/nodes/{node_id}/readiness\")",
                ),
            ),
            FileExpectation(
                "src/api/maas/endpoints/provisioning.py",
                (
                    "@router.post(\"/generate-setup\")",
                    "ProvisionResponse",
                    "install_command",
                    "provisioning_setup_claim_gate",
                    "PROVISIONING_CLAIM_BOUNDARY",
                ),
            ),
        ),
    ),
    RequirementSpec(
        requirement_id="commercial_loop_contract",
        details=(
            "Marketplace and billing surfaces are wired for list/search/rent/escrow, "
            "plan/usage/payment, and rental lifecycle review."
        ),
        files=(
            FileExpectation(
                "src/api/maas/endpoints/marketplace.py",
                (
                    "@router.post(\"/list\"",
                    "@router.get(\"/search\"",
                    "@router.get(\"/rental/{listing_id}/lifecycle\")",
                    "@router.post(\"/rent/{listing_id}\")",
                    "@router.post(\"/escrow/{listing_id}/release\")",
                    "@router.post(\"/escrow/{listing_id}/refund\")",
                    "publish_marketplace_escrow_event",
                    "Marketplace API escrow evidence records local authenticated request",
                ),
            ),
            FileExpectation(
                "src/api/maas/endpoints/billing.py",
                (
                    "_modular_billing_claim_gate",
                    "payment_provider_settlement_claim_allowed",
                    "dataplane_delivery_claim_allowed",
                    "customer_traffic_claim_allowed",
                    "production_readiness_claim_allowed",
                    "billing/pay",
                    "billing/plans",
                    "billing/estimate",
                    "billing/usage",
                ),
            ),
            FileExpectation(
                "x0tta6bl4-app/src/App.tsx",
                (
                    "marketplace.rent_listing",
                    "marketplace.release_escrow",
                    "marketplace.refund_escrow",
                    "billing.create_payment_intent",
                    "refreshRentalLifecycle",
                ),
            ),
        ),
    ),
    RequirementSpec(
        requirement_id="product_idea_portfolio_contract",
        details=(
            "The ten x0tta6bl4 product ideas are represented as a static, "
            "claim-bounded portfolio, exposed through the desktop control plane, "
            "and exported as sales-ready artifacts."
        ),
        files=(
            FileExpectation(
                "src/sales/product_ideas.py",
                (
                    "PRODUCT_IDEAS",
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
                    "demo_scenario",
                    "open_product_card",
                    "check_claim_gate",
                    "production_readiness_claim_allowed",
                    "customer_traffic_claim_allowed",
                    "settlement_finality_claim_allowed",
                ),
            ),
            FileExpectation(
                "src/core/app_desktop.py",
                (
                    "build_product_idea_portfolio",
                    "build_pilot_package",
                    "product.refresh_ideas",
                    "product.open_pilot_package",
                    "@app.get(\"/api/v1/product/ideas\")",
                    "@app.get(\"/api/v1/product/ideas/{idea_id}\")",
                    "@app.get(\"/api/v1/product/pilot-package\")",
                ),
            ),
            FileExpectation(
                "src/sales/pilot_package.py",
                (
                    "PRIMARY_IDEA_ID",
                    "Self-hosted secure mesh access pilot",
                    "provisioning.generate_setup",
                    "node.approve",
                    "node.revoke",
                    "production_readiness_claim_allowed",
                ),
            ),
            FileExpectation(
                "tests/unit/sales/test_product_ideas_unit.py",
                (
                    "test_product_ideas_cover_all_ten_requested_concepts",
                    "test_each_product_idea_has_paid_offer_and_blocks_strong_claims",
                    "test_each_product_idea_has_demo_scenario",
                    "ideas_total",
                ),
            ),
            FileExpectation(
                "tests/unit/sales/test_pilot_package_unit.py",
                (
                    "test_first_paid_pilot_package_is_claim_bounded",
                    "test_first_paid_pilot_blocks_when_primary_assets_are_missing",
                    "Self-hosted secure mesh access pilot",
                ),
            ),
            FileExpectation(
                "tests/unit/core/test_app_desktop_live_snapshot_unit.py",
                (
                    "test_product_ideas_api_exposes_ten_scaffolded_products",
                    "test_product_pilot_package_api_exposes_first_paid_offer",
                    "/api/v1/product/ideas",
                    "/api/v1/product/pilot-package",
                ),
            ),
            FileExpectation(
                "x0tta6bl4-app/src/App.tsx",
                (
                    "ProductIdeasPanel",
                    "productPilotPackage",
                    "demo: {String(demoSteps.length)} steps",
                    "product.open_pilot_package",
                    "/api/v1/product/pilot-package",
                ),
            ),
            FileExpectation(
                "scripts/ops/export_product_idea_portfolio.py",
                (
                    "DEFAULT_OUTPUT_MD",
                    "build_pilot_package",
                    "build_product_idea_portfolio",
                    "render_markdown",
                    "write_export",
                ),
            ),
            FileExpectation(
                "scripts/ops/build_productization_snapshot.py",
                (
                    "DEFAULT_OUTPUT_JSON",
                    "build_export",
                    "build_report",
                    "render_markdown",
                    "production_readiness_claim_allowed",
                ),
            ),
            FileExpectation(
                "tests/unit/scripts/test_export_product_idea_portfolio.py",
                (
                    "test_product_idea_export_builds_markdown_and_json",
                    "test_product_idea_export_cli_writes_artifacts",
                    "Production readiness claim allowed: False",
                ),
            ),
            FileExpectation(
                "tests/unit/scripts/test_build_productization_snapshot.py",
                (
                    "test_productization_snapshot_combines_product_and_readiness",
                    "test_productization_snapshot_cli_writes_outputs",
                    "Self-hosted secure mesh access pilot",
                ),
            ),
            FileExpectation(
                "docs/commercial/PRODUCT_IDEA_PORTFOLIO.md",
                (
                    "x0tta6bl4 Product Idea Portfolio",
                    "First Paid Pilot",
                    "Self-hosted secure mesh access pilot",
                    "Demo scenario: agent_black_box.demo.v1",
                    "check_claim_gate",
                    "AI agent black box",
                    "Industrial edge AI commander",
                    "Claim Boundary",
                ),
            ),
        ),
    ),
    RequirementSpec(
        requirement_id="wallet_payment_intake_contract",
        details=(
            "The first paid pilot has a wallet payment intake package with a "
            "target EVM wallet, pricing ladder, buyer/operator steps, and a "
            "fail-closed funds-received claim boundary."
        ),
        files=(
            FileExpectation(
                "src/sales/wallet_payment_intake.py",
                (
                    "TARGET_WALLET_ADDRESS",
                    "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099",
                    "pricing_ladder",
                    "network_policy",
                    "funds_received_claim_allowed",
                ),
            ),
            FileExpectation(
                "src/core/app_desktop.py",
                (
                    "build_wallet_payment_intake",
                    "product.open_payment_intake",
                    "@app.get(\"/api/v1/product/payment-intake\")",
                ),
            ),
            FileExpectation(
                "x0tta6bl4-app/src/App.tsx",
                (
                    "productPaymentIntake",
                    "/api/v1/product/payment-intake",
                    "OPEN PAYMENT INTAKE",
                    "Funds Claim",
                ),
            ),
            FileExpectation(
                "scripts/ops/export_wallet_payment_intake.py",
                (
                    "DEFAULT_OUTPUT_MD",
                    "build_wallet_payment_intake",
                    "Funds received claim allowed",
                    "Settlement finality claim allowed",
                ),
            ),
            FileExpectation(
                "scripts/ops/build_productization_snapshot.py",
                (
                    "build_payment_export",
                    "payment_intake_status",
                    "payment_wallet",
                    "funds_received_claim_allowed",
                ),
            ),
            FileExpectation(
                "tests/unit/sales/test_wallet_payment_intake_unit.py",
                (
                    "test_wallet_payment_intake_is_ready_for_target_wallet",
                    "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099",
                    "funds_received_claim_allowed",
                ),
            ),
            FileExpectation(
                "tests/unit/scripts/test_export_wallet_payment_intake.py",
                (
                    "test_wallet_payment_intake_export_builds_markdown",
                    "test_wallet_payment_intake_export_cli_writes_artifacts",
                    "Payment reference: X0T-PILOT-6017E099",
                ),
            ),
            FileExpectation(
                "tests/unit/core/test_app_desktop_live_snapshot_unit.py",
                (
                    "test_product_payment_intake_api_exposes_target_wallet_without_funds_claim",
                    "/api/v1/product/payment-intake",
                    "funds_received_claim_allowed",
                ),
            ),
            FileExpectation(
                "docs/commercial/PAYMENT_INTAKE.md",
                (
                    "x0tta6bl4 Payment Intake",
                    "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099",
                    "Payment reference: X0T-PILOT-6017E099",
                    "Funds received claim allowed: False",
                ),
            ),
        ),
    ),
    RequirementSpec(
        requirement_id="paid_task_automation_pipeline_contract",
        details=(
            "The monetization goal is represented as a legal paid-task automation "
            "pipeline with source catalog, task types, human gates, wallet routing, "
            "and a fail-closed funds-received claim boundary."
        ),
        files=(
            FileExpectation(
                "src/sales/paid_task_pipeline.py",
                (
                    "Find legitimate paid online tasks",
                    "Algora",
                    "collect_paid_task_listings.py",
                    "score_paid_task_listings.py",
                    "GH Bounty",
                    "Superteam Earn",
                    "Dework",
                    "DoraHacks",
                    "funds_received_claim_allowed",
                    "No CAPTCHA bypass",
                ),
            ),
            FileExpectation(
                "scripts/ops/build_paid_task_automation_plan.py",
                (
                    "DEFAULT_OUTPUT_MD",
                    "build_paid_task_pipeline",
                    "Funds received claim allowed",
                    "PAID_TASK_AUTOMATION_PLAN.md",
                ),
            ),
            FileExpectation(
                "src/sales/paid_task_collectors.py",
                (
                    "collect_github_algora_bounty_listings",
                    "GITHUB_ALGORA_BOUNTY_QUERY",
                    "github_issue_to_paid_task_listing",
                    "extract_usd_bounty_amount",
                    "funds_received_claim_allowed",
                ),
            ),
            FileExpectation(
                "scripts/ops/collect_paid_task_listings.py",
                (
                    "DEFAULT_OUTPUT_JSON",
                    "collect_github_algora_bounty_listings",
                    "paid-task-listings-current.json",
                    "funds_received_claim_allowed",
                ),
            ),
            FileExpectation(
                "src/sales/paid_task_selector.py",
                (
                    "score_paid_task_listings",
                    "FIT_KEYWORDS",
                    "HARD_REJECT_KEYWORDS",
                    "payout_usd_estimate",
                    "hard_reject",
                ),
            ),
            FileExpectation(
                "scripts/ops/score_paid_task_listings.py",
                (
                    "DEFAULT_OUTPUT_JSON",
                    "score_paid_task_listings",
                    "paid-task-selection",
                    "Funds received claim allowed",
                ),
            ),
            FileExpectation(
                "scripts/ops/build_productization_snapshot.py",
                (
                    "build_paid_task_plan",
                    "paid_task_pipeline_status",
                    "paid_task_sources_total",
                ),
            ),
            FileExpectation(
                "tests/unit/sales/test_paid_task_pipeline_unit.py",
                (
                    "test_paid_task_pipeline_has_goal_sources_and_claim_gate",
                    "ghbounty",
                    "funds_received_claim_allowed",
                ),
            ),
            FileExpectation(
                "tests/unit/sales/test_paid_task_collectors_unit.py",
                (
                    "test_collect_github_algora_bounty_listings_from_fixture",
                    "test_github_issue_to_paid_task_listing_normalises_algora_bounty",
                    "payout_usd",
                ),
            ),
            FileExpectation(
                "tests/unit/sales/test_paid_task_selector_unit.py",
                (
                    "test_paid_task_selector_picks_engineering_bounty_first",
                    "test_paid_task_selector_rejects_private_key_or_spam_tasks",
                    "private key",
                ),
            ),
            FileExpectation(
                "tests/unit/scripts/test_build_paid_task_automation_plan.py",
                (
                    "test_paid_task_automation_plan_renders_goal_and_sources",
                    "test_paid_task_automation_plan_cli_writes_artifacts",
                    "GH Bounty",
                ),
            ),
            FileExpectation(
                "tests/unit/scripts/test_collect_paid_task_listings.py",
                (
                    "test_collect_paid_task_listings_cli_writes_fixture_collection",
                    "fixture-json",
                    "collection_ready",
                ),
            ),
            FileExpectation(
                "tests/unit/scripts/test_score_paid_task_listings.py",
                (
                    "test_score_paid_task_listings_cli_writes_artifacts",
                    "Fix Python test failure",
                    "Funds received claim allowed: False",
                ),
            ),
            FileExpectation(
                "docs/commercial/paid_task_listings.example.json",
                (
                    "ghbounty",
                    "Fix Python test failure",
                    "Docs runbook",
                    "private key",
                ),
            ),
            FileExpectation(
                "docs/commercial/PAID_TASK_AUTOMATION_PLAN.md",
                (
                    "x0tta6bl4 Paid Task Automation Plan",
                    "Algora",
                    "collect_paid_task_listings.py",
                    "GH Bounty",
                    "Superteam Earn",
                    "score_paid_task_listings.py",
                    "No CAPTCHA bypass",
                    "Funds received claim allowed: False",
                ),
            ),
        ),
    ),
    RequirementSpec(
        requirement_id="evidence_gate_contract",
        details=(
            "High-risk production, dataplane, customer-traffic, and settlement claims "
            "remain behind fail-closed evidence gates across product surfaces."
        ),
        files=(
            FileExpectation(
                "docs/05-operations/REAL_READINESS_GATE.md",
                (
                    "Cross-plane proof gate exists",
                    "Traffic delivery and customer traffic",
                    "Dirty worktree review is command-gated",
                    "still does not prove real operator-run evidence",
                ),
            ),
            FileExpectation(
                "scripts/ops/run_cross_plane_proof_gate.py",
                (
                    "production_readiness",
                    "dataplane_delivery",
                    "traffic_delivery",
                    "customer_traffic",
                    "settlement_finality",
                ),
            ),
            FileExpectation(
                "scripts/ops/check_real_readiness.py",
                (
                    "REAL_READINESS_READY means local static contracts",
                    "api_readiness_claim_gate_inventory",
                    "run_cross_plane_proof_gate.py",
                    "summarize_dirty_worktree_review.py",
                ),
            ),
            FileExpectation(
                "src/api/maas/endpoints/billing.py",
                (
                    "\"dataplane_delivery_claim_allowed\": False",
                    "\"customer_traffic_claim_allowed\": False",
                    "\"production_readiness_claim_allowed\": False",
                    "requires_cross_plane_proof_for_production_claim",
                ),
            ),
            FileExpectation(
                "src/api/maas/endpoints/provisioning.py",
                (
                    "\"node_dataplane_join_claim_allowed\": False",
                    "\"dataplane_delivery_claim_allowed\": False",
                    "\"customer_traffic_claim_allowed\": False",
                    "\"production_readiness_claim_allowed\": False",
                ),
            ),
            FileExpectation(
                "src/core/app_desktop.py",
                (
                    "\"production_readiness_claim_allowed\": False",
                    "\"dataplane_delivery_claim_allowed\": False",
                    "\"customer_traffic_claim_allowed\": False",
                    "\"settlement_finality_claim_allowed\": False",
                ),
            ),
        ),
    ),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_file(root: Path, relative_path: str) -> tuple[str | None, str | None]:
    path = root / relative_path
    if not path.exists():
        return None, "missing_file"
    try:
        return path.read_text(encoding="utf-8"), None
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace"), None
    except OSError as exc:
        return None, f"read_error:{exc}"


def check_requirement(root: Path, spec: RequirementSpec) -> RequirementCheck:
    missing: list[str] = []
    evidence_parts: list[str] = []
    for expected_file in spec.files:
        body, error = _read_file(root, expected_file.path)
        evidence_parts.append(expected_file.path)
        if error:
            missing.append(f"{expected_file.path}:{error}")
            continue
        assert body is not None
        for marker in expected_file.markers:
            if marker not in body:
                missing.append(f"{expected_file.path}:missing_marker:{marker}")
    status = STATUS_PASS if not missing else STATUS_FAIL
    return RequirementCheck(
        requirement_id=spec.requirement_id,
        status=status,
        details=spec.details,
        evidence=", ".join(evidence_parts),
        missing=tuple(missing),
    )


def build_report(root: Path) -> dict[str, object]:
    root = root.resolve()
    checks = [check_requirement(root, spec) for spec in REQUIREMENT_SPECS]
    failures = [check for check in checks if check.status == STATUS_FAIL]
    ready = not failures
    return {
        "schema": SCHEMA,
        "timestamp_utc": utc_now(),
        "root": root.as_posix(),
        "ready": ready,
        "decision": DECISION_READY if ready else DECISION_BLOCKED,
        "claim_boundary": CLAIM_BOUNDARY,
        "summary": {
            "requirements_total": len(checks),
            "passed": sum(1 for check in checks if check.status == STATUS_PASS),
            "failures": len(failures),
            "static_only": True,
            "starts_services": False,
            "mutates_state": False,
            "charges_customers": False,
            "proves_production_readiness": False,
            "proves_customer_traffic": False,
            "proves_settlement_finality": False,
        },
        "checks": [asdict(check) for check in checks],
        "blockers": [asdict(check) for check in failures],
    }


def render_markdown(report: Mapping[str, object]) -> str:
    summary = report.get("summary", {})
    if not isinstance(summary, Mapping):
        summary = {}
    lines = [
        "# x0tta6bl4 Commercial Mesh Platform Readiness",
        "",
        f"- decision: `{report.get('decision')}`",
        f"- ready: `{report.get('ready')}`",
        f"- timestamp_utc: `{report.get('timestamp_utc')}`",
        f"- requirements_total: `{summary.get('requirements_total')}`",
        f"- passed: `{summary.get('passed')}`",
        f"- failures: `{summary.get('failures')}`",
        "",
        "## Claim Boundary",
        "",
        str(report.get("claim_boundary", "")),
        "",
        "## Checks",
        "",
        "| status | requirement | details | evidence | missing |",
        "|---|---|---|---|---|",
    ]
    checks = report.get("checks", [])
    if isinstance(checks, list):
        for item in checks:
            if not isinstance(item, Mapping):
                continue
            missing = item.get("missing", [])
            missing_text = ", ".join(str(value) for value in missing) if isinstance(missing, list) else ""
            lines.append(
                "| `{status}` | `{requirement}` | {details} | `{evidence}` | {missing} |".format(
                    status=item.get("status"),
                    requirement=item.get("requirement_id"),
                    details=str(item.get("details", "")).replace("|", "\\|"),
                    evidence=str(item.get("evidence", "")).replace("|", "\\|"),
                    missing=missing_text.replace("|", "\\|"),
                )
            )
    return "\n".join(lines) + "\n"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check static commercial Mesh-as-a-Service platform wiring."
    )
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument("--json", action="store_true", help="Print JSON report")
    parser.add_argument(
        "--write-json",
        nargs="?",
        const=DEFAULT_OUTPUT_JSON,
        help="Write JSON report",
    )
    parser.add_argument(
        "--write-md",
        nargs="?",
        const=DEFAULT_OUTPUT_MD,
        help="Write Markdown report",
    )
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Exit 2 when the static commercial platform contract is not ready",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.root).resolve()
    report = build_report(root)
    if args.write_json:
        _write(root / args.write_json, json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n")
    if args.write_md:
        _write(root / args.write_md, render_markdown(report))
    if args.json or not (args.write_json or args.write_md):
        print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
    if args.require_ready and report["ready"] is not True:
        return 2
    return 0 if report["ready"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
