#!/usr/bin/env python3
"""Build the top-level VPN production-candidate goal status.

This report reads local evidence artifacts only. It does not SSH to NL/SPB,
does not restart services, and does not mutate VPN runtime state.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path("/mnt/projects")
DIAGNOSTICS_DIR = ROOT / "nl-diagnostics"
DEFAULT_DECISION = DIAGNOSTICS_DIR / "current-vpn-decision-2026-05-28.json"
DEFAULT_ANTI_BLOCK_AUDIT = DIAGNOSTICS_DIR / "nl-anti-block-production-audit-2026-06-02.json"
DEFAULT_CLIENT_MATRIX = (
    DIAGNOSTICS_DIR / "nl-anti-block-client-compatibility-matrix-2026-06-02.json"
)
DEFAULT_REMOTE_REQUEST = (
    DIAGNOSTICS_DIR / "nl-anti-block-remote-client-evidence-request-2026-06-02.json"
)
DEFAULT_TELEGRAM_WARP_PLAN = (
    DIAGNOSTICS_DIR / "nl-telegram-media-warp-route-plan-2026-06-02-fresh.json"
)
DEFAULT_MONITOR_RESTORE_READINESS = (
    DIAGNOSTICS_DIR / "vpn-monitor-restore-readiness-2026-06-06.json"
)
DEFAULT_READINESS_AUDIT = DIAGNOSTICS_DIR / "vpn-plan-readiness-audit-2026-05-28.json"
DEFAULT_MANIFEST = ROOT / "services" / "nl-server" / "manifest.json"
DEFAULT_PREFLIGHT_VALIDATOR = (
    ROOT / "services" / "nl-server" / "tools" / "validate_preflight_readiness.py"
)
DEFAULT_FIRSTPARTY_ROOT = ROOT / "src" / "network" / "firstparty_vpn"
DEFAULT_FIRSTPARTY_CONTRACT = (
    ROOT / "docs" / "architecture" / "FIRSTPARTY_PQC_ZERO_TRUST_VPN_CONTRACT.md"
)
DEFAULT_FIRSTPARTY_TEST_NODE = (
    ROOT / "services" / "nl-server" / "firstparty-vpn-test" / "x0vpn_test_node.py"
)
DEFAULT_FIRSTPARTY_UNIT_TEST = (
    ROOT / "tests" / "unit" / "network" / "test_firstparty_vpn_protocol_unit.py"
)
DEFAULT_JSON_OUT = DIAGNOSTICS_DIR / "vpn-production-candidate-goal-2026-06-02.json"
DEFAULT_MARKDOWN_OUT = DIAGNOSTICS_DIR / "vpn-production-candidate-goal-2026-06-02.md"
DEFAULT_MAX_EVIDENCE_AGE_HOURS = 24

PASS = "pass"
READY_TO_STAGE = "ready_to_stage"
BLOCKED_EXTERNAL_EVIDENCE = "blocked_external_evidence"
MISSING = "missing"

REQUIRED_FORBIDDEN_RESTARTS = {
    "ghost-access-nl-xhttp.service",
    "ghost-access-nl-https-ws.service",
    "telegram-bot-simple.service",
    "nginx",
}
REQUIRED_SAFE_REPLY_OPTIONS = {
    "pass connected",
    "fail timeout",
    "fail import",
    "fail no-internet",
}
LEGACY_FOREIGN_REQUIREMENT_IDS = {
    "CORE-REALITY-01",
    "ANTIBLOCK-CLIENTS-01",
    "TELEGRAM-WARP-01",
}


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def age_hours(timestamp: datetime | None, *, now: datetime) -> float | None:
    if timestamp is None:
        return None
    return (now - timestamp).total_seconds() / 3600


def age_text(value: float | None) -> str:
    if value is None:
        return "missing"
    return f"{value:.2f}"


def is_fresh_age(value: float | None, *, max_age_hours: int) -> bool:
    return value is not None and 0 <= value <= max_age_hours


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def read_latest_firstparty_canary(diagnostics_dir: Path = DIAGNOSTICS_DIR) -> dict[str, Any]:
    candidates = sorted(diagnostics_dir.glob("firstparty-live-canary-*/summary.json"))
    if not candidates:
        return {}
    path = candidates[-1]
    payload = read_json(path)
    payload["summary_path"] = str(path)
    return payload


def read_latest_firstparty_production_readiness(
    diagnostics_dir: Path = DIAGNOSTICS_DIR,
) -> dict[str, Any]:
    candidates = sorted(
        diagnostics_dir.glob("firstparty-production-readiness-*/summary.json")
    )
    if not candidates:
        return {}
    path = candidates[-1]
    payload = read_json(path)
    payload["summary_path"] = str(path)
    return payload


def read_latest_firstparty_staging_packet(
    diagnostics_dir: Path = DIAGNOSTICS_DIR,
) -> dict[str, Any]:
    candidates = sorted(diagnostics_dir.glob("firstparty-staging-packet-*/summary.json"))
    if not candidates:
        return {}
    path = candidates[-1]
    payload = read_json(path)
    payload["summary_path"] = str(path)
    return payload


def read_latest_firstparty_rollout_packet(
    diagnostics_dir: Path = DIAGNOSTICS_DIR,
) -> dict[str, Any]:
    candidates = sorted(diagnostics_dir.glob("firstparty-rollout-packet-*/summary.json"))
    if not candidates:
        return {}
    path = candidates[-1]
    payload = read_json(path)
    payload["summary_path"] = str(path)
    return payload


def read_latest_firstparty_preapply_readiness(
    diagnostics_dir: Path = DIAGNOSTICS_DIR,
) -> dict[str, Any]:
    candidates = sorted(
        diagnostics_dir.glob("firstparty-preapply-readiness-*/summary.json")
    )
    if not candidates:
        return {}
    path = candidates[-1]
    payload = read_json(path)
    payload["summary_path"] = str(path)
    return payload


def read_latest_firstparty_production_endpoint(
    diagnostics_dir: Path = DIAGNOSTICS_DIR,
) -> dict[str, Any]:
    candidates = sorted(
        diagnostics_dir.glob("firstparty-production-endpoint-*/summary.json")
    )
    if not candidates:
        return {}
    path = candidates[-1]
    payload = read_json(path)
    payload["summary_path"] = str(path)
    return payload


def read_latest_firstparty_production_apply_packet(
    diagnostics_dir: Path = DIAGNOSTICS_DIR,
) -> dict[str, Any]:
    candidates = sorted(
        diagnostics_dir.glob("firstparty-production-apply-packet-*/summary.json")
    )
    if not candidates:
        return {}
    path = candidates[-1]
    payload = read_json(path)
    payload["summary_path"] = str(path)
    return payload


def read_latest_firstparty_secure_material_handoff(
    diagnostics_dir: Path = DIAGNOSTICS_DIR,
) -> dict[str, Any]:
    candidates = sorted(
        diagnostics_dir.glob("firstparty-secure-material-handoff-*/summary.json")
    )
    if not candidates:
        return {}
    path = candidates[-1]
    payload = read_json(path)
    payload["summary_path"] = str(path)
    return payload


def read_latest_firstparty_production_authorization(
    diagnostics_dir: Path = DIAGNOSTICS_DIR,
) -> dict[str, Any]:
    candidates = sorted(
        diagnostics_dir.glob("firstparty-production-authorization-*/summary.json")
    )
    if not candidates:
        return {}
    path = candidates[-1]
    payload = read_json(path)
    payload["summary_path"] = str(path)
    return payload


def read_latest_firstparty_production_apply_runbook(
    diagnostics_dir: Path = DIAGNOSTICS_DIR,
) -> dict[str, Any]:
    candidates = sorted(
        diagnostics_dir.glob("firstparty-production-apply-runbook-*/summary.json")
    )
    if not candidates:
        return {}
    path = candidates[-1]
    payload = read_json(path)
    payload["summary_path"] = str(path)
    return payload


def read_latest_firstparty_production_operator_script(
    diagnostics_dir: Path = DIAGNOSTICS_DIR,
) -> dict[str, Any]:
    candidates = sorted(
        diagnostics_dir.glob("firstparty-production-operator-script-*/summary.json")
    )
    if not candidates:
        return {}
    path = candidates[-1]
    payload = read_json(path)
    payload["summary_path"] = str(path)
    return payload


def read_latest_firstparty_production_operator_dryrun_audit(
    diagnostics_dir: Path = DIAGNOSTICS_DIR,
) -> dict[str, Any]:
    candidates = sorted(
        diagnostics_dir.glob("firstparty-production-operator-dryrun-audit-*/summary.json")
    )
    if not candidates:
        return {}
    path = candidates[-1]
    payload = read_json(path)
    payload["summary_path"] = str(path)
    return payload


def read_latest_firstparty_production_apply_transcript_audit(
    diagnostics_dir: Path = DIAGNOSTICS_DIR,
) -> dict[str, Any]:
    candidates = sorted(
        diagnostics_dir.glob("firstparty-production-apply-transcript-audit-*/summary.json")
    )
    if not candidates:
        return {}
    path = candidates[-1]
    payload = read_json(path)
    payload["summary_path"] = str(path)
    return payload


def read_latest_firstparty_production_completion_audit(
    diagnostics_dir: Path = DIAGNOSTICS_DIR,
) -> dict[str, Any]:
    candidates = sorted(
        diagnostics_dir.glob("firstparty-production-completion-audit-*/summary.json")
    )
    if not candidates:
        return {}
    path = candidates[-1]
    payload = read_json(path)
    payload["summary_path"] = str(path)
    return payload


def read_vpn_monitor_restore_readiness(
    path: Path = DEFAULT_MONITOR_RESTORE_READINESS,
) -> dict[str, Any]:
    payload = read_json(path)
    if payload:
        payload["summary_path"] = str(path)
    return payload


def run_preflight_validator(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "ok": False,
            "deploy_status": "validator_missing",
            "nl_write_allowed": None,
            "checks": [],
        }
    completed = subprocess.run(
        [sys.executable, str(path)],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    payload.setdefault("ok", completed.returncode == 0)
    payload["validator_exit_code"] = completed.returncode
    if completed.stderr:
        payload["validator_stderr_tail"] = completed.stderr[-1000:]
    return payload


def requirement(
    *,
    item_id: str,
    title: str,
    status: str,
    evidence: list[str],
    next_step: str,
    ok: bool | None = None,
) -> dict[str, Any]:
    if ok is None:
        ok = status in {PASS, READY_TO_STAGE}
    return {
        "id": item_id,
        "title": title,
        "status": status,
        "ok": ok,
        "evidence": evidence,
        "next_step": next_step,
    }


def bool_text(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if value is None:
        return "missing"
    return str(value)


def compact_list(values: Any, *, limit: int = 6) -> str:
    if not isinstance(values, list):
        return "missing"
    compacted = [str(value) for value in values[:limit]]
    if len(values) > limit:
        compacted.append(f"...+{len(values) - limit}")
    return ", ".join(compacted) if compacted else "none"


def requirement_evidence_map(row: dict[str, Any]) -> dict[str, str]:
    evidence: dict[str, str] = {}
    for value in row.get("evidence") or []:
        if not isinstance(value, str) or "=" not in value:
            continue
        key, raw = value.split("=", 1)
        evidence[key] = raw
    return evidence


def missing_client_requirements(matrix: dict[str, Any]) -> list[str]:
    completion = matrix.get("completion_rule")
    if not isinstance(completion, dict):
        return []
    return [str(value) for value in completion.get("missing_requirements") or []]


def client_matrix_complete(matrix: dict[str, Any]) -> bool:
    completion = matrix.get("completion_rule")
    if not isinstance(completion, dict):
        return str(matrix.get("decision") or "") == "CLIENT_MATRIX_COMPLETE"
    return (
        str(completion.get("current_status") or "") == "complete"
        or str(matrix.get("decision") or "") == "CLIENT_MATRIX_COMPLETE"
    ) and not missing_client_requirements(matrix)


def passing_real_client_checks(matrix: dict[str, Any]) -> int:
    checks = matrix.get("real_client_checks")
    if not isinstance(checks, list):
        return 0
    return sum(
        1
        for row in checks
        if isinstance(row, dict)
        and row.get("status") == "pass"
        and row.get("raw_secret_material_stored") is False
    )


def remote_request_ready(packet: dict[str, Any], missing: list[str]) -> bool:
    if not missing:
        return packet.get("decision") in {
            "REMOTE_CLIENT_EVIDENCE_REQUEST_NOT_NEEDED",
            "REMOTE_CLIENT_EVIDENCE_REQUEST_READY",
        }
    request_count = packet.get("request_count")
    minimum_reports = packet.get("minimum_reports_required")
    packet_missing = [str(value) for value in packet.get("missing_requirements") or []]
    return (
        packet.get("decision") == "REMOTE_CLIENT_EVIDENCE_REQUEST_READY"
        and isinstance(request_count, int)
        and request_count > 0
        and minimum_reports == request_count
        and set(missing).issubset(set(packet_missing))
    )


def remote_request_safety(packet: dict[str, Any]) -> dict[str, bool]:
    requests = packet.get("requests")
    if not isinstance(requests, list):
        requests = []
    no_requests_needed = packet.get("decision") == "REMOTE_CLIENT_EVIDENCE_REQUEST_NOT_NEEDED"
    if no_requests_needed and not requests:
        return {
            "privacy_ok": (packet.get("privacy") or {}).get("output_privacy_ok") is True,
            "freshness_policy_ok": True,
            "record_commands_use_stdin": True,
            "validate_commands_no_write": True,
            "safe_reply_options_ok": True,
            "hash_binding_policy_ok": True,
            "reply_commands_hash_guard_ok": True,
            "ready": (packet.get("privacy") or {}).get("output_privacy_ok") is True,
        }

    def _command(row: dict[str, Any], key: str) -> str:
        return str(row.get(key) or "")

    def _record_command_ok(row: dict[str, Any], key: str) -> bool:
        command = _command(row, key)
        return (
            "record_remote_client_evidence_reply.py" in command
            and "--reply-stdin" in command
            and "--write" in command
            and "--record-matrix" in command
            and "--refresh-artifacts" in command
            and "--reply " not in command
        )

    def _validate_command_ok(row: dict[str, Any], key: str) -> bool:
        command = _command(row, key)
        return (
            "record_remote_client_evidence_reply.py" in command
            and "--reply-stdin" in command
            and "--write" not in command
            and "--record-matrix" not in command
            and "--refresh-artifacts" not in command
            and "--reply " not in command
        )

    def _command_hash_guard_ok(row: dict[str, Any], key: str) -> bool:
        command = _command(row, key)
        return "--expect-request-packet-sha256" in command and "sha256sum" in command

    privacy_ok = (packet.get("privacy") or {}).get("output_privacy_ok") is True
    freshness_policy_ok = "older than 24 hours" in str(packet.get("request_freshness_policy") or "")
    hash_policy = str(packet.get("request_packet_hash_binding_policy") or "")
    hash_binding_policy_ok = (
        "--expect-request-packet-sha256" in hash_policy
        and "source_sha256" in hash_policy
        and "sha256sum" in hash_policy
    )
    record_commands_use_stdin = bool(requests) and all(
        isinstance(row, dict)
        and _record_command_ok(row, "operator_reply_record_pass_command")
        and _record_command_ok(row, "operator_reply_record_fail_command")
        for row in requests
    )
    validate_commands_no_write = bool(requests) and all(
        isinstance(row, dict)
        and _validate_command_ok(row, "operator_reply_validate_pass_command")
        and _validate_command_ok(row, "operator_reply_validate_fail_command")
        for row in requests
    )
    safe_reply_options_ok = bool(requests) and all(
        isinstance(row, dict)
        and REQUIRED_SAFE_REPLY_OPTIONS.issubset(set(str(value) for value in row.get("safe_reply_options") or []))
        for row in requests
    )
    reply_commands_hash_guard_ok = bool(requests) and all(
        isinstance(row, dict)
        and _command_hash_guard_ok(row, "operator_reply_record_pass_command")
        and _command_hash_guard_ok(row, "operator_reply_record_fail_command")
        and _command_hash_guard_ok(row, "operator_reply_validate_pass_command")
        and _command_hash_guard_ok(row, "operator_reply_validate_fail_command")
        for row in requests
    )
    ready = all(
        [
            privacy_ok,
            freshness_policy_ok,
            record_commands_use_stdin,
            validate_commands_no_write,
            safe_reply_options_ok,
            hash_binding_policy_ok,
            reply_commands_hash_guard_ok,
        ]
    )
    return {
        "privacy_ok": privacy_ok,
        "freshness_policy_ok": freshness_policy_ok,
        "record_commands_use_stdin": record_commands_use_stdin,
        "validate_commands_no_write": validate_commands_no_write,
        "safe_reply_options_ok": safe_reply_options_ok,
        "hash_binding_policy_ok": hash_binding_policy_ok,
        "reply_commands_hash_guard_ok": reply_commands_hash_guard_ok,
        "ready": ready,
    }


def preflight_check_ok(preflight: dict[str, Any], name: str) -> bool:
    checks = preflight.get("checks")
    if not isinstance(checks, list):
        return False
    return any(
        isinstance(row, dict) and row.get("name") == name and row.get("ok") is True
        for row in checks
    )


def collect_privacy_findings(payload: Any, *, path: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(payload, dict):
        privacy = payload.get("privacy")
        if isinstance(privacy, dict):
            if privacy.get("output_privacy_ok") is False:
                findings.append(f"{path}.privacy.output_privacy_ok=false")
            for key, value in privacy.items():
                if key.startswith("raw_") and key.endswith("_stored") and value is not False:
                    findings.append(f"{path}.privacy.{key}={value}")
        privacy_rule = payload.get("privacy_rule")
        if isinstance(privacy_rule, dict) and privacy_rule.get("raw_secret_material_stored") is not False:
            findings.append(f"{path}.privacy_rule.raw_secret_material_stored={privacy_rule.get('raw_secret_material_stored')}")
        if payload.get("raw_secret_material_stored") is not False and "raw_secret_material_stored" in payload:
            findings.append(f"{path}.raw_secret_material_stored={payload.get('raw_secret_material_stored')}")
        for key, value in payload.items():
            if isinstance(value, (dict, list)):
                findings.extend(collect_privacy_findings(value, path=f"{path}.{key}"))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            if isinstance(value, (dict, list)):
                findings.extend(collect_privacy_findings(value, path=f"{path}[{index}]"))
    return findings


def audit_core_vless_reality(
    decision: dict[str, Any],
    monitor_restore_readiness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    monitor_restore_readiness = monitor_restore_readiness or {}
    decision_data = decision.get("decision") if isinstance(decision.get("decision"), dict) else {}
    classification = (
        decision.get("classification") if isinstance(decision.get("classification"), dict) else {}
    )
    evidence_rows = classification.get("evidence") if isinstance(classification.get("evidence"), list) else []
    evidence_text = "\n".join(str(row) for row in evidence_rows)
    safe_flags = (
        decision.get("mutation_allowed") is False
        and decision.get("nl_mutation_allowed") is False
        and decision.get("auto_profile_switch_allowed") is False
        and decision_data.get("nl_mutation_allowed") is False
    )
    core_evidence_present = all(
        marker in evidence_text
        for marker in (
            "external exit IP is VPN server",
            "packet_loss_percent=0",
            "NL key services active",
            "NL core listeners 443/2083/39829 present",
        )
    )
    overall = str(classification.get("overall_status") or "missing")
    transport = str(classification.get("transport_status") or "missing")
    decision_name = str(decision_data.get("decision") or "")
    ready = (
        decision_name in {"observe", "manual_profile_review"}
        and overall in {"ok", "advisory"}
        and transport in {"healthy", "advisory"}
        and core_evidence_present
        and safe_flags
    )
    if decision_name == "restore_transport_canary_monitor":
        next_step = (
            "run restore_nl_vpn_monitor_canary_timer.sh --dry-run/--precheck, "
            "then apply only after APPLY_RESTORE_NL_VPN_MONITOR_CANARY_TIMER and collect a fresh snapshot"
        )
    else:
        next_step = "keep observing core Reality separately from Telegram media degradation"
    return requirement(
        item_id="CORE-REALITY-01",
        title="Main NL VLESS/Reality contour remains stable",
        status=PASS if ready else MISSING,
        evidence=[
            f"decision={decision_data.get('decision') or 'missing'}",
            f"overall_status={overall}",
            f"transport_status={transport}",
            f"telegram_media_status={classification.get('telegram_media_status') or 'missing'}",
            f"core_evidence_present={bool_text(core_evidence_present)}",
            f"safe_mutation_flags={bool_text(safe_flags)}",
            f"monitor_restore_decision={monitor_restore_readiness.get('decision') or 'missing'}",
            f"monitor_restore_ready_for_approval={bool_text(monitor_restore_readiness.get('ready_for_approval'))}",
            f"monitor_restore_apply_allowed_now={bool_text(monitor_restore_readiness.get('apply_allowed_now'))}",
        ],
        next_step=next_step,
    )


def audit_evidence_freshness(
    decision: dict[str, Any],
    remote_request: dict[str, Any],
    *,
    now: datetime | None = None,
    max_age_hours: int = DEFAULT_MAX_EVIDENCE_AGE_HOURS,
) -> dict[str, Any]:
    now = (now or datetime.now(UTC)).astimezone(UTC)
    decision_generated_at = decision.get("generated_at")
    request_generated_at = remote_request.get("generated_at")
    decision_age = age_hours(parse_timestamp(decision_generated_at), now=now)
    request_age = age_hours(parse_timestamp(request_generated_at), now=now)
    decision_fresh = is_fresh_age(decision_age, max_age_hours=max_age_hours)
    request_fresh = is_fresh_age(request_age, max_age_hours=max_age_hours)
    ready = decision_fresh and request_fresh
    return requirement(
        item_id="EVIDENCE-FRESHNESS-01",
        title="Decision and remote request evidence are fresh enough for operator action",
        status=PASS if ready else MISSING,
        evidence=[
            f"max_age_hours={max_age_hours}",
            f"decision_generated_at={decision_generated_at or 'missing'}",
            f"decision_age_hours={age_text(decision_age)}",
            f"decision_fresh={bool_text(decision_fresh)}",
            f"remote_request_generated_at={request_generated_at or 'missing'}",
            f"remote_request_age_hours={age_text(request_age)}",
            f"remote_request_fresh={bool_text(request_fresh)}",
        ],
        next_step=(
            "continue using current read-only evidence"
            if ready
            else "refresh read-only snapshot, current decision, remote request packet, and goal status"
        ),
    )


def audit_anti_block_real_clients(
    anti_block_audit: dict[str, Any],
    matrix: dict[str, Any],
    remote_request: dict[str, Any],
    preflight: dict[str, Any],
) -> dict[str, Any]:
    missing = missing_client_requirements(matrix)
    complete = client_matrix_complete(matrix)
    request_contract_ready = remote_request_ready(remote_request, missing)
    request_safety = remote_request_safety(remote_request)
    no_requests_needed = remote_request.get("decision") == "REMOTE_CLIENT_EVIDENCE_REQUEST_NOT_NEEDED"
    preflight_reply_dry_run_uses_packet_hash = no_requests_needed or preflight_check_ok(
        preflight,
        "remote_client_evidence_reply_dry_run_uses_packet_hash",
    )
    request_ready = (
        request_contract_ready
        and request_safety["ready"]
        and preflight_reply_dry_run_uses_packet_hash
    )
    remaining = anti_block_audit.get("remaining_before_goal_complete")
    if not isinstance(remaining, list):
        remaining = []
    status = PASS if complete else BLOCKED_EXTERNAL_EVIDENCE
    next_step = (
        "rerun refresh_client_evidence_artifacts.py --write and final audit"
        if complete
        else "collect the privacy-safe remote request-packet reports and record short replies"
        if request_ready
        else "rerun preflight validator; reply dry-run must bind to the request packet hash"
        if request_contract_ready and request_safety["ready"]
        else "regenerate remote request packet with stdin record commands, non-writing validate commands, and packet hash guard"
        if request_contract_ready
        else "record safe real-client evidence for Android Happ/Hiddify, mobile network, and restricted/work Wi-Fi"
    )
    return requirement(
        item_id="ANTIBLOCK-CLIENTS-01",
        title="VLESS Reality profile is confirmed by real clients",
        status=status,
        ok=complete,
        evidence=[
            f"matrix_decision={matrix.get('decision') or 'missing'}",
            f"matrix_complete={bool_text(complete)}",
            f"missing_requirements={compact_list(missing)}",
            f"passing_real_client_checks={passing_real_client_checks(matrix)}",
            f"production_audit_decision={anti_block_audit.get('decision') or 'missing'}",
            f"remote_request_decision={remote_request.get('decision') or 'missing'}",
            f"remote_request_count={remote_request.get('request_count') if remote_request else 'missing'}",
            f"remote_request_ready={bool_text(request_ready)}",
            f"remote_request_contract_ready={bool_text(request_contract_ready)}",
            f"remote_request_privacy_ok={bool_text(request_safety['privacy_ok'])}",
            f"remote_request_freshness_policy_ok={bool_text(request_safety['freshness_policy_ok'])}",
            f"remote_request_record_commands_use_stdin={bool_text(request_safety['record_commands_use_stdin'])}",
            f"remote_request_validate_commands_no_write={bool_text(request_safety['validate_commands_no_write'])}",
            f"remote_request_safe_reply_options_ok={bool_text(request_safety['safe_reply_options_ok'])}",
            f"remote_request_hash_binding_policy_ok={bool_text(request_safety['hash_binding_policy_ok'])}",
            f"remote_request_reply_commands_hash_guard_ok={bool_text(request_safety['reply_commands_hash_guard_ok'])}",
            f"remote_request_reply_dry_run_uses_packet_hash={bool_text(preflight_reply_dry_run_uses_packet_hash)}",
            f"remaining_count={len(remaining)}",
        ],
        next_step=next_step,
    )


def audit_telegram_warp_route(plan: dict[str, Any]) -> dict[str, Any]:
    rollout = plan.get("rollout") if isinstance(plan.get("rollout"), dict) else {}
    evidence = plan.get("current_evidence") if isinstance(plan.get("current_evidence"), dict) else {}
    forbidden_restarts = set(str(value) for value in rollout.get("forbidden_restarts") or [])
    restart_scope = [str(value) for value in rollout.get("restart_scope") or []]
    safe_rollout = (
        rollout.get("requires_explicit_operator_confirm") == "APPLY_TELEGRAM_MEDIA_WARP_ROUTE"
        and rollout.get("requires_fresh_readonly_snapshot") is True
        and rollout.get("requires_config_backup") is True
        and rollout.get("requires_xray_config_test_before_restart") is True
        and restart_scope == ["x-ui"]
        and REQUIRED_FORBIDDEN_RESTARTS.issubset(forbidden_restarts)
        and rollout.get("mutation_scope") == "routing.rules only"
    )
    target_rule = plan.get("target_rule") if isinstance(plan.get("target_rule"), dict) else {}
    ready = (
        plan.get("decision") == "TELEGRAM_MEDIA_WARP_ROUTE_READY_TO_STAGE"
        and not plan.get("blockers")
        and evidence.get("warp_status") == "healthy"
        and "warp" in set(str(value) for value in evidence.get("xray_outbound_tags") or [])
        and target_rule.get("outboundTag") == "warp"
        and safe_rollout
    )
    return requirement(
        item_id="TELEGRAM-WARP-01",
        title="Telegram media has a guarded WARP-route plan",
        status=READY_TO_STAGE if ready else MISSING,
        evidence=[
            f"plan_decision={plan.get('decision') or 'missing'}",
            f"telegram_media_status={evidence.get('telegram_media_status') or 'missing'}",
            f"warp_status={evidence.get('warp_status') or 'missing'}",
            f"target_outbound={target_rule.get('outboundTag') or 'missing'}",
            f"safe_rollout_guard={bool_text(safe_rollout)}",
            f"restart_scope={compact_list(restart_scope)}",
        ],
        next_step="stage only after explicit APPLY_TELEGRAM_MEDIA_WARP_ROUTE approval and a fresh read-only snapshot",
    )


def audit_nl_readonly_gate(
    readiness: dict[str, Any],
    manifest: dict[str, Any],
    preflight: dict[str, Any],
) -> dict[str, Any]:
    summary = readiness.get("summary") if isinstance(readiness.get("summary"), dict) else {}
    preflight_ok = (
        preflight.get("ok") is True
        and preflight.get("deploy_status") == "local_ready_but_deploy_blocked"
        and preflight.get("nl_write_allowed") is False
    )
    safety_flags_block_writes = (
        summary.get("nl_write_allowed") is False
        and summary.get("automatic_failover_allowed") is False
        and summary.get("spb_fallback_allowed") is False
    )
    ready = (
        manifest.get("status") == "planning_only"
        and manifest.get("nl_write_allowed") is False
        and safety_flags_block_writes
        and preflight_ok
    )
    return requirement(
        item_id="NL-GATE-01",
        title="NL actions stay read-only by default and approval-gated",
        status=PASS if ready else MISSING,
        evidence=[
            f"manifest_status={manifest.get('status') or 'missing'}",
            f"manifest_nl_write_allowed={bool_text(manifest.get('nl_write_allowed'))}",
            f"readiness_ok={bool_text(readiness.get('ok'))}",
            f"readiness_nl_write_allowed={bool_text(summary.get('nl_write_allowed'))}",
            f"automatic_failover_allowed={bool_text(summary.get('automatic_failover_allowed'))}",
            f"spb_fallback_allowed={bool_text(summary.get('spb_fallback_allowed'))}",
            f"safety_flags_block_writes={bool_text(safety_flags_block_writes)}",
            f"preflight_ok={bool_text(preflight.get('ok'))}",
            f"preflight_deploy_status={preflight.get('deploy_status') or 'missing'}",
            f"preflight_check_count={len(preflight.get('checks') or [])}",
        ],
        next_step="keep NL writes blocked until a separate explicit operator approval phrase exists",
    )


def audit_evidence_claims_privacy(payloads: dict[str, dict[str, Any]]) -> dict[str, Any]:
    findings: list[str] = []
    for name, payload in payloads.items():
        findings.extend(f"{name}:{finding}" for finding in collect_privacy_findings(payload))

    matrix = payloads.get("client_matrix", {})
    anti_block = payloads.get("anti_block_audit", {})
    not_overclaiming = (
        client_matrix_complete(matrix)
        or anti_block.get("decision") == "PRODUCTION_CANDIDATE_GOAL_NOT_MARKED_COMPLETE"
    )
    ready = not findings and not_overclaiming
    return requirement(
        item_id="CLAIMS-EVIDENCE-01",
        title="Production/customer claims stay evidence-backed and secret-free",
        status=PASS if ready else MISSING,
        evidence=[
            f"privacy_findings={len(findings)}",
            f"not_overclaiming_production_candidate={bool_text(not_overclaiming)}",
            f"anti_block_audit_decision={anti_block.get('decision') or 'missing'}",
            f"client_matrix_complete={bool_text(client_matrix_complete(matrix))}",
        ],
        next_step=(
            "fix privacy findings before publishing readiness claims"
            if findings
            else "publish only the generated evidence summaries, never raw client secrets"
        ),
    )


def audit_firstparty_vpn_core(firstparty: dict[str, Any] | None = None) -> dict[str, Any]:
    """Report whether the new in-repo VPN core is present and source-audited.

    This check is local-only. It does not connect to NL, does not restart
    services, and does not claim production rollout readiness.
    """

    firstparty = firstparty or {}
    root = Path(str(firstparty.get("source_root") or DEFAULT_FIRSTPARTY_ROOT))
    contract = Path(str(firstparty.get("contract") or DEFAULT_FIRSTPARTY_CONTRACT))
    test_node = Path(str(firstparty.get("test_node") or DEFAULT_FIRSTPARTY_TEST_NODE))
    unit_test = Path(str(firstparty.get("unit_test") or DEFAULT_FIRSTPARTY_UNIT_TEST))
    required_files = [
        root / "__init__.py",
        root / "protocol.py",
        root / "crypto.py",
        root / "handshake.py",
        root / "mlkem.py",
        root / "mldsa.py",
        root / "runtime.py",
        root / "stream.py",
        root / "tun.py",
        root / "service.py",
        root / "source_audit.py",
        root / "production_readiness.py",
    ]
    required_present = all(path.exists() for path in required_files)
    source_audit_error = ""
    source_audit_passed = False
    source_audit_scanned_files = 0
    source_audit_reasons: list[str] = []
    source_audit_root_hash = "missing"
    source_audit_tree_hash = "missing"

    if firstparty.get("source_audit_precomputed") is True:
        source_audit_passed = firstparty.get("source_audit_passed") is True
        source_audit_scanned_files = int(firstparty.get("source_audit_scanned_files") or 0)
        source_audit_reasons = [str(value) for value in firstparty.get("source_audit_reasons") or []]
        source_audit_root_hash = str(firstparty.get("source_audit_root_hash") or "precomputed")
        source_audit_tree_hash = str(firstparty.get("source_audit_tree_hash") or "precomputed")
    elif root.exists():
        try:
            if str(ROOT) not in sys.path:
                sys.path.insert(0, str(ROOT))
            from src.network.firstparty_vpn.source_audit import audit_firstparty_source_tree

            audit = audit_firstparty_source_tree(root)
            source_audit_passed = audit.passed
            source_audit_scanned_files = audit.scanned_files
            source_audit_reasons = list(audit.reasons)
            source_audit_root_hash = audit.root_hash
            source_audit_tree_hash = audit.source_tree_hash
        except Exception as exc:  # pragma: no cover - defensive evidence path
            source_audit_error = f"{type(exc).__name__}: {exc}"

    wire_magic_present = False
    protocol_path = root / "protocol.py"
    if protocol_path.exists():
        try:
            wire_magic_present = "X0VPN001" in protocol_path.read_text(encoding="utf-8")
        except OSError:
            wire_magic_present = False

    ready = (
        root.is_dir()
        and contract.exists()
        and test_node.exists()
        and unit_test.exists()
        and required_present
        and wire_magic_present
        and source_audit_passed
        and source_audit_scanned_files >= len(required_files)
    )
    return requirement(
        item_id="FIRSTPARTY-CORE-01",
        title="New first-party VPN core is present and no-foreign-backend source-audited",
        status=READY_TO_STAGE if ready else MISSING,
        evidence=[
            f"source_root_exists={bool_text(root.is_dir())}",
            f"contract_exists={bool_text(contract.exists())}",
            f"test_node_exists={bool_text(test_node.exists())}",
            f"unit_test_exists={bool_text(unit_test.exists())}",
            f"required_core_files_present={bool_text(required_present)}",
            f"wire_magic_x0vpn001_present={bool_text(wire_magic_present)}",
            f"source_audit_passed={bool_text(source_audit_passed)}",
            f"source_audit_scanned_files={source_audit_scanned_files}",
            f"source_audit_reasons={compact_list(source_audit_reasons)}",
            f"source_audit_root_hash={source_audit_root_hash}",
            f"source_audit_tree_hash={source_audit_tree_hash}",
            f"source_audit_error={source_audit_error or 'none'}",
        ],
        next_step=(
            "collect live first-party canary, TUN dataplane, leak-protection, MTU, and production-readiness evidence"
            if ready
            else "restore the first-party VPN core files and rerun source audit before any rollout claim"
        ),
    )


def audit_firstparty_live_canary(canary: dict[str, Any] | None = None) -> dict[str, Any]:
    """Report whether the local first-party dataplane canary passed.

    This check proves the loopback server/client path only. It is intentionally
    not a claim that NL production traffic has been moved to the new VPN.
    """

    canary = canary or {}
    checks = canary.get("checks") if isinstance(canary.get("checks"), dict) else {}
    return_codes = (
        canary.get("return_codes") if isinstance(canary.get("return_codes"), dict) else {}
    )
    required_checks = {
        "generate_ok",
        "server_ok",
        "probe_ok",
        "admission_ok",
        "dataplane_readiness_ok",
        "dataplane_validation_passed",
        "tun_dataplane_validation_passed",
        "mtu_validation_passed",
        "source_audit_ok",
        "source_audit_allowed",
    }
    checks_passed = all(checks.get(name) is True for name in required_checks)
    return_codes_ok = bool(return_codes) and all(value == 0 for value in return_codes.values())
    bind_addr = canary.get("server_bind_addr")
    bind_host = bind_addr[0] if isinstance(bind_addr, list) and bind_addr else None
    local_only = (
        canary.get("host") == "127.0.0.1"
        and bind_host == "127.0.0.1"
        and canary.get("os_mutation_performed") is False
        and canary.get("nl_vpn_services_touched") is False
    )
    ready = canary.get("ok") is True and checks_passed and return_codes_ok and local_only
    failed_checks = sorted(name for name in required_checks if checks.get(name) is not True)
    return requirement(
        item_id="FIRSTPARTY-CANARY-01",
        title="Local first-party VPN canary passes protected DATA, admission, TUN dataplane, MTU, and source audit",
        status=PASS if ready else MISSING,
        evidence=[
            f"summary_path={canary.get('summary_path') or canary.get('evidence_dir') or 'missing'}",
            f"canary_ok={bool_text(canary.get('ok'))}",
            f"transport={canary.get('transport') or 'missing'}",
            f"deployment_epoch={canary.get('deployment_epoch') or 'missing'}",
            f"host={canary.get('host') or 'missing'}",
            f"server_bind_host={bind_host or 'missing'}",
            f"local_only={bool_text(local_only)}",
            f"checks_passed={bool_text(checks_passed)}",
            f"failed_checks={compact_list(failed_checks)}",
            f"return_codes_ok={bool_text(return_codes_ok)}",
            f"dataplane_failed_reasons={compact_list(canary.get('dataplane_failed_reasons'))}",
            f"tun_dataplane_failed_reasons={compact_list(canary.get('tun_dataplane_failed_reasons'))}",
            f"mtu_failed_reasons={compact_list(canary.get('mtu_failed_reasons'))}",
            f"source_tree_hash={canary.get('source_tree_hash') or 'missing'}",
            f"scanned_files={canary.get('scanned_files') or 'missing'}",
        ],
        next_step=(
            "collect leak-protection, linux preflight, and production-readiness evidence for a staged first-party deployment"
            if ready
            else "rerun the local first-party live canary and fix any failed protected DATA/TUN/MTU/source-audit check"
        ),
    )


def audit_firstparty_production_readiness(
    readiness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Report whether the local first-party production-readiness bundle passed."""

    readiness = readiness or {}
    checks = readiness.get("checks") if isinstance(readiness.get("checks"), dict) else {}
    collected = (
        readiness.get("collected") if isinstance(readiness.get("collected"), dict) else {}
    )
    return_codes = (
        readiness.get("return_codes")
        if isinstance(readiness.get("return_codes"), dict)
        else {}
    )
    required_checks = {
        "generate_ok",
        "server_ok",
        "pqc_promote_server_ok",
        "pqc_promote_client_ok",
        "policy_snapshot_ok",
        "production_readiness_ok",
        "pqc_provider_gate_allowed",
        "linux_preflight_collected",
        "leak_protection_collected",
        "dataplane_collected",
        "pqc_collected",
        "identity_signer_collected",
        "zero_trust_policy_collected",
        "external_policy_source_collected",
        "rekey_policy_collected",
        "rollout_gate_collected",
        "source_audit_collected",
        "os_mutation_performed_false",
    }
    required_collected = {
        "dataplane",
        "external_policy_source",
        "identity_signer",
        "leak_protection",
        "linux_preflight",
        "pqc",
        "rekey_policy",
        "rollout_gate",
        "source_audit",
        "zero_trust_policy",
    }
    checks_passed = all(checks.get(name) is True for name in required_checks)
    collected_passed = all(collected.get(name) is True for name in required_collected)
    return_codes_ok = bool(return_codes) and all(value == 0 for value in return_codes.values())
    bind_addr = readiness.get("server_bind_addr")
    bind_host = bind_addr[0] if isinstance(bind_addr, list) and bind_addr else None
    local_only = bind_host == "127.0.0.1"
    ready = (
        readiness.get("ok") is True
        and readiness.get("decision_allowed") is True
        and checks_passed
        and collected_passed
        and return_codes_ok
        and local_only
        and readiness.get("os_mutation_performed") is False
        and readiness.get("no_nl_or_spb_writes_performed") is True
    )
    failed_checks = sorted(name for name in required_checks if checks.get(name) is not True)
    missing_collected = sorted(
        name for name in required_collected if collected.get(name) is not True
    )
    return requirement(
        item_id="FIRSTPARTY-PROD-READY-01",
        title="Local first-party production-readiness bundle passes all staged gates without OS or NL/SPB writes",
        status=READY_TO_STAGE if ready else MISSING,
        evidence=[
            f"summary_path={readiness.get('summary_path') or readiness.get('evidence_dir') or 'missing'}",
            f"readiness_ok={bool_text(readiness.get('ok'))}",
            f"decision_allowed={bool_text(readiness.get('decision_allowed'))}",
            f"decision_reasons={compact_list(readiness.get('decision_reasons'))}",
            f"deployment_epoch={readiness.get('deployment_epoch') or 'missing'}",
            f"transport={readiness.get('transport') or 'missing'}",
            f"server_bind_host={bind_host or 'missing'}",
            f"local_only={bool_text(local_only)}",
            f"checks_passed={bool_text(checks_passed)}",
            f"failed_checks={compact_list(failed_checks)}",
            f"collected_passed={bool_text(collected_passed)}",
            f"missing_collected={compact_list(missing_collected)}",
            f"return_codes_ok={bool_text(return_codes_ok)}",
            f"pqc_runtime_metadata_matches_manifest={bool_text(readiness.get('pqc_runtime_metadata_matches_manifest'))}",
            f"pqc_provider_gate_reasons={compact_list(readiness.get('pqc_provider_gate_reasons'))}",
            f"source_tree_hash={readiness.get('source_tree_hash') or 'missing'}",
            f"os_mutation_performed={bool_text(readiness.get('os_mutation_performed'))}",
            f"no_nl_or_spb_writes_performed={bool_text(readiness.get('no_nl_or_spb_writes_performed'))}",
        ],
        next_step=(
            "prepare a guarded staging deploy packet; do not touch NL production until explicit approval and fresh read-only evidence exist"
            if ready
            else "rerun local first-party production-readiness after fixing missing PQC/dataplane/leak-prevention/preflight evidence"
        ),
    )


def audit_firstparty_staging_packet(staging: dict[str, Any] | None = None) -> dict[str, Any]:
    """Report whether the guarded first-party staging packet exists and verifies."""

    staging = staging or {}
    checks = staging.get("checks") if isinstance(staging.get("checks"), dict) else {}
    required_checks = {
        "generate_ok",
        "server_ok",
        "server_service_plan_ok",
        "client_service_plan_ok",
        "apply_server_dry_run_ok",
        "apply_client_dry_run_ok",
        "export_client_kits_ok",
        "verify_client_kits_ok",
        "export_server_secrets_excluded",
        "verify_signature_required",
        "verify_archives_checked",
        "client_kit_count_matches",
        "client_readiness_required",
        "all_verified_kits_ok",
        "all_verified_archives_present",
        "all_verified_signatures_present",
        "all_verified_readiness_ok",
        "all_verified_server_secrets_excluded",
        "no_os_mutation",
    }
    checks_passed = all(checks.get(name) is True for name in required_checks)
    bind_addr = staging.get("server_bind_addr")
    bind_host = bind_addr[0] if isinstance(bind_addr, list) and bind_addr else None
    local_only = bind_host == "127.0.0.1"
    client_kit_count = staging.get("client_kit_count")
    verified_kit_count = staging.get("verified_kit_count")
    kit_counts_ok = (
        isinstance(client_kit_count, int)
        and isinstance(verified_kit_count, int)
        and client_kit_count >= 1
        and client_kit_count == verified_kit_count
    )
    no_secrets = (
        staging.get("server_secrets_included") is False
        and staging.get("raw_secret_material_stored_in_evidence") is False
        and staging.get("kit_material_persisted_in_repo") is False
    )
    target_paths_ok = all(
        isinstance(staging.get(key), str) and str(staging.get(key)).startswith(prefix)
        for key, prefix in (
            ("server_unit_path", "/etc/systemd/system/"),
            ("client_unit_path", "/etc/systemd/system/"),
            ("server_config_target", "/etc/"),
            ("client_config_target", "/etc/"),
        )
    )
    ready = (
        staging.get("ok") is True
        and checks_passed
        and local_only
        and kit_counts_ok
        and no_secrets
        and target_paths_ok
        and staging.get("os_mutation_performed") is False
        and staging.get("no_nl_or_spb_writes_performed") is True
    )
    failed_checks = sorted(name for name in required_checks if checks.get(name) is not True)
    return requirement(
        item_id="FIRSTPARTY-STAGING-PACKET-01",
        title="First-party staging packet has service plans, dry-run config apply, signed client kits, and live readiness",
        status=READY_TO_STAGE if ready else MISSING,
        evidence=[
            f"summary_path={staging.get('summary_path') or staging.get('evidence_dir') or 'missing'}",
            f"staging_ok={bool_text(staging.get('ok'))}",
            f"deployment_epoch={staging.get('deployment_epoch') or 'missing'}",
            f"transport={staging.get('transport') or 'missing'}",
            f"server_bind_host={bind_host or 'missing'}",
            f"local_only={bool_text(local_only)}",
            f"server_service_name={staging.get('server_service_name') or 'missing'}",
            f"client_service_name={staging.get('client_service_name') or 'missing'}",
            f"target_paths_ok={bool_text(target_paths_ok)}",
            f"client_kit_count={client_kit_count if client_kit_count is not None else 'missing'}",
            f"verified_kit_count={verified_kit_count if verified_kit_count is not None else 'missing'}",
            f"kit_counts_ok={bool_text(kit_counts_ok)}",
            f"readiness_required={bool_text(staging.get('readiness_required'))}",
            f"archive_checked={bool_text(staging.get('archive_checked'))}",
            f"signature_required={bool_text(staging.get('signature_required'))}",
            f"server_secrets_included={bool_text(staging.get('server_secrets_included'))}",
            f"raw_secret_material_stored_in_evidence={bool_text(staging.get('raw_secret_material_stored_in_evidence'))}",
            f"kit_material_persisted_in_repo={bool_text(staging.get('kit_material_persisted_in_repo'))}",
            f"checks_passed={bool_text(checks_passed)}",
            f"failed_checks={compact_list(failed_checks)}",
            f"os_mutation_performed={bool_text(staging.get('os_mutation_performed'))}",
            f"no_nl_or_spb_writes_performed={bool_text(staging.get('no_nl_or_spb_writes_performed'))}",
        ],
        next_step=(
            "wait for explicit production approval and fresh read-only NL evidence before any real service install"
            if ready
            else "rebuild first-party staging packet; service plans, dry-run apply, signed kits, and live readiness must all pass"
        ),
    )


def audit_firstparty_rollout_packet(rollout: dict[str, Any] | None = None) -> dict[str, Any]:
    """Report whether the guarded first-party production rollout packet is ready."""

    rollout = rollout or {}
    checks = rollout.get("checks") if isinstance(rollout.get("checks"), dict) else {}
    required_checks = {
        "staging_ok",
        "production_readiness_ok",
        "canary_ok",
        "server_service_plan_ok",
        "client_service_plan_ok",
        "server_unit_starts_firstparty_server_tun",
        "client_unit_starts_firstparty_client_tun",
        "client_unit_has_rollback_exec_stop",
        "server_apply_dry_run_ok",
        "client_apply_dry_run_ok",
        "server_config_hash_matches_staging",
        "client_config_hash_matches_staging",
        "client_kits_verified",
        "client_kits_exported_without_server_secrets",
        "no_raw_secret_material_in_evidence",
        "kit_material_not_persisted_in_repo",
        "legacy_protocol_markers_absent",
        "approval_required",
        "production_mutation_blocked",
        "os_mutation_not_performed",
        "no_nl_or_spb_writes_performed",
    }
    checks_passed = all(checks.get(name) is True for name in required_checks)
    failed_checks = sorted(name for name in required_checks if checks.get(name) is not True)
    approval_phrase = str(rollout.get("approval_phrase_required") or "")
    approval_guarded = (
        approval_phrase == "APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT"
        and rollout.get("approval_present") is False
        and rollout.get("production_mutation_allowed") is False
    )
    no_mutation = (
        rollout.get("os_mutation_performed") is False
        and rollout.get("no_nl_or_spb_writes_performed") is True
    )
    kit_counts_ok = (
        isinstance(rollout.get("client_kit_count"), int)
        and isinstance(rollout.get("verified_kit_count"), int)
        and rollout.get("client_kit_count") >= 1
        and rollout.get("client_kit_count") == rollout.get("verified_kit_count")
    )
    ready = (
        rollout.get("ok") is True
        and checks_passed
        and approval_guarded
        and no_mutation
        and kit_counts_ok
    )
    return requirement(
        item_id="FIRSTPARTY-ROLLOUT-PACKET-01",
        title="First-party production rollout packet is approval-gated, rollback-ready, signed, and legacy-free",
        status=READY_TO_STAGE if ready else MISSING,
        evidence=[
            f"summary_path={rollout.get('summary_path') or rollout.get('evidence_dir') or 'missing'}",
            f"rollout_ok={bool_text(rollout.get('ok'))}",
            f"deployment_epoch={rollout.get('deployment_epoch') or 'missing'}",
            f"approval_phrase_required={approval_phrase or 'missing'}",
            f"approval_present={bool_text(rollout.get('approval_present'))}",
            f"approval_guarded={bool_text(approval_guarded)}",
            f"production_mutation_allowed={bool_text(rollout.get('production_mutation_allowed'))}",
            f"os_mutation_performed={bool_text(rollout.get('os_mutation_performed'))}",
            f"no_nl_or_spb_writes_performed={bool_text(rollout.get('no_nl_or_spb_writes_performed'))}",
            f"checks_passed={bool_text(checks_passed)}",
            f"failed_checks={compact_list(failed_checks)}",
            f"server_service_name={rollout.get('server_service_name') or 'missing'}",
            f"client_service_name={rollout.get('client_service_name') or 'missing'}",
            f"server_config_target={rollout.get('server_config_target') or 'missing'}",
            f"client_config_target={rollout.get('client_config_target') or 'missing'}",
            f"client_kit_count={rollout.get('client_kit_count') if rollout.get('client_kit_count') is not None else 'missing'}",
            f"verified_kit_count={rollout.get('verified_kit_count') if rollout.get('verified_kit_count') is not None else 'missing'}",
            f"kit_counts_ok={bool_text(kit_counts_ok)}",
            f"legacy_protocol_findings={compact_list(rollout.get('legacy_protocol_findings'))}",
        ],
        next_step=(
            "wait for explicit production approval and fresh read-only NL evidence before applying the rollout packet"
            if ready
            else "rebuild first-party rollout packet; service plans, dry-run apply, rollback, signed kits, and no-legacy checks must pass"
        ),
    )


def audit_firstparty_preapply_readiness(
    preapply: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Report whether first-party production apply is safely pre-gated."""

    preapply = preapply or {}
    checks = preapply.get("checks") if isinstance(preapply.get("checks"), dict) else {}
    source_checks = (
        preapply.get("source_checks")
        if isinstance(preapply.get("source_checks"), dict)
        else {}
    )
    required_checks = {
        "rollout_packet_ok",
        "rollout_packet_mutation_blocked",
        "rollout_packet_no_nl_spb_writes",
        "approval_phrase_expected",
        "approval_not_present",
        "manifest_nl_write_allowed_false",
        "manifest_not_deployable_to_nl",
        "firstparty_service_names_unique",
        "firstparty_service_names_scoped",
        "firstparty_unit_paths_scoped",
        "firstparty_config_targets_scoped",
        "firstparty_server_client_targets_distinct",
        "legacy_service_markers_absent",
        "source_post_apply_validation_ready",
        "preapply_packet_does_not_authorize_mutation",
        "os_mutation_not_performed",
        "no_nl_or_spb_writes_performed",
    }
    required_source_checks = {
        "build_linux_post_apply_validator",
        "executor_requires_post_apply_validation",
        "collect_linux_applied_state_snapshot",
        "evaluate_linux_applied_state",
        "applied_state_checks_tun_routes_dns_nat",
    }
    checks_passed = all(checks.get(name) is True for name in required_checks)
    source_checks_passed = all(
        source_checks.get(name) is True for name in required_source_checks
    )
    failed_checks = sorted(name for name in required_checks if checks.get(name) is not True)
    failed_source_checks = sorted(
        name for name in required_source_checks if source_checks.get(name) is not True
    )
    approval_guarded = (
        preapply.get("approval_phrase_required")
        == "APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT"
        and preapply.get("approval_present") is False
        and preapply.get("production_mutation_allowed") is False
    )
    no_mutation = (
        preapply.get("os_mutation_performed") is False
        and preapply.get("no_nl_or_spb_writes_performed") is True
    )
    ready = (
        preapply.get("ok") is True
        and checks_passed
        and source_checks_passed
        and approval_guarded
        and no_mutation
    )
    return requirement(
        item_id="FIRSTPARTY-PREAPPLY-READY-01",
        title="First-party production apply is blocked until approval and has mandatory post-apply validation",
        status=READY_TO_STAGE if ready else MISSING,
        evidence=[
            f"summary_path={preapply.get('summary_path') or preapply.get('evidence_dir') or 'missing'}",
            f"preapply_ok={bool_text(preapply.get('ok'))}",
            f"deployment_epoch={preapply.get('deployment_epoch') or 'missing'}",
            f"approval_phrase_required={preapply.get('approval_phrase_required') or 'missing'}",
            f"approval_present={bool_text(preapply.get('approval_present'))}",
            f"approval_guarded={bool_text(approval_guarded)}",
            f"production_mutation_allowed={bool_text(preapply.get('production_mutation_allowed'))}",
            f"os_mutation_performed={bool_text(preapply.get('os_mutation_performed'))}",
            f"no_nl_or_spb_writes_performed={bool_text(preapply.get('no_nl_or_spb_writes_performed'))}",
            f"checks_passed={bool_text(checks_passed)}",
            f"failed_checks={compact_list(failed_checks)}",
            f"source_checks_passed={bool_text(source_checks_passed)}",
            f"failed_source_checks={compact_list(failed_source_checks)}",
            f"server_service_name={preapply.get('server_service_name') or 'missing'}",
            f"client_service_name={preapply.get('client_service_name') or 'missing'}",
            f"legacy_service_findings={compact_list(preapply.get('legacy_service_findings'))}",
        ],
        next_step=(
            "collect fresh read-only NL host evidence, then require explicit approval before any production apply"
            if ready
            else "rebuild first-party pre-apply readiness; approval, scoped services, manifest gate, and post-apply validator must all pass"
        ),
    )


def audit_firstparty_production_endpoint(
    endpoint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Report whether a non-loopback first-party production endpoint is ready."""

    endpoint = endpoint or {}
    checks = endpoint.get("checks") if isinstance(endpoint.get("checks"), dict) else {}
    required_checks = {
        "generate_ok",
        "server_service_plan_ok",
        "client_service_plan_ok",
        "endpoint_host_public",
        "server_bind_not_loopback",
        "generated_server_bind_matches",
        "generated_client_host_matches",
        "generated_port_matches",
        "generated_transport_matches",
        "candidate_port_in_range",
        "candidate_port_not_legacy_known",
        "candidate_port_free_on_nl_snapshot",
        "service_units_firstparty_only",
        "temp_config_dir_removed",
        "raw_secret_material_not_stored_in_evidence",
        "os_mutation_not_performed",
        "no_nl_or_spb_writes_performed",
    }
    checks_passed = all(checks.get(name) is True for name in required_checks)
    failed_checks = sorted(name for name in required_checks if checks.get(name) is not True)
    host = str(endpoint.get("host") or "")
    bind_host = str(endpoint.get("bind_host") or "")
    port = endpoint.get("port")
    external_shape_ok = (
        bool(host)
        and host not in {"127.0.0.1", "localhost", "0.0.0.0"}
        and bind_host not in {"127.0.0.1", "localhost"}
        and isinstance(port, int)
        and port > 0
    )
    no_mutation = (
        endpoint.get("os_mutation_performed") is False
        and endpoint.get("no_nl_or_spb_writes_performed") is True
        and endpoint.get("raw_secret_material_stored_in_evidence") is False
    )
    ready = endpoint.get("ok") is True and checks_passed and external_shape_ok and no_mutation
    return requirement(
        item_id="FIRSTPARTY-PRODUCTION-ENDPOINT-01",
        title="First-party production endpoint is external, free on NL, and independent of legacy listeners",
        status=READY_TO_STAGE if ready else MISSING,
        evidence=[
            f"summary_path={endpoint.get('summary_path') or endpoint.get('evidence_dir') or 'missing'}",
            f"endpoint_ok={bool_text(endpoint.get('ok'))}",
            f"host={host or 'missing'}",
            f"bind_host={bind_host or 'missing'}",
            f"port={port if port is not None else 'missing'}",
            f"transport={endpoint.get('transport') or 'missing'}",
            f"deployment_epoch={endpoint.get('deployment_epoch') or 'missing'}",
            f"external_shape_ok={bool_text(external_shape_ok)}",
            f"checks_passed={bool_text(checks_passed)}",
            f"failed_checks={compact_list(failed_checks)}",
            f"server_service_name={endpoint.get('server_service_name') or 'missing'}",
            f"client_service_name={endpoint.get('client_service_name') or 'missing'}",
            f"candidate_port_free_on_nl_snapshot={bool_text(checks.get('candidate_port_free_on_nl_snapshot'))}",
            f"occupied_port_count={endpoint.get('occupied_port_count') if endpoint.get('occupied_port_count') is not None else 'missing'}",
            f"legacy_unit_findings={compact_list(endpoint.get('legacy_unit_findings'))}",
            f"no_mutation={bool_text(no_mutation)}",
        ],
        next_step=(
            "bind rollout/pre-apply packet to this external endpoint before production apply"
            if ready
            else "rebuild production endpoint packet with non-loopback bind, public host, free NL port, and first-party-only units"
        ),
    )


def audit_firstparty_production_apply_packet(
    apply_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Report whether production apply dry-run is bound to the external endpoint."""

    apply_packet = apply_packet or {}
    checks = (
        apply_packet.get("checks")
        if isinstance(apply_packet.get("checks"), dict)
        else {}
    )
    required_checks = {
        "endpoint_summary_ok",
        "endpoint_host_public",
        "endpoint_bind_not_loopback",
        "endpoint_port_free_on_nl_snapshot",
        "endpoint_no_mutation",
        "generate_ok",
        "generated_server_bind_matches_endpoint",
        "generated_client_host_matches_endpoint",
        "generated_port_matches_endpoint",
        "generated_transport_matches_endpoint",
        "server_service_plan_ok",
        "client_service_plan_ok",
        "server_unit_starts_firstparty_server_tun",
        "client_unit_starts_firstparty_client_tun",
        "client_unit_has_rollback_exec_stop",
        "service_units_firstparty_only",
        "server_apply_dry_run_ok",
        "client_apply_dry_run_ok",
        "server_apply_hash_matches_generated",
        "client_apply_hash_matches_generated",
        "client_kits_exported",
        "client_kits_verified",
        "client_kits_signed",
        "client_kits_without_server_secrets",
        "approval_required",
        "approval_not_present",
        "production_mutation_blocked",
        "post_apply_validation_required",
        "secure_material_handoff_required",
        "temp_config_dir_removed",
        "raw_secret_material_not_stored_in_evidence",
        "kit_material_not_persisted_in_repo",
        "os_mutation_not_performed",
        "no_nl_or_spb_writes_performed",
    }
    checks_passed = all(checks.get(name) is True for name in required_checks)
    failed_checks = sorted(name for name in required_checks if checks.get(name) is not True)
    host = str(apply_packet.get("host") or "")
    bind_host = str(apply_packet.get("bind_host") or "")
    port = apply_packet.get("port")
    external_shape_ok = (
        bool(host)
        and host not in {"127.0.0.1", "localhost", "0.0.0.0"}
        and bind_host not in {"127.0.0.1", "localhost"}
        and isinstance(port, int)
        and port > 0
    )
    approval_guarded = (
        apply_packet.get("approval_phrase_required")
        == "APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT"
        and apply_packet.get("approval_present") is False
        and apply_packet.get("production_mutation_allowed") is False
    )
    no_mutation = (
        apply_packet.get("os_mutation_performed") is False
        and apply_packet.get("no_nl_or_spb_writes_performed") is True
        and apply_packet.get("raw_secret_material_stored_in_evidence") is False
        and apply_packet.get("kit_material_persisted_in_repo") is False
    )
    kit_counts_ok = (
        isinstance(apply_packet.get("client_kit_count"), int)
        and isinstance(apply_packet.get("verified_kit_count"), int)
        and apply_packet.get("client_kit_count") >= 1
        and apply_packet.get("client_kit_count") == apply_packet.get("verified_kit_count")
    )
    ready = (
        apply_packet.get("ok") is True
        and checks_passed
        and external_shape_ok
        and approval_guarded
        and no_mutation
        and kit_counts_ok
        and apply_packet.get("post_apply_validation_required") is True
        and apply_packet.get("secure_material_handoff_required") is True
    )
    return requirement(
        item_id="FIRSTPARTY-PRODUCTION-APPLY-PACKET-01",
        title="First-party production apply packet is external-endpoint-bound, dry-run verified, and approval-blocked",
        status=READY_TO_STAGE if ready else MISSING,
        evidence=[
            f"summary_path={apply_packet.get('summary_path') or apply_packet.get('evidence_dir') or 'missing'}",
            f"apply_packet_ok={bool_text(apply_packet.get('ok'))}",
            f"host={host or 'missing'}",
            f"bind_host={bind_host or 'missing'}",
            f"port={port if port is not None else 'missing'}",
            f"transport={apply_packet.get('transport') or 'missing'}",
            f"deployment_epoch={apply_packet.get('deployment_epoch') or 'missing'}",
            f"endpoint_deployment_epoch={apply_packet.get('endpoint_deployment_epoch') or 'missing'}",
            f"external_shape_ok={bool_text(external_shape_ok)}",
            f"approval_guarded={bool_text(approval_guarded)}",
            f"checks_passed={bool_text(checks_passed)}",
            f"failed_checks={compact_list(failed_checks)}",
            f"server_apply_dry_run_ok={bool_text(checks.get('server_apply_dry_run_ok'))}",
            f"client_apply_dry_run_ok={bool_text(checks.get('client_apply_dry_run_ok'))}",
            f"post_apply_validation_required={bool_text(apply_packet.get('post_apply_validation_required'))}",
            f"secure_material_handoff_required={bool_text(apply_packet.get('secure_material_handoff_required'))}",
            f"server_service_name={apply_packet.get('server_service_name') or 'missing'}",
            f"client_service_name={apply_packet.get('client_service_name') or 'missing'}",
            f"client_kit_count={apply_packet.get('client_kit_count') if apply_packet.get('client_kit_count') is not None else 'missing'}",
            f"verified_kit_count={apply_packet.get('verified_kit_count') if apply_packet.get('verified_kit_count') is not None else 'missing'}",
            f"kit_counts_ok={bool_text(kit_counts_ok)}",
            f"legacy_protocol_findings={compact_list(apply_packet.get('legacy_protocol_findings'))}",
            f"no_mutation={bool_text(no_mutation)}",
        ],
        next_step=(
            "requires explicit APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT plus secure non-repo material handoff before any real NL apply"
            if ready
            else "rebuild production apply packet from the external endpoint; dry-run apply, signed kits, approval block, and secret-free evidence must pass"
        ),
    )


def audit_firstparty_secure_material_handoff(
    handoff: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Report whether private production material is staged outside git."""

    handoff = handoff or {}
    checks = handoff.get("checks") if isinstance(handoff.get("checks"), dict) else {}
    required_checks = {
        "apply_packet_ok",
        "apply_packet_approval_blocked",
        "apply_packet_external_endpoint",
        "apply_packet_requires_secure_handoff",
        "handoff_dir_outside_repo",
        "handoff_archive_outside_repo",
        "handoff_dir_private",
        "handoff_archive_private",
        "private_files_mode_ok",
        "source_tree_included",
        "source_tree_hash_matches_current",
        "generate_ok",
        "server_service_plan_ok",
        "client_service_plan_ok",
        "server_apply_dry_run_ok",
        "client_apply_dry_run_ok",
        "generated_server_bind_matches_apply_packet",
        "generated_client_host_matches_apply_packet",
        "generated_port_matches_apply_packet",
        "generated_transport_matches_apply_packet",
        "client_kits_exported",
        "client_kits_verified",
        "client_kits_signed",
        "client_kits_without_server_secrets",
        "legacy_protocol_markers_absent",
        "manifest_secret_free",
        "raw_secret_material_not_stored_in_evidence",
        "repo_material_not_persisted",
        "os_mutation_not_performed",
        "no_nl_or_spb_writes_performed",
    }
    checks_passed = all(checks.get(name) is True for name in required_checks)
    failed_checks = sorted(name for name in required_checks if checks.get(name) is not True)
    approval_guarded = (
        handoff.get("approval_phrase_required")
        == "APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT"
        and handoff.get("approval_present") is False
        and handoff.get("production_mutation_allowed") is False
    )
    no_mutation = (
        handoff.get("os_mutation_performed") is False
        and handoff.get("no_nl_or_spb_writes_performed") is True
        and handoff.get("raw_secret_material_stored_in_evidence") is False
        and handoff.get("repo_material_persisted") is False
    )
    kit_counts_ok = (
        isinstance(handoff.get("client_kit_count"), int)
        and isinstance(handoff.get("verified_kit_count"), int)
        and handoff.get("client_kit_count") >= 1
        and handoff.get("client_kit_count") == handoff.get("verified_kit_count")
    )
    private_handoff_ready = (
        isinstance(handoff.get("handoff_dir"), str)
        and str(handoff.get("handoff_dir")).startswith("/")
        and handoff.get("handoff_dir_mode") == "0700"
        and handoff.get("handoff_archive_mode") == "0600"
        and isinstance(handoff.get("archive_sha256"), str)
        and len(str(handoff.get("archive_sha256"))) == 64
    )
    ready = (
        handoff.get("ok") is True
        and checks_passed
        and approval_guarded
        and no_mutation
        and kit_counts_ok
        and private_handoff_ready
    )
    return requirement(
        item_id="FIRSTPARTY-SECURE-MATERIAL-HANDOFF-01",
        title="First-party private production material is staged outside repo with secret-free evidence",
        status=READY_TO_STAGE if ready else MISSING,
        evidence=[
            f"summary_path={handoff.get('summary_path') or handoff.get('evidence_dir') or 'missing'}",
            f"handoff_ok={bool_text(handoff.get('ok'))}",
            f"host={handoff.get('host') or 'missing'}",
            f"bind_host={handoff.get('bind_host') or 'missing'}",
            f"port={handoff.get('port') if handoff.get('port') is not None else 'missing'}",
            f"transport={handoff.get('transport') or 'missing'}",
            f"deployment_epoch={handoff.get('deployment_epoch') or 'missing'}",
            f"approval_guarded={bool_text(approval_guarded)}",
            f"checks_passed={bool_text(checks_passed)}",
            f"failed_checks={compact_list(failed_checks)}",
            f"handoff_dir={handoff.get('handoff_dir') or 'missing'}",
            f"handoff_archive={handoff.get('handoff_archive') or 'missing'}",
            f"handoff_dir_mode={handoff.get('handoff_dir_mode') or 'missing'}",
            f"handoff_archive_mode={handoff.get('handoff_archive_mode') or 'missing'}",
            f"archive_sha256={handoff.get('archive_sha256') or 'missing'}",
            f"manifest_sha256={handoff.get('manifest_sha256') or 'missing'}",
            f"source_tree_hash={handoff.get('source_tree_hash') or 'missing'}",
            f"client_kit_count={handoff.get('client_kit_count') if handoff.get('client_kit_count') is not None else 'missing'}",
            f"verified_kit_count={handoff.get('verified_kit_count') if handoff.get('verified_kit_count') is not None else 'missing'}",
            f"kit_counts_ok={bool_text(kit_counts_ok)}",
            f"legacy_protocol_findings={compact_list(handoff.get('legacy_protocol_findings'))}",
            f"private_handoff_ready={bool_text(private_handoff_ready)}",
            f"no_mutation={bool_text(no_mutation)}",
        ],
        next_step=(
            "requires explicit APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT before copying the handoff to NL and applying it"
            if ready
            else "rebuild secure handoff outside repo; private modes, signed kits, source tree, dry-run apply, and secret-free evidence must pass"
        ),
    )


def audit_firstparty_production_authorization(
    authorization: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Report whether final pre-approval production apply evidence is bound."""

    authorization = authorization or {}
    checks = (
        authorization.get("checks")
        if isinstance(authorization.get("checks"), dict)
        else {}
    )
    required_checks = {
        "endpoint_summary_ok",
        "apply_packet_ok",
        "secure_handoff_ok",
        "rollout_packet_ok",
        "preapply_readiness_ok",
        "endpoint_fields_match_apply_and_handoff",
        "approval_blocked_apply_packet",
        "approval_blocked_handoff",
        "approval_blocked_rollout",
        "approval_blocked_preapply",
        "mutation_blocked_all_packets",
        "post_apply_validation_required",
        "secure_material_handoff_required",
        "handoff_dir_exists",
        "handoff_archive_exists",
        "handoff_manifest_exists",
        "handoff_dir_outside_repo",
        "handoff_archive_outside_repo",
        "handoff_manifest_outside_repo",
        "handoff_dir_private",
        "handoff_archive_private",
        "handoff_manifest_private",
        "handoff_archive_hash_matches_summary",
        "handoff_manifest_hash_matches_summary",
        "handoff_summary_secret_free",
        "all_evidence_fresh",
        "manual_approval_still_required",
        "os_mutation_not_performed",
        "no_nl_or_spb_writes_performed",
    }
    checks_passed = all(checks.get(name) is True for name in required_checks)
    failed_checks = sorted(name for name in required_checks if checks.get(name) is not True)
    endpoint = (
        authorization.get("endpoint")
        if isinstance(authorization.get("endpoint"), dict)
        else {}
    )
    evidence_paths = (
        authorization.get("evidence_paths")
        if isinstance(authorization.get("evidence_paths"), dict)
        else {}
    )
    evidence_hashes = (
        authorization.get("evidence_hashes")
        if isinstance(authorization.get("evidence_hashes"), dict)
        else {}
    )
    approval_guarded = (
        authorization.get("approval_phrase_required")
        == "APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT"
        and authorization.get("approval_present") is False
        and authorization.get("production_mutation_allowed") is False
        and authorization.get("manual_approval_still_required") is True
    )
    no_mutation = (
        authorization.get("os_mutation_performed") is False
        and authorization.get("no_nl_or_spb_writes_performed") is True
    )
    hashes_present = all(
        isinstance(evidence_hashes.get(name), str)
        and len(str(evidence_hashes.get(name))) == 64
        for name in (
            "endpoint_summary_sha256",
            "apply_packet_summary_sha256",
            "handoff_summary_sha256",
            "rollout_summary_sha256",
            "preapply_summary_sha256",
            "handoff_archive_sha256",
            "handoff_manifest_sha256",
        )
    )
    ready = (
        authorization.get("ok") is True
        and checks_passed
        and approval_guarded
        and no_mutation
        and hashes_present
    )
    return requirement(
        item_id="FIRSTPARTY-PRODUCTION-AUTHZ-01",
        title="First-party production apply materials are bound and still approval-blocked",
        status=READY_TO_STAGE if ready else MISSING,
        evidence=[
            f"summary_path={authorization.get('summary_path') or authorization.get('evidence_dir') or 'missing'}",
            f"authorization_ok={bool_text(authorization.get('ok'))}",
            f"host={endpoint.get('host') or 'missing'}",
            f"bind_host={endpoint.get('bind_host') or 'missing'}",
            f"port={endpoint.get('port') if endpoint.get('port') is not None else 'missing'}",
            f"transport={endpoint.get('transport') or 'missing'}",
            f"approval_guarded={bool_text(approval_guarded)}",
            f"checks_passed={bool_text(checks_passed)}",
            f"failed_checks={compact_list(failed_checks)}",
            f"all_evidence_fresh={bool_text(checks.get('all_evidence_fresh'))}",
            f"endpoint_fields_match_apply_and_handoff={bool_text(checks.get('endpoint_fields_match_apply_and_handoff'))}",
            f"handoff_dir={evidence_paths.get('handoff_dir') or 'missing'}",
            f"handoff_archive={evidence_paths.get('handoff_archive') or 'missing'}",
            f"handoff_dir_mode={authorization.get('handoff_dir_mode') or 'missing'}",
            f"handoff_archive_mode={authorization.get('handoff_archive_mode') or 'missing'}",
            f"handoff_manifest_mode={authorization.get('handoff_manifest_mode') or 'missing'}",
            f"handoff_archive_hash_matches_summary={bool_text(checks.get('handoff_archive_hash_matches_summary'))}",
            f"handoff_manifest_hash_matches_summary={bool_text(checks.get('handoff_manifest_hash_matches_summary'))}",
            f"hashes_present={bool_text(hashes_present)}",
            f"manual_approval_still_required={bool_text(authorization.get('manual_approval_still_required'))}",
            f"production_mutation_allowed={bool_text(authorization.get('production_mutation_allowed'))}",
            f"no_mutation={bool_text(no_mutation)}",
        ],
        next_step=(
            "requires explicit APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT before copying material to NL and running post-apply validation"
            if ready
            else "rebuild first-party production authorization packet; endpoint/apply/handoff/rollout/preapply evidence, hashes, freshness, and approval block must pass"
        ),
    )


def audit_firstparty_production_apply_runbook(
    runbook: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Report whether production apply commands are explicit, guarded, and reversible.

    The runbook artifact is evidence only. This audit checks that it contains the
    exact guarded commands an operator would run later; it does not execute them.
    """

    runbook = runbook or {}
    checks = runbook.get("checks") if isinstance(runbook.get("checks"), dict) else {}
    commands = runbook.get("commands") if isinstance(runbook.get("commands"), list) else []
    required_checks = {
        "authorization_ok",
        "authorization_approval_guarded",
        "authorization_no_mutation",
        "authorization_evidence_fresh",
        "apply_packet_ok",
        "apply_packet_hash_bound_to_authorization",
        "handoff_summary_ok",
        "handoff_summary_hash_bound_to_authorization",
        "handoff_archive_exists",
        "handoff_archive_private",
        "handoff_archive_hash_bound_to_authorization",
        "handoff_manifest_exists",
        "handoff_manifest_private",
        "handoff_manifest_hash_bound_to_authorization",
        "handoff_manifest_secret_free",
        "endpoint_external_shape",
        "service_names_firstparty_only",
        "precheck_commands_present",
        "guarded_copy_command_present",
        "guarded_apply_commands_present",
        "post_apply_validation_commands_present",
        "post_apply_evidence_paths_present",
        "post_apply_validation_commands_capture_json",
        "completion_audit_command_present",
        "rollback_commands_present",
        "mutating_commands_have_approval_guard",
        "mutating_x0vpn_commands_have_allow_os_mutation",
        "no_legacy_service_targets_in_commands",
        "server_rollback_scope_firstparty_only",
        "client_rollback_scope_firstparty_only",
        "runbook_does_not_execute_commands",
        "approval_not_present",
        "production_mutation_blocked",
        "os_mutation_not_performed",
        "no_nl_or_spb_writes_performed",
    }
    required_command_ids = {
        "verify_authorization_summary_hash",
        "verify_apply_packet_hash",
        "verify_handoff_summary_hash",
        "verify_handoff_archive_hash_and_mode",
        "verify_handoff_manifest_hash_and_mode",
        "verify_nl_port_still_free_readonly",
        "copy_handoff_to_nl_after_approval",
        "install_server_service_after_approval",
        "server_health_post_apply",
        "apply_client_config_after_approval",
        "client_health_post_apply",
        "client_doctor_post_apply",
        "build_completion_audit_after_post_apply",
        "rollback_client_policy_and_service_after_approval",
        "rollback_server_service_after_approval",
    }
    checks_passed = all(checks.get(name) is True for name in required_checks)
    failed_checks = sorted(name for name in required_checks if checks.get(name) is not True)
    command_ids = {
        str(row.get("id") or "")
        for row in commands
        if isinstance(row, dict)
    }
    required_commands_present = required_command_ids.issubset(command_ids)
    mutating_commands = [
        row for row in commands if isinstance(row, dict) and row.get("mutation") is True
    ]
    command_text = "\n".join(
        str(row.get("command") or "") for row in commands if isinstance(row, dict)
    )
    approval_guarded = (
        runbook.get("approval_phrase_required")
        == "APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT"
        and runbook.get("approval_present") is False
        and runbook.get("production_mutation_allowed") is False
        and runbook.get("manual_approval_still_required") is True
        and "APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT" in command_text
    )
    no_mutation = (
        runbook.get("os_mutation_performed") is False
        and runbook.get("no_nl_or_spb_writes_performed") is True
        and checks.get("runbook_does_not_execute_commands") is True
    )
    service_names = (
        runbook.get("service_names")
        if isinstance(runbook.get("service_names"), dict)
        else {}
    )
    firstparty_services_ok = (
        service_names.get("server") == "x0tta-firstparty-vpn.service"
        and service_names.get("client") == "x0tta-firstparty-vpn-client.service"
    )
    evidence_hashes = (
        runbook.get("evidence_hashes")
        if isinstance(runbook.get("evidence_hashes"), dict)
        else {}
    )
    hashes_present = all(
        isinstance(evidence_hashes.get(name), str)
        and len(str(evidence_hashes.get(name))) == 64
        and str(evidence_hashes.get(name)) != "missing"
        for name in (
            "authorization_summary_sha256",
            "apply_packet_summary_sha256",
            "handoff_summary_sha256",
            "handoff_archive_sha256",
            "handoff_manifest_sha256",
        )
    )
    ready = (
        runbook.get("ok") is True
        and checks_passed
        and required_commands_present
        and bool(mutating_commands)
        and approval_guarded
        and no_mutation
        and firstparty_services_ok
        and hashes_present
        and not runbook.get("legacy_command_findings")
    )
    return requirement(
        item_id="FIRSTPARTY-PRODUCTION-RUNBOOK-01",
        title="First-party production apply runbook is hash-bound, approval-guarded, post-apply validated, rollback-ready, and legacy-free",
        status=READY_TO_STAGE if ready else MISSING,
        evidence=[
            f"summary_path={runbook.get('summary_path') or runbook.get('evidence_dir') or 'missing'}",
            f"runbook_ok={bool_text(runbook.get('ok'))}",
            f"approval_guarded={bool_text(approval_guarded)}",
            f"production_mutation_allowed={bool_text(runbook.get('production_mutation_allowed'))}",
            f"os_mutation_performed={bool_text(runbook.get('os_mutation_performed'))}",
            f"no_nl_or_spb_writes_performed={bool_text(runbook.get('no_nl_or_spb_writes_performed'))}",
            f"checks_passed={bool_text(checks_passed)}",
            f"failed_checks={compact_list(failed_checks)}",
            f"command_count={len(commands)}",
            f"required_commands_present={bool_text(required_commands_present)}",
            f"mutating_command_count={len(mutating_commands)}",
            f"mutating_commands_have_approval_guard={bool_text(checks.get('mutating_commands_have_approval_guard'))}",
            f"mutating_x0vpn_commands_have_allow_os_mutation={bool_text(checks.get('mutating_x0vpn_commands_have_allow_os_mutation'))}",
            f"post_apply_validation_commands_present={bool_text(checks.get('post_apply_validation_commands_present'))}",
            f"post_apply_evidence_paths_present={bool_text(checks.get('post_apply_evidence_paths_present'))}",
            f"post_apply_validation_commands_capture_json={bool_text(checks.get('post_apply_validation_commands_capture_json'))}",
            f"completion_audit_command_present={bool_text(checks.get('completion_audit_command_present'))}",
            f"rollback_commands_present={bool_text(checks.get('rollback_commands_present'))}",
            f"runbook_does_not_execute_commands={bool_text(checks.get('runbook_does_not_execute_commands'))}",
            f"apply_packet_hash_bound_to_authorization={bool_text(checks.get('apply_packet_hash_bound_to_authorization'))}",
            f"handoff_summary_hash_bound_to_authorization={bool_text(checks.get('handoff_summary_hash_bound_to_authorization'))}",
            f"handoff_archive_hash_bound_to_authorization={bool_text(checks.get('handoff_archive_hash_bound_to_authorization'))}",
            f"handoff_manifest_hash_bound_to_authorization={bool_text(checks.get('handoff_manifest_hash_bound_to_authorization'))}",
            f"service_names_firstparty_only={bool_text(checks.get('service_names_firstparty_only'))}",
            f"firstparty_services_ok={bool_text(firstparty_services_ok)}",
            f"hashes_present={bool_text(hashes_present)}",
            f"legacy_command_findings={compact_list(runbook.get('legacy_command_findings'))}",
        ],
        next_step=(
            "requires explicit APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT before executing any runbook mutation command"
            if ready
            else "rebuild first-party production apply runbook; approval guard, rollback, post-apply validation, handoff hashes, and no-legacy command scope must pass"
        ),
    )


def audit_firstparty_production_operator_script(
    operator_script: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Report whether generated operator scripts are guarded and hash-bound."""

    operator_script = operator_script or {}
    checks = (
        operator_script.get("checks")
        if isinstance(operator_script.get("checks"), dict)
        else {}
    )
    script_paths = (
        operator_script.get("script_paths")
        if isinstance(operator_script.get("script_paths"), dict)
        else {}
    )
    script_hashes = (
        operator_script.get("script_file_hashes")
        if isinstance(operator_script.get("script_file_hashes"), dict)
        else {}
    )
    script_modes = (
        operator_script.get("script_file_modes")
        if isinstance(operator_script.get("script_file_modes"), dict)
        else {}
    )
    required_checks = {
        "runbook_summary_ok",
        "runbook_hash_present",
        "runbook_approval_guarded",
        "runbook_no_mutation",
        "required_apply_commands_present",
        "required_rollback_commands_present",
        "apply_script_excludes_rollback",
        "rollback_script_contains_only_rollback",
        "mutating_commands_guarded",
        "commands_syntax_ok",
        "apply_script_syntax_ok",
        "rollback_script_syntax_ok",
        "scripts_default_dry_run",
        "scripts_require_approval_to_execute",
        "scripts_hash_bound_to_runbook",
        "scripts_log_self_hash_meta",
        "no_legacy_commands",
        "operator_builder_does_not_execute_commands",
        "no_nl_or_spb_writes_performed",
        "script_files_written_executable_not_group_world_writable",
        "script_file_hashes_match_preview",
    }
    failed_required_checks = sorted(
        name for name in required_checks if checks.get(name) is not True
    )
    paths_present = all(
        isinstance(script_paths.get(name), str)
        and bool(str(script_paths.get(name)).strip())
        and str(script_paths.get(name)) != "not_written"
        for name in ("apply", "rollback")
    )
    hashes_present = all(
        isinstance(script_hashes.get(name), str)
        and len(str(script_hashes.get(name))) == 64
        and str(script_hashes.get(name)) != "missing"
        for name in ("apply_script_sha256", "rollback_script_sha256")
    )
    def executable_not_group_world_writable(mode: Any) -> bool:
        try:
            value = int(str(mode), 8)
        except ValueError:
            return False
        return bool(value & 0o100) and not bool(value & 0o022)

    modes_not_group_world_writable = (
        executable_not_group_world_writable(script_modes.get("apply"))
        and executable_not_group_world_writable(script_modes.get("rollback"))
    )
    ready = (
        operator_script.get("ok") is True
        and operator_script.get("approval_phrase_required")
        == "APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT"
        and operator_script.get("approval_present") is False
        and operator_script.get("production_mutation_allowed") is False
        and operator_script.get("manual_approval_still_required") is True
        and operator_script.get("os_mutation_performed") is False
        and operator_script.get("no_nl_or_spb_writes_performed") is True
        and not failed_required_checks
        and paths_present
        and hashes_present
        and modes_not_group_world_writable
        and not operator_script.get("legacy_command_findings")
    )
    failed_checks = operator_script.get("failed_checks")
    if not isinstance(failed_checks, list):
        failed_checks = failed_required_checks
    return requirement(
        item_id="FIRSTPARTY-PRODUCTION-OPERATOR-SCRIPT-01",
        title="First-party production apply and rollback operator scripts are dry-run by default, approval-gated, hash-bound, and legacy-free",
        status=READY_TO_STAGE if ready else MISSING,
        evidence=[
            f"summary_path={operator_script.get('summary_path') or operator_script.get('evidence_dir') or 'missing'}",
            f"operator_script_ok={bool_text(operator_script.get('ok'))}",
            f"approval_phrase_required={operator_script.get('approval_phrase_required') or 'missing'}",
            f"production_mutation_allowed={bool_text(operator_script.get('production_mutation_allowed'))}",
            f"os_mutation_performed={bool_text(operator_script.get('os_mutation_performed'))}",
            f"no_nl_or_spb_writes_performed={bool_text(operator_script.get('no_nl_or_spb_writes_performed'))}",
            f"apply_script={script_paths.get('apply') or 'missing'}",
            f"rollback_script={script_paths.get('rollback') or 'missing'}",
            f"runbook_summary_sha256={operator_script.get('runbook_summary_sha256') or 'missing'}",
            f"paths_present={bool_text(paths_present)}",
            f"hashes_present={bool_text(hashes_present)}",
            f"modes_not_group_world_writable={bool_text(modes_not_group_world_writable)}",
            f"scripts_default_dry_run={bool_text(checks.get('scripts_default_dry_run'))}",
            f"scripts_require_approval_to_execute={bool_text(checks.get('scripts_require_approval_to_execute'))}",
            f"scripts_hash_bound_to_runbook={bool_text(checks.get('scripts_hash_bound_to_runbook'))}",
            f"scripts_log_self_hash_meta={bool_text(checks.get('scripts_log_self_hash_meta'))}",
            f"apply_script_excludes_rollback={bool_text(checks.get('apply_script_excludes_rollback'))}",
            f"rollback_script_contains_only_rollback={bool_text(checks.get('rollback_script_contains_only_rollback'))}",
            f"commands_syntax_ok={bool_text(checks.get('commands_syntax_ok'))}",
            f"apply_script_syntax_ok={bool_text(checks.get('apply_script_syntax_ok'))}",
            f"rollback_script_syntax_ok={bool_text(checks.get('rollback_script_syntax_ok'))}",
            f"script_file_hashes_match_preview={bool_text(checks.get('script_file_hashes_match_preview'))}",
            f"legacy_command_findings={compact_list(operator_script.get('legacy_command_findings'))}",
            f"failed_required_checks={compact_list(failed_required_checks)}",
            f"failed_checks={compact_list(failed_checks)}",
        ],
        next_step=(
            "execute generated apply script only after explicit approval phrase, then collect post-apply health JSON"
            if ready
            else "rebuild first-party production operator scripts from the latest guarded runbook; scripts must be dry-run by default, approval-gated, hash-bound, rollback-separated, and legacy-free"
        ),
    )


def audit_firstparty_production_operator_dryrun_audit(
    dryrun: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Report whether generated production operator scripts have a clean dry-run."""

    dryrun = dryrun or {}
    checks = dryrun.get("checks") if isinstance(dryrun.get("checks"), dict) else {}
    transcript_paths = (
        dryrun.get("transcript_paths")
        if isinstance(dryrun.get("transcript_paths"), dict)
        else {}
    )
    dryrun_results = (
        dryrun.get("dryrun_results")
        if isinstance(dryrun.get("dryrun_results"), dict)
        else {}
    )
    guard_results = (
        dryrun.get("guard_results")
        if isinstance(dryrun.get("guard_results"), dict)
        else {}
    )
    required_checks = {
        "operator_summary_ok",
        "operator_summary_no_mutation",
        "operator_summary_approval_guarded",
        "script_paths_present",
        "script_hashes_match_summary",
        "scripts_syntax_ok",
        "dryrun_env_safe",
        "apply_dryrun_exit_zero",
        "rollback_dryrun_exit_zero",
        "apply_transcript_complete",
        "rollback_transcript_complete",
        "apply_transcript_excludes_rollback",
        "rollback_transcript_contains_only_rollback",
        "dryrun_transcripts_have_no_finish_events",
        "apply_transcript_meta_present",
        "rollback_transcript_meta_present",
        "apply_transcript_meta_role_apply",
        "rollback_transcript_meta_role_rollback",
        "apply_transcript_meta_execute_disabled",
        "rollback_transcript_meta_execute_disabled",
        "apply_transcript_meta_dry_run_enabled",
        "rollback_transcript_meta_dry_run_enabled",
        "apply_transcript_meta_approval_not_ok",
        "rollback_transcript_meta_approval_not_ok",
        "apply_transcript_meta_runbook_hash_matches",
        "rollback_transcript_meta_runbook_hash_matches",
        "apply_transcript_meta_script_hash_matches",
        "rollback_transcript_meta_script_hash_matches",
        "guard_blocks_execute_without_dryrun_pair",
        "guard_blocks_wrong_approval",
        "guard_checks_do_not_start_steps",
        "no_legacy_command_findings",
        "audit_only_runs_dryrun_scripts",
        "os_mutation_not_performed",
        "no_nl_or_spb_writes_performed",
    }
    failed_required_checks = sorted(
        name for name in required_checks if checks.get(name) is not True
    )
    transcript_paths_present = all(
        isinstance(transcript_paths.get(name), str)
        and bool(str(transcript_paths.get(name)).strip())
        for name in (
            "apply",
            "rollback",
            "guard_requires_pair",
            "guard_requires_approval",
        )
    )
    apply_result = (
        dryrun_results.get("apply") if isinstance(dryrun_results.get("apply"), dict) else {}
    )
    rollback_result = (
        dryrun_results.get("rollback")
        if isinstance(dryrun_results.get("rollback"), dict)
        else {}
    )
    pair_guard = (
        guard_results.get("execute_without_dryrun_pair")
        if isinstance(guard_results.get("execute_without_dryrun_pair"), dict)
        else {}
    )
    approval_guard = (
        guard_results.get("wrong_approval")
        if isinstance(guard_results.get("wrong_approval"), dict)
        else {}
    )
    ready = (
        dryrun.get("ok") is True
        and dryrun.get("approval_phrase_required")
        == "APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT"
        and dryrun.get("approval_present") is False
        and dryrun.get("production_mutation_allowed") is False
        and dryrun.get("manual_approval_still_required") is True
        and dryrun.get("os_mutation_performed") is False
        and dryrun.get("no_nl_or_spb_writes_performed") is True
        and not failed_required_checks
        and transcript_paths_present
    )
    failed_checks = dryrun.get("failed_checks")
    if not isinstance(failed_checks, list):
        failed_checks = failed_required_checks
    return requirement(
        item_id="FIRSTPARTY-PRODUCTION-OPERATOR-DRYRUN-01",
        title="First-party production apply and rollback operator scripts have clean dry-run transcripts and pre-step approval guard failures",
        status=READY_TO_STAGE if ready else MISSING,
        evidence=[
            f"summary_path={dryrun.get('summary_path') or dryrun.get('evidence_dir') or 'missing'}",
            f"dryrun_ok={bool_text(dryrun.get('ok'))}",
            f"approval_phrase_required={dryrun.get('approval_phrase_required') or 'missing'}",
            f"production_mutation_allowed={bool_text(dryrun.get('production_mutation_allowed'))}",
            f"os_mutation_performed={bool_text(dryrun.get('os_mutation_performed'))}",
            f"no_nl_or_spb_writes_performed={bool_text(dryrun.get('no_nl_or_spb_writes_performed'))}",
            f"operator_summary_path={dryrun.get('operator_summary_path') or 'missing'}",
            f"transcript_apply={transcript_paths.get('apply') or 'missing'}",
            f"transcript_rollback={transcript_paths.get('rollback') or 'missing'}",
            f"transcript_paths_present={bool_text(transcript_paths_present)}",
            f"apply_exit_code={apply_result.get('exit_code', 'missing')}",
            f"rollback_exit_code={rollback_result.get('exit_code', 'missing')}",
            f"guard_pair_exit_code={pair_guard.get('exit_code', 'missing')}",
            f"guard_approval_exit_code={approval_guard.get('exit_code', 'missing')}",
            f"apply_transcript_complete={bool_text(checks.get('apply_transcript_complete'))}",
            f"rollback_transcript_complete={bool_text(checks.get('rollback_transcript_complete'))}",
            f"apply_transcript_excludes_rollback={bool_text(checks.get('apply_transcript_excludes_rollback'))}",
            f"rollback_transcript_contains_only_rollback={bool_text(checks.get('rollback_transcript_contains_only_rollback'))}",
            f"dryrun_transcripts_have_no_finish_events={bool_text(checks.get('dryrun_transcripts_have_no_finish_events'))}",
            f"apply_transcript_meta_present={bool_text(checks.get('apply_transcript_meta_present'))}",
            f"rollback_transcript_meta_present={bool_text(checks.get('rollback_transcript_meta_present'))}",
            f"apply_transcript_meta_role_apply={bool_text(checks.get('apply_transcript_meta_role_apply'))}",
            f"rollback_transcript_meta_role_rollback={bool_text(checks.get('rollback_transcript_meta_role_rollback'))}",
            f"apply_transcript_meta_execute_disabled={bool_text(checks.get('apply_transcript_meta_execute_disabled'))}",
            f"rollback_transcript_meta_execute_disabled={bool_text(checks.get('rollback_transcript_meta_execute_disabled'))}",
            f"apply_transcript_meta_dry_run_enabled={bool_text(checks.get('apply_transcript_meta_dry_run_enabled'))}",
            f"rollback_transcript_meta_dry_run_enabled={bool_text(checks.get('rollback_transcript_meta_dry_run_enabled'))}",
            f"apply_transcript_meta_approval_not_ok={bool_text(checks.get('apply_transcript_meta_approval_not_ok'))}",
            f"rollback_transcript_meta_approval_not_ok={bool_text(checks.get('rollback_transcript_meta_approval_not_ok'))}",
            f"apply_transcript_meta_runbook_hash_matches={bool_text(checks.get('apply_transcript_meta_runbook_hash_matches'))}",
            f"rollback_transcript_meta_runbook_hash_matches={bool_text(checks.get('rollback_transcript_meta_runbook_hash_matches'))}",
            f"apply_transcript_meta_script_hash_matches={bool_text(checks.get('apply_transcript_meta_script_hash_matches'))}",
            f"rollback_transcript_meta_script_hash_matches={bool_text(checks.get('rollback_transcript_meta_script_hash_matches'))}",
            f"guard_blocks_execute_without_dryrun_pair={bool_text(checks.get('guard_blocks_execute_without_dryrun_pair'))}",
            f"guard_blocks_wrong_approval={bool_text(checks.get('guard_blocks_wrong_approval'))}",
            f"guard_checks_do_not_start_steps={bool_text(checks.get('guard_checks_do_not_start_steps'))}",
            f"failed_required_checks={compact_list(failed_required_checks)}",
            f"failed_checks={compact_list(failed_checks)}",
        ],
        next_step=(
            "execute generated apply script only after explicit approval phrase, then collect post-apply health JSON"
            if ready
            else "rerun first-party production operator scripts in dry-run mode and verify transcripts plus pre-step approval guard failures"
        ),
    )


def audit_firstparty_production_apply_transcript_audit(
    transcript: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Report whether the real apply transcript proves guarded execution."""

    transcript = transcript or {}
    checks = (
        transcript.get("checks") if isinstance(transcript.get("checks"), dict) else {}
    )
    required_checks = {
        "operator_summary_ok",
        "operator_summary_approval_guarded",
        "operator_summary_no_mutation",
        "apply_script_path_present",
        "rollback_script_path_present",
        "apply_script_hash_matches_summary",
        "rollback_script_hash_matches_summary",
        "apply_script_syntax_ok",
        "rollback_script_syntax_ok",
        "apply_transcript_present",
        "apply_transcript_nonempty",
        "apply_transcript_all_expected_starts_present",
        "apply_transcript_all_expected_finishes_rc0",
        "apply_transcript_no_dry_run_events",
        "apply_transcript_excludes_rollback_steps",
        "apply_transcript_no_failed_finishes",
        "apply_transcript_has_only_expected_apply_steps",
        "apply_transcript_meta_present",
        "apply_transcript_meta_role_apply",
        "apply_transcript_meta_execute_enabled",
        "apply_transcript_meta_dry_run_disabled",
        "apply_transcript_meta_approval_ok",
        "apply_transcript_meta_runbook_hash_matches",
        "apply_transcript_meta_script_hash_matches",
        "audit_does_not_execute_commands",
        "os_mutation_not_performed_by_audit",
        "no_nl_or_spb_writes_performed",
    }
    failed_required_checks = sorted(
        name for name in required_checks if checks.get(name) is not True
    )
    ready = (
        transcript.get("ok") is True
        and transcript.get("apply_execution_proven") is True
        and transcript.get("approval_phrase_required")
        == "APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT"
        and transcript.get("approval_present") is False
        and transcript.get("production_mutation_allowed") is False
        and transcript.get("manual_approval_still_required") is True
        and transcript.get("os_mutation_performed") is False
        and transcript.get("no_nl_or_spb_writes_performed") is True
        and not failed_required_checks
    )
    failed_checks = transcript.get("failed_checks")
    if not isinstance(failed_checks, list):
        failed_checks = failed_required_checks
    return requirement(
        item_id="FIRSTPARTY-PRODUCTION-APPLY-TRANSCRIPT-01",
        title="First-party production apply transcript proves all guarded apply steps finished successfully without dry-run or rollback steps",
        status=PASS if ready else MISSING,
        evidence=[
            f"summary_path={transcript.get('summary_path') or transcript.get('evidence_dir') or 'missing'}",
            f"transcript_ok={bool_text(transcript.get('ok'))}",
            f"apply_execution_proven={bool_text(transcript.get('apply_execution_proven'))}",
            f"approval_phrase_required={transcript.get('approval_phrase_required') or 'missing'}",
            f"production_mutation_allowed={bool_text(transcript.get('production_mutation_allowed'))}",
            f"os_mutation_performed={bool_text(transcript.get('os_mutation_performed'))}",
            f"no_nl_or_spb_writes_performed={bool_text(transcript.get('no_nl_or_spb_writes_performed'))}",
            f"operator_summary_path={transcript.get('operator_summary_path') or 'missing'}",
            f"apply_transcript_path={transcript.get('apply_transcript_path') or 'missing'}",
            f"apply_transcript_present={bool_text(checks.get('apply_transcript_present'))}",
            f"apply_transcript_nonempty={bool_text(checks.get('apply_transcript_nonempty'))}",
            f"apply_transcript_all_expected_starts_present={bool_text(checks.get('apply_transcript_all_expected_starts_present'))}",
            f"apply_transcript_all_expected_finishes_rc0={bool_text(checks.get('apply_transcript_all_expected_finishes_rc0'))}",
            f"apply_transcript_no_dry_run_events={bool_text(checks.get('apply_transcript_no_dry_run_events'))}",
            f"apply_transcript_excludes_rollback_steps={bool_text(checks.get('apply_transcript_excludes_rollback_steps'))}",
            f"apply_transcript_no_failed_finishes={bool_text(checks.get('apply_transcript_no_failed_finishes'))}",
            f"apply_transcript_has_only_expected_apply_steps={bool_text(checks.get('apply_transcript_has_only_expected_apply_steps'))}",
            f"apply_transcript_meta_present={bool_text(checks.get('apply_transcript_meta_present'))}",
            f"apply_transcript_meta_role_apply={bool_text(checks.get('apply_transcript_meta_role_apply'))}",
            f"apply_transcript_meta_execute_enabled={bool_text(checks.get('apply_transcript_meta_execute_enabled'))}",
            f"apply_transcript_meta_dry_run_disabled={bool_text(checks.get('apply_transcript_meta_dry_run_disabled'))}",
            f"apply_transcript_meta_approval_ok={bool_text(checks.get('apply_transcript_meta_approval_ok'))}",
            f"apply_transcript_meta_runbook_hash_matches={bool_text(checks.get('apply_transcript_meta_runbook_hash_matches'))}",
            f"apply_transcript_meta_script_hash_matches={bool_text(checks.get('apply_transcript_meta_script_hash_matches'))}",
            f"apply_script_hash_matches_summary={bool_text(checks.get('apply_script_hash_matches_summary'))}",
            f"rollback_script_hash_matches_summary={bool_text(checks.get('rollback_script_hash_matches_summary'))}",
            f"failed_required_checks={compact_list(failed_required_checks)}",
            f"failed_checks={compact_list(failed_checks)}",
        ],
        next_step=(
            "collect post-apply server-health, client-health, and client-doctor JSON, then rebuild completion audit"
            if ready
            else "run the generated apply script only after explicit approval and audit its apply-execution transcript; meta must prove EXECUTE=1, DRY_RUN=0, approval_ok=true, matching runbook/script hashes, and all apply steps must finish rc=0 without dry-run or rollback events"
        ),
    )


def audit_firstparty_production_completion_audit(
    completion: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Report whether first-party production completion is actually proven."""

    completion = completion or {}
    checks = (
        completion.get("checks") if isinstance(completion.get("checks"), dict) else {}
    )
    evidence_commands = (
        completion.get("required_operator_evidence_commands")
        if isinstance(completion.get("required_operator_evidence_commands"), dict)
        else {}
    )
    rollback_commands = (
        completion.get("rollback_commands")
        if isinstance(completion.get("rollback_commands"), dict)
        else {}
    )
    required_checks = {
        "runbook_summary_ok",
        "runbook_approval_guarded",
        "runbook_required_checks_ok",
        "runbook_required_commands_present",
        "runbook_no_legacy_commands",
        "completion_evidence_present",
        "server_health_evidence_present",
        "server_health_ok",
        "client_health_evidence_present",
        "client_health_ok",
        "client_doctor_evidence_present",
        "client_doctor_ok",
        "client_doctor_requires_installed_health",
        "endpoint_matches_runbook",
        "service_names_match",
        "post_apply_evidence_no_os_mutation",
        "audit_does_not_execute_commands",
        "no_nl_or_spb_writes_performed",
    }
    failed_required_checks = sorted(
        name for name in required_checks if checks.get(name) is not True
    )
    required_evidence_commands_present = all(
        isinstance(evidence_commands.get(name), str)
        and bool(str(evidence_commands.get(name)).strip())
        for name in (
            "server_health_post_apply",
            "client_health_post_apply",
            "client_doctor_post_apply",
        )
    )
    rollback_commands_present = all(
        isinstance(rollback_commands.get(name), str)
        and bool(str(rollback_commands.get(name)).strip())
        for name in ("client", "server")
    )
    ready = (
        completion.get("ok") is True
        and completion.get("completion_decision")
        == "FIRSTPARTY_VPN_PRODUCTION_COMPLETE"
        and completion.get("goal_completion_claim_allowed") is True
        and completion.get("production_apply_still_required") is False
        and completion.get("os_mutation_performed") is False
        and completion.get("no_nl_or_spb_writes_performed") is True
        and not failed_required_checks
        and required_evidence_commands_present
        and rollback_commands_present
    )
    failed_checks = completion.get("failed_checks")
    if not isinstance(failed_checks, list):
        failed_checks = failed_required_checks
    return requirement(
        item_id="FIRSTPARTY-PRODUCTION-COMPLETION-01",
        title="First-party production endpoint is applied and proven by post-apply server/client health evidence",
        status=PASS if ready else MISSING,
        evidence=[
            f"summary_path={completion.get('summary_path') or completion.get('evidence_dir') or 'missing'}",
            f"completion_ok={bool_text(completion.get('ok'))}",
            f"completion_decision={completion.get('completion_decision') or 'missing'}",
            f"goal_completion_claim_allowed={bool_text(completion.get('goal_completion_claim_allowed'))}",
            f"production_apply_still_required={bool_text(completion.get('production_apply_still_required'))}",
            f"os_mutation_performed={bool_text(completion.get('os_mutation_performed'))}",
            f"no_nl_or_spb_writes_performed={bool_text(completion.get('no_nl_or_spb_writes_performed'))}",
            f"completion_evidence_present={bool_text(checks.get('completion_evidence_present'))}",
            f"server_health_ok={bool_text(checks.get('server_health_ok'))}",
            f"client_health_ok={bool_text(checks.get('client_health_ok'))}",
            f"client_doctor_ok={bool_text(checks.get('client_doctor_ok'))}",
            f"endpoint_matches_runbook={bool_text(checks.get('endpoint_matches_runbook'))}",
            f"service_names_match={bool_text(checks.get('service_names_match'))}",
            f"post_apply_evidence_no_os_mutation={bool_text(checks.get('post_apply_evidence_no_os_mutation'))}",
            f"audit_does_not_execute_commands={bool_text(checks.get('audit_does_not_execute_commands'))}",
            f"required_evidence_commands_present={bool_text(required_evidence_commands_present)}",
            f"rollback_commands_present={bool_text(rollback_commands_present)}",
            f"failed_required_checks={compact_list(failed_required_checks)}",
            f"failed_checks={compact_list(failed_checks)}",
        ],
        next_step=(
            "first-party production endpoint is proven by post-apply health evidence"
            if ready
            else "collect post-apply server-health, client-health, and client-doctor JSON from the guarded first-party production runbook, then rebuild completion audit"
        ),
    )


def audit_firstparty_no_foreign_dependencies(
    core_requirement: dict[str, Any],
    canary_requirement: dict[str, Any],
    production_readiness_requirement: dict[str, Any],
    no_foreign: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Report whether the first-party objective is independent of legacy VPN stacks."""

    no_foreign = no_foreign or {}
    if no_foreign.get("precomputed") is True:
        source_audit_passed = no_foreign.get("source_audit_passed") is True
        source_audit_reasons = compact_list(no_foreign.get("source_audit_reasons") or [])
        source_audit_scanned_files = int(no_foreign.get("source_audit_scanned_files") or 0)
        current_source_tree_hash = str(
            no_foreign.get("current_source_tree_hash") or "missing"
        )
        canary_source_tree_hash = str(
            no_foreign.get("canary_source_tree_hash") or current_source_tree_hash
        )
        readiness_source_tree_hash = str(
            no_foreign.get("production_readiness_source_tree_hash")
            or current_source_tree_hash
        )
    else:
        core_evidence = requirement_evidence_map(core_requirement)
        canary_evidence = requirement_evidence_map(canary_requirement)
        readiness_evidence = requirement_evidence_map(production_readiness_requirement)
        source_audit_passed = core_evidence.get("source_audit_passed") == "true"
        source_audit_reasons = core_evidence.get("source_audit_reasons", "missing")
        try:
            source_audit_scanned_files = int(
                core_evidence.get("source_audit_scanned_files", "0")
            )
        except ValueError:
            source_audit_scanned_files = 0
        current_source_tree_hash = core_evidence.get("source_audit_tree_hash", "missing")
        canary_source_tree_hash = canary_evidence.get("source_tree_hash", "missing")
        readiness_source_tree_hash = readiness_evidence.get("source_tree_hash", "missing")

    known_hashes = [
        value
        for value in (
            current_source_tree_hash,
            canary_source_tree_hash,
            readiness_source_tree_hash,
        )
        if value and value != "missing"
    ]
    source_tree_hash_consistent = len(set(known_hashes)) <= 1 and bool(known_hashes)
    legacy_requirements_non_blocking = True
    ready = (
        source_audit_passed
        and source_audit_reasons == "none"
        and source_audit_scanned_files > 0
        and source_tree_hash_consistent
        and legacy_requirements_non_blocking
    )
    return requirement(
        item_id="FIRSTPARTY-NO-FOREIGN-01",
        title="First-party VPN objective is independent of legacy VLESS/WARP/Happ/Hiddify evidence",
        status=PASS if ready else MISSING,
        evidence=[
            f"source_audit_passed={bool_text(source_audit_passed)}",
            f"source_audit_reasons={source_audit_reasons}",
            f"source_audit_scanned_files={source_audit_scanned_files}",
            f"current_source_tree_hash={current_source_tree_hash}",
            f"canary_source_tree_hash={canary_source_tree_hash}",
            f"production_readiness_source_tree_hash={readiness_source_tree_hash}",
            f"source_tree_hash_consistent={bool_text(source_tree_hash_consistent)}",
            f"legacy_requirement_ids={compact_list(sorted(LEGACY_FOREIGN_REQUIREMENT_IDS))}",
            f"legacy_requirements_non_blocking_for_firstparty_goal={bool_text(legacy_requirements_non_blocking)}",
        ],
        next_step=(
            "keep legacy VLESS/WARP/Happ/Hiddify evidence out of the first-party completion decision"
            if ready
            else "rerun first-party source audit and refresh local canary/readiness evidence from the same source tree"
        ),
    )


def unique_ordered(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def build_payload(inputs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    decision = inputs.get("decision") or {}
    anti_block_audit = inputs.get("anti_block_audit") or {}
    client_matrix = inputs.get("client_matrix") or {}
    remote_request = inputs.get("remote_request") or {}
    telegram_warp_plan = inputs.get("telegram_warp_plan") or {}
    monitor_restore_readiness = inputs.get("monitor_restore_readiness") or {}
    readiness_audit = inputs.get("readiness_audit") or {}
    manifest = inputs.get("manifest") or {}
    preflight = inputs.get("preflight") or {}
    firstparty_core = inputs.get("firstparty_core") or {}
    firstparty_canary = inputs.get("firstparty_canary") or {}
    firstparty_production_readiness = inputs.get("firstparty_production_readiness") or {}
    firstparty_staging_packet = inputs.get("firstparty_staging_packet") or {}
    firstparty_production_endpoint = inputs.get("firstparty_production_endpoint") or {}
    firstparty_production_apply_packet = (
        inputs.get("firstparty_production_apply_packet") or {}
    )
    firstparty_secure_material_handoff = (
        inputs.get("firstparty_secure_material_handoff") or {}
    )
    firstparty_production_authorization = (
        inputs.get("firstparty_production_authorization") or {}
    )
    firstparty_production_apply_runbook = (
        inputs.get("firstparty_production_apply_runbook") or {}
    )
    firstparty_production_operator_script = (
        inputs.get("firstparty_production_operator_script") or {}
    )
    firstparty_production_operator_dryrun_audit = (
        inputs.get("firstparty_production_operator_dryrun_audit") or {}
    )
    firstparty_production_apply_transcript_audit = (
        inputs.get("firstparty_production_apply_transcript_audit") or {}
    )
    firstparty_production_completion_audit = (
        inputs.get("firstparty_production_completion_audit") or {}
    )
    firstparty_rollout_packet = inputs.get("firstparty_rollout_packet") or {}
    firstparty_preapply_readiness = inputs.get("firstparty_preapply_readiness") or {}
    firstparty_no_foreign = inputs.get("firstparty_no_foreign") or {}

    firstparty_core_requirement = audit_firstparty_vpn_core(firstparty_core)
    firstparty_canary_requirement = audit_firstparty_live_canary(firstparty_canary)
    firstparty_production_readiness_requirement = (
        audit_firstparty_production_readiness(firstparty_production_readiness)
    )
    firstparty_staging_packet_requirement = audit_firstparty_staging_packet(
        firstparty_staging_packet
    )
    firstparty_production_endpoint_requirement = audit_firstparty_production_endpoint(
        firstparty_production_endpoint
    )
    firstparty_production_apply_packet_requirement = (
        audit_firstparty_production_apply_packet(firstparty_production_apply_packet)
    )
    firstparty_secure_material_handoff_requirement = (
        audit_firstparty_secure_material_handoff(firstparty_secure_material_handoff)
    )
    firstparty_production_authorization_requirement = (
        audit_firstparty_production_authorization(firstparty_production_authorization)
    )
    firstparty_production_apply_runbook_requirement = (
        audit_firstparty_production_apply_runbook(firstparty_production_apply_runbook)
    )
    firstparty_production_operator_script_requirement = (
        audit_firstparty_production_operator_script(
            firstparty_production_operator_script
        )
    )
    firstparty_production_operator_dryrun_requirement = (
        audit_firstparty_production_operator_dryrun_audit(
            firstparty_production_operator_dryrun_audit
        )
    )
    firstparty_production_apply_transcript_requirement = (
        audit_firstparty_production_apply_transcript_audit(
            firstparty_production_apply_transcript_audit
        )
    )
    firstparty_production_completion_requirement = (
        audit_firstparty_production_completion_audit(
            firstparty_production_completion_audit
        )
    )
    firstparty_rollout_packet_requirement = audit_firstparty_rollout_packet(
        firstparty_rollout_packet
    )
    firstparty_preapply_readiness_requirement = audit_firstparty_preapply_readiness(
        firstparty_preapply_readiness
    )
    firstparty_no_foreign_requirement = audit_firstparty_no_foreign_dependencies(
        firstparty_core_requirement,
        firstparty_canary_requirement,
        firstparty_production_readiness_requirement,
        firstparty_no_foreign,
    )

    firstparty_requirements = [
        firstparty_core_requirement,
        firstparty_canary_requirement,
        firstparty_production_readiness_requirement,
        firstparty_staging_packet_requirement,
        firstparty_production_endpoint_requirement,
        firstparty_production_apply_packet_requirement,
        firstparty_secure_material_handoff_requirement,
        firstparty_production_authorization_requirement,
        firstparty_production_apply_runbook_requirement,
        firstparty_production_operator_script_requirement,
        firstparty_production_operator_dryrun_requirement,
        firstparty_production_apply_transcript_requirement,
        firstparty_production_completion_requirement,
        firstparty_rollout_packet_requirement,
        firstparty_preapply_readiness_requirement,
        firstparty_no_foreign_requirement,
    ]
    legacy_requirements = [
        audit_core_vless_reality(decision, monitor_restore_readiness),
        audit_evidence_freshness(decision, remote_request),
        audit_anti_block_real_clients(anti_block_audit, client_matrix, remote_request, preflight),
        audit_telegram_warp_route(telegram_warp_plan),
        audit_nl_readonly_gate(readiness_audit, manifest, preflight),
        audit_evidence_claims_privacy(
            {
                "decision": decision,
                "anti_block_audit": anti_block_audit,
                "client_matrix": client_matrix,
                "remote_request": remote_request,
                "telegram_warp_plan": telegram_warp_plan,
                "readiness_audit": readiness_audit,
            }
        ),
    ]
    requirements = [*firstparty_requirements, *legacy_requirements]
    incomplete = [row for row in requirements if row.get("ok") is not True]
    firstparty_incomplete = [
        row for row in firstparty_requirements if row.get("ok") is not True
    ]
    firstparty_remaining = unique_ordered([row["next_step"] for row in firstparty_incomplete])
    firstparty_build_complete = not firstparty_incomplete
    firstparty_decision = (
        "FIRSTPARTY_VPN_PRODUCTION_COMPLETE"
        if firstparty_build_complete
        else "FIRSTPARTY_VPN_PRODUCTION_NOT_PROVEN"
    )
    remaining = [
        str(value)
        for value in anti_block_audit.get("remaining_before_goal_complete") or []
        if isinstance(value, str)
    ]
    for row in incomplete:
        if row["id"] == "ANTIBLOCK-CLIENTS-01" and remaining:
            continue
        remaining.append(row["next_step"])
    goal_complete = not incomplete
    decision_name = (
        "VPN_PRODUCTION_CANDIDATE_GOAL_COMPLETE"
        if goal_complete
        else "VPN_PRODUCTION_CANDIDATE_GOAL_NOT_COMPLETE"
    )
    return {
        "schema_version": 2,
        "source": "nl-diagnostics/build_vpn_goal_status.py",
        "generated_at": utc_now(),
        "decision": decision_name,
        "goal_complete": goal_complete,
        "firstparty_decision": firstparty_decision,
        "firstparty_build_complete": firstparty_build_complete,
        "firstparty_requirements_passed": (
            len(firstparty_requirements) - len(firstparty_incomplete)
        ),
        "firstparty_requirements_total": len(firstparty_requirements),
        "firstparty_requirement_ids": [row["id"] for row in firstparty_requirements],
        "firstparty_remaining_before_build_complete": firstparty_remaining,
        "legacy_foreign_requirement_ids": sorted(LEGACY_FOREIGN_REQUIREMENT_IDS),
        "legacy_requirements_non_blocking_for_firstparty_goal": True,
        "requirements_passed": len(requirements) - len(incomplete),
        "requirements_total": len(requirements),
        "requirements": requirements,
        "remaining_before_goal_complete": unique_ordered(remaining),
        "no_nl_or_spb_writes_performed": True,
        "preflight": {
            "ok": preflight.get("ok"),
            "deploy_status": preflight.get("deploy_status"),
            "nl_write_allowed": preflight.get("nl_write_allowed"),
            "check_count": len(preflight.get("checks") or []),
            "validator_exit_code": preflight.get("validator_exit_code"),
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# VPN Production-Candidate Goal Status",
        "",
        f"generated_at: `{payload['generated_at']}`",
        f"decision: `{payload['decision']}`",
        f"goal_complete: `{str(payload['goal_complete']).lower()}`",
        f"firstparty_decision: `{payload.get('firstparty_decision', 'missing')}`",
        f"firstparty_build_complete: `{str(payload.get('firstparty_build_complete')).lower()}`",
        "",
        "## First-Party Objective",
        "",
        f"firstparty_requirements: `{payload.get('firstparty_requirements_passed', 0)}/{payload.get('firstparty_requirements_total', 0)}`",
        f"legacy_requirements_non_blocking: `{str(payload.get('legacy_requirements_non_blocking_for_firstparty_goal')).lower()}`",
        "",
        "### Remaining First-Party Work",
        "",
    ]
    firstparty_remaining = payload.get("firstparty_remaining_before_build_complete") or []
    if firstparty_remaining:
        lines.extend(f"- {value}" for value in firstparty_remaining)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Requirements",
            "",
            "| ID | Status | OK | Requirement | Next Step |",
            "|---|---|---|---|---|",
        ]
    )
    for row in payload["requirements"]:
        lines.append(
            f"| `{row['id']}` | `{row['status']}` | `{str(row['ok']).lower()}` | "
            f"{row['title']} | {row['next_step']} |"
        )

    lines.extend(["", "## Evidence", ""])
    for row in payload["requirements"]:
        lines.extend([f"### {row['id']}", ""])
        lines.extend(f"- {value}" for value in row["evidence"])
        lines.append("")

    lines.extend(["## Remaining Before Goal Complete", ""])
    remaining = payload.get("remaining_before_goal_complete") or []
    if remaining:
        lines.extend(f"- {value}" for value in remaining)
    else:
        lines.append("- none")

    preflight = payload.get("preflight") or {}
    lines.extend(
        [
            "",
            "## Preflight",
            "",
            "```text",
            f"ok={bool_text(preflight.get('ok'))}",
            f"deploy_status={preflight.get('deploy_status')}",
            f"nl_write_allowed={bool_text(preflight.get('nl_write_allowed'))}",
            f"check_count={preflight.get('check_count')}",
            f"validator_exit_code={preflight.get('validator_exit_code')}",
            "```",
            "",
            "No NL or SPB writes were performed by this goal report.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build VPN production-candidate goal status")
    parser.add_argument("--decision", default=str(DEFAULT_DECISION))
    parser.add_argument("--anti-block-audit", default=str(DEFAULT_ANTI_BLOCK_AUDIT))
    parser.add_argument("--client-matrix", default=str(DEFAULT_CLIENT_MATRIX))
    parser.add_argument("--remote-request", default=str(DEFAULT_REMOTE_REQUEST))
    parser.add_argument("--telegram-warp-plan", default=str(DEFAULT_TELEGRAM_WARP_PLAN))
    parser.add_argument("--readiness-audit", default=str(DEFAULT_READINESS_AUDIT))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--preflight-validator", default=str(DEFAULT_PREFLIGHT_VALIDATOR))
    parser.add_argument("--skip-preflight", action="store_true")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    parser.add_argument("--json", action="store_true", help="Print payload JSON to stdout")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return exit code 2 when the goal is not complete",
    )
    args = parser.parse_args()

    preflight = (
        {
            "ok": None,
            "deploy_status": "skipped",
            "nl_write_allowed": None,
            "checks": [],
            "validator_exit_code": None,
        }
        if args.skip_preflight
        else run_preflight_validator(Path(args.preflight_validator))
    )
    payload = build_payload(
        {
            "decision": read_json(Path(args.decision)),
            "anti_block_audit": read_json(Path(args.anti_block_audit)),
            "client_matrix": read_json(Path(args.client_matrix)),
            "remote_request": read_json(Path(args.remote_request)),
            "telegram_warp_plan": read_json(Path(args.telegram_warp_plan)),
            "monitor_restore_readiness": read_vpn_monitor_restore_readiness(),
            "readiness_audit": read_json(Path(args.readiness_audit)),
            "manifest": read_json(Path(args.manifest)),
            "preflight": preflight,
            "firstparty_canary": read_latest_firstparty_canary(),
            "firstparty_production_readiness": read_latest_firstparty_production_readiness(),
            "firstparty_staging_packet": read_latest_firstparty_staging_packet(),
            "firstparty_production_endpoint": read_latest_firstparty_production_endpoint(),
            "firstparty_production_apply_packet": read_latest_firstparty_production_apply_packet(),
            "firstparty_secure_material_handoff": read_latest_firstparty_secure_material_handoff(),
            "firstparty_production_authorization": read_latest_firstparty_production_authorization(),
            "firstparty_production_apply_runbook": read_latest_firstparty_production_apply_runbook(),
            "firstparty_production_operator_script": read_latest_firstparty_production_operator_script(),
            "firstparty_production_operator_dryrun_audit": read_latest_firstparty_production_operator_dryrun_audit(),
            "firstparty_production_apply_transcript_audit": read_latest_firstparty_production_apply_transcript_audit(),
            "firstparty_production_completion_audit": read_latest_firstparty_production_completion_audit(),
            "firstparty_rollout_packet": read_latest_firstparty_rollout_packet(),
            "firstparty_preapply_readiness": read_latest_firstparty_preapply_readiness(),
        }
    )

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.markdown_out:
        Path(args.markdown_out).write_text(render_markdown(payload), encoding="utf-8")
    if args.json or (not args.json_out and not args.markdown_out):
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 2 if args.strict and not payload["goal_complete"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
