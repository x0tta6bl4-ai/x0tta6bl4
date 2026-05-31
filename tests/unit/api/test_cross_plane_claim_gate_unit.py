from __future__ import annotations

from src.api import cross_plane_claim_gate


def test_cross_plane_claim_gate_metadata_surfaces_claim_blockers(
    monkeypatch,
    tmp_path,
) -> None:
    def fake_build_report(root, *, claims):
        assert root == tmp_path
        assert claims == (
            "production_readiness",
            "dataplane_delivery",
            "dpi_bypass",
        )
        return {
            "schema": "x0tta6bl4.cross_plane_proof_gate.v1",
            "decision": "CROSS_PLANE_CLAIMS_BLOCKED",
            "allowed": False,
            "summary": {"claims_blocked": 2, "claims_allowed": 1},
            "context": {"source_artifact_hashes_present": True},
            "claim_results": [
                {
                    "claim_id": "production_readiness",
                    "allowed": False,
                    "blockers": [
                        "production_readiness_dataplane_artifact_not_verified",
                        "trust_finality_artifact_not_verified",
                    ],
                },
                {"claim_id": "dataplane_delivery", "allowed": True},
                {
                    "claim_id": "dpi_bypass",
                    "allowed": False,
                    "blockers": ["dpi_lab_imported_artifact_not_verified"],
                },
            ],
            "claim_boundary": "test boundary",
        }

    monkeypatch.setattr(
        cross_plane_claim_gate,
        "build_cross_plane_proof_gate_report",
        fake_build_report,
    )

    metadata = cross_plane_claim_gate.cross_plane_claim_gate_metadata(
        [
            "production_readiness",
            "dataplane_delivery",
            "production_readiness",
            "dpi_bypass",
        ],
        root=tmp_path,
        surface="maas.test",
    )

    assert metadata["allowed"] is False
    assert metadata["surface"] == "maas.test"
    assert metadata["requested_claim_ids"] == [
        "production_readiness",
        "dataplane_delivery",
        "dpi_bypass",
    ]
    assert metadata["allowed_claim_ids"] == ["dataplane_delivery"]
    assert metadata["blocked_claim_ids"] == ["dpi_bypass", "production_readiness"]
    assert metadata["blockers"] == [
        "dpi_lab_imported_artifact_not_verified",
        "production_readiness_dataplane_artifact_not_verified",
        "trust_finality_artifact_not_verified",
    ]
    assert metadata["claim_blockers"] == {
        "dpi_bypass": ["dpi_lab_imported_artifact_not_verified"],
        "production_readiness": [
            "production_readiness_dataplane_artifact_not_verified",
            "trust_finality_artifact_not_verified",
        ],
    }


def test_cross_plane_claim_gate_unavailable_blocks_every_requested_claim(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        cross_plane_claim_gate,
        "build_cross_plane_proof_gate_report",
        None,
    )

    metadata = cross_plane_claim_gate.cross_plane_claim_gate_metadata(
        ["production_readiness", "settlement_finality"],
        surface="maas.test",
    )

    assert metadata["allowed"] is False
    assert metadata["available"] is False
    assert metadata["blocked_claim_ids"] == [
        "production_readiness",
        "settlement_finality",
    ]
    assert metadata["allowed_claim_ids"] == []
    assert metadata["blockers"] == ["cross_plane_proof_gate_unavailable"]
    assert metadata["claim_blockers"] == {
        "production_readiness": ["cross_plane_proof_gate_unavailable"],
        "settlement_finality": ["cross_plane_proof_gate_unavailable"],
    }
