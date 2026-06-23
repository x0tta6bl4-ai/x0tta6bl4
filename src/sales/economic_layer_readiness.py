"""Economic-layer readiness map for x0tta6bl4 monetization claims."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.sales.wallet_payment_intake import TARGET_WALLET_ADDRESS, mask_wallet


SCHEMA = "x0tta6bl4.economic_layer_readiness.v1"
CLAIM_BOUNDARY = (
    "This report verifies local source-code and business-document evidence for "
    "monetization paths. It does not prove accepted tasks, active customers, live "
    "traffic delivery, submitted blockchain transactions, chain finality, bank "
    "settlement, or received funds."
)


@dataclass(frozen=True)
class ExpectedFile:
    path: str
    markers: tuple[str, ...]


@dataclass(frozen=True)
class EconomicPathSpec:
    path_id: str
    name: str
    monetization_mode: str
    current_state: str
    verified_finding: str
    next_evidence_needed: tuple[str, ...]
    expected_files: tuple[ExpectedFile, ...]
    local_claim_key: str


ECONOMIC_LAYER_PATH_SPECS: tuple[EconomicPathSpec, ...] = (
    EconomicPathSpec(
        path_id="share_to_earn_depin",
        name="Share-to-Earn DePIN relay accounting",
        monetization_mode="DePIN: reward accounting for relayed packets and exit-node role.",
        current_state=(
            "Local accounting and simulation are implemented. The service records reward "
            "events but does not claim a payout transaction."
        ),
        verified_finding=(
            "The service writes local reward evidence with submitted_transaction=False, "
            "settlement_recorded=False, and an empty transaction hash."
        ),
        next_evidence_needed=(
            "Real relay-meter evidence tied to customer traffic.",
            "A payout path that calls TokenRewards.reward_relay or another on-chain settlement path.",
            "A confirmed transaction hash to the payout wallet.",
        ),
        expected_files=(
            ExpectedFile(
                "src/services/share_to_earn_service.py",
                (
                    "Record local share-to-earn accounting without claiming payout settlement.",
                    "submitted_transaction=False",
                    "settlement_recorded=False",
                    "transaction_hash=\"\"",
                    "GHOST_ENABLE_ECONOMY_SIMULATION",
                    "OBSERVE_ONLY_NOT_EARNING",
                ),
            ),
        ),
        local_claim_key="local_share_to_earn_accounting_claim_allowed",
    ),
    EconomicPathSpec(
        path_id="token_rewards_chain_path",
        name="TokenRewards ERC20 transfer path",
        monetization_mode="Token payout path: local accounting first, optional Base Sepolia ERC20 transfer.",
        current_state=(
            "A blockchain submission path exists, but it only runs when Web3, RPC, "
            "contract, account, and a private key are configured."
        ),
        verified_finding=(
            "Without blockchain configuration, settlement is local_accounting_only. "
            "With configuration and a returned tx hash, the status becomes blockchain_submitted."
        ),
        next_evidence_needed=(
            "Locally configured RPC URL and token contract address.",
            "Operator private key stored locally, not in chat.",
            "On-chain receipt proving transfer finality.",
        ),
        expected_files=(
            ExpectedFile(
                "src/dao/token_rewards.py",
                (
                    "Supports both local simulation and real Base Sepolia transactions.",
                    "TOKEN_REWARDS_USE_ENV_KEY",
                    "OPERATOR_PRIVATE_KEY",
                    "local_accounting_only",
                    "blockchain_submitted",
                    "send_raw_transaction",
                ),
            ),
        ),
        local_claim_key="chain_submission_code_path_claim_allowed",
    ),
    EconomicPathSpec(
        path_id="marketplace_settlement",
        name="Marketplace escrow settlement worker",
        monetization_mode="Marketplace: release or refund escrow after uptime check.",
        current_state=(
            "The worker can release or refund local escrow records and attempts a token bridge "
            "for X0T escrows, but it does not prove external settlement finality."
        ),
        verified_finding=(
            "The claim gate explicitly blocks traffic delivery, external finality, bank settlement, "
            "revenue recognition, and production-readiness claims."
        ),
        next_evidence_needed=(
            "A real held escrow created by a paying customer.",
            "24-hour uptime evidence linked to the rented node.",
            "External bridge receipt and independent finality verification.",
        ),
        expected_files=(
            ExpectedFile(
                "src/services/marketplace_settlement.py",
                (
                    "SETTLEMENT_UPTIME_THRESHOLD = 0.999",
                    "release_escrow_on_chain",
                    "refund_escrow_on_chain",
                    "\"external_settlement_finality_claim_allowed\": False",
                    "\"revenue_recognition_claim_allowed\": False",
                ),
            ),
        ),
        local_claim_key="local_escrow_lifecycle_claim_allowed",
    ),
    EconomicPathSpec(
        path_id="mesh_ai_router_business",
        name="Distributed AI opportunity draft",
        monetization_mode="DeAI: route inference, federated learning, and AI service work.",
        current_state=(
            "The document describes a business direction. It is not proof of paying users "
            "or live inference revenue."
        ),
        verified_finding=(
            "The document itself says its current gate note is not current production proof."
        ),
        next_evidence_needed=(
            "A concrete inference product offer with price and buyer.",
            "A working request router with metering.",
            "Invoice, escrow, or payout evidence from a real customer/task platform.",
        ),
        expected_files=(
            ExpectedFile(
                "business/DISTRIBUTED_AI_OPPORTUNITY.md",
                (
                    "current production proof unless",
                    "Mesh AI Router",
                    "Federated learning",
                ),
            ),
        ),
        local_claim_key="business_opportunity_claim_allowed",
    ),
)


def _check_file(root: Path, expected: ExpectedFile) -> dict[str, Any]:
    path = root / expected.path
    exists = path.exists()
    text = path.read_text(encoding="utf-8", errors="replace") if exists else ""
    markers_found = [marker for marker in expected.markers if marker in text]
    markers_missing = [marker for marker in expected.markers if marker not in text]
    return {
        "path": expected.path,
        "exists": exists,
        "markers_found": markers_found,
        "markers_missing": markers_missing,
        "complete": exists and not markers_missing,
    }


def _build_path(root: Path, spec: EconomicPathSpec) -> dict[str, Any]:
    file_checks = [_check_file(root, expected) for expected in spec.expected_files]
    local_verified = all(check["complete"] for check in file_checks)
    return {
        "path_id": spec.path_id,
        "name": spec.name,
        "monetization_mode": spec.monetization_mode,
        "current_state": spec.current_state,
        "verified_finding": spec.verified_finding,
        "readiness": "local_evidence_verified" if local_verified else "local_evidence_blocked",
        "files": file_checks,
        "next_evidence_needed": list(spec.next_evidence_needed),
        "claim_gate": {
            spec.local_claim_key: local_verified,
            "live_traffic_delivery_claim_allowed": False,
            "submitted_transaction_claim_allowed": False,
            "chain_finality_claim_allowed": False,
            "funds_received_claim_allowed": False,
            "revenue_recognition_claim_allowed": False,
        },
    }


def build_economic_layer_readiness(root: Path | str = ".") -> dict[str, Any]:
    root_path = Path(root)
    paths = [_build_path(root_path, spec) for spec in ECONOMIC_LAYER_PATH_SPECS]
    local_verified_total = sum(
        1 for path in paths if path["readiness"] == "local_evidence_verified"
    )
    all_local_verified = local_verified_total == len(paths)
    return {
        "schema": SCHEMA,
        "root": str(root_path.resolve()),
        "status": (
            "economic_layer_local_evidence_ready"
            if all_local_verified
            else "economic_layer_local_evidence_blocked"
        ),
        "wallet": {
            "address": TARGET_WALLET_ADDRESS,
            "masked": mask_wallet(TARGET_WALLET_ADDRESS),
            "routing_note": "Use this wallet only where a platform supports direct EVM payout.",
        },
        "summary": {
            "paths_total": len(paths),
            "local_verified_total": local_verified_total,
            "local_blocked_total": len(paths) - local_verified_total,
            "share_to_earn_live_payout_claim_allowed": False,
            "x0t_chain_submission_code_path_present": any(
                path["path_id"] == "token_rewards_chain_path"
                and path["readiness"] == "local_evidence_verified"
                for path in paths
            ),
            "marketplace_external_finality_claim_allowed": False,
            "live_revenue_ready": False,
            "funds_received_claim_allowed": False,
        },
        "paths": paths,
        "machine_commands": [
            "PYTHONPATH=. python3 scripts/ops/build_economic_layer_readiness_report.py",
            "PYTHONPATH=. python3 scripts/ops/build_productization_snapshot.py",
        ],
        "claim_boundary": CLAIM_BOUNDARY,
    }
