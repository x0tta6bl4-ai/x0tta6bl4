from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from src.coordination.events import EventBus, EventType


ROOT = Path(__file__).resolve().parents[3]


def _load_module():
    path = ROOT / "scripts/ops/smoke_ledger_event_trace_citation.py"
    spec = importlib.util.spec_from_file_location(
        "smoke_ledger_event_trace_citation",
        path,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_smoke_returns_event_backed_ledger_citation(tmp_path):
    smoke = _load_module()
    stale_bus = EventBus(str(tmp_path))
    stale_bus.publish(
        EventType.SYSTEM_ALERT,
        "stale-source",
        {"spiffe_id": "spiffe://secret/stale-history"},
    )

    payload = await smoke.run_smoke(temp_root=tmp_path)

    assert payload["status"] == "PASS"
    assert payload["assertions"] == {
        "indexed_successfully": True,
        "citations_present": True,
        "swarm_event_id_matches": True,
        "swarm_layer_matches": True,
        "marketplace_event_id_matches": True,
        "marketplace_layer_matches": True,
        "marketplace_api_event_id_matches": True,
        "marketplace_api_layer_matches": True,
        "marketplace_api_evidence_summary_request_present": True,
        "marketplace_api_evidence_summary_idempotency_present": True,
        "marketplace_api_evidence_summary_identity_present": True,
        "maas_governance_event_id_matches": True,
        "maas_governance_layer_matches": True,
        "maas_billing_event_id_matches": True,
        "maas_billing_layer_matches": True,
        "dao_event_id_matches": True,
        "dao_layer_matches": True,
        "recovery_event_id_matches": True,
        "recovery_layer_matches": True,
        "mesh_reward_event_id_matches": True,
        "mesh_reward_layer_matches": True,
        "mesh_reward_upstream_event_id_matches": True,
        "mesh_reward_upstream_source_agent_matches": True,
        "mesh_reward_upstream_payloads_redacted": True,
        "share_to_earn_event_id_matches": True,
        "share_to_earn_layer_matches": True,
        "mptcp_event_id_matches": True,
        "mptcp_layer_matches": True,
        "spire_server_event_id_matches": True,
        "spire_server_layer_matches": True,
        "pqc_rotator_event_id_matches": True,
        "pqc_rotator_layer_matches": True,
        "pqc_healer_event_id_matches": True,
        "pqc_healer_layer_matches": True,
        "pqc_healer_service_name_matches": True,
        "source_class_matches": True,
        "redacted_true": True,
        "citation_summary_metadata_present": True,
        "claim_boundary_summaries_bounded": True,
        "claim_boundaries_present_for_bounded_services": True,
        "cross_plane_summaries_fail_closed": True,
        "economy_summaries_fail_closed": True,
        "economy_services_have_local_only_gates": True,
        "secret_values_absent": True,
    }
    citations = payload["citations_by_service"]
    assert set(citations) == {
        "swarm-pbft",
        "maas-settlement",
        "maas-marketplace",
        "maas-governance",
        "maas-billing",
        "dao-executor",
        "recovery-action-executor",
        "mesh-vpn-bridge",
        "share-to-earn",
        "mptcp-manager",
        "spire-server-client",
        "pqc-rotator",
        "pqc-zero-trust-healer",
    }
    assert "stale-source" not in citations

    swarm = citations["swarm-pbft"]
    assert swarm["source"] == "EventBus"
    assert swarm["source_class"] == "event_trace"
    assert swarm["event_id"] == payload["events"]["swarm-pbft"]["event_id"]
    assert swarm["layer"] == "swarm_consensus_to_control_plane"
    assert swarm["claim_boundary_summary"]["present"] is False
    assert swarm["claim_boundary_summary"]["redacted"] is True
    assert swarm["cross_plane_evidence_profile"]["primary_status"] == "local_only"
    assert swarm["cross_plane_evidence_profile"]["dataplane_confirmed"] is False
    assert swarm["economy_finality_summary"]["production_ready_candidate"] is False
    assert swarm["redacted"] is True

    marketplace = citations["maas-settlement"]
    assert marketplace["source"] == "EventBus"
    assert marketplace["source_class"] == "event_trace"
    assert marketplace["event_id"] == payload["events"]["maas-settlement"]["event_id"]
    assert marketplace["event_type"] == "marketplace.escrow.released"
    assert marketplace["layer"] == "commerce_settlement_to_events"
    assert marketplace["entrypoint"] == "src/services/marketplace_settlement.py"
    assert marketplace["claim_boundary_summary"]["present"] is True
    assert marketplace["cross_plane_evidence_profile"]["local_only"] is True
    assert marketplace["economy_finality_summary"]["local_or_pending_only"] is True
    assert (
        marketplace["economy_finality_summary"]["high_risk_claim_gate"][
            "external_settlement_finality_claim_allowed"
        ]
        is False
    )
    assert (
        marketplace["economy_finality_summary"]["high_risk_claim_gate"][
            "production_readiness_claim_allowed"
        ]
        is False
    )
    assert marketplace["redacted"] is True

    marketplace_api = citations["maas-marketplace"]
    assert marketplace_api["source"] == "EventBus"
    assert marketplace_api["source_class"] == "event_trace"
    assert marketplace_api["event_id"] == (
        payload["events"]["maas-marketplace"]["event_id"]
    )
    assert marketplace_api["event_type"] == "marketplace.escrow.held"
    assert marketplace_api["layer"] == "api_to_commerce"
    assert marketplace_api["entrypoint"] == "src/api/maas_marketplace.py"
    marketplace_api_summary = marketplace_api["evidence_summary"]
    assert marketplace_api_summary["request_evidence"]["present"] is True
    assert (
        marketplace_api_summary["request_evidence"]["idempotency_key_present"]
        is True
    )
    assert marketplace_api_summary["request_evidence"]["service_identity_present"] == {
        "spiffe_id": True,
        "did": True,
        "wallet_address": True,
    }
    assert marketplace_api["claim_boundary_summary"]["present"] is True
    assert marketplace_api["cross_plane_evidence_profile"]["local_only"] is True
    assert marketplace_api["economy_finality_summary"]["local_or_pending_only"] is True
    assert marketplace_api["redacted"] is True

    maas_governance = citations["maas-governance"]
    assert maas_governance["source"] == "EventBus"
    assert maas_governance["source_class"] == "event_trace"
    assert maas_governance["event_id"] == (
        payload["events"]["maas-governance"]["event_id"]
    )
    assert maas_governance["event_type"] == "pipeline.stage_end"
    assert maas_governance["layer"] == "api_to_control_plane"
    assert maas_governance["entrypoint"] == "src/api/maas_governance.py"
    assert maas_governance["redacted"] is True

    maas_billing = citations["maas-billing"]
    assert maas_billing["source"] == "EventBus"
    assert maas_billing["source_class"] == "event_trace"
    assert maas_billing["event_id"] == payload["events"]["maas-billing"]["event_id"]
    assert maas_billing["event_type"] == "pipeline.stage_end"
    assert maas_billing["layer"] == "billing_webhook_to_commerce_bridge"
    assert maas_billing["entrypoint"] == "src/api/maas_billing.py"
    assert maas_billing["redacted"] is True

    dao = citations["dao-executor"]
    assert dao["source"] == "EventBus"
    assert dao["source_class"] == "event_trace"
    assert dao["event_id"] == payload["events"]["dao-executor"]["event_id"]
    assert dao["event_type"] == "task.blocked"
    assert dao["layer"] == "dao_to_control_plane"
    assert dao["entrypoint"] == "src/dao/executor_webhook.py"
    assert dao["redacted"] is True

    recovery = citations["recovery-action-executor"]
    assert recovery["source"] == "EventBus"
    assert recovery["source_class"] == "event_trace"
    assert recovery["event_id"] == (
        payload["events"]["recovery-action-executor"]["event_id"]
    )
    assert recovery["event_type"] == "task.blocked"
    assert recovery["layer"] == "self_healing_to_control_plane"
    assert recovery["entrypoint"] == "src/self_healing/recovery/executor.py"
    assert recovery["redacted"] is True

    mesh_reward = citations["mesh-vpn-bridge"]
    assert mesh_reward["source"] == "EventBus"
    assert mesh_reward["source_class"] == "event_trace"
    assert mesh_reward["event_id"] == payload["events"]["mesh-vpn-bridge"]["event_id"]
    assert mesh_reward["event_type"] == "reward.relay.recorded"
    assert mesh_reward["layer"] == "network_to_rewards"
    assert mesh_reward["entrypoint"] == "src/network/mesh_vpn_bridge.py"
    assert mesh_reward["redacted"] is True
    mesh_reward_event = payload["events"]["mesh-vpn-bridge"]
    assert mesh_reward_event["upstream_event_linked"] is True
    assert mesh_reward_event["upstream_source_agent_linked"] is True
    assert mesh_reward_event["upstream_payloads_redacted"] is True
    assert mesh_reward_event["upstream_event_id"] != mesh_reward_event["event_id"]

    share_to_earn = citations["share-to-earn"]
    assert share_to_earn["source"] == "EventBus"
    assert share_to_earn["source_class"] == "event_trace"
    assert share_to_earn["event_id"] == payload["events"]["share-to-earn"]["event_id"]
    assert share_to_earn["event_type"] == "reward.relay.recorded"
    assert share_to_earn["layer"] == "network_usage_to_rewards"
    assert share_to_earn["entrypoint"] == "src/services/share_to_earn_service.py"
    assert share_to_earn["redacted"] is True

    mptcp = citations["mptcp-manager"]
    assert mptcp["source"] == "EventBus"
    assert mptcp["source_class"] == "event_trace"
    assert mptcp["event_id"] == payload["events"]["mptcp-manager"]["event_id"]
    assert mptcp["event_type"] == "pipeline.stage_end"
    assert mptcp["layer"] == "network_to_control_plane"
    assert mptcp["entrypoint"] == "src/network/mptcp_manager.py"
    assert mptcp["redacted"] is True

    spire_server = citations["spire-server-client"]
    assert spire_server["source"] == "EventBus"
    assert spire_server["source_class"] == "event_trace"
    assert spire_server["event_id"] == (
        payload["events"]["spire-server-client"]["event_id"]
    )
    assert spire_server["event_type"] == "pipeline.stage_end"
    assert spire_server["layer"] == "security_identity_to_control_plane"
    assert spire_server["entrypoint"] == "src/security/spiffe/server/client.py"
    assert spire_server["redacted"] is True

    pqc_rotator = citations["pqc-rotator"]
    assert pqc_rotator["source"] == "EventBus"
    assert pqc_rotator["source_class"] == "event_trace"
    assert pqc_rotator["event_id"] == payload["events"]["pqc-rotator"]["event_id"]
    assert pqc_rotator["event_type"] == "pipeline.stage_end"
    assert pqc_rotator["layer"] == "security_service_to_control_plane"
    assert pqc_rotator["entrypoint"] == "src/services/pqc_rotator_service.py"
    assert pqc_rotator["redacted"] is True

    pqc_healer = citations["pqc-zero-trust-healer"]
    assert pqc_healer["source"] == "EventBus"
    assert pqc_healer["source_class"] == "event_trace"
    assert pqc_healer["event_id"] == (
        payload["events"]["pqc-zero-trust-healer"]["event_id"]
    )
    assert pqc_healer["event_type"] == "pipeline.stage_end"
    assert pqc_healer["source_agent"] == "pqc-zero-trust-healer"
    assert pqc_healer["service_name"] == "pqc-zero-trust-executor"
    assert pqc_healer["layer"] == "self_healing_pqc_identity"
    assert pqc_healer["entrypoint"] == "src/self_healing/pqc_zero_trust_healer.py"
    assert pqc_healer["redacted"] is True
