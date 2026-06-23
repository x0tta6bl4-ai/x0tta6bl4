import json
from pathlib import Path

from src.integration.production_raw_evidence_operator_packet import build_report, main


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_inputs(root: Path, *, production_ready: bool = False) -> tuple[Path, Path]:
    collector_id = "zero-trust-pqc"
    script_dir = root / "scripts/ops"
    script_dir.mkdir(parents=True, exist_ok=True)
    for script in [
        "collect_zero_trust_pqc_evidence_bundle.py",
        "verify_zero_trust_pqc_evidence_gate.py",
    ]:
        (script_dir / script).write_text("# stub\n", encoding="utf-8")

    manifest = root / ".tmp/validation-shards/production-raw-evidence-intake-manifest-current.json"
    semantic = root / ".tmp/validation-shards/production-raw-evidence-semantics-current.json"
    _write_json(
        manifest,
        {
            "collectors": [
                {
                    "collector_id": collector_id,
                    "collector_script": "scripts/ops/collect_zero_trust_pqc_evidence_bundle.py",
                    "collector_command": (
                        "python3 scripts/ops/collect_zero_trust_pqc_evidence_bundle.py "
                        "--raw-root .tmp/zero-trust-pqc-raw-evidence"
                    ),
                    "raw_root": ".tmp/zero-trust-pqc-raw-evidence",
                    "raw_files": [
                        {
                            "raw_id": f"{collector_id}/operator-manifest.json",
                            "file_name": "operator-manifest.json",
                            "path": f".tmp/{collector_id}-raw-evidence/operator-manifest.json",
                            "required_evidence_status": "VERIFIED HERE",
                        }
                    ],
                }
            ],
        },
    )
    _write_json(
        semantic,
        {
            "semantic_readiness_decision": "BLOCKED_RAW_INPUTS",
            "summary": {"collectors_total": 1, "collectors_ready": 0},
        },
    )
    _write_json(
        root / ".tmp/zero-trust-pqc-raw-evidence/operator-manifest.json",
        {
            "status": "VERIFIED HERE",
            "production_ready": production_ready,
            "production_promotion_blockers": [] if production_ready else ["retained component evidence only"],
            "collected_at": "2026-05-20T00:00:00Z",
            "collected_by": "operator",
            "source_commands": ["kubectl --context prod get spire-server -o json"],
            "environment": "production" if production_ready else "local contract-validation",
        },
    )
    _write_json(
        root / ".tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/operator-manifest.json",
        {
            "status": "VERIFIED HERE",
            "production_ready": production_ready,
            "production_promotion_blockers": [] if production_ready else ["retained component evidence only"],
            "collected_at": "2026-05-20T00:00:00Z",
            "collected_by": "operator",
            "source_commands": ["kubectl --context prod get spire-server -o json"],
            "environment": "production" if production_ready else "local contract-validation",
        },
    )
    return manifest, semantic


def test_raw_evidence_operator_packet_indexes_replacements_without_promoting(tmp_path):
    manifest, semantic = _write_inputs(tmp_path, production_ready=False)

    report = build_report(tmp_path, manifest, semantic)

    assert report["schema_version"].endswith("v1-repo-generated")
    assert report["decision"] == "RAW_EVIDENCE_OPERATOR_PACKET_ACTIONABLE"
    assert report["local_handoff_complete"] is True
    assert report["production_ready"] is False
    assert report["goal_can_be_marked_complete"] is False
    assert report["summary"]["packets_total"] == 1
    assert report["summary"]["raw_files_total"] == 1
    assert report["summary"]["operator_bundle_files_existing"] == 1
    assert report["summary"]["operator_bundle_files_production_ready"] == 0
    assert report["summary"]["operator_bundle_files_replacement_required"] == 1
    assert report["summary"]["raw_readiness_ready_for_collectors"] is False
    assert report["summary"]["raw_readiness_collectors_blocked"] == 1
    assert report["summary"]["raw_readiness_raw_files_local_observation"] == 1
    assert report["summary"]["production_ready_blocked_by_raw_readiness"] is False
    packet = report["packets"][0]
    assert packet["collector_id"] == "zero-trust-pqc"
    assert packet["actionable"] is True
    assert packet["files"][0]["operator_bundle_path"].endswith(
        ".tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/operator-manifest.json"
    )
    assert packet["files"][0]["replacement_required"] is True
    assert any("Do not promote retained/local" in rule for rule in packet["fail_closed_rules"])


def test_raw_evidence_operator_packet_reports_production_ready_files(tmp_path):
    manifest, semantic = _write_inputs(tmp_path, production_ready=True)

    report = build_report(tmp_path, manifest, semantic)

    assert report["production_ready"] is True
    assert report["goal_can_be_marked_complete"] is False
    assert report["summary"]["operator_bundle_files_production_ready"] == 1
    assert report["summary"]["operator_bundle_files_replacement_required"] == 0
    assert report["summary"]["raw_readiness_ready_for_collectors"] is True
    assert report["summary"]["raw_readiness_collectors_blocked"] == 0
    assert report["summary"]["raw_readiness_raw_files_local_observation"] == 0
    assert report["summary"]["production_ready_blocked_by_raw_readiness"] is False


def test_raw_evidence_operator_packet_requires_readiness_gate_for_production_ready(tmp_path):
    manifest, semantic = _write_inputs(tmp_path, production_ready=True)
    retained_raw = tmp_path / ".tmp/zero-trust-pqc-raw-evidence/operator-manifest.json"
    retained_raw.write_text(
        json.dumps(
            {
                "status": "VERIFIED HERE",
                "production_ready": False,
                "production_promotion_blockers": ["retained component evidence only"],
                "collected_at": "2026-05-20T00:00:00Z",
                "collected_by": "operator",
                "source_commands": ["kubectl --context prod get spire-server -o json"],
                "environment": "local contract-validation",
            }
        ),
        encoding="utf-8",
    )

    report = build_report(tmp_path, manifest, semantic)

    assert report["summary"]["operator_bundle_files_production_ready"] == 1
    assert report["summary"]["operator_bundle_files_replacement_required"] == 0
    assert report["summary"]["raw_readiness_ready_for_collectors"] is False
    assert report["summary"]["raw_readiness_collectors_blocked"] == 1
    assert report["summary"]["raw_readiness_raw_files_local_observation"] == 1
    assert report["summary"]["production_ready_blocked_by_raw_readiness"] is True
    assert report["production_ready"] is False


def test_raw_evidence_operator_packet_blocks_missing_entrypoints(tmp_path):
    manifest, semantic = _write_inputs(tmp_path, production_ready=True)
    (tmp_path / "scripts/ops/verify_zero_trust_pqc_evidence_gate.py").unlink()

    report = build_report(tmp_path, manifest, semantic)

    assert report["decision"] == "RAW_EVIDENCE_OPERATOR_PACKET_INCOMPLETE"
    assert report["local_handoff_complete"] is False
    assert report["summary"]["local_entrypoints_missing"] == 1
    assert report["packets"][0]["missing_local_entrypoints"] == ["evidence_gate_script"]


def test_raw_evidence_operator_packet_cli_writes_actionable_fail_closed_report(tmp_path):
    manifest, semantic = _write_inputs(tmp_path, production_ready=False)
    output = tmp_path / "packet.json"

    exit_code = main([
        "--root",
        str(tmp_path),
        "--intake-manifest",
        str(manifest),
        "--semantic-readiness",
        str(semantic),
        "--output-json",
        str(output),
        "--require-actionable",
    ])

    report = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert report["local_handoff_complete"] is True
    assert report["production_ready"] is False
    assert report["summary"]["operator_bundle_files_replacement_required"] == 1


def test_raw_evidence_operator_packet_cli_require_production_ready_returns_two(tmp_path):
    manifest, semantic = _write_inputs(tmp_path, production_ready=False)
    output = tmp_path / "packet.json"

    exit_code = main([
        "--root",
        str(tmp_path),
        "--intake-manifest",
        str(manifest),
        "--semantic-readiness",
        str(semantic),
        "--output-json",
        str(output),
        "--require-production-ready",
    ])

    assert exit_code == 2
