from __future__ import annotations

import importlib.util
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from scripts.ops.run_cross_plane_proof_gate import (
    DEFAULT_CLAIMS,
    build_report,
    dataplane_delivery_artifact_evidence,
    main,
    measured_attestation_verifier_smoke_artifact_evidence,
)


ROOT = Path(__file__).resolve().parents[3]
COLLECTOR = ROOT / "scripts/ops/collect_external_dpi_proxy_reachability_evidence.py"
IMPORTER = ROOT / "scripts/ops/import_ghost_pulse_external_evidence.py"
CONTRACT = ROOT / "docs/verification/EXTERNAL_DPI_PROXY_REACHABILITY_EVIDENCE_SCHEMA.json"
SETTLEMENT_TX_HASH = "0x" + "a" * 64
SETTLEMENT_BLOCK_HASH = "0x" + "b" * 64
SETTLEMENT_FROM = "0x" + "1" * 40
SETTLEMENT_TO = "0x" + "2" * 40


def _load_script(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _write_contract(root: Path) -> None:
    path = root / "docs/verification/EXTERNAL_DPI_PROXY_REACHABILITY_EVIDENCE_SCHEMA.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(CONTRACT.read_bytes())


def _collector_args(root: Path):
    collector = _load_script(COLLECTOR, "collect_external_dpi_proxy_reachability_for_cross_plane_args")
    return collector.parse_args(
        [
            "--root",
            str(root),
            "--target-url",
            "https://blocked.example/probe",
            "--treatment-proxy",
            "socks5h://127.0.0.1:19080",
            "--attempts",
            "2",
            "--timeout-s",
            "1",
            "--operator-or-lab-id",
            "authorized-operator",
            "--authorization-scope-id",
            "ticket-123",
            "--scope-summary",
            "authorized bounded lab run",
            "--network-region-bucket",
            "coarse-region",
            "--network-type",
            "authorized-lab-network",
            "--isp-or-lab-profile",
            "lab-profile-private",
            "--egress-location-bucket",
            "coarse-egress",
            "--policy-context",
            "authorized external DPI lab",
            "--allow-external-probes",
        ]
    )


def _write_collected_dpi_lab_candidate(root: Path) -> tuple[object, dict, Path]:
    collector = _load_script(COLLECTOR, "collect_external_dpi_proxy_reachability_for_cross_plane")
    importer = _load_script(IMPORTER, "import_ghost_pulse_external_evidence_for_cross_plane")
    _write_contract(root)

    def fake_runner(command: Sequence[str], timeout: int) -> subprocess.CompletedProcess[str]:
        if "--proxy" in command:
            return subprocess.CompletedProcess(command, 0, stdout="200 0.120 512", stderr="")
        return subprocess.CompletedProcess(command, 0, stdout="451 0.100 64", stderr="")

    collector.collect(_collector_args(root), runner=fake_runner)
    candidate = root / "docs/verification/incoming/dpi_lab.json"
    proof = importer.load_proof_gate(root)
    requirement = importer.requirement_by_claim(proof)["dpi_lab"]
    return importer, requirement, candidate


def _write_gap_audit(root: Path, claim_id: str = "dpi_lab") -> Path:
    scaffold = _load_script(
        ROOT / "scripts/ops/scaffold_ghost_pulse_external_evidence_gaps.py",
        f"scaffold_ghost_pulse_external_evidence_gaps_for_cross_plane_{claim_id}",
    )
    audit = _load_script(
        ROOT / "scripts/ops/audit_ghost_pulse_external_evidence_gaps.py",
        f"audit_ghost_pulse_external_evidence_gaps_for_cross_plane_{claim_id}",
    )
    scaffold.scaffold(root, [claim_id])
    report = audit.build_report(root, [claim_id])
    paths = audit.write_report_outputs(
        root,
        report,
        root / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_GAP_AUDIT_LATEST.json",
        root / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_GAP_AUDIT_LATEST.md",
    )
    return paths["latest_json"]


def _write_fresh_import_preflight_reports(root: Path, claim_id: str = "dpi_lab") -> None:
    audit_path = _write_gap_audit(root, claim_id)
    scaffold = _load_script(
        ROOT / "scripts/ops/scaffold_ghost_pulse_external_evidence_gaps.py",
        f"scaffold_ghost_pulse_external_evidence_examples_for_cross_plane_{claim_id}",
    )
    replacement = _load_script(
        ROOT / "scripts/ops/verify_ghost_pulse_replacement_candidates.py",
        f"verify_ghost_pulse_replacement_candidates_for_cross_plane_{claim_id}",
    )
    intake = _load_script(
        ROOT / "scripts/ops/verify_ghost_pulse_external_evidence_intake.py",
        f"verify_ghost_pulse_external_evidence_intake_for_cross_plane_{claim_id}",
    )
    audit_payload = json.loads(audit_path.read_text(encoding="utf-8"))
    scaffold.write_incoming_examples(root, audit_payload.get("replacement_required", [claim_id]))
    replacement_report = replacement.build_report(root, audit_path)
    replacement_paths = replacement.write_report_outputs(
        root,
        replacement_report,
        root / "docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json",
        root / "docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.md",
    )
    intake_report = intake.build_report(root, replacement_paths["latest_json"])
    intake.write_report_outputs(
        root,
        intake_report,
        root / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.json",
        root / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.md",
    )


def _write_rejected_dpi_lab_gap_candidate_reports(root: Path) -> None:
    claim_id = "dpi_lab"
    audit_path = _write_gap_audit(root, claim_id)
    scaffold = _load_script(
        ROOT / "scripts/ops/scaffold_ghost_pulse_external_evidence_gaps.py",
        "scaffold_ghost_pulse_rejected_dpi_lab_gap_candidate_for_cross_plane",
    )
    replacement = _load_script(
        ROOT / "scripts/ops/verify_ghost_pulse_replacement_candidates.py",
        "verify_ghost_pulse_rejected_dpi_lab_gap_candidate_for_cross_plane",
    )
    intake = _load_script(
        ROOT / "scripts/ops/verify_ghost_pulse_external_evidence_intake.py",
        "verify_ghost_pulse_rejected_dpi_lab_gap_candidate_intake_for_cross_plane",
    )
    scaffold.write_incoming_examples(root, [claim_id])
    scaffold.write_incoming_gap_candidates(root, [claim_id])
    replacement_report = replacement.build_report(root, audit_path)
    replacement_paths = replacement.write_report_outputs(
        root,
        replacement_report,
        root / "docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json",
        root / "docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.md",
    )
    intake_report = intake.build_report(root, replacement_paths["latest_json"])
    intake.write_report_outputs(
        root,
        intake_report,
        root / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.json",
        root / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.md",
    )


def _write_imported_dpi_lab_artifact(root: Path) -> None:
    importer, requirement, candidate = _write_collected_dpi_lab_candidate(root)
    _write_fresh_import_preflight_reports(root)
    report = importer.build_report(root, "dpi_lab", candidate, write_requested=True)
    assert report["decision"] == importer.DECISION_READY
    importer.write_import_outputs(root, report, candidate, root / requirement["path"])


def _write_verified_dpi_lab_latest_without_import_trace(root: Path) -> None:
    _, requirement, candidate = _write_collected_dpi_lab_candidate(root)
    destination = root / requirement["path"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(candidate.read_bytes())


def _write_stub_production_readiness_proof(root: Path, *, verified: bool = True) -> None:
    script = root / "scripts/ops/run_ghost_pulse_proof_gate.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    status = "VERIFIED" if verified else "INVALID"
    script.write_text(
        f'''
from pathlib import Path

def requirement_by_claim():
    return {{
        "production_readiness": {{
            "claim_id": "production_readiness",
            "title": "Production readiness approval and rollback evidence",
            "path": "docs/verification/GHOST_PULSE_PRODUCTION_READINESS_LATEST.json",
        }}
    }}

def validate_external_evidence(root: Path, requirement):
    path = root / requirement["path"]
    return {{
        "claim_id": requirement["claim_id"],
        "title": requirement["title"],
        "status": "{status}" if path.is_file() else "MISSING",
        "evidence": requirement["path"],
        "errors": [] if path.is_file() and "{status}" == "VERIFIED" else ["not verified"],
        "sha256": "0" * 64 if path.is_file() else None,
    }}
''',
        encoding="utf-8",
    )
    artifact = root / "docs/verification/GHOST_PULSE_PRODUCTION_READINESS_LATEST.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        json.dumps(
            {
                "schema": "x0tta6bl4.ghost_pulse.claim_evidence.v1",
                "claim_id": "production_readiness",
                "status": status,
            }
        ),
        encoding="utf-8",
    )


def _write_valid_external_settlement_artifacts(root: Path) -> None:
    from src.integration import external_settlement as settlement

    evidence_path = root / settlement.DEFAULT_EVIDENCE_PATH
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "VERIFIED HERE",
        "evidence_status": "VERIFIED HERE",
        "schema_version": "x0tta6bl4-x0t-external-settlement-submit-evidence-v1",
        "collected_at": "2026-05-31T00:00:00Z",
        "collected_by": "authorized-settlement-lab",
        "settlement_submitted": True,
        "destination_chain": "base-sepolia",
        "destination_chain_id": 84532,
        "observed_chain_id": 84532,
        "settlement_id": "settlement-2026-05-31-001",
        "token_symbol": "X0T",
        "transaction_receipt_status": "mined_success",
        "block_number": 123456,
        "block_hash": SETTLEMENT_BLOCK_HASH,
        "from_address": SETTLEMENT_FROM,
        "to_address": SETTLEMENT_TO,
        "transaction_hash": SETTLEMENT_TX_HASH,
        "explorer_url": f"https://sepolia.basescan.org/tx/{SETTLEMENT_TX_HASH}",
        "source_commands": [
            (
                "python3 -m src.integration.external_settlement --root . --capture-from-rpc "
                f"--transaction-hash {SETTLEMENT_TX_HASH} --destination-chain base-sepolia "
                "--settlement-id settlement-2026-05-31-001 --rpc-url $X0T_BASE_RPC_URL "
                f"--evidence {settlement.DEFAULT_EVIDENCE_PATH} --write-evidence"
            ),
            (
                "python3 -m src.integration.external_settlement --root . "
                f"--evidence {settlement.DEFAULT_EVIDENCE_PATH} "
                "--rpc-url $X0T_BASE_RPC_URL --require-ready"
            ),
        ],
        "source_rpc_methods": [
            "eth_chainId",
            "eth_getTransactionReceipt",
            "eth_getTransactionByHash",
        ],
        "template_only": False,
        "submits_transaction": False,
        "mutates_chain": False,
        "mutates_files": True,
        "mutates_nl": False,
        "mutates_spb": False,
        "mutates_vpn_runtime": False,
        "claim_boundary": "Retained external X0T settlement receipt captured from read-only Base RPC.",
    }
    payload["packet_hash"] = settlement._packet_hash(payload)
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    evidence = settlement.validate_evidence_file(evidence_path, settlement.DEFAULT_EVIDENCE_PATH)
    evidence_report = evidence.report()
    rpc_report = {
        "schema_version": "x0tta6bl4-x0t-external-settlement-live-rpc-gate-v2",
        "generated_at": "2026-05-31T00:00:00Z",
        "status": "VERIFIED HERE",
        "ok": True,
        "live_rpc_result": {
            "ready": True,
            "destination_chain": "base-sepolia",
            "expected_chain_id": 84532,
            "observed_chain_id": 84532,
            "transaction_hash": SETTLEMENT_TX_HASH,
            "receipt_block_number": 123456,
            "transaction_block_number": 123456,
            "receipt_block_hash": SETTLEMENT_BLOCK_HASH,
            "errors": [],
        },
        "summary": {
            "evidence_file_found": True,
            "retained_evidence_invalid": False,
            "retained_evidence_ready": True,
            "rpc_url_available": True,
            "live_rpc_checked": True,
            "fake_external_settlement_prevention_enforced": True,
            "x0t_external_settlement_live_rpc_ready": True,
        },
        "x0t_external_settlement_live_rpc_decision": "READY",
    }
    blocker_report = settlement.build_blocker_report(evidence_report, rpc_report)

    for relative, report in (
        (settlement.DEFAULT_EVIDENCE_REPORT, evidence_report),
        (settlement.DEFAULT_RPC_REPORT, rpc_report),
        (settlement.DEFAULT_BLOCKER_REPORT, blocker_report),
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report), encoding="utf-8")


def _write_valid_dataplane_delivery_event(
    root: Path,
    *,
    traffic_delivery_allowed: bool = False,
) -> None:
    event_log = root / ".agent_coordination/events.log"
    event_log.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "event_id": "dataplane-event-1",
        "event_type": "pipeline.stage_end",
        "source_agent": "mesh-action-enforcer",
        "timestamp": "2026-05-31T00:00:00",
        "target_agents": None,
        "priority": 6,
        "requires_ack": False,
        "acked_by": [],
        "data": {
            "dataplane_confirmed": True,
            "post_action_dataplane_revalidated": True,
            "restored_dataplane_claim_allowed": True,
            "traffic_delivery_claim_allowed": traffic_delivery_allowed,
            "traffic_delivery_confirmed": traffic_delivery_allowed,
            "customer_traffic_claim_allowed": False,
            "production_readiness_claim_allowed": False,
            "post_action_dataplane_revalidation": {
                "status": "success",
                "reason": "bounded_dataplane_probe_succeeded",
                "probe_attempted": True,
                "dataplane_confirmed": True,
                "post_action_dataplane_revalidated": True,
                "restored_dataplane_claim_allowed": True,
                "traffic_delivery_claim_allowed": traffic_delivery_allowed,
                "traffic_delivery_confirmed": traffic_delivery_allowed,
                "redacted": True,
                "claim_boundary": "Bounded dataplane probe evidence only.",
                "claim_gate": {
                    "restored_dataplane_claim_allowed": True,
                    "traffic_delivery_claim_allowed": traffic_delivery_allowed,
                    "traffic_delivery_confirmed": traffic_delivery_allowed,
                    "blockers": [],
                    "observed_evidence": {
                        "probe_attempted": True,
                        "dataplane_confirmed": True,
                    },
                    "claim_boundary": "Restored-dataplane gate metadata only.",
                    "redacted": True,
                },
                "evidence": {
                    "source_agents": ["real-network-adapter"],
                    "event_ids": ["probe-event-1"],
                    "events_total": 1,
                    "event_ids_count": 1,
                    "claim_boundaries": ["Bounded dataplane probe evidence only."],
                    "claim_boundaries_total": 1,
                    "redacted": True,
                },
            },
        },
    }
    event_log.write_text(json.dumps(event) + "\n", encoding="utf-8")


def _write_valid_mesh_recovery_lifecycle_event(root: Path) -> None:
    event_log = root / ".agent_coordination/events.log"
    event_log.parent.mkdir(parents=True, exist_ok=True)
    node_id_hash = "a" * 64
    event = {
        "event_id": "mesh-recovery-lifecycle-event-1",
        "event_type": "pipeline.stage_end",
        "source_agent": "mesh-recovery-orchestrator",
        "timestamp": "2026-05-31T00:00:00",
        "target_agents": None,
        "priority": 6,
        "requires_ack": False,
        "acked_by": [],
        "data": {
            "schema": "mesh_node_degradation_recovery.eventbus.v1",
            "recovery_evidence_schema": "mesh_node_degradation_recovery.v1",
            "component": "src.mesh.recovery_orchestrator",
            "operation": "mesh_node_degradation_recovery",
            "stage": "recovery_revalidated",
            "status": "success",
            "success": True,
            "observed_state": True,
            "policy_allowed": True,
            "cooldown_active": False,
            "safe_mode_required": False,
            "execution_limit_checked": "1_attempt_per_10_minutes",
            "duration_ms": 0,
            "return_code": 0,
            "returncode": 0,
            "action_error": False,
            "action_error_type": None,
            "action_error_redacted": True,
            "escalation_required": False,
            "node_id_hash": node_id_hash,
            "identity": {"node_id_hash": node_id_hash},
            "identity_fields_present": {
                "node_id_hash": True,
                "spiffe_id": False,
                "did": False,
                "wallet_address": False,
            },
            "claim_gate": {
                "local_peer_visible": "PROVEN",
                "yggdrasil_status_improved": "PROVEN",
                "packet_loss_metric_decreased": "PROVEN",
                "customer_traffic_restored": "UNPROVEN_AWAITING_DATAPLANE_PROOF",
            },
            "raw_values_redacted": True,
            "raw_identifiers_redacted": True,
            "payloads_redacted": True,
            "production_readiness_claim_allowed": False,
            "customer_traffic_claim_allowed": False,
            "settlement_finality_claim_allowed": False,
            "claim_boundary": "Mesh recovery lifecycle evidence only.",
        },
    }
    with event_log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")


def test_gate_blocks_mesh_recovery_lifecycle_when_event_overpromotes_traffic_delivery(
    tmp_path: Path,
) -> None:
    _write_valid_mesh_recovery_lifecycle_event(tmp_path)
    event_log = tmp_path / ".agent_coordination/events.log"
    event = json.loads(event_log.read_text(encoding="utf-8"))
    event["data"]["post_action_dataplane_revalidation"] = {
        "traffic_delivery_claim_allowed": True,
        "claim_gate": {
            "traffic_delivery_confirmed": True,
        },
    }
    event_log.write_text(json.dumps(event) + "\n", encoding="utf-8")

    report = build_report(tmp_path, claims=("mesh_recovery_lifecycle",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    [recovery] = report["claim_results"]
    assert "mesh_recovery_lifecycle_eventbus_artifact_not_verified" in recovery[
        "blockers"
    ]
    artifact = recovery["required_artifact_evidence"]
    assert artifact["valid"] is False
    assert "mesh_recovery_overpromotes_traffic_delivery" in artifact[
        "candidate_blockers"
    ]


def _write_valid_trust_finality_event(root: Path) -> None:
    event_log = root / ".agent_coordination/events.log"
    event_log.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "event_id": "trust-finality-event-1",
        "event_type": "pipeline.stage_end",
        "source_agent": "spiffe-workload-api",
        "timestamp": "2026-05-31T00:00:00",
        "target_agents": None,
        "priority": 6,
        "requires_ack": False,
        "acked_by": [],
        "data": {
            "component": "src.security.spiffe.workload.api_client",
            "operation": "validate_svid",
            "live_spiffe_svid_confirmed": True,
            "raw_identity_values_redacted": True,
            "payloads_redacted": True,
            "source_artifacts_count": 1,
            "source_artifacts": [
                {
                    "role": "redacted_local_spiffe_svid_probe_report",
                    "sha256": "a" * 64,
                    "path_redacted": True,
                    "redacted": True,
                }
            ],
            "claim_boundary": (
                "Live SPIFFE SVID validation evidence only; not dataplane, "
                "settlement, customer traffic, or production readiness proof."
            ),
            "claim_gate": {
                "schema": "x0tta6bl4.trust_finality.claim_gate.v1",
                "live_spiffe_svid_claim_allowed": True,
                "did_ownership_claim_allowed": False,
                "wallet_control_claim_allowed": False,
                "chain_identity_finality_claim_allowed": False,
                "dataplane_delivery_claim_allowed": False,
                "production_readiness_claim_allowed": False,
                "raw_identity_values_redacted": True,
                "payloads_redacted": True,
                "claim_boundary": "Bounded trust-finality gate metadata only.",
                "redacted": True,
            },
        },
    }
    with event_log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")


def _write_valid_local_service_identity_status_event(root: Path) -> None:
    event_log = root / ".agent_coordination/events.log"
    event_log.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "event_id": "local-service-identity-status-event-1",
        "event_type": "pipeline.stage_end",
        "source_agent": "service-identity-status",
        "timestamp": "2026-05-31T00:00:00",
        "target_agents": None,
        "priority": 5,
        "requires_ack": False,
        "acked_by": [],
        "data": {
            "schema": "x0tta6bl4.local_service_identity_status.eventbus_evidence.v1",
            "component": "local_service_identity_status_collector",
            "operation": "service_identity_status_inventory",
            "status": "success",
            "services_total": 3,
            "services_with_any_identity": 1,
            "services_complete": 0,
            "configured_field_counts": {
                "spiffe_id": 1,
                "did": 0,
                "wallet_address": 0,
            },
            "raw_identity_values_redacted": True,
            "raw_identifiers_redacted": True,
            "payloads_redacted": True,
            "live_spiffe_svid_confirmed": False,
            "did_ownership_confirmed": False,
            "wallet_control_confirmed": False,
            "chain_identity_finality_confirmed": False,
            "production_readiness_claim_allowed": False,
            "claim_gate": {
                "schema": "x0tta6bl4.local_service_identity_status.claim_gate.v1",
                "local_service_identity_status_claim_allowed": True,
                "raw_identity_values_redacted": True,
                "payloads_redacted": True,
                "live_spiffe_svid_claim_allowed": False,
                "did_ownership_claim_allowed": False,
                "wallet_control_claim_allowed": False,
                "chain_identity_finality_claim_allowed": False,
                "production_readiness_claim_allowed": False,
                "claim_boundary": "Local service identity status only.",
                "redacted": True,
            },
            "claim_boundary": "Local service identity status only.",
            "redacted": True,
        },
    }
    with event_log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _artifact_content_sha256(payload: dict) -> str:
    normalized = json.loads(_canonical_json(payload))
    normalized["artifact_identity"]["artifact_sha256"] = "0" * 64
    return _sha256_text(_canonical_json(normalized))


def _write_valid_measured_attestation_smoke_artifact(root: Path) -> None:
    path = root / "docs/verification/incoming/measured_attestation_verifier_smoke.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "x0tta6bl4.measured_attestation_verifier_smoke.v1",
        "decision": "MEASURED_ATTESTATION_VERIFIER_SMOKE_READY",
        "ready": True,
        "captured_at_utc": "2026-05-31T00:00:00Z",
        "provider": "sgx",
        "artifact_identity": {
            "claim_id": "measured_attestation_verifier_smoke",
            "operator_or_lab_hash": "a" * 64,
            "authorization_scope_hash": "b" * 64,
            "environment_bucket": "lab-sgx-node",
            "hardware_profile_bucket": "sgx-dcap",
            "policy_context_hash": "c" * 64,
            "artifact_sha256": "0" * 64,
        },
        "input_redaction": {
            "raw_attestation_material_retained": False,
            "raw_file_paths_redacted": True,
            "report_data": {
                "present": True,
                "size_bytes": 17,
                "sha256": "d" * 64,
                "raw_value_redacted": True,
            },
            "quote": {
                "present": True,
                "size_bytes": 19,
                "sha256": "e" * 64,
                "raw_value_redacted": True,
            },
            "signature": {
                "present": True,
                "size_bytes": 23,
                "sha256": "f" * 64,
                "raw_value_redacted": True,
            },
        },
        "verifier": {
            "backend": "sgx_command",
            "verified": True,
            "reason": "verified_by_non_mock_local_command",
            "production_verifier_claim_allowed": True,
            "command_configured": True,
            "provenance": {
                "raw_attestation_redacted": True,
                "verifier_id": "dcap-local",
                "policy_id": "sgx-prod-policy",
            },
        },
        "measurements": {
            "non_mock_provider": True,
            "hardware_quote_present": True,
            "signature_present": True,
            "attestation_verified": True,
            "verifier_provenance_recorded": True,
            "production_verifier_claim_allowed": True,
            "production_trust_finality": False,
            "production_ready": False,
        },
        "result_summary": {
            "production_attestation_verifier_smoke_ready": True,
            "confidence_bucket": "bounded-single-verifier-run",
            "production_trust_finality": False,
            "production_ready": False,
        },
        "claim_boundary": {
            "summary": "Bounded local measured-attestation verifier smoke only.",
            "not_proven": [
                "production trust finality",
                "fleet-wide hardware coverage",
                "live customer traffic",
                "payment or token settlement finality",
                "PQC identity finality",
                "production readiness",
            ],
            "proof_claims": {
                "non_mock_attestation_verified": True,
                "verifier_provenance_recorded": True,
                "production_attestation_verifier_claim_allowed": True,
                "production_trust_finality": False,
                "production_ready": False,
            },
        },
    }
    payload["artifact_identity"]["artifact_sha256"] = _artifact_content_sha256(payload)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_valid_customer_traffic_event(root: Path) -> None:
    event_log = root / ".agent_coordination/events.log"
    event_log.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "event_id": "customer-traffic-event-1",
        "event_type": "pipeline.stage_end",
        "source_agent": "customer-traffic-probe",
        "timestamp": "2026-05-31T00:00:00",
        "target_agents": None,
        "priority": 6,
        "requires_ack": False,
        "acked_by": [],
        "data": {
            "component": "scripts.ops.customer_traffic_probe",
            "operation": "end_to_end_customer_path_probe",
            "environment": "production",
            "production_customer_traffic_confirmed": True,
            "raw_identifiers_redacted": True,
            "payloads_redacted": True,
            "source_artifacts_count": 1,
            "source_artifacts": [
                {
                    "role": "redacted_end_to_end_customer_path_probe_report",
                    "sha256": "b" * 64,
                    "path_redacted": True,
                    "redacted": True,
                }
            ],
            "claim_boundary": (
                "End-to-end customer traffic evidence only; not production "
                "readiness, settlement finality, or trust finality proof."
            ),
            "customer_traffic_claim_gate": {
                "schema": "x0tta6bl4.customer_traffic.claim_gate.v1",
                "customer_traffic_claim_allowed": True,
                "production_customer_traffic_confirmed": True,
                "production_readiness_claim_allowed": False,
                "external_settlement_finality_claim_allowed": False,
                "raw_identifiers_redacted": True,
                "payloads_redacted": True,
                "claim_boundary": "Bounded customer traffic gate metadata only.",
                "redacted": True,
            },
        },
    }
    with event_log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")


def _write_valid_economy_boundary_event(root: Path) -> None:
    event_log = root / ".agent_coordination/events.log"
    event_log.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "event_id": "economy-boundary-event-1",
        "event_type": "marketplace.escrow.released",
        "source_agent": "maas-marketplace",
        "timestamp": "2026-05-31T00:00:00",
        "target_agents": None,
        "priority": 6,
        "requires_ack": False,
        "acked_by": [],
        "data": {
            "claim_boundary": "Local economy lifecycle evidence only.",
            "settlement_evidence": {
                "decision_basis": "local_escrow_lifecycle",
                "source_quality": "local_db",
                "settlement_action": "escrow_release_local",
                "dataplane_confirmed": False,
                "live_provider_settlement_confirmed": False,
                "bank_settlement_confirmed": False,
                "chain_finality_confirmed": False,
                "claim_gate": {
                    "decision": "LOCAL_ONLY",
                    "local_escrow_lifecycle_claim_allowed": True,
                    "traffic_delivery_claim_allowed": False,
                    "dataplane_delivery_claim_allowed": False,
                    "external_settlement_finality_claim_allowed": False,
                    "production_readiness_claim_allowed": False,
                    "requires_dataplane_evidence_for_delivery_claim": True,
                    "requires_external_finality_evidence_for_settlement_claim": True,
                    "raw_identifiers_redacted": True,
                    "payloads_redacted": True,
                },
                "output_summary": {
                    "escrow_status_after": "released",
                    "raw_identifiers_redacted": True,
                    "payloads_redacted": True,
                },
            },
        },
    }
    with event_log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")


def _append_irrelevant_event_log_entries(root: Path, count: int) -> None:
    event_log = root / ".agent_coordination/events.log"
    event_log.parent.mkdir(parents=True, exist_ok=True)
    with event_log.open("a", encoding="utf-8") as handle:
        for index in range(count):
            event = {
                "event_id": f"irrelevant-event-{index}",
                "event_type": "pipeline.stage_end",
                "source_agent": "yggdrasil-client",
                "timestamp": f"2026-05-31T00:01:{index % 60:02d}",
                "data": {
                    "component": "src.network.yggdrasil_client",
                    "operation": "getPeers",
                    "observed_state": True,
                    "raw_identifiers_redacted": True,
                    "payloads_redacted": True,
                    "claim_boundary": "Local Yggdrasil observed-state only.",
                },
            }
            handle.write(json.dumps(event) + "\n")


def _append_valid_yggdrasil_observed_state_event(root: Path) -> None:
    event_log = root / ".agent_coordination/events.log"
    event_log.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "event_id": "yggdrasil-observed-state-event-1",
        "event_type": "pipeline.stage_end",
        "source_agent": "yggdrasil-client",
        "timestamp": "2026-05-31T00:00:00+00:00",
        "data": {
            "schema": "x0tta6bl4.yggdrasil_observed_state.eventbus_evidence.v1",
            "component": "network.yggdrasil_client",
            "stage": "observed_state",
            "operation": "get_peers",
            "resource": "network:yggdrasil:get_peers",
            "service_name": "yggdrasil-client",
            "layer": "network_yggdrasil_observed_state",
            "identity": {
                "service_name": "yggdrasil-client",
                "spiffe_id_configured": False,
                "did_configured": False,
                "wallet_address_configured": False,
                "redacted": True,
            },
            "service_identity": {
                "service_name": "yggdrasil-client",
                "spiffe_id_configured": False,
                "did_configured": False,
                "wallet_address_configured": False,
                "redacted": True,
            },
            "command": ["yggdrasilctl", "getPeers"],
            "status": "succeeded",
            "source_mode": "real_command",
            "returncode": 0,
            "return_code": 0,
            "duration_ms": 3.5,
            "read_only": True,
            "observed_state": True,
            "safe_actuator": False,
            "parsed_summary": {
                "status": "ok",
                "peer_count": 2,
                "protocols": ["tcp"],
            },
            "output": {
                "stdout_chars": 80,
                "stderr_chars": 0,
                "stdout_sha256": "a" * 64,
                "stderr_sha256": None,
                "stdout_preview_chars": 0,
                "stderr_preview_chars": 0,
                "stdout_truncated": True,
                "stderr_truncated": False,
                "output_preview_limit": 0,
                "output_bounded": True,
                "output_redacted": True,
            },
            "claim_gate": {
                "schema": "x0tta6bl4.yggdrasil_observed_state.claim_gate.v1",
                "decision": "LOCAL_YGGDRASIL_OBSERVED_STATE_ONLY",
                "local_observed_state_claim_allowed": True,
                "real_yggdrasil_daemon_observed": True,
                "mock_source_mode": False,
                "return_code_observed": True,
                "remote_peer_authenticity_claim_allowed": False,
                "route_quality_claim_allowed": False,
                "live_packet_reachability_claim_allowed": False,
                "customer_traffic_claim_allowed": False,
                "production_readiness_claim_allowed": False,
                "blockers": [],
                "claim_boundary": "Local Yggdrasil observed-state only.",
                "redacted": True,
            },
            "raw_values_redacted": True,
            "payloads_redacted": True,
            "claim_boundary": "Local Yggdrasil observed-state only.",
        },
    }
    with event_log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")


def _write_map(
    root: Path,
    *,
    gaps: list[dict] | None = None,
    next_actions: list[dict] | None = None,
    dataplane_flags: bool = False,
    dpi_flags: bool = False,
    production_flags: bool = False,
    settlement_flags: bool = False,
    trust_flags: bool = False,
    customer_flags: bool = False,
) -> None:
    architecture = root / "docs/architecture"
    architecture.mkdir(parents=True, exist_ok=True)
    (architecture / "CURRENT_ACTIVE_GOAL_GAP_AUDIT.md").write_text("# audit\n", encoding="utf-8")
    payload = {
        "status": "working_map_not_production_completion_proof",
        "planes": {
            "data_plane": {},
            "control_plane": {},
            "trust_plane": {},
            "evidence_plane": {},
            "economy_plane": {},
        },
        "cross_plane_links": [
            {
                "id": "local-link",
                "from_planes": ["data_plane"],
                "to_planes": ["evidence_plane"],
                "proof_flags": {
                    "local_observed_state": True,
                    "eventbus_evidence": True,
                    "dataplane_confirmed": production_flags or dataplane_flags,
                    "production_customer_traffic_confirmed": customer_flags,
                },
            },
            {
                "id": "dataplane-delivery-link",
                "from_planes": ["data_plane"],
                "to_planes": ["evidence_plane"],
                "proof_flags": {
                    "customer_dataplane_delivery_claim_allowed": dataplane_flags,
                    "traffic_delivery_claim_allowed": dataplane_flags,
                },
            },
            {
                "id": "billing-link",
                "from_planes": ["economy_plane"],
                "to_planes": ["evidence_plane"],
                "proof_flags": {
                    "billing_claim_gate_present": True,
                    "local_billing_lifecycle_claim_allowed": True,
                    "payment_settlement_confirmed": production_flags or settlement_flags,
                    "external_settlement_finality_confirmed": production_flags or settlement_flags,
                    "settlement_finality_confirmed": production_flags or settlement_flags,
                    "production_readiness_claim_allowed": production_flags,
                },
            },
            {
                "id": "trust-link",
                "from_planes": ["trust_plane"],
                "to_planes": ["evidence_plane"],
                "proof_flags": {
                    "live_spire_svid_confirmed": production_flags or trust_flags,
                },
            },
            {
                "id": "dpi-link",
                "from_planes": ["data_plane"],
                "to_planes": ["evidence_plane"],
                "proof_flags": {
                    "external_dpi_tested": dpi_flags,
                    "dpi_bypass_confirmed": dpi_flags,
                    "bypass_confirmed": dpi_flags,
                },
            },
        ],
        "current_gaps": gaps or [],
        "next_actions": next_actions or [],
    }
    (architecture / "CURRENT_CROSS_PLANE_EVIDENCE_MAP.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def test_gate_allows_local_claim_when_required_flags_are_true(tmp_path: Path) -> None:
    _write_map(tmp_path)
    _append_valid_yggdrasil_observed_state_event(tmp_path)

    report = build_report(tmp_path, claims=("local_observed_state", "local_billing_lifecycle"))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_ALLOWED"
    assert report["allowed"] is True
    assert {item["claim_id"] for item in report["claim_results"]} == {
        "local_observed_state",
        "local_billing_lifecycle",
    }
    local_observed = next(
        item for item in report["claim_results"]
        if item["claim_id"] == "local_observed_state"
    )
    artifact = local_observed["required_artifact_evidence"]
    assert artifact["valid"] is True
    assert artifact["selected_event"]["event_id"] == "yggdrasil-observed-state-event-1"
    assert artifact["selected_event"]["return_code"] == 0
    assert artifact["selected_event"]["duration_ms"] == 3.5


def test_gate_blocks_local_claim_without_eventbus_artifact(tmp_path: Path) -> None:
    _write_map(tmp_path)

    report = build_report(tmp_path, claims=("local_observed_state",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    [local_observed] = report["claim_results"]
    assert local_observed["allowed"] is False
    assert "local_observed_state_eventbus_artifact_not_verified" in local_observed[
        "blockers"
    ]
    artifact = local_observed["required_artifact_evidence"]
    assert artifact["valid"] is False
    assert "local_observed_state_event_log_missing" in artifact["blockers"]


def test_gate_routes_verified_local_observed_artifact_to_map_reconciliation(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path)
    _append_valid_yggdrasil_observed_state_event(tmp_path)
    path = tmp_path / "docs/architecture/CURRENT_CROSS_PLANE_EVIDENCE_MAP.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["cross_plane_links"][0]["proof_flags"].pop("local_observed_state")
    payload["cross_plane_links"][0]["proof_flags"].pop("eventbus_evidence")
    path.write_text(json.dumps(payload), encoding="utf-8")

    report = build_report(tmp_path, claims=("local_observed_state",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    [local_observed] = report["claim_results"]
    assert "evidence_map_local_observed_state_flags_not_reconciled" in (
        local_observed["blockers"]
    )
    assert local_observed["required_artifact_evidence"]["valid"] is True
    assert report["next_actions"][0]["action_id"] == (
        "reconcile_local_observed_state_evidence_map_flags"
    )


def test_gate_blocks_local_claim_when_yggdrasil_event_is_mock_only(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path)
    _append_valid_yggdrasil_observed_state_event(tmp_path)
    event_log = tmp_path / ".agent_coordination/events.log"
    event = json.loads(event_log.read_text(encoding="utf-8"))
    event["data"]["source_mode"] = "mock"
    event["data"]["claim_gate"]["real_yggdrasil_daemon_observed"] = False
    event["data"]["claim_gate"]["mock_source_mode"] = True
    event["data"]["claim_gate"]["blockers"] = [
        "mock_source_mode_not_live_mesh_evidence"
    ]
    event_log.write_text(json.dumps(event) + "\n", encoding="utf-8")

    report = build_report(tmp_path, claims=("local_observed_state",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    [local_observed] = report["claim_results"]
    artifact = local_observed["required_artifact_evidence"]
    assert artifact["valid"] is False
    assert "local_observed_state_not_real_command" in artifact["candidate_blockers"]
    assert "local_observed_state_mock_source_mode" in artifact["candidate_blockers"]
    assert "local_observed_state_claim_gate_has_blockers" in artifact[
        "candidate_blockers"
    ]


def test_gate_blocks_local_claim_when_output_metadata_is_not_bounded(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path)
    _append_valid_yggdrasil_observed_state_event(tmp_path)
    event_log = tmp_path / ".agent_coordination/events.log"
    event = json.loads(event_log.read_text(encoding="utf-8"))
    event["data"]["output"]["output_bounded"] = False
    event["data"]["stdout"] = "raw peer 10.0.0.1"
    event_log.write_text(json.dumps(event) + "\n", encoding="utf-8")

    report = build_report(tmp_path, claims=("local_observed_state",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    [local_observed] = report["claim_results"]
    artifact = local_observed["required_artifact_evidence"]
    assert artifact["valid"] is False
    assert "local_observed_state_output_not_bounded" in artifact["candidate_blockers"]
    assert "local_observed_state_raw_output_present" in artifact["candidate_blockers"]


def test_default_claims_cover_all_high_risk_proof_surfaces(tmp_path: Path) -> None:
    _write_map(tmp_path)

    expected_claims = (
        "production_readiness",
        "local_observed_state",
        "mesh_recovery_lifecycle",
        "local_restored_dataplane",
        "dataplane_delivery",
        "traffic_delivery",
        "customer_traffic",
        "local_service_identity_status",
        "measured_attestation_verifier_smoke",
        "trust_finality",
        "dpi_bypass",
        "settlement_finality",
    )

    assert DEFAULT_CLAIMS == expected_claims

    report = build_report(tmp_path)

    assert [item["claim_id"] for item in report["claim_results"]] == list(
        expected_claims
    )
    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    assert report["allowed"] is False
    assert report["summary"]["claims_total"] == len(expected_claims)
    assert report["summary"]["claims_blocked"] == len(expected_claims)
    assert report["allowed_claim_ids"] == []
    assert report["blocked_claim_ids"] == list(expected_claims)
    assert set(report["claim_blockers"]) == set(expected_claims)
    assert report["summary"]["high_risk_claims_requested"] == (
        len(expected_claims) - 5
    )
    assert report["plane_claims"] == {
        "data_plane": [
            "production_readiness",
            "local_observed_state",
            "local_restored_dataplane",
            "dataplane_delivery",
            "traffic_delivery",
            "customer_traffic",
            "dpi_bypass",
        ],
        "control_plane": ["production_readiness", "mesh_recovery_lifecycle"],
        "trust_plane": [
            "production_readiness",
            "local_service_identity_status",
            "measured_attestation_verifier_smoke",
            "trust_finality",
        ],
        "evidence_plane": list(expected_claims),
        "economy_plane": ["production_readiness", "settlement_finality"],
    }
    assert report["allowed_plane_ids"] == []
    assert report["blocked_plane_ids"] == [
        "data_plane",
        "control_plane",
        "trust_plane",
        "evidence_plane",
        "economy_plane",
    ]
    assert set(report["plane_blockers"]) == set(report["blocked_plane_ids"])
    assert "dataplane_delivery_eventbus_artifact_not_verified" in report[
        "plane_blockers"
    ]["data_plane"]
    assert "trust_finality_eventbus_artifact_not_verified" in report[
        "plane_blockers"
    ]["trust_plane"]
    assert "external_settlement_artifact_not_verified" in report[
        "plane_blockers"
    ]["economy_plane"]
    graph = report["proof_dependency_graph"]
    assert set(graph) == set(expected_claims)
    assert graph["production_readiness"]["planes"] == [
        "data_plane",
        "control_plane",
        "trust_plane",
        "evidence_plane",
        "economy_plane",
    ]
    assert [
        item["artifact_id"]
        for item in graph["production_readiness"]["artifact_dependencies"]
    ] == [
        "production_readiness",
        "mesh_recovery_lifecycle",
        "local_restored_dataplane",
        "dataplane_delivery",
        "traffic_delivery",
        "customer_traffic",
        "local_service_identity_status",
        "measured_attestation_verifier_smoke",
        "trust_finality",
        "external_settlement",
        "economy_boundary",
    ]
    assert graph["dataplane_delivery"]["artifact_dependencies"][0]["path"] == (
        ".agent_coordination/events.log"
    )
    assert graph["traffic_delivery"]["artifact_dependencies"][0]["artifact_id"] == (
        "traffic_delivery"
    )
    assert graph["traffic_delivery"]["artifact_dependencies"][0]["path"] == (
        ".agent_coordination/events.log"
    )
    assert graph["local_observed_state"]["artifact_dependencies"][0]["path"] == (
        ".agent_coordination/events.log"
    )
    assert graph["mesh_recovery_lifecycle"]["artifact_dependencies"][0]["path"] == (
        ".agent_coordination/events.log"
    )
    assert graph["local_restored_dataplane"]["artifact_dependencies"][0]["path"] == (
        ".agent_coordination/events.log"
    )
    assert graph["local_service_identity_status"]["artifact_dependencies"][0]["path"] == (
        ".agent_coordination/events.log"
    )
    assert graph["measured_attestation_verifier_smoke"]["artifact_dependencies"][0]["path"] == (
        "docs/verification/incoming/measured_attestation_verifier_smoke.json"
    )
    assert graph["dpi_bypass"]["next_action_ids"] == [
        "import_verified_dpi_lab_evidence"
    ]
    assert graph["settlement_finality"]["next_action_ids"] == [
        "verify_external_settlement_artifacts"
    ]
    assert [
        action["action_id"]
        for action in report["next_actions_by_plane"]["data_plane"]
    ] == [
        "collect_local_yggdrasil_observed_state_eventbus_evidence",
        "collect_verified_dataplane_delivery_eventbus_evidence",
        "collect_verified_traffic_delivery_eventbus_evidence",
        "collect_mesh_recovery_lifecycle_eventbus_evidence",
        "collect_verified_customer_traffic_eventbus_evidence",
        "collect_verified_trust_finality_eventbus_evidence",
        "collect_local_service_identity_status_eventbus_evidence",
        "validate_measured_attestation_verifier_smoke_artifact",
        "import_verified_dpi_lab_evidence",
        "verify_external_settlement_artifacts",
        "import_verified_production_readiness_evidence",
    ]
    assert [
        action["action_id"]
        for action in report["next_actions_by_plane"]["trust_plane"]
    ] == [
        "collect_verified_dataplane_delivery_eventbus_evidence",
        "collect_verified_traffic_delivery_eventbus_evidence",
        "collect_mesh_recovery_lifecycle_eventbus_evidence",
        "collect_verified_customer_traffic_eventbus_evidence",
        "collect_verified_trust_finality_eventbus_evidence",
        "collect_local_service_identity_status_eventbus_evidence",
        "validate_measured_attestation_verifier_smoke_artifact",
        "verify_external_settlement_artifacts",
        "import_verified_production_readiness_evidence",
    ]
    assert report["next_actions_by_plane"]["trust_plane"][4][
        "reason_blockers"
    ] == [
        "explicit_false_flag:live_spire_svid_confirmed",
        "missing_any_true_flags:live_spire_svid_confirmed,did_ownership_confirmed,wallet_control_confirmed,chain_identity_finality_confirmed",
        "trust_finality_artifact_not_verified",
        "trust_finality_eventbus_artifact_not_verified",
    ]
    assert [action["action_id"] for action in report["next_actions"]] == [
        "collect_local_yggdrasil_observed_state_eventbus_evidence",
        "collect_verified_dataplane_delivery_eventbus_evidence",
        "collect_verified_traffic_delivery_eventbus_evidence",
        "collect_mesh_recovery_lifecycle_eventbus_evidence",
        "collect_verified_customer_traffic_eventbus_evidence",
        "collect_verified_trust_finality_eventbus_evidence",
        "collect_local_service_identity_status_eventbus_evidence",
        "validate_measured_attestation_verifier_smoke_artifact",
        "import_verified_dpi_lab_evidence",
        "verify_external_settlement_artifacts",
        "import_verified_production_readiness_evidence",
    ]
    local_observed_action = report["next_actions"][0]
    assert local_observed_action["plane_ids"] == ["data_plane", "evidence_plane"]
    assert local_observed_action["claim_ids"] == ["local_observed_state"]
    assert local_observed_action["automation_status"] == (
        "local_command_available_when_yggdrasilctl_exists"
    )
    assert "yggdrasilctl-backed read" in local_observed_action[
        "implementation_gap"
    ]
    dataplane_action = report["next_actions"][1]
    assert dataplane_action["plane_ids"] == [
        "data_plane",
        "control_plane",
        "trust_plane",
        "evidence_plane",
        "economy_plane",
    ]
    assert dataplane_action["claim_ids"] == [
        "production_readiness",
        "local_restored_dataplane",
        "dataplane_delivery",
    ]
    assert "dataplane_delivery_eventbus_artifact_not_verified" in dataplane_action[
        "reason_blockers"
    ]
    assert dataplane_action["automation_status"] == "local_command_available"
    assert dataplane_action["suggested_commands"][0] == [
        "python3",
        "scripts/ops/collect_dataplane_delivery_eventbus_evidence.py",
        "--host",
        "127.0.0.1",
        "--port",
        "<local_port>",
        "--allow-local-probe",
        "--write-event",
        "--json",
    ]
    traffic_action = report["next_actions"][2]
    assert traffic_action["claim_ids"] == [
        "production_readiness",
        "traffic_delivery",
    ]
    assert "production_readiness_traffic_delivery_artifact_not_verified" in (
        traffic_action["reason_blockers"]
    )
    assert traffic_action["automation_status"] == "manual_or_scenario_probe_required"
    assert traffic_action["suggested_commands"][0] == [
        "python3",
        "scripts/ops/collect_traffic_delivery_eventbus_evidence.py",
        "--proof-json",
        "docs/verification/incoming/traffic_delivery.json",
        "--allow-redacted-local-proof-intake",
        "--write-event",
        "--json",
    ]
    assert "docs/verification/incoming/traffic_delivery.json" in traffic_action[
        "artifact_paths"
    ]
    assert "Do not reuse the local restored-dataplane collector" in traffic_action[
        "implementation_gap"
    ]
    recovery_action = report["next_actions"][3]
    assert recovery_action["automation_status"] == (
        "local_command_available_for_safe_simulation"
    )
    assert recovery_action["suggested_commands"][0] == [
        "python3",
        "scripts/ops/collect_mesh_recovery_lifecycle_eventbus_evidence.py",
        "--allow-local-simulation",
        "--write-event",
        "--json",
    ]
    assert "does not mutate live mesh state" in recovery_action[
        "implementation_gap"
    ]
    customer_action = report["next_actions"][4]
    assert customer_action["automation_status"] == (
        "local_command_available_for_redacted_proof_intake"
    )
    assert customer_action["suggested_commands"][0] == [
        "python3",
        "scripts/ops/collect_customer_traffic_eventbus_evidence.py",
        "--proof-json",
        "docs/verification/incoming/customer_traffic.json",
        "--allow-redacted-local-proof-intake",
        "--write-event",
        "--json",
    ]
    assert "docs/verification/incoming/customer_traffic.json" in customer_action[
        "artifact_paths"
    ]
    assert "does not run probes" in customer_action[
        "implementation_gap"
    ]
    trust_action = report["next_actions"][5]
    assert trust_action["automation_status"] == (
        "local_command_available_for_redacted_proof_intake"
    )
    assert trust_action["suggested_commands"][0] == [
        "python3",
        "scripts/ops/collect_trust_finality_eventbus_evidence.py",
        "--proof-json",
        "docs/verification/incoming/trust_finality.json",
        "--allow-redacted-local-proof-intake",
        "--write-event",
        "--json",
    ]
    assert "docs/verification/incoming/trust_finality.json" in trust_action[
        "artifact_paths"
    ]
    identity_action = report["next_actions"][6]
    assert identity_action["automation_status"] == "local_command_available"
    assert identity_action["suggested_commands"][0] == [
        "python3",
        "scripts/ops/collect_local_service_identity_status_eventbus_evidence.py",
        "--write-event",
        "--json",
    ]
    measured_attestation_action = report["next_actions"][7]
    assert measured_attestation_action["automation_status"] == (
        "local_command_available_with_operator_inputs"
    )
    assert measured_attestation_action["suggested_commands"][0][:2] == [
        "python3",
        "scripts/ops/verify_measured_attestation_verifier_smoke.py",
    ]
    assert "docs/verification/incoming/measured_attestation_verifier_smoke.json" in (
        measured_attestation_action["artifact_paths"]
    )
    assert "out of chat" in measured_attestation_action["implementation_gap"]
    dpi_action = report["next_actions"][8]
    assert dpi_action["automation_status"] == (
        "local_command_available_with_operator_inputs"
    )
    assert dpi_action["suggested_commands"][0] == [
        "python3",
        "scripts/ops/run_external_dpi_intake_local.py",
        "--dry-run",
        "--json",
    ]
    assert dpi_action["suggested_commands"][1] == [
        "python3",
        "scripts/ops/run_external_dpi_intake_local.py",
        "--json",
        "--write-ready",
    ]
    assert "docs/verification/incoming/artifacts/dpi_lab" in dpi_action[
        "artifact_paths"
    ]
    assert "ghost-pulse-external-evidence-import-*/import-report.json" in " ".join(
        dpi_action["artifact_paths"]
    )
    assert "authorized external lab/field run" in dpi_action["implementation_gap"]
    settlement_action = report["next_actions"][9]
    assert settlement_action["automation_status"] == (
        "local_command_available_with_operator_inputs"
    )
    assert settlement_action["suggested_commands"][1] == [
        "python3",
        "scripts/ops/collect_x0t_external_settlement_evidence.py",
        "--preflight-only",
        "--output",
        "json",
    ]
    assert settlement_action["suggested_commands"][2] == [
        "python3",
        "scripts/ops/collect_x0t_external_settlement_evidence.py",
        "--transaction-hash",
        "<submitted_tx_hash>",
        "--destination-chain",
        "base-sepolia",
        "--settlement-id",
        "<settlement_id>",
        "--write-evidence",
        "--output",
        "json",
        "--require-ready",
    ]
    assert settlement_action["suggested_commands"][-1] == [
        "python3",
        "scripts/ops/run_x0t_external_settlement_operator_handoff.py",
        "--output",
        "json",
        "--require-ready",
    ]
    assert (
        ".tmp/validation-shards/"
        "x0t-external-settlement-operator-handoff-current.json"
    ) in settlement_action["artifact_paths"]
    assert "do not submit a transaction" in settlement_action["implementation_gap"]
    production_action = report["next_actions"][-1]
    assert production_action["automation_status"] == (
        "local_command_available_after_supporting_proofs"
    )
    assert "docs/verification/incoming/production_readiness.json" in production_action[
        "artifact_paths"
    ]
    assert "production_readiness_imported_artifact_not_verified" in report["blockers"]
    assert "trust_finality_eventbus_artifact_not_verified" in report["blockers"]
    assert "customer_traffic_eventbus_artifact_not_verified" in report["blockers"]


def test_gate_blocks_high_risk_claims_when_current_gaps_are_open(tmp_path: Path) -> None:
    _write_map(
        tmp_path,
        gaps=[{"id": "external-dpi-proof-missing"}],
        next_actions=[{"id": "external-dpi-real-artifact-intake"}],
    )

    report = build_report(tmp_path, claims=("production_readiness", "dpi_bypass"))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    assert report["allowed"] is False
    for result in report["claim_results"]:
        assert result["allowed"] is False
        assert "current_evidence_open_gaps" in result["blockers"]
        assert "current_evidence_next_actions_open" in result["blockers"]
    dpi = next(item for item in report["claim_results"] if item["claim_id"] == "dpi_bypass")
    assert "missing_true_flag:external_dpi_tested" in dpi["blockers"]
    assert any(item["flag"] == "dpi_bypass_confirmed" for item in dpi["blocking_false_flags"])


def test_gate_tracks_non_blocking_gaps_without_blocking_high_risk_context(
    tmp_path: Path,
) -> None:
    _write_map(
        tmp_path,
        gaps=[{"id": "tracked-local-risk", "blocks_real_readiness": False}],
    )

    report = build_report(tmp_path, claims=("dpi_bypass",))

    assert report["context"]["current_gap_count"] == 0
    assert report["context"]["tracked_gap_count"] == 1
    assert report["context"]["non_blocking_gap_ids"] == ["tracked-local-risk"]
    blockers = report["claim_results"][0]["blockers"]
    assert "current_evidence_open_gaps" not in blockers
    assert "missing_true_flag:external_dpi_tested" in blockers


def test_gate_blocks_dpi_bypass_when_map_flags_are_true_but_imported_artifact_is_missing(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path, dpi_flags=True)

    report = build_report(tmp_path, claims=("dpi_bypass",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    assert report["allowed"] is False
    [dpi] = report["claim_results"]
    assert dpi["allowed"] is False
    assert dpi["missing_true_flags"] == []
    assert "dpi_lab_imported_artifact_not_verified" in dpi["blockers"]
    artifact = dpi["required_artifact_evidence"]
    assert artifact["valid"] is False
    assert artifact["artifact_path"] == "docs/verification/GHOST_PULSE_DPI_LAB_LATEST.json"
    assert artifact["proof_gate_validation"]["status"] == "MISSING"


def test_gate_blocks_dpi_bypass_when_imported_artifact_lacks_fresh_import_trace(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path, dpi_flags=True)
    _write_verified_dpi_lab_latest_without_import_trace(tmp_path)

    report = build_report(tmp_path, claims=("dpi_bypass",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    assert report["allowed"] is False
    [dpi] = report["claim_results"]
    assert dpi["allowed"] is False
    assert "dpi_lab_imported_artifact_not_verified" in dpi["blockers"]
    artifact = dpi["required_artifact_evidence"]
    assert artifact["proof_gate_validation"]["status"] == "VERIFIED"
    assert artifact["external_dpi_proxy_validation"]["decision"] == "READY_TO_IMPORT"
    assert artifact["import_freshness"]["valid"] is False
    assert "verified_dpi_lab_fresh_import_report_not_found" in artifact["import_freshness"]["blockers"]
    assert "dpi_lab_import_freshness_not_verified" in artifact["blockers"]


def test_gate_surfaces_bounded_dpi_intake_context_for_rejected_gap_candidate(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path, dpi_flags=True)
    _write_rejected_dpi_lab_gap_candidate_reports(tmp_path)

    report = build_report(tmp_path, claims=("dpi_bypass",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    [dpi] = report["claim_results"]
    assert "dpi_lab_imported_artifact_not_verified" in dpi["blockers"]
    artifact = dpi["required_artifact_evidence"]
    context = artifact["intake_context"]
    assert context["available"] is True
    assert context["ready_to_import"] is False
    assert context["ready_for_write_import"] is False
    assert context["replacement_report"]["decision"] == "REPLACEMENT_CANDIDATES_NOT_READY"
    assert context["intake_report"]["decision"] == "EXTERNAL_EVIDENCE_INTAKE_ACTION_REQUIRED"
    assert context["candidate"] == "docs/verification/incoming/dpi_lab.json"
    assert context["candidate_exists"] is True
    assert context["candidate_is_file"] is True
    assert context["candidate_is_symlink"] is False
    assert context["validation"]["status"] == "INVALID"
    assert context["validation"]["failures_total"] > context["validation"]["failures_limit"]
    assert context["validation"]["failures_capped"] is True
    assert len(context["validation"]["failures"]) == context["validation"]["failures_limit"]
    assert context["external_dpi_proxy_validation"]["decision"] == "REJECTED"
    assert context["command_shapes"]["read_only_import_entrypoint_present"] is True
    assert context["command_shapes"]["write_import_entrypoint_present"] is True
    assert context["command_shapes"]["collector_entrypoint_present"] is True
    dumped = json.dumps(context)
    assert "--target-url" not in dumped
    assert "--treatment-proxy" not in dumped
    assert "authorized target URL" not in dumped
    assert "authorized proxy URL" not in dumped
    assert "DPI intake context is diagnostic" in context["claim_boundary"]


def test_gate_allows_dpi_bypass_only_with_map_flags_and_verified_imported_artifact(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path, dpi_flags=True)
    _write_imported_dpi_lab_artifact(tmp_path)

    report = build_report(tmp_path, claims=("dpi_bypass",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_ALLOWED"
    assert report["allowed"] is True
    [dpi] = report["claim_results"]
    assert dpi["allowed"] is True
    assert dpi["blockers"] == []
    artifact = dpi["required_artifact_evidence"]
    assert artifact["valid"] is True
    assert artifact["proof_gate_validation"]["status"] == "VERIFIED"
    assert artifact["external_dpi_proxy_validation"]["decision"] == "READY_TO_IMPORT"
    assert artifact["import_freshness"]["valid"] is True
    assert artifact["import_freshness"]["selected_report"]["write_freshness_claim_allowed"] is True
    assert artifact["external_dpi_proxy_validation"]["summary"]["production_ready"] is False
    assert artifact["intake_context"]["available"] is True
    assert artifact["intake_context"]["ready_to_import"] is True
    assert artifact["intake_context"]["ready_for_write_import"] is True


def test_gate_blocks_trust_finality_when_map_flags_are_true_but_event_is_missing(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path, trust_flags=True)

    report = build_report(tmp_path, claims=("trust_finality",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    assert report["allowed"] is False
    [trust] = report["claim_results"]
    assert trust["allowed"] is False
    assert trust["missing_any_flag_groups"] == []
    assert "trust_finality_eventbus_artifact_not_verified" in trust["blockers"]
    artifact = trust["required_artifact_evidence"]
    assert artifact["valid"] is False
    assert artifact["event_log_path"] == ".agent_coordination/events.log"
    assert "trust_finality_event_log_missing" in artifact["blockers"]


def test_gate_allows_trust_finality_only_with_verified_eventbus_artifact(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path, trust_flags=True)
    _write_valid_trust_finality_event(tmp_path)

    report = build_report(tmp_path, claims=("trust_finality",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_ALLOWED"
    assert report["allowed"] is True
    [trust] = report["claim_results"]
    assert trust["allowed"] is True
    assert trust["blockers"] == []
    artifact = trust["required_artifact_evidence"]
    assert artifact["valid"] is True
    assert artifact["selected_event"]["event_id"] == "trust-finality-event-1"
    assert artifact["selected_event"]["redacted"] is True
    assert "dataplane delivery" in artifact["claim_boundary"]


def test_gate_blocks_trust_finality_without_required_source_artifact_context(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path, trust_flags=True)
    _write_valid_trust_finality_event(tmp_path)
    event_log = tmp_path / ".agent_coordination/events.log"
    event = json.loads(event_log.read_text(encoding="utf-8"))
    event["data"]["source_artifacts"] = [
        {
            "role": "generic_redacted_identity_log",
            "sha256": "a" * 64,
            "path_redacted": True,
            "redacted": True,
        }
    ]
    event_log.write_text(json.dumps(event) + "\n", encoding="utf-8")

    report = build_report(tmp_path, claims=("trust_finality",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    [trust] = report["claim_results"]
    assert "trust_finality_eventbus_artifact_not_verified" in trust["blockers"]
    artifact = trust["required_artifact_evidence"]
    assert artifact["valid"] is False
    assert "trust_finality_required_source_artifact_missing" in artifact[
        "candidate_blockers"
    ]


def test_gate_finds_trust_finality_event_outside_tail_scan_via_source_filter(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path, trust_flags=True)
    _write_valid_trust_finality_event(tmp_path)
    _append_irrelevant_event_log_entries(tmp_path, 1001)

    report = build_report(tmp_path, claims=("trust_finality",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_ALLOWED"
    [trust] = report["claim_results"]
    artifact = trust["required_artifact_evidence"]
    assert artifact["valid"] is True
    assert artifact["selected_event"]["event_id"] == "trust-finality-event-1"
    assert artifact["selected_event"]["scan_source"] == (
        "source_agent_prefiltered_reverse_scan"
    )
    assert artifact["candidate_scan"]["event_log_lines_seen"] > artifact[
        "tail_events_scanned_limit"
    ]


def test_gate_allows_local_service_identity_status_without_trust_finality(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path)
    _write_valid_local_service_identity_status_event(tmp_path)

    report = build_report(
        tmp_path,
        claims=("local_service_identity_status", "trust_finality"),
    )

    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    assert report["allowed_claim_ids"] == ["local_service_identity_status"]
    assert report["blocked_claim_ids"] == ["trust_finality"]
    [identity, trust] = report["claim_results"]
    assert identity["allowed"] is True
    assert identity["blockers"] == []
    artifact = identity["required_artifact_evidence"]
    assert artifact["valid"] is True
    assert artifact["selected_event"]["event_id"] == (
        "local-service-identity-status-event-1"
    )
    assert artifact["selected_event"]["services_total"] == 3
    assert "trust_finality_eventbus_artifact_not_verified" in trust["blockers"]


def test_gate_blocks_measured_attestation_smoke_without_validated_artifact(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path)

    report = build_report(tmp_path, claims=("measured_attestation_verifier_smoke",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    [attestation] = report["claim_results"]
    assert attestation["allowed"] is False
    assert "measured_attestation_verifier_smoke_artifact_not_verified" in (
        attestation["blockers"]
    )
    artifact = attestation["required_artifact_evidence"]
    assert artifact["valid"] is False
    assert artifact["artifact_path"] == (
        "docs/verification/incoming/measured_attestation_verifier_smoke.json"
    )
    assert artifact["validation"]["decision"] == "REJECTED"
    assert "measured_attestation_verifier_smoke_artifact_not_ready" in artifact[
        "blockers"
    ]
    dependency = report["proof_dependency_graph"][
        "measured_attestation_verifier_smoke"
    ]["artifact_dependencies"][0]
    assert dependency["present"] is False
    assert dependency["valid"] is False
    assert dependency["path"] == (
        "docs/verification/incoming/measured_attestation_verifier_smoke.json"
    )


def test_gate_allows_measured_attestation_smoke_only_with_validated_artifact(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path)
    _write_valid_measured_attestation_smoke_artifact(tmp_path)

    report = build_report(tmp_path, claims=("measured_attestation_verifier_smoke",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_ALLOWED"
    assert report["allowed"] is True
    [attestation] = report["claim_results"]
    assert attestation["allowed"] is True
    assert attestation["blockers"] == []
    artifact = attestation["required_artifact_evidence"]
    assert artifact["valid"] is True
    assert artifact["validation"]["decision"] == "READY_TO_IMPORT"
    assert artifact["validation"]["candidate_sha256_present"] is True
    assert "production readiness by itself" in artifact["claim_boundary"]


def test_gate_blocks_measured_attestation_smoke_when_artifact_overpromotes_production(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path)
    _write_valid_measured_attestation_smoke_artifact(tmp_path)
    path = tmp_path / "docs/verification/incoming/measured_attestation_verifier_smoke.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["result_summary"]["production_ready"] = True
    payload["artifact_identity"]["artifact_sha256"] = _artifact_content_sha256(payload)
    path.write_text(json.dumps(payload), encoding="utf-8")

    report = build_report(tmp_path, claims=("measured_attestation_verifier_smoke",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    [attestation] = report["claim_results"]
    artifact = attestation["required_artifact_evidence"]
    assert artifact["valid"] is False
    assert "measured_attestation_verifier_smoke_artifact_not_ready" in artifact[
        "blockers"
    ]
    assert "result_summary.production_ready must be false" in artifact[
        "validation"
    ]["failures"]


def test_gate_blocks_customer_traffic_when_map_flags_are_true_but_event_is_missing(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path, customer_flags=True)

    report = build_report(tmp_path, claims=("customer_traffic",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    assert report["allowed"] is False
    [customer] = report["claim_results"]
    assert customer["allowed"] is False
    assert customer["missing_true_flags"] == []
    assert "customer_traffic_eventbus_artifact_not_verified" in customer["blockers"]
    artifact = customer["required_artifact_evidence"]
    assert artifact["valid"] is False
    assert "customer_traffic_event_log_missing" in artifact["blockers"]


def test_gate_blocks_customer_traffic_when_only_dataplane_artifact_exists(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path, customer_flags=True)
    _write_valid_dataplane_delivery_event(tmp_path)

    report = build_report(tmp_path, claims=("customer_traffic",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    [customer] = report["claim_results"]
    assert "customer_traffic_eventbus_artifact_not_verified" in customer["blockers"]
    artifact = customer["required_artifact_evidence"]
    assert artifact["valid"] is False
    assert "verified_customer_traffic_event_not_found" in artifact["blockers"]


def test_gate_allows_customer_traffic_only_with_verified_customer_artifact(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path, customer_flags=True)
    _write_valid_customer_traffic_event(tmp_path)

    report = build_report(tmp_path, claims=("customer_traffic",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_ALLOWED"
    assert report["allowed"] is True
    [customer] = report["claim_results"]
    assert customer["allowed"] is True
    assert customer["blockers"] == []
    artifact = customer["required_artifact_evidence"]
    assert artifact["valid"] is True
    assert artifact["selected_event"]["event_id"] == "customer-traffic-event-1"
    assert artifact["selected_event"]["production_customer_traffic_confirmed"] is True
    assert artifact["selected_event"]["environment"] == "production"
    assert "Dataplane probes" in artifact["claim_boundary"]


def test_gate_blocks_customer_traffic_without_production_probe_artifact_context(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path, customer_flags=True)
    _write_valid_customer_traffic_event(tmp_path)
    event_log = tmp_path / ".agent_coordination/events.log"
    event = json.loads(event_log.read_text(encoding="utf-8"))
    event["data"]["environment"] = "lab"
    event["data"]["source_artifacts"] = [
        {
            "role": "generic_redacted_log",
            "sha256": "b" * 64,
            "path_redacted": True,
            "redacted": True,
        }
    ]
    event_log.write_text(json.dumps(event) + "\n", encoding="utf-8")

    report = build_report(tmp_path, claims=("customer_traffic",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    [customer] = report["claim_results"]
    assert "customer_traffic_eventbus_artifact_not_verified" in customer["blockers"]
    artifact = customer["required_artifact_evidence"]
    assert artifact["valid"] is False
    assert "customer_traffic_environment_not_production" in artifact[
        "candidate_blockers"
    ]
    assert "customer_traffic_required_source_artifact_missing" in artifact[
        "candidate_blockers"
    ]


def test_gate_finds_customer_traffic_event_outside_tail_scan_via_source_filter(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path, customer_flags=True)
    _write_valid_customer_traffic_event(tmp_path)
    _append_irrelevant_event_log_entries(tmp_path, 1001)

    report = build_report(tmp_path, claims=("customer_traffic",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_ALLOWED"
    [customer] = report["claim_results"]
    artifact = customer["required_artifact_evidence"]
    assert artifact["valid"] is True
    assert artifact["selected_event"]["event_id"] == "customer-traffic-event-1"
    assert artifact["selected_event"]["scan_source"] == (
        "source_agent_prefiltered_reverse_scan"
    )
    assert artifact["candidate_scan"]["event_log_lines_seen"] > artifact[
        "tail_events_scanned_limit"
    ]


def test_dataplane_source_filter_includes_local_collector() -> None:
    artifact = dataplane_delivery_artifact_evidence(Path("/tmp/nonexistent-x0t-proof"))

    assert "dataplane-delivery-local-collector" in artifact[
        "candidate_source_agents"
    ]


def test_gate_blocks_production_readiness_when_map_flags_are_true_but_imported_artifact_is_missing(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path, production_flags=True, customer_flags=True)
    _write_valid_dataplane_delivery_event(tmp_path, traffic_delivery_allowed=True)
    _write_valid_customer_traffic_event(tmp_path)
    _write_valid_trust_finality_event(tmp_path)
    _write_valid_local_service_identity_status_event(tmp_path)
    _write_valid_measured_attestation_smoke_artifact(tmp_path)
    _write_valid_economy_boundary_event(tmp_path)
    _write_valid_external_settlement_artifacts(tmp_path)

    report = build_report(tmp_path, claims=("production_readiness",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    assert report["allowed"] is False
    [production] = report["claim_results"]
    assert production["allowed"] is False
    assert production["missing_true_flags"] == []
    assert "production_readiness_imported_artifact_not_verified" in production["blockers"]
    artifact = production["required_artifact_evidence"]
    assert artifact["valid"] is False
    assert artifact["artifact_path"] == "docs/verification/GHOST_PULSE_PRODUCTION_READINESS_LATEST.json"
    assert artifact["proof_gate_validation"]["status"] in {"MISSING", "INVALID"}


def test_gate_allows_production_readiness_only_with_map_flags_and_verified_imported_artifact(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path, production_flags=True, customer_flags=True)
    _write_stub_production_readiness_proof(tmp_path, verified=True)
    _write_valid_dataplane_delivery_event(tmp_path, traffic_delivery_allowed=True)
    _write_valid_mesh_recovery_lifecycle_event(tmp_path)
    _write_valid_customer_traffic_event(tmp_path)
    _write_valid_trust_finality_event(tmp_path)
    _write_valid_local_service_identity_status_event(tmp_path)
    _write_valid_measured_attestation_smoke_artifact(tmp_path)
    _write_valid_economy_boundary_event(tmp_path)
    _write_valid_external_settlement_artifacts(tmp_path)

    report = build_report(tmp_path, claims=("production_readiness",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_ALLOWED"
    assert report["allowed"] is True
    [production] = report["claim_results"]
    assert production["allowed"] is True
    assert production["blockers"] == []
    artifact = production["required_artifact_evidence"]
    assert artifact["valid"] is True
    assert artifact["proof_gate_validation"]["status"] == "VERIFIED"
    assert "live customer traffic" in artifact["claim_boundary"]
    dataplane = production["supporting_artifact_evidence"]["dataplane_delivery"]
    assert dataplane["valid"] is True
    assert dataplane["selected_event"]["event_id"] == "dataplane-event-1"
    assert dataplane["selected_event"]["restored_dataplane_claim_allowed"] is True
    traffic = production["supporting_artifact_evidence"]["traffic_delivery"]
    assert traffic["valid"] is True
    assert traffic["selected_event"]["event_id"] == "dataplane-event-1"
    assert traffic["selected_event"]["traffic_delivery_claim_allowed"] is True
    assert traffic["selected_event"]["claim_scope"] == "traffic_delivery"
    recovery = production["supporting_artifact_evidence"]["mesh_recovery_lifecycle"]
    assert recovery["valid"] is True
    assert recovery["selected_event"]["event_id"] == (
        "mesh-recovery-lifecycle-event-1"
    )
    assert recovery["selected_event"]["redacted"] is True
    customer = production["supporting_artifact_evidence"]["customer_traffic"]
    assert customer["valid"] is True
    assert customer["selected_event"]["event_id"] == "customer-traffic-event-1"
    assert customer["selected_event"]["production_customer_traffic_confirmed"] is True
    settlement = production["supporting_artifact_evidence"]["external_settlement"]
    assert settlement["valid"] is True
    assert (
        settlement["retained_evidence_validation"]["summary"][
            "x0t_external_settlement_ready"
        ]
        is True
    )
    assert "does not prove production readiness by itself" in settlement["claim_boundary"]
    economy = production["supporting_artifact_evidence"]["economy_boundary"]
    assert economy["valid"] is True
    assert economy["selected_event"]["event_id"] == "economy-boundary-event-1"
    trust = production["supporting_artifact_evidence"]["trust_finality"]
    assert trust["valid"] is True
    assert trust["selected_event"]["event_id"] == "trust-finality-event-1"
    identity = production["supporting_artifact_evidence"][
        "local_service_identity_status"
    ]
    assert identity["valid"] is True
    assert identity["selected_event"]["event_id"] == (
        "local-service-identity-status-event-1"
    )
    measured_attestation = production["supporting_artifact_evidence"][
        "measured_attestation_verifier_smoke"
    ]
    assert measured_attestation["valid"] is True
    assert measured_attestation["validation"]["decision"] == "READY_TO_IMPORT"


def test_gate_blocks_production_readiness_when_traffic_delivery_artifact_is_missing(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path, production_flags=True, customer_flags=True)
    _write_stub_production_readiness_proof(tmp_path, verified=True)
    _write_valid_dataplane_delivery_event(tmp_path)
    _write_valid_mesh_recovery_lifecycle_event(tmp_path)
    _write_valid_customer_traffic_event(tmp_path)
    _write_valid_trust_finality_event(tmp_path)
    _write_valid_local_service_identity_status_event(tmp_path)
    _write_valid_measured_attestation_smoke_artifact(tmp_path)
    _write_valid_economy_boundary_event(tmp_path)
    _write_valid_external_settlement_artifacts(tmp_path)

    report = build_report(tmp_path, claims=("production_readiness",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    assert report["allowed"] is False
    [production] = report["claim_results"]
    assert production["allowed"] is False
    assert (
        "production_readiness_traffic_delivery_artifact_not_verified"
        in production["blockers"]
    )
    assert production["required_artifact_evidence"]["valid"] is True
    assert production["supporting_artifact_evidence"]["dataplane_delivery"]["valid"] is True
    traffic = production["supporting_artifact_evidence"]["traffic_delivery"]
    assert traffic["valid"] is False
    assert "verified_traffic_delivery_event_not_found" in traffic["blockers"]
    assert (
        "traffic_delivery_not_proven_by_local_restored_dataplane_artifact"
        in traffic["candidate_blockers"]
    )


def test_gate_blocks_production_readiness_when_measured_attestation_smoke_is_missing(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path, production_flags=True, customer_flags=True)
    _write_stub_production_readiness_proof(tmp_path, verified=True)
    _write_valid_dataplane_delivery_event(tmp_path, traffic_delivery_allowed=True)
    _write_valid_mesh_recovery_lifecycle_event(tmp_path)
    _write_valid_customer_traffic_event(tmp_path)
    _write_valid_trust_finality_event(tmp_path)
    _write_valid_local_service_identity_status_event(tmp_path)
    _write_valid_economy_boundary_event(tmp_path)
    _write_valid_external_settlement_artifacts(tmp_path)

    report = build_report(tmp_path, claims=("production_readiness",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    [production] = report["claim_results"]
    assert (
        "production_readiness_measured_attestation_verifier_smoke_artifact_not_verified"
        in production["blockers"]
    )
    measured_attestation = production["supporting_artifact_evidence"][
        "measured_attestation_verifier_smoke"
    ]
    assert measured_attestation["valid"] is False
    assert "measured_attestation_verifier_smoke_artifact_not_ready" in (
        measured_attestation["blockers"]
    )


def test_gate_blocks_production_readiness_when_dataplane_artifact_is_missing(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path, production_flags=True, customer_flags=True)
    _write_stub_production_readiness_proof(tmp_path, verified=True)
    _write_valid_customer_traffic_event(tmp_path)
    _write_valid_trust_finality_event(tmp_path)
    _write_valid_local_service_identity_status_event(tmp_path)
    _write_valid_measured_attestation_smoke_artifact(tmp_path)
    _write_valid_economy_boundary_event(tmp_path)
    _write_valid_external_settlement_artifacts(tmp_path)

    report = build_report(tmp_path, claims=("production_readiness",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    assert report["allowed"] is False
    [production] = report["claim_results"]
    assert production["allowed"] is False
    assert "production_readiness_dataplane_artifact_not_verified" in production["blockers"]
    dataplane = production["supporting_artifact_evidence"]["dataplane_delivery"]
    assert dataplane["valid"] is False
    assert "verified_dataplane_delivery_event_not_found" in dataplane["blockers"]
    assert production["required_artifact_evidence"]["valid"] is True
    assert production["supporting_artifact_evidence"]["trust_finality"]["valid"] is True
    assert production["supporting_artifact_evidence"]["economy_boundary"]["valid"] is True
    assert production["supporting_artifact_evidence"]["external_settlement"]["valid"] is True


def test_gate_blocks_production_readiness_when_customer_traffic_artifact_is_missing(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path, production_flags=True, customer_flags=True)
    _write_stub_production_readiness_proof(tmp_path, verified=True)
    _write_valid_dataplane_delivery_event(tmp_path, traffic_delivery_allowed=True)
    _write_valid_trust_finality_event(tmp_path)
    _write_valid_local_service_identity_status_event(tmp_path)
    _write_valid_measured_attestation_smoke_artifact(tmp_path)
    _write_valid_economy_boundary_event(tmp_path)
    _write_valid_external_settlement_artifacts(tmp_path)

    report = build_report(tmp_path, claims=("production_readiness",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    assert report["allowed"] is False
    [production] = report["claim_results"]
    assert production["allowed"] is False
    assert (
        "production_readiness_customer_traffic_artifact_not_verified"
        in production["blockers"]
    )
    customer = production["supporting_artifact_evidence"]["customer_traffic"]
    assert customer["valid"] is False
    assert "verified_customer_traffic_event_not_found" in customer["blockers"]
    assert production["required_artifact_evidence"]["valid"] is True
    assert production["supporting_artifact_evidence"]["dataplane_delivery"]["valid"] is True
    assert production["supporting_artifact_evidence"]["traffic_delivery"]["valid"] is True
    assert production["supporting_artifact_evidence"]["trust_finality"]["valid"] is True
    assert production["supporting_artifact_evidence"]["economy_boundary"]["valid"] is True
    assert production["supporting_artifact_evidence"]["external_settlement"]["valid"] is True


def test_gate_blocks_production_readiness_when_external_settlement_artifact_is_missing(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path, production_flags=True, customer_flags=True)
    _write_stub_production_readiness_proof(tmp_path, verified=True)
    _write_valid_dataplane_delivery_event(tmp_path, traffic_delivery_allowed=True)
    _write_valid_customer_traffic_event(tmp_path)
    _write_valid_trust_finality_event(tmp_path)
    _write_valid_local_service_identity_status_event(tmp_path)
    _write_valid_measured_attestation_smoke_artifact(tmp_path)
    _write_valid_economy_boundary_event(tmp_path)

    report = build_report(tmp_path, claims=("production_readiness",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    assert report["allowed"] is False
    [production] = report["claim_results"]
    assert production["allowed"] is False
    assert (
        "production_readiness_external_settlement_artifact_not_verified"
        in production["blockers"]
    )
    settlement = production["supporting_artifact_evidence"]["external_settlement"]
    assert settlement["valid"] is False
    assert "external_settlement_retained_evidence_not_verified" in settlement["blockers"]
    assert "external_settlement_live_rpc_report_missing" in settlement["blockers"]
    assert "external_settlement_blocker_report_missing" in settlement["blockers"]
    assert production["required_artifact_evidence"]["valid"] is True
    assert production["supporting_artifact_evidence"]["dataplane_delivery"]["valid"] is True
    assert production["supporting_artifact_evidence"]["traffic_delivery"]["valid"] is True
    assert production["supporting_artifact_evidence"]["customer_traffic"]["valid"] is True
    assert production["supporting_artifact_evidence"]["trust_finality"]["valid"] is True
    assert production["supporting_artifact_evidence"]["economy_boundary"]["valid"] is True


def test_gate_blocks_production_readiness_when_customer_traffic_map_flag_is_missing(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path, production_flags=True)
    _write_stub_production_readiness_proof(tmp_path, verified=True)
    _write_valid_dataplane_delivery_event(tmp_path, traffic_delivery_allowed=True)
    _write_valid_customer_traffic_event(tmp_path)
    _write_valid_trust_finality_event(tmp_path)
    _write_valid_local_service_identity_status_event(tmp_path)
    _write_valid_measured_attestation_smoke_artifact(tmp_path)
    _write_valid_economy_boundary_event(tmp_path)
    _write_valid_external_settlement_artifacts(tmp_path)

    report = build_report(tmp_path, claims=("production_readiness",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    assert report["allowed"] is False
    [production] = report["claim_results"]
    assert production["allowed"] is False
    assert "production_customer_traffic_confirmed" in production["missing_true_flags"]
    assert "missing_true_flag:production_customer_traffic_confirmed" in production["blockers"]
    assert any(
        item["flag"] == "production_customer_traffic_confirmed"
        for item in production["blocking_false_flags"]
    )
    assert production["required_artifact_evidence"]["valid"] is True
    assert production["supporting_artifact_evidence"]["traffic_delivery"]["valid"] is True
    assert production["supporting_artifact_evidence"]["customer_traffic"]["valid"] is True


def test_gate_blocks_dataplane_delivery_when_map_flags_are_true_but_eventbus_artifact_is_missing(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path, dataplane_flags=True)

    report = build_report(tmp_path, claims=("dataplane_delivery",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    assert report["allowed"] is False
    [dataplane] = report["claim_results"]
    assert dataplane["allowed"] is False
    assert dataplane["missing_true_flags"] == []
    assert dataplane["missing_any_flag_groups"] == []
    assert "dataplane_delivery_eventbus_artifact_not_verified" in dataplane["blockers"]
    artifact = dataplane["required_artifact_evidence"]
    assert artifact["valid"] is False
    assert artifact["event_log_path"] == ".agent_coordination/events.log"
    assert "dataplane_event_log_missing" in artifact["blockers"]


def test_gate_routes_to_map_reconciliation_after_verified_dataplane_artifact(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path)
    _write_valid_dataplane_delivery_event(tmp_path)

    report = build_report(
        tmp_path,
        claims=("dataplane_delivery", "traffic_delivery"),
    )

    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    assert report["allowed"] is False
    [dataplane, traffic] = report["claim_results"]
    assert dataplane["required_artifact_evidence"]["valid"] is True
    assert traffic["required_artifact_evidence"]["valid"] is False
    assert "dataplane_delivery_eventbus_artifact_not_verified" not in dataplane[
        "blockers"
    ]
    assert "traffic_delivery_eventbus_artifact_not_verified" in traffic[
        "blockers"
    ]
    assert "evidence_map_dataplane_flags_not_reconciled" in dataplane[
        "blockers"
    ]
    traffic_artifact = traffic["required_artifact_evidence"]
    assert "traffic_delivery_not_proven_by_local_restored_dataplane_artifact" in (
        traffic_artifact["candidate_blockers"]
    )

    assert [action["action_id"] for action in report["next_actions"]] == [
        "collect_verified_traffic_delivery_eventbus_evidence",
        "reconcile_dataplane_delivery_evidence_map_flags"
    ]
    traffic_action, reconcile_action = report["next_actions"]
    assert traffic_action["automation_status"] == "manual_or_scenario_probe_required"
    assert reconcile_action["automation_status"] == (
        "manual_review_required_with_verified_artifact"
    )
    assert "CURRENT_CROSS_PLANE_EVIDENCE_MAP.json" in " ".join(
        reconcile_action["artifact_paths"]
    )


def test_gate_allows_local_restored_dataplane_without_promoting_delivery_claims(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path)
    _write_valid_dataplane_delivery_event(tmp_path)

    report = build_report(
        tmp_path,
        claims=(
            "local_restored_dataplane",
            "dataplane_delivery",
            "traffic_delivery",
        ),
    )

    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    assert report["allowed_claim_ids"] == ["local_restored_dataplane"]
    assert report["blocked_claim_ids"] == ["dataplane_delivery", "traffic_delivery"]

    [local, dataplane, traffic] = report["claim_results"]
    assert local["allowed"] is True
    assert local["blockers"] == []
    assert local["required_artifact_evidence"]["valid"] is True
    assert local["required_artifact_evidence"]["selected_event"]["event_id"] == (
        "dataplane-event-1"
    )
    assert "evidence_map_dataplane_flags_not_reconciled" in dataplane["blockers"]
    assert "traffic_delivery_eventbus_artifact_not_verified" in traffic[
        "blockers"
    ]
    assert "traffic_delivery_not_proven_by_local_restored_dataplane_artifact" in traffic[
        "required_artifact_evidence"
    ]["candidate_blockers"]


def test_production_dependency_graph_uses_dataplane_artifact_for_local_restored_dataplane(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path)
    _write_valid_dataplane_delivery_event(tmp_path)

    report = build_report(tmp_path, claims=("production_readiness",))

    dependencies = {
        item["artifact_id"]: item
        for item in report["proof_dependency_graph"]["production_readiness"][
            "artifact_dependencies"
        ]
    }
    local_restored = dependencies["local_restored_dataplane"]
    assert local_restored["present"] is True
    assert local_restored["valid"] is True
    assert local_restored["path"] == ".agent_coordination/events.log"
    assert local_restored["blockers"] == []
    assert "production_readiness_dataplane_artifact_not_verified" not in report[
        "claim_blockers"
    ]["production_readiness"]


def test_gate_blocks_traffic_delivery_when_map_flags_are_true_but_artifact_is_missing(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path, dataplane_flags=True)

    report = build_report(tmp_path, claims=("traffic_delivery",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    assert report["allowed"] is False
    [traffic] = report["claim_results"]
    assert traffic["allowed"] is False
    assert traffic["missing_any_flag_groups"] == []
    assert "traffic_delivery_eventbus_artifact_not_verified" in traffic["blockers"]
    artifact = traffic["required_artifact_evidence"]
    assert artifact["valid"] is False
    assert "dataplane_event_log_missing" in artifact["blockers"]


def test_gate_blocks_traffic_delivery_when_artifact_is_local_restored_only(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path, dataplane_flags=True)
    _write_valid_dataplane_delivery_event(tmp_path)

    report = build_report(tmp_path, claims=("traffic_delivery",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    [traffic] = report["claim_results"]
    assert traffic["allowed"] is False
    assert "traffic_delivery_eventbus_artifact_not_verified" in traffic["blockers"]
    artifact = traffic["required_artifact_evidence"]
    assert artifact["valid"] is False
    assert artifact["selected_event"] is None
    assert "verified_traffic_delivery_event_not_found" in artifact["blockers"]
    assert (
        "traffic_delivery_not_proven_by_local_restored_dataplane_artifact"
        in artifact["candidate_blockers"]
    )
    assert report["next_actions"][0]["action_id"] == (
        "collect_verified_traffic_delivery_eventbus_evidence"
    )


def test_gate_allows_traffic_delivery_only_with_verified_traffic_artifact(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path, dataplane_flags=True)
    _write_valid_dataplane_delivery_event(
        tmp_path,
        traffic_delivery_allowed=True,
    )

    report = build_report(tmp_path, claims=("traffic_delivery",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_ALLOWED"
    assert report["allowed"] is True
    [traffic] = report["claim_results"]
    assert traffic["allowed"] is True
    assert traffic["blockers"] == []
    artifact = traffic["required_artifact_evidence"]
    assert artifact["valid"] is True
    assert artifact["selected_event"]["event_id"] == "dataplane-event-1"
    assert artifact["selected_event"]["restored_dataplane_claim_allowed"] is True
    assert artifact["selected_event"]["traffic_delivery_claim_allowed"] is True
    assert artifact["selected_event"]["claim_scope"] == "traffic_delivery"


def test_gate_allows_dataplane_delivery_only_with_map_flags_and_verified_eventbus_artifact(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path, dataplane_flags=True)
    _write_valid_dataplane_delivery_event(tmp_path)

    report = build_report(tmp_path, claims=("dataplane_delivery",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_ALLOWED"
    assert report["allowed"] is True
    [dataplane] = report["claim_results"]
    assert dataplane["allowed"] is True
    assert dataplane["blockers"] == []
    artifact = dataplane["required_artifact_evidence"]
    assert artifact["valid"] is True
    assert artifact["selected_event"]["event_id"] == "dataplane-event-1"
    assert artifact["selected_event"]["redacted"] is True
    assert "customer traffic" in artifact["claim_boundary"]


def test_gate_finds_dataplane_delivery_event_outside_tail_scan_via_source_filter(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path, dataplane_flags=True)
    _write_valid_dataplane_delivery_event(tmp_path)
    _append_irrelevant_event_log_entries(tmp_path, 1001)

    report = build_report(tmp_path, claims=("dataplane_delivery",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_ALLOWED"
    [dataplane] = report["claim_results"]
    artifact = dataplane["required_artifact_evidence"]
    assert artifact["valid"] is True
    assert artifact["selected_event"]["event_id"] == "dataplane-event-1"
    assert artifact["selected_event"]["scan_source"] == (
        "source_agent_prefiltered_reverse_scan"
    )
    assert artifact["candidate_scan"]["event_log_lines_seen"] > artifact[
        "tail_events_scanned_limit"
    ]


def test_gate_blocks_dataplane_delivery_when_eventbus_artifact_lacks_probe_evidence(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path, dataplane_flags=True)
    _write_valid_dataplane_delivery_event(tmp_path)
    event_log = tmp_path / ".agent_coordination/events.log"
    event = json.loads(event_log.read_text(encoding="utf-8"))
    event["data"]["post_action_dataplane_revalidation"]["evidence"]["event_ids"] = []
    event["data"]["post_action_dataplane_revalidation"]["evidence"]["event_ids_count"] = 0
    event_log.write_text(json.dumps(event) + "\n", encoding="utf-8")

    report = build_report(tmp_path, claims=("dataplane_delivery",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    [dataplane] = report["claim_results"]
    assert "dataplane_delivery_eventbus_artifact_not_verified" in dataplane["blockers"]
    artifact = dataplane["required_artifact_evidence"]
    assert artifact["valid"] is False
    assert "verified_dataplane_delivery_event_not_found" in artifact["blockers"]


def test_gate_blocks_dataplane_delivery_without_nested_claim_gate(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path, dataplane_flags=True)
    _write_valid_dataplane_delivery_event(tmp_path)
    event_log = tmp_path / ".agent_coordination/events.log"
    event = json.loads(event_log.read_text(encoding="utf-8"))
    event["data"]["post_action_dataplane_revalidation"].pop("claim_gate")
    event_log.write_text(json.dumps(event) + "\n", encoding="utf-8")

    report = build_report(tmp_path, claims=("dataplane_delivery",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    [dataplane] = report["claim_results"]
    assert "dataplane_delivery_eventbus_artifact_not_verified" in dataplane["blockers"]
    artifact = dataplane["required_artifact_evidence"]
    assert artifact["valid"] is False
    assert "restored_dataplane_claim_gate_missing" in artifact["candidate_blockers"]
    assert "verified_dataplane_delivery_event_not_found" in artifact["blockers"]


def test_gate_blocks_dataplane_delivery_from_yggdrasil_observed_state_only(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path, dataplane_flags=True)
    _write_valid_dataplane_delivery_event(tmp_path)
    event_log = tmp_path / ".agent_coordination/events.log"
    event = json.loads(event_log.read_text(encoding="utf-8"))
    revalidation = event["data"]["post_action_dataplane_revalidation"]
    revalidation["evidence"]["source_agents"] = ["yggdrasil-client"]
    revalidation["evidence"]["source_agents_count"] = 1
    event["data"]["downstream_claim_gates"] = {
        "present": True,
        "claim_gates": [
            {
                "source_agent": "yggdrasil-client",
                "schema": "x0tta6bl4.yggdrasil_observed_state.claim_gate.v1",
                "decision": "LOCAL_YGGDRASIL_OBSERVED_STATE_ONLY",
                "flags": {
                    "local_observed_state_claim_allowed": True,
                    "live_packet_reachability_claim_allowed": False,
                    "customer_traffic_claim_allowed": False,
                    "production_readiness_claim_allowed": False,
                },
                "redacted": True,
            }
        ],
        "redacted": True,
    }
    event_log.write_text(json.dumps(event) + "\n", encoding="utf-8")

    report = build_report(tmp_path, claims=("dataplane_delivery",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    [dataplane] = report["claim_results"]
    assert "dataplane_delivery_eventbus_artifact_not_verified" in dataplane["blockers"]
    artifact = dataplane["required_artifact_evidence"]
    assert artifact["valid"] is False
    assert "dataplane_evidence_source_agent_not_dataplane_probe" in artifact[
        "candidate_blockers"
    ]
    assert "dataplane_evidence_is_local_observed_state_only" in artifact[
        "candidate_blockers"
    ]


def test_gate_blocks_settlement_finality_when_map_flags_are_true_but_artifact_is_missing(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path, settlement_flags=True)

    report = build_report(tmp_path, claims=("settlement_finality",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    assert report["allowed"] is False
    [settlement] = report["claim_results"]
    assert settlement["allowed"] is False
    assert settlement["missing_any_flag_groups"] == []
    assert "external_settlement_artifact_not_verified" in settlement["blockers"]
    artifact = settlement["required_artifact_evidence"]
    assert artifact["valid"] is False
    assert artifact["evidence_path"] == ".tmp/external-settlement-evidence/settlement-submit.json"
    assert "external_settlement_retained_evidence_not_verified" in artifact["blockers"]
    assert "external_settlement_live_rpc_report_missing" in artifact["blockers"]
    assert "external_settlement_blocker_report_missing" in artifact["blockers"]
    handoff = artifact["operator_handoff"]
    assert handoff["available"] is True
    assert handoff["ready_for_completion_rerun"] is False
    assert any(item["id"] == "retained_settlement_receipt" for item in handoff["missing_inputs"])
    assert "settlement finality" in handoff["claim_boundary"]


def test_gate_blocks_settlement_finality_when_economy_boundary_event_is_missing(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path, settlement_flags=True)
    _write_valid_external_settlement_artifacts(tmp_path)

    report = build_report(tmp_path, claims=("settlement_finality",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    assert report["allowed"] is False
    [settlement] = report["claim_results"]
    assert settlement["allowed"] is False
    assert "external_settlement_artifact_not_verified" not in settlement["blockers"]
    assert "economy_boundary_artifact_not_verified" in settlement["blockers"]
    assert settlement["required_artifact_evidence"]["valid"] is True
    economy = settlement["supporting_artifact_evidence"]["economy_boundary"]
    assert economy["valid"] is False
    assert "economy_event_log_missing" in economy["blockers"]


def test_gate_blocks_economy_boundary_when_source_gate_overpromotes_production(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path, settlement_flags=True)
    _write_valid_external_settlement_artifacts(tmp_path)
    _write_valid_economy_boundary_event(tmp_path)
    event_log = tmp_path / ".agent_coordination/events.log"
    event = json.loads(event_log.read_text(encoding="utf-8"))
    event["data"]["settlement_evidence"]["claim_gate"][
        "production_readiness_claim_allowed"
    ] = True
    event_log.write_text(json.dumps(event) + "\n", encoding="utf-8")

    report = build_report(tmp_path, claims=("settlement_finality",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    [settlement] = report["claim_results"]
    assert "economy_boundary_artifact_not_verified" in settlement["blockers"]
    economy = settlement["supporting_artifact_evidence"]["economy_boundary"]
    assert economy["valid"] is False
    assert "economy_source_gate_overpromotes_production_readiness" in economy[
        "candidate_blockers"
    ]


def test_gate_allows_settlement_finality_only_with_map_flags_and_verified_settlement_artifact(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path, settlement_flags=True)
    _write_valid_external_settlement_artifacts(tmp_path)
    _write_valid_economy_boundary_event(tmp_path)

    report = build_report(tmp_path, claims=("settlement_finality",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_ALLOWED"
    assert report["allowed"] is True
    [settlement] = report["claim_results"]
    assert settlement["allowed"] is True
    assert settlement["blockers"] == []
    artifact = settlement["required_artifact_evidence"]
    assert artifact["valid"] is True
    assert artifact["retained_evidence_validation"]["summary"]["x0t_external_settlement_ready"] is True
    assert artifact["live_rpc_report"]["summary"]["x0t_external_settlement_live_rpc_ready"] is True
    assert artifact["blocker_report"]["decision"] == "READY_TO_PROMOTE"
    assert artifact["operator_handoff"]["available"] is True
    assert artifact["operator_handoff"]["summary"]["evidence_file_ready"] is True
    assert artifact["operator_handoff"]["summary"]["live_rpc_ready"] is True
    assert "required_command" not in json.dumps(artifact["operator_handoff"])
    assert "customer traffic" in artifact["claim_boundary"]
    economy = settlement["supporting_artifact_evidence"]["economy_boundary"]
    assert economy["valid"] is True
    assert economy["selected_event"]["local_or_pending_only"] is True
    assert economy["selected_event"]["production_readiness_claim_allowed"] is False


def test_gate_redacts_external_settlement_live_rpc_endpoint(
    tmp_path: Path,
) -> None:
    from src.integration import external_settlement as settlement_module

    _write_map(tmp_path, settlement_flags=True)
    _write_valid_external_settlement_artifacts(tmp_path)
    _write_valid_economy_boundary_event(tmp_path)
    rpc_path = tmp_path / settlement_module.DEFAULT_RPC_REPORT
    rpc_report = json.loads(rpc_path.read_text(encoding="utf-8"))
    rpc_report["rpc_endpoint"] = "https://secret-rpc.example/api-key"
    rpc_path.write_text(json.dumps(rpc_report), encoding="utf-8")

    report = build_report(tmp_path, claims=("settlement_finality",))

    [settlement] = report["claim_results"]
    artifact = settlement["required_artifact_evidence"]
    live_rpc = artifact["live_rpc_report"]
    assert live_rpc["rpc_endpoint"] is None
    assert live_rpc["rpc_endpoint_present"] is True
    assert live_rpc["rpc_endpoint_scheme"] == "https"
    assert live_rpc["rpc_endpoint_hash"]
    assert live_rpc["rpc_endpoint_redacted"] is True
    assert "secret-rpc.example" not in json.dumps(artifact)


def test_gate_finds_economy_boundary_event_outside_tail_scan_via_source_filter(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path, settlement_flags=True)
    _write_valid_external_settlement_artifacts(tmp_path)
    _write_valid_economy_boundary_event(tmp_path)
    _append_irrelevant_event_log_entries(tmp_path, 1001)

    report = build_report(tmp_path, claims=("settlement_finality",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_ALLOWED"
    [settlement] = report["claim_results"]
    economy = settlement["supporting_artifact_evidence"]["economy_boundary"]
    assert economy["valid"] is True
    assert economy["selected_event"]["event_id"] == "economy-boundary-event-1"
    assert economy["selected_event"]["scan_source"] == "source_agent_prefiltered_reverse_scan"
    assert economy["candidate_scan"]["event_log_lines_seen"] > economy["tail_events_scanned_limit"]
    assert "maas-marketplace" in economy["candidate_scan"]["candidate_source_agents"]


def test_cli_loads_service_event_trace_from_repo_root_when_cwd_differs(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path, settlement_flags=True)
    _write_valid_external_settlement_artifacts(tmp_path)
    _write_valid_economy_boundary_event(tmp_path)

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/ops/run_cross_plane_proof_gate.py"),
            "--root",
            str(tmp_path),
            "--claim",
            "settlement_finality",
            "--json",
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )

    report = json.loads(completed.stdout)
    [settlement] = report["claim_results"]
    economy = settlement["supporting_artifact_evidence"]["economy_boundary"]
    assert economy["valid"] is True
    assert "trace_summary_errors" not in economy


def test_cli_writes_output_json_shard_even_when_claims_are_blocked(
    tmp_path: Path,
) -> None:
    _write_map(tmp_path)
    output_json = tmp_path / ".tmp/validation-shards/cross-plane-proof-gate-current.json"

    exit_code = main(
        [
            "--root",
            str(tmp_path),
            "--claim",
            "dpi_bypass",
            "--output-json",
            str(output_json),
        ]
    )

    report = json.loads(output_json.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert report["schema"] == "x0tta6bl4.cross_plane_proof_gate.v1"
    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    assert report["allowed"] is False
    assert [item["claim_id"] for item in report["claim_results"]] == ["dpi_bypass"]
    assert report["summary"]["claims_blocked"] == 1
    context = report["context"]
    assert context["source_artifact_hashes_present"] is True
    assert len(context["map_sha256"]) == 64
    assert len(context["audit_sha256"]) == 64
    source_artifacts = {item["role"]: item for item in context["source_artifacts"]}
    assert source_artifacts["current_cross_plane_evidence_map"]["path"] == (
        "docs/architecture/CURRENT_CROSS_PLANE_EVIDENCE_MAP.json"
    )
    assert source_artifacts["current_active_goal_gap_audit"]["path"] == (
        "docs/architecture/CURRENT_ACTIVE_GOAL_GAP_AUDIT.md"
    )
    assert source_artifacts["current_cross_plane_evidence_map"]["sha256_present"] is True
    assert source_artifacts["current_active_goal_gap_audit"]["sha256_present"] is True
    assert "does not prove" in source_artifacts["current_cross_plane_evidence_map"]["claim_boundary"]


def test_gate_blocks_settlement_finality_when_blocker_report_lacks_source_artifacts(
    tmp_path: Path,
) -> None:
    from src.integration import external_settlement as settlement_module

    _write_map(tmp_path, settlement_flags=True)
    _write_valid_external_settlement_artifacts(tmp_path)
    blocker_path = tmp_path / settlement_module.DEFAULT_BLOCKER_REPORT
    blocker_report = json.loads(blocker_path.read_text(encoding="utf-8"))
    blocker_report["source_artifacts"] = []
    blocker_path.write_text(json.dumps(blocker_report), encoding="utf-8")

    report = build_report(tmp_path, claims=("settlement_finality",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    [settlement] = report["claim_results"]
    assert "external_settlement_artifact_not_verified" in settlement["blockers"]
    artifact = settlement["required_artifact_evidence"]
    assert "external_settlement_blocker_source_artifacts_missing" in artifact["blockers"]


def test_gate_blocks_unknown_claims_by_default(tmp_path: Path) -> None:
    _write_map(tmp_path)

    report = build_report(tmp_path, claims=("local_observed_state", "not-a-known-claim"))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    unknown = next(item for item in report["claim_results"] if item["claim_id"] == "not-a-known-claim")
    assert unknown["allowed"] is False
    assert unknown["blockers"] == ["unknown_claim"]


def test_gate_blocks_when_required_planes_are_missing(tmp_path: Path) -> None:
    _write_map(tmp_path)
    path = tmp_path / "docs/architecture/CURRENT_CROSS_PLANE_EVIDENCE_MAP.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    del payload["planes"]["trust_plane"]
    path.write_text(json.dumps(payload), encoding="utf-8")

    report = build_report(tmp_path, claims=("local_observed_state",))

    assert report["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    assert report["claim_results"][0]["allowed"] is False
    assert "current_evidence_required_planes_missing" in report["claim_results"][0]["blockers"]
