from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAP_PATH = ROOT / "docs/architecture/CURRENT_EVIDENCE_RUNTIME_BRIDGE_MAP.json"
EVIDENCE_ROOT = ROOT / "docs/verification"
INDEXABLE_SUFFIXES = {".md", ".json", ".jsonl"}


def _load_map() -> dict:
    return json.loads(MAP_PATH.read_text(encoding="utf-8"))


def _source_refs(value) -> list[str]:
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


def _indexable_evidence_files() -> list[Path]:
    return sorted(
        path
        for path in EVIDENCE_ROOT.rglob("*")
        if path.is_file() and path.suffix.lower() in INDEXABLE_SUFFIXES
    )


def test_evidence_runtime_bridge_map_matches_current_verification_tree():
    bridge_map = _load_map()
    files = _indexable_evidence_files()
    latest = [path for path in files if "_LATEST" in path.name]

    assert bridge_map["evidence_source"]["path"] == "docs/verification"
    assert set(bridge_map["evidence_source"]["indexable_suffixes"]) == INDEXABLE_SUFFIXES
    assert bridge_map["evidence_source"]["current_indexable_files"] == len(files)
    assert bridge_map["evidence_source"]["current_latest_alias_files"] == len(latest)
    assert bridge_map["evidence_source"]["by_suffix"] == dict(
        Counter(path.suffix.lower() for path in files)
    )
    assert bridge_map["evidence_source"]["latest_by_suffix"] == dict(
        Counter(path.suffix.lower() for path in latest)
    )
    external_dpi = bridge_map["evidence_source"]["external_dpi_intake_boundary"]
    candidate = EVIDENCE_ROOT / "incoming" / "dpi_lab.json"
    candidate_payload = json.loads(candidate.read_text(encoding="utf-8"))
    assert external_dpi["candidate_path"] == "docs/verification/incoming/dpi_lab.json"
    assert external_dpi["candidate_exists"] == candidate.exists()
    assert external_dpi["candidate_is_file"] == candidate.is_file()
    assert external_dpi["current_mode"] == candidate_payload["mode"]
    assert external_dpi["current_status"] == candidate_payload["status"]
    assert external_dpi["current_claim_status"] == "external_dpi_gap_record"
    assert external_dpi["candidate_is_proof"] is False
    assert external_dpi["proof_gate_dpi_bypass_claim_allowed"] is False
    assert external_dpi["production_readiness_claim_allowed"] is False


def test_evidence_runtime_bridge_source_refs_resolve_to_existing_files_and_lines():
    bridge_map = _load_map()
    source_refs = _source_refs(bridge_map)

    for source_ref in source_refs:
        path_text, line_text = source_ref.rsplit(":", 1)
        path = ROOT / path_text
        assert path.exists(), source_ref
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        assert 1 <= int(line_text) <= line_count, source_ref


def test_evidence_runtime_bridge_claims_match_code_markers():
    bridge_map = _load_map()
    endpoint_source = (ROOT / "src/api/ledger_endpoints.py").read_text(encoding="utf-8")
    rag_source = (ROOT / "src/ledger/rag_search.py").read_text(encoding="utf-8")
    smoke_source = (
        ROOT / "scripts/ops/smoke_ledger_event_trace_citation.py"
    ).read_text(encoding="utf-8")

    assert "include_verification" in endpoint_source
    assert "@router.post(\"/evidence/index\")" in endpoint_source
    assert "@router.get(\"/evidence/status\")" in endpoint_source
    assert "@router.post(\"/event-traces/index\")" in endpoint_source
    assert "@router.get(\"/event-traces/status\")" in endpoint_source
    assert "service_event_trace_history" in endpoint_source
    assert "event_id" in endpoint_source
    assert "source_agent" in endpoint_source
    assert "layer" in endpoint_source
    assert "_search_response_from_result" in endpoint_source
    assert "_extract_citations" in endpoint_source
    assert "response_metadata[\"citations\"]" in endpoint_source
    assert "external_dpi_intake_claim_gate_summary" in endpoint_source
    assert "external_evidence_gap_record_not_proof" in endpoint_source
    assert "external_dpi_proof_gate_not_allowed" in endpoint_source

    assert "VERIFICATION_ROOT" in rag_source
    assert "VERIFICATION_SUFFIXES" in rag_source
    assert "index_verification_evidence" in rag_source
    assert "verification_evidence_status" in rag_source
    assert "source_class" in rag_source
    assert "verification_evidence" in rag_source
    assert "CLAIM_STATUS_EXTERNAL_DPI_GAP_RECORD" in rag_source
    assert "EXTERNAL_DPI_INTAKE_RELATIVE_PATH" in rag_source
    assert "_external_dpi_intake_claim_gate_summary" in rag_source
    assert "external_dpi_intake_claim_gate_summary" in rag_source
    assert '"proof_gate_dpi_bypass_claim_allowed": False' in rag_source
    assert "EVENT_TRACE_SOURCE_CLASS" in rag_source
    assert "index_event_traces" in rag_source
    assert "event_trace_status" in rag_source
    assert "event_trace" in rag_source
    assert "redacted" in rag_source

    endpoint_paths = {
        (endpoint["method"], endpoint["path"])
        for endpoint in bridge_map["runtime_surface"]["endpoints"]
    }
    assert ("POST", "/api/v1/ledger/evidence/index") in endpoint_paths
    assert ("GET", "/api/v1/ledger/evidence/status") in endpoint_paths
    assert ("POST", "/api/v1/ledger/event-traces/index") in endpoint_paths
    assert ("GET", "/api/v1/ledger/event-traces/status") in endpoint_paths
    assert bridge_map["operator_citation_flow"]["response_field"] == "metadata.citations"
    assert "external_dpi_intake_claim_gate_summary" in bridge_map[
        "operator_citation_flow"
    ]["high_risk_boundary_fields"]
    assert "external_evidence_gap_record" in bridge_map["operator_citation_flow"][
        "high_risk_boundary_fields"
    ]
    assert bridge_map["event_trace_source"]["source_class"] == "event_trace"
    assert bridge_map["rag_bridge"]["metadata_contract"]["external_dpi_gap_record"][
        "claim_status"
    ] == "external_dpi_gap_record"
    assert bridge_map["rag_bridge"]["metadata_contract"]["external_dpi_gap_record"][
        "proof_gate_dpi_bypass_claim_allowed"
    ] is False
    assert bridge_map["operator_smoke"]["command"] == (
        "python3 scripts/ops/smoke_ledger_event_trace_citation.py --json"
    )
    assert bridge_map["operator_smoke"]["scenario"] == (
        "eventbus_multi_layer_trace_to_ledger_rag_citation"
    )
    covered_services = {
        item["service_name"]: item["layer"]
        for item in bridge_map["operator_smoke"]["covered_services"]
    }
    assert covered_services["swarm-pbft"] == "swarm_consensus_to_control_plane"
    assert covered_services["maas-settlement"] == "commerce_settlement_to_events"
    assert covered_services["maas-marketplace"] == "api_to_commerce"
    assert covered_services["maas-governance"] == "api_to_control_plane"
    assert covered_services["maas-billing"] == "billing_webhook_to_commerce_bridge"
    assert covered_services["dao-executor"] == "dao_to_control_plane"
    assert (
        covered_services["recovery-action-executor"]
        == "self_healing_to_control_plane"
    )
    assert covered_services["mesh-vpn-bridge"] == "network_to_rewards"
    assert covered_services["share-to-earn"] == "network_usage_to_rewards"
    assert covered_services["mptcp-manager"] == "network_to_control_plane"
    assert (
        covered_services["spire-server-client"]
        == "security_identity_to_control_plane"
    )
    assert covered_services["pqc-rotator"] == "security_service_to_control_plane"
    assert (
        covered_services["pqc-zero-trust-executor"]
        == "self_healing_pqc_identity"
    )
    assert "/api/v1/ledger/event-traces/index" in smoke_source
    assert "/api/v1/ledger/search" in smoke_source
    assert "publish_marketplace_escrow_event" in smoke_source
    assert "MARKETPLACE_API_SERVICE_NAME" in smoke_source
    assert "marketplace_api_event_id_matches" in smoke_source
    assert "execute_maas_governance_action" in smoke_source
    assert "maas_governance_event_id_matches" in smoke_source
    assert "maas_billing_api.stripe_webhook" in smoke_source
    assert "maas_billing_event_id_matches" in smoke_source
    assert "TokenRewards" in smoke_source
    assert "reward_relay" in smoke_source
    assert "mesh_reward_event_id_matches" in smoke_source
    assert "publish_share_to_earn_reward_event" in smoke_source
    assert "share_to_earn_event_id_matches" in smoke_source
    assert "MPTCPManager.enable_mptcp" in smoke_source
    assert "mptcp_event_id_matches" in smoke_source
    assert "DAOExecutor.__new__" in smoke_source
    assert "RecoveryActionExecutor.__new__" in smoke_source
    assert "SPIREServerClient" in smoke_source
    assert "create_entry" in smoke_source
    assert "spire_server_event_id_matches" in smoke_source
    assert "PQCRotatorService" in smoke_source
    assert "rotate_once" in smoke_source
    assert "pqc_rotator_event_id_matches" in smoke_source
    assert "PQCZeroTrustExecutor" in smoke_source
    assert "pqc-zero-trust-healer" in smoke_source
    assert "pqc_healer_event_id_matches" in smoke_source
    assert "pqc_healer_service_name_matches" in smoke_source
    assert "recovery_event_id_matches" in smoke_source
    assert "dao_event_id_matches" in smoke_source
    assert "marketplace_event_id_matches" in smoke_source
    assert "swarm_event_id_matches" in smoke_source
    assert "secret_values_absent" in smoke_source
