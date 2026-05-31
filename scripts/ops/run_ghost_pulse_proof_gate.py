#!/usr/bin/env python3
"""Build a fail-closed proof gate for x0tta6bl4_pulse claims.

The gate separates what is locally proven from what still needs controlled lab
or production evidence. It does not run packet probes, attach XDP programs,
mutate routes, touch runtime services, or upgrade any claim by itself.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
VERIFY_ROOT = ROOT / "docs" / "verification"
DEFAULT_SUITE = VERIFY_ROOT / "GHOST_PULSE_VERIFICATION_SUITE_LATEST.json"
DEFAULT_REPLACEMENT_CANDIDATES = VERIFY_ROOT / "GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json"
DEFAULT_OUTPUT_JSON = VERIFY_ROOT / "GHOST_PULSE_PROOF_GATE_LATEST.json"
DEFAULT_OUTPUT_MD = VERIFY_ROOT / "GHOST_PULSE_PROOF_GATE_LATEST.md"

SCHEMA = "x0tta6bl4.ghost_pulse.proof_gate.v1"
EVIDENCE_SCHEMA = "x0tta6bl4.ghost_pulse.claim_evidence.v1"
DECISION_PROVEN = "GHOST_PULSE_ALL_CLAIMS_PROVEN"
DECISION_INCOMPLETE = "GHOST_PULSE_PROOF_INCOMPLETE"
INCOMING_EXAMPLE_MODE = "INCOMING_CANDIDATE_EXAMPLE_NOT_EVIDENCE"
PLACEHOLDER_MARKERS = (
    "REPLACE_WITH",
    "EXAMPLE_ONLY_NOT_EVIDENCE",
    INCOMING_EXAMPLE_MODE,
)
REPLACEMENT_CANDIDATE_DECISIONS = (
    "REPLACEMENT_CANDIDATES_READY",
    "REPLACEMENT_CANDIDATES_NOT_READY",
)
REPLACEMENT_CANDIDATE_BOUNDARY_KEYS = (
    "stealth_verified",
    "whitelist_verified",
    "kernel_attach_verified",
    "production_ready",
)
PRODUCTION_READINESS_REFERENCE_CLAIMS = (
    "kernel_attach",
    "packet_capture",
    "baseline_timing_comparison",
    "dpi_lab",
    "whitelist_lab",
    "security_review",
)
CURRENT_RUNTIME_CLAIM_ID = "current_runtime_attached"
CURRENT_RUNTIME_TITLE = "Current runtime x0tta6bl4_pulse XDP attach"
RUNTIME_INTERFACE_ENV = "GHOST_PULSE_RUNTIME_INTERFACE"

EXTERNAL_REQUIREMENTS: tuple[dict[str, Any], ...] = (
    {
        "claim_id": "kernel_attach",
        "title": "XDP attach and map-counter evidence",
        "path": "docs/verification/GHOST_PULSE_KERNEL_ATTACH_LATEST.json",
        "measurements": {
            "interface": "nonempty",
            "xdp_attached": True,
            "bpftool_prog_show_contains_pulse": True,
            "bpftool_net_contains_interface": True,
            "map_counter_delta_packets": "positive_int",
        },
        "required_commands": [
            ["uname", "-r"],
            ["ip", "-d", "-j", "link", "show"],
            ["ip", "-j", "link", "show", "<interface>"],
            ["ip", "-d", "-j", "link", "show", "<interface>"],
            ["bpftool", "prog", "show"],
            ["bpftool", "net"],
            ["bpftool", "map", "show", "name", "pulse_stats"],
            ["bpftool", "map", "dump", "name", "pulse_stats"],
            ["bpftool", "map", "dump", "name", "pulse_stats"],
        ],
        "required_artifact_roles": [
            "kernel_commands",
            "kernel_measurements",
            "kernel_interface_scan",
            "kernel_candidate_audit",
        ],
        "json_artifact_payload_links": {
            "kernel_commands": "commands",
            "kernel_interface_scan": "interface_scan",
            "kernel_candidate_audit": "candidate_audit",
        },
        "json_artifact_object_field_links": {
            "kernel_measurements": [
                "measurements",
                "failures",
                "claim_boundary",
            ],
        },
    },
    {
        "claim_id": "packet_capture",
        "title": "Sender and receiver packet captures",
        "path": "docs/verification/GHOST_PULSE_PACKET_CAPTURE_LATEST.json",
        "measurements": {
            "sender_pcap_packets": "positive_int",
            "receiver_pcap_packets": "positive_int",
            "sender_pcap_sha256": "sha256",
            "receiver_pcap_sha256": "sha256",
        },
        "required_artifact_roles": [
            "sender_pcap",
            "receiver_pcap",
            "sender_events",
            "receiver_events",
            "capture_summary",
        ],
        "artifact_sha256_measurements": {
            "sender_pcap": "sender_pcap_sha256",
            "receiver_pcap": "receiver_pcap_sha256",
        },
        "pcap_packet_count_measurements": {
            "sender_pcap": "sender_pcap_packets",
            "receiver_pcap": "receiver_pcap_packets",
        },
        "jsonl_record_count_measurements": {
            "sender_events": "sender_pcap_packets",
            "receiver_events": "receiver_pcap_packets",
        },
        "pcap_payload_sha256_jsonl_roles": {
            "sender_pcap": "sender_events",
            "receiver_pcap": "receiver_events",
        },
        "paired_jsonl_payload_sha256_roles": [
            ["sender_events", "receiver_events"],
        ],
    },
    {
        "claim_id": "baseline_timing_comparison",
        "title": "Baseline-vs-pulse timing comparison",
        "path": "docs/verification/GHOST_PULSE_BASELINE_COMPARISON_LATEST.json",
        "measurements": {
            "sample_count": "positive_int",
            "baseline_digest": "sha256",
            "pulse_digest": "sha256",
            "comparison_passed": True,
        },
        "required_artifact_roles": [
            "baseline_events",
            "pulse_events",
            "timing_comparison",
        ],
        "artifact_sha256_measurements": {
            "baseline_events": "baseline_digest",
            "pulse_events": "pulse_digest",
        },
        "paired_jsonl_gap_count_measurements": [
            {
                "roles": ["baseline_events", "pulse_events"],
                "measurement": "sample_count",
            }
        ],
        "json_artifact_object_field_links": {
            "timing_comparison": [
                "measurements",
                "comparison",
                "failures",
            ],
        },
    },
    {
        "claim_id": "dpi_lab",
        "title": "Authorized DPI lab result",
        "path": "docs/verification/GHOST_PULSE_DPI_LAB_LATEST.json",
        "measurements": {
            "authorized_lab": True,
            "baseline_detected_or_blocked": True,
            "pulse_result_recorded": True,
            "dpi_bypass_verified": True,
        },
        "required_artifact_roles": [
            "lab_scope",
            "baseline_result",
            "pulse_result",
            "lab_conclusion",
        ],
        "json_artifact_object_field_links": {
            "lab_conclusion": [
                "measurements",
                "failures",
                "claim_boundary",
            ],
        },
    },
    {
        "claim_id": "whitelist_lab",
        "title": "Authorized whitelist-behavior lab result",
        "path": "docs/verification/GHOST_PULSE_WHITELIST_LAB_LATEST.json",
        "measurements": {
            "authorized_provider_or_lab": True,
            "provider_profile": "nonempty",
            "third_party_baseline_captured": True,
            "whitelist_behavior_verified": True,
        },
        "required_artifact_roles": [
            "provider_or_lab_authorization",
            "provider_profile",
            "third_party_baseline_capture",
            "whitelist_conclusion",
        ],
        "json_artifact_object_field_links": {
            "whitelist_conclusion": [
                "measurements",
                "failures",
                "claim_boundary",
            ],
        },
    },
    {
        "claim_id": "security_review",
        "title": "Security review with no open high-severity findings",
        "path": "docs/verification/GHOST_PULSE_SECURITY_REVIEW_LATEST.json",
        "measurements": {
            "reviewer": "nonempty",
            "scope_includes_pulse_transport": True,
            "open_critical_findings": 0,
            "open_high_findings": 0,
        },
        "required_artifact_roles": [
            "reviewer_identity",
            "review_scope",
            "findings_report",
        ],
        "json_artifact_object_field_links": {
            "findings_report": [
                "measurements",
                "failures",
                "claim_boundary",
            ],
        },
    },
    {
        "claim_id": "production_readiness",
        "title": "Production readiness approval and rollback evidence",
        "path": "docs/verification/GHOST_PULSE_PRODUCTION_READINESS_LATEST.json",
        "measurements": {
            "production_ready": "bool_true",
            "rollback_plan_verified": True,
            "monitoring_plan_verified": True,
            "operator_approval_recorded": True,
            "all_prior_claims_referenced": True,
        },
        "required_artifact_roles": [
            "operator_approval",
            "rollback_plan",
            "monitoring_plan",
            "prior_claim_references",
        ],
        "required_references": list(PRODUCTION_READINESS_REFERENCE_CLAIMS),
        "json_artifact_object_field_links": {
            "prior_claim_references": [
                "measurements",
                "references",
                "failures",
                "claim_boundary",
            ],
        },
    },
)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def atomic_write_text(path: Path, text: str) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
    finally:
        if tmp.exists():
            tmp.unlink()


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def display_path(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def resolve_path(root: Path, value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value)
    return path if path.is_absolute() else root / path


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def default_suite_failures(root: Path, suite_path: Path) -> list[str]:
    verifier = load_module(
        "verify_ghost_pulse_verification_suite_for_proof_gate",
        root / "scripts" / "ops" / "verify_ghost_pulse_verification_suite.py",
    )
    return verifier.verify_suite(suite_path, root)


def default_artifact_chain_report(root: Path, suite_path: Path) -> dict[str, Any]:
    chain = load_module(
        "verify_ghost_pulse_artifact_chain_for_proof_gate",
        root / "scripts" / "ops" / "verify_ghost_pulse_artifact_chain.py",
    )
    return chain.build_report(root=root, suite_path=suite_path)


def default_replacement_candidate_preflight(root: Path, report_path: Path) -> dict[str, Any]:
    verifier = load_module(
        "verify_ghost_pulse_replacement_candidates_for_proof_gate",
        root / "scripts" / "ops" / "verify_ghost_pulse_replacement_candidates.py",
    )
    failures = verifier.verify_saved_report(report_path, root)
    try:
        data = load_json(report_path) if report_path.exists() else {}
    except Exception:
        data = {}
    return replacement_candidate_preflight_summary(root, report_path, data, failures)


def replacement_candidate_preflight_summary(
    root: Path,
    report_path: Path,
    data: dict[str, Any],
    verifier_failures: list[str],
) -> dict[str, Any]:
    claim_boundary = data.get("claim_boundary", {})
    failures = list(verifier_failures)
    if not isinstance(claim_boundary, dict):
        failures.append("replacement_candidates.claim_boundary must be an object")
        claim_boundary = {}
    for key in REPLACEMENT_CANDIDATE_BOUNDARY_KEYS:
        if claim_boundary.get(key) is not False:
            failures.append(f"replacement_candidates.claim_boundary.{key} must remain false")
    if data.get("decision") not in (*REPLACEMENT_CANDIDATE_DECISIONS, None):
        failures.append(f"replacement_candidates.decision is unexpected: {data.get('decision')}")
    return {
        "report": display_path(root, report_path),
        "sha256": sha256_file(report_path),
        "status": "PASS" if not failures else "FAIL",
        "decision": data.get("decision"),
        "replacement_required": data.get("replacement_required", []),
        "ready": data.get("ready", []),
        "not_ready": data.get("not_ready", []),
        "missing_candidates": data.get("missing_candidates", []),
        "claim_boundary": claim_boundary,
        "verifier_command": [
            "python3",
            "scripts/ops/verify_ghost_pulse_replacement_candidates.py",
            "--report",
            display_path(root, report_path),
            "--json",
        ],
        "failures": failures,
    }


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def measurement_matches(value: Any, expectation: Any) -> bool:
    if expectation == "nonempty":
        return isinstance(value, str) and bool(value.strip())
    if expectation == "positive_int":
        return isinstance(value, int) and value > 0
    if expectation == "sha256":
        return is_sha256(value)
    if expectation == "bool_true":
        return value is True
    return value == expectation


def render_command_template(template: list[str], measurements: dict[str, Any]) -> list[str]:
    rendered: list[str] = []
    for part in template:
        if part == "<interface>":
            rendered.append(str(measurements.get("interface", "")))
        else:
            rendered.append(part)
    return rendered


def missing_required_commands(
    commands: list[dict[str, Any]],
    templates: list[list[str]],
    measurements: dict[str, Any],
) -> list[list[str]]:
    available = [
        [str(part) for part in command.get("args", [])]
        for command in commands
        if isinstance(command, dict) and isinstance(command.get("args"), list)
    ]
    missing: list[list[str]] = []
    used_indexes: set[int] = set()
    for template in templates:
        expected = render_command_template(template, measurements)
        match_index = None
        for index, args in enumerate(available):
            if index in used_indexes:
                continue
            if args == expected:
                match_index = index
                break
        if match_index is None:
            missing.append(expected)
        else:
            used_indexes.add(match_index)
    return missing


def external_requirement_contract(requirement: dict[str, Any]) -> dict[str, Any]:
    contract = {
        "claim_id": requirement["claim_id"],
        "title": requirement["title"],
        "path": requirement["path"],
        "measurements": requirement["measurements"],
    }
    if "required_artifact_roles" in requirement:
        contract["required_artifact_roles"] = requirement["required_artifact_roles"]
    if "required_commands" in requirement:
        contract["required_commands"] = requirement["required_commands"]
    if "required_references" in requirement:
        contract["required_references"] = requirement["required_references"]
    if "artifact_sha256_measurements" in requirement:
        contract["artifact_sha256_measurements"] = requirement["artifact_sha256_measurements"]
    if "pcap_packet_count_measurements" in requirement:
        contract["pcap_packet_count_measurements"] = requirement["pcap_packet_count_measurements"]
    if "jsonl_record_count_measurements" in requirement:
        contract["jsonl_record_count_measurements"] = requirement["jsonl_record_count_measurements"]
    if "paired_jsonl_gap_count_measurements" in requirement:
        contract["paired_jsonl_gap_count_measurements"] = requirement["paired_jsonl_gap_count_measurements"]
    if "pcap_payload_sha256_jsonl_roles" in requirement:
        contract["pcap_payload_sha256_jsonl_roles"] = requirement["pcap_payload_sha256_jsonl_roles"]
    if "paired_jsonl_payload_sha256_roles" in requirement:
        contract["paired_jsonl_payload_sha256_roles"] = requirement["paired_jsonl_payload_sha256_roles"]
    if "json_artifact_payload_links" in requirement:
        contract["json_artifact_payload_links"] = requirement["json_artifact_payload_links"]
    if "json_artifact_object_field_links" in requirement:
        contract["json_artifact_object_field_links"] = requirement["json_artifact_object_field_links"]
    contract["rejected_placeholder_markers"] = list(PLACEHOLDER_MARKERS)
    return contract


def requirement_by_claim() -> dict[str, dict[str, Any]]:
    return {item["claim_id"]: item for item in EXTERNAL_REQUIREMENTS}


def artifact_path_errors(root: Path, artifact_path: str) -> list[str]:
    path = Path(artifact_path)
    if path.is_absolute():
        return [f"artifact path must be repo-relative: {artifact_path}"]
    current = root
    for part in path.parts:
        current = current / part
        if current.is_symlink():
            return [f"artifact path must not include symlink components: {artifact_path}"]
    resolved = (root / path).resolve()
    verification_root = (root / "docs" / "verification").resolve()
    try:
        resolved.relative_to(verification_root)
    except ValueError:
        return [f"artifact path must stay under docs/verification: {artifact_path}"]
    return []


def validate_required_artifact_roles(root: Path, artifacts: Any, roles: list[str]) -> list[str]:
    if not isinstance(artifacts, list) or not artifacts:
        return ["artifacts must include required roles"]

    errors: list[str] = []
    observed: set[str] = set()
    artifact_path_by_role: dict[str, str] = {}
    required_artifact_paths: dict[str, str] = {}
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            continue
        role = artifact.get("role")
        if not isinstance(role, str) or not role.strip():
            errors.append(f"artifacts[{index}].role is required")
            continue
        artifact_path = artifact.get("path")
        if role in observed:
            errors.append(f"duplicate artifact role: {role}")
        observed.add(role)
        if isinstance(artifact_path, str) and artifact_path and role in roles:
            artifact_path_by_role[role] = artifact_path
            previous_role = required_artifact_paths.get(artifact_path)
            if previous_role and previous_role != role:
                errors.append(f"artifact path reused for required roles: {previous_role}, {role}")
            else:
                required_artifact_paths[artifact_path] = role

    for role in roles:
        if role not in observed:
            errors.append(f"required artifact role missing: {role}")
        elif role not in artifact_path_by_role:
            errors.append(f"required artifact role has no path: {role}")
    return errors


def validate_artifact_sha256_measurements(
    artifacts: Any,
    measurements: dict[str, Any],
    links: dict[str, str],
) -> list[str]:
    if not isinstance(artifacts, list):
        return ["artifacts must be a list before artifact sha256 measurement checks"]
    errors: list[str] = []
    sha_by_role = {
        artifact.get("role"): artifact.get("sha256")
        for artifact in artifacts
        if isinstance(artifact, dict) and isinstance(artifact.get("role"), str)
    }
    for role, measurement_key in links.items():
        artifact_sha = sha_by_role.get(role)
        measurement_sha = measurements.get(measurement_key)
        if artifact_sha is None:
            errors.append(f"artifact sha256 measurement role missing: {role}")
            continue
        if measurement_sha != artifact_sha:
            errors.append(
                f"measurements.{measurement_key} must match artifact role {role} sha256"
            )
    return errors


def artifact_by_role(artifacts: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(artifacts, list):
        return {}
    return {
        artifact["role"]: artifact
        for artifact in artifacts
        if isinstance(artifact, dict) and isinstance(artifact.get("role"), str)
    }


def artifact_path_for_role(root: Path, artifacts: Any, role: str) -> tuple[Path | None, list[str]]:
    artifact = artifact_by_role(artifacts).get(role)
    if not artifact:
        return None, [f"artifact role missing for content check: {role}"]
    artifact_path = artifact.get("path")
    if not isinstance(artifact_path, str) or not artifact_path:
        return None, [f"artifact role has no path for content check: {role}"]
    path_errors = artifact_path_errors(root, artifact_path)
    if path_errors:
        return None, [f"artifact role {role}: {error}" for error in path_errors]
    resolved = resolve_path(root, artifact_path)
    if not resolved or not resolved.exists():
        return resolved, [f"artifact role file missing for content check: {role}"]
    if not resolved.is_file():
        return resolved, [f"artifact role path is not a regular file for content check: {role}"]
    return resolved, []


def load_artifact_json(path: Path, role: str) -> tuple[Any | None, list[str]]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f), []
    except Exception as exc:
        return None, [f"artifact role {role} json content could not be loaded: {exc}"]


def validate_json_artifact_payload_links(
    root: Path,
    artifacts: Any,
    payload: dict[str, Any],
    links: dict[str, str],
) -> list[str]:
    errors: list[str] = []
    for role, payload_key in links.items():
        path, path_errors = artifact_path_for_role(root, artifacts, role)
        errors.extend(path_errors)
        if path_errors or not path:
            continue
        if payload_key not in payload:
            errors.append(f"payload.{payload_key} is required for artifact role {role} content check")
            continue
        artifact_payload, load_errors = load_artifact_json(path, role)
        errors.extend(load_errors)
        if load_errors:
            continue
        if artifact_payload != payload[payload_key]:
            errors.append(f"artifact role {role} JSON must match payload.{payload_key}")
    return errors


def validate_json_artifact_object_field_links(
    root: Path,
    artifacts: Any,
    payload: dict[str, Any],
    links: dict[str, list[str]],
) -> list[str]:
    errors: list[str] = []
    for role, payload_keys in links.items():
        path, path_errors = artifact_path_for_role(root, artifacts, role)
        errors.extend(path_errors)
        if path_errors or not path:
            continue
        if not isinstance(payload_keys, list) or not payload_keys:
            errors.append(f"artifact role {role} object field link must include payload fields")
            continue
        missing_keys = [key for key in payload_keys if key not in payload]
        for key in missing_keys:
            errors.append(f"payload.{key} is required for artifact role {role} content check")
        if missing_keys:
            continue
        artifact_payload, load_errors = load_artifact_json(path, role)
        errors.extend(load_errors)
        if load_errors:
            continue
        expected = {key: payload[key] for key in payload_keys}
        if artifact_payload != expected:
            errors.append(f"artifact role {role} JSON must match payload fields: {', '.join(payload_keys)}")
    return errors


def pcap_packet_count(path: Path) -> tuple[int | None, list[str]]:
    data = path.read_bytes()
    if len(data) < 24:
        return None, ["pcap is shorter than the global header"]
    magic = data[:4]
    if magic in (b"\xd4\xc3\xb2\xa1", b"M<\xb2\xa1"):
        endian = "<"
    elif magic in (b"\xa1\xb2\xc3\xd4", b"\xa1\xb2<M"):
        endian = ">"
    else:
        return None, [f"unsupported pcap magic: {magic.hex()}"]
    offset = 24
    count = 0
    while offset < len(data):
        if offset + 16 > len(data):
            return None, [f"truncated pcap packet header at offset {offset}"]
        _ts_sec, _ts_usec, included_len, _original_len = struct.unpack(
            f"{endian}IIII",
            data[offset : offset + 16],
        )
        offset += 16
        if offset + included_len > len(data):
            return None, [f"truncated pcap packet body at packet {count}"]
        offset += included_len
        count += 1
    return count, []


def pcap_udp_payload_sha256s(path: Path) -> tuple[list[str] | None, list[str]]:
    data = path.read_bytes()
    if len(data) < 24:
        return None, ["pcap is shorter than the global header"]
    magic = data[:4]
    if magic in (b"\xd4\xc3\xb2\xa1", b"M<\xb2\xa1"):
        endian = "<"
    elif magic in (b"\xa1\xb2\xc3\xd4", b"\xa1\xb2<M"):
        endian = ">"
    else:
        return None, [f"unsupported pcap magic: {magic.hex()}"]

    errors: list[str] = []
    hashes: list[str] = []
    offset = 24
    packet_index = 0
    while offset < len(data):
        if offset + 16 > len(data):
            return None, [f"truncated pcap packet header at offset {offset}"]
        _ts_sec, _ts_usec, included_len, _original_len = struct.unpack(
            f"{endian}IIII",
            data[offset : offset + 16],
        )
        offset += 16
        if offset + included_len > len(data):
            return None, [f"truncated pcap packet body at packet {packet_index}"]
        raw = data[offset : offset + included_len]
        offset += included_len

        if len(raw) < 28:
            errors.append(f"packet {packet_index} is too short for raw IPv4 UDP")
            packet_index += 1
            continue
        version = raw[0] >> 4
        ihl = (raw[0] & 0x0F) * 4
        if version != 4:
            errors.append(f"packet {packet_index} is not IPv4")
            packet_index += 1
            continue
        if ihl < 20 or len(raw) < ihl + 8:
            errors.append(f"packet {packet_index} has invalid IPv4 header length")
            packet_index += 1
            continue
        if raw[9] != 17:
            errors.append(f"packet {packet_index} is not UDP")
            packet_index += 1
            continue
        total_length = struct.unpack("!H", raw[2:4])[0]
        if total_length < ihl + 8 or total_length > len(raw):
            errors.append(f"packet {packet_index} has invalid IPv4 total length")
            packet_index += 1
            continue
        udp_start = ihl
        udp_length = struct.unpack("!H", raw[udp_start + 4 : udp_start + 6])[0]
        if udp_length < 8 or udp_start + udp_length > total_length:
            errors.append(f"packet {packet_index} has invalid UDP length")
            packet_index += 1
            continue
        payload = raw[udp_start + 8 : udp_start + udp_length]
        hashes.append(hashlib.sha256(payload).hexdigest())
        packet_index += 1
    return (None, errors) if errors else (hashes, [])


def jsonl_record_count(path: Path) -> tuple[int | None, list[str]]:
    errors: list[str] = []
    count = 0
    with path.open("r", encoding="utf-8") as f:
        for index, line in enumerate(f, start=1):
            if not line.strip():
                errors.append(f"jsonl line {index} is empty")
                continue
            try:
                json.loads(line)
            except Exception as exc:
                errors.append(f"jsonl line {index} is invalid JSON: {exc}")
                continue
            count += 1
    return (None, errors) if errors else (count, [])


def jsonl_payload_sha256s(path: Path) -> tuple[list[str] | None, list[str]]:
    errors: list[str] = []
    hashes: list[str] = []
    with path.open("r", encoding="utf-8") as f:
        for index, line in enumerate(f, start=1):
            if not line.strip():
                errors.append(f"jsonl line {index} is empty")
                continue
            try:
                event = json.loads(line)
            except Exception as exc:
                errors.append(f"jsonl line {index} is invalid JSON: {exc}")
                continue
            payload_sha = event.get("payload_sha256")
            if not is_sha256(payload_sha):
                errors.append(f"jsonl line {index} payload_sha256 must be sha256")
                continue
            hashes.append(payload_sha)
    return (None, errors) if errors else (hashes, [])


def validate_pcap_packet_count_measurements(
    root: Path,
    artifacts: Any,
    measurements: dict[str, Any],
    links: dict[str, str],
) -> list[str]:
    errors: list[str] = []
    for role, measurement_key in links.items():
        path, path_errors = artifact_path_for_role(root, artifacts, role)
        errors.extend(path_errors)
        if path_errors or not path:
            continue
        count, count_errors = pcap_packet_count(path)
        errors.extend(f"artifact role {role} pcap: {error}" for error in count_errors)
        if count is not None and measurements.get(measurement_key) != count:
            errors.append(f"measurements.{measurement_key} must match artifact role {role} pcap packet count")
    return errors


def validate_jsonl_record_count_measurements(
    root: Path,
    artifacts: Any,
    measurements: dict[str, Any],
    links: dict[str, str],
) -> list[str]:
    errors: list[str] = []
    for role, measurement_key in links.items():
        path, path_errors = artifact_path_for_role(root, artifacts, role)
        errors.extend(path_errors)
        if path_errors or not path:
            continue
        count, count_errors = jsonl_record_count(path)
        errors.extend(f"artifact role {role} jsonl: {error}" for error in count_errors)
        if count is not None and measurements.get(measurement_key) != count:
            errors.append(f"measurements.{measurement_key} must match artifact role {role} jsonl record count")
    return errors


def validate_pcap_payload_sha256_jsonl_roles(
    root: Path,
    artifacts: Any,
    links: dict[str, str],
) -> list[str]:
    errors: list[str] = []
    for pcap_role, jsonl_role in links.items():
        pcap_path, pcap_path_errors = artifact_path_for_role(root, artifacts, pcap_role)
        jsonl_path, jsonl_path_errors = artifact_path_for_role(root, artifacts, jsonl_role)
        errors.extend(pcap_path_errors)
        errors.extend(jsonl_path_errors)
        if pcap_path_errors or jsonl_path_errors or not pcap_path or not jsonl_path:
            continue
        pcap_hashes, pcap_errors = pcap_udp_payload_sha256s(pcap_path)
        jsonl_hashes, jsonl_errors = jsonl_payload_sha256s(jsonl_path)
        errors.extend(f"artifact role {pcap_role} pcap: {error}" for error in pcap_errors)
        errors.extend(f"artifact role {jsonl_role} jsonl: {error}" for error in jsonl_errors)
        if pcap_hashes is not None and jsonl_hashes is not None and pcap_hashes != jsonl_hashes:
            errors.append(
                f"artifact role {jsonl_role} payload_sha256 sequence must match "
                f"pcap role {pcap_role} UDP payloads"
            )
    return errors


def validate_paired_jsonl_payload_sha256_roles(
    root: Path,
    artifacts: Any,
    role_pairs: list[list[str]],
) -> list[str]:
    errors: list[str] = []
    for roles in role_pairs:
        if not isinstance(roles, list) or len(roles) < 2:
            errors.append("paired jsonl payload sha256 roles must include at least two roles")
            continue
        sequences: list[tuple[str, list[str]]] = []
        for role in roles:
            if not isinstance(role, str):
                errors.append("paired jsonl payload sha256 role must be a string")
                continue
            path, path_errors = artifact_path_for_role(root, artifacts, role)
            errors.extend(path_errors)
            if path_errors or not path:
                continue
            hashes, hash_errors = jsonl_payload_sha256s(path)
            errors.extend(f"artifact role {role} jsonl: {error}" for error in hash_errors)
            if hashes is not None:
                sequences.append((role, hashes))
        if len(sequences) == len(roles):
            first_role, first_hashes = sequences[0]
            for role, hashes in sequences[1:]:
                if hashes != first_hashes:
                    errors.append(
                        f"artifact role {role} payload_sha256 sequence must match artifact role {first_role}"
                    )
    return errors


def validate_paired_jsonl_gap_count_measurements(
    root: Path,
    artifacts: Any,
    measurements: dict[str, Any],
    links: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    for link in links:
        roles = link.get("roles")
        measurement_key = link.get("measurement")
        if not isinstance(roles, list) or not roles or not isinstance(measurement_key, str):
            errors.append("paired jsonl gap count link must include roles and measurement")
            continue
        gap_counts: list[int] = []
        for role in roles:
            if not isinstance(role, str):
                errors.append("paired jsonl gap count role must be a string")
                continue
            path, path_errors = artifact_path_for_role(root, artifacts, role)
            errors.extend(path_errors)
            if path_errors or not path:
                continue
            count, count_errors = jsonl_record_count(path)
            errors.extend(f"artifact role {role} jsonl: {error}" for error in count_errors)
            if count is not None:
                gap_counts.append(max(0, count - 1))
        if len(gap_counts) == len(roles):
            expected = min(gap_counts)
            if measurements.get(measurement_key) != expected:
                errors.append(
                    f"measurements.{measurement_key} must match paired jsonl gap count for roles "
                    f"{', '.join(roles)}"
                )
    return errors


def validate_required_references(root: Path, references: Any, claim_ids: list[str]) -> list[str]:
    if not isinstance(references, list) or not references:
        return ["references must be a non-empty list"]

    errors: list[str] = []
    refs_by_claim: dict[str, dict[str, Any]] = {}
    seen: set[str] = set()
    for index, reference in enumerate(references):
        if not isinstance(reference, dict):
            errors.append(f"references[{index}] must be an object")
            continue
        claim_id = reference.get("claim_id")
        if not isinstance(claim_id, str) or not claim_id:
            errors.append(f"references[{index}].claim_id is required")
            continue
        if claim_id in seen:
            errors.append(f"references duplicate claim: {claim_id}")
            continue
        seen.add(claim_id)
        refs_by_claim[claim_id] = reference

    requirements = requirement_by_claim()
    for claim_id in claim_ids:
        reference = refs_by_claim.get(claim_id)
        if not reference:
            errors.append(f"references missing claim: {claim_id}")
            continue
        requirement = requirements.get(claim_id)
        if not requirement:
            errors.append(f"references.{claim_id} is not a known external requirement")
            continue
        validation = validate_external_evidence(root, requirement)
        for key in ("status", "evidence", "sha256"):
            if reference.get(key) != validation.get(key):
                errors.append(f"references.{claim_id}.{key} does not match current evidence validation")
        if validation.get("status") != "VERIFIED":
            errors.append(f"references.{claim_id}.status must be VERIFIED before production readiness")

    unexpected = sorted(set(refs_by_claim) - set(claim_ids))
    for claim_id in unexpected:
        errors.append(f"references unexpected claim: {claim_id}")
    return errors


def validate_not_gap_record(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("mode") == "EXTERNAL_EVIDENCE_GAP_RECORD":
        errors.append("mode must not be EXTERNAL_EVIDENCE_GAP_RECORD")
    if payload.get("mode") == INCOMING_EXAMPLE_MODE:
        errors.append(f"mode must not be {INCOMING_EXAMPLE_MODE}")
    if payload.get("missing_inputs"):
        errors.append("missing_inputs must be absent or empty for VERIFIED evidence")
    if payload.get("failures"):
        errors.append("failures must be absent or empty for VERIFIED evidence")
    claim_boundary = payload.get("claim_boundary")
    if isinstance(claim_boundary, dict) and claim_boundary.get("claim_verified") is False:
        errors.append("claim_boundary.claim_verified must not be false for VERIFIED evidence")
    return errors


def placeholder_marker_errors(value: Any, path: str = "payload") -> list[str]:
    errors: list[str] = []
    if isinstance(value, str):
        for marker in PLACEHOLDER_MARKERS:
            if marker in value:
                errors.append(f"{path} contains placeholder marker: {marker}")
                break
        return errors
    if isinstance(value, dict):
        for key, child in value.items():
            errors.extend(placeholder_marker_errors(child, f"{path}.{key}"))
        return errors
    if isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(placeholder_marker_errors(child, f"{path}[{index}]"))
    return errors


def artifact_file_placeholder_marker_errors(path: Path, index: int) -> list[str]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        return [f"artifacts[{index}] file could not be scanned for placeholder markers: {exc}"]
    for marker in PLACEHOLDER_MARKERS:
        if marker.encode("utf-8") in data:
            return [f"artifacts[{index}] file contains placeholder marker: {marker}"]
    return []


def validate_observed_at_utc(value: Any) -> list[str]:
    if not isinstance(value, str) or not value:
        return ["observed_at_utc is required"]
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return ["observed_at_utc must be an ISO-8601 timestamp"]
    if parsed.tzinfo is None:
        return ["observed_at_utc must include a UTC timezone"]
    offset = parsed.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        return ["observed_at_utc must be UTC"]
    return []


def validate_external_evidence(root: Path, requirement: dict[str, Any]) -> dict[str, Any]:
    rel_path = requirement["path"]
    evidence_path = resolve_path(root, rel_path)
    errors: list[str] = []
    payload: dict[str, Any] = {}

    if not evidence_path or not evidence_path.exists():
        return {
            "claim_id": requirement["claim_id"],
            "title": requirement["title"],
            "status": "MISSING",
            "evidence": rel_path,
            "errors": [f"missing evidence file: {rel_path}"],
            "sha256": None,
        }

    try:
        payload = load_json(evidence_path)
    except Exception as exc:
        return {
            "claim_id": requirement["claim_id"],
            "title": requirement["title"],
            "status": "INVALID",
            "evidence": display_path(root, evidence_path),
            "errors": [f"could not load evidence JSON: {exc}"],
            "sha256": sha256_file(evidence_path),
        }

    if payload.get("schema") != EVIDENCE_SCHEMA:
        errors.append(f"schema must be {EVIDENCE_SCHEMA}")
    if payload.get("claim_id") != requirement["claim_id"]:
        errors.append(f"claim_id must be {requirement['claim_id']}")
    if payload.get("status") != "VERIFIED":
        errors.append("status must be VERIFIED")
    for flag in ("simulated", "dry_run", "template"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    errors.extend(validate_not_gap_record(payload))
    errors.extend(placeholder_marker_errors(payload))
    errors.extend(validate_observed_at_utc(payload.get("observed_at_utc")))

    commands = payload.get("commands")
    if not isinstance(commands, list) or not commands:
        errors.append("commands must be a non-empty list")
    else:
        for index, command in enumerate(commands):
            if not isinstance(command, dict):
                errors.append(f"commands[{index}] must be an object")
                continue
            if not isinstance(command.get("args"), list) or not command["args"]:
                errors.append(f"commands[{index}].args must be a non-empty list")
            else:
                for arg_index, arg in enumerate(command["args"]):
                    if not isinstance(arg, str) or not arg:
                        errors.append(f"commands[{index}].args[{arg_index}] must be a non-empty string")
            exit_code = command.get("exit_code")
            if not isinstance(exit_code, int) or isinstance(exit_code, bool) or exit_code != 0:
                errors.append(f"commands[{index}].exit_code must be integer 0")

    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("artifacts must be a non-empty list")
    else:
        for index, artifact in enumerate(artifacts):
            if not isinstance(artifact, dict):
                errors.append(f"artifacts[{index}] must be an object")
                continue
            artifact_path = artifact.get("path")
            artifact_sha = artifact.get("sha256")
            if not isinstance(artifact_path, str) or not artifact_path:
                errors.append(f"artifacts[{index}].path is required")
                continue
            path_errors = artifact_path_errors(root, artifact_path)
            errors.extend(path_errors)
            if path_errors:
                continue
            resolved = resolve_path(root, artifact_path)
            if not resolved or not resolved.exists():
                errors.append(f"artifacts[{index}] file is missing: {artifact_path}")
                continue
            if not resolved.is_file():
                errors.append(f"artifacts[{index}] path is not a regular file: {artifact_path}")
                continue
            if artifact_sha != sha256_file(resolved):
                errors.append(f"artifacts[{index}].sha256 mismatch: {artifact_path}")
            errors.extend(artifact_file_placeholder_marker_errors(resolved, index))
    if "required_artifact_roles" in requirement:
        errors.extend(validate_required_artifact_roles(root, artifacts, requirement["required_artifact_roles"]))

    measurements = payload.get("measurements", {})
    if not isinstance(measurements, dict):
        errors.append("measurements must be an object")
        measurements = {}
    for key, expectation in requirement["measurements"].items():
        if not measurement_matches(measurements.get(key), expectation):
            errors.append(f"measurements.{key} must be {expectation}")
    if "artifact_sha256_measurements" in requirement:
        errors.extend(
            validate_artifact_sha256_measurements(
                artifacts,
                measurements,
                requirement["artifact_sha256_measurements"],
            )
        )
    if "pcap_packet_count_measurements" in requirement:
        errors.extend(
            validate_pcap_packet_count_measurements(
                root,
                artifacts,
                measurements,
                requirement["pcap_packet_count_measurements"],
            )
        )
    if "jsonl_record_count_measurements" in requirement:
        errors.extend(
            validate_jsonl_record_count_measurements(
                root,
                artifacts,
                measurements,
                requirement["jsonl_record_count_measurements"],
            )
        )
    if "json_artifact_payload_links" in requirement:
        errors.extend(
            validate_json_artifact_payload_links(
                root,
                artifacts,
                payload,
                requirement["json_artifact_payload_links"],
            )
        )
    if "json_artifact_object_field_links" in requirement:
        errors.extend(
            validate_json_artifact_object_field_links(
                root,
                artifacts,
                payload,
                requirement["json_artifact_object_field_links"],
            )
        )
    if "pcap_payload_sha256_jsonl_roles" in requirement:
        errors.extend(
            validate_pcap_payload_sha256_jsonl_roles(
                root,
                artifacts,
                requirement["pcap_payload_sha256_jsonl_roles"],
            )
        )
    if "paired_jsonl_payload_sha256_roles" in requirement:
        errors.extend(
            validate_paired_jsonl_payload_sha256_roles(
                root,
                artifacts,
                requirement["paired_jsonl_payload_sha256_roles"],
            )
        )
    if "paired_jsonl_gap_count_measurements" in requirement:
        errors.extend(
            validate_paired_jsonl_gap_count_measurements(
                root,
                artifacts,
                measurements,
                requirement["paired_jsonl_gap_count_measurements"],
            )
        )
    if isinstance(commands, list) and "required_commands" in requirement:
        for expected in missing_required_commands(commands, requirement["required_commands"], measurements):
            errors.append(f"required command not observed: {' '.join(expected)}")
    if "required_references" in requirement:
        errors.extend(validate_required_references(root, payload.get("references"), requirement["required_references"]))

    return {
        "claim_id": requirement["claim_id"],
        "title": requirement["title"],
        "status": "VERIFIED" if not errors else "INVALID",
        "evidence": display_path(root, evidence_path),
        "errors": errors,
        "sha256": sha256_file(evidence_path),
    }


SuiteFailureProvider = Callable[[Path, Path], list[str]]
ArtifactChainProvider = Callable[[Path, Path], dict[str, Any]]
ReplacementCandidateProvider = Callable[[Path, Path], dict[str, Any]]
CurrentRuntimeProvider = Callable[[Path, str | None, bool, float], dict[str, Any]]


def current_runtime_invalid_row(error: str, interface: str | None = None) -> dict[str, Any]:
    evidence_suffix = interface.strip() if isinstance(interface, str) and interface.strip() else "unconfigured"
    return {
        "claim_id": CURRENT_RUNTIME_CLAIM_ID,
        "title": CURRENT_RUNTIME_TITLE,
        "status": "INVALID",
        "evidence": f"READ_ONLY_KERNEL_OBSERVATION:{evidence_suffix}",
        "errors": [error],
        "sha256": None,
    }


def default_current_runtime_provider(
    root: Path,
    interface: str | None,
    bpftool_sudo: bool,
    counter_wait_seconds: float,
) -> dict[str, Any]:
    iface = (interface or "").strip()
    if not iface:
        return current_runtime_invalid_row(
            f"current runtime interface not configured; set {RUNTIME_INTERFACE_ENV} or pass --runtime-interface",
            interface,
        )
    try:
        collector = load_module(
            "collect_ghost_pulse_kernel_attach_evidence_for_proof_gate",
            root / "scripts" / "ops" / "collect_ghost_pulse_kernel_attach_evidence.py",
        )
        runtime_report = collector.build_report(
            root=root,
            iface=iface,
            counter_wait_seconds=counter_wait_seconds,
            bpftool_sudo=bpftool_sudo,
        )
    except Exception as exc:
        return current_runtime_invalid_row(f"current runtime observation failed: {exc}", iface)
    diagnostics = runtime_report.get("collection_diagnostics", {})
    blockers = diagnostics.get("blockers", []) if isinstance(diagnostics, dict) else []
    errors = list(runtime_report.get("failures") or [])
    if blockers:
        errors.extend(f"runtime diagnostic blocker: {blocker}" for blocker in blockers)
    verified = runtime_report.get("status") == "VERIFIED" and not errors
    return {
        "claim_id": CURRENT_RUNTIME_CLAIM_ID,
        "title": CURRENT_RUNTIME_TITLE,
        "status": "VERIFIED" if verified else "INVALID",
        "evidence": f"READ_ONLY_KERNEL_OBSERVATION:{iface}",
        "errors": [] if verified else errors or ["current runtime observation is not VERIFIED"],
        "sha256": None,
    }


def local_rows(
    root: Path,
    suite_path: Path,
    suite: dict[str, Any],
    suite_failures: list[str],
    artifact_chain: dict[str, Any],
) -> list[dict[str, Any]]:
    summary = suite.get("summary", {})
    matrix_summary = summary.get("matrix", {})
    local_summary = summary.get("local", {})
    suite_ok = not suite_failures and suite.get("decision") == "GHOST_PULSE_VERIFICATION_SUITE_VERIFIED_STEALTH_NOT_VERIFIED"
    replay_ok = (
        suite_ok
        and local_summary.get("replay_status") == "LOCAL_SEED_REPLAYABLE"
        and matrix_summary.get("run_count") == matrix_summary.get("replayable_run_count")
    )
    false_scan_ok = suite_ok and suite.get("gates", {}).get("false_claim_scan", {}).get("status") == "PASS"
    artifact_gate_ok = suite_ok and suite.get("gates", {}).get("artifact_integrity", {}).get("status") == "PASS"
    chain_ok = artifact_chain.get("decision") == "GHOST_PULSE_ARTIFACT_CHAIN_VERIFIED"
    return [
        {
            "claim_id": "local_timing_replay",
            "title": "Seeded local timing plan replay",
            "status": "VERIFIED" if replay_ok else "INVALID",
            "evidence": display_path(root, suite_path),
            "errors": [] if replay_ok else ["local or matrix replay evidence is not fully replayable"],
            "sha256": sha256_file(suite_path),
        },
        {
            "claim_id": "false_claim_hygiene",
            "title": "False-claim hygiene scan",
            "status": "VERIFIED" if false_scan_ok else "INVALID",
            "evidence": display_path(root, suite_path),
            "errors": [] if false_scan_ok else ["false_claim_scan is not PASS"],
            "sha256": sha256_file(suite_path),
        },
        {
            "claim_id": "artifact_chain",
            "title": "Latest artifact chain integrity",
            "status": "VERIFIED" if artifact_gate_ok and chain_ok else "INVALID",
            "evidence": display_path(root, suite_path),
            "errors": [] if artifact_gate_ok and chain_ok else ["artifact_integrity or artifact-chain verification is not PASS"],
            "sha256": sha256_file(suite_path),
        },
    ]


def build_report(
    *,
    root: Path = ROOT,
    suite_path: Path | None = None,
    replacement_candidates_path: Path | None = None,
    runtime_interface: str | None = None,
    bpftool_sudo: bool = False,
    runtime_counter_wait_seconds: float = 0.2,
    suite_failure_provider: SuiteFailureProvider = default_suite_failures,
    artifact_chain_provider: ArtifactChainProvider = default_artifact_chain_report,
    replacement_candidate_provider: ReplacementCandidateProvider = default_replacement_candidate_preflight,
    current_runtime_provider: CurrentRuntimeProvider = default_current_runtime_provider,
) -> dict[str, Any]:
    suite_path = suite_path or DEFAULT_SUITE
    suite_path = suite_path if suite_path.is_absolute() else root / suite_path
    replacement_candidates_path = replacement_candidates_path or DEFAULT_REPLACEMENT_CANDIDATES
    replacement_candidates_path = (
        replacement_candidates_path
        if replacement_candidates_path.is_absolute()
        else root / replacement_candidates_path
    )
    failures: list[str] = []

    if not suite_path.exists():
        suite: dict[str, Any] = {}
        suite_failures = [f"missing suite: {display_path(root, suite_path)}"]
        artifact_chain = {"decision": "GHOST_PULSE_ARTIFACT_CHAIN_INCOMPLETE"}
    else:
        suite = load_json(suite_path)
        suite_failures = suite_failure_provider(root, suite_path)
        artifact_chain = artifact_chain_provider(root, suite_path)

    rows = local_rows(root, suite_path, suite, suite_failures, artifact_chain)
    rows.extend(validate_external_evidence(root, requirement) for requirement in EXTERNAL_REQUIREMENTS)
    runtime_interface = runtime_interface or os.getenv(RUNTIME_INTERFACE_ENV)
    rows.append(current_runtime_provider(root, runtime_interface, bpftool_sudo, runtime_counter_wait_seconds))
    replacement_candidates = replacement_candidate_provider(root, replacement_candidates_path)

    for failure in suite_failures:
        failures.append(f"suite verifier: {failure}")
    for row in rows:
        if row["status"] != "VERIFIED":
            failures.extend(f"{row['claim_id']}: {error}" for error in row["errors"])
    if replacement_candidates.get("status") != "PASS":
        replacement_failures = replacement_candidates.get("failures", [])
        if replacement_failures:
            failures.extend(f"replacement_candidates: {failure}" for failure in replacement_failures)
        else:
            failures.append("replacement_candidates: verifier status is not PASS")

    status_by_claim = {row["claim_id"]: row["status"] for row in rows}
    external_ready = all(status_by_claim[item["claim_id"]] == "VERIFIED" for item in EXTERNAL_REQUIREMENTS)
    all_verified = all(row["status"] == "VERIFIED" for row in rows)
    replacement_candidates_ok = replacement_candidates.get("status") == "PASS"
    current_runtime_verified = status_by_claim.get(CURRENT_RUNTIME_CLAIM_ID) == "VERIFIED"
    production_ready = (
        all_verified
        and external_ready
        and replacement_candidates_ok
        and current_runtime_verified
        and status_by_claim.get("production_readiness") == "VERIFIED"
    )
    claim_boundary = {
        "stealth_verified": (
            status_by_claim.get("dpi_lab") == "VERIFIED"
            and status_by_claim.get("packet_capture") == "VERIFIED"
            and status_by_claim.get("baseline_timing_comparison") == "VERIFIED"
        ),
        "whitelist_verified": status_by_claim.get("whitelist_lab") == "VERIFIED",
        "kernel_attach_verified": status_by_claim.get("kernel_attach") == "VERIFIED",
        "current_runtime_attached": current_runtime_verified,
        "production_ready": production_ready,
    }
    decision = DECISION_PROVEN if production_ready else DECISION_INCOMPLETE

    return {
        "schema": SCHEMA,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "suite": display_path(root, suite_path),
        "suite_sha256": sha256_file(suite_path),
        "replacement_candidates": replacement_candidates,
        "proof_rows": rows,
        "failures": failures,
        "not_verified_yet": [row["claim_id"] for row in rows if row["status"] != "VERIFIED"],
        "required_external_evidence": [external_requirement_contract(item) for item in EXTERNAL_REQUIREMENTS],
        "claim_boundary": claim_boundary,
        "claim_boundary_note": (
            "Only the local timing replay, false-claim hygiene, and artifact chain can be proven "
            "from current repo-local evidence. DPI, whitelist, kernel attach, and production "
            "claims require the external evidence files listed in required_external_evidence. "
            "Historical kernel_attach evidence does not prove that the current runtime is attached; "
            "current_runtime_attached is verified only by a fresh read-only kernel observation. "
            "Replacement-candidate preflight is supporting evidence only and never promotes claims."
        ),
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# x0tta6bl4_pulse Proof Gate",
        "",
        f"Timestamp: `{report['timestamp_utc']}`",
        "",
        f"Decision: `{report['decision']}`",
        "",
        "## Claim Boundary",
        "",
    ]
    for key in sorted(report["claim_boundary"]):
        value = report["claim_boundary"][key]
        lines.append(f"- {key}: `{value}`")
    replacement_candidates = report.get("replacement_candidates", {})
    lines.extend(["", "## Replacement Candidate Preflight", ""])
    if isinstance(replacement_candidates, dict):
        lines.append(f"- report: `{replacement_candidates.get('report')}`")
        lines.append(f"- sha256: `{replacement_candidates.get('sha256')}`")
        lines.append(f"- status: `{replacement_candidates.get('status')}`")
        lines.append(f"- decision: `{replacement_candidates.get('decision')}`")
        lines.append(
            f"- not_ready: `{', '.join(replacement_candidates.get('not_ready', [])) or 'none'}`"
        )
    else:
        lines.append("- INVALID")
    lines.extend(["", "## Proof Rows", "", "| Claim | Status | Evidence |", "| --- | --- | --- |"])
    for row in report["proof_rows"]:
        lines.append(f"| {row['claim_id']} | `{row['status']}` | `{row['evidence']}` |")
    lines.extend(["", "## Missing Or Invalid Evidence", ""])
    if report["not_verified_yet"]:
        lines.extend(f"- {claim_id}" for claim_id in report["not_verified_yet"])
    else:
        lines.append("- None")
    lines.extend(["", "## Failures", ""])
    if report["failures"]:
        lines.extend(f"- {failure}" for failure in report["failures"])
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def stamp_from_timestamp(timestamp: str) -> str:
    parsed = datetime.fromisoformat(timestamp)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_report_outputs(root: Path, report: dict[str, Any], output_json: Path, output_md: Path) -> dict[str, Path]:
    stamp = stamp_from_timestamp(report["timestamp_utc"])
    bundle_dir = root / "docs" / "verification" / f"ghost-pulse-proof-gate-{stamp}"
    bundle_json = bundle_dir / "proof.json"
    bundle_md = bundle_dir / "summary.md"

    report["bundle"] = display_path(root, bundle_dir)
    report.setdefault("artifacts", {}).update(
        {
            "proof_bundle_json": display_path(root, bundle_json),
            "proof_bundle_md": display_path(root, bundle_md),
            "proof_latest_json": display_path(root, output_json),
            "proof_latest_md": display_path(root, output_md),
        }
    )

    rendered_json = json.dumps(report, indent=2, sort_keys=True)
    rendered_md = render_markdown(report)
    bundle_dir.mkdir(parents=True, exist_ok=True)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(bundle_json, rendered_json)
    atomic_write_text(bundle_md, rendered_md)
    atomic_write_text(output_json, rendered_json)
    atomic_write_text(output_md, rendered_md)
    return {
        "bundle_dir": bundle_dir,
        "bundle_json": bundle_json,
        "bundle_md": bundle_md,
        "latest_json": output_json,
        "latest_md": output_md,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    parser.add_argument("--replacement-candidates", type=Path, default=DEFAULT_REPLACEMENT_CANDIDATES)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--runtime-interface", default=os.getenv(RUNTIME_INTERFACE_ENV))
    parser.add_argument("--bpftool-sudo", action="store_true")
    parser.add_argument("--runtime-counter-wait-seconds", type=float, default=0.2)
    parser.add_argument("--json", action="store_true", help="Print the full JSON report.")
    parser.add_argument("--require-all-proven", action="store_true")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    suite_path = args.suite if args.suite.is_absolute() else root / args.suite
    replacement_candidates_path = (
        args.replacement_candidates
        if args.replacement_candidates.is_absolute()
        else root / args.replacement_candidates
    )
    report = build_report(
        root=root,
        suite_path=suite_path,
        replacement_candidates_path=replacement_candidates_path,
        runtime_interface=args.runtime_interface,
        bpftool_sudo=args.bpftool_sudo,
        runtime_counter_wait_seconds=args.runtime_counter_wait_seconds,
    )
    output_json = args.output_json if args.output_json.is_absolute() else root / args.output_json
    output_md = args.output_md if args.output_md.is_absolute() else root / args.output_md
    output_paths = write_report_outputs(root, report, output_json, output_md)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            json.dumps(
                {
                    "decision": report["decision"],
                    "bundle": display_path(root, output_paths["bundle_dir"]),
                    "output_json": display_path(root, output_paths["latest_json"]),
                    "output_md": display_path(root, output_paths["latest_md"]),
                    "not_verified_yet": report["not_verified_yet"],
                },
                indent=2,
                sort_keys=True,
            )
        )

    if args.require_all_proven and report["decision"] != DECISION_PROVEN:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
