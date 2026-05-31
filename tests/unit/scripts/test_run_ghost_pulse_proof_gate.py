import importlib.util
import hashlib
import json
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _load_module():
    path = ROOT / "scripts/ops/run_ghost_pulse_proof_gate.py"
    spec = importlib.util.spec_from_file_location("run_ghost_pulse_proof_gate", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _suite_payload():
    return {
        "decision": "GHOST_PULSE_VERIFICATION_SUITE_VERIFIED_STEALTH_NOT_VERIFIED",
        "claim_boundary": {
            "stealth_verified": False,
            "whitelist_verified": False,
            "production_ready": False,
            "kernel_attach_verified": False,
            "kernel_read_only_visible": False,
        },
        "summary": {
            "local": {"replay_status": "LOCAL_SEED_REPLAYABLE"},
            "matrix": {"run_count": 2, "replayable_run_count": 2},
        },
        "gates": {
            "false_claim_scan": {"status": "PASS"},
            "artifact_integrity": {"status": "PASS"},
        },
    }


def _write_suite(root: Path):
    suite_path = root / "docs/verification/GHOST_PULSE_VERIFICATION_SUITE_LATEST.json"
    suite_path.parent.mkdir(parents=True)
    suite_path.write_text(json.dumps(_suite_payload()), encoding="utf-8")
    return suite_path


def _suite_failures(_root: Path, _suite_path: Path):
    return []


def _artifact_chain(_root: Path, _suite_path: Path):
    return {"decision": "GHOST_PULSE_ARTIFACT_CHAIN_VERIFIED"}


def _replacement_candidates(_root: Path, _report_path: Path):
    return {
        "report": "docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json",
        "sha256": "b" * 64,
        "status": "PASS",
        "decision": "REPLACEMENT_CANDIDATES_NOT_READY",
        "replacement_required": ["kernel_attach", "dpi_lab"],
        "ready": [],
        "not_ready": ["kernel_attach", "dpi_lab"],
        "missing_candidates": ["kernel_attach", "dpi_lab"],
        "claim_boundary": {
            "note": "fixture",
            "stealth_verified": False,
            "whitelist_verified": False,
            "kernel_attach_verified": False,
            "production_ready": False,
        },
        "verifier_command": [
            "python3",
            "scripts/ops/verify_ghost_pulse_replacement_candidates.py",
            "--report",
            "docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json",
            "--json",
        ],
        "failures": [],
    }


def _replacement_candidates_failed(_root: Path, _report_path: Path):
    payload = _replacement_candidates(_root, _report_path)
    payload["status"] = "FAIL"
    payload["failures"] = ["saved preflight report is stale"]
    return payload


def _current_runtime_verified(_root: Path, _interface, _bpftool_sudo, _counter_wait_seconds):
    return {
        "claim_id": "current_runtime_attached",
        "title": "Current runtime x0tta6bl4_pulse XDP attach",
        "status": "VERIFIED",
        "evidence": "READ_ONLY_KERNEL_OBSERVATION:test0",
        "errors": [],
        "sha256": None,
    }


def _current_runtime_invalid(_root: Path, _interface, _bpftool_sudo, _counter_wait_seconds):
    return {
        "claim_id": "current_runtime_attached",
        "title": "Current runtime x0tta6bl4_pulse XDP attach",
        "status": "INVALID",
        "evidence": "READ_ONLY_KERNEL_OBSERVATION:test0",
        "errors": ["current runtime is not attached"],
        "sha256": None,
    }


def _measurement_value(expectation):
    if expectation in (True, False):
        return expectation
    if expectation == 0:
        return 0
    if expectation == "nonempty":
        return "recorded"
    if expectation == "positive_int":
        return 3
    if expectation == "sha256":
        return "a" * 64
    if expectation == "bool_true":
        return True
    raise AssertionError(f"unhandled expectation: {expectation!r}")


def _commands_for_requirement(requirement, measurements):
    if "required_commands" not in requirement:
        return [
            {
                "args": ["proof-fixture", requirement["claim_id"]],
                "exit_code": 0,
            }
        ]
    commands = []
    for template in requirement["required_commands"]:
        args = [
            measurements[part[1:-1]] if isinstance(part, str) and part.startswith("<") and part.endswith(">") else part
            for part in template
        ]
        commands.append({"args": args, "exit_code": 0})
    return commands


def _write_fixture_pcap(path: Path, packet_count: int):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        f.write(struct.pack("<IHHIIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 101))
        for index in range(packet_count):
            payload = f"packet-{index}".encode("ascii")
            total_length = 20 + 8 + len(payload)
            ip_header = struct.pack(
                "!BBHHHBBH4s4s",
                0x45,
                0,
                total_length,
                index,
                0,
                64,
                17,
                0,
                b"\x7f\x00\x00\x01",
                b"\x7f\x00\x00\x01",
            )
            udp_header = struct.pack("!HHHH", 40000 + index, 50000, 8 + len(payload), 0)
            raw = ip_header + udp_header + payload
            f.write(struct.pack("<IIII", 1_700_000_000, index, len(raw), len(raw)))
            f.write(raw)


def _write_fixture_jsonl(path: Path, record_count: int):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for index in range(record_count):
            payload = f"packet-{index}".encode("ascii")
            f.write(
                json.dumps(
                    {
                        "index": index,
                        "payload_sha256": hashlib.sha256(payload).hexdigest(),
                    },
                    sort_keys=True,
                )
                + "\n"
            )


def _artifacts_for_requirement(root: Path, proof, requirement, measurements):
    roles = requirement.get("required_artifact_roles")
    if not roles:
        artifact_path = root / "docs/verification/ghost-pulse-proof-fixtures" / f"{requirement['claim_id']}.txt"
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(f"{requirement['claim_id']} proof fixture\n", encoding="utf-8")
        return [
            {
                "path": proof.display_path(root, artifact_path),
                "sha256": proof.sha256_file(artifact_path),
            }
        ]

    artifacts = []
    for role in roles:
        artifact_path = (
            root
            / "docs/verification/ghost-pulse-proof-fixtures"
            / requirement["claim_id"]
            / f"{role}.txt"
        )
        if role in requirement.get("pcap_packet_count_measurements", {}):
            artifact_path = artifact_path.with_suffix(".pcap")
            measurement_key = requirement["pcap_packet_count_measurements"][role]
            _write_fixture_pcap(artifact_path, measurements[measurement_key])
        elif role in requirement.get("jsonl_record_count_measurements", {}):
            artifact_path = artifact_path.with_suffix(".jsonl")
            measurement_key = requirement["jsonl_record_count_measurements"][role]
            _write_fixture_jsonl(artifact_path, measurements[measurement_key])
        elif any(role in item.get("roles", []) for item in requirement.get("paired_jsonl_gap_count_measurements", [])):
            artifact_path = artifact_path.with_suffix(".jsonl")
            measurement_key = next(
                item["measurement"]
                for item in requirement["paired_jsonl_gap_count_measurements"]
                if role in item.get("roles", [])
            )
            _write_fixture_jsonl(artifact_path, measurements[measurement_key] + 1)
        else:
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text(f"{requirement['claim_id']} {role} proof fixture\n", encoding="utf-8")
        artifacts.append(
            {
                "role": role,
                "path": proof.display_path(root, artifact_path),
                "sha256": proof.sha256_file(artifact_path),
            }
        )
    return artifacts


def _artifact_by_role(payload, role):
    for artifact in payload["artifacts"]:
        if artifact.get("role") == role:
            return artifact
    raise AssertionError(f"missing artifact role: {role}")


def _write_artifact_json(root: Path, proof, artifact, value):
    artifact_path = root / artifact["path"]
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    artifact["sha256"] = proof.sha256_file(artifact_path)


def _sync_linked_json_artifacts(root: Path, proof, requirement, payload):
    for role, payload_key in requirement.get("json_artifact_payload_links", {}).items():
        _write_artifact_json(
            root,
            proof,
            _artifact_by_role(payload, role),
            payload[payload_key],
        )
    for role, payload_keys in requirement.get("json_artifact_object_field_links", {}).items():
        _write_artifact_json(
            root,
            proof,
            _artifact_by_role(payload, role),
            {key: payload[key] for key in payload_keys},
        )


def _references_for_requirement(root: Path, proof, requirement):
    references = []
    requirements = {item["claim_id"]: item for item in proof.EXTERNAL_REQUIREMENTS}
    for claim_id in requirement.get("required_references", []):
        validation = proof.validate_external_evidence(root, requirements[claim_id])
        references.append(
            {
                "claim_id": claim_id,
                "status": validation["status"],
                "evidence": validation["evidence"],
                "sha256": validation["sha256"],
            }
        )
    return references


def _write_external_evidence(root: Path, proof, requirement):
    evidence_path = root / requirement["path"]
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    measurements = {
        key: _measurement_value(expectation)
        for key, expectation in requirement["measurements"].items()
    }
    payload = {
        "schema": proof.EVIDENCE_SCHEMA,
        "claim_id": requirement["claim_id"],
        "status": "VERIFIED",
        "observed_at_utc": "2026-05-22T00:00:00Z",
        "simulated": False,
        "dry_run": False,
        "template": False,
        "commands": _commands_for_requirement(requirement, measurements),
        "artifacts": _artifacts_for_requirement(root, proof, requirement, measurements),
        "measurements": measurements,
    }
    if "json_artifact_payload_links" in requirement or "json_artifact_object_field_links" in requirement:
        payload["failures"] = []
        payload["claim_boundary"] = {
            f"{requirement['claim_id']}_verified": True,
        }
        payload["interface_scan"] = {
            "parse_status": "OK",
            "interface_count": 1,
            "interfaces": [measurements.get("interface", "recorded")],
            "xdp_interfaces": [{"ifname": measurements.get("interface", "recorded")}],
        }
        payload["candidate_audit"] = {
            "status": "HAS_ACCEPTED_CANDIDATE",
            "accepted": [],
            "candidates": [],
            "claim_boundary": "fixture only",
        }
        for payload_keys in requirement.get("json_artifact_object_field_links", {}).values():
            for key in payload_keys:
                payload.setdefault(key, {"fixture": requirement["claim_id"]})
    for role, measurement_key in requirement.get("artifact_sha256_measurements", {}).items():
        for artifact in payload["artifacts"]:
            if artifact.get("role") == role:
                payload["measurements"][measurement_key] = artifact["sha256"]
                break
    if "required_references" in requirement:
        payload["references"] = _references_for_requirement(root, proof, requirement)
    _sync_linked_json_artifacts(root, proof, requirement, payload)
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")
    return evidence_path


def test_proof_gate_fails_closed_without_external_evidence(tmp_path):
    proof = _load_module()
    suite_path = _write_suite(tmp_path)

    report = proof.build_report(
        root=tmp_path,
        suite_path=suite_path,
        suite_failure_provider=_suite_failures,
        artifact_chain_provider=_artifact_chain,
        replacement_candidate_provider=_replacement_candidates,
    )

    assert report["decision"] == proof.DECISION_INCOMPLETE
    assert report["claim_boundary"]["stealth_verified"] is False
    assert report["claim_boundary"]["whitelist_verified"] is False
    assert report["claim_boundary"]["kernel_attach_verified"] is False
    assert report["claim_boundary"]["current_runtime_attached"] is False
    assert report["claim_boundary"]["production_ready"] is False
    assert "kernel_attach" in report["not_verified_yet"]
    assert proof.CURRENT_RUNTIME_CLAIM_ID in report["not_verified_yet"]
    assert "production_readiness" in report["not_verified_yet"]
    assert "local_timing_replay" not in report["not_verified_yet"]


def test_proof_gate_rejects_simulated_external_evidence(tmp_path):
    proof = _load_module()
    requirement = proof.EXTERNAL_REQUIREMENTS[0]
    evidence_path = _write_external_evidence(tmp_path, proof, requirement)
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload["simulated"] = True
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    row = proof.validate_external_evidence(tmp_path, requirement)

    assert row["status"] == "INVALID"
    assert "simulated must be false" in row["errors"]


def test_proof_gate_rejects_promoted_gap_record_metadata(tmp_path):
    proof = _load_module()
    requirement = proof.EXTERNAL_REQUIREMENTS[3]
    evidence_path = _write_external_evidence(tmp_path, proof, requirement)
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload["mode"] = "EXTERNAL_EVIDENCE_GAP_RECORD"
    payload["missing_inputs"] = ["authorized lab identity and scope"]
    payload["failures"] = ["missing external input: authorized lab identity and scope"]
    payload["claim_boundary"] = {"claim_verified": False}
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    row = proof.validate_external_evidence(tmp_path, requirement)

    assert row["status"] == "INVALID"
    assert "mode must not be EXTERNAL_EVIDENCE_GAP_RECORD" in row["errors"]
    assert "missing_inputs must be absent or empty for VERIFIED evidence" in row["errors"]
    assert "failures must be absent or empty for VERIFIED evidence" in row["errors"]
    assert "claim_boundary.claim_verified must not be false for VERIFIED evidence" in row["errors"]


def test_proof_gate_rejects_incoming_example_placeholder_markers(tmp_path):
    proof = _load_module()
    requirement = proof.EXTERNAL_REQUIREMENTS[3]
    evidence_path = _write_external_evidence(tmp_path, proof, requirement)
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload["mode"] = proof.INCOMING_EXAMPLE_MODE
    payload["observed_at_utc"] = "REPLACE_WITH_REAL_OBSERVATION_TIME_UTC"
    payload["commands"] = [
        {
            "args": ["REPLACE_WITH_REAL_COLLECTION_OR_REVIEW_COMMAND"],
            "exit_code": 0,
        }
    ]
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    row = proof.validate_external_evidence(tmp_path, requirement)

    assert row["status"] == "INVALID"
    assert f"mode must not be {proof.INCOMING_EXAMPLE_MODE}" in row["errors"]
    assert "payload.mode contains placeholder marker: INCOMING_CANDIDATE_EXAMPLE_NOT_EVIDENCE" in row["errors"]
    assert "payload.observed_at_utc contains placeholder marker: REPLACE_WITH" in row["errors"]
    assert "payload.commands[0].args[0] contains placeholder marker: REPLACE_WITH" in row["errors"]


def test_proof_gate_rejects_non_utc_observation_time(tmp_path):
    proof = _load_module()
    requirement = proof.EXTERNAL_REQUIREMENTS[3]
    evidence_path = _write_external_evidence(tmp_path, proof, requirement)
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))

    payload["observed_at_utc"] = "2026-05-22T03:00:00+03:00"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")
    row = proof.validate_external_evidence(tmp_path, requirement)
    assert row["status"] == "INVALID"
    assert "observed_at_utc must be UTC" in row["errors"]

    payload["observed_at_utc"] = "2026-05-22T00:00:00"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")
    row = proof.validate_external_evidence(tmp_path, requirement)
    assert row["status"] == "INVALID"
    assert "observed_at_utc must include a UTC timezone" in row["errors"]

    payload["observed_at_utc"] = "not-a-timestamp"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")
    row = proof.validate_external_evidence(tmp_path, requirement)
    assert row["status"] == "INVALID"
    assert "observed_at_utc must be an ISO-8601 timestamp" in row["errors"]


def test_proof_gate_rejects_kernel_attach_without_required_commands(tmp_path):
    proof = _load_module()
    requirement = proof.EXTERNAL_REQUIREMENTS[0]
    evidence_path = _write_external_evidence(tmp_path, proof, requirement)
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload["commands"] = [{"args": ["proof-fixture", "kernel_attach"], "exit_code": 0}]
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    row = proof.validate_external_evidence(tmp_path, requirement)

    assert row["status"] == "INVALID"
    assert "required command not observed: ip -j link show recorded" in row["errors"]
    assert "required command not observed: bpftool prog show" in row["errors"]


def test_proof_gate_rejects_non_string_command_args_and_bool_exit_code(tmp_path):
    proof = _load_module()
    requirement = proof.EXTERNAL_REQUIREMENTS[3]
    evidence_path = _write_external_evidence(tmp_path, proof, requirement)
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload["commands"] = [
        {
            "args": ["external-fixture", 123, ""],
            "exit_code": False,
        }
    ]
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    row = proof.validate_external_evidence(tmp_path, requirement)

    assert row["status"] == "INVALID"
    assert "commands[0].args[1] must be a non-empty string" in row["errors"]
    assert "commands[0].args[2] must be a non-empty string" in row["errors"]
    assert "commands[0].exit_code must be integer 0" in row["errors"]


def test_proof_gate_rejects_kernel_attach_without_required_artifact_roles(tmp_path):
    proof = _load_module()
    requirement = proof.EXTERNAL_REQUIREMENTS[0]
    evidence_path = _write_external_evidence(tmp_path, proof, requirement)
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    for artifact in payload["artifacts"]:
        artifact.pop("role")
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    row = proof.validate_external_evidence(tmp_path, requirement)

    assert row["status"] == "INVALID"
    assert "artifacts[0].role is required" in row["errors"]
    assert "required artifact role missing: kernel_commands" in row["errors"]


def test_proof_gate_rejects_kernel_attach_artifact_content_mismatch(tmp_path):
    proof = _load_module()
    requirement = proof.EXTERNAL_REQUIREMENTS[0]
    evidence_path = _write_external_evidence(tmp_path, proof, requirement)
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    measurements_artifact = _artifact_by_role(payload, "kernel_measurements")
    measurements_path = tmp_path / measurements_artifact["path"]
    measurements_payload = json.loads(measurements_path.read_text(encoding="utf-8"))
    measurements_payload["measurements"]["interface"] = "different-interface"
    measurements_path.write_text(json.dumps(measurements_payload, sort_keys=True), encoding="utf-8")
    measurements_artifact["sha256"] = proof.sha256_file(measurements_path)
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    row = proof.validate_external_evidence(tmp_path, requirement)

    assert row["status"] == "INVALID"
    assert (
        "artifact role kernel_measurements JSON must match payload fields: "
        "measurements, failures, claim_boundary"
    ) in row["errors"]


def test_proof_gate_rejects_packet_capture_without_required_artifact_roles(tmp_path):
    proof = _load_module()
    requirement = proof.EXTERNAL_REQUIREMENTS[1]
    evidence_path = _write_external_evidence(tmp_path, proof, requirement)
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    for artifact in payload["artifacts"]:
        artifact.pop("role")
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    row = proof.validate_external_evidence(tmp_path, requirement)

    assert row["status"] == "INVALID"
    assert "artifacts[0].role is required" in row["errors"]
    assert "required artifact role missing: sender_pcap" in row["errors"]


def test_proof_gate_rejects_duplicate_required_artifact_roles(tmp_path):
    proof = _load_module()
    requirement = proof.EXTERNAL_REQUIREMENTS[1]
    evidence_path = _write_external_evidence(tmp_path, proof, requirement)
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload["artifacts"][1]["role"] = "sender_pcap"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    row = proof.validate_external_evidence(tmp_path, requirement)

    assert row["status"] == "INVALID"
    assert "duplicate artifact role: sender_pcap" in row["errors"]
    assert "required artifact role missing: receiver_pcap" in row["errors"]


def test_proof_gate_rejects_reused_artifact_path_for_required_roles(tmp_path):
    proof = _load_module()
    requirement = proof.EXTERNAL_REQUIREMENTS[1]
    evidence_path = _write_external_evidence(tmp_path, proof, requirement)
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload["artifacts"][1]["path"] = payload["artifacts"][0]["path"]
    payload["artifacts"][1]["sha256"] = payload["artifacts"][0]["sha256"]
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    row = proof.validate_external_evidence(tmp_path, requirement)

    assert row["status"] == "INVALID"
    assert "artifact path reused for required roles: sender_pcap, receiver_pcap" in row["errors"]


def test_proof_gate_rejects_packet_capture_measurement_artifact_sha_mismatch(tmp_path):
    proof = _load_module()
    requirement = proof.EXTERNAL_REQUIREMENTS[1]
    evidence_path = _write_external_evidence(tmp_path, proof, requirement)
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload["measurements"]["sender_pcap_sha256"] = "0" * 64
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    row = proof.validate_external_evidence(tmp_path, requirement)

    assert row["status"] == "INVALID"
    assert (
        "measurements.sender_pcap_sha256 must match artifact role sender_pcap sha256"
        in row["errors"]
    )


def test_proof_gate_rejects_packet_capture_pcap_count_mismatch(tmp_path):
    proof = _load_module()
    requirement = proof.EXTERNAL_REQUIREMENTS[1]
    evidence_path = _write_external_evidence(tmp_path, proof, requirement)
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload["measurements"]["sender_pcap_packets"] = 99
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    row = proof.validate_external_evidence(tmp_path, requirement)

    assert row["status"] == "INVALID"
    assert (
        "measurements.sender_pcap_packets must match artifact role sender_pcap pcap packet count"
        in row["errors"]
    )
    assert (
        "measurements.sender_pcap_packets must match artifact role sender_events jsonl record count"
        in row["errors"]
    )


def test_proof_gate_rejects_packet_capture_payload_hash_mismatch(tmp_path):
    proof = _load_module()
    requirement = proof.EXTERNAL_REQUIREMENTS[1]
    evidence_path = _write_external_evidence(tmp_path, proof, requirement)
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    sender_events = next(artifact for artifact in payload["artifacts"] if artifact["role"] == "sender_events")
    sender_events_path = tmp_path / sender_events["path"]
    lines = sender_events_path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["payload_sha256"] = "0" * 64
    lines[0] = json.dumps(first, sort_keys=True)
    sender_events_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    sender_events["sha256"] = proof.sha256_file(sender_events_path)
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    row = proof.validate_external_evidence(tmp_path, requirement)

    assert row["status"] == "INVALID"
    assert (
        "artifact role sender_events payload_sha256 sequence must match pcap role sender_pcap UDP payloads"
        in row["errors"]
    )
    assert (
        "artifact role receiver_events payload_sha256 sequence must match artifact role sender_events"
        in row["errors"]
    )


def test_proof_gate_rejects_baseline_measurement_artifact_sha_mismatch(tmp_path):
    proof = _load_module()
    requirement = proof.EXTERNAL_REQUIREMENTS[2]
    evidence_path = _write_external_evidence(tmp_path, proof, requirement)
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload["measurements"]["baseline_digest"] = "0" * 64
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    row = proof.validate_external_evidence(tmp_path, requirement)

    assert row["status"] == "INVALID"
    assert (
        "measurements.baseline_digest must match artifact role baseline_events sha256"
        in row["errors"]
    )


def test_proof_gate_rejects_baseline_sample_count_mismatch(tmp_path):
    proof = _load_module()
    requirement = proof.EXTERNAL_REQUIREMENTS[2]
    evidence_path = _write_external_evidence(tmp_path, proof, requirement)
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload["measurements"]["sample_count"] = 99
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    row = proof.validate_external_evidence(tmp_path, requirement)

    assert row["status"] == "INVALID"
    assert (
        "measurements.sample_count must match paired jsonl gap count for roles baseline_events, pulse_events"
        in row["errors"]
    )


def test_proof_gate_rejects_baseline_timing_comparison_artifact_content_mismatch(tmp_path):
    proof = _load_module()
    requirement = proof.EXTERNAL_REQUIREMENTS[2]
    evidence_path = _write_external_evidence(tmp_path, proof, requirement)
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    comparison_artifact = _artifact_by_role(payload, "timing_comparison")
    comparison_path = tmp_path / comparison_artifact["path"]
    comparison_payload = json.loads(comparison_path.read_text(encoding="utf-8"))
    comparison_payload["comparison"]["pulse_status"] = "TAMPERED"
    comparison_path.write_text(json.dumps(comparison_payload, sort_keys=True), encoding="utf-8")
    comparison_artifact["sha256"] = proof.sha256_file(comparison_path)
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    row = proof.validate_external_evidence(tmp_path, requirement)

    assert row["status"] == "INVALID"
    assert (
        "artifact role timing_comparison JSON must match payload fields: "
        "measurements, comparison, failures"
    ) in row["errors"]


def test_proof_gate_rejects_absolute_artifact_path(tmp_path):
    proof = _load_module()
    requirement = proof.EXTERNAL_REQUIREMENTS[1]
    evidence_path = _write_external_evidence(tmp_path, proof, requirement)
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload["artifacts"][0]["path"] = str((tmp_path / "docs/verification/ghost-pulse-proof-fixtures/abs.txt").resolve())
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    row = proof.validate_external_evidence(tmp_path, requirement)

    assert row["status"] == "INVALID"
    assert "artifact path must be repo-relative:" in "\n".join(row["errors"])


def test_proof_gate_rejects_artifact_path_outside_verification_tree(tmp_path):
    proof = _load_module()
    requirement = proof.EXTERNAL_REQUIREMENTS[1]
    evidence_path = _write_external_evidence(tmp_path, proof, requirement)
    outside = tmp_path / "outside-artifact.txt"
    outside.write_text("outside artifact\n", encoding="utf-8")
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload["artifacts"][0]["path"] = proof.display_path(tmp_path, outside)
    payload["artifacts"][0]["sha256"] = proof.sha256_file(outside)
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    row = proof.validate_external_evidence(tmp_path, requirement)

    assert row["status"] == "INVALID"
    assert "artifact path must stay under docs/verification: outside-artifact.txt" in row["errors"]
    assert not any("artifact role sender_pcap pcap:" in error for error in row["errors"])


def test_proof_gate_rejects_symlink_artifact_path_without_loading_target(tmp_path):
    proof = _load_module()
    requirement = proof.EXTERNAL_REQUIREMENTS[1]
    evidence_path = _write_external_evidence(tmp_path, proof, requirement)
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    target = tmp_path / payload["artifacts"][0]["path"]
    symlink = target.with_name("sender-pcap-symlink.pcap")
    symlink.symlink_to(target)
    payload["artifacts"][0]["path"] = proof.display_path(tmp_path, symlink)
    payload["artifacts"][0]["sha256"] = proof.sha256_file(target)
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    row = proof.validate_external_evidence(tmp_path, requirement)

    assert row["status"] == "INVALID"
    assert (
        "artifact path must not include symlink components: "
        "docs/verification/ghost-pulse-proof-fixtures/packet_capture/sender-pcap-symlink.pcap"
    ) in row["errors"]
    assert (
        "artifact role sender_pcap: artifact path must not include symlink components: "
        "docs/verification/ghost-pulse-proof-fixtures/packet_capture/sender-pcap-symlink.pcap"
    ) in row["errors"]
    assert not any("sender_pcap pcap:" in error for error in row["errors"])


def test_proof_gate_does_not_load_structured_artifact_outside_verification_tree(tmp_path):
    proof = _load_module()
    requirement = proof.EXTERNAL_REQUIREMENTS[3]
    evidence_path = _write_external_evidence(tmp_path, proof, requirement)
    outside = tmp_path / "outside-lab-conclusion.json"
    outside.write_text("{not-json", encoding="utf-8")
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    artifact = _artifact_by_role(payload, "lab_conclusion")
    artifact["path"] = proof.display_path(tmp_path, outside)
    artifact["sha256"] = proof.sha256_file(outside)
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    row = proof.validate_external_evidence(tmp_path, requirement)

    assert row["status"] == "INVALID"
    assert "artifact path must stay under docs/verification: outside-lab-conclusion.json" in row["errors"]
    assert (
        "artifact role lab_conclusion: artifact path must stay under docs/verification: "
        "outside-lab-conclusion.json"
    ) in row["errors"]
    assert not any("json content could not be loaded" in error for error in row["errors"])


def test_proof_gate_rejects_artifact_directory_without_crashing(tmp_path):
    proof = _load_module()
    requirement = proof.EXTERNAL_REQUIREMENTS[1]
    evidence_path = _write_external_evidence(tmp_path, proof, requirement)
    artifact_dir = tmp_path / "docs/verification/ghost-pulse-proof-fixtures/not-a-file"
    artifact_dir.mkdir(parents=True)
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload["artifacts"][0]["path"] = proof.display_path(tmp_path, artifact_dir)
    payload["artifacts"][0]["sha256"] = proof.sha256_file(artifact_dir)
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    row = proof.validate_external_evidence(tmp_path, requirement)

    assert row["status"] == "INVALID"
    assert (
        "artifacts[0] path is not a regular file: "
        "docs/verification/ghost-pulse-proof-fixtures/not-a-file"
    ) in row["errors"]
    assert "artifact role path is not a regular file for content check: sender_pcap" in row["errors"]


def test_proof_gate_rejects_dpi_lab_without_required_artifact_roles(tmp_path):
    proof = _load_module()
    requirement = proof.EXTERNAL_REQUIREMENTS[3]
    evidence_path = _write_external_evidence(tmp_path, proof, requirement)
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    for artifact in payload["artifacts"]:
        artifact.pop("role")
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    row = proof.validate_external_evidence(tmp_path, requirement)

    assert row["status"] == "INVALID"
    assert "artifacts[0].role is required" in row["errors"]
    assert "required artifact role missing: lab_scope" in row["errors"]


def test_proof_gate_rejects_artifact_file_placeholder_markers(tmp_path):
    proof = _load_module()
    requirement = proof.EXTERNAL_REQUIREMENTS[3]
    evidence_path = _write_external_evidence(tmp_path, proof, requirement)
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    scope_artifact = _artifact_by_role(payload, "lab_scope")
    scope_path = tmp_path / scope_artifact["path"]
    scope_path.write_text("authorized lab scope: REPLACE_WITH_REAL_SCOPE\n", encoding="utf-8")
    scope_artifact["sha256"] = proof.sha256_file(scope_path)
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    row = proof.validate_external_evidence(tmp_path, requirement)

    assert row["status"] == "INVALID"
    assert "artifacts[0] file contains placeholder marker: REPLACE_WITH" in row["errors"]


def test_proof_gate_rejects_external_claim_structured_artifact_mismatch(tmp_path):
    proof = _load_module()
    cases = [
        (3, "lab_conclusion"),
        (4, "whitelist_conclusion"),
        (5, "findings_report"),
    ]
    for requirement_index, role in cases:
        requirement = proof.EXTERNAL_REQUIREMENTS[requirement_index]
        evidence_path = _write_external_evidence(tmp_path, proof, requirement)
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        artifact = _artifact_by_role(payload, role)
        artifact_path = tmp_path / artifact["path"]
        artifact_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        artifact_payload["measurements"] = {"tampered": True}
        artifact_path.write_text(json.dumps(artifact_payload, sort_keys=True), encoding="utf-8")
        artifact["sha256"] = proof.sha256_file(artifact_path)
        evidence_path.write_text(json.dumps(payload), encoding="utf-8")

        row = proof.validate_external_evidence(tmp_path, requirement)

        assert row["status"] == "INVALID"
        assert (
            f"artifact role {role} JSON must match payload fields: "
            "measurements, failures, claim_boundary"
        ) in row["errors"]


def test_proof_gate_rejects_production_readiness_reference_artifact_mismatch(tmp_path):
    proof = _load_module()
    production = proof.EXTERNAL_REQUIREMENTS[-1]
    for requirement in proof.EXTERNAL_REQUIREMENTS[:-1]:
        _write_external_evidence(tmp_path, proof, requirement)
    evidence_path = _write_external_evidence(tmp_path, proof, production)
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    artifact = _artifact_by_role(payload, "prior_claim_references")
    artifact_path = tmp_path / artifact["path"]
    artifact_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    artifact_payload["references"][0]["sha256"] = "0" * 64
    artifact_path.write_text(json.dumps(artifact_payload, sort_keys=True), encoding="utf-8")
    artifact["sha256"] = proof.sha256_file(artifact_path)
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    row = proof.validate_external_evidence(tmp_path, production)

    assert row["status"] == "INVALID"
    assert (
        "artifact role prior_claim_references JSON must match payload fields: "
        "measurements, references, failures, claim_boundary"
    ) in row["errors"]


def test_proof_gate_rejects_production_readiness_without_prior_references(tmp_path):
    proof = _load_module()
    production = proof.EXTERNAL_REQUIREMENTS[-1]
    for requirement in proof.EXTERNAL_REQUIREMENTS[:-1]:
        _write_external_evidence(tmp_path, proof, requirement)
    evidence_path = _write_external_evidence(tmp_path, proof, production)
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload.pop("references")
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    row = proof.validate_external_evidence(tmp_path, production)

    assert row["status"] == "INVALID"
    assert "references must be a non-empty list" in row["errors"]


def test_proof_gate_rejects_production_readiness_with_stale_prior_reference(tmp_path):
    proof = _load_module()
    production = proof.EXTERNAL_REQUIREMENTS[-1]
    for requirement in proof.EXTERNAL_REQUIREMENTS[:-1]:
        _write_external_evidence(tmp_path, proof, requirement)
    evidence_path = _write_external_evidence(tmp_path, proof, production)
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload["references"][0]["sha256"] = "0" * 64
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    row = proof.validate_external_evidence(tmp_path, production)

    assert row["status"] == "INVALID"
    assert "references.kernel_attach.sha256 does not match current evidence validation" in row["errors"]


def test_proof_gate_can_pass_with_complete_fixture_evidence(tmp_path):
    proof = _load_module()
    suite_path = _write_suite(tmp_path)
    for requirement in proof.EXTERNAL_REQUIREMENTS:
        _write_external_evidence(tmp_path, proof, requirement)

    report = proof.build_report(
        root=tmp_path,
        suite_path=suite_path,
        suite_failure_provider=_suite_failures,
        artifact_chain_provider=_artifact_chain,
        replacement_candidate_provider=_replacement_candidates,
        current_runtime_provider=_current_runtime_verified,
    )

    assert report["decision"] == proof.DECISION_PROVEN
    assert report["not_verified_yet"] == []
    assert report["failures"] == []
    assert report["claim_boundary"]["stealth_verified"] is True
    assert report["claim_boundary"]["whitelist_verified"] is True
    assert report["claim_boundary"]["kernel_attach_verified"] is True
    assert report["claim_boundary"]["current_runtime_attached"] is True
    assert report["claim_boundary"]["production_ready"] is True


def test_proof_gate_blocks_production_when_current_runtime_is_not_attached(tmp_path):
    proof = _load_module()
    suite_path = _write_suite(tmp_path)
    for requirement in proof.EXTERNAL_REQUIREMENTS:
        _write_external_evidence(tmp_path, proof, requirement)

    report = proof.build_report(
        root=tmp_path,
        suite_path=suite_path,
        suite_failure_provider=_suite_failures,
        artifact_chain_provider=_artifact_chain,
        replacement_candidate_provider=_replacement_candidates,
        current_runtime_provider=_current_runtime_invalid,
    )

    assert report["decision"] == proof.DECISION_INCOMPLETE
    assert report["claim_boundary"]["kernel_attach_verified"] is True
    assert report["claim_boundary"]["current_runtime_attached"] is False
    assert report["claim_boundary"]["production_ready"] is False
    assert proof.CURRENT_RUNTIME_CLAIM_ID in report["not_verified_yet"]
    assert f"{proof.CURRENT_RUNTIME_CLAIM_ID}: current runtime is not attached" in report["failures"]


def test_proof_gate_writes_latest_and_bundle_outputs_atomically(tmp_path):
    proof = _load_module()
    suite_path = _write_suite(tmp_path)
    report = proof.build_report(
        root=tmp_path,
        suite_path=suite_path,
        suite_failure_provider=_suite_failures,
        artifact_chain_provider=_artifact_chain,
        replacement_candidate_provider=_replacement_candidates,
    )
    output_json = tmp_path / "docs/verification/GHOST_PULSE_PROOF_GATE_LATEST.json"
    output_md = tmp_path / "docs/verification/GHOST_PULSE_PROOF_GATE_LATEST.md"

    paths = proof.write_report_outputs(tmp_path, report, output_json, output_md)

    assert paths["latest_json"].exists()
    assert paths["latest_md"].exists()
    assert paths["bundle_json"].read_text(encoding="utf-8") == paths["latest_json"].read_text(encoding="utf-8")
    assert paths["bundle_md"].read_text(encoding="utf-8") == paths["latest_md"].read_text(encoding="utf-8")
    assert list(paths["latest_json"].parent.glob(".*.tmp")) == []
    assert list(paths["bundle_json"].parent.glob(".*.tmp")) == []


def test_proof_gate_blocks_all_claims_proven_when_replacement_preflight_is_stale(tmp_path):
    proof = _load_module()
    suite_path = _write_suite(tmp_path)
    for requirement in proof.EXTERNAL_REQUIREMENTS:
        _write_external_evidence(tmp_path, proof, requirement)

    report = proof.build_report(
        root=tmp_path,
        suite_path=suite_path,
        suite_failure_provider=_suite_failures,
        artifact_chain_provider=_artifact_chain,
        replacement_candidate_provider=_replacement_candidates_failed,
        current_runtime_provider=_current_runtime_verified,
    )

    assert report["decision"] == proof.DECISION_INCOMPLETE
    assert report["claim_boundary"]["stealth_verified"] is True
    assert report["claim_boundary"]["whitelist_verified"] is True
    assert report["claim_boundary"]["kernel_attach_verified"] is True
    assert report["claim_boundary"]["current_runtime_attached"] is True
    assert report["claim_boundary"]["production_ready"] is False
    assert "replacement_candidates: saved preflight report is stale" in report["failures"]
