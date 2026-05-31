#!/usr/bin/env python3
"""Collect bounded external DPI/proxy reachability evidence.

This collector is intentionally conservative. It only promotes a candidate to
VERIFIED when an operator explicitly authorizes the run, the control path is
blocked or detected, and the treatment path is reachable. Raw URLs, proxy
endpoints, headers, payloads, subscriber data, and response bodies are never
written to the artifact; only hashes and coarse buckets are retained.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Sequence


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = Path("docs/verification/incoming/dpi_lab.json")
DEFAULT_ARTIFACT_DIR = Path("docs/verification/incoming/artifacts/external-dpi-proxy")
GHOST_PULSE_CLAIM_SCHEMA = "x0tta6bl4.ghost_pulse.claim_evidence.v1"
EVIDENCE_SCHEMA_VERSION = "x0tta6bl4.external_dpi_proxy_reachability_evidence.v1"
COLLECTOR_OPERATOR_HANDOFF_SCHEMA = "x0tta6bl4.external_dpi_proxy.collector_operator_handoff.v1"
GHOST_PULSE_DPI_ARTIFACT_ROLES = (
    "lab_scope",
    "baseline_result",
    "pulse_result",
    "lab_conclusion",
)
BLOCKED_BUCKETS = {
    "dns_failed",
    "tcp_failed",
    "tls_failed",
    "http_blocked",
    "http_403",
    "http_451",
    "timeout",
    "reset",
    "throttled",
}
REACHABLE_BUCKETS = {"http_2xx", "http_3xx"}


@dataclass(frozen=True)
class ProbeResult:
    path_kind: str
    attempt_index: int
    returncode: int
    http_code: int | None
    total_time_s: float | None
    size_download: int | None
    bucket: str
    stderr_bucket: str


Runner = Callable[[Sequence[str], int], subprocess.CompletedProcess[str]]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_text(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_payload(payload: object) -> str:
    return sha256_text(canonical_json(payload))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_content_sha256(payload: object) -> str:
    normalized = json.loads(canonical_json(payload))
    if isinstance(normalized, dict) and isinstance(normalized.get("artifact_identity"), dict):
        normalized["artifact_identity"]["artifact_sha256"] = "0" * 64
    return sha256_payload(normalized)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--target-url", required=True, help="Probe target URL; stored only as sha256")
    parser.add_argument("--treatment-url", help="Optional treatment URL; defaults to --target-url")
    parser.add_argument("--treatment-proxy", help="Optional curl proxy URL; stored only as presence+hash")
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--timeout-s", type=int, default=10)
    parser.add_argument("--transport", default="https")
    parser.add_argument("--proxy-or-fronting-mode", default="proxy")
    parser.add_argument("--target-category", default="controlled-endpoint")
    parser.add_argument("--collector-kind", default="authorized_lab")
    parser.add_argument("--operator-or-lab-id", required=True, help="Raw value is hashed and not stored")
    parser.add_argument("--authorization-scope-id", required=True, help="Raw value is hashed and not stored")
    parser.add_argument("--scope-summary", required=True)
    parser.add_argument("--network-region-bucket", required=True)
    parser.add_argument("--network-type", required=True)
    parser.add_argument("--isp-or-lab-profile", required=True, help="Raw value is hashed and not stored")
    parser.add_argument("--egress-location-bucket", required=True)
    parser.add_argument("--policy-context", required=True)
    parser.add_argument("--clock-sync-status", default="operator-confirmed")
    parser.add_argument("--redaction-tool-version", default="1.0")
    parser.add_argument(
        "--allow-external-probes",
        action="store_true",
        help="Required. Confirms the operator is authorized to run the external probes.",
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def resolve_path(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def relative_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def default_runner(args: Sequence[str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def parse_curl_metrics(raw: str) -> tuple[int | None, float | None, int | None]:
    parts = (raw or "").strip().split()
    if len(parts) != 3:
        return None, None, None
    http_code: int | None
    total_time_s: float | None
    size_download: int | None
    try:
        http_code = int(parts[0])
    except ValueError:
        http_code = None
    try:
        total_time_s = float(parts[1])
    except ValueError:
        total_time_s = None
    try:
        size_download = int(parts[2])
    except ValueError:
        size_download = None
    return http_code, total_time_s, size_download


def classify_result(returncode: int, http_code: int | None, stderr: str) -> tuple[str, str]:
    stderr_lower = (stderr or "").lower()
    if returncode == 124 or "timed out" in stderr_lower or "timeout" in stderr_lower:
        return "timeout", "timeout"
    if "connection reset" in stderr_lower:
        return "reset", "connection_reset"
    if "could not resolve" in stderr_lower or "resolve" in stderr_lower:
        return "dns_failed", "dns_failed"
    if "ssl" in stderr_lower or "tls" in stderr_lower or "certificate" in stderr_lower:
        return "tls_failed", "tls_failed"
    if http_code == 451:
        return "http_451", "none"
    if http_code == 403:
        return "http_403", "none"
    if http_code and 200 <= http_code < 300:
        return "http_2xx", "none"
    if http_code and 300 <= http_code < 400:
        return "http_3xx", "none"
    if http_code and http_code >= 400:
        return "http_blocked", "none"
    if returncode != 0:
        return "tcp_failed", "curl_failed"
    return "unknown", "none"


def run_probe(
    *,
    path_kind: str,
    url: str,
    proxy: str | None,
    attempt_index: int,
    timeout_s: int,
    runner: Runner,
) -> ProbeResult:
    command = [
        "curl",
        "-kS",
        "--max-time",
        str(timeout_s),
        "--connect-timeout",
        str(timeout_s),
        "-o",
        "/dev/null",
        "-w",
        "%{http_code} %{time_total} %{size_download}",
    ]
    if proxy:
        command.extend(["--proxy", proxy])
    command.append(url)
    try:
        completed = runner(command, timeout_s + 5)
        returncode = completed.returncode
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
    except subprocess.TimeoutExpired as exc:
        returncode = 124
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else "timeout"

    http_code, total_time_s, size_download = parse_curl_metrics(stdout)
    bucket, stderr_bucket = classify_result(returncode, http_code, stderr)
    return ProbeResult(
        path_kind=path_kind,
        attempt_index=attempt_index,
        returncode=returncode,
        http_code=http_code,
        total_time_s=total_time_s,
        size_download=size_download,
        bucket=bucket,
        stderr_bucket=stderr_bucket,
    )


def bucket_counts(results: list[ProbeResult]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.bucket] = counts.get(result.bucket, 0) + 1
    return counts


def bucket_http_status(results: list[ProbeResult]) -> str:
    codes = [item.http_code for item in results if item.http_code]
    if not codes:
        return "none"
    if any(200 <= code < 300 for code in codes):
        return "2xx"
    if any(300 <= code < 400 for code in codes):
        return "3xx"
    if any(code == 451 for code in codes):
        return "451"
    if any(code == 403 for code in codes):
        return "403"
    if any(code >= 400 for code in codes):
        return "4xx_or_5xx"
    return "other"


def bucket_duration_ms(results: list[ProbeResult]) -> str:
    values = [item.total_time_s for item in results if item.total_time_s is not None]
    if not values:
        return "unknown"
    max_ms = max(values) * 1000
    if max_ms < 250:
        return "0-250"
    if max_ms < 1000:
        return "250-1000"
    if max_ms < 5000:
        return "1000-5000"
    return "5000+"


def bucket_bytes(results: list[ProbeResult]) -> str:
    total = sum(item.size_download or 0 for item in results)
    if total == 0:
        return "0"
    if total < 1024:
        return "1-1k"
    if total < 10 * 1024:
        return "1k-10k"
    if total < 100 * 1024:
        return "10k-100k"
    return "100k+"

def write_json_artifact(root: Path, path: Path, payload: object) -> dict[str, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "path": relative_path(root, path),
        "sha256": sha256_file(path),
    }


def validator_command(candidate: str) -> list[str]:
    return [
        "python3",
        "scripts/ops/verify_external_dpi_proxy_reachability_evidence.py",
        "--candidate",
        candidate,
        "--require-ready",
        "--json",
    ]


def import_preflight_command(candidate: str) -> list[str]:
    return [
        "python3",
        "scripts/ops/import_ghost_pulse_external_evidence.py",
        "--claim",
        "dpi_lab",
        "--candidate",
        candidate,
        "--require-ready",
        "--json",
    ]


def write_import_command(candidate: str) -> list[str]:
    return [
        "python3",
        "scripts/ops/import_ghost_pulse_external_evidence.py",
        "--claim",
        "dpi_lab",
        "--candidate",
        candidate,
        "--write",
        "--json",
    ]


def refresh_replacement_candidates_command() -> list[str]:
    return [
        "python3",
        "scripts/ops/verify_ghost_pulse_replacement_candidates.py",
        "--write-report",
        "--json",
    ]


def refresh_intake_report_command() -> list[str]:
    return [
        "python3",
        "scripts/ops/verify_ghost_pulse_external_evidence_intake.py",
        "--write-report",
        "--json",
    ]


def regenerate_cross_plane_proof_gate_command() -> list[str]:
    return [
        "python3",
        "scripts/ops/run_cross_plane_proof_gate.py",
        "--claim",
        "production_readiness",
        "--claim",
        "dataplane_delivery",
        "--claim",
        "traffic_delivery",
        "--claim",
        "customer_traffic",
        "--claim",
        "settlement_finality",
        "--claim",
        "dpi_bypass",
        "--json",
        "--output-json",
        ".tmp/validation-shards/cross-plane-proof-gate-current.json",
    ]


def build_operator_handoff(
    *,
    root: Path,
    candidate: Path,
    redacted_capture: str,
    redacted_capture_sha256: str,
) -> dict[str, object]:
    candidate_display = relative_path(root, candidate)
    validate_command = validator_command(candidate_display)
    preflight_command = import_preflight_command(candidate_display)
    refresh_replacement = refresh_replacement_candidates_command()
    refresh_intake = refresh_intake_report_command()
    write_command = write_import_command(candidate_display)
    return {
        "schema": COLLECTOR_OPERATOR_HANDOFF_SCHEMA,
        "surface": "external_dpi_proxy.collector",
        "candidate": candidate_display,
        "candidate_sha256": sha256_file(candidate) if candidate.is_file() else None,
        "redacted_capture": redacted_capture,
        "redacted_capture_sha256": redacted_capture_sha256,
        "commands_redacted": True,
        "raw_inputs_retained": False,
        "safe_local_input_rule": (
            "Do not paste private URLs, proxy endpoints, operator IDs, authorization "
            "scope, policy context, subscriber data, tokens, or raw captures into chat. "
            "Keep them only in the authorized local collector process."
        ),
        "read_only_post_collection_commands": [
            validate_command,
            preflight_command,
            refresh_replacement,
            refresh_intake,
        ],
        "write_sequence_after_ready": [
            write_command,
            refresh_replacement,
            refresh_intake,
            regenerate_cross_plane_proof_gate_command(),
        ],
        "claim_boundary": {
            "collector_handoff_is_not_evidence": True,
            "external_dpi_tested_claim_allowed": False,
            "dpi_bypass_claim_allowed": False,
            "dataplane_confirmed_claim_allowed": False,
            "customer_traffic_claim_allowed": False,
            "production_readiness_claim_allowed": False,
        },
    }


def attach_ghost_pulse_import_contract(
    root: Path,
    artifact_dir: Path,
    payload: dict[str, object],
    args: argparse.Namespace,
    *,
    started_at: datetime,
    control_results: list[ProbeResult],
    treatment_results: list[ProbeResult],
    baseline_blocked: bool,
    treatment_reachable: bool,
    verified: bool,
) -> None:
    failures = []
    if not verified:
        if not baseline_blocked:
            failures.append("control path was not blocked or detected")
        if not treatment_reachable:
            failures.append("treatment path was not reachable")
    measurements = {
        "authorized_lab": bool(args.allow_external_probes),
        "baseline_detected_or_blocked": baseline_blocked,
        "pulse_result_recorded": bool(treatment_results),
        "dpi_bypass_verified": verified,
    }
    payload.update(
        {
            "schema": GHOST_PULSE_CLAIM_SCHEMA,
            "claim_id": "dpi_lab",
            "observed_at_utc": utc_text(started_at),
            "simulated": False,
            "dry_run": False,
            "template": False,
            "commands": [
                {
                    "args": [
                        "scripts/ops/collect_external_dpi_proxy_reachability_evidence.py",
                        "--allow-external-probes",
                        "--target-url-sha256",
                        sha256_text(args.target_url),
                        "--treatment-url-sha256",
                        sha256_text(args.treatment_url or args.target_url),
                        "--treatment-proxy-present",
                        str(bool(args.treatment_proxy)).lower(),
                    ],
                    "exit_code": 0,
                }
            ],
            "measurements": measurements,
            "failures": failures,
            "required_artifact_roles": list(GHOST_PULSE_DPI_ARTIFACT_ROLES),
        }
    )

    artifact_base = artifact_dir / "ghost-pulse-claim"
    lab_scope = write_json_artifact(
        root,
        artifact_base / "lab-scope.json",
        {
            "authorization_scope": payload["authorization_scope"],
            "environment": payload["environment"],
        },
    )
    baseline_result = write_json_artifact(
        root,
        artifact_base / "baseline-result.json",
        {
            "control_buckets": bucket_counts(control_results),
            "baseline_detected_or_blocked": baseline_blocked,
            "raw_values_retained": False,
        },
    )
    pulse_result = write_json_artifact(
        root,
        artifact_base / "pulse-result.json",
        {
            "treatment_buckets": bucket_counts(treatment_results),
            "treatment_reachability_observed": treatment_reachable,
            "raw_values_retained": False,
        },
    )
    lab_conclusion = write_json_artifact(
        root,
        artifact_base / "lab-conclusion.json",
        {
            "measurements": payload["measurements"],
            "failures": payload["failures"],
            "claim_boundary": payload["claim_boundary"],
        },
    )
    payload["artifacts"] = [
        {"role": "lab_scope", **lab_scope},
        {"role": "baseline_result", **baseline_result},
        {"role": "pulse_result", **pulse_result},
        {"role": "lab_conclusion", **lab_conclusion},
    ]
    if isinstance(payload.get("artifact_identity"), dict):
        payload["artifact_identity"]["artifact_sha256"] = artifact_content_sha256(payload)  # type: ignore[index]


def build_payload(
    args: argparse.Namespace,
    *,
    started_at: datetime,
    finished_at: datetime,
    control_results: list[ProbeResult],
    treatment_results: list[ProbeResult],
    redacted_capture_sha256: str,
    redacted_capture_rel_path: str,
) -> dict[str, object]:
    target_hash = sha256_text(args.target_url)
    treatment_url = args.treatment_url or args.target_url
    treatment_hash = sha256_text(treatment_url)
    scope_hash = sha256_text(args.authorization_scope_id)
    operator_hash = sha256_text(args.operator_or_lab_id)
    profile_hash = sha256_text(args.isp_or_lab_profile)
    attempt_count = len(control_results) + len(treatment_results)
    treatment_success_count = sum(1 for item in treatment_results if item.bucket in REACHABLE_BUCKETS)
    baseline_blocked = bool(control_results) and all(item.bucket in BLOCKED_BUCKETS for item in control_results)
    treatment_reachable = bool(treatment_results) and treatment_success_count > 0
    verified = bool(args.allow_external_probes and baseline_blocked and treatment_reachable)
    decision = "bounded_external_dpi_bypass_observed" if verified else "rejected"
    control_failures = sorted(bucket_counts(control_results)) or ["none"]
    all_results = [*control_results, *treatment_results]
    artifact_id = f"external-dpi-proxy-reachability-{utc_text(started_at).replace(':', '').replace('-', '')}"

    payload: dict[str, object] = {
        "status": "VERIFIED" if verified else "INCOMPLETE",
        "artifact_identity": {
            "artifact_id": artifact_id,
            "schema_version": EVIDENCE_SCHEMA_VERSION,
            "claim_id": "dpi_lab",
            "captured_at_utc": utc_text(started_at),
            "collector_kind": args.collector_kind,
            "operator_or_lab_hash": operator_hash,
            "artifact_sha256": "0" * 64,
        },
        "authorization_scope": {
            "authorization_present": bool(args.allow_external_probes),
            "scope_id_hash": scope_hash,
            "scope_summary": args.scope_summary,
            "consent_or_legal_basis_present": bool(args.allow_external_probes),
            "collection_boundaries": [
                "no customer traffic",
                "no raw target identifiers retained in repository",
                "no raw proxy endpoint retained in repository",
                "no response bodies retained in repository",
            ],
        },
        "environment": {
            "network_region_bucket": args.network_region_bucket,
            "network_type": args.network_type,
            "isp_or_lab_profile_hash": profile_hash,
            "egress_location_bucket": args.egress_location_bucket,
            "time_window_utc": f"{utc_text(started_at)}/{utc_text(finished_at)}",
            "tool_versions": {"collector": "collect_external_dpi_proxy_reachability_evidence.py"},
            "policy_context": args.policy_context,
            "clock_sync_status": args.clock_sync_status,
        },
        "methodology": {
            "control_path_description": "direct control curl probe to hashed target",
            "treatment_path_description": (
                "curl probe to hashed target through configured proxy/fronting path"
                if args.treatment_proxy
                else "curl probe to hashed treatment URL without storing raw endpoint"
            ),
            "external_dpi_or_blocking_middlebox_observed": baseline_blocked,
            "probe_payload_class": "synthetic HTTP reachability probe",
            "success_criteria": "control path is blocked or detected and treatment path reaches the controlled endpoint",
            "failure_criteria": "control path is reachable, treatment path fails, or raw identifiers would need to be retained",
            "anti_replay_controls": ["bounded attempt count", "bounded time window", "hash-only target identity"],
        },
        "probe_matrix": {
            "probe_pairs": [
                {
                    "pair_id": "pair-1",
                    "transport": args.transport,
                    "proxy_or_fronting_mode": args.proxy_or_fronting_mode,
                    "target_category": args.target_category,
                    "probe_target_hash": target_hash,
                    "control_result_bucket": control_results[-1].bucket if control_results else "not_run",
                    "treatment_result_bucket": treatment_results[-1].bucket if treatment_results else "not_run",
                    "attempts": attempt_count,
                    "successes": treatment_success_count,
                    "failure_buckets": control_failures,
                }
            ],
            "attempt_count": attempt_count,
            "success_count": treatment_success_count,
            "failure_buckets": control_failures,
            "control_probe_ids": [f"control-{item.attempt_index}" for item in control_results],
            "treatment_probe_ids": [f"treatment-{item.attempt_index}" for item in treatment_results],
        },
        "packet_flow_summary": {
            "flows_observed": attempt_count,
            "bytes_bucket": bucket_bytes(all_results),
            "duration_ms_bucket": bucket_duration_ms(all_results),
            "rtt_ms_bucket": "not_measured_by_curl",
            "loss_bucket": "not_measured_by_curl",
            "dns_result_bucket": "summarized_in_failure_buckets",
            "tls_handshake_bucket": "summarized_in_failure_buckets",
            "http_status_bucket": bucket_http_status(all_results),
            "capture_artifact_hashes": [redacted_capture_sha256],
            "packet_payloads_redacted": True,
        },
        "raw_capture_redaction": {
            "redaction_performed": True,
            "redaction_tool": "collect_external_dpi_proxy_reachability_evidence.py",
            "redaction_tool_version": args.redaction_tool_version,
            "redacted_fields": ["target_url", "treatment_url", "proxy_endpoint", "response_body", "headers"],
            "forbidden_raw_fields_absent": True,
            "raw_capture_retention_policy": "raw curl response bodies were discarded; only redacted buckets and hashes were written",
            "redacted_capture_sha256": redacted_capture_sha256,
        },
        "repeatability_limits": {
            "sample_window_utc": f"{utc_text(started_at)}/{utc_text(finished_at)}",
            "sample_count": attempt_count,
            "locations_count": 1,
            "networks_count": 1,
            "known_confounders": [
                "middlebox policy can change",
                "CDN routing can change",
                "target-side failures can mimic blocking",
                "proxy path health can change",
            ],
            "not_generalizable_beyond_environment": True,
            "refresh_after_utc": utc_text(finished_at + timedelta(days=7)),
        },
        "result_summary": {
            "external_dpi_tested": verified,
            "baseline_blocked_or_detected": baseline_blocked,
            "treatment_reachability_observed": treatment_reachable,
            "reachability_observed": treatment_reachable,
            "dpi_bypass_confirmed": verified,
            "bypass_confirmed": verified,
            "dataplane_confirmed": verified,
            "production_ready": False,
            "confidence_bucket": "bounded-single-network-window" if verified else "insufficient-for-dpi-claim",
            "decision": decision,
        },
        "claim_boundary": {
            "summary": "Bounded authorized external observation only; not production proof.",
            "not_proven": [
                "production readiness",
                "durable censorship bypass",
                "anonymity",
                "provider health",
                "customer traffic",
                "payment or token settlement finality",
            ],
            "proof_claims": {
                "external_dpi_tested": verified,
                "baseline_blocked_or_detected": baseline_blocked,
                "treatment_reachability_observed": treatment_reachable,
                "reachability_observed": treatment_reachable,
                "dpi_bypass_confirmed": verified,
                "bypass_confirmed": verified,
                "dataplane_confirmed": verified,
                "production_ready": False,
                "customer_traffic_confirmed": False,
                "durable_policy_confirmed": False,
                "anonymity_confirmed": False,
                "provider_health_confirmed": False,
                "payment_or_token_settlement_finality_confirmed": False,
            },
            "upgrade_rule": "Only a verified authorized control-vs-treatment artifact can raise DPI flags; production flags remain false.",
        },
        "evidence_links": {
            "source_artifacts": [
                {
                    "path": redacted_capture_rel_path,
                    "role": "redacted_probe_summary",
                }
            ],
            "artifact_roles": ["redacted_probe_summary", "collector_summary"],
            "source_hashes": [
                {
                    "path": redacted_capture_rel_path,
                    "sha256": redacted_capture_sha256,
                }
            ],
            "related_local_evidence_refs": [],
        },
    }
    source_hashes = payload["evidence_links"]["source_hashes"]
    if treatment_hash != target_hash:
        source_hashes.append({"path": "treatment_target_hash", "sha256": treatment_hash})
    if args.treatment_proxy:
        source_hashes.append(
            {"path": "treatment_proxy_endpoint_hash", "sha256": sha256_text(args.treatment_proxy)}
        )
    payload["artifact_identity"]["artifact_sha256"] = artifact_content_sha256(payload)
    return payload


def redacted_capture_payload(
    args: argparse.Namespace,
    control_results: list[ProbeResult],
    treatment_results: list[ProbeResult],
) -> dict[str, object]:
    return {
        "schema": "x0tta6bl4.external_dpi_proxy_redacted_probe_summary.v1",
        "target_hash": sha256_text(args.target_url),
        "treatment_target_hash": sha256_text(args.treatment_url or args.target_url),
        "treatment_proxy_present": bool(args.treatment_proxy),
        "treatment_proxy_hash_present": bool(args.treatment_proxy),
        "control_results": [asdict(result) for result in control_results],
        "treatment_results": [asdict(result) for result in treatment_results],
        "raw_values_retained": False,
    }


def collect(args: argparse.Namespace, runner: Runner = default_runner) -> dict[str, object]:
    if not args.allow_external_probes:
        raise SystemExit("--allow-external-probes is required for network collection")
    if args.attempts <= 0:
        raise SystemExit("--attempts must be positive")
    if args.timeout_s <= 0:
        raise SystemExit("--timeout-s must be positive")

    root = args.root.resolve()
    output = resolve_path(root, args.output)
    artifact_dir = resolve_path(root, args.artifact_dir)
    started_at = utc_now()
    control_results: list[ProbeResult] = []
    treatment_results: list[ProbeResult] = []
    for index in range(1, args.attempts + 1):
        control_results.append(
            run_probe(
                path_kind="control",
                url=args.target_url,
                proxy=None,
                attempt_index=index,
                timeout_s=args.timeout_s,
                runner=runner,
            )
        )
        treatment_results.append(
            run_probe(
                path_kind="treatment",
                url=args.treatment_url or args.target_url,
                proxy=args.treatment_proxy,
                attempt_index=index,
                timeout_s=args.timeout_s,
                runner=runner,
            )
        )
    finished_at = utc_now()

    artifact_dir.mkdir(parents=True, exist_ok=True)
    redacted_capture = redacted_capture_payload(args, control_results, treatment_results)
    redacted_text = json.dumps(redacted_capture, ensure_ascii=False, indent=2, sort_keys=True)
    redacted_hash = sha256_text(redacted_text)
    redacted_path = artifact_dir / f"redacted-probe-summary-{redacted_hash[:12]}.json"
    redacted_path.write_text(redacted_text, encoding="utf-8")

    try:
        redacted_rel = redacted_path.relative_to(root).as_posix()
    except ValueError:
        redacted_rel = redacted_path.as_posix()
    payload = build_payload(
        args,
        started_at=started_at,
        finished_at=finished_at,
        control_results=control_results,
        treatment_results=treatment_results,
        redacted_capture_sha256=redacted_hash,
        redacted_capture_rel_path=redacted_rel,
    )
    baseline_blocked = bool(control_results) and all(item.bucket in BLOCKED_BUCKETS for item in control_results)
    treatment_reachable = bool(treatment_results) and any(item.bucket in REACHABLE_BUCKETS for item in treatment_results)
    attach_ghost_pulse_import_contract(
        root,
        artifact_dir,
        payload,
        args,
        started_at=started_at,
        control_results=control_results,
        treatment_results=treatment_results,
        baseline_blocked=baseline_blocked,
        treatment_reachable=treatment_reachable,
        verified=payload["status"] == "VERIFIED",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    output_display = relative_path(root, output)
    operator_handoff = build_operator_handoff(
        root=root,
        candidate=output,
        redacted_capture=redacted_rel,
        redacted_capture_sha256=redacted_hash,
    )
    return {
        "status": payload["status"],
        "output": output_display,
        "redacted_capture": redacted_rel,
        "control_buckets": bucket_counts(control_results),
        "treatment_buckets": bucket_counts(treatment_results),
        "validator_command": " ".join(validator_command(output_display)),
        "validator_command_args": validator_command(output_display),
        "import_preflight_command_args": import_preflight_command(output_display),
        "operator_handoff": operator_handoff,
        "claim_boundary": {
            "production_ready": False,
            "customer_traffic_confirmed": False,
            "settlement_finality_confirmed": False,
            "raw_values_retained": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = collect(args)
    except SystemExit as exc:
        if isinstance(exc.code, int):
            return exc.code
        print(str(exc), file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"status={report['status']}")
        print(f"output={report['output']}")
        print(f"redacted_capture={report['redacted_capture']}")
        print(f"validator_command={report['validator_command']}")
        print(f"import_preflight_command={' '.join(report['import_preflight_command_args'])}")
    return 0 if report["status"] == "VERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
