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


def _load_script(name: str, rel_path: str):
    path = ROOT / rel_path
    spec = importlib.util.spec_from_file_location(name, path)
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


def _claim_boundary():
    return {
        "stealth_verified": False,
        "whitelist_verified": False,
        "production_ready": False,
        "kernel_attach_verified": False,
        "kernel_read_only_visible": False,
    }


def _write_source_latest(root: Path):
    verify_root = root / "docs" / "verification"
    verify_root.mkdir(parents=True)

    local_payload = {
        "bundle": "docs/verification/ghost-pulse-local-evidence-fixture",
        "decision": "LOCAL_TIMING_VERIFIED_STEALTH_NOT_VERIFIED",
        "claim_boundary": _claim_boundary(),
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
    matrix_payload = {
        "bundle": "docs/verification/ghost-pulse-profile-matrix-fixture",
        "decision": "PROFILE_MATRIX_LOCAL_VERIFIED_STEALTH_NOT_VERIFIED",
        "claim_boundary": _claim_boundary(),
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

    local_json = json.dumps(local_payload)
    matrix_json = json.dumps(matrix_payload)
    local_path = verify_root / "GHOST_PULSE_LOCAL_EVIDENCE_LATEST.json"
    matrix_path = verify_root / "GHOST_PULSE_PROFILE_MATRIX_LATEST.json"
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


def _write_suite_fixture(root: Path):
    suite_runner = _load_script(
        "run_ghost_pulse_verification_suite",
        "scripts/ops/run_ghost_pulse_verification_suite.py",
    )
    local_path, matrix_path = _write_source_latest(root)
    report = suite_runner.build_report(
        root=root,
        local_path=local_path,
        matrix_path=matrix_path,
        command_runner=_pass_runner,
    )
    latest_json = root / "docs/verification/GHOST_PULSE_VERIFICATION_SUITE_LATEST.json"
    latest_md = root / "docs/verification/GHOST_PULSE_VERIFICATION_SUITE_LATEST.md"
    return suite_runner.write_report_outputs(root, report, latest_json, latest_md)


def test_suite_self_verifier_accepts_consistent_report(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_verification_suite",
        "scripts/ops/verify_ghost_pulse_verification_suite.py",
    )
    paths = _write_suite_fixture(tmp_path)

    assert verifier.verify_suite(paths["latest_json"], tmp_path) == []


def test_suite_self_verifier_rejects_promoted_claim_boundary(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_verification_suite_promoted",
        "scripts/ops/verify_ghost_pulse_verification_suite.py",
    )
    paths = _write_suite_fixture(tmp_path)
    payload = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
    payload["claim_boundary"]["production_ready"] = True
    paths["latest_json"].write_text(json.dumps(payload), encoding="utf-8")

    failures = verifier.verify_suite(paths["latest_json"], tmp_path)

    assert "claim_boundary.production_ready must be false" in failures


def test_suite_self_verifier_rejects_latest_bundle_mismatch(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_verification_suite_mismatch",
        "scripts/ops/verify_ghost_pulse_verification_suite.py",
    )
    paths = _write_suite_fixture(tmp_path)
    paths["latest_md"].write_text("tampered summary\n", encoding="utf-8")

    failures = verifier.verify_suite(paths["latest_json"], tmp_path)

    assert "suite_latest_md does not mirror suite_bundle_md" in failures


def test_suite_self_verifier_rejects_missing_false_claim_scan_target(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_verification_suite_scan_target",
        "scripts/ops/verify_ghost_pulse_verification_suite.py",
    )
    paths = _write_suite_fixture(tmp_path)
    payload = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
    targets = payload["gates"]["false_claim_scan"]["targets_scanned"]
    targets.remove("docs/verification/GHOST_PULSE_LOCAL_EVIDENCE_LATEST.json")
    paths["latest_json"].write_text(json.dumps(payload), encoding="utf-8")

    failures = verifier.verify_suite(paths["latest_json"], tmp_path)

    assert (
        "false_claim_scan missing target: docs/verification/GHOST_PULSE_LOCAL_EVIDENCE_LATEST.json"
        in failures
    )


def test_suite_self_verifier_rejects_false_claim_scan_failures(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_verification_suite_scan_failures",
        "scripts/ops/verify_ghost_pulse_verification_suite.py",
    )
    paths = _write_suite_fixture(tmp_path)
    payload = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
    payload["gates"]["false_claim_scan"]["failures"] = [
        "false_claim_scan target is missing: docs/verification/example.md"
    ]
    paths["latest_json"].write_text(json.dumps(payload), encoding="utf-8")

    failures = verifier.verify_suite(paths["latest_json"], tmp_path)

    assert "false_claim_scan failures must be empty" in failures


def test_suite_self_verifier_rejects_false_claim_target_policy_tamper(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_verification_suite_scan_policy",
        "scripts/ops/verify_ghost_pulse_verification_suite.py",
    )
    paths = _write_suite_fixture(tmp_path)
    payload = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
    payload["gates"]["false_claim_scan"]["target_policy"]["target_count"] += 1
    paths["latest_json"].write_text(json.dumps(payload), encoding="utf-8")

    failures = verifier.verify_suite(paths["latest_json"], tmp_path)

    assert "false_claim_scan target_policy does not match expected policy" in failures


def test_suite_self_verifier_rejects_artifact_integrity_policy_tamper(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_verification_suite_artifact_policy",
        "scripts/ops/verify_ghost_pulse_verification_suite.py",
    )
    paths = _write_suite_fixture(tmp_path)
    payload = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
    payload["gates"]["artifact_integrity"]["policy"]["sha256"] = "0" * 64
    paths["latest_json"].write_text(json.dumps(payload), encoding="utf-8")

    failures = verifier.verify_suite(paths["latest_json"], tmp_path)

    assert "artifact_integrity policy does not match expected policy" in failures


def test_suite_self_verifier_computes_artifact_policy_locally(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_verification_suite_local_artifact_policy",
        "scripts/ops/verify_ghost_pulse_verification_suite.py",
    )
    paths = _write_suite_fixture(tmp_path)
    payload = json.loads(paths["latest_json"].read_text(encoding="utf-8"))

    expected_checks, failures = verifier.expected_artifact_integrity_checks(tmp_path, payload)
    expected_policy = verifier.expected_artifact_integrity_policy(expected_checks)

    assert failures == []
    assert expected_policy == payload["gates"]["artifact_integrity"]["policy"]
    assert expected_policy["mode"] == "required_latest_bundle_path_pairs"
    assert expected_policy["required"] is True
    assert expected_policy["check_count"] == 4


def test_suite_self_verifier_rejects_missing_false_claim_target_record(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_verification_suite_scan_record",
        "scripts/ops/verify_ghost_pulse_verification_suite.py",
    )
    paths = _write_suite_fixture(tmp_path)
    payload = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
    records = payload["gates"]["false_claim_scan"]["target_records"]
    payload["gates"]["false_claim_scan"]["target_records"] = [
        record
        for record in records
        if record["path"] != "docs/verification/GHOST_PULSE_LOCAL_EVIDENCE_LATEST.json"
    ]
    paths["latest_json"].write_text(json.dumps(payload), encoding="utf-8")

    failures = verifier.verify_suite(paths["latest_json"], tmp_path)

    assert (
        "false_claim_scan target record is missing: docs/verification/GHOST_PULSE_LOCAL_EVIDENCE_LATEST.json"
        in failures
    )


def test_suite_self_verifier_rejects_unexpected_false_claim_scan_target(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_verification_suite_unexpected_scan_target",
        "scripts/ops/verify_ghost_pulse_verification_suite.py",
    )
    paths = _write_suite_fixture(tmp_path)
    unexpected = tmp_path / "docs/verification/unexpected-false-claim-target.md"
    unexpected.write_text("research draft only\n", encoding="utf-8")
    payload = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
    target = "docs/verification/unexpected-false-claim-target.md"
    payload["gates"]["false_claim_scan"]["targets_scanned"].append(target)
    payload["gates"]["false_claim_scan"]["target_records"].append(
        {
            "path": target,
            "exists": True,
            "size_bytes": unexpected.stat().st_size,
            "sha256": "c" * 64,
        }
    )
    paths["latest_json"].write_text(json.dumps(payload), encoding="utf-8")

    failures = verifier.verify_suite(paths["latest_json"], tmp_path)

    assert f"false_claim_scan unexpected target: {target}" in failures


def test_suite_self_verifier_rejects_reordered_false_claim_scan_targets(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_verification_suite_reordered_scan_targets",
        "scripts/ops/verify_ghost_pulse_verification_suite.py",
    )
    paths = _write_suite_fixture(tmp_path)
    payload = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
    scan_gate = payload["gates"]["false_claim_scan"]
    scan_gate["targets_scanned"][0], scan_gate["targets_scanned"][1] = (
        scan_gate["targets_scanned"][1],
        scan_gate["targets_scanned"][0],
    )
    scan_gate["target_records"][0], scan_gate["target_records"][1] = (
        scan_gate["target_records"][1],
        scan_gate["target_records"][0],
    )
    paths["latest_json"].write_text(json.dumps(payload), encoding="utf-8")

    failures = verifier.verify_suite(paths["latest_json"], tmp_path)

    assert "false_claim_scan targets_scanned order does not match expected targets" in failures


def test_suite_self_verifier_rejects_malformed_false_claim_scan_target(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_verification_suite_malformed_scan_target",
        "scripts/ops/verify_ghost_pulse_verification_suite.py",
    )
    paths = _write_suite_fixture(tmp_path)
    payload = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
    target = payload["gates"]["false_claim_scan"]["targets_scanned"][0]
    payload["gates"]["false_claim_scan"]["targets_scanned"][0] = {"path": target}
    paths["latest_json"].write_text(json.dumps(payload), encoding="utf-8")

    failures = verifier.verify_suite(paths["latest_json"], tmp_path)

    assert "false_claim_scan target 0 has invalid path" in failures


def test_suite_self_verifier_rejects_reordered_false_claim_target_records(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_verification_suite_reordered_scan_records",
        "scripts/ops/verify_ghost_pulse_verification_suite.py",
    )
    paths = _write_suite_fixture(tmp_path)
    payload = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
    records = payload["gates"]["false_claim_scan"]["target_records"]
    records[0], records[1] = records[1], records[0]
    paths["latest_json"].write_text(json.dumps(payload), encoding="utf-8")

    failures = verifier.verify_suite(paths["latest_json"], tmp_path)

    assert (
        "false_claim_scan target_records path order does not match targets_scanned"
        in failures
    )


def test_suite_self_verifier_rejects_duplicate_false_claim_scan_targets(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_verification_suite_duplicate_scan_targets",
        "scripts/ops/verify_ghost_pulse_verification_suite.py",
    )
    paths = _write_suite_fixture(tmp_path)
    payload = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
    scan_gate = payload["gates"]["false_claim_scan"]
    scan_gate["targets_scanned"].append(scan_gate["targets_scanned"][0])
    scan_gate["target_records"].append(dict(scan_gate["target_records"][0]))
    target = scan_gate["targets_scanned"][0]
    paths["latest_json"].write_text(json.dumps(payload), encoding="utf-8")

    failures = verifier.verify_suite(paths["latest_json"], tmp_path)

    assert f"false_claim_scan duplicate target: {target}" in failures
    assert f"false_claim_scan duplicate target record: {target}" in failures


def test_suite_self_verifier_rejects_stale_false_claim_target_metadata(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_verification_suite_scan_metadata",
        "scripts/ops/verify_ghost_pulse_verification_suite.py",
    )
    paths = _write_suite_fixture(tmp_path)
    payload = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
    record = payload["gates"]["false_claim_scan"]["target_records"][0]
    target = record["path"]
    record["exists"] = False
    record["size_bytes"] = record["size_bytes"] + 1
    paths["latest_json"].write_text(json.dumps(payload), encoding="utf-8")

    failures = verifier.verify_suite(paths["latest_json"], tmp_path)

    assert f"false_claim_scan target exists metadata is not true: {target}" in failures
    assert f"false_claim_scan target size_bytes mismatch: {target}" in failures


def test_suite_self_verifier_rejects_stale_artifact_integrity_metadata(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_verification_suite_artifact_metadata",
        "scripts/ops/verify_ghost_pulse_verification_suite.py",
    )
    paths = _write_suite_fixture(tmp_path)
    payload = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
    record = payload["gates"]["artifact_integrity"]["checks"]["local_latest_vs_bundle_json"]["left"]
    record["exists"] = False
    record["size_bytes"] = record["size_bytes"] + 1
    paths["latest_json"].write_text(json.dumps(payload), encoding="utf-8")

    failures = verifier.verify_suite(paths["latest_json"], tmp_path)

    assert (
        "artifact_integrity.local_latest_vs_bundle_json.left exists metadata is not true"
        in failures
    )
    assert "artifact_integrity.local_latest_vs_bundle_json.left size_bytes mismatch" in failures


def test_suite_self_verifier_rejects_missing_artifact_integrity_check(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_verification_suite_missing_artifact_check",
        "scripts/ops/verify_ghost_pulse_verification_suite.py",
    )
    paths = _write_suite_fixture(tmp_path)
    payload = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
    del payload["gates"]["artifact_integrity"]["checks"]["matrix_latest_vs_bundle_md"]
    paths["latest_json"].write_text(json.dumps(payload), encoding="utf-8")

    failures = verifier.verify_suite(paths["latest_json"], tmp_path)

    assert "artifact_integrity missing check: matrix_latest_vs_bundle_md" in failures


def test_suite_self_verifier_rejects_artifact_integrity_path_mismatch(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_verification_suite_artifact_path_mismatch",
        "scripts/ops/verify_ghost_pulse_verification_suite.py",
    )
    paths = _write_suite_fixture(tmp_path)
    payload = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
    check = payload["gates"]["artifact_integrity"]["checks"]["local_latest_vs_bundle_json"]
    check["right"]["path"] = check["left"]["path"]
    paths["latest_json"].write_text(json.dumps(payload), encoding="utf-8")

    failures = verifier.verify_suite(paths["latest_json"], tmp_path)

    assert "artifact_integrity.local_latest_vs_bundle_json.right path mismatch" in failures


def test_suite_self_verifier_rejects_stale_false_claim_target_hash(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_verification_suite_scan_hash",
        "scripts/ops/verify_ghost_pulse_verification_suite.py",
    )
    protocol = tmp_path / "docs/architecture/X0TTA6BL4_PULSE_PROTOCOL.md"
    protocol.parent.mkdir(parents=True)
    protocol.write_text("research draft only\n", encoding="utf-8")
    paths = _write_suite_fixture(tmp_path)
    protocol.write_text("research draft only\nchanged after suite generation\n", encoding="utf-8")

    failures = verifier.verify_suite(paths["latest_json"], tmp_path)

    assert "false_claim_scan target sha256 mismatch: docs/architecture/X0TTA6BL4_PULSE_PROTOCOL.md" in failures


def test_suite_self_verifier_rejects_summary_not_rendered_from_json(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_verification_suite_summary",
        "scripts/ops/verify_ghost_pulse_verification_suite.py",
    )
    paths = _write_suite_fixture(tmp_path)
    paths["latest_md"].write_text("consistent but wrong summary\n", encoding="utf-8")
    paths["bundle_md"].write_text("consistent but wrong summary\n", encoding="utf-8")

    failures = verifier.verify_suite(paths["latest_json"], tmp_path)

    assert "suite_bundle_md does not match rendered suite markdown" in failures
    assert "suite_latest_md does not match rendered suite markdown" in failures


def test_suite_self_verifier_cli_accepts_fixture(tmp_path, capsys):
    verifier = _load_script(
        "verify_ghost_pulse_verification_suite_cli",
        "scripts/ops/verify_ghost_pulse_verification_suite.py",
    )
    paths = _write_suite_fixture(tmp_path)

    exit_code = verifier.main(["--root", str(tmp_path), "--suite", str(paths["latest_json"])])

    assert exit_code == 0
    assert "PASS: x0tta6bl4_pulse verification suite report is internally consistent" in (
        capsys.readouterr().out
    )
