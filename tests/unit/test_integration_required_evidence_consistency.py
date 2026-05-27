import json
from pathlib import Path

from src.integration.required_evidence_consistency import ConsistencyInputs, build_report, main


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _inputs(root: Path) -> ConsistencyInputs:
    return ConsistencyInputs(
        root=root,
        passport_path=root / "passport.json",
        operator_packet_index_path=root / "packet-index.json",
        input_manifest_path=root / "input-manifest.json",
        return_acceptance_path=root / "return-acceptance.json",
        input_pipeline_path=root / "input-pipeline.json",
        rollup_contract_path=root / "rollup.json",
        closeout_path=root / "closeout.json",
        raw_operator_packet_index_path=root / "raw-operator-packet.json",
    )


def _required_item(*, item_id: str = "01:raw_evidence:live_spire_mtls:zero-trust-pqc/operator-manifest.json", ready: bool = False) -> dict:
    return {
        "item_id": item_id,
        "kind": "raw_evidence",
        "evidence_key": "live_spire_mtls",
        "raw_id": "zero-trust-pqc/operator-manifest.json",
        "ready": ready,
        "blocks_production": not ready,
        "operator_return_path": ".tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/operator-manifest.json",
        "retained_destination_path": ".tmp/zero-trust-pqc-raw-evidence/operator-manifest.json",
    }


def _write_sources(root: Path, *, ready: bool = False, packet_items: list[dict] | None = None) -> None:
    item = _required_item(ready=ready)
    packet_items = [item] if packet_items is None else packet_items
    _write_json(
        root / "passport.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "PRODUCTION_EVIDENCE_REPLACEMENT_PASSPORT_CLEAR"
            if ready
            else "PRODUCTION_EVIDENCE_REPLACEMENT_PASSPORT_READY_FOR_OPERATOR",
            "production_ready": ready,
            "required_evidence_files": [item],
            "summary": {
                "required_evidence_files_total": 1,
                "required_evidence_files_ready": 1 if ready else 0,
            },
        },
    )
    _write_json(
        root / "packet-index.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "ALL_OPERATOR_PACKETS_ACTIONABLE",
            "packet_summaries": [
                {
                    "evidence_key": "live_spire_mtls",
                    "replacement_passport_items": packet_items,
                }
            ],
        },
    )
    _write_json(
        root / "input-manifest.json",
        {
            "decision": "READY_FOR_PRODUCTION_CLOSEOUT_REVIEW" if ready else "OPERATOR_INPUT_BUNDLE_REQUIRED",
            "goal_can_be_marked_complete": ready,
        },
    )
    _write_json(
        root / "return-acceptance.json",
        {
            "decision": "RETURN_ACCEPTANCE_READY" if ready else "RETURN_ACCEPTANCE_BLOCKED",
            "summary": {
                "ready_for_pipeline_install": ready,
                "ready_to_stage": ready,
                "external_settlement_live_rpc_report_found": ready,
                "external_settlement_live_rpc_ready": ready,
                "external_artifacts_operator_required": 0 if ready else 1,
                "raw_files_staged": 1 if ready else 0,
                "raw_files_ready_to_stage": 1 if ready else 0,
                "raw_files_destination_existing": 1,
                "raw_files_local_observation": 0 if ready else 1,
                "raw_ready_to_stage": ready,
            },
        },
    )
    _write_json(
        root / "input-pipeline.json",
        {
            "pipeline_decision": "READY" if ready else "BLOCKED_INPUT_STAGE",
            "summary": {
                "external_settlement_ready": ready,
                "raw_files_installed": 1,
                "raw_files_expected": 1,
            },
        },
    )
    _write_json(
        root / "rollup.json",
        {
            "decision": "READY" if ready else "ROLLUP_APPROVAL_BLOCKED_ON_EVIDENCE",
            "summary": {
                "evidence_files_total": 1,
                "evidence_files_valid": 1 if ready else 0,
                "evidence_files_missing": 0,
                "evidence_files_invalid": 0 if ready else 1,
                "evidence_files_operator_input_required": 0 if ready else 1,
            },
        },
    )
    _write_json(
        root / "closeout.json",
        {
            "decision": "CLOSEOUT_REVIEW_READY" if ready else "CLOSEOUT_REVIEW_BLOCKED_ON_OPERATOR_EVIDENCE",
            "summary": {"ready": ready},
        },
    )
    _write_json(
        root / "raw-operator-packet.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "RAW_EVIDENCE_OPERATOR_PACKET_ACTIONABLE",
            "local_handoff_complete": True,
            "production_ready": ready,
            "packets": [
                {
                    "collector_id": "zero-trust-pqc",
                    "files": [
                        {
                            "operator_bundle_path": item["operator_return_path"],
                            "production_ready": ready,
                            "replacement_required": not ready,
                        }
                    ],
                }
            ],
            "summary": {
                "raw_files_total": 1,
                "operator_bundle_files_existing": 1,
                "operator_bundle_files_production_ready": 1 if ready else 0,
                "operator_bundle_files_replacement_required": 0 if ready else 1,
                "raw_readiness_decision": "RAW_EVIDENCE_READY_FOR_COLLECTORS"
                if ready
                else "BLOCKED_ON_OPERATOR_PRODUCTION_EVIDENCE",
                "raw_readiness_ready_for_collectors": ready,
                "raw_readiness_collectors_ready": 1 if ready else 0,
                "raw_readiness_collectors_blocked": 0 if ready else 1,
                "raw_readiness_collectors_total": 1,
                "raw_readiness_raw_files_ready": 1 if ready else 0,
                "raw_readiness_raw_files_local_observation": 0 if ready else 1,
                "raw_readiness_raw_files_total": 1,
                "production_ready_blocked_by_raw_readiness": False,
            },
        },
    )


def test_required_evidence_consistency_accepts_valid_blocked_state(tmp_path):
    _write_sources(tmp_path, ready=False)

    report = build_report(_inputs(tmp_path))

    assert report["decision"] == "VALID_REQUIRED_EVIDENCE_CONSISTENCY_BLOCKED_ON_OPERATOR"
    assert report["valid"] is True
    assert report["production_ready"] is False
    assert report["summary"]["required_evidence_files_total"] == 1
    assert report["summary"]["required_evidence_files_blocking"] == 1
    assert report["summary"]["packet_passport_item_coverage_ready"] is True
    assert report["summary"]["raw_operator_packet_local_handoff_complete"] is True
    assert report["summary"]["raw_operator_packet_production_ready"] is False
    assert report["summary"]["raw_operator_packet_files_replacement_required"] == 1
    assert report["summary"]["raw_operator_packet_readiness_decision"] == "BLOCKED_ON_OPERATOR_PRODUCTION_EVIDENCE"
    assert report["summary"]["raw_operator_packet_readiness_ready_for_collectors"] is False
    assert report["summary"]["raw_operator_packet_readiness_collectors_ready"] == 0
    assert report["summary"]["raw_operator_packet_readiness_collectors_blocked"] == 1
    assert report["summary"]["raw_operator_packet_readiness_collectors_total"] == 1
    assert report["summary"]["raw_operator_packet_readiness_raw_files_ready"] == 0
    assert report["summary"]["raw_operator_packet_readiness_raw_files_local_observation"] == 1
    assert report["summary"]["raw_operator_packet_readiness_raw_files_total"] == 1
    assert report["summary"]["raw_operator_packet_paths_missing_from_passport"] == 0
    assert report["summary"]["errors_total"] == 0
    assert report["summary"]["return_acceptance_raw_files_staged"] == 0
    assert report["summary"]["return_acceptance_raw_files_local_observation"] == 1
    assert report["summary"]["input_pipeline_raw_files_reported_installed"] == 1
    assert report["summary"]["rollup_evidence_files_invalid"] == 1
    assert report["summary"]["rollup_evidence_files_operator_input_required"] == 1


def test_required_evidence_consistency_rejects_packet_passport_mismatch(tmp_path):
    _write_sources(tmp_path, ready=False, packet_items=[_required_item(item_id="different", ready=False)])

    report = build_report(_inputs(tmp_path))

    assert report["decision"] == "INVALID_REQUIRED_EVIDENCE_CONSISTENCY"
    assert report["valid"] is False
    assert report["summary"]["errors_total"] > 0
    assert any("item_ids" in error for error in report["errors"])


def test_required_evidence_consistency_can_clear_when_sources_ready(tmp_path):
    _write_sources(tmp_path, ready=True)

    report = build_report(_inputs(tmp_path))

    assert report["decision"] == "VALID_REQUIRED_EVIDENCE_CONSISTENCY_CLEAR"
    assert report["valid"] is True
    assert report["production_ready"] is True
    assert report["summary"]["return_acceptance_raw_files_staged"] == 1
    assert report["summary"]["raw_operator_packet_production_ready"] is True
    assert report["summary"]["raw_operator_packet_files_replacement_required"] == 0
    assert report["summary"]["raw_operator_packet_readiness_ready_for_collectors"] is True
    assert report["summary"]["raw_operator_packet_readiness_raw_files_ready"] == 1
    assert report["summary"]["raw_operator_packet_readiness_collectors_blocked"] == 0
    assert report["summary"]["raw_operator_packet_readiness_raw_files_local_observation"] == 0
    assert report["summary"]["rollup_evidence_files_operator_input_required"] == 0
    assert report["not_verified_yet"] == []


def test_required_evidence_consistency_blocks_clear_when_raw_operator_packet_not_ready(tmp_path):
    _write_sources(tmp_path, ready=True)
    raw_operator_packet = json.loads((tmp_path / "raw-operator-packet.json").read_text(encoding="utf-8"))
    raw_operator_packet["production_ready"] = False
    raw_operator_packet["summary"]["operator_bundle_files_production_ready"] = 0
    raw_operator_packet["summary"]["operator_bundle_files_replacement_required"] = 1
    raw_operator_packet["summary"]["raw_readiness_decision"] = "BLOCKED_ON_OPERATOR_PRODUCTION_EVIDENCE"
    raw_operator_packet["summary"]["raw_readiness_ready_for_collectors"] = False
    raw_operator_packet["summary"]["raw_readiness_collectors_ready"] = 0
    raw_operator_packet["summary"]["raw_readiness_collectors_blocked"] = 1
    raw_operator_packet["summary"]["raw_readiness_raw_files_ready"] = 0
    raw_operator_packet["summary"]["raw_readiness_raw_files_local_observation"] = 1
    raw_operator_packet["summary"]["production_ready_blocked_by_raw_readiness"] = True
    raw_operator_packet["packets"][0]["files"][0]["production_ready"] = False
    raw_operator_packet["packets"][0]["files"][0]["replacement_required"] = True
    _write_json(tmp_path / "raw-operator-packet.json", raw_operator_packet)

    report = build_report(_inputs(tmp_path))

    assert report["decision"] == "VALID_REQUIRED_EVIDENCE_CONSISTENCY_BLOCKED_ON_OPERATOR"
    assert report["valid"] is True
    assert report["production_ready"] is False
    assert report["summary"]["raw_operator_packet_production_ready"] is False
    assert report["summary"]["raw_operator_packet_files_replacement_required"] == 1
    assert report["summary"]["raw_operator_packet_readiness_ready_for_collectors"] is False
    assert report["summary"]["raw_operator_packet_production_ready_blocked_by_raw_readiness"] is True


def test_required_evidence_consistency_cli_require_clear_returns_two_when_blocked(tmp_path):
    _write_sources(tmp_path, ready=False)
    output_json = tmp_path / "consistency.json"

    exit_code = main([
        "--root",
        str(tmp_path),
        "--passport",
        "passport.json",
        "--operator-packet-index",
        "packet-index.json",
        "--input-manifest",
        "input-manifest.json",
        "--return-acceptance",
        "return-acceptance.json",
        "--input-pipeline",
        "input-pipeline.json",
        "--rollup-contract",
        "rollup.json",
        "--closeout",
        "closeout.json",
        "--raw-operator-packet-index",
        "raw-operator-packet.json",
        "--output-json",
        str(output_json),
        "--require-valid",
        "--require-clear",
    ])

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert payload["valid"] is True
    assert payload["production_ready"] is False
