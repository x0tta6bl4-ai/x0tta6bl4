from __future__ import annotations

from pathlib import Path

from src.sales.pilot_package import PRIMARY_IDEA_ID
from src.sales.product_ideas import PRODUCT_IDEAS
from src.sales.wallet_payment_intake import (
    PAYMENT_REFERENCE,
    TARGET_WALLET_ADDRESS,
    build_wallet_payment_intake,
    is_evm_address_shape,
    mask_wallet,
)


def _write_primary_assets(root: Path) -> None:
    primary = next(idea for idea in PRODUCT_IDEAS if idea.idea_id == PRIMARY_IDEA_ID)
    for relative_path in primary.existing_repo_paths:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("asset\n", encoding="utf-8")


def test_wallet_payment_intake_is_ready_for_target_wallet(tmp_path: Path) -> None:
    _write_primary_assets(tmp_path)

    intake = build_wallet_payment_intake(tmp_path)

    assert TARGET_WALLET_ADDRESS == "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099"
    assert intake["schema"] == "x0tta6bl4.wallet_payment_intake.v1"
    assert intake["status"] == "payment_intake_ready"
    assert intake["wallet"]["address"] == TARGET_WALLET_ADDRESS
    assert intake["wallet"]["masked"] == "0x6017...e099"
    assert intake["wallet"]["address_kind"] == "evm_compatible_address"
    assert intake["wallet"]["address_shape_valid"] is True
    assert intake["payment_reference"] == PAYMENT_REFERENCE
    assert [item["amount_usd"] for item in intake["pricing_ladder"]] == [500, 2500, 10000]
    assert "Do not guess the chain" in intake["wallet"]["network_policy"]
    assert intake["claim_gate"]["payment_intake_claim_allowed"] is True
    assert intake["claim_gate"]["funds_received_claim_allowed"] is False
    assert intake["claim_gate"]["settlement_finality_claim_allowed"] is False
    assert "funds_received" in intake["claim_gate"]["blocked_claim_ids"]


def test_wallet_payment_intake_blocks_without_primary_pilot_assets(tmp_path: Path) -> None:
    intake = build_wallet_payment_intake(tmp_path)

    assert intake["status"] == "payment_intake_blocked"
    assert intake["claim_gate"]["payment_intake_claim_allowed"] is False
    assert intake["pilot_package_status"] == "pilot_package_blocked"


def test_evm_wallet_shape_and_masking() -> None:
    assert is_evm_address_shape(TARGET_WALLET_ADDRESS) is True
    assert is_evm_address_shape("0x123") is False
    assert is_evm_address_shape("not-a-wallet") is False
    assert mask_wallet(TARGET_WALLET_ADDRESS) == "0x6017...e099"
