import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCAN_TARGET_REL_PATHS = (
    "src/network/transport/pulse_transport.py",
    "src/network/obfuscation/whitelist_mimicry.py",
    "scripts/ops/collect_ghost_pulse_local_evidence.py",
    "scripts/ops/run_ghost_pulse_profile_matrix.py",
    "scripts/ops/verify_ghost_pulse_local_evidence.py",
    "scripts/ops/verify_ghost_pulse_profile_matrix.py",
    "scripts/ops/verify_ghost_pulse_artifact_chain.py",
    "scripts/ops/verify_ghost_pulse_rng_replay.py",
    "scripts/ops/verify_ghost_pulse_verification_suite.py",
    "scripts/ops/collect_ghost_pulse_kernel_attach_evidence.py",
    "scripts/ops/collect_ghost_pulse_packet_capture_evidence.py",
    "scripts/ops/collect_ghost_pulse_baseline_comparison_evidence.py",
    "scripts/ops/scaffold_ghost_pulse_external_evidence_gaps.py",
    "scripts/ops/audit_ghost_pulse_external_evidence_gaps.py",
    "scripts/ops/import_ghost_pulse_external_evidence.py",
    "scripts/ops/verify_ghost_pulse_external_evidence_intake.py",
    "scripts/ops/verify_ghost_pulse_incoming_gap_candidates.py",
    "scripts/ops/verify_ghost_pulse_replacement_candidates.py",
    "scripts/ops/verify_ghost_pulse_external_evidence_gap_audit.py",
    "scripts/ops/verify_ghost_pulse_external_evidence.py",
    "scripts/ops/verify_ghost_pulse_external_evidence_inventory.py",
    "scripts/ops/verify_ghost_pulse_proof_gate.py",
    "scripts/ops/verify_ghost_pulse_goal_state.py",
    "scripts/ops/run_ghost_pulse_proof_gate.py",
    "scripts/ops/run_ghost_pulse_verification_suite.py",
    "docs/architecture/X0TTA6BL4_PULSE_PROTOCOL.md",
    "docs/verification/ghost-core-pulse-claim-audit-2026-05-21.md",
    "docs/verification/gemini-ghost-core-vv-audit-2026-05-20.md",
    "docs/verification/ghost-pulse-local-evidence-runbook.md",
    "docs/verification/ghost-pulse-profile-matrix-runbook.md",
    "docs/verification/GHOST_PULSE_LOCAL_EVIDENCE_LATEST.json",
    "docs/verification/GHOST_PULSE_LOCAL_EVIDENCE_LATEST.md",
    "docs/verification/GHOST_PULSE_PROFILE_MATRIX_LATEST.json",
    "docs/verification/GHOST_PULSE_PROFILE_MATRIX_LATEST.md",
    "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INVENTORY_LATEST.json",
    "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INVENTORY_LATEST.md",
    "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.json",
    "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.md",
    "docs/verification/GHOST_PULSE_INCOMING_GAP_CANDIDATES_LATEST.json",
    "docs/verification/GHOST_PULSE_INCOMING_GAP_CANDIDATES_LATEST.md",
)


def _load_module():
    path = ROOT / "scripts/ops/run_ghost_pulse_verification_suite.py"
    spec = importlib.util.spec_from_file_location("run_ghost_pulse_verification_suite", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_scan_targets(root: Path):
    for rel_path in SCAN_TARGET_REL_PATHS:
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("research draft only\n", encoding="utf-8")


def _claim_boundary(**overrides):
    boundary = {
        "stealth_verified": False,
        "whitelist_verified": False,
        "production_ready": False,
        "kernel_attach_verified": False,
        "kernel_read_only_visible": False,
    }
    boundary.update(overrides)
    return boundary


def _local_payload(**claim_overrides):
    return {
        "bundle": "docs/verification/ghost-pulse-local-evidence-fixture",
        "decision": "LOCAL_TIMING_VERIFIED_STEALTH_NOT_VERIFIED",
        "claim_boundary": _claim_boundary(**claim_overrides),
        "local_probe": {
            "mode": "corporate",
            "seed": 20260521,
            "packets_received": 2,
            "transport_stats": {
                "pulse_rng_seed": 20260521,
                "timing_plan_replay": {
                    "status": "LOCAL_SEED_REPLAYABLE",
                    "sample_count": 2,
                    "sha256": "a" * 64,
                },
            },
        },
    }


def _matrix_payload(**claim_overrides):
    return {
        "bundle": "docs/verification/ghost-pulse-profile-matrix-fixture",
        "decision": "PROFILE_MATRIX_LOCAL_VERIFIED_STEALTH_NOT_VERIFIED",
        "claim_boundary": _claim_boundary(**claim_overrides),
        "parameters": {"modes": ["corporate"], "seed": 20260522},
        "runs": [
            {
                "mode": "corporate",
                "repetition": 0,
                "seed": 20260522,
                "pulse_rng_seed": 20260522,
                "timing_plan_replay_status": "LOCAL_SEED_REPLAYABLE",
                "timing_plan_replay_sha256": "b" * 64,
            }
        ],
    }


def _write_latest(root: Path, local: dict | None = None, matrix: dict | None = None):
    verify_root = root / "docs" / "verification"
    verify_root.mkdir(parents=True)
    local_payload = local or _local_payload()
    matrix_payload = matrix or _matrix_payload()
    local_path = verify_root / "GHOST_PULSE_LOCAL_EVIDENCE_LATEST.json"
    matrix_path = verify_root / "GHOST_PULSE_PROFILE_MATRIX_LATEST.json"
    local_json = json.dumps(local_payload)
    matrix_json = json.dumps(matrix_payload)
    local_path.write_text(local_json, encoding="utf-8")
    matrix_path.write_text(matrix_json, encoding="utf-8")
    local_path.with_suffix(".md").write_text("local summary\n", encoding="utf-8")
    matrix_path.with_suffix(".md").write_text("matrix summary\n", encoding="utf-8")

    local_bundle = root / local_payload["bundle"]
    matrix_bundle = root / matrix_payload["bundle"]
    local_bundle.mkdir(parents=True)
    matrix_bundle.mkdir(parents=True)
    (local_bundle / "evidence.json").write_text(local_json, encoding="utf-8")
    (local_bundle / "summary.md").write_text("local summary\n", encoding="utf-8")
    (matrix_bundle / "matrix.json").write_text(matrix_json, encoding="utf-8")
    (matrix_bundle / "summary.md").write_text("matrix summary\n", encoding="utf-8")
    _write_scan_targets(root)
    return local_path, matrix_path


def _pass_runner(_root, args, _timeout):
    return {
        "args": args,
        "available": True,
        "returncode": 0,
        "stdout": "PASS",
        "stderr": "",
    }


def test_suite_report_passes_with_latest_artifacts_and_command_gates(tmp_path):
    suite = _load_module()
    local_path, matrix_path = _write_latest(tmp_path)

    report = suite.build_report(
        root=tmp_path,
        local_path=local_path,
        matrix_path=matrix_path,
        command_runner=_pass_runner,
    )

    assert report["decision"] == suite.DECISION_PASS
    assert report["failures"] == []
    assert report["summary"]["local"]["replay_status"] == "LOCAL_SEED_REPLAYABLE"
    assert report["summary"]["matrix"]["replayable_run_count"] == 1
    assert report["gates"]["artifact_integrity"]["status"] == "PASS"
    assert report["gates"]["incoming_gap_candidates_verifier"]["status"] == "PASS"
    assert all(gate["status"] == "PASS" for gate in report["gates"].values())


def test_suite_artifact_integrity_records_required_path_policy(tmp_path):
    suite = _load_module()
    local_path, matrix_path = _write_latest(tmp_path)
    local = json.loads(local_path.read_text(encoding="utf-8"))
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))

    report = suite.build_report(
        root=tmp_path,
        local_path=local_path,
        matrix_path=matrix_path,
        command_runner=_pass_runner,
    )
    expected_paths, policy_failures = suite.artifact_integrity_check_paths(
        tmp_path,
        local_path,
        local,
        matrix_path,
        matrix,
    )

    assert policy_failures == []
    assert report["gates"]["artifact_integrity"]["policy"] == suite.artifact_integrity_policy(
        expected_paths
    )
    assert report["gates"]["artifact_integrity"]["policy"]["mode"] == (
        "required_latest_bundle_path_pairs"
    )
    assert report["gates"]["artifact_integrity"]["policy"]["required"] is True
    assert report["gates"]["artifact_integrity"]["policy"]["check_count"] == 4


def test_suite_report_fails_closed_when_claim_boundary_is_promoted(tmp_path):
    suite = _load_module()
    local_path, matrix_path = _write_latest(
        tmp_path,
        local=_local_payload(production_ready=True),
    )

    report = suite.build_report(
        root=tmp_path,
        local_path=local_path,
        matrix_path=matrix_path,
        command_runner=_pass_runner,
    )

    assert report["decision"] == suite.DECISION_FAIL
    assert "local.claim_boundary.production_ready must be false" in report["failures"]
    assert report["claim_boundary"]["production_ready"] is False


def test_suite_false_claim_scan_detects_promoted_latest_json(tmp_path):
    suite = _load_module()
    local_path, _matrix_path = _write_latest(
        tmp_path,
        local=_local_payload(stealth_verified=True),
    )

    result = suite.scan_false_claims(tmp_path, targets=[local_path])

    assert result["status"] == "FAIL"
    assert result["matches"][0]["path"] == "docs/verification/GHOST_PULSE_LOCAL_EVIDENCE_LATEST.json"
    assert "stealth_verified" in result["matches"][0]["text"]


def test_suite_false_claim_scan_allows_proof_derived_kernel_attach_inventory(tmp_path):
    suite = _load_module()
    _write_scan_targets(tmp_path)
    inventory = tmp_path / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INVENTORY_LATEST.json"
    inventory.write_text('{"claim_boundary": {"kernel_attach_verified": true}}\n', encoding="utf-8")

    result = suite.scan_false_claims(tmp_path)

    assert result["status"] == "PASS"
    assert result["matches"] == []
    assert result["allowed_matches"][0]["path"] == (
        "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INVENTORY_LATEST.json"
    )
    assert "kernel_attach_verified" in result["allowed_matches"][0]["text"]


def test_suite_false_claim_scan_covers_operator_runbooks(tmp_path):
    suite = _load_module()
    runbook = tmp_path / "docs/verification/ghost-pulse-local-evidence-runbook.md"
    runbook.parent.mkdir(parents=True)
    runbook.write_text("Do not mark production_ready=true here.\n", encoding="utf-8")
    _write_scan_targets(tmp_path)

    result = suite.scan_false_claims(tmp_path)

    assert result["status"] == "FAIL"
    assert result["matches"][0]["path"] == "docs/verification/ghost-pulse-local-evidence-runbook.md"
    assert result["matches"][0]["text"] == "Do not mark production_ready=true here."
    assert "docs/verification/ghost-pulse-local-evidence-runbook.md" in result["targets_scanned"]
    record = next(
        item
        for item in result["target_records"]
        if item["path"] == "docs/verification/ghost-pulse-local-evidence-runbook.md"
    )
    assert record["sha256"]


def test_suite_false_claim_scan_covers_protocol_notes(tmp_path):
    suite = _load_module()
    protocol = tmp_path / "docs/architecture/X0TTA6BL4_PULSE_PROTOCOL.md"
    protocol.parent.mkdir(parents=True)
    protocol.write_text("READY FOR PRODUCTION\n", encoding="utf-8")
    _write_scan_targets(tmp_path)

    result = suite.scan_false_claims(tmp_path)

    assert result["status"] == "FAIL"
    assert result["matches"][0]["path"] == "docs/architecture/X0TTA6BL4_PULSE_PROTOCOL.md"
    assert result["matches"][0]["text"] == "READY FOR PRODUCTION"
    assert "docs/architecture/X0TTA6BL4_PULSE_PROTOCOL.md" in result["targets_scanned"]
    record = next(
        item
        for item in result["target_records"]
        if item["path"] == "docs/architecture/X0TTA6BL4_PULSE_PROTOCOL.md"
    )
    assert record["sha256"]


def test_suite_false_claim_scan_excludes_self_referential_latest_outputs(tmp_path):
    suite = _load_module()
    verify_root = tmp_path / "docs" / "verification"
    verify_root.mkdir(parents=True)
    latest_json = verify_root / "GHOST_PULSE_VERIFICATION_SUITE_LATEST.json"
    latest_md = verify_root / "GHOST_PULSE_VERIFICATION_SUITE_LATEST.md"
    latest_json.write_text('{"note": "READY FOR PRODUCTION"}\n', encoding="utf-8")
    latest_md.write_text("READY FOR PRODUCTION\n", encoding="utf-8")
    _write_scan_targets(tmp_path)

    result = suite.scan_false_claims(tmp_path)
    scanned = set(result["targets_scanned"])
    records = {record["path"] for record in result["target_records"]}

    assert result["status"] == "PASS"
    assert result["matches"] == []
    assert "docs/verification/GHOST_PULSE_VERIFICATION_SUITE_LATEST.json" not in scanned
    assert "docs/verification/GHOST_PULSE_VERIFICATION_SUITE_LATEST.md" not in scanned
    assert "docs/verification/GHOST_PULSE_VERIFICATION_SUITE_LATEST.json" not in records
    assert "docs/verification/GHOST_PULSE_VERIFICATION_SUITE_LATEST.md" not in records


def test_suite_false_claim_scan_fails_when_required_target_is_missing(tmp_path):
    suite = _load_module()
    _write_scan_targets(tmp_path)
    missing = tmp_path / "docs/verification/ghost-pulse-local-evidence-runbook.md"
    missing.unlink()

    result = suite.scan_false_claims(tmp_path)

    assert result["status"] == "FAIL"
    assert (
        "false_claim_scan target is missing: docs/verification/ghost-pulse-local-evidence-runbook.md"
        in result["failures"]
    )
    assert any(
        record["path"] == "docs/verification/ghost-pulse-local-evidence-runbook.md"
        and record["exists"] is False
        for record in result["target_records"]
    )


def test_suite_false_claim_scan_records_required_target_policy(tmp_path):
    suite = _load_module()
    _write_scan_targets(tmp_path)

    result = suite.scan_false_claims(tmp_path)

    assert result["status"] == "PASS"
    assert result["target_policy"] == suite.false_claim_target_policy()
    assert result["target_policy"]["mode"] == "required_static_rel_paths"
    assert result["target_policy"]["required"] is True
    assert result["target_policy"]["target_count"] == len(result["targets_scanned"])


def test_suite_fails_when_command_gates_are_skipped(tmp_path):
    suite = _load_module()
    local_path, matrix_path = _write_latest(tmp_path)

    report = suite.build_report(
        root=tmp_path,
        local_path=local_path,
        matrix_path=matrix_path,
        run_command_gates=False,
    )

    assert report["decision"] == suite.DECISION_FAIL
    assert "command gates were skipped" in report["failures"]
    assert report["gates"]["command_gates"]["status"] == "SKIPPED"


def test_suite_fails_when_latest_json_differs_from_bundle(tmp_path):
    suite = _load_module()
    local_path, matrix_path = _write_latest(tmp_path)
    local_path.write_text(json.dumps({**_local_payload(), "decision": "LOCAL_EVIDENCE_INCOMPLETE"}), encoding="utf-8")

    report = suite.build_report(
        root=tmp_path,
        local_path=local_path,
        matrix_path=matrix_path,
        command_runner=_pass_runner,
    )

    assert report["decision"] == suite.DECISION_FAIL
    assert report["gates"]["artifact_integrity"]["status"] == "FAIL"
    assert "local_latest_vs_bundle_json hash mismatch or missing artifact" in report["failures"]


def test_suite_writer_creates_timestamped_bundle_and_mirrors_latest(tmp_path):
    suite = _load_module()
    local_path, matrix_path = _write_latest(tmp_path)
    report = suite.build_report(
        root=tmp_path,
        local_path=local_path,
        matrix_path=matrix_path,
        command_runner=_pass_runner,
    )
    latest_json = tmp_path / "docs/verification/GHOST_PULSE_VERIFICATION_SUITE_LATEST.json"
    latest_md = tmp_path / "docs/verification/GHOST_PULSE_VERIFICATION_SUITE_LATEST.md"

    paths = suite.write_report_outputs(tmp_path, report, latest_json, latest_md)

    assert paths["bundle_dir"].name.startswith("ghost-pulse-verification-suite-")
    assert paths["bundle_json"].exists()
    assert paths["bundle_md"].exists()
    assert latest_json.read_bytes() == paths["bundle_json"].read_bytes()
    assert latest_md.read_bytes() == paths["bundle_md"].read_bytes()
    written = json.loads(latest_json.read_text(encoding="utf-8"))
    assert written["bundle"] == suite.display_path(tmp_path, paths["bundle_dir"])
    assert written["artifacts"]["suite_bundle_json"] == suite.display_path(
        tmp_path,
        paths["bundle_json"],
    )
