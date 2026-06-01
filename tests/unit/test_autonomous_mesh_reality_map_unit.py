from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAP_PATH = ROOT / "docs/architecture/CURRENT_AUTONOMOUS_MESH_REALITY_MAP.json"
REQUIRED_PLANES = {
    "data_plane",
    "control_plane",
    "trust_plane",
    "evidence_plane",
    "economy_plane",
}


def _load_map() -> dict:
    return json.loads(MAP_PATH.read_text(encoding="utf-8"))


def _source_paths(value):
    if isinstance(value, dict):
        for key, nested in value.items():
            if key == "source_refs":
                for ref in nested:
                    yield str(ref).split(":", 1)[0]
            else:
                yield from _source_paths(nested)
    elif isinstance(value, list):
        for item in value:
            yield from _source_paths(item)


def test_autonomous_mesh_reality_map_has_required_planes() -> None:
    payload = _load_map()

    assert payload["schema"] == "x0tta6bl4.autonomous_mesh_reality_map.v1"
    assert payload["status"] == "working_map_not_production_completion_proof"
    assert set(payload["planes"]) == REQUIRED_PLANES
    assert set(payload["not_a_vpn_mvp"]["required_planes_present"]) == REQUIRED_PLANES


def test_autonomous_mesh_reality_map_separates_verified_and_unproven_claims() -> None:
    payload = _load_map()

    for plane_name, plane in payload["planes"].items():
        assert plane["verified_contours"], plane_name
        assert plane["unproven_or_blocked_claims"], plane_name
    assert "live customer traffic" in payload["claim_boundary"]
    assert "payment settlement finality" in payload["claim_boundary"]
    assert "production readiness" in payload["claim_boundary"]


def test_autonomous_mesh_reality_map_source_refs_exist() -> None:
    payload = _load_map()
    missing = sorted(
        {
            source_path
            for source_path in _source_paths(payload)
            if not (ROOT / source_path).exists()
        }
    )

    assert missing == []


def test_autonomous_mesh_reality_map_names_next_control_spine_improvement() -> None:
    payload = _load_map()
    next_step = payload["next_best_code_improvement"]

    assert next_step["id"] == "production_attestation_verifier_external_smoke"
    assert "scripts/ops/verify_measured_attestation_verifier_smoke.py" in next_step["description"]
    assert (
        "scripts/ops/verify_measured_attestation_verifier_smoke_artifact.py"
        in next_step["description"]
    )
    assert "scripts/ops/run_cross_plane_proof_gate.py" in next_step["description"]
    assert "--claim measured_attestation_verifier_smoke" in next_step["description"]
    assert "real non-mock SGX/SEV/Nitro verifier backend" in next_step["description"]
    assert "attestation_data" in next_step["blocked_by"]
    assert "measured_attestation hash" in next_step["blocked_by"]
    assert "stale measured_attestation now blocks" in next_step["blocked_by"]
    assert "Go agent can refresh measured-attestation" in next_step["blocked_by"]
    assert "verifier provenance is propagated" in next_step["blocked_by"]
    assert "local verifier-smoke artifact writer plus read-only artifact validator exist" in next_step["blocked_by"]
    assert "wired into the cross-plane proof gate" in next_step["blocked_by"]
    assert "running it against real non-mock SGX/SEV/Nitro infrastructure" in next_step["blocked_by"]
    assert "production trust finality" in next_step["blocked_by"]


def test_autonomous_mesh_reality_map_records_runtime_smoke_verifier() -> None:
    payload = _load_map()
    control_contours = {
        contour["id"]: contour
        for contour in payload["planes"]["control_plane"]["verified_contours"]
    }

    smoke = control_contours["maas_autonomous_mesh_runtime_smoke"]
    assert "DB-backed auth" in smoke["what_is_proven"]
    assert "synthetic self-healing revalidation" in smoke["what_is_proven"]
    assert "scripts/ops/verify_maas_autonomous_mesh_runtime_smoke.py" in (
        smoke["source_refs"]
    )


def test_autonomous_mesh_reality_map_records_maas_heal_post_action_probe_smoke() -> None:
    payload = _load_map()
    control_contours = {
        contour["id"]: contour
        for contour in payload["planes"]["control_plane"]["verified_contours"]
    }

    smoke = control_contours["maas_heal_post_action_dataplane_probe_smoke"]
    assert "synthetic stale route" in smoke["what_is_proven"]
    assert "loopback post-action dataplane probe" in smoke["what_is_proven"]
    assert "traffic/customer/production claims to remain false" in smoke["what_is_proven"]
    assert "not customer traffic" in smoke["what_is_proven"]
    assert "scripts/ops/verify_maas_heal_post_action_dataplane_probe.py" in (
        smoke["source_refs"]
    )
    assert "tests/unit/scripts/test_verify_maas_heal_post_action_dataplane_probe.py" in (
        smoke["source_refs"]
    )


def test_autonomous_mesh_reality_map_records_real_agent_smoke() -> None:
    payload = _load_map()
    control_contours = {
        contour["id"]: contour
        for contour in payload["planes"]["control_plane"]["verified_contours"]
    }

    smoke = control_contours["real_go_agent_control_loop_smoke"]
    assert "builds the Go agent binary" in smoke["what_is_proven"]
    assert "observes agent node-config fetch" in smoke["what_is_proven"]
    assert "verifies heartbeat persistence" in smoke["what_is_proven"]
    assert "fail closed" in smoke["what_is_proven"]
    assert "rotated-old credentials" in smoke["what_is_proven"]
    assert "scripts/ops/verify_maas_real_agent_control_loop.py" in (
        smoke["source_refs"]
    )


def test_autonomous_mesh_reality_map_records_ghost_l3_safe_actuator_metadata() -> None:
    payload = _load_map()
    control_contours = {
        contour["id"]: contour
        for contour in payload["planes"]["control_plane"]["verified_contours"]
    }

    contour = control_contours["ghost_l3_safe_actuator_metadata"]
    assert "typed SafeActuator metadata" in contour["what_is_proven"]
    assert "local TUN/NAT setup" in contour["what_is_proven"]
    assert "restored dataplane" in contour["what_is_proven"]
    assert "customer traffic" in contour["what_is_proven"]
    assert "production readiness" in contour["what_is_proven"]
    assert "src/server/ghost_server.py" in contour["source_refs"]
    assert "scripts/ops/check_real_readiness.py" in contour["source_refs"]
    assert "tests/unit/server/test_ghost_server_unit.py" in contour["source_refs"]


def test_autonomous_mesh_reality_map_records_ebpf_safe_actuator_metadata() -> None:
    payload = _load_map()
    control_contours = {
        contour["id"]: contour
        for contour in payload["planes"]["control_plane"]["verified_contours"]
    }

    contour = control_contours["ebpf_safe_actuator_metadata"]
    assert "typed SafeActuator metadata" in contour["what_is_proven"]
    assert "local eBPF recovery" in contour["what_is_proven"]
    assert "route convergence" in contour["what_is_proven"]
    assert "kernel forwarding correctness" in contour["what_is_proven"]
    assert "customer traffic" in contour["what_is_proven"]
    assert "production readiness" in contour["what_is_proven"]
    assert "src/self_healing/ebpf_anomaly_detector.py" in contour["source_refs"]
    assert "scripts/ops/check_real_readiness.py" in contour["source_refs"]
    assert (
        "tests/unit/self_healing/test_ebpf_anomaly_detector_unit.py"
        in contour["source_refs"]
    )


def test_autonomous_mesh_reality_map_records_maas_governance_safe_actuator_metadata() -> None:
    payload = _load_map()
    control_contours = {
        contour["id"]: contour
        for contour in payload["planes"]["control_plane"]["verified_contours"]
    }

    contour = control_contours["maas_governance_safe_actuator_metadata"]
    assert "typed SafeActuator metadata" in contour["what_is_proven"]
    assert "local MaaS governance API action" in contour["what_is_proven"]
    assert "DAO governance finality" in contour["what_is_proven"]
    assert "external settlement finality" in contour["what_is_proven"]
    assert "customer traffic" in contour["what_is_proven"]
    assert "production readiness" in contour["what_is_proven"]
    assert "src/api/maas/endpoints/governance.py" in contour["source_refs"]
    assert "scripts/ops/check_real_readiness.py" in contour["source_refs"]
    assert "tests/unit/api/test_maas_governance_spine_unit.py" in contour["source_refs"]


def test_autonomous_mesh_reality_map_records_deployment_safe_actuator_metadata() -> None:
    payload = _load_map()
    control_contours = {
        contour["id"]: contour
        for contour in payload["planes"]["control_plane"]["verified_contours"]
    }
    cross_plane_links = {link["id"]: link for link in payload["cross_plane_links"]}

    contour = control_contours["deployment_safe_actuator_metadata"]
    assert "typed SafeActuator metadata" in contour["what_is_proven"]
    assert "local gated rollout" in contour["what_is_proven"]
    assert "canary rollout script" in contour["what_is_proven"]
    assert "ops monitor" in contour["what_is_proven"]
    assert "auto-rollback" in contour["what_is_proven"]
    assert "production_deploy.py" in contour["what_is_proven"]
    assert "blocked-preflight evidence runner" in contour["what_is_proven"]
    assert "refuses live subprocess/kubectl" in contour["what_is_proven"]
    assert "build/push" in contour["what_is_proven"]
    assert "health-observation" in contour["what_is_proven"]
    assert "traffic shifting" in contour["what_is_proven"]
    assert "live customer traffic" in contour["what_is_proven"]
    assert "production SLO" in contour["what_is_proven"]
    assert "production readiness" in contour["what_is_proven"]
    assert "src/deployment/canary_deployment.py" in contour["source_refs"]
    assert "src/deployment/multi_cloud_deployment.py" in contour["source_refs"]
    assert "scripts/canary_deployment.py" in contour["source_refs"]
    assert "scripts/production_monitor.py" in contour["source_refs"]
    assert "scripts/auto_rollback.py" in contour["source_refs"]
    assert "scripts/deploy/production_deploy.py" in contour["source_refs"]
    assert "scripts/ops/run_production_deploy_blocked_preflight_evidence.py" in contour["source_refs"]
    assert "scripts/ops/check_real_readiness.py" in contour["source_refs"]
    assert "tests/unit/deployment/test_canary_deployment_unit.py" in contour["source_refs"]
    assert (
        "tests/unit/deployment/test_multi_cloud_deployment_unit.py"
        in contour["source_refs"]
    )
    assert "tests/unit/scripts/test_canary_deployment_claim_boundary.py" in contour["source_refs"]
    assert "tests/unit/scripts/test_production_monitor_claim_boundary.py" in contour["source_refs"]
    assert "tests/unit/scripts/test_auto_rollback_claim_boundary.py" in contour["source_refs"]
    assert "tests/unit/scripts/test_python_production_deploy_boundary.py" in contour["source_refs"]
    assert "tests/unit/scripts/test_run_production_deploy_blocked_preflight_evidence.py" in contour["source_refs"]

    link = cross_plane_links["deployment_runtime_to_bounded_evidence"]
    assert "bounded local deployment-control evidence" in link["verified_path"]
    assert "ops canary/monitor/rollback/deploy" in link["verified_path"]
    assert "blocked-preflight evidence runner" in link["verified_path"]
    assert "refuses live subprocess/kubectl" in link["verified_path"]
    assert "live deployment" in link["boundary"]
    assert "traffic shifting" in link["boundary"]
    assert "production SLOs" in link["boundary"]
    assert "production readiness" in link["boundary"]


def test_autonomous_mesh_reality_map_records_token_bridge_safe_actuator_metadata() -> None:
    payload = _load_map()
    economy_contours = {
        contour["id"]: contour
        for contour in payload["planes"]["economy_plane"]["verified_contours"]
    }
    cross_plane_links = {link["id"]: link for link in payload["cross_plane_links"]}

    contour = economy_contours["token_bridge_safe_actuator_metadata"]
    assert "typed SafeActuator metadata" in contour["what_is_proven"]
    assert "local policy-gated reward" in contour["what_is_proven"]
    assert "pending transaction submission" in contour["what_is_proven"]
    assert "external settlement finality" in contour["what_is_proven"]
    assert "payment-provider settlement" in contour["what_is_proven"]
    assert "bank settlement" in contour["what_is_proven"]
    assert "live token-settlement finality" in contour["what_is_proven"]
    assert "customer traffic" in contour["what_is_proven"]
    assert "revenue recognition" in contour["what_is_proven"]
    assert "production readiness" in contour["what_is_proven"]
    assert "src/dao/bridge/core.py" in contour["source_refs"]
    assert "src/dao/bridge/policy.py" in contour["source_refs"]
    assert "scripts/ops/check_real_readiness.py" in contour["source_refs"]
    assert "tests/unit/dao/test_token_bridge_spine_unit.py" in contour["source_refs"]

    link = cross_plane_links["token_bridge_runtime_to_bounded_evidence"]
    assert "bounded local economy/control evidence" in link["verified_path"]
    assert "external settlement finality" in link["boundary"]
    assert "revenue recognition" in link["boundary"]
    assert "production readiness" in link["boundary"]


def test_autonomous_mesh_reality_map_records_pqc_rotator_safe_actuator_metadata() -> None:
    payload = _load_map()
    trust_contours = {
        contour["id"]: contour
        for contour in payload["planes"]["trust_plane"]["verified_contours"]
    }

    contour = trust_contours["pqc_rotator_safe_actuator_metadata"]
    assert "typed SafeActuator metadata" in contour["what_is_proven"]
    assert "local PQC identity rotation" in contour["what_is_proven"]
    assert "live PQC trust finality" in contour["what_is_proven"]
    assert "fleet-wide key rollout" in contour["what_is_proven"]
    assert "production readiness" in contour["what_is_proven"]
    assert "src/services/pqc_rotator_service.py" in contour["source_refs"]
    assert "scripts/ops/check_real_readiness.py" in contour["source_refs"]
    assert "tests/unit/services/test_pqc_rotator_service_unit.py" in contour["source_refs"]


def test_autonomous_mesh_reality_map_records_spire_safe_actuator_metadata() -> None:
    payload = _load_map()
    trust_contours = {
        contour["id"]: contour
        for contour in payload["planes"]["trust_plane"]["verified_contours"]
    }

    contour = trust_contours["spire_safe_actuator_metadata"]
    assert "typed SafeActuator metadata" in contour["what_is_proven"]
    assert "local policy-gated SPIRE CLI" in contour["what_is_proven"]
    assert "live SPIRE mTLS" in contour["what_is_proven"]
    assert "workload SVID possession" in contour["what_is_proven"]
    assert "node attestation finality" in contour["what_is_proven"]
    assert "production readiness" in contour["what_is_proven"]
    assert "src/security/spiffe/server/client.py" in contour["source_refs"]
    assert "src/security/spiffe/agent/manager.py" in contour["source_refs"]
    assert "scripts/ops/check_real_readiness.py" in contour["source_refs"]
    assert (
        "tests/unit/security/spiffe/test_spire_server_client_spine_unit.py"
        in contour["source_refs"]
    )
    assert (
        "tests/unit/security/spiffe/test_spire_agent_manager_spine_unit.py"
        in contour["source_refs"]
    )


def test_autonomous_mesh_reality_map_records_node_runtime_credential_contract() -> None:
    payload = _load_map()
    trust_contours = {
        contour["id"]: contour
        for contour in payload["planes"]["trust_plane"]["verified_contours"]
    }

    contour = trust_contours["node_bound_runtime_credential_contract"]
    assert "stores only its hash" in contour["what_is_proven"]
    assert "expiry/rotation metadata" in contour["what_is_proven"]
    assert "Go agent uses that scoped credential" in contour["what_is_proven"]
    assert "Go client has a rotation path before expiry" in contour["what_is_proven"]
    assert "not live SPIFFE SVID possession" in contour["what_is_proven"]
    assert "src/api/maas/nodes/admission.py" in contour["source_refs"]
    assert "agent/internal/api/client.go" in contour["source_refs"]
    assert (
        "alembic/versions/f6a7b8c9d0e1_add_node_runtime_credential_rotation.py"
        in contour["source_refs"]
    )


def test_autonomous_mesh_reality_map_records_node_runtime_identity_binding_contract() -> None:
    payload = _load_map()
    trust_contours = {
        contour["id"]: contour
        for contour in payload["planes"]["trust_plane"]["verified_contours"]
    }

    contour = trust_contours["node_runtime_identity_binding_contract"]
    assert "hash-only local runtime identity proof metadata" in contour["what_is_proven"]
    assert "verified_spiffe_svid" in contour["what_is_proven"]
    assert "verified_jwt_svid" in contour["what_is_proven"]
    assert "enclave-enabled node approval" in contour["what_is_proven"]
    assert "raw report/quote/signature" in contour["what_is_proven"]
    assert "runtime-identity/refresh-measured-attestation" in contour["what_is_proven"]
    assert "runtime measured-attestation freshness enforcement" in contour["what_is_proven"]
    assert "structured verifier provenance" in contour["what_is_proven"]
    assert "production_attestation_verifier_claim_allowed" in contour["what_is_proven"]
    assert "redacted verifier provenance propagation" in contour["what_is_proven"]
    assert "local redacted verifier-smoke artifact generation" in contour["what_is_proven"]
    assert "local redacted verifier-smoke artifact generation plus validation" in contour["what_is_proven"]
    assert "cross-plane gate enforcement of the bounded artifact" in contour["what_is_proven"]
    assert "separate trust/evidence claim" in contour["what_is_proven"]
    assert "automatically refresh measured-attestation" in contour["what_is_proven"]
    assert "Go-agent measured-attestation refresh wiring" in contour["what_is_proven"]
    assert "mock attestation without explicit local opt-in fails closed" in contour["what_is_proven"]
    assert "API verifies JWT-SVID signature" in contour["what_is_proven"]
    assert "trusted mTLS proxy CIDR" in contour["what_is_proven"]
    assert "heartbeat and node-config" in contour["what_is_proven"]
    assert "local SPIFFE Workload API socket" in contour["what_is_proven"]
    assert "wrong-audience" in contour["what_is_proven"]
    assert "API-side JWT-SVID cryptographic verification" in contour["what_is_proven"]
    assert "not direct Workload API socket integration" in contour["what_is_proven"]
    assert "src/api/maas/endpoints/nodes.py" in contour["source_refs"]
    assert "src/security/tee_attestation.py" in contour["source_refs"]
    assert "agent/internal/api/client.go" in contour["source_refs"]
    assert "agent/internal/identity/jwtsvid.go" in contour["source_refs"]
    assert "agent/go.mod" in contour["source_refs"]
    assert "scripts/ops/verify_measured_attestation_verifier_smoke.py" in contour["source_refs"]
    assert (
        "scripts/ops/verify_measured_attestation_verifier_smoke_artifact.py"
        in contour["source_refs"]
    )
    assert "scripts/ops/run_cross_plane_proof_gate.py" in contour["source_refs"]
    assert "tests/unit/scripts/test_run_cross_plane_proof_gate.py" in contour["source_refs"]
    assert "scripts/ops/check_real_readiness.py" in contour["source_refs"]
    assert (
        "tests/unit/scripts/test_verify_measured_attestation_verifier_smoke.py"
        in contour["source_refs"]
    )
    assert "tests/unit/security/test_tee_attestation_unit.py" in contour["source_refs"]
    assert (
        "tests/unit/scripts/test_verify_measured_attestation_verifier_smoke_artifact.py"
        in contour["source_refs"]
    )
    assert (
        "alembic/versions/a8b9c0d1e2f3_add_node_runtime_identity_binding.py"
        in contour["source_refs"]
    )
