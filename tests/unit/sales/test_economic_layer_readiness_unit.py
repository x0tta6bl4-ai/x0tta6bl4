from __future__ import annotations

from pathlib import Path

from src.sales.economic_layer_readiness import (
    ECONOMIC_LAYER_PATH_SPECS,
    build_economic_layer_readiness,
)


def _write_expected_files(root: Path) -> None:
    for spec in ECONOMIC_LAYER_PATH_SPECS:
        for expected_file in spec.expected_files:
            path = root / expected_file.path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("\n".join(expected_file.markers) + "\n", encoding="utf-8")


def test_economic_layer_readiness_verifies_local_evidence_without_money_claims(
    tmp_path: Path,
) -> None:
    _write_expected_files(tmp_path)

    report = build_economic_layer_readiness(tmp_path)

    assert report["schema"] == "x0tta6bl4.economic_layer_readiness.v1"
    assert report["status"] == "economic_layer_local_evidence_ready"
    assert report["wallet"]["address"] == "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099"
    assert report["summary"]["paths_total"] == 4
    assert report["summary"]["local_verified_total"] == 4
    assert report["summary"]["x0t_chain_submission_code_path_present"] is True
    assert report["summary"]["live_revenue_ready"] is False
    assert report["summary"]["funds_received_claim_allowed"] is False
    for path in report["paths"]:
        assert path["readiness"] == "local_evidence_verified"
        assert path["claim_gate"]["funds_received_claim_allowed"] is False
        assert path["claim_gate"]["chain_finality_claim_allowed"] is False


def test_economic_layer_readiness_blocks_when_files_are_missing(tmp_path: Path) -> None:
    report = build_economic_layer_readiness(tmp_path)

    assert report["status"] == "economic_layer_local_evidence_blocked"
    assert report["summary"]["local_verified_total"] == 0
    assert report["summary"]["local_blocked_total"] == 4
    assert report["summary"]["funds_received_claim_allowed"] is False
