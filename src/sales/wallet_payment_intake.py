"""Wallet payment intake package for the first x0tta6bl4 paid pilot."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from src.sales.pilot_package import OFFER_NAME, build_pilot_package
from src.sales.product_ideas import CLAIM_BOUNDARY, STRONG_CLAIMS


SCHEMA = "x0tta6bl4.wallet_payment_intake.v1"
CLAIM_GATE_SCHEMA = "x0tta6bl4.wallet_payment_intake.claim_gate.v1"
TARGET_WALLET_ADDRESS = "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099"
PAYMENT_REFERENCE = "X0T-PILOT-6017E099"


def is_evm_address_shape(value: str) -> bool:
    return bool(re.fullmatch(r"0x[a-fA-F0-9]{40}", value.strip()))


def mask_wallet(value: str) -> str:
    value = value.strip()
    if len(value) <= 12:
        return value
    return f"{value[:6]}...{value[-4:]}"


def _claim_gate(*, intake_ready: bool) -> dict[str, Any]:
    blockers = []
    if not intake_ready:
        blockers.append("payment_intake_contract_not_ready")
    blockers.extend(f"{claim}_requires_onchain_payment_evidence" for claim in STRONG_CLAIMS)
    blockers.append("funds_received_requires_confirmed_transaction_hash")
    return {
        "schema": CLAIM_GATE_SCHEMA,
        "surface": "wallet_payment_intake",
        "payment_intake_claim_allowed": intake_ready,
        "funds_received_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "blocked_claim_ids": [*STRONG_CLAIMS, "funds_received"],
        "blockers": blockers,
        "claim_boundary": (
            f"{CLAIM_BOUNDARY} This payment intake proves only that a wallet-based "
            "checkout package exists. It does not prove funds were received."
        ),
    }


def build_wallet_payment_intake(root: Path | str = ".") -> dict[str, Any]:
    pilot = build_pilot_package(root)
    address_shape_valid = is_evm_address_shape(TARGET_WALLET_ADDRESS)
    intake_ready = bool(address_shape_valid and pilot["status"] == "pilot_package_ready")
    return {
        "schema": SCHEMA,
        "status": "payment_intake_ready" if intake_ready else "payment_intake_blocked",
        "offer_name": OFFER_NAME,
        "payment_reference": PAYMENT_REFERENCE,
        "wallet": {
            "address": TARGET_WALLET_ADDRESS,
            "masked": mask_wallet(TARGET_WALLET_ADDRESS),
            "address_kind": "evm_compatible_address",
            "address_shape_valid": address_shape_valid,
            "checksum_status": "not_checked_without_keccak",
            "network_policy": (
                "Do not guess the chain. Buyer and operator must agree the exact "
                "EVM network and token before payment."
            ),
            "wallet_uri": f"ethereum:{TARGET_WALLET_ADDRESS}",
        },
        "pricing_ladder": [
            {
                "item_id": "pilot_deposit",
                "label": "Pilot deposit",
                "amount_usd": 500,
                "purpose": "Reserve the first setup call and local controller walkthrough.",
            },
            {
                "item_id": "pilot_setup",
                "label": "Pilot setup package",
                "amount_usd": 2500,
                "purpose": "Package the local controller, onboarding runbook, and proof report.",
            },
            {
                "item_id": "site_pilot",
                "label": "Small site pilot",
                "amount_usd": 10000,
                "purpose": "Run a focused site pilot with node onboarding and operator handoff.",
            },
        ],
        "buyer_steps": [
            "Pick one pricing item.",
            "Agree the exact EVM network and token with the operator before sending funds.",
            f"Send the agreed amount to {TARGET_WALLET_ADDRESS}.",
            f"Use reference {PAYMENT_REFERENCE} in the invoice, email, or chat thread.",
            "Return the transaction hash for local verification.",
        ],
        "operator_steps": [
            "Send the buyer the payment intake document or PRODUCT tab screenshot.",
            "Confirm chain, token, amount, and payment reference before payment.",
            "After payment, verify the transaction hash on the selected chain.",
            "Only then mark funds as received in local records.",
        ],
        "pilot_package_status": pilot["status"],
        "pilot_package_claim_gate": pilot["claim_gate"],
        "claim_gate": _claim_gate(intake_ready=intake_ready),
    }
