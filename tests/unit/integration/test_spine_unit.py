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


def test_safe_actuator_default_bool_result_carries_bounded_metadata() -> None:
    def executor(_action: str, _context: dict) -> bool:
        return True

    result = SafeActuator(executor).execute(
        "local_heal",
        {"api_token": "super-secret", "node_id": "node-1"},
    )

    assert result.success is True
    metadata = result.evidence_metadata.to_dict()
    assert metadata["schema"] == SAFE_ACTUATOR_EVIDENCE_METADATA_SCHEMA
    assert metadata["redacted"] is True
    assert "super-secret" not in str(metadata)
    claim_gate = metadata["claim_gate"]
    assert claim_gate["schema"] == "x0tta6bl4.safe_actuator.adapter_claim_gate.v1"
    assert claim_gate["local_executor_invoked"] is True
    assert claim_gate["local_executor_result_claim_allowed"] is True
    assert claim_gate["dataplane_delivery_claim_allowed"] is False
    assert claim_gate["customer_traffic_claim_allowed"] is False
    assert claim_gate["external_settlement_finality_claim_allowed"] is False
    assert claim_gate["production_readiness_claim_allowed"] is False
    assert metadata["cross_plane_claim_gate"]["allowed"] is False
    assert metadata["evidence"]["context_keys"] == ["api_token", "node_id"]
    assert metadata["evidence"]["raw_context_values_redacted"] is True


def test_safe_actuator_missing_executor_carries_fail_closed_metadata() -> None:
    result = SafeActuator().execute("local_heal", {"api_token": "super-secret"})

    assert result.success is False
    metadata = result.evidence_metadata.to_dict()
    assert "super-secret" not in str(metadata)
    claim_gate = metadata["claim_gate"]
    assert claim_gate["local_executor_configured"] is False
    assert claim_gate["local_executor_callable"] is False
    assert claim_gate["local_executor_invoked"] is False
    assert claim_gate["local_executor_result_claim_allowed"] is False
    assert claim_gate["production_readiness_claim_allowed"] is False
    assert "executor_not_configured" in claim_gate["blockers"]


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


@pytest.mark.asyncio
async def test_async_safe_actuator_default_result_carries_bounded_metadata() -> None:
    async def executor(_action: str, _context: dict) -> bool:
        return False

    result = await AsyncSafeActuator(executor).execute(
        "rotate_identity",
        {"private_key": "super-secret"},
    )

    assert result.success is False
    metadata = result.evidence_metadata.to_dict()
    assert "super-secret" not in str(metadata)
    claim_gate = metadata["claim_gate"]
    assert claim_gate["surface"] == "src.integration.spine.AsyncSafeActuator"
    assert claim_gate["local_executor_invoked"] is True
    assert claim_gate["local_executor_result_claim_allowed"] is False
    assert claim_gate["dataplane_delivery_claim_allowed"] is False
    assert claim_gate["production_readiness_claim_allowed"] is False
    assert "local_executor_result_not_successful" in claim_gate["blockers"]
