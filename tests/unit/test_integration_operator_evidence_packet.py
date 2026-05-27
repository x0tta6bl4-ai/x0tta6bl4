import json
from pathlib import Path

from src.integration.operator_evidence_packet import PacketInputs, build_packet, build_packet_index, main


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _inputs(root: Path) -> PacketInputs:
    return PacketInputs(
        root=root,
        gap_index_path=root / "gap.json",
        source_candidate_path=root / "source.json",
        next_inputs_path=root / "next.json",
        replacement_passport_path=root / "passport.json",
    )


def _write_external_settlement_route(root: Path) -> None:
    _write_json(
        root / "source.json",
        {
            "evidence_source_routes": [
                {
                    "evidence_key": "external_settlement",
                    "kind": "external_settlement",
                    "required_artifact_path": ".tmp/external-settlement-evidence/settlement-submit.json",
                    "required_operator_action": "submit or locate real X0T settlement",
                    "source_candidates": [
                        {
                            "source_id": "required_artifact:external_settlement",
                            "not_ready_reasons": ["retained submitted settlement receipt is missing"],
                        }
                    ],
                }
            ]
        },
    )
    _write_json(
        root / "next.json",
        {
            "required_inputs": [
                {
                    "evidence_key": "external_settlement",
                    "operator_action": "submit or locate real X0T settlement",
                }
            ]
        },
    )


def _write_integration_entrypoints(root: Path) -> None:
    module_dir = root / "src/integration"
    module_dir.mkdir(parents=True, exist_ok=True)
    for name in [
        "external_settlement",
        "evidence_source_candidates",
        "operator_bundle_identity",
        "rollout_provenance",
        "production_evidence_replacement_passport",
        "production_evidence_intake",
        "production_input_return_acceptance",
        "production_input_pipeline",
        "production_closeout_review",
        "completion_audit",
        "production_gap_index",
    ]:
        (module_dir / f"{name}.py").write_text("", encoding="utf-8")
    script_dir = root / "scripts/ops"
    script_dir.mkdir(parents=True, exist_ok=True)
    for script in [
        "scaffold_x0t_external_settlement_evidence.py",
        "verify_x0t_external_settlement_evidence.py",
        "verify_x0t_external_settlement_live_rpc.py",
    ]:
        (script_dir / script).write_text("", encoding="utf-8")


def _write_ops_entrypoints(root: Path) -> None:
    scripts = [
        "collect_zero_trust_pqc_evidence_bundle.py",
        "verify_zero_trust_pqc_evidence_gate.py",
        "collect_self_healing_pqc_mesh_evidence_bundle.py",
        "verify_self_healing_pqc_mesh_evidence_gate.py",
        "collect_paid_client_serviceability_evidence_bundle.py",
        "verify_paid_client_serviceability_evidence_gate.py",
        "scaffold_x0t_external_settlement_evidence.py",
        "verify_x0t_external_settlement_evidence.py",
        "verify_x0t_external_settlement_live_rpc.py",
        "generate_production_raw_evidence_template_pack.py",
        "collect_live_rollout_evidence_bundle.py",
        "verify_live_rollout_evidence_gate.py",
        "scaffold_live_rollout_image_provenance_evidence.py",
        "apply_operator_bundle_identity_patch.py",
    ]
    script_dir = root / "scripts/ops"
    script_dir.mkdir(parents=True, exist_ok=True)
    for script in scripts:
        (script_dir / script).write_text("", encoding="utf-8")


def _write_common(root: Path, *, key: str) -> None:
    _write_json(
        root / "gap.json",
        {
            "decision": "BLOCKED_ON_OPERATOR_EVIDENCE",
            "operator_priority_order": [key],
            "summary": {"primary_blocker_evidence_key": key},
            "evidence_gaps": [
                {
                    "evidence_key": key,
                    "blocker_class": "MISSING_SOURCE_ARTIFACT" if key == "external_settlement" else "SOURCE_ARTIFACT_BLOCKED",
                    "source_artifact_path": ".tmp/external-settlement-evidence/settlement-submit.json"
                    if key == "external_settlement"
                    else ".tmp/validation-shards/zero-trust-pqc-evidence-gate-current.json",
                    "top_errors": ["artifact missing"] if key == "external_settlement" else ["gate blocked"],
                    "raw_paths_to_replace": [".tmp/zero-trust-pqc-raw-evidence/operator-manifest.json"],
                    "operator_action": "provide production evidence",
                }
            ],
        },
    )


def test_operator_packet_uses_existing_external_settlement_verifier(tmp_path):
    _write_common(tmp_path, key="external_settlement")
    _write_external_settlement_route(tmp_path)
    (tmp_path / "src/integration").mkdir(parents=True)
    (tmp_path / "src/integration/external_settlement.py").write_text("", encoding="utf-8")

    report = build_packet(_inputs(tmp_path))

    assert report["decision"] == "OPERATOR_ACTION_REQUIRED"
    assert report["selected_evidence_key"] == "external_settlement"
    packet = report["packet"]
    assert packet["packet_kind"] == "external_settlement"
    assert any("transaction_hash" in field for field in packet["required_fields"])
    assert any("X0T_DESTINATION_CHAIN" in command["command"] for command in packet["commands"])
    assert any("X0T_DESTINATION_CHAIN='<base-sepolia|base|base-mainnet>'" in command["command"] for command in packet["commands"])
    assert any("--preflight-capture-inputs" in command["command"] for command in packet["commands"])
    assert any("scaffold_x0t_external_settlement_evidence.py" in command["command"] for command in packet["commands"])
    assert any("production_evidence_replacement_passport" in command["command"] for command in packet["commands"])
    assert any("production_input_return_acceptance" in command["command"] for command in packet["commands"])
    assert any("production_input_pipeline" in command["command"] for command in packet["commands"])
    assert any("production_closeout_review" in command["command"] for command in packet["commands"])
    assert any("verify_x0t_external_settlement_evidence.py" in command["command"] for command in packet["commands"])
    assert any("verify_x0t_external_settlement_live_rpc.py" in command["command"] for command in packet["commands"])
    assert any("verify_x0t_external_settlement_evidence.py reports READY" in check for check in packet["acceptance_checks"])
    assert any("verify_x0t_external_settlement_live_rpc.py reports READY" in check for check in packet["acceptance_checks"])
    assert any("PRODUCTION_EVIDENCE_REPLACEMENT_PASSPORT_CLEAR" in check for check in packet["acceptance_checks"])
    assert any("READY_FOR_PRODUCTION_CLOSEOUT_REVIEW" in check for check in packet["acceptance_checks"])
    assert any("scaffold templates" in rule for rule in packet["fail_closed_rules"])
    verifier = [command for command in packet["commands"] if "src.integration.external_settlement" in command["command"]][0]
    assert verifier["existing_entrypoint"] is True
    assert "--destination-chain \"$X0T_DESTINATION_CHAIN\"" in verifier["command"]
    assert "--destination-chain base-sepolia" not in verifier["command"]
    assert not any("collect_x0t_external_settlement_evidence.py" in command["command"] for command in packet["commands"])


def test_operator_packet_lists_raw_bundle_files_and_fail_closed_rules(tmp_path):
    _write_common(tmp_path, key="live_spire_mtls")
    _write_json(
        tmp_path / "source.json",
        {
            "evidence_source_routes": [
                {
                    "evidence_key": "live_spire_mtls",
                    "kind": "raw_evidence",
                    "operator_bundle_paths": [
                        ".tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/operator-manifest.json",
                        ".tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/mtls-fail-closed.json",
                    ],
                    "raw_paths": [
                        ".tmp/zero-trust-pqc-raw-evidence/operator-manifest.json",
                        ".tmp/zero-trust-pqc-raw-evidence/mtls-fail-closed.json",
                    ],
                    "source_candidates": [
                        {
                            "source_id": "operator_bundle:zero-trust-pqc",
                            "not_ready_reasons": ["production_ready must be true"],
                            "file_reports": [
                                {
                                    "artifact_path": ".tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/operator-manifest.json",
                                    "available": True,
                                    "manifest_collector_id": "zero-trust-pqc",
                                    "manifest_raw_id": "zero-trust-pqc/operator-manifest.json",
                                    "manifest_file_name": "operator-manifest.json",
                                    "evidence_collector_id": None,
                                    "evidence_raw_id": "zero-trust-pqc/operator-manifest.json",
                                    "evidence_file_name": "operator-manifest.json",
                                    "collector_id_matches_manifest": False,
                                    "raw_id_matches_manifest": True,
                                    "file_name_matches_manifest": True,
                                }
                            ],
                        }
                    ],
                }
            ]
        },
    )
    _write_json(
        tmp_path / "next.json",
        {
            "required_inputs": [
                {
                    "evidence_key": "live_spire_mtls",
                    "collector_command": "python3 scripts/ops/collect_zero_trust_pqc_evidence_bundle.py --require-ready",
                    "verification_command": "python3 scripts/ops/verify_zero_trust_pqc_evidence_gate.py --require-ready",
                }
            ]
        },
    )
    _write_json(
        tmp_path / "passport.json",
        {
            "status": "VERIFIED HERE",
            "ok": True,
            "required_evidence_files": [
                {
                    "item_id": "01:raw_evidence:live_spire_mtls:zero-trust-pqc/operator-manifest.json",
                    "kind": "raw_evidence",
                    "evidence_key": "live_spire_mtls",
                    "raw_id": "zero-trust-pqc/operator-manifest.json",
                    "ready": False,
                    "blocks_production": True,
                    "current_status": "LOCAL_OBSERVATION",
                    "replacement_status": "BLOCKED_LOCAL_OBSERVATION_REPLACEMENT_REQUIRED",
                    "operator_return_path": ".tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/operator-manifest.json",
                    "retained_destination_path": ".tmp/zero-trust-pqc-raw-evidence/operator-manifest.json",
                    "required_action": "replace local observation with retained production JSON",
                    "required_statuses": ["VERIFIED HERE"],
                    "required_operator_provenance_fields": ["collected_at", "collected_by", "source_commands"],
                    "required_hash_binding_fields": ["evidence_root", "evidence_files[].sha256"],
                    "production_evidence_requirements": ["operator-manifest environment must be production"],
                    "semantic_json_pointers": ["/environment"],
                    "validation_commands": ["python3 scripts/ops/import_production_raw_evidence_bundle.py --require-ready"],
                    "objective_blocking_row_ids": ["goal_audit:production_evidence_import"],
                }
            ],
        },
    )

    report = build_packet(_inputs(tmp_path))

    packet = report["packet"]
    assert packet["packet_kind"] == "raw_production_bundle"
    assert [item["path"] for item in packet["required_artifacts"]] == [
        ".tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/operator-manifest.json",
        ".tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/mtls-fail-closed.json",
    ]
    assert "production_ready == true" in packet["required_fields"]
    assert any("Do not promote local" in rule for rule in packet["fail_closed_rules"])
    assert any("raw evidence template pack" in rule for rule in packet["fail_closed_rules"])
    assert any("generate_production_raw_evidence_template_pack.py" in command["command"] for command in packet["commands"])
    assert any("operator_bundle_identity" in command["command"] for command in packet["commands"])
    assert any("apply_operator_bundle_identity_patch.py" in command["command"] for command in packet["commands"])
    assert any(
        "apply_operator_bundle_identity_patch.py" in command["command"]
        and " --apply" not in command["command"]
        for command in packet["commands"]
    )
    assert any(
        "apply_operator_bundle_identity_patch.py" in command["command"]
        and " --apply" in command["command"]
        for command in packet["commands"]
    )
    assert any("production_evidence_replacement_passport" in command["command"] for command in packet["commands"])
    assert any("production_input_return_acceptance" in command["command"] for command in packet["commands"])
    assert any("production_input_pipeline" in command["command"] for command in packet["commands"])
    assert any("production_closeout_review" in command["command"] for command in packet["commands"])
    assert any("production_gap_index" in command["command"] for command in packet["commands"])
    assert any("OPERATOR_BUNDLE_IDENTITY_CLEAN" in check for check in packet["acceptance_checks"])
    assert any("PRODUCTION_EVIDENCE_REPLACEMENT_PASSPORT_CLEAR" in check for check in packet["acceptance_checks"])
    assert any("READY_FOR_PRODUCTION_CLOSEOUT_REVIEW" in check for check in packet["acceptance_checks"])
    assert packet["identity_updates_total"] == 1
    assert packet["identity_update_plan"] == [
        {
            "path": ".tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/operator-manifest.json",
            "available": True,
            "suggested_fields": {
                "collector_id": "zero-trust-pqc",
                "raw_id": "zero-trust-pqc/operator-manifest.json",
                "file_name": "operator-manifest.json",
            },
            "current_fields": {
                "collector_id": None,
                "raw_id": "zero-trust-pqc/operator-manifest.json",
                "file_name": "operator-manifest.json",
            },
            "identity_mismatch_fields": ["collector_id"],
            "json_merge_patch": {
                "collector_id": "zero-trust-pqc",
                "raw_id": "zero-trust-pqc/operator-manifest.json",
                "file_name": "operator-manifest.json",
            },
            "json_patch_operations": [
                {"op": "add", "path": "/collector_id", "value": "zero-trust-pqc"},
            ],
        }
    ]
    assert packet["replacement_passport_summary"] == {
        "items_total": 1,
        "items_ready": 0,
        "items_blocking": 1,
        "semantic_json_pointers_total": 1,
        "production_evidence_requirements_total": 1,
    }
    assert packet["replacement_passport_items"][0]["evidence_key"] == "live_spire_mtls"
    assert packet["replacement_passport_items"][0]["semantic_json_pointers"] == ["/environment"]
    assert packet["replacement_passport_items"][0]["production_evidence_requirements"] == [
        "operator-manifest environment must be production"
    ]


def test_operator_packet_cli_writes_json_and_markdown(tmp_path):
    _write_common(tmp_path, key="external_settlement")
    _write_json(tmp_path / "source.json", {"evidence_source_routes": [{"evidence_key": "external_settlement"}]})
    _write_json(tmp_path / "next.json", {"required_inputs": [{"evidence_key": "external_settlement"}]})

    output_json = tmp_path / "packet.json"
    output_md = tmp_path / "packet.md"
    exit_code = main([
        "--root",
        str(tmp_path),
        "--gap-index",
        "gap.json",
        "--source-candidate-audit",
        "source.json",
        "--next-inputs",
        "next.json",
        "--output-json",
        str(output_json),
        "--output-md",
        str(output_md),
    ])

    assert exit_code == 0
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["selected_evidence_key"] == "external_settlement"
    assert "Selected evidence key" in output_md.read_text(encoding="utf-8")


def test_operator_packet_require_actionable_succeeds_when_all_entrypoints_exist(tmp_path):
    _write_common(tmp_path, key="external_settlement")
    _write_external_settlement_route(tmp_path)
    _write_integration_entrypoints(tmp_path)
    _write_ops_entrypoints(tmp_path)

    output_json = tmp_path / "packet.json"
    exit_code = main([
        "--root",
        str(tmp_path),
        "--gap-index",
        "gap.json",
        "--source-candidate-audit",
        "source.json",
        "--next-inputs",
        "next.json",
        "--output-json",
        str(output_json),
        "--require-actionable",
    ])

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["actionable"] is True
    assert payload["summary"]["commands_missing_entrypoints"] == 0


def test_operator_packet_require_actionable_returns_two_for_missing_entrypoints(tmp_path):
    _write_common(tmp_path, key="external_settlement")
    _write_external_settlement_route(tmp_path)

    output_json = tmp_path / "packet.json"
    exit_code = main([
        "--root",
        str(tmp_path),
        "--gap-index",
        "gap.json",
        "--source-candidate-audit",
        "source.json",
        "--next-inputs",
        "next.json",
        "--output-json",
        str(output_json),
        "--require-actionable",
    ])

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert payload["actionable"] is False
    assert payload["summary"]["commands_missing_entrypoints"] > 0


def test_operator_packet_covers_all_blocking_evidence_keys(tmp_path):
    keys = [
        "external_settlement",
        "live_spire_mtls",
        "multi_host_mesh",
        "paid_client_path",
        "safe_rollout_rollback",
    ]
    _write_json(
        tmp_path / "gap.json",
        {
            "decision": "BLOCKED_ON_OPERATOR_EVIDENCE",
            "operator_priority_order": keys,
            "blocking_evidence_keys": keys,
            "summary": {
                "primary_blocker_evidence_key": "external_settlement",
                "pending_evidence_keys": len(keys),
            },
            "evidence_gaps": [
                {
                    "evidence_key": key,
                    "blocker_class": "MISSING_SOURCE_ARTIFACT"
                    if key == "external_settlement"
                    else "SOURCE_ARTIFACT_BLOCKED",
                    "source_artifact_path": f".tmp/{key}.json",
                    "top_errors": [f"{key} blocked"],
                    "raw_paths_to_replace": [f".tmp/raw/{key}.json"],
                    "operator_action": "provide production evidence",
                }
                for key in keys
            ],
        },
    )
    _write_json(
        tmp_path / "source.json",
        {
            "evidence_source_routes": [
                {
                    "evidence_key": "external_settlement",
                    "kind": "external_settlement",
                    "required_artifact_path": ".tmp/external-settlement-evidence/settlement-submit.json",
                    "source_candidates": [
                        {"source_id": "required_artifact:external_settlement", "not_ready_reasons": ["missing receipt"]}
                    ],
                },
                {
                    "evidence_key": "live_spire_mtls",
                    "kind": "raw_evidence",
                    "operator_bundle_paths": [".tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/operator-manifest.json"],
                    "raw_paths": [".tmp/zero-trust-pqc-raw-evidence/operator-manifest.json"],
                    "source_candidates": [{"not_ready_reasons": ["production_ready must be true"]}],
                },
                {
                    "evidence_key": "multi_host_mesh",
                    "kind": "raw_evidence",
                    "operator_bundle_paths": [".tmp/production-raw-evidence-operator-bundle/self-healing-pqc-mesh/operator-manifest.json"],
                    "raw_paths": [".tmp/self-healing-pqc-mesh-raw-evidence/operator-manifest.json"],
                    "source_candidates": [{"not_ready_reasons": ["production_ready must be true"]}],
                },
                {
                    "evidence_key": "paid_client_path",
                    "kind": "raw_evidence",
                    "operator_bundle_paths": [".tmp/production-raw-evidence-operator-bundle/paid-client-serviceability/operator-manifest.json"],
                    "raw_paths": [".tmp/paid-client-serviceability-raw-evidence/operator-manifest.json"],
                    "source_candidates": [{"not_ready_reasons": ["production_ready must be true"]}],
                },
                {
                    "evidence_key": "safe_rollout_rollback",
                    "kind": "raw_evidence",
                    "operator_bundle_paths": [".tmp/production-raw-evidence-operator-bundle/live-rollout/operator-manifest.json"],
                    "raw_paths": [".tmp/live-rollout-raw-evidence/operator-manifest.json"],
                    "source_candidates": [{"not_ready_reasons": ["production_ready must be true"]}],
                },
            ]
        },
    )
    _write_json(
        tmp_path / "next.json",
        {
            "required_inputs": [
                {
                    "evidence_key": "external_settlement",
                    "operator_action": "submit or locate real X0T settlement",
                },
                {
                    "evidence_key": "live_spire_mtls",
                    "collector_command": "python3 scripts/ops/collect_zero_trust_pqc_evidence_bundle.py --require-ready",
                    "verification_command": "python3 scripts/ops/verify_zero_trust_pqc_evidence_gate.py --require-ready",
                },
                {
                    "evidence_key": "multi_host_mesh",
                    "collector_command": "python3 scripts/ops/collect_self_healing_pqc_mesh_evidence_bundle.py --require-ready",
                    "verification_command": "python3 scripts/ops/verify_self_healing_pqc_mesh_evidence_gate.py --require-ready",
                },
                {
                    "evidence_key": "paid_client_path",
                    "collector_command": "python3 scripts/ops/collect_paid_client_serviceability_evidence_bundle.py --require-ready",
                    "verification_command": "python3 scripts/ops/verify_paid_client_serviceability_evidence_gate.py --require-ready",
                },
                {
                    "evidence_key": "safe_rollout_rollback",
                    "collector_command": "python3 scripts/ops/collect_live_rollout_evidence_bundle.py --require-ready",
                    "verification_command": "python3 scripts/ops/verify_live_rollout_evidence_gate.py --require-ready",
                },
            ]
        },
    )
    _write_integration_entrypoints(tmp_path)
    _write_ops_entrypoints(tmp_path)

    report = build_packet(_inputs(tmp_path))

    assert report["selected_evidence_key"] == "external_settlement"
    assert [entry["evidence_key"] for entry in report["all_blocker_packets"]] == keys
    assert report["summary"]["blocker_packets_total"] == 5
    assert report["summary"]["blocker_packets_actionable"] == 5
    assert report["summary"]["blocker_commands_missing_entrypoints"] == 0
    packet_kinds = {
        entry["evidence_key"]: entry["packet"]["packet_kind"]
        for entry in report["all_blocker_packets"]
    }
    assert packet_kinds["external_settlement"] == "external_settlement"
    assert packet_kinds["live_spire_mtls"] == "raw_production_bundle"
    raw_packets = [
        entry["packet"]
        for entry in report["all_blocker_packets"]
        if entry["packet"]["packet_kind"] == "raw_production_bundle"
    ]
    assert all(
        any("generate_production_raw_evidence_template_pack.py" in command["command"] for command in packet["commands"])
        for packet in raw_packets
    )
    assert all(
        any("raw evidence template pack" in rule for rule in packet["fail_closed_rules"])
        for packet in raw_packets
    )
    assert all(
        any("production environment identifier" in value for value in packet["required_operator_inputs"])
        and any("source_commands" in value for value in packet["required_operator_inputs"])
        and any("production_ready == true" in value for value in packet["required_fields"])
        and any("template/mock/placeholder markers" in value for value in packet["required_fields"])
        for packet in raw_packets
    )
    assert all(
        any(
            "apply_operator_bundle_identity_patch.py" in command["command"]
            and " --apply" not in command["command"]
            for command in packet["commands"]
        )
        for packet in raw_packets
    )
    assert all(
        any(
            "apply_operator_bundle_identity_patch.py" in command["command"]
            and " --apply" in command["command"]
            for command in packet["commands"]
        )
        for packet in raw_packets
    )
    assert all(
        any("production_input_return_acceptance" in command["command"] for command in entry["packet"]["commands"])
        for entry in report["all_blocker_packets"]
    )
    assert all(
        any("production_input_pipeline" in command["command"] for command in entry["packet"]["commands"])
        for entry in report["all_blocker_packets"]
    )
    assert all(
        any("production_closeout_review" in command["command"] for command in entry["packet"]["commands"])
        for entry in report["all_blocker_packets"]
    )
    safe_rollout_packet = next(
        entry["packet"]
        for entry in report["all_blocker_packets"]
        if entry["evidence_key"] == "safe_rollout_rollback"
    )
    assert any("src.integration.rollout_provenance" in command["command"] for command in safe_rollout_packet["commands"])
    assert any(
        "scaffold_live_rollout_image_provenance_evidence.py" in command["command"]
        for command in safe_rollout_packet["commands"]
    )
    assert any("READY_TO_CLOSE" in check for check in safe_rollout_packet["acceptance_checks"])
    assert any("digest-pinned Helm" in value for value in safe_rollout_packet["required_operator_inputs"])
    assert any("scaffold templates" in rule for rule in safe_rollout_packet["fail_closed_rules"])


def test_operator_packet_index_reports_missing_entrypoints_by_blocker(tmp_path):
    _write_json(
        tmp_path / "gap.json",
        {
            "decision": "BLOCKED_ON_OPERATOR_EVIDENCE",
            "operator_priority_order": ["external_settlement", "live_spire_mtls"],
            "summary": {"primary_blocker_evidence_key": "external_settlement"},
            "evidence_gaps": [
                {
                    "evidence_key": "external_settlement",
                    "blocker_class": "MISSING_SOURCE_ARTIFACT",
                    "source_artifact_path": ".tmp/external-settlement-evidence/settlement-submit.json",
                },
                {
                    "evidence_key": "live_spire_mtls",
                    "blocker_class": "SOURCE_ARTIFACT_BLOCKED",
                    "source_artifact_path": ".tmp/validation-shards/zero-trust-pqc-evidence-gate-current.json",
                },
            ],
        },
    )
    _write_json(
        tmp_path / "source.json",
        {
            "evidence_source_routes": [
                {"evidence_key": "external_settlement", "kind": "external_settlement"},
                {
                    "evidence_key": "live_spire_mtls",
                    "kind": "raw_evidence",
                    "operator_bundle_paths": [".tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/operator-manifest.json"],
                    "source_candidates": [
                        {
                            "source_id": "operator_bundle:zero-trust-pqc",
                            "file_reports": [
                                {
                                    "artifact_path": ".tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/operator-manifest.json",
                                    "available": True,
                                    "manifest_collector_id": "zero-trust-pqc",
                                    "manifest_raw_id": "zero-trust-pqc/operator-manifest.json",
                                    "manifest_file_name": "operator-manifest.json",
                                    "evidence_collector_id": None,
                                    "evidence_raw_id": "zero-trust-pqc/operator-manifest.json",
                                    "evidence_file_name": "operator-manifest.json",
                                    "collector_id_matches_manifest": False,
                                    "raw_id_matches_manifest": True,
                                    "file_name_matches_manifest": True,
                                }
                            ],
                        }
                    ],
                },
            ]
        },
    )
    _write_json(
        tmp_path / "next.json",
        {
            "required_inputs": [
                {"evidence_key": "external_settlement"},
                {
                    "evidence_key": "live_spire_mtls",
                    "collector_command": "python3 scripts/ops/collect_zero_trust_pqc_evidence_bundle.py --require-ready",
                    "verification_command": "python3 scripts/ops/verify_zero_trust_pqc_evidence_gate.py --require-ready",
                },
            ]
        },
    )
    _write_integration_entrypoints(tmp_path)

    report = build_packet_index(_inputs(tmp_path))

    assert report["decision"] == "OPERATOR_PACKET_ENTRYPOINTS_MISSING"
    assert report["all_packets_actionable"] is False
    assert report["summary"]["packets_total"] == 2
    assert report["summary"]["actionable_packets"] == 1
    assert report["summary"]["required_artifacts_total"] == 5
    assert report["summary"]["missing_required_artifacts_total"] == 5
    assert report["summary"]["missing_local_required_artifacts_total"] == 3
    assert report["summary"]["missing_operator_required_artifacts_total"] == 2
    assert report["local_handoff_complete"] is False
    assert any("missing local verification artifacts" in item for item in report["not_verified_yet"])
    assert any("operator production evidence artifacts" in item for item in report["not_verified_yet"])
    external = [item for item in report["packet_summaries"] if item["evidence_key"] == "external_settlement"][0]
    assert any("transaction hash" in value for value in external["required_operator_inputs"])
    assert any("read-only RPC URL" in value for value in external["required_operator_inputs"])
    assert any("transaction_hash" in value for value in external["required_fields"])
    assert any("packet_hash" in value for value in external["required_fields"])
    assert external["missing_operator_required_artifact_paths"] == [
        ".tmp/external-settlement-evidence/settlement-submit.json"
    ]
    assert external["missing_local_required_artifacts_total"] == 3
    live_spire = [item for item in report["packet_summaries"] if item["evidence_key"] == "live_spire_mtls"][0]
    assert live_spire["commands_missing_entrypoints"] == 5
    assert any("collect_zero_trust_pqc" in command for command in live_spire["missing_entrypoint_commands"])
    assert any("generate_production_raw_evidence_template_pack.py" in command for command in live_spire["missing_entrypoint_commands"])
    assert any("apply_operator_bundle_identity_patch.py" in command for command in live_spire["missing_entrypoint_commands"])
    assert any("apply_operator_bundle_identity_patch.py" in command and " --apply" not in command for command in live_spire["missing_entrypoint_commands"])
    assert any("apply_operator_bundle_identity_patch.py" in command and " --apply" in command for command in live_spire["missing_entrypoint_commands"])
    assert live_spire["missing_required_artifact_paths"] == [
        ".tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/operator-manifest.json"
    ]
    assert live_spire["missing_local_required_artifact_paths"] == []
    assert live_spire["missing_operator_required_artifact_paths"] == [
        ".tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/operator-manifest.json"
    ]
    assert any("READY_TO_INSTALL" in check for check in live_spire["acceptance_checks"])
    assert any("Do not promote local" in rule for rule in live_spire["fail_closed_rules"])
    assert any("collect_zero_trust_pqc" in command["command"] for command in live_spire["commands"])
    assert live_spire["identity_updates_total"] == 1
    assert live_spire["identity_update_plan"][0]["suggested_fields"]["collector_id"] == "zero-trust-pqc"
    assert live_spire["identity_update_plan"][0]["json_patch_operations"] == [
        {"op": "add", "path": "/collector_id", "value": "zero-trust-pqc"},
    ]


def test_operator_packet_index_cli_require_all_actionable_returns_two(tmp_path):
    _write_common(tmp_path, key="live_spire_mtls")
    _write_json(
        tmp_path / "source.json",
        {
            "evidence_source_routes": [
                {
                    "evidence_key": "live_spire_mtls",
                    "kind": "raw_evidence",
                    "operator_bundle_paths": [".tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/operator-manifest.json"],
                }
            ]
        },
    )
    _write_json(
        tmp_path / "next.json",
        {
            "required_inputs": [
                {
                    "evidence_key": "live_spire_mtls",
                    "collector_command": "python3 scripts/ops/collect_zero_trust_pqc_evidence_bundle.py --require-ready",
                    "verification_command": "python3 scripts/ops/verify_zero_trust_pqc_evidence_gate.py --require-ready",
                }
            ]
        },
    )

    output_json = tmp_path / "packet-index.json"
    exit_code = main([
        "--root",
        str(tmp_path),
        "--gap-index",
        "gap.json",
        "--source-candidate-audit",
        "source.json",
        "--next-inputs",
        "next.json",
        "--all-blockers",
        "--output-json",
        str(output_json),
        "--require-all-actionable",
    ])

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert payload["all_packets_actionable"] is False
    assert payload["summary"]["packets_with_missing_entrypoints"] == 1
