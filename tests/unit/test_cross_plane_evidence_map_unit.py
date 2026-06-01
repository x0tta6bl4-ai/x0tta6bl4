from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MAP_PATH = ROOT / "docs/architecture/CURRENT_CROSS_PLANE_EVIDENCE_MAP.json"

REQUIRED_PLANES = {
    "data_plane",
    "control_plane",
    "trust_plane",
    "evidence_plane",
    "economy_plane",
}

REQUIRED_LINK_IDS = {
    "local-mesh-observed-state-to-event-trace-memory",
    "mesh-metric-quality-to-high-risk-control",
    "maas-heal-post-action-probe-to-bounded-restored-dataplane",
    "ebpf-safe-actuator-runtime-metadata-boundary",
    "maas-governance-safe-actuator-runtime-metadata-boundary",
    "spire-safe-actuator-runtime-metadata-boundary",
    "token-bridge-safe-actuator-runtime-metadata-boundary",
    "deployment-safe-actuator-runtime-metadata-boundary",
    "identity-configuration-to-redacted-runtime-traces",
    "measured-attestation-smoke-to-proof-gate-boundary",
    "pqc-ghost-safe-actuator-runtime-metadata-boundary",
    "billing-webhook-to-vpn-provisioning-boundary",
    "mesh-usage-to-reward-accounting-boundary",
    "marketplace-escrow-to-bounded-settlement-evidence",
    "anti-censorship-local-evidence-to-dpi-claim-boundary",
}

REQUIRED_LINK_FALSE_FLAGS = {
    "local-mesh-observed-state-to-event-trace-memory": {
        "dataplane_confirmed",
        "remote_peer_authenticity_confirmed",
        "production_customer_traffic_confirmed",
    },
    "mesh-metric-quality-to-high-risk-control": {
        "all_high_risk_actions_covered",
        "maas_heal_dataplane_claim_allowed",
        "post_action_dataplane_revalidated",
        "restored_dataplane_claim_allowed",
    },
    "ebpf-safe-actuator-runtime-metadata-boundary": {
        "restored_dataplane_claim_allowed",
        "route_convergence_claim_allowed",
        "kernel_forwarding_correctness_claim_allowed",
        "dataplane_delivery_claim_allowed",
        "traffic_delivery_claim_allowed",
        "customer_traffic_claim_allowed",
        "external_dpi_bypass_confirmed",
        "settlement_finality_confirmed",
        "production_slo_claim_allowed",
        "production_readiness_claim_allowed",
    },
    "maas-governance-safe-actuator-runtime-metadata-boundary": {
        "dao_governance_finality_claim_allowed",
        "external_settlement_finality_claim_allowed",
        "dataplane_delivery_claim_allowed",
        "customer_traffic_claim_allowed",
        "production_governance_execution_claim_allowed",
        "production_readiness_claim_allowed",
    },
    "spire-safe-actuator-runtime-metadata-boundary": {
        "live_spire_mtls_claim_allowed",
        "workload_svid_possession_claim_allowed",
        "workload_identity_trust_finality_claim_allowed",
        "node_attestation_finality_claim_allowed",
        "dataplane_delivery_claim_allowed",
        "customer_traffic_claim_allowed",
        "production_identity_readiness_claim_allowed",
        "production_readiness_claim_allowed",
    },
    "token-bridge-safe-actuator-runtime-metadata-boundary": {
        "external_settlement_finality_claim_allowed",
        "payment_provider_settlement_claim_allowed",
        "bank_settlement_claim_allowed",
        "live_token_settlement_finality_claim_allowed",
        "dataplane_delivery_claim_allowed",
        "traffic_delivery_claim_allowed",
        "customer_traffic_claim_allowed",
        "revenue_recognition_claim_allowed",
        "production_readiness_claim_allowed",
    },
    "deployment-safe-actuator-runtime-metadata-boundary": {
        "traffic_shift_claim_allowed",
        "live_customer_traffic_claim_allowed",
        "production_slo_claim_allowed",
        "external_dpi_bypass_confirmed",
        "external_settlement_finality_claim_allowed",
        "production_readiness_claim_allowed",
    },
    "maas-heal-post-action-probe-to-bounded-restored-dataplane": {
        "traffic_delivery_claim_allowed",
        "customer_traffic_claim_allowed",
        "external_reachability_claim_allowed",
        "production_slo_claim_allowed",
        "production_readiness_claim_allowed",
    },
    "identity-configuration-to-redacted-runtime-traces": {
        "live_spire_svid_confirmed",
        "did_ownership_confirmed",
        "wallet_control_confirmed",
        "chain_identity_finality_confirmed",
    },
    "measured-attestation-smoke-to-proof-gate-boundary": {
        "production_trust_finality",
        "production_ready",
        "fleet_wide_hardware_coverage_confirmed",
        "pqc_identity_finality_confirmed",
        "production_readiness_claim_allowed",
    },
    "pqc-ghost-safe-actuator-runtime-metadata-boundary": {
        "live_pqc_trust_finality_claim_allowed",
        "fleet_wide_key_rollout_claim_allowed",
        "restored_dataplane_claim_allowed",
        "dataplane_delivery_claim_allowed",
        "kernel_forwarding_correctness_claim_allowed",
        "customer_traffic_claim_allowed",
        "external_settlement_finality_claim_allowed",
        "production_readiness_claim_allowed",
    },
    "billing-webhook-to-vpn-provisioning-boundary": {
        "payment_settlement_confirmed",
        "payment_provider_settlement_claim_allowed",
        "bank_settlement_claim_allowed",
        "customer_vpn_reachability_confirmed",
        "customer_client_installation_confirmed",
        "customer_access_claim_allowed",
        "customer_dataplane_delivery_claim_allowed",
        "traffic_delivery_claim_allowed",
        "external_settlement_finality_claim_allowed",
        "production_readiness_claim_allowed",
        "dataplane_confirmed",
    },
    "mesh-usage-to-reward-accounting-boundary": {
        "settlement_finality_confirmed",
        "dataplane_confirmed",
        "traffic_delivery_confirmed",
        "live_token_settlement_confirmed",
        "reward_traffic_delivery_claim_allowed",
        "reward_token_settlement_finality_claim_allowed",
        "reward_production_readiness_claim_allowed",
    },
    "marketplace-escrow-to-bounded-settlement-evidence": {
        "dataplane_confirmed",
        "external_settlement_finality_confirmed",
        "maas_telemetry_dataplane_delivery_claim_allowed",
        "maas_telemetry_node_reachability_claim_allowed",
        "maas_telemetry_production_readiness_claim_allowed",
        "maas_telemetry_settlement_finality_claim_allowed",
        "provider_sla_confirmed",
        "production_readiness_claim_allowed",
        "traffic_delivery_claim_allowed",
    },
    "anti-censorship-local-evidence-to-dpi-claim-boundary": {
        "customer_traffic_claim_allowed",
        "external_dpi_intake_production_readiness_claim_allowed",
        "dataplane_confirmed",
        "durable_censorship_bypass_claim_allowed",
        "proof_gate_dpi_bypass_claim_allowed",
    },
}


def _load_map() -> dict[str, Any]:
    return json.loads(MAP_PATH.read_text(encoding="utf-8"))


def _source_refs(value: Any) -> list[str]:
    refs: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "source_refs":
                refs.extend(str(item) for item in child)
            elif key == "source_ref":
                refs.append(str(child))
            else:
                refs.extend(_source_refs(child))
    elif isinstance(value, list):
        for child in value:
            refs.extend(_source_refs(child))
    return refs


def test_cross_plane_evidence_map_is_working_map_not_completion_proof():
    evidence_map = _load_map()

    assert evidence_map["status"] == "working_map_not_production_completion_proof"
    assert "not a production readiness claim" in evidence_map["scope"]


def test_cross_plane_evidence_map_links_current_authoritative_maps():
    evidence_map = _load_map()
    linked_paths = {entry["path"] for entry in evidence_map["linked_maps"]}

    assert {
        "docs/architecture/CURRENT_ACTIVE_GOAL_GAP_AUDIT.md",
        "docs/architecture/CURRENT_EVENT_CONTROL_PLANE_MAP.json",
        "docs/architecture/CURRENT_EVIDENCE_RUNTIME_BRIDGE_MAP.json",
        "docs/architecture/CURRENT_POLICY_ENFORCEMENT_MAP.json",
    }.issubset(linked_paths)


def test_cross_plane_evidence_map_source_refs_resolve_to_existing_lines():
    evidence_map = _load_map()

    for source_ref in _source_refs(evidence_map):
        path_text, line_text = source_ref.rsplit(":", 1)
        path = ROOT / path_text
        assert path.exists(), source_ref
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        assert 1 <= int(line_text) <= line_count, source_ref


def test_cross_plane_evidence_map_has_required_planes_with_boundaries():
    evidence_map = _load_map()
    planes = evidence_map["planes"]

    assert set(planes) == REQUIRED_PLANES
    for plane_id, plane in planes.items():
        assert plane["role"], plane_id
        assert plane["verified_contours"], plane_id
        assert plane["claim_boundaries"], plane_id
        assert plane["source_refs"], plane_id
        assert any("not" in item.lower() for item in plane["claim_boundaries"]), plane_id


def test_cross_plane_links_cover_required_links_and_known_planes():
    evidence_map = _load_map()
    planes = set(evidence_map["planes"])
    links = evidence_map["cross_plane_links"]

    assert {link["id"] for link in links} == REQUIRED_LINK_IDS
    for link in links:
        assert set(link["from_planes"]).issubset(planes), link["id"]
        assert set(link["to_planes"]).issubset(planes), link["id"]
        assert link["current_path"], link["id"]
        assert link["verified_evidence"], link["id"]
        assert link["boundary"], link["id"]
        assert link["source_refs"], link["id"]
        assert isinstance(link["proof_flags"], dict), link["id"]
        assert any(value is False for value in link["proof_flags"].values()), link["id"]


def test_cross_plane_local_only_links_keep_high_risk_claim_flags_false():
    evidence_map = _load_map()
    links = {link["id"]: link for link in evidence_map["cross_plane_links"]}

    for link_id, false_flags in REQUIRED_LINK_FALSE_FLAGS.items():
        proof_flags = links[link_id]["proof_flags"]
        for flag in false_flags:
            assert proof_flags[flag] is False, (link_id, flag)


def test_cross_plane_current_dpi_subclaim_stays_false_without_latest_json():
    evidence_map = _load_map()
    links = {link["id"]: link for link in evidence_map["cross_plane_links"]}
    link = links["anti-censorship-local-evidence-to-dpi-claim-boundary"]
    proof_flags = link["proof_flags"]

    assert proof_flags["external_dpi_tested"] is False
    assert proof_flags["dpi_bypass_confirmed"] is False
    assert proof_flags["bypass_confirmed"] is False
    assert proof_flags["customer_traffic_claim_allowed"] is False
    assert proof_flags["external_dpi_intake_production_readiness_claim_allowed"] is False
    assert "machine-readable latest JSON" in link["current_path"]
    assert "must not claim external DPI" in link["boundary"]


def test_cross_plane_measured_attestation_smoke_is_bounded_trust_evidence():
    evidence_map = _load_map()
    links = {link["id"]: link for link in evidence_map["cross_plane_links"]}
    link = links["measured-attestation-smoke-to-proof-gate-boundary"]
    proof_flags = link["proof_flags"]

    assert proof_flags["measured_attestation_verifier_smoke_claim_available"] is True
    assert proof_flags["measured_attestation_verifier_smoke_validator_present"] is True
    assert proof_flags["production_trust_finality"] is False
    assert proof_flags["production_ready"] is False
    assert proof_flags["production_readiness_claim_allowed"] is False
    assert "one supplied attestation sample" in link["boundary"]
    assert "docs/verification/incoming/measured_attestation_verifier_smoke.json" in (
        link["current_path"]
    )


def test_cross_plane_maas_heal_probe_is_bounded_local_dataplane_evidence():
    evidence_map = _load_map()
    links = {link["id"]: link for link in evidence_map["cross_plane_links"]}
    link = links["maas-heal-post-action-probe-to-bounded-restored-dataplane"]
    proof_flags = link["proof_flags"]

    assert proof_flags["local_healing_action_applied"] is True
    assert proof_flags["bounded_post_action_probe_executed"] is True
    assert proof_flags["maas_heal_surface_revalidated"] is True
    assert proof_flags["bounded_restored_dataplane_claim_allowed"] is True
    assert proof_flags["traffic_delivery_claim_allowed"] is False
    assert proof_flags["customer_traffic_claim_allowed"] is False
    assert proof_flags["production_readiness_claim_allowed"] is False
    assert "scripts/ops/verify_maas_heal_post_action_dataplane_probe.py:1" in (
        link["source_refs"]
    )
    assert "bounded local post-action dataplane revalidation" in link["boundary"]


def test_cross_plane_ebpf_safe_actuator_metadata_is_bounded_runtime_evidence():
    evidence_map = _load_map()
    links = {link["id"]: link for link in evidence_map["cross_plane_links"]}
    link = links["ebpf-safe-actuator-runtime-metadata-boundary"]
    proof_flags = link["proof_flags"]

    assert proof_flags["ebpf_self_healing_safe_actuator_metadata_present"] is True
    assert proof_flags["local_ebpf_recovery_action_metadata_present"] is True
    assert proof_flags["restored_dataplane_claim_allowed"] is False
    assert proof_flags["route_convergence_claim_allowed"] is False
    assert proof_flags["kernel_forwarding_correctness_claim_allowed"] is False
    assert proof_flags["customer_traffic_claim_allowed"] is False
    assert proof_flags["production_readiness_claim_allowed"] is False
    assert "typed redacted SafeActuator metadata" in link["boundary"]
    assert "src/self_healing/ebpf_anomaly_detector.py:1" in link["source_refs"]
    assert "scripts/ops/check_real_readiness.py:1" in link["source_refs"]


def test_cross_plane_maas_governance_safe_actuator_metadata_is_bounded_runtime_evidence():
    evidence_map = _load_map()
    links = {link["id"]: link for link in evidence_map["cross_plane_links"]}
    link = links["maas-governance-safe-actuator-runtime-metadata-boundary"]
    proof_flags = link["proof_flags"]

    assert proof_flags["maas_governance_safe_actuator_metadata_present"] is True
    assert proof_flags["local_maas_governance_action_metadata_present"] is True
    assert proof_flags["dao_governance_finality_claim_allowed"] is False
    assert proof_flags["external_settlement_finality_claim_allowed"] is False
    assert proof_flags["dataplane_delivery_claim_allowed"] is False
    assert proof_flags["customer_traffic_claim_allowed"] is False
    assert proof_flags["production_readiness_claim_allowed"] is False
    assert "typed redacted SafeActuator metadata" in link["boundary"]
    assert "src/api/maas/endpoints/governance.py:1" in link["source_refs"]
    assert "scripts/ops/check_real_readiness.py:1" in link["source_refs"]


def test_cross_plane_spire_safe_actuator_metadata_is_bounded_runtime_evidence():
    evidence_map = _load_map()
    links = {link["id"]: link for link in evidence_map["cross_plane_links"]}
    link = links["spire-safe-actuator-runtime-metadata-boundary"]
    proof_flags = link["proof_flags"]

    assert proof_flags["spire_server_safe_actuator_metadata_present"] is True
    assert proof_flags["spire_agent_safe_actuator_metadata_present"] is True
    assert proof_flags["local_spire_server_cli_action_metadata_present"] is True
    assert proof_flags["local_spire_agent_cli_action_metadata_present"] is True
    assert proof_flags["live_spire_mtls_claim_allowed"] is False
    assert proof_flags["workload_svid_possession_claim_allowed"] is False
    assert proof_flags["workload_identity_trust_finality_claim_allowed"] is False
    assert proof_flags["node_attestation_finality_claim_allowed"] is False
    assert proof_flags["dataplane_delivery_claim_allowed"] is False
    assert proof_flags["customer_traffic_claim_allowed"] is False
    assert proof_flags["production_readiness_claim_allowed"] is False
    assert "typed redacted SafeActuator metadata" in link["boundary"]
    assert "src/security/spiffe/server/client.py:1" in link["source_refs"]
    assert "src/security/spiffe/agent/manager.py:1" in link["source_refs"]
    assert "scripts/ops/check_real_readiness.py:1" in link["source_refs"]


def test_cross_plane_token_bridge_safe_actuator_metadata_is_bounded_runtime_evidence():
    evidence_map = _load_map()
    links = {link["id"]: link for link in evidence_map["cross_plane_links"]}
    link = links["token-bridge-safe-actuator-runtime-metadata-boundary"]
    proof_flags = link["proof_flags"]

    assert proof_flags["token_bridge_safe_actuator_metadata_present"] is True
    assert proof_flags["local_chain_write_attempt_metadata_present"] is True
    assert proof_flags["pending_chain_submission_claim_allowed"] is True
    assert proof_flags["external_settlement_finality_claim_allowed"] is False
    assert proof_flags["payment_provider_settlement_claim_allowed"] is False
    assert proof_flags["bank_settlement_claim_allowed"] is False
    assert proof_flags["live_token_settlement_finality_claim_allowed"] is False
    assert proof_flags["dataplane_delivery_claim_allowed"] is False
    assert proof_flags["traffic_delivery_claim_allowed"] is False
    assert proof_flags["customer_traffic_claim_allowed"] is False
    assert proof_flags["revenue_recognition_claim_allowed"] is False
    assert proof_flags["production_readiness_claim_allowed"] is False
    assert "typed redacted SafeActuator metadata" in link["boundary"]
    assert "src/dao/bridge/core.py:1" in link["source_refs"]
    assert "scripts/ops/check_real_readiness.py:1" in link["source_refs"]


def test_cross_plane_deployment_safe_actuator_metadata_is_bounded_runtime_evidence():
    evidence_map = _load_map()
    links = {link["id"]: link for link in evidence_map["cross_plane_links"]}
    link = links["deployment-safe-actuator-runtime-metadata-boundary"]
    proof_flags = link["proof_flags"]

    assert proof_flags["canary_deployment_safe_actuator_metadata_present"] is True
    assert proof_flags["multi_cloud_deployment_safe_actuator_metadata_present"] is True
    assert proof_flags["ops_canary_rollout_safe_actuator_metadata_present"] is True
    assert proof_flags["ops_production_monitor_safe_actuator_metadata_present"] is True
    assert proof_flags["ops_auto_rollback_safe_actuator_metadata_present"] is True
    assert proof_flags["ops_production_deploy_safe_actuator_metadata_present"] is True
    assert proof_flags["local_canary_rollout_attempt_metadata_present"] is True
    assert proof_flags["local_deployment_command_attempt_metadata_present"] is True
    assert proof_flags["local_deployment_health_observation_metadata_present"] is True
    assert proof_flags["local_ops_canary_rollout_observation_metadata_present"] is True
    assert proof_flags["local_ops_monitor_observation_metadata_present"] is True
    assert proof_flags["local_ops_rollback_recommendation_metadata_present"] is True
    assert proof_flags["local_ops_real_readiness_preflight_metadata_present"] is True
    assert proof_flags["traffic_shift_claim_allowed"] is False
    assert proof_flags["live_customer_traffic_claim_allowed"] is False
    assert proof_flags["production_slo_claim_allowed"] is False
    assert proof_flags["external_dpi_bypass_confirmed"] is False
    assert proof_flags["external_settlement_finality_claim_allowed"] is False
    assert proof_flags["production_readiness_claim_allowed"] is False
    assert "typed redacted SafeActuator metadata" in link["boundary"]
    assert "src/deployment/canary_deployment.py:1" in link["source_refs"]
    assert "src/deployment/multi_cloud_deployment.py:1" in link["source_refs"]
    assert "scripts/canary_deployment.py:1" in link["source_refs"]
    assert "scripts/production_monitor.py:1" in link["source_refs"]
    assert "scripts/auto_rollback.py:1" in link["source_refs"]
    assert "scripts/deploy/production_deploy.py:1" in link["source_refs"]
    assert "scripts/ops/check_real_readiness.py:1" in link["source_refs"]


def test_cross_plane_pqc_ghost_safe_actuator_metadata_is_bounded_runtime_evidence():
    evidence_map = _load_map()
    links = {link["id"]: link for link in evidence_map["cross_plane_links"]}
    link = links["pqc-ghost-safe-actuator-runtime-metadata-boundary"]
    proof_flags = link["proof_flags"]

    assert proof_flags["pqc_rotator_safe_actuator_metadata_present"] is True
    assert proof_flags["ghost_l3_safe_actuator_metadata_present"] is True
    assert proof_flags["service_trace_safe_actuator_metadata_profile_present"] is True
    assert proof_flags["live_pqc_trust_finality_claim_allowed"] is False
    assert proof_flags["restored_dataplane_claim_allowed"] is False
    assert proof_flags["dataplane_delivery_claim_allowed"] is False
    assert proof_flags["customer_traffic_claim_allowed"] is False
    assert proof_flags["production_readiness_claim_allowed"] is False
    assert "typed redacted SafeActuator metadata" in link["boundary"]
    assert "src/services/pqc_rotator_service.py:1" in link["source_refs"]
    assert "src/server/ghost_server.py:1" in link["source_refs"]
    assert "scripts/ops/check_real_readiness.py:1" in link["source_refs"]


def test_cross_plane_gaps_and_next_actions_stay_focused():
    evidence_map = _load_map()

    assert evidence_map["current_gaps"]
    assert "external-dpi-proof-missing" not in {
        gap["id"] for gap in evidence_map["current_gaps"]
    }
    for gap in evidence_map["current_gaps"]:
        assert gap["gap"], gap["id"]
        assert gap["risk"], gap["id"]
        assert gap["practical_next_action"], gap["id"]
        assert gap["source_refs"], gap["id"]
        if gap.get("blocks_real_readiness") is False:
            assert gap["blocking_status"], gap["id"]

    for action in evidence_map["next_actions"]:
        assert action["action"], action["id"]
        assert action["expected_result"], action["id"]
        assert action["preferred_scope"], action["id"]
