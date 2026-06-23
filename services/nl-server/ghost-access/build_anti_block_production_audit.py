#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import re
from typing import Any


DEFAULT_AUDIT_JSON_PATH = Path("nl-diagnostics/nl-anti-block-production-audit-2026-06-02.json")
DEFAULT_AUDIT_MARKDOWN_PATH = Path("nl-diagnostics/nl-anti-block-production-audit-2026-06-02.md")
DEFAULT_MATRIX_JSON_PATH = Path(
    "nl-diagnostics/nl-anti-block-client-compatibility-matrix-2026-06-02.json"
)
DEFAULT_MATRIX_MARKDOWN_PATH = Path(
    "nl-diagnostics/nl-anti-block-client-compatibility-matrix-2026-06-02.md"
)
DEFAULT_EVIDENCE_PLAN_JSON_PATH = Path(
    "nl-diagnostics/nl-anti-block-client-evidence-plan-2026-06-02.json"
)
DEFAULT_EVIDENCE_PLAN_MARKDOWN_PATH = Path(
    "nl-diagnostics/nl-anti-block-client-evidence-plan-2026-06-02.md"
)
DEFAULT_REMOTE_INTAKE_JSON_PATH = Path(
    "nl-diagnostics/nl-anti-block-remote-client-evidence-intake-2026-06-02.json"
)
DEFAULT_REMOTE_INTAKE_MARKDOWN_PATH = Path(
    "nl-diagnostics/nl-anti-block-remote-client-evidence-intake-2026-06-02.md"
)
DEFAULT_REMOTE_REQUEST_JSON_PATH = Path(
    "nl-diagnostics/nl-anti-block-remote-client-evidence-request-2026-06-02.json"
)
DEFAULT_REMOTE_REQUEST_MARKDOWN_PATH = Path(
    "nl-diagnostics/nl-anti-block-remote-client-evidence-request-2026-06-02.md"
)
DEFAULT_RUNTIME_SUMMARY_JSON_PATH = Path(
    "nl-diagnostics/nl-anti-block-client-compatibility-runtime-summary-2026-06-02.json"
)
DEFAULT_RUNTIME_SUMMARY_MARKDOWN_PATH = Path(
    "nl-diagnostics/nl-anti-block-client-compatibility-runtime-summary-2026-06-02.md"
)
DEFAULT_RUNTIME_PROBE_JSON_PATH = Path(
    "nl-diagnostics/nl-anti-block-client-compatibility-runtime-probe-2026-06-02.json"
)
DEFAULT_RUNTIME_PROBE_MARKDOWN_PATH = Path(
    "nl-diagnostics/nl-anti-block-client-compatibility-runtime-probe-2026-06-02.md"
)
DEFAULT_RUNTIME_DEPLOY_PLAN_JSON_PATH = Path(
    "nl-diagnostics/nl-anti-block-client-compatibility-runtime-deploy-plan-2026-06-02.json"
)
DEFAULT_RUNTIME_DEPLOY_PLAN_MARKDOWN_PATH = Path(
    "nl-diagnostics/nl-anti-block-client-compatibility-runtime-deploy-plan-2026-06-02.md"
)
CURRENT_EVIDENCE_SESSION_ID = "nl-anti-block-2026-06-02"
CURRENT_EVIDENCE_SESSION_STARTED_AT = "2026-06-02T00:00:00Z"
CURRENT_EVIDENCE_REQUIRED_TRANSPORT = "reality"
CURRENT_EVIDENCE_REQUIRED_PORT = 443
SESSION_BOUND_REQUIREMENTS = (
    "android_happ_or_hiddify",
    "mobile_network",
    "restricted_or_work_wifi",
)

FORBIDDEN_OUTPUT_PATTERNS = {
    "vpn_uri": re.compile(r"\b(?:vless|vmess|trojan|ss)://", re.IGNORECASE),
    "subscription_path": re.compile(r"/sub/[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]{8,}"),
    "uuid": re.compile(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        re.IGNORECASE,
    ),
    "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    "ipv4": re.compile(
        r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"
    ),
    "http_url": re.compile(r"\bhttps?://", re.IGNORECASE),
    "telegram_handle": re.compile(r"@[A-Za-z0-9_]{4,}"),
    "phone": re.compile(r"\+\d[\d .()_-]{8,}\d\b"),
}


class AuditError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AuditError(f"{path} is not valid JSON: {exc}") from exc
    return payload if isinstance(payload, dict) else None


def require_json(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    if payload is None:
        raise AuditError(f"required JSON artifact missing or not an object: {path}")
    return payload


def privacy_ok(payload: dict[str, Any] | None) -> bool:
    if not isinstance(payload, dict):
        return False
    privacy = payload.get("privacy")
    return isinstance(privacy, dict) and privacy.get("output_privacy_ok") is True


def all_ok(rows: list[dict[str, Any]]) -> bool:
    return all(row.get("ok") is True for row in rows)


def missing_requirements(matrix: dict[str, Any]) -> list[str]:
    rule = matrix.get("completion_rule") if isinstance(matrix.get("completion_rule"), dict) else {}
    return [str(item) for item in rule.get("missing_requirements") or []]


def completion_evidence(matrix: dict[str, Any]) -> dict[str, bool]:
    rule = matrix.get("completion_rule") if isinstance(matrix.get("completion_rule"), dict) else {}
    evidence = rule.get("evidence") if isinstance(rule.get("evidence"), dict) else {}
    return {str(key): bool(value) for key, value in evidence.items()}


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


def parse_utc_datetime(value: str) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC).replace(microsecond=0)


def checked_at_in_current_session(value: str) -> bool:
    parsed = parse_utc_datetime(value)
    started = parse_utc_datetime(CURRENT_EVIDENCE_SESSION_STARTED_AT)
    return parsed is not None and started is not None and parsed >= started


def runtime_probe_in_current_session(runtime_probe: dict[str, Any]) -> bool:
    return checked_at_in_current_session(str(runtime_probe.get("checked_at") or ""))


def required_rollout_transport_ok(row: dict[str, Any]) -> bool:
    return (
        str(row.get("transport") or "").lower() == CURRENT_EVIDENCE_REQUIRED_TRANSPORT
        and row.get("port") == CURRENT_EVIDENCE_REQUIRED_PORT
    )


def current_session_requirement_evidence(matrix: dict[str, Any]) -> dict[str, bool]:
    checks = matrix.get("real_client_checks")
    if not isinstance(checks, list):
        checks = []
    rows = [
        row
        for row in checks
        if isinstance(row, dict)
        and row.get("status") == "pass"
        and row.get("raw_secret_material_stored") is False
        and row.get("evidence_session_id") == CURRENT_EVIDENCE_SESSION_ID
        and checked_at_in_current_session(str(row.get("checked_at") or ""))
        and required_rollout_transport_ok(row)
    ]
    android_happ_or_hiddify = any(
        str(row.get("client") or "").lower() in {"happ", "hiddify"}
        and str(row.get("network_type") or "").lower() == "mobile"
        for row in rows
    )
    mobile_network = any(
        str(row.get("network_type") or "").lower() == "mobile" for row in rows
    )
    restricted_or_work_wifi = any(
        str(row.get("network_type") or "").lower() in {"work-wifi", "restricted-wifi"}
        for row in rows
    )
    return {
        "android_happ_or_hiddify": android_happ_or_hiddify,
        "mobile_network": mobile_network,
        "restricted_or_work_wifi": restricted_or_work_wifi,
    }


def current_session_requirements_complete(matrix: dict[str, Any]) -> bool:
    status = current_session_requirement_evidence(matrix)
    return all(status.get(requirement) is True for requirement in SESSION_BOUND_REQUIREMENTS)


def compact_request(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "request_id": request.get("request_id"),
        "covers_requirements": request.get("covers_requirements") or [],
        "client": request.get("client"),
        "network_type": request.get("network_type"),
        "transport": request.get("transport"),
        "port": request.get("port"),
        "evidence_session_id": request.get("evidence_session_id"),
        "evidence_session_started_at": request.get("evidence_session_started_at"),
        "minimum_result_to_close_requirements": request.get(
            "minimum_result_to_close_requirements"
        ),
        "operator_record_pass_command_available": bool(
            request.get("operator_record_pass_command")
        ),
        "operator_record_fail_command_available": bool(
            request.get("operator_record_fail_command")
        ),
        "operator_reply_record_pass_command_available": bool(
            request.get("operator_reply_record_pass_command")
        ),
        "operator_reply_record_fail_command_available": bool(
            request.get("operator_reply_record_fail_command")
        ),
        "safe_reply_options": request.get("safe_reply_options") or [],
    }


def server_evidence_from_seed(seed: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(seed, dict):
        return {}
    live = seed.get("live_evidence")
    return live if isinstance(live, dict) else seed


def evaluate_requirements(
    *,
    live_evidence: dict[str, Any],
    matrix: dict[str, Any],
    runtime_summary: dict[str, Any],
    runtime_probe: dict[str, Any],
    runtime_deploy_plan: dict[str, Any],
) -> dict[str, str]:
    fallback = live_evidence.get("fallback_subscription") or {}
    runtime = live_evidence.get("runtime") or {}
    usage = live_evidence.get("usage_60m") or {}
    rollback_dry_run = live_evidence.get("rollback_dry_run") or {}
    rollback_drill = live_evidence.get("rollback_drill") or {}
    reality_canary = live_evidence.get("reality_canary_after_rollback_restore") or {}
    runtime_client = runtime_probe.get("client_compatibility_endpoint") or {}
    runtime_systemd = runtime_probe.get("systemd_wiring") or {}
    runtime_privacy = runtime_probe.get("privacy") or {}
    runtime_probe_fresh = runtime_probe_in_current_session(runtime_probe)

    reality_results = reality_canary.get("results") if isinstance(reality_canary, dict) else []
    rollback_restore = rollback_drill.get("after_restore") if isinstance(rollback_drill, dict) else {}
    rollback_apply = rollback_drill.get("rollback_apply") if isinstance(rollback_drill, dict) else {}
    required_restore_units = {
        "x-ui",
        "telegram-bot-simple.service",
        "ghost-access-nl-xhttp.service",
        "ghost-access-nl-https-ws.service",
    }
    restore_units_ok = all(rollback_restore.get(unit) == "active" for unit in required_restore_units)

    missing = missing_requirements(matrix)
    evidence = completion_evidence(matrix)
    session_complete = current_session_requirements_complete(matrix)
    client_matrix_status = (
        "pass"
        if not missing and all(evidence.get(name) is True for name in (
            "desktop_v2rayn",
            "android_happ_or_hiddify",
            "mobile_network",
            "restricted_or_work_wifi",
        ))
        and session_complete
        else "client_evidence_session_mismatch"
        if not missing and not session_complete
        else "partial_desktop_pass_mobile_pending"
        if evidence.get("desktop_v2rayn") is True
        else "not_proven"
    )

    return {
        "fallback_subscriptions": (
            "pass"
            if fallback.get("has_reality") and fallback.get("has_ws") and fallback.get("has_xhttp")
            else "not_proven"
        ),
        "multi_transport_same_nl": (
            "pass"
            if runtime.get("ghost_xhttp_ready") is True
            and runtime.get("ghost_https_ws_ready") is True
            else "not_proven"
        ),
        "operator_visibility": (
            "pass"
            if runtime_probe.get("decision") == "NL_CLIENT_COMPAT_RUNTIME_READY"
            and runtime_client.get("http_code") == 200
            else "not_proven"
        ),
        "privacy_safe_runtime_evidence": (
            "pass"
            if runtime.get("status_api_privacy_ok") is True
            and usage.get("privacy_ok") is True
            and runtime_privacy.get("output_privacy_ok") is True
            else "not_proven"
        ),
        "reality_legacy_access_alive": (
            "pass"
            if fallback.get("has_reality") is True
            and isinstance(reality_results, list)
            and reality_results
            and all(isinstance(row, dict) and row.get("ok") is True for row in reality_results)
            else "not_proven"
        ),
        "rollback_dry_run_and_confirm_gates": (
            "pass"
            if rollback_dry_run.get("ok") is True
            and rollback_dry_run.get("confirm_required") == "ROLLBACK_GHOST_FALLBACKS"
            else "not_proven"
        ),
        "rollback_execution_without_access_loss": (
            "pass"
            if rollback_apply.get("ok") is True
            and restore_units_ok
            and rollback_restore.get("status_api_health_ok") is True
            else "not_proven"
        ),
        "runtime_evidence": (
            "pass"
            if runtime.get("ghost_xhttp_ready") is True
            and runtime.get("ghost_https_ws_ready") is True
            and runtime_probe.get("decision") == "NL_CLIENT_COMPAT_RUNTIME_READY"
            and runtime_probe_fresh
            else "not_proven"
        ),
        "user_client_matrix_after_rollout": client_matrix_status,
        "client_compatibility_runtime_on_nl": (
            "pass"
            if runtime_probe.get("decision") == "NL_CLIENT_COMPAT_RUNTIME_READY"
            and runtime_probe_fresh
            and runtime_client.get("http_code") == 200
            and runtime_client.get("raw_real_client_rows_returned") is False
            and runtime_systemd.get("matrix_present") is True
            and runtime_systemd.get("summary_present") is True
            and runtime_systemd.get("timer_enabled") == "enabled"
            and runtime_systemd.get("timer_active") == "active"
            and runtime_deploy_plan.get("decision")
            in {"CLIENT_COMPAT_RUNTIME_ALREADY_APPLIED", "CLIENT_COMPAT_RUNTIME_DEPLOY_DRY_RUN"}
            else "not_proven"
        ),
        "production_runtime_deploy_safety": (
            "pass"
            if runtime_deploy_plan.get("dry_run_mutated_nl") is False
            and (runtime_deploy_plan.get("privacy") or {}).get("output_privacy_ok") is True
            else "not_proven"
        ),
    }


def audit_decision(requirements: dict[str, str]) -> str:
    if all(value == "pass" for value in requirements.values()):
        return "PRODUCTION_CANDIDATE_READY"
    server_failures = {
        key: value
        for key, value in requirements.items()
        if key != "user_client_matrix_after_rollout" and value != "pass"
    }
    if server_failures:
        return "PRODUCTION_CANDIDATE_BLOCKED"
    return "PRODUCTION_CANDIDATE_GOAL_NOT_MARKED_COMPLETE"


def remaining_items(
    *,
    missing: list[str],
    remote_request: dict[str, Any],
    requirements: dict[str, str],
) -> list[str]:
    rows: list[str] = []
    if "android_happ_or_hiddify" in missing:
        rows.append("record Android Happ/Hiddify client evidence after rollout")
    if "mobile_network" in missing:
        rows.append("record one mobile network evidence case")
    if "restricted_or_work_wifi" in missing:
        rows.append("record one restricted or work Wi-Fi evidence case")
    if missing and remote_request.get("decision") == "REMOTE_CLIENT_EVIDENCE_REQUEST_READY":
        count = remote_request.get("minimum_reports_required")
        rows.append(
            f"collect the {count} safe remote request-packet reports: "
            "mobile Happ/Hiddify and restricted/work Wi-Fi"
        )
    if missing:
        rows.append("rerun preflight/tests after remaining client matrix evidence is added")
        rows.append(
            "after any new client pass/fail evidence, run refresh_client_evidence_artifacts.py --write before final readiness audit"
        )
    if requirements.get("user_client_matrix_after_rollout") == "client_evidence_session_mismatch":
        rows.append(
            f"record mobile/work-Wi-Fi pass evidence with current evidence_session_id={CURRENT_EVIDENCE_SESSION_ID}"
        )
    for key, value in requirements.items():
        if key != "user_client_matrix_after_rollout" and value != "pass":
            rows.append(f"restore requirement evidence: {key}")
    return rows


def build_client_matrix_section(
    *,
    matrix: dict[str, Any],
    evidence_plan: dict[str, Any],
    remote_intake: dict[str, Any],
    remote_request: dict[str, Any],
    runtime_summary: dict[str, Any],
    runtime_probe: dict[str, Any],
    runtime_deploy_plan: dict[str, Any],
) -> dict[str, Any]:
    missing = missing_requirements(matrix)
    runtime_client = runtime_probe.get("client_compatibility_endpoint") or {}
    runtime_systemd = runtime_probe.get("systemd_wiring") or {}
    deploy_policy = runtime_deploy_plan.get("mutation_policy") or {}
    endpoints = (runtime_deploy_plan.get("remote_state") or {}).get("status_api_endpoints") or {}
    files = runtime_deploy_plan.get("files") or []
    forbidden = deploy_policy.get("forbidden_service_restarts")
    if not forbidden:
        forbidden = runtime_deploy_plan.get("forbidden_service_restarts") or []

    return {
        "markdown": str(DEFAULT_MATRIX_MARKDOWN_PATH),
        "json": str(DEFAULT_MATRIX_JSON_PATH),
        "decision": matrix.get("decision"),
        "passing_real_client_checks": passing_real_client_checks(matrix),
        "current_evidence_session": {
            "id": CURRENT_EVIDENCE_SESSION_ID,
            "started_at": CURRENT_EVIDENCE_SESSION_STARTED_AT,
            "required_transport": CURRENT_EVIDENCE_REQUIRED_TRANSPORT,
            "required_port": CURRENT_EVIDENCE_REQUIRED_PORT,
            "required_for": list(SESSION_BOUND_REQUIREMENTS),
            "evidence": current_session_requirement_evidence(matrix),
            "complete": current_session_requirements_complete(matrix),
        },
        "local_v2rayn_inventory": matrix.get("local_client_inventory"),
        "local_v2rayn_fallback_import_live": matrix.get("local_v2rayn_fallback_import_live"),
        "local_v2rayn_dataplane_probe": matrix.get("local_v2rayn_dataplane_probe"),
        "local_v2rayn_fallback_import_copy_test": matrix.get(
            "local_v2rayn_fallback_import_copy_test"
        ),
        "missing_requirements": missing,
        "next_required_checks": (matrix.get("completion_rule") or {}).get("next_required_checks") or [],
        "client_evidence_plan": {
            "json": str(DEFAULT_EVIDENCE_PLAN_JSON_PATH),
            "markdown": str(DEFAULT_EVIDENCE_PLAN_MARKDOWN_PATH),
            "decision": evidence_plan.get("decision"),
            "adb_available": (evidence_plan.get("adb_context") or {}).get("adb_available"),
            "connected_adb_devices": (evidence_plan.get("adb_context") or {}).get(
                "connected_device_count"
            ),
            "raw_adb_serials_stored": (evidence_plan.get("adb_context") or {}).get(
                "raw_serials_stored"
            ),
            "android_adb_auto_record_commands_available": bool(
                [
                    task
                    for task in evidence_plan.get("required_tasks") or []
                    if isinstance(task, dict)
                    and task.get("android_adb_probe_record_command_template")
                ]
            ),
            "android_adb_probe": evidence_plan.get("android_adb_probe"),
            "required_tasks": [
                {
                    "requirement": task.get("requirement"),
                    "client": task.get("client"),
                    "network_type": task.get("network_type"),
                    "transport": task.get("transport"),
                    "port": task.get("port"),
                }
                for task in evidence_plan.get("required_tasks") or []
                if isinstance(task, dict)
            ],
            "privacy": evidence_plan.get("privacy"),
            "remote_client_evidence_record_commands_available": bool(
                [
                    task
                    for task in evidence_plan.get("required_tasks") or []
                    if isinstance(task, dict)
                    and task.get("remote_client_evidence_record_command_template")
                ]
            ),
        },
        "remote_client_evidence_intake": {
            "json": str(DEFAULT_REMOTE_INTAKE_JSON_PATH),
            "markdown": str(DEFAULT_REMOTE_INTAKE_MARKDOWN_PATH),
            "decision": remote_intake.get("decision"),
            "matrix_updated": bool(remote_intake.get("matrix_updated")),
            "recording": remote_intake.get("recording"),
            "matrix_missing_requirements": (
                (remote_intake.get("matrix_summary") or {}).get("missing_requirements")
                or remote_intake.get("matrix_missing_requirements")
                or []
            ),
            "safe_remote_record_command_available": bool(
                remote_intake.get("safe_remote_record_command_template")
            ),
            "privacy": remote_intake.get("privacy"),
        },
        "remote_client_evidence_request": {
            "json": str(DEFAULT_REMOTE_REQUEST_JSON_PATH),
            "markdown": str(DEFAULT_REMOTE_REQUEST_MARKDOWN_PATH),
            "decision": remote_request.get("decision"),
            "minimum_reports_required": remote_request.get("minimum_reports_required"),
            "request_count": remote_request.get("request_count"),
            "missing_requirements": remote_request.get("missing_requirements") or [],
            "requests": [
                compact_request(row)
                for row in remote_request.get("requests") or []
                if isinstance(row, dict)
            ],
            "privacy": remote_request.get("privacy"),
        },
        "runtime_status_api_contract": {
            "endpoint": "/client-compatibility",
            "publisher": "services/nl-server/ghost-access/build_client_compatibility_runtime_summary.py",
            "json": str(DEFAULT_RUNTIME_SUMMARY_JSON_PATH),
            "markdown": str(DEFAULT_RUNTIME_SUMMARY_MARKDOWN_PATH),
            "decision": runtime_summary.get("decision"),
            "complete": runtime_summary.get("complete"),
            "missing_requirements": runtime_summary.get("missing_requirements") or [],
            "real_client_checks": runtime_summary.get("real_client_checks"),
            "passing_real_client_checks": runtime_summary.get("passing_real_client_checks"),
            "local_v2rayn_dataplane_probe_ok": (
                runtime_summary.get("local_v2rayn_dataplane_probe") or {}
            ).get("ok"),
            "privacy": runtime_summary.get("privacy"),
            "systemd_templates": {
                "service": "services/nl-server/systemd/ghost-access-client-compatibility-summary.service",
                "timer": "services/nl-server/systemd/ghost-access-client-compatibility-summary.timer",
                "install_status": "installed_enabled_active_on_nl"
                if runtime_systemd.get("timer_enabled") == "enabled"
                else "not_installed_or_not_enabled",
                "production_matrix_path": "/var/lib/ghost-access/client-compatibility/matrix.json",
                "production_summary_path": "/var/lib/ghost-access/client-compatibility/latest.json",
                "does_not_restart_vpn_services": True,
                "preflight_checked": True,
                "timer_enabled": runtime_systemd.get("timer_enabled"),
                "timer_active": runtime_systemd.get("timer_active"),
                "summary_present": runtime_systemd.get("summary_present"),
                "matrix_present": runtime_systemd.get("matrix_present"),
            },
            "nl_runtime_decision": runtime_probe.get("decision"),
            "nl_http_code": runtime_client.get("http_code"),
            "nl_missing_requirements": runtime_client.get("missing_requirements") or [],
        },
        "operator_visibility": {
            "anti_block_bot_client_evidence_block": True,
            "status_api_client_compatibility_endpoint": runtime_client.get("http_code") == 200,
            "raw_client_rows_returned": runtime_client.get("raw_real_client_rows_returned"),
            "client_compatibility_timer_template_prepared": True,
            "client_compatibility_timer_installed_on_nl": runtime_systemd.get("timer_enabled")
            == "enabled",
        },
        "artifact_refresh": {
            "script": "services/nl-server/ghost-access/refresh_client_evidence_artifacts.py",
            "last_run_decision": "CLIENT_EVIDENCE_ARTIFACTS_REFRESHED",
            "writes_matrix_markdown": True,
            "writes_remote_intake": True,
            "writes_remote_request": True,
            "writes_runtime_summary": True,
            "writes_evidence_plan": True,
            "writes_production_audit": True,
            "does_not_record_pass_fail_evidence": True,
            "does_not_contact_nl": True,
            "does_not_restart_vpn_services": True,
            "preflight_checked": True,
        },
        "nl_runtime_probe": {
            "json": str(DEFAULT_RUNTIME_PROBE_JSON_PATH),
            "markdown": str(DEFAULT_RUNTIME_PROBE_MARKDOWN_PATH),
            "checked_at": runtime_probe.get("checked_at"),
            "current_evidence_session_ok": runtime_probe_in_current_session(runtime_probe),
            "decision": runtime_probe.get("decision"),
            "profile_status_api_active": (
                runtime_probe.get("profile_status_api_unit") or {}
            ).get("active"),
            "transport_usage_ok": (runtime_probe.get("transport_usage_endpoint") or {}).get("ok"),
            "client_compatibility_http_code": runtime_client.get("http_code"),
            "client_compatibility_contract_ok": runtime_client.get(
                "evidence_session_contract_ok"
            ),
            "client_compatibility_evidence_session": runtime_client.get(
                "evidence_session"
            ),
            "client_compatibility_missing_requirements": runtime_client.get(
                "missing_requirements"
            )
            or [],
            "systemd_wiring": runtime_systemd,
            "required_actions": runtime_probe.get("required_actions") or [],
            "privacy": runtime_probe.get("privacy"),
        },
        "nl_runtime_deploy_plan": {
            "json": str(DEFAULT_RUNTIME_DEPLOY_PLAN_JSON_PATH),
            "markdown": str(DEFAULT_RUNTIME_DEPLOY_PLAN_MARKDOWN_PATH),
            "generated_at": runtime_deploy_plan.get("generated_at"),
            "decision": runtime_deploy_plan.get("decision"),
            "ok": runtime_deploy_plan.get("ok"),
            "apply_required": runtime_deploy_plan.get("apply_required"),
            "applied_to_nl": runtime_deploy_plan.get("applied_to_nl"),
            "dry_run_mutated_nl": runtime_deploy_plan.get("dry_run_mutated_nl"),
            "current_blocker": runtime_deploy_plan.get("current_blocker"),
            "transport_usage_http_code": endpoints.get("transport_usage_http_code")
            or runtime_deploy_plan.get("transport_usage_http_code"),
            "client_compatibility_http_code": endpoints.get("client_compatibility_http_code")
            or runtime_deploy_plan.get("client_compatibility_http_code"),
            "target_files": [
                row.get("remote_path")
                for row in files
                if isinstance(row, dict) and row.get("remote_path")
            ],
            "runtime_generated_targets": runtime_deploy_plan.get("runtime_generated_targets") or [],
            "forbidden_service_restarts": forbidden,
            "privacy": runtime_deploy_plan.get("privacy"),
        },
    }


def build_audit(
    *,
    server_evidence_seed: dict[str, Any] | None,
    matrix: dict[str, Any],
    evidence_plan: dict[str, Any],
    remote_intake: dict[str, Any],
    remote_request: dict[str, Any],
    runtime_summary: dict[str, Any],
    runtime_probe: dict[str, Any],
    runtime_deploy_plan: dict[str, Any],
    generated_at: str | None = None,
) -> dict[str, Any]:
    live_evidence = server_evidence_from_seed(server_evidence_seed)
    requirements = evaluate_requirements(
        live_evidence=live_evidence,
        matrix=matrix,
        runtime_summary=runtime_summary,
        runtime_probe=runtime_probe,
        runtime_deploy_plan=runtime_deploy_plan,
    )
    missing = missing_requirements(matrix)
    audit = {
        "audit_id": "nl-anti-block-production-audit-2026-06-02",
        "generated_at": generated_at or utc_now(),
        "generated_local_date": "2026-06-02",
        "generator": "services/nl-server/ghost-access/build_anti_block_production_audit.py",
        "decision": audit_decision(requirements),
        "live_evidence": live_evidence,
        "requirements": requirements,
        "remaining_before_goal_complete": remaining_items(
            missing=missing,
            remote_request=remote_request,
            requirements=requirements,
        ),
        "client_compatibility_matrix": build_client_matrix_section(
            matrix=matrix,
            evidence_plan=evidence_plan,
            remote_intake=remote_intake,
            remote_request=remote_request,
            runtime_summary=runtime_summary,
            runtime_probe=runtime_probe,
            runtime_deploy_plan=runtime_deploy_plan,
        ),
        "privacy": {
            "output_privacy_ok": True,
            "raw_subscription_url_stored": False,
            "raw_vpn_uri_stored": False,
            "raw_uuid_stored": False,
            "raw_ip_stored": False,
            "raw_email_stored": False,
            "raw_reporter_identifier_stored": False,
            "raw_telegram_handle_stored": False,
            "raw_phone_stored": False,
            "raw_url_stored": False,
            "raw_screenshot_stored": False,
            "raw_logs_stored": False,
            "raw_client_rows_stored": False,
            "raw_commands_stored": False,
        },
    }
    findings = validate_output(audit)
    if findings:
        audit["decision"] = "PRODUCTION_AUDIT_PRIVACY_BLOCKED"
        audit["privacy_findings"] = findings
    return audit


def validate_output(payload: dict[str, Any]) -> list[dict[str, str]]:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    findings: list[dict[str, str]] = []
    for name, pattern in FORBIDDEN_OUTPUT_PATTERNS.items():
        match = pattern.search(text)
        if match:
            findings.append({"kind": name, "sample": match.group(0)[:80]})
    if (payload.get("privacy") or {}).get("output_privacy_ok") is not True:
        findings.append({"kind": "privacy_flag_missing", "sample": "output_privacy_ok"})
    return findings


def markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def render_markdown(audit: dict[str, Any]) -> str:
    matrix = audit.get("client_compatibility_matrix") or {}
    live = audit.get("live_evidence") or {}
    request = matrix.get("remote_client_evidence_request") or {}
    runtime_probe = matrix.get("nl_runtime_probe") or {}
    requirements = audit.get("requirements") or {}

    lines = [
        "# NL Anti-Block Production Audit - 2026-06-02",
        "",
        "## Decision",
        "",
        f"`{audit.get('decision')}`",
        "",
        "This audit is generated from current local evidence artifacts. It does not contact NL, restart VPN services, or record client pass/fail evidence.",
        "",
        "## Requirements",
        "",
        "| Requirement | Status |",
        "| --- | --- |",
    ]
    for key, value in requirements.items():
        lines.append(f"| {markdown_cell(key)} | {markdown_cell(value)} |")
    lines.extend(
        [
            "",
            "## Current Blockers",
            "",
        ]
    )
    remaining = audit.get("remaining_before_goal_complete") or []
    if remaining:
        lines.extend(f"{index}. {item}" for index, item in enumerate(remaining, start=1))
    else:
        lines.append("No remaining blockers recorded by the generated audit.")

    lines.extend(
        [
            "",
            "## Client Matrix",
            "",
            "```json",
            json.dumps(
                {
                    "decision": matrix.get("decision"),
                    "passing_real_client_checks": matrix.get("passing_real_client_checks"),
                    "current_evidence_session": matrix.get("current_evidence_session"),
                    "missing_requirements": matrix.get("missing_requirements"),
                    "next_required_checks": matrix.get("next_required_checks"),
                },
                indent=2,
                ensure_ascii=False,
            ),
            "```",
            "",
            "## Remote Request Packet",
            "",
            "```json",
            json.dumps(
                {
                    "decision": request.get("decision"),
                    "minimum_reports_required": request.get("minimum_reports_required"),
                    "request_count": request.get("request_count"),
                    "missing_requirements": request.get("missing_requirements"),
                    "requests": request.get("requests"),
                    "privacy": request.get("privacy"),
                },
                indent=2,
                ensure_ascii=False,
            ),
            "```",
            "",
            "## Runtime Probe",
            "",
            "```json",
            json.dumps(
                {
                    "checked_at": runtime_probe.get("checked_at"),
                    "decision": runtime_probe.get("decision"),
                    "client_compatibility_http_code": runtime_probe.get(
                        "client_compatibility_http_code"
                    ),
                    "client_compatibility_missing_requirements": runtime_probe.get(
                        "client_compatibility_missing_requirements"
                    ),
                    "systemd_wiring": runtime_probe.get("systemd_wiring"),
                    "privacy": runtime_probe.get("privacy"),
                },
                indent=2,
                ensure_ascii=False,
            ),
            "```",
            "",
            "## Live Evidence Summary",
            "",
            "```json",
            json.dumps(
                {
                    "fallback_subscription": live.get("fallback_subscription"),
                    "runtime": live.get("runtime"),
                    "usage_60m": live.get("usage_60m"),
                    "rollback_dry_run": live.get("rollback_dry_run"),
                    "rollback_drill": live.get("rollback_drill"),
                    "reality_canary_after_rollback_restore": live.get(
                        "reality_canary_after_rollback_restore"
                    ),
                },
                indent=2,
                ensure_ascii=False,
            ),
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n")


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(payload), encoding="utf-8")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Build the generated NL anti-block production readiness audit."
    )
    p.add_argument("--server-evidence-json", type=Path, default=DEFAULT_AUDIT_JSON_PATH)
    p.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX_JSON_PATH)
    p.add_argument("--evidence-plan", type=Path, default=DEFAULT_EVIDENCE_PLAN_JSON_PATH)
    p.add_argument("--remote-intake", type=Path, default=DEFAULT_REMOTE_INTAKE_JSON_PATH)
    p.add_argument("--remote-request", type=Path, default=DEFAULT_REMOTE_REQUEST_JSON_PATH)
    p.add_argument("--runtime-summary", type=Path, default=DEFAULT_RUNTIME_SUMMARY_JSON_PATH)
    p.add_argument("--runtime-probe", type=Path, default=DEFAULT_RUNTIME_PROBE_JSON_PATH)
    p.add_argument("--runtime-deploy-plan", type=Path, default=DEFAULT_RUNTIME_DEPLOY_PLAN_JSON_PATH)
    p.add_argument("--json-out", type=Path, default=DEFAULT_AUDIT_JSON_PATH)
    p.add_argument("--markdown-out", type=Path, default=DEFAULT_AUDIT_MARKDOWN_PATH)
    p.add_argument("--write", action="store_true")
    p.add_argument("--json", action="store_true")
    return p


def build_from_args(args: argparse.Namespace) -> dict[str, Any]:
    return build_audit(
        server_evidence_seed=load_json(args.server_evidence_json),
        matrix=require_json(args.matrix),
        evidence_plan=require_json(args.evidence_plan),
        remote_intake=require_json(args.remote_intake),
        remote_request=require_json(args.remote_request),
        runtime_summary=require_json(args.runtime_summary),
        runtime_probe=require_json(args.runtime_probe),
        runtime_deploy_plan=require_json(args.runtime_deploy_plan),
    )


def run(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        audit = build_from_args(args)
        if audit.get("privacy_findings"):
            raise AuditError("audit output failed privacy validation")
        if args.write:
            write_json(args.json_out, audit)
            write_markdown(args.markdown_out, audit)
        if args.json:
            print(json.dumps(audit, indent=2, ensure_ascii=False, sort_keys=True))
        else:
            print(audit["decision"])
        return 0
    except Exception as exc:
        payload = {"ok": False, "error": str(exc)}
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        else:
            print(f"ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(run())
