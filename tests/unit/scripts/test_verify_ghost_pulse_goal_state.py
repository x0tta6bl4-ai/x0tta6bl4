import importlib.util
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _load_script(name: str, rel_path: str):
    path = ROOT / rel_path
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _boundary(statuses: dict[str, str]) -> dict[str, bool]:
    return {
        "kernel_attach_verified": statuses.get("kernel_attach") == "VERIFIED",
        "production_ready": all(status == "VERIFIED" for status in statuses.values()),
        "stealth_verified": (
            statuses.get("packet_capture") == "VERIFIED"
            and statuses.get("baseline_timing_comparison") == "VERIFIED"
            and statuses.get("dpi_lab") == "VERIFIED"
        ),
        "whitelist_verified": statuses.get("whitelist_lab") == "VERIFIED",
    }


def _false_boundary() -> dict:
    return {
        "stealth_verified": False,
        "whitelist_verified": False,
        "kernel_attach_verified": False,
        "production_ready": False,
    }


def _candidate_path(claim_id: str) -> str:
    return f"docs/verification/incoming/{claim_id}.json"


def _current_evidence_path(claim_id: str) -> str:
    filenames = {
        "kernel_attach": "GHOST_PULSE_KERNEL_ATTACH_LATEST.json",
        "packet_capture": "GHOST_PULSE_PACKET_CAPTURE_LATEST.json",
        "baseline_timing_comparison": "GHOST_PULSE_BASELINE_COMPARISON_LATEST.json",
        "dpi_lab": "GHOST_PULSE_DPI_LAB_LATEST.json",
        "whitelist_lab": "GHOST_PULSE_WHITELIST_LAB_LATEST.json",
        "security_review": "GHOST_PULSE_SECURITY_REVIEW_LATEST.json",
        "production_readiness": "GHOST_PULSE_PRODUCTION_READINESS_LATEST.json",
    }
    return f"docs/verification/{filenames[claim_id]}"


def _write_current_evidence(root: Path, claim_id: str, status: str) -> tuple[str, str]:
    evidence_path = root / _current_evidence_path(claim_id)
    payload = {
        "schema": "x0tta6bl4.ghost_pulse.fixture_current_evidence.v1",
        "claim_id": claim_id,
        "status": "VERIFIED" if status == "VERIFIED" else "INCOMPLETE",
        "failures": [] if status == "VERIFIED" else [f"{claim_id}: fixture current evidence gap"],
    }
    if claim_id == "kernel_attach":
        payload["collection_diagnostics"] = {
            "status": "ACTION_REQUIRED",
            "blockers": [
                "xdp_attach_not_visible",
                "bpftool_permission_denied",
                "pulse_stats_counter_not_positive",
            ],
            "next_action": "Collect with readable bpftool data and a positive pulse_stats counter.",
            "interface": "enp8s0",
            "interface_seen": True,
            "xdp_attached": False,
            "xdp_interfaces": [],
            "bpftool_permission_denied": True,
            "bpftool_privilege_mode": "direct",
            "bpftool_net_contains_interface": False,
            "sudo_noninteractive_enabled": False,
            "sudo_noninteractive_unavailable": False,
            "sudo_unavailable": False,
            "pulse_marker_visible": False,
            "map_counter_delta_packets": 0,
            "object_preflight_status": "READY_FOR_CONTROLLED_ATTACH_TEST",
            "object_preflight_blockers": [],
        }
        payload["object_preflight"] = {
            "status": "READY_FOR_CONTROLLED_ATTACH_TEST",
            "blockers": [],
            "source": {
                "path": "src/network/ebpf/x0tta6bl4_pulse.bpf.c",
                "exists": True,
                "contains_xdp_section": True,
                "contains_pulse_stats": True,
                "contains_pulse_function": True,
            },
            "object": {
                "path": "src/network/ebpf/x0tta6bl4_pulse.o",
                "exists": True,
                "is_ebpf": True,
                "has_xdp_section": True,
                "has_maps_section": True,
                "has_btf_section": True,
                "contains_pulse_stats": True,
                "contains_pulse_function": True,
            },
        }
    _write_json(evidence_path, payload)
    return _current_evidence_path(claim_id), _sha256(evidence_path)


def _write_reports(root: Path, goal, statuses: dict[str, str] | None = None):
    verify_root = root / "docs/verification"
    statuses = statuses or {
        "local_timing_replay": "VERIFIED",
        "false_claim_hygiene": "VERIFIED",
        "artifact_chain": "VERIFIED",
        "kernel_attach": "INVALID",
        "packet_capture": "VERIFIED",
        "baseline_timing_comparison": "VERIFIED",
        "dpi_lab": "INVALID",
        "whitelist_lab": "INVALID",
        "security_review": "INVALID",
        "production_readiness": "INVALID",
    }
    pending = [
        claim_id
        for claim_id in goal.CLOSURE_CLAIMS
        if statuses.get(claim_id) != "VERIFIED"
    ]
    not_verified = [
        claim_id
        for claim_id in goal.EXPECTED_PROOF_ROW_CLAIMS
        if statuses.get(claim_id) != "VERIFIED"
    ]
    current_evidence: dict[str, tuple[str, str]] = {}
    for claim_id in goal.EXTERNAL_EVIDENCE_CLAIMS:
        current_evidence[claim_id] = _write_current_evidence(root, claim_id, statuses[claim_id])
    proof_rows = [
        {
            "claim_id": claim_id,
            "status": statuses[claim_id],
            "errors": [] if statuses[claim_id] == "VERIFIED" else [f"{claim_id}: fixture gap"],
            **(
                {
                    "evidence": current_evidence[claim_id][0],
                    "sha256": current_evidence[claim_id][1],
                }
                if claim_id in current_evidence
                else {}
            ),
        }
        for claim_id in goal.EXPECTED_PROOF_ROW_CLAIMS
    ]
    proof = {
        "schema": "x0tta6bl4.ghost_pulse.proof_gate.v1",
        "decision": goal.PROOF_DECISION_INCOMPLETE if pending else goal.PROOF_DECISION_PROVEN,
        "proof_rows": proof_rows,
        "not_verified_yet": not_verified,
        "claim_boundary": _boundary(statuses),
        "failures": ["fixture proof incomplete"] if pending else [],
    }
    _write_json(verify_root / "GHOST_PULSE_PROOF_GATE_LATEST.json", proof)

    ready: list[str] = []
    not_ready = list(pending)
    replacement = {
        "schema": "x0tta6bl4.ghost_pulse.replacement_candidate_preflight.v1",
        "status": "PASS",
        "decision": goal.REPLACEMENT_DECISION_NOT_READY if not_ready else goal.REPLACEMENT_DECISION_READY,
        "replacement_required": pending,
        "ready": ready,
        "not_ready": not_ready,
        "failures": [],
        "gap_audit_failures": [],
        "candidate_intake_plan": {
            "status": "ACTION_REQUIRED" if not_ready else "READY",
            "ready_claims": ready,
            "not_ready_claims": not_ready,
            "missing_candidate_paths": [_candidate_path(claim_id) for claim_id in not_ready],
        },
        "claim_boundary": _false_boundary(),
    }
    _write_json(verify_root / "GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json", replacement)

    examples = [
        {"claim_id": claim_id, "candidate": _candidate_path(claim_id)}
        for claim_id in goal.EXTERNAL_EVIDENCE_CLAIMS
    ]
    intake = {
        "schema": "x0tta6bl4.ghost_pulse.external_evidence_intake.v1",
        "status": "PASS",
        "decision": goal.INTAKE_DECISION_ACTION_REQUIRED if not_ready else goal.INTAKE_DECISION_READY_NOT_WRITTEN,
        "replacement_required": pending,
        "ready": ready,
        "not_ready": not_ready,
        "missing_candidate_paths": [_candidate_path(claim_id) for claim_id in not_ready],
        "preflight_verification": {"status": "PASS", "failures": []},
        "incoming_examples_verification": {"status": "PASS", "examples": examples},
        "failures": [],
        "claim_boundary": _false_boundary(),
    }
    _write_json(verify_root / "GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.json", intake)

    inventory = {
        "schema": "x0tta6bl4.ghost_pulse.external_evidence_inventory.v1",
        "status": "PASS",
        "inventory_status": goal.INVENTORY_STATUS_GAPS if pending else goal.INVENTORY_STATUS_ALL_VERIFIED,
        "failures": [],
        "gap_audit": {
            "expected_replacement_required": pending,
            "replacement_required": pending,
            "failures": [],
        },
    }
    _write_json(verify_root / "GHOST_PULSE_EXTERNAL_EVIDENCE_INVENTORY_LATEST.json", inventory)

    chain = {
        "schema": "x0tta6bl4.ghost_pulse.artifact_chain.v1",
        "decision": goal.CHAIN_DECISION_VERIFIED,
        "failures": [],
    }
    _write_json(verify_root / "GHOST_PULSE_ARTIFACT_CHAIN_LATEST.json", chain)

    manifest = {
        "schema": "x0tta6bl4.ghost_pulse.incoming_example_manifest.v1",
        "status": goal.EXAMPLES_STATUS,
        "examples": examples,
        "claim_boundary": _false_boundary(),
    }
    _write_json(verify_root / "incoming/examples/manifest.json", manifest)


def test_goal_state_accepts_current_latest():
    goal = _load_script(
        "verify_ghost_pulse_goal_state_current",
        "scripts/ops/verify_ghost_pulse_goal_state.py",
    )

    report = goal.build_report(ROOT)

    assert report["status"] == "PASS"
    assert report["decision"] == goal.DECISION_GAPS_RECORDED
    assert report["starter_verified_claims"] == ["packet_capture", "baseline_timing_comparison"]
    assert report["claim_boundary"]["kernel_attach_verified"] is True
    assert report["claim_boundary"]["stealth_verified"] is False
    assert report["pending_external_evidence_claims"] == [
        "dpi_lab",
        "whitelist_lab",
        "security_review",
        "production_readiness",
    ]


def test_goal_state_records_current_gap_contract(tmp_path):
    goal = _load_script(
        "verify_ghost_pulse_goal_state_fixture",
        "scripts/ops/verify_ghost_pulse_goal_state.py",
    )
    _write_reports(tmp_path, goal)

    report = goal.build_report(tmp_path)

    assert report["status"] == "PASS"
    assert report["decision"] == goal.DECISION_GAPS_RECORDED
    assert report["checks"]["external_evidence_intake"]["missing_candidate_paths"] == [
        "docs/verification/incoming/kernel_attach.json",
        "docs/verification/incoming/dpi_lab.json",
        "docs/verification/incoming/whitelist_lab.json",
        "docs/verification/incoming/security_review.json",
        "docs/verification/incoming/production_readiness.json",
    ]
    details = report["pending_external_evidence_details"]
    assert [detail["claim_id"] for detail in details] == [
        "kernel_attach",
        "dpi_lab",
        "whitelist_lab",
        "security_review",
        "production_readiness",
    ]
    kernel = details[0]
    assert kernel["candidate_path"] == "docs/verification/incoming/kernel_attach.json"
    assert kernel["candidate_missing"] is True
    assert kernel["proof"]["status"] == "INVALID"
    assert kernel["proof"]["errors_count"] == 1
    assert kernel["replacement"]["ready_to_import"] is False
    assert kernel["replacement"]["not_ready"] is True
    assert kernel["intake"]["missing_candidate_path"] is True
    assert kernel["current_evidence"]["sha256_matches_proof"] is True
    assert kernel["current_evidence"]["status"] == "INCOMPLETE"
    assert kernel["current_evidence"]["collection_diagnostics"]["bpftool_permission_denied"] is True
    assert kernel["current_evidence"]["collection_diagnostics"]["bpftool_privilege_mode"] == "direct"
    assert kernel["current_evidence"]["collection_diagnostics"]["sudo_noninteractive_enabled"] is False
    assert kernel["current_evidence"]["collection_diagnostics"]["xdp_attached"] is False
    assert kernel["current_evidence"]["collection_diagnostics"]["map_counter_delta_packets"] == 0
    assert kernel["current_evidence"]["collection_diagnostics"]["object_preflight_status"] == (
        "READY_FOR_CONTROLLED_ATTACH_TEST"
    )
    assert kernel["current_evidence"]["object_preflight"]["status"] == "READY_FOR_CONTROLLED_ATTACH_TEST"
    assert kernel["current_evidence"]["object_preflight"]["object_is_ebpf"] is True
    assert kernel["current_evidence"]["object_preflight"]["object_has_xdp_section"] is True
    assert kernel["current_evidence"]["object_preflight"]["object_has_btf_section"] is True
    assert kernel["current_evidence"]["object_preflight"]["object_contains_pulse_stats"] is True
    assert kernel["blocking_reasons"] == [
        "proof_status_not_verified",
        "proof_errors_present",
        "candidate_file_missing",
        "replacement_not_ready",
        "intake_not_ready",
        "intake_missing_candidate_path",
        "current_evidence_not_verified",
    ]
    assert report["claim_boundary"] == {
        "kernel_attach_verified": False,
        "production_ready": False,
        "stealth_verified": False,
        "whitelist_verified": False,
    }


def test_goal_state_rejects_unverified_starter_claim(tmp_path):
    goal = _load_script(
        "verify_ghost_pulse_goal_state_starter",
        "scripts/ops/verify_ghost_pulse_goal_state.py",
    )
    statuses = {
        claim_id: "VERIFIED"
        for claim_id in goal.EXPECTED_PROOF_ROW_CLAIMS
    }
    statuses["packet_capture"] = "INVALID"
    statuses["dpi_lab"] = "INVALID"
    _write_reports(tmp_path, goal, statuses)

    report = goal.build_report(tmp_path)

    assert report["status"] == "FAIL"
    assert "packet_capture: starter claim must be VERIFIED" in report["failures"]
    assert "packet_capture: non-closure claim must not be pending" in report["failures"]


def test_goal_state_accepts_closure_progress_without_unearned_boundaries(tmp_path):
    goal = _load_script(
        "verify_ghost_pulse_goal_state_progress",
        "scripts/ops/verify_ghost_pulse_goal_state.py",
    )
    statuses = {
        claim_id: "VERIFIED"
        for claim_id in goal.EXPECTED_PROOF_ROW_CLAIMS
    }
    for claim_id in ("dpi_lab", "whitelist_lab", "security_review", "production_readiness"):
        statuses[claim_id] = "INVALID"
    _write_reports(tmp_path, goal, statuses)

    report = goal.build_report(tmp_path)

    assert report["status"] == "PASS"
    assert report["decision"] == goal.DECISION_GAPS_RECORDED
    assert report["pending_external_evidence_claims"] == [
        "dpi_lab",
        "whitelist_lab",
        "security_review",
        "production_readiness",
    ]
    assert report["claim_boundary"]["kernel_attach_verified"] is True
    assert report["claim_boundary"]["stealth_verified"] is False


def test_goal_state_accepts_all_proven_state(tmp_path):
    goal = _load_script(
        "verify_ghost_pulse_goal_state_complete",
        "scripts/ops/verify_ghost_pulse_goal_state.py",
    )
    statuses = {
        claim_id: "VERIFIED"
        for claim_id in goal.EXPECTED_PROOF_ROW_CLAIMS
    }
    _write_reports(tmp_path, goal, statuses)

    report = goal.build_report(tmp_path)

    assert report["status"] == "PASS"
    assert report["decision"] == goal.DECISION_ALL_PROVEN
    assert report["pending_external_evidence_claims"] == []
    assert report["claim_boundary"]["production_ready"] is True


def test_goal_state_saved_report_detects_stale_source(tmp_path):
    goal = _load_script(
        "verify_ghost_pulse_goal_state_saved",
        "scripts/ops/verify_ghost_pulse_goal_state.py",
    )
    _write_reports(tmp_path, goal)
    report = goal.build_report(tmp_path)
    latest_json = tmp_path / "docs/verification/GHOST_PULSE_GOAL_STATE_LATEST.json"
    latest_md = tmp_path / "docs/verification/GHOST_PULSE_GOAL_STATE_LATEST.md"
    goal.write_report_outputs(tmp_path, report, latest_json, latest_md)
    assert goal.verify_saved_report(latest_json, tmp_path) == []

    proof_path = tmp_path / "docs/verification/GHOST_PULSE_PROOF_GATE_LATEST.json"
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    proof["not_verified_yet"] = []
    proof_path.write_text(json.dumps(proof, indent=2, sort_keys=True), encoding="utf-8")

    failures = goal.verify_saved_report(latest_json, tmp_path)

    assert "goal state stable fields do not match current proof/intake/inventory state" in failures


def test_goal_state_saved_report_detects_stale_pending_detail(tmp_path):
    goal = _load_script(
        "verify_ghost_pulse_goal_state_saved_detail",
        "scripts/ops/verify_ghost_pulse_goal_state.py",
    )
    _write_reports(tmp_path, goal)
    report = goal.build_report(tmp_path)
    latest_json = tmp_path / "docs/verification/GHOST_PULSE_GOAL_STATE_LATEST.json"
    latest_md = tmp_path / "docs/verification/GHOST_PULSE_GOAL_STATE_LATEST.md"
    goal.write_report_outputs(tmp_path, report, latest_json, latest_md)
    saved = json.loads(latest_json.read_text(encoding="utf-8"))
    saved["pending_external_evidence_details"][0]["candidate_path"] = (
        "docs/verification/incoming/wrong.json"
    )
    latest_json.write_text(json.dumps(saved, indent=2, sort_keys=True), encoding="utf-8")

    failures = goal.verify_saved_report(latest_json, tmp_path)

    assert "goal state stable fields do not match current proof/intake/inventory state" in failures
