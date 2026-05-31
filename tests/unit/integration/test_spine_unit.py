import pytest

from src.integration.spine import (
    SAFE_ACTUATOR_EVIDENCE_METADATA_SCHEMA,
    AsyncSafeActuator,
    SafeActuator,
    SafeActuatorEvidenceMetadata,
    SafeActuatorResult,
)


def _safe_actuator_evidence_payload() -> dict:
    return {
        "claim_gate": {
            "schema": "x0tta6bl4.test.claim_gate.v1",
            "decision": "LOCAL_RECOVERY_LIFECYCLE_ONLY",
            "claim_boundary": "bounded test claim only",
        },
        "cross_plane_claim_gate": {"allowed": False},
        "evidence": {
            "event_ids": ["evt-1"],
            "source_agents": ["test-probe"],
            "events_total": 1,
            "redacted": True,
        },
        "claim_boundary": "bounded test claim only",
        "redacted": True,
    }


def test_safe_actuator_evidence_metadata_normalizes_redacted_payload() -> None:
    metadata = SafeActuatorEvidenceMetadata.from_value(
        {"safe_actuator_evidence": _safe_actuator_evidence_payload()}
    )

    assert metadata.claim_gate["schema"] == "x0tta6bl4.test.claim_gate.v1"
    assert metadata.cross_plane_claim_gate == {"allowed": False}
    assert metadata.event_ids == ["evt-1"]
    assert metadata.source_agents == ["test-probe"]
    assert metadata.redacted is True
    assert metadata.to_dict()["schema"] == SAFE_ACTUATOR_EVIDENCE_METADATA_SCHEMA


def test_safe_actuator_preserves_evidence_metadata_from_dict_result() -> None:
    def executor(_action: str, _context: dict) -> dict:
        return {
            "success": True,
            "reason": "bounded local action",
            "safe_actuator_evidence": _safe_actuator_evidence_payload(),
        }

    result = SafeActuator(executor).execute("local_heal", {})

    assert result == SafeActuatorResult(
        success=True,
        reason="bounded local action",
        evidence_metadata=result.evidence_metadata,
    )
    assert result.evidence_metadata.claim_gate["decision"] == (
        "LOCAL_RECOVERY_LIFECYCLE_ONLY"
    )
    assert result.evidence_metadata.event_ids == ["evt-1"]


@pytest.mark.asyncio
async def test_async_safe_actuator_preserves_evidence_metadata_from_dict_result() -> None:
    async def executor(_action: str, _context: dict) -> dict:
        return {
            "ok": True,
            "safe_actuator_evidence": _safe_actuator_evidence_payload(),
        }

    result = await AsyncSafeActuator(executor).execute("local_heal", {})

    assert result.success is True
    assert result.evidence_metadata.source_agents == ["test-probe"]
    assert result.evidence_metadata.to_dict()["redacted"] is True
