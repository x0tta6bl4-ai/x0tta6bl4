import json
from pathlib import Path

import src.integration.external_settlement as external_settlement
from src.integration.evidence_source_candidates import (
    COLLECTOR_BY_KEY,
    REQUIRED_EVIDENCE_KEYS,
    BuildInputs,
    build_audit,
    main,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _inputs(root: Path) -> BuildInputs:
    return BuildInputs(
        root=root,
        intake_manifest=root / ".tmp/validation-shards/production-raw-evidence-intake-manifest-current.json",
        semantic_queue=root / ".tmp/validation-shards/integration-spine-semantic-production-blocker-queue-current.json",
        operator_bundle_root=root / ".tmp/production-raw-evidence-operator-bundle",
        external_settlement_evidence=root / ".tmp/external-settlement-evidence/settlement-submit.json",
        external_settlement_gate=root / ".tmp/validation-shards/x0t-external-settlement-evidence-current.json",
        external_settlement_live_rpc=root / ".tmp/validation-shards/x0t-external-settlement-live-rpc-current.json",
    )


def _write_manifest(root: Path) -> None:
    collectors = []
    for collector_id in sorted(set(COLLECTOR_BY_KEY.values())):
        collectors.append(
            {
                "collector_id": collector_id,
                "raw_files": [
                    {
                        "raw_id": f"{collector_id}/operator-manifest.json",
                        "file_name": "operator-manifest.json",
                        "path": f".tmp/{collector_id}-raw-evidence/operator-manifest.json",
                    }
                ],
            }
        )
    _write_json(
        root / ".tmp/validation-shards/production-raw-evidence-intake-manifest-current.json",
        {"collectors": collectors},
    )


def _write_semantic(root: Path, *, ready: bool) -> None:
    by_collector = {} if ready else {collector: 1 for collector in set(COLLECTOR_BY_KEY.values())}
    if not ready:
        by_collector["external-settlement"] = 1
    _write_json(
        root / ".tmp/validation-shards/integration-spine-semantic-production-blocker-queue-current.json",
        {
            "status": "VERIFIED HERE",
            "summary": {"by_collector": by_collector},
        },
    )


def _write_operator_bundle(root: Path, *, ready: bool) -> None:
    for collector_id in set(COLLECTOR_BY_KEY.values()):
        raw_id = f"{collector_id}/operator-manifest.json"
        payload = {
            "evidence_status": "VERIFIED HERE",
            "collector_id": collector_id,
            "raw_id": raw_id,
            "file_name": "operator-manifest.json",
            "collected_at": "2026-05-20T00:00:00Z",
            "collected_by": "codex-production-operator",
            "source_commands": [f"kubectl --context prod get evidence {collector_id} -o json"],
            "production_ready": ready,
        }
        if not ready:
            payload.update(
                {
                    "environment": "production-like-local-runtime",
                    "production_promotion_blockers": ["not production"],
                    "claim_boundary": "must not be promoted to production",
                }
            )
        _write_json(
            root / f".tmp/production-raw-evidence-operator-bundle/{collector_id}/operator-manifest.json",
            payload,
        )


def _valid_settlement() -> dict:
    tx = "0x" + "1" * 64
    payload = {
        "status": "VERIFIED HERE",
        "settlement_submitted": True,
        "destination_chain": "base-sepolia",
        "settlement_id": "settlement-2026-05-20-001",
        "token_symbol": "X0T",
        "transaction_receipt_status": "success",
        "block_number": 123,
        "block_hash": "0x" + "2" * 64,
        "from_address": "0x" + "3" * 40,
        "to_address": "0x" + "4" * 40,
        "transaction_hash": tx,
        "source_commands": [f"cast tx {tx}", f"cast receipt {tx}"],
        "explorer_url": f"https://sepolia.basescan.org/tx/{tx}",
        "template_only": False,
    }
    payload["packet_hash"] = external_settlement._packet_hash(payload)
    return payload


def _write_external_settlement(root: Path, *, ready: bool) -> None:
    if ready:
        _write_json(root / ".tmp/external-settlement-evidence/settlement-submit.json", _valid_settlement())
    _write_json(
        root / ".tmp/validation-shards/x0t-external-settlement-evidence-current.json",
        {
            "status": "VERIFIED HERE",
            "summary": {"x0t_external_settlement_ready": ready},
            "x0t_external_settlement_decision": "READY" if ready else "BLOCKED",
        },
    )
    _write_json(
        root / ".tmp/validation-shards/x0t-external-settlement-live-rpc-current.json",
        {
            "status": "VERIFIED HERE",
            "summary": {"x0t_external_settlement_live_rpc_ready": ready},
        },
    )


def _write_fixture(root: Path, *, ready: bool) -> None:
    _write_manifest(root)
    _write_semantic(root, ready=ready)
    _write_operator_bundle(root, ready=ready)
    _write_external_settlement(root, ready=ready)


def test_source_candidate_audit_rejects_local_operator_bundle(tmp_path):
    _write_fixture(tmp_path, ready=False)

    report = build_audit(_inputs(tmp_path))

    assert report["decision"] == "NO_PRODUCTION_SOURCE_CANDIDATES_OPERATOR_REQUIRED"
    assert report["summary"]["ready_source_candidates_total"] == 0
    assert report["summary"]["required_inputs_ready"] == 0
    raw_routes = [route for route in report["evidence_source_routes"] if route["kind"] == "raw_evidence"]
    assert raw_routes
    assert all(route["route_classification"] == "PARTIAL_CONTEXT_ONLY" for route in raw_routes)
    assert any("production_ready must be true" in reason for reason in raw_routes[0]["source_candidates"][0]["not_ready_reasons"])


def test_source_candidate_audit_accepts_complete_production_candidates(tmp_path):
    _write_fixture(tmp_path, ready=True)

    report = build_audit(_inputs(tmp_path))

    assert report["decision"] == "READY_SOURCE_CANDIDATES_AVAILABLE"
    assert report["summary"]["required_inputs_ready"] == len(REQUIRED_EVIDENCE_KEYS)
    assert report["summary"]["ready_source_candidates_total"] == len(REQUIRED_EVIDENCE_KEYS)
    assert {route["route_classification"] for route in report["evidence_source_routes"]} == {"READY_TO_INSTALL"}


def test_source_candidate_audit_rejects_placeholder_source_command(tmp_path):
    _write_fixture(tmp_path, ready=True)
    _write_json(
        tmp_path / ".tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/operator-manifest.json",
        {
            "evidence_status": "VERIFIED HERE",
            "collector_id": "zero-trust-pqc",
            "raw_id": "zero-trust-pqc/operator-manifest.json",
            "file_name": "operator-manifest.json",
            "collected_at": "2026-05-20T00:00:00Z",
            "collected_by": "codex-production-operator",
            "source_commands": ["kubectl get example -o json"],
            "production_ready": True,
            "production_promotion_blockers": [],
        },
    )

    report = build_audit(_inputs(tmp_path))

    assert report["decision"] == "NO_PRODUCTION_SOURCE_CANDIDATES_OPERATOR_REQUIRED"
    route = next(route for route in report["evidence_source_routes"] if route["evidence_key"] == "live_spire_mtls")
    assert route["route_classification"] == "PARTIAL_CONTEXT_ONLY"
    assert any(
        "source_commands must not contain placeholders" in reason
        for reason in route["source_candidates"][0]["not_ready_reasons"]
    )


def test_source_candidate_audit_rejects_mismatched_raw_identity(tmp_path):
    _write_fixture(tmp_path, ready=True)
    _write_json(
        tmp_path / ".tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/operator-manifest.json",
        {
            "evidence_status": "VERIFIED HERE",
            "collector_id": "zero-trust-pqc",
            "raw_id": "paid-client-serviceability/operator-manifest.json",
            "file_name": "operator-manifest.json",
            "collected_at": "2026-05-20T00:00:00Z",
            "collected_by": "codex-production-operator",
            "source_commands": ["kubectl --context prod get evidence zero-trust-pqc -o json"],
            "production_ready": True,
            "production_promotion_blockers": [],
        },
    )

    report = build_audit(_inputs(tmp_path))

    assert report["decision"] == "NO_PRODUCTION_SOURCE_CANDIDATES_OPERATOR_REQUIRED"
    route = next(route for route in report["evidence_source_routes"] if route["evidence_key"] == "live_spire_mtls")
    assert route["route_classification"] == "PARTIAL_CONTEXT_ONLY"
    candidate = route["source_candidates"][0]
    assert any(
        "raw_id must match the intake manifest raw_id" in reason
        for reason in candidate["not_ready_reasons"]
    )
    assert candidate["file_report_summary"]["manifest_identity_mismatches_total"] == 1
    assert candidate["file_report_summary"]["raw_id_mismatches"] == 1
    file_report = candidate["file_reports"][0]
    assert file_report["manifest_raw_id"] == "zero-trust-pqc/operator-manifest.json"
    assert file_report["evidence_raw_id"] == "paid-client-serviceability/operator-manifest.json"
    assert file_report["raw_id_matches_manifest"] is False
    assert file_report["collector_id_matches_manifest"] is True
    assert file_report["file_name_matches_manifest"] is True


def test_source_candidate_audit_cli_writes_fail_closed_report(tmp_path):
    exit_code = main(["--root", str(tmp_path), "--require-ready"])

    assert exit_code == 2
    report = json.loads(
        (
            tmp_path / ".tmp/validation-shards/integration-spine-evidence-source-candidate-audit-current.json"
        ).read_text(encoding="utf-8")
    )
    assert report["decision"] == "NO_PRODUCTION_SOURCE_CANDIDATES_OPERATOR_REQUIRED"
    assert report["summary"]["required_inputs_ready"] == 0
