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


def _claim_boundary():
    return {
        "stealth_verified": False,
        "whitelist_verified": False,
        "production_ready": False,
        "kernel_attach_verified": False,
        "kernel_read_only_visible": False,
    }


def _write_scan_targets(root: Path):
    for rel_path in SCAN_TARGET_REL_PATHS:
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("research draft only\n", encoding="utf-8")


def _write_replacement_candidates_latest(root: Path) -> Path:
    path = root / "docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema": "x0tta6bl4.ghost_pulse.replacement_candidate_preflight.v1",
                "decision": "REPLACEMENT_CANDIDATES_NOT_READY",
                "claim_boundary": _claim_boundary(),
            }
        ),
        encoding="utf-8",
    )
    path.with_suffix(".md").write_text("replacement candidates summary\n", encoding="utf-8")
    return path


def _pass_runner(_root, args, _timeout):
    return {
        "args": args,
        "available": True,
        "returncode": 0,
        "stdout": "PASS",
        "stderr": "",
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


def _write_suite_fixture(root: Path):
    suite_runner = _load_script(
        "run_ghost_pulse_verification_suite_for_chain",
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
    suite_runner.write_report_outputs(root, report, latest_json, latest_md)
    _write_replacement_candidates_latest(root)
    return local_path, matrix_path, latest_json


def test_artifact_chain_accepts_consistent_latest_artifacts(tmp_path):
    chain = _load_script(
        "verify_ghost_pulse_artifact_chain",
        "scripts/ops/verify_ghost_pulse_artifact_chain.py",
    )
    local_path, matrix_path, suite_path = _write_suite_fixture(tmp_path)

    report = chain.build_report(
        root=tmp_path,
        local_path=local_path,
        matrix_path=matrix_path,
        suite_path=suite_path,
        command_runner=_pass_runner,
    )

    assert report["decision"] == "GHOST_PULSE_ARTIFACT_CHAIN_VERIFIED"
    assert report["failures"] == []
    assert report["artifacts"]["local_evidence_sha256"] == chain.sha256_file(local_path)
    assert report["artifacts"]["profile_matrix_sha256"] == chain.sha256_file(matrix_path)
    inventory_path = tmp_path / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INVENTORY_LATEST.json"
    assert report["artifacts"]["external_evidence_inventory"] == chain.display_path(tmp_path, inventory_path)
    assert report["artifacts"]["external_evidence_inventory_sha256"] == chain.sha256_file(inventory_path)
    assert report["gates"]["external_evidence_inventory_verifier"]["status"] == "PASS"
    assert "--skip-proof-consistency" in report["gates"]["external_evidence_inventory_verifier"]["command"]["args"]
    intake_path = tmp_path / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.json"
    assert report["artifacts"]["external_evidence_intake"] == chain.display_path(tmp_path, intake_path)
    assert report["artifacts"]["external_evidence_intake_sha256"] == chain.sha256_file(intake_path)
    assert report["gates"]["external_evidence_intake_verifier"]["status"] == "PASS"
    replacement_path = tmp_path / "docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json"
    assert report["artifacts"]["replacement_candidates"] == chain.display_path(tmp_path, replacement_path)
    assert report["artifacts"]["replacement_candidates_sha256"] == chain.sha256_file(replacement_path)
    assert report["gates"]["replacement_candidates_verifier"]["status"] == "PASS"


def test_artifact_chain_writes_and_verifies_saved_report(tmp_path):
    chain = _load_script(
        "verify_ghost_pulse_artifact_chain_saved",
        "scripts/ops/verify_ghost_pulse_artifact_chain.py",
    )
    local_path, matrix_path, suite_path = _write_suite_fixture(tmp_path)
    report = chain.build_report(
        root=tmp_path,
        local_path=local_path,
        matrix_path=matrix_path,
        suite_path=suite_path,
        command_runner=_pass_runner,
    )
    output_json = tmp_path / "docs/verification/GHOST_PULSE_ARTIFACT_CHAIN_LATEST.json"
    output_md = tmp_path / "docs/verification/GHOST_PULSE_ARTIFACT_CHAIN_LATEST.md"

    paths = chain.write_report_outputs(tmp_path, report, output_json, output_md)

    assert chain.verify_saved_report(paths["latest_json"], tmp_path, command_runner=_pass_runner) == []
    saved = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
    assert saved["bundle"].startswith("docs/verification/ghost-pulse-artifact-chain-")
    assert saved["artifacts"]["chain_latest_json"] == "docs/verification/GHOST_PULSE_ARTIFACT_CHAIN_LATEST.json"
    assert saved["artifacts"]["chain_latest_md"] == "docs/verification/GHOST_PULSE_ARTIFACT_CHAIN_LATEST.md"
    assert paths["latest_json"].read_bytes() == paths["bundle_json"].read_bytes()
    assert paths["latest_md"].read_bytes() == paths["bundle_md"].read_bytes()
    assert paths["latest_md"].read_text(encoding="utf-8") == chain.render_markdown(saved)


def test_artifact_chain_saved_report_rejects_stale_fields(tmp_path):
    chain = _load_script(
        "verify_ghost_pulse_artifact_chain_saved_stale",
        "scripts/ops/verify_ghost_pulse_artifact_chain.py",
    )
    local_path, matrix_path, suite_path = _write_suite_fixture(tmp_path)
    report = chain.build_report(
        root=tmp_path,
        local_path=local_path,
        matrix_path=matrix_path,
        suite_path=suite_path,
        command_runner=_pass_runner,
    )
    output_json = tmp_path / "docs/verification/GHOST_PULSE_ARTIFACT_CHAIN_LATEST.json"
    output_md = tmp_path / "docs/verification/GHOST_PULSE_ARTIFACT_CHAIN_LATEST.md"
    paths = chain.write_report_outputs(tmp_path, report, output_json, output_md)
    saved = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
    saved["decision"] = "GHOST_PULSE_ARTIFACT_CHAIN_INCOMPLETE"
    stale_json = json.dumps(saved, indent=2, sort_keys=True)
    paths["latest_json"].write_text(stale_json, encoding="utf-8")
    paths["bundle_json"].write_text(stale_json, encoding="utf-8")

    failures = chain.verify_saved_report(paths["latest_json"], tmp_path, command_runner=_pass_runner)

    assert "artifact-chain stable fields do not match current artifact state" in failures


def test_artifact_chain_saved_report_rejects_latest_bundle_mismatch(tmp_path):
    chain = _load_script(
        "verify_ghost_pulse_artifact_chain_saved_bundle_mismatch",
        "scripts/ops/verify_ghost_pulse_artifact_chain.py",
    )
    local_path, matrix_path, suite_path = _write_suite_fixture(tmp_path)
    report = chain.build_report(
        root=tmp_path,
        local_path=local_path,
        matrix_path=matrix_path,
        suite_path=suite_path,
        command_runner=_pass_runner,
    )
    paths = chain.write_report_outputs(
        tmp_path,
        report,
        tmp_path / "docs/verification/GHOST_PULSE_ARTIFACT_CHAIN_LATEST.json",
        tmp_path / "docs/verification/GHOST_PULSE_ARTIFACT_CHAIN_LATEST.md",
    )
    paths["bundle_json"].write_text('{"tampered": true}\n', encoding="utf-8")

    failures = chain.verify_saved_report(paths["latest_json"], tmp_path, command_runner=_pass_runner)

    assert "artifact-chain latest JSON does not match bundle JSON" in failures


def test_artifact_chain_rejects_missing_external_evidence_inventory_latest(tmp_path):
    chain = _load_script(
        "verify_ghost_pulse_artifact_chain_missing_external_inventory",
        "scripts/ops/verify_ghost_pulse_artifact_chain.py",
    )
    local_path, matrix_path, suite_path = _write_suite_fixture(tmp_path)
    (tmp_path / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INVENTORY_LATEST.json").unlink()

    report = chain.build_report(
        root=tmp_path,
        local_path=local_path,
        matrix_path=matrix_path,
        suite_path=suite_path,
        command_runner=_pass_runner,
    )

    assert report["decision"] == "GHOST_PULSE_ARTIFACT_CHAIN_INCOMPLETE"
    assert "external evidence inventory latest artifact is missing" in report["failures"]


def test_artifact_chain_rejects_external_evidence_inventory_verifier_failure(tmp_path):
    chain = _load_script(
        "verify_ghost_pulse_artifact_chain_external_inventory_verifier",
        "scripts/ops/verify_ghost_pulse_artifact_chain.py",
    )
    local_path, matrix_path, suite_path = _write_suite_fixture(tmp_path)

    def fail_inventory_runner(_root, args, _timeout):
        if "scripts/ops/verify_ghost_pulse_external_evidence_inventory.py" in args:
            return {
                "args": args,
                "available": True,
                "returncode": 1,
                "stdout": "FAIL",
                "stderr": "",
            }
        return _pass_runner(_root, args, _timeout)

    report = chain.build_report(
        root=tmp_path,
        local_path=local_path,
        matrix_path=matrix_path,
        suite_path=suite_path,
        command_runner=fail_inventory_runner,
    )

    assert report["decision"] == "GHOST_PULSE_ARTIFACT_CHAIN_INCOMPLETE"
    assert report["gates"]["external_evidence_inventory_verifier"]["status"] == "FAIL"
    assert "external_evidence_inventory_verifier did not pass" in report["failures"]


def test_artifact_chain_rejects_missing_replacement_candidates_latest(tmp_path):
    chain = _load_script(
        "verify_ghost_pulse_artifact_chain_missing_replacement_candidates",
        "scripts/ops/verify_ghost_pulse_artifact_chain.py",
    )
    local_path, matrix_path, suite_path = _write_suite_fixture(tmp_path)
    (tmp_path / "docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json").unlink()

    report = chain.build_report(
        root=tmp_path,
        local_path=local_path,
        matrix_path=matrix_path,
        suite_path=suite_path,
        command_runner=_pass_runner,
    )

    assert report["decision"] == "GHOST_PULSE_ARTIFACT_CHAIN_INCOMPLETE"
    assert "replacement candidates latest artifact is missing" in report["failures"]


def test_artifact_chain_rejects_suite_hash_mismatch(tmp_path):
    chain = _load_script(
        "verify_ghost_pulse_artifact_chain_hash",
        "scripts/ops/verify_ghost_pulse_artifact_chain.py",
    )
    local_path, matrix_path, suite_path = _write_suite_fixture(tmp_path)
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    suite["artifacts"]["local_evidence_sha256"] = "0" * 64
    suite_path.write_text(json.dumps(suite), encoding="utf-8")

    report = chain.build_report(
        root=tmp_path,
        local_path=local_path,
        matrix_path=matrix_path,
        suite_path=suite_path,
        command_runner=_pass_runner,
    )

    assert report["decision"] == "GHOST_PULSE_ARTIFACT_CHAIN_INCOMPLETE"
    assert "suite local_evidence_sha256 does not match selected local latest" in report["failures"]


def test_artifact_chain_rejects_suite_pointer_mismatch(tmp_path):
    chain = _load_script(
        "verify_ghost_pulse_artifact_chain_pointer",
        "scripts/ops/verify_ghost_pulse_artifact_chain.py",
    )
    local_path, matrix_path, suite_path = _write_suite_fixture(tmp_path)
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    suite["artifacts"]["profile_matrix"] = "docs/verification/other-matrix.json"
    suite_path.write_text(json.dumps(suite), encoding="utf-8")

    report = chain.build_report(
        root=tmp_path,
        local_path=local_path,
        matrix_path=matrix_path,
        suite_path=suite_path,
        command_runner=_pass_runner,
    )

    assert report["decision"] == "GHOST_PULSE_ARTIFACT_CHAIN_INCOMPLETE"
    assert "suite profile_matrix pointer does not match selected profile matrix latest" in report["failures"]


def test_artifact_chain_rejects_missing_suite_bundle_json_artifact(tmp_path):
    chain = _load_script(
        "verify_ghost_pulse_artifact_chain_missing_suite_bundle",
        "scripts/ops/verify_ghost_pulse_artifact_chain.py",
    )
    local_path, matrix_path, suite_path = _write_suite_fixture(tmp_path)
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    suite["artifacts"]["suite_bundle_json"] = "docs/verification/missing-suite/suite.json"
    suite_path.write_text(json.dumps(suite), encoding="utf-8")

    report = chain.build_report(
        root=tmp_path,
        local_path=local_path,
        matrix_path=matrix_path,
        suite_path=suite_path,
        command_runner=_pass_runner,
    )

    assert report["decision"] == "GHOST_PULSE_ARTIFACT_CHAIN_INCOMPLETE"
    assert "suite_bundle_json artifact is missing" in report["failures"]


def test_artifact_chain_rejects_false_claim_scan_failures(tmp_path):
    chain = _load_script(
        "verify_ghost_pulse_artifact_chain_scan_failures",
        "scripts/ops/verify_ghost_pulse_artifact_chain.py",
    )
    local_path, matrix_path, suite_path = _write_suite_fixture(tmp_path)
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    suite["gates"]["false_claim_scan"]["failures"] = [
        "false_claim_scan target is missing: docs/verification/example.md"
    ]
    suite_path.write_text(json.dumps(suite), encoding="utf-8")

    report = chain.build_report(
        root=tmp_path,
        local_path=local_path,
        matrix_path=matrix_path,
        suite_path=suite_path,
        command_runner=_pass_runner,
    )

    assert report["decision"] == "GHOST_PULSE_ARTIFACT_CHAIN_INCOMPLETE"
    assert "suite false_claim_scan failures must be empty" in report["failures"]


def test_artifact_chain_rejects_false_claim_target_policy_tamper(tmp_path):
    chain = _load_script(
        "verify_ghost_pulse_artifact_chain_scan_policy",
        "scripts/ops/verify_ghost_pulse_artifact_chain.py",
    )
    local_path, matrix_path, suite_path = _write_suite_fixture(tmp_path)
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    suite["gates"]["false_claim_scan"]["target_policy"]["sha256"] = "0" * 64
    suite_path.write_text(json.dumps(suite), encoding="utf-8")

    report = chain.build_report(
        root=tmp_path,
        local_path=local_path,
        matrix_path=matrix_path,
        suite_path=suite_path,
        command_runner=_pass_runner,
    )

    assert report["decision"] == "GHOST_PULSE_ARTIFACT_CHAIN_INCOMPLETE"
    assert "suite false_claim_scan target_policy does not match expected policy" in report["failures"]


def test_artifact_chain_rejects_artifact_integrity_policy_tamper(tmp_path):
    chain = _load_script(
        "verify_ghost_pulse_artifact_chain_artifact_policy",
        "scripts/ops/verify_ghost_pulse_artifact_chain.py",
    )
    local_path, matrix_path, suite_path = _write_suite_fixture(tmp_path)
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    suite["gates"]["artifact_integrity"]["policy"]["check_count"] += 1
    suite_path.write_text(json.dumps(suite), encoding="utf-8")

    report = chain.build_report(
        root=tmp_path,
        local_path=local_path,
        matrix_path=matrix_path,
        suite_path=suite_path,
        command_runner=_pass_runner,
    )

    assert report["decision"] == "GHOST_PULSE_ARTIFACT_CHAIN_INCOMPLETE"
    assert "suite artifact_integrity policy does not match expected policy" in report["failures"]


def test_artifact_chain_computes_artifact_policy_locally(tmp_path):
    chain = _load_script(
        "verify_ghost_pulse_artifact_chain_local_artifact_policy",
        "scripts/ops/verify_ghost_pulse_artifact_chain.py",
    )
    _local_path, _matrix_path, suite_path = _write_suite_fixture(tmp_path)
    suite = json.loads(suite_path.read_text(encoding="utf-8"))

    expected_checks, failures = chain.expected_artifact_integrity_checks(tmp_path, suite)
    expected_policy = chain.expected_artifact_integrity_policy(expected_checks)

    assert failures == []
    assert expected_policy == suite["gates"]["artifact_integrity"]["policy"]
    assert expected_policy["mode"] == "required_latest_bundle_path_pairs"
    assert expected_policy["required"] is True
    assert expected_policy["check_count"] == 4


def test_artifact_chain_rejects_stale_artifact_integrity_metadata(tmp_path):
    chain = _load_script(
        "verify_ghost_pulse_artifact_chain_artifact_metadata",
        "scripts/ops/verify_ghost_pulse_artifact_chain.py",
    )
    local_path, matrix_path, suite_path = _write_suite_fixture(tmp_path)
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    record = suite["gates"]["artifact_integrity"]["checks"]["local_latest_vs_bundle_json"]["left"]
    record["exists"] = False
    record["size_bytes"] = record["size_bytes"] + 1
    suite_path.write_text(json.dumps(suite), encoding="utf-8")

    report = chain.build_report(
        root=tmp_path,
        local_path=local_path,
        matrix_path=matrix_path,
        suite_path=suite_path,
        command_runner=_pass_runner,
    )

    assert report["decision"] == "GHOST_PULSE_ARTIFACT_CHAIN_INCOMPLETE"
    assert (
        "suite artifact_integrity.local_latest_vs_bundle_json.left exists metadata is not true"
        in report["failures"]
    )
    assert (
        "suite artifact_integrity.local_latest_vs_bundle_json.left size_bytes mismatch"
        in report["failures"]
    )


def test_artifact_chain_rejects_missing_artifact_integrity_check(tmp_path):
    chain = _load_script(
        "verify_ghost_pulse_artifact_chain_missing_artifact_check",
        "scripts/ops/verify_ghost_pulse_artifact_chain.py",
    )
    local_path, matrix_path, suite_path = _write_suite_fixture(tmp_path)
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    del suite["gates"]["artifact_integrity"]["checks"]["matrix_latest_vs_bundle_md"]
    suite_path.write_text(json.dumps(suite), encoding="utf-8")

    report = chain.build_report(
        root=tmp_path,
        local_path=local_path,
        matrix_path=matrix_path,
        suite_path=suite_path,
        command_runner=_pass_runner,
    )

    assert report["decision"] == "GHOST_PULSE_ARTIFACT_CHAIN_INCOMPLETE"
    assert "suite artifact_integrity missing check: matrix_latest_vs_bundle_md" in report["failures"]


def test_artifact_chain_rejects_artifact_integrity_path_mismatch(tmp_path):
    chain = _load_script(
        "verify_ghost_pulse_artifact_chain_artifact_path_mismatch",
        "scripts/ops/verify_ghost_pulse_artifact_chain.py",
    )
    local_path, matrix_path, suite_path = _write_suite_fixture(tmp_path)
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    check = suite["gates"]["artifact_integrity"]["checks"]["local_latest_vs_bundle_json"]
    check["right"]["path"] = check["left"]["path"]
    suite_path.write_text(json.dumps(suite), encoding="utf-8")

    report = chain.build_report(
        root=tmp_path,
        local_path=local_path,
        matrix_path=matrix_path,
        suite_path=suite_path,
        command_runner=_pass_runner,
    )

    assert report["decision"] == "GHOST_PULSE_ARTIFACT_CHAIN_INCOMPLETE"
    assert (
        "suite artifact_integrity.local_latest_vs_bundle_json.right path mismatch"
        in report["failures"]
    )


def test_artifact_chain_rejects_suite_latest_bundle_json_mismatch(tmp_path):
    chain = _load_script(
        "verify_ghost_pulse_artifact_chain_suite_latest_mismatch",
        "scripts/ops/verify_ghost_pulse_artifact_chain.py",
    )
    local_path, matrix_path, suite_path = _write_suite_fixture(tmp_path)
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    bundle_json = tmp_path / suite["artifacts"]["suite_bundle_json"]
    bundle_json.write_text('{"tampered": true}\n', encoding="utf-8")

    report = chain.build_report(
        root=tmp_path,
        local_path=local_path,
        matrix_path=matrix_path,
        suite_path=suite_path,
        command_runner=_pass_runner,
    )

    assert report["decision"] == "GHOST_PULSE_ARTIFACT_CHAIN_INCOMPLETE"
    assert "suite latest json does not match suite bundle json" in report["failures"]


def test_artifact_chain_rejects_stale_false_claim_scan_hash(tmp_path):
    chain = _load_script(
        "verify_ghost_pulse_artifact_chain_scan_hash",
        "scripts/ops/verify_ghost_pulse_artifact_chain.py",
    )
    local_path, matrix_path, suite_path = _write_suite_fixture(tmp_path)
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    record = suite["gates"]["false_claim_scan"]["target_records"][0]
    target = record["path"]
    record["sha256"] = "0" * 64
    suite_path.write_text(json.dumps(suite), encoding="utf-8")

    report = chain.build_report(
        root=tmp_path,
        local_path=local_path,
        matrix_path=matrix_path,
        suite_path=suite_path,
        command_runner=_pass_runner,
    )

    assert report["decision"] == "GHOST_PULSE_ARTIFACT_CHAIN_INCOMPLETE"
    assert f"suite false_claim_scan target sha256 mismatch: {target}" in report["failures"]


def test_artifact_chain_rejects_reordered_false_claim_scan_records(tmp_path):
    chain = _load_script(
        "verify_ghost_pulse_artifact_chain_scan_order",
        "scripts/ops/verify_ghost_pulse_artifact_chain.py",
    )
    local_path, matrix_path, suite_path = _write_suite_fixture(tmp_path)
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    records = suite["gates"]["false_claim_scan"]["target_records"]
    records[0], records[1] = records[1], records[0]
    suite_path.write_text(json.dumps(suite), encoding="utf-8")

    report = chain.build_report(
        root=tmp_path,
        local_path=local_path,
        matrix_path=matrix_path,
        suite_path=suite_path,
        command_runner=_pass_runner,
    )

    assert report["decision"] == "GHOST_PULSE_ARTIFACT_CHAIN_INCOMPLETE"
    assert (
        "suite false_claim_scan target_records path order does not match targets_scanned"
        in report["failures"]
    )


def test_artifact_chain_rejects_duplicate_false_claim_scan_target(tmp_path):
    chain = _load_script(
        "verify_ghost_pulse_artifact_chain_scan_duplicate",
        "scripts/ops/verify_ghost_pulse_artifact_chain.py",
    )
    local_path, matrix_path, suite_path = _write_suite_fixture(tmp_path)
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    scan_gate = suite["gates"]["false_claim_scan"]
    scan_gate["targets_scanned"].append(scan_gate["targets_scanned"][0])
    scan_gate["target_records"].append(dict(scan_gate["target_records"][0]))
    target = scan_gate["targets_scanned"][0]
    suite_path.write_text(json.dumps(suite), encoding="utf-8")

    report = chain.build_report(
        root=tmp_path,
        local_path=local_path,
        matrix_path=matrix_path,
        suite_path=suite_path,
        command_runner=_pass_runner,
    )

    assert report["decision"] == "GHOST_PULSE_ARTIFACT_CHAIN_INCOMPLETE"
    assert f"suite false_claim_scan duplicate target: {target}" in report["failures"]
    assert f"suite false_claim_scan duplicate target record: {target}" in report["failures"]
