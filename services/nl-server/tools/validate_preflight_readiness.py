#!/usr/bin/env python3
from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[1]
MANIFEST = ROOT / "manifest.json"

REQUIRED_FILES = [
    ROOT / "mesh-runtime" / "health_action_policy.py",
    ROOT / "mesh-runtime" / "health_check.sh",
    ROOT / "mesh-runtime" / "health_check_readonly.sh",
    ROOT / "mesh-runtime" / "health_heal_xui.sh",
    ROOT / "ghost-access" / "run_vpn_delivery_canary.py",
    ROOT / "ghost-access" / "check_live_subscription_payload.py",
    ROOT / "ghost-access" / "run_vpn_service_access_agent.py",
    ROOT / "ghost-access" / "collect_transport_usage_evidence.py",
    ROOT / "ghost-access" / "rollback_ghost_fallbacks.py",
    ROOT / "ghost-access" / "record_client_compatibility.py",
    ROOT / "ghost-access" / "record_remote_client_evidence.py",
    ROOT / "ghost-access" / "record_remote_client_evidence_reply.py",
    ROOT / "ghost-access" / "build_client_compatibility_runtime_summary.py",
    ROOT / "ghost-access" / "refresh_client_evidence_artifacts.py",
    ROOT / "ghost-access" / "build_anti_block_production_audit.py",
    ROOT / "ghost-access" / "probe_nl_client_compatibility_runtime.py",
    ROOT / "ghost-access" / "plan_client_compatibility_runtime_deploy.py",
    ROOT / "ghost-access" / "build_remote_client_evidence_request_packet.py",
    ROOT / "ghost-access" / "build_client_evidence_plan.py",
    ROOT / "ghost-access" / "probe_android_adb_vpn.py",
    ROOT / "ghost-access" / "inspect_v2rayn_client_inventory.py",
    ROOT / "ghost-access" / "sync_v2rayn_subscription_fallbacks.py",
    ROOT / "ghost-access" / "probe_v2rayn_imported_fallbacks.py",
    ROOT / "ghost-access" / "sync_ghost_https_ws_clients.py",
    ROOT / "ghost-access" / "send_legacy_no_progress_nudge.py",
    ROOT / "ghost-access" / "xray_runtime_user_manager.py",
    ROOT / "ghost-access" / "xui_client_manager.py",
    ROOT / "tests" / "test_current_nl_runtime_source.py",
    ROOT / "tests" / "test_check_live_subscription_payload.py",
    ROOT / "tests" / "test_health_action_policy.py",
    ROOT / "tests" / "test_live_subscription_payload_systemd_templates.py",
    ROOT / "tests" / "test_listener_and_profile_hint.py",
    ROOT / "tests" / "test_activity_sync_and_tcp_bridge.py",
    ROOT / "tests" / "test_transport_usage_evidence.py",
    ROOT / "tests" / "test_rollback_ghost_fallbacks.py",
    ROOT / "tests" / "test_record_client_compatibility.py",
    ROOT / "tests" / "test_record_remote_client_evidence.py",
    ROOT / "tests" / "test_record_remote_client_evidence_reply.py",
    ROOT / "tests" / "test_build_client_compatibility_runtime_summary.py",
    ROOT / "tests" / "test_refresh_client_evidence_artifacts.py",
    ROOT / "tests" / "test_build_anti_block_production_audit.py",
    ROOT / "tests" / "test_probe_nl_client_compatibility_runtime.py",
    ROOT / "tests" / "test_plan_client_compatibility_runtime_deploy.py",
    ROOT / "tests" / "test_build_remote_client_evidence_request_packet.py",
    ROOT / "tests" / "test_build_client_evidence_plan.py",
    ROOT / "tests" / "test_probe_android_adb_vpn.py",
    ROOT / "tests" / "test_inspect_v2rayn_client_inventory.py",
    ROOT / "tests" / "test_sync_v2rayn_subscription_fallbacks.py",
    ROOT / "tests" / "test_probe_v2rayn_imported_fallbacks.py",
    ROOT / "tests" / "test_telegram_bot_anti_block_source.py",
    ROOT / "tests" / "test_client_compatibility_systemd_templates.py",
    ROOT / "tests" / "test_send_legacy_no_progress_nudge.py",
    ROOT / "tests" / "test_legacy_no_progress_nudge_dry_run_systemd_templates.py",
    ROOT / "tests" / "test_ghost_vpn_runtime_source.py",
    ROOT / "tests" / "test_auto_monitor_source.py",
    ROOT / "tests" / "test_apply_config_auto_source.py",
    ROOT / "tests" / "test_full_stealth_config_source.py",
    ROOT / "tests" / "test_rotation_timer_source.py",
    ROOT / "tests" / "test_spb_standalone_sync_source.py",
    ROOT / "tests" / "test_templates.py",
    ROOT / "templates" / "nl-beta-2443.example.json",
    ROOT / "templates" / "nl-beta-2443.example.json.meta.json",
    ROOT / "systemd" / "ghost-access-client-compatibility-summary.service",
    ROOT / "systemd" / "ghost-access-client-compatibility-summary.timer",
    ROOT / "systemd" / "ghost-access-live-subscription-payload-check.service",
    ROOT / "systemd" / "ghost-access-live-subscription-payload-check.timer",
    ROOT / "systemd" / "ghost-access-legacy-no-progress-nudge-dry-run.service",
    ROOT / "systemd" / "ghost-access-legacy-no-progress-nudge-dry-run.timer",
    WORKSPACE / "nl-diagnostics" / "nl-deploy-preflight-checklist-2026-05-27.md",
    WORKSPACE / "nl-diagnostics" / "nl-mutation-gate-design-2026-05-27.md",
    WORKSPACE / "nl-diagnostics" / "nl-anti-block-client-compatibility-matrix-2026-06-02.json",
    WORKSPACE / "nl-diagnostics" / "nl-anti-block-client-compatibility-matrix-2026-06-02.md",
    WORKSPACE / "nl-diagnostics" / "nl-anti-block-client-evidence-plan-2026-06-02.json",
    WORKSPACE / "nl-diagnostics" / "nl-anti-block-client-evidence-plan-2026-06-02.md",
    WORKSPACE / "nl-diagnostics" / "nl-anti-block-android-adb-probe-2026-06-02.json",
    WORKSPACE / "nl-diagnostics" / "nl-anti-block-android-adb-probe-2026-06-02.md",
    WORKSPACE / "nl-diagnostics" / "nl-anti-block-remote-client-evidence-intake-2026-06-02.json",
    WORKSPACE / "nl-diagnostics" / "nl-anti-block-remote-client-evidence-intake-2026-06-02.md",
    WORKSPACE / "nl-diagnostics" / "nl-anti-block-client-compatibility-runtime-summary-2026-06-02.json",
    WORKSPACE / "nl-diagnostics" / "nl-anti-block-client-compatibility-runtime-summary-2026-06-02.md",
    WORKSPACE / "nl-diagnostics" / "nl-anti-block-client-compatibility-runtime-probe-2026-06-02.json",
    WORKSPACE / "nl-diagnostics" / "nl-anti-block-client-compatibility-runtime-probe-2026-06-02.md",
    WORKSPACE / "nl-diagnostics" / "nl-anti-block-client-compatibility-runtime-deploy-plan-2026-06-02.json",
    WORKSPACE / "nl-diagnostics" / "nl-anti-block-client-compatibility-runtime-deploy-plan-2026-06-02.md",
    WORKSPACE / "nl-diagnostics" / "nl-anti-block-remote-client-evidence-request-2026-06-02.json",
    WORKSPACE / "nl-diagnostics" / "nl-anti-block-remote-client-evidence-request-2026-06-02.md",
    WORKSPACE / "nl-diagnostics" / "nl-anti-block-production-audit-2026-06-02.json",
    WORKSPACE / "nl-diagnostics" / "nl-anti-block-production-audit-2026-06-02.md",
]

READONLY_FORBIDDEN = re.compile(
    r"\b(systemctl|service|restart|reload|scp|rsync|install|mv|rm|cp|sqlite3)\b"
)
MATRIX_SECRET_PATTERNS = {
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
CURRENT_EVIDENCE_SESSION_ID = "nl-anti-block-2026-06-02"
CURRENT_EVIDENCE_SESSION_STARTED_AT = "2026-06-02T00:00:00Z"
CURRENT_EVIDENCE_REQUIRED_TRANSPORT = "reality"
CURRENT_EVIDENCE_REQUIRED_PORT = 443


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return str(path.relative_to(WORKSPACE))


def fail(checks: list[dict[str, Any]], name: str, reason: str) -> None:
    checks.append({"name": name, "ok": False, "reason": reason})


def ok(checks: list[dict[str, Any]], name: str, reason: str = "ok") -> None:
    checks.append({"name": name, "ok": True, "reason": reason})


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


def timestamp_in_current_evidence_session(value: str) -> bool:
    parsed = parse_utc_datetime(value)
    started = parse_utc_datetime(CURRENT_EVIDENCE_SESSION_STARTED_AT)
    return parsed is not None and started is not None and parsed >= started


def iter_manifest_files(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    source = manifest.get("source_promotion_status") or {}
    rows: list[dict[str, Any]] = []
    for key in ("promoted_files", "local_policy_files", "redacted_templates"):
        values = source.get(key) or []
        if isinstance(values, list):
            rows.extend(item for item in values if isinstance(item, dict))
    return rows


def main() -> int:
    checks: list[dict[str, Any]] = []

    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        ok(checks, "manifest_json")
    except Exception as exc:
        fail(checks, "manifest_json", str(exc))
        print(json.dumps({"ok": False, "checks": checks}, indent=2))
        return 1

    if manifest.get("nl_write_allowed") is False:
        ok(checks, "nl_write_allowed_false")
    else:
        fail(checks, "nl_write_allowed_false", "manifest must keep nl_write_allowed=false")

    source_status = manifest.get("source_promotion_status") or {}
    if source_status.get("deployable_to_nl") is False:
        ok(checks, "deployable_to_nl_false")
    else:
        fail(checks, "deployable_to_nl_false", "local artifacts must not be marked deployable")

    inactive_integrations = manifest.get("inactive_integrations") or []
    spb = next(
        (
            item
            for item in inactive_integrations
            if isinstance(item, dict) and item.get("name") == "spb_standalone_xray"
        ),
        None,
    )
    if spb and spb.get("enabled") is False:
        ok(checks, "spb_integration_disabled")
    else:
        fail(checks, "spb_integration_disabled", "SPB standalone integration must remain disabled")

    promoted_rows = source_status.get("promoted_files") or []
    spb_sync = next(
        (
            item
            for item in promoted_rows
            if isinstance(item, dict)
            and item.get("path") == "services/nl-server/ghost-access/sync_spb_standalone_clients.py"
        ),
        None,
    )
    if spb_sync and spb_sync.get("deployable_to_nl") is False:
        ok(checks, "spb_sync_not_deployable")
    else:
        fail(checks, "spb_sync_not_deployable", "SPB sync source must stay non-deployable")
    if spb_sync and spb_sync.get("operational_status") == "inactive_spb_disabled":
        ok(checks, "spb_sync_marked_inactive")
    else:
        fail(checks, "spb_sync_marked_inactive", "SPB sync source must be marked inactive")

    accepted_deltas = manifest.get("accepted_local_deltas") or []
    if accepted_deltas:
        ok(checks, "accepted_local_deltas_present")
    else:
        fail(checks, "accepted_local_deltas_present", "expected accepted local deltas for intentional NL drift")
    for row in accepted_deltas:
        if not isinstance(row, dict):
            fail(checks, "accepted_local_delta_shape", "row is not an object")
            continue
        local_path = row.get("local_path")
        expected_hash = row.get("local_sha256")
        if row.get("deployable_to_nl") is not False:
            fail(checks, f"accepted_delta_not_deployable:{local_path}", "must be deployable_to_nl=false")
        else:
            ok(checks, f"accepted_delta_not_deployable:{local_path}")
        if local_path and expected_hash:
            path = WORKSPACE / str(local_path)
            if path.exists() and sha256(path) == expected_hash:
                ok(checks, f"accepted_delta_hash:{local_path}")
            else:
                fail(checks, f"accepted_delta_hash:{local_path}", "local file missing or hash mismatch")

    for path in REQUIRED_FILES:
        if path.exists():
            ok(checks, f"exists:{rel(path)}")
        else:
            fail(checks, f"exists:{rel(path)}", "missing")

    manifest_rows = iter_manifest_files(manifest)
    for row in manifest_rows:
        path_value = row.get("path")
        expected = row.get("sha256")
        if not path_value or not expected:
            fail(checks, f"manifest_hash:{path_value}", "missing path or sha256")
            continue
        path = WORKSPACE / str(path_value)
        if not path.exists():
            fail(checks, f"manifest_hash:{path_value}", "file missing")
            continue
        actual = sha256(path)
        if actual == expected:
            ok(checks, f"manifest_hash:{path_value}")
        else:
            fail(checks, f"manifest_hash:{path_value}", f"expected {expected}, got {actual}")

    readonly = ROOT / "mesh-runtime" / "health_check_readonly.sh"
    if readonly.exists():
        text = readonly.read_text(encoding="utf-8")
        match = READONLY_FORBIDDEN.search(text)
        if match:
            fail(checks, "readonly_wrapper_has_no_mutation_commands", f"found {match.group(1)}")
        else:
            ok(checks, "readonly_wrapper_has_no_mutation_commands")

    heal = ROOT / "mesh-runtime" / "health_heal_xui.sh"
    if heal.exists():
        text = heal.read_text(encoding="utf-8")
        for token in ("NL_XUI_RESTART_APPROVED", "NL_HEAL_EXECUTE", "health_action_policy.py"):
            if token in text:
                ok(checks, f"heal_wrapper_contains:{token}")
            else:
                fail(checks, f"heal_wrapper_contains:{token}", "missing")

    status_api = ROOT / "mesh-runtime" / "profile_status_api.py"
    if status_api.exists():
        text = status_api.read_text(encoding="utf-8")
        for token in (
            "CLIENT_COMPATIBILITY_PATH",
            "build_client_compatibility",
            'if path == "/client-compatibility"',
            "raw_real_client_rows_returned",
            "_safe_evidence_session",
            "required_transport",
            "required_port",
        ):
            if token in text:
                ok(checks, f"profile_status_api_contains:{token}")
            else:
                fail(checks, f"profile_status_api_contains:{token}", "missing")

    bot_source = ROOT / "redacted" / "ghost-access" / "telegram_bot_simple.redacted.py"
    if bot_source.exists():
        text = bot_source.read_text(encoding="utf-8")
        for token in (
            "render_client_compatibility_block()",
            'load_profile_status_api("/client-compatibility")',
            "Client evidence:",
            "Android Happ/Hiddify",
        ):
            if token in text:
                ok(checks, f"anti_block_bot_contains:{token}")
            else:
                fail(checks, f"anti_block_bot_contains:{token}", "missing")

    client_compat_service = ROOT / "systemd" / "ghost-access-client-compatibility-summary.service"
    client_compat_timer = ROOT / "systemd" / "ghost-access-client-compatibility-summary.timer"
    if client_compat_service.exists():
        text = client_compat_service.read_text(encoding="utf-8")
        for token in (
            "build_client_compatibility_runtime_summary.py",
            "/opt/x0tta6bl4-mesh/scripts/build_client_compatibility_runtime_summary.py",
            "--matrix /var/lib/ghost-access/client-compatibility/matrix.json",
            "--json-out /var/lib/ghost-access/client-compatibility/latest.json",
            "ConditionPathExists=/var/lib/ghost-access/client-compatibility/matrix.json",
            "ReadWritePaths=/var/lib/ghost-access/client-compatibility",
            "ReadOnlyPaths=/opt/x0tta6bl4-mesh/scripts",
            "ProtectSystem=strict",
            "NoNewPrivileges=true",
        ):
            if token in text:
                ok(checks, f"client_compat_systemd_service_contains:{token}")
            else:
                fail(checks, f"client_compat_systemd_service_contains:{token}", "missing")
        forbidden = [
            "systemctl restart",
            "systemctl reload",
            "x-ui",
            "nginx",
            "telegram-bot-simple",
            "ghost-access-nl-xhttp",
            "ghost-access-nl-https-ws",
        ]
        leaked = [token for token in forbidden if token in text]
        if leaked:
            fail(checks, "client_compat_systemd_service_no_vpn_mutation", ",".join(leaked))
        else:
            ok(checks, "client_compat_systemd_service_no_vpn_mutation")
    if client_compat_timer.exists():
        text = client_compat_timer.read_text(encoding="utf-8")
        for token in (
            "Unit=ghost-access-client-compatibility-summary.service",
            "OnBootSec=2min",
            "OnUnitActiveSec=2min",
            "Persistent=true",
        ):
            if token in text:
                ok(checks, f"client_compat_systemd_timer_contains:{token}")
            else:
                fail(checks, f"client_compat_systemd_timer_contains:{token}", "missing")

    client_matrix_recorder_source = ROOT / "ghost-access" / "record_client_compatibility.py"
    if client_matrix_recorder_source.exists():
        text = client_matrix_recorder_source.read_text(encoding="utf-8")
        for token in (
            "CURRENT_EVIDENCE_SESSION_ID",
            "CURRENT_EVIDENCE_SESSION_STARTED_AT",
            "CURRENT_EVIDENCE_REQUIRED_TRANSPORT",
            "CURRENT_EVIDENCE_REQUIRED_PORT",
            "required_rollout_transport_ok",
            "session-bound pass evidence must use",
        ):
            if token in text:
                ok(checks, f"client_matrix_recorder_contains:{token}")
            else:
                fail(checks, f"client_matrix_recorder_contains:{token}", "missing")

    refresh_evidence = ROOT / "ghost-access" / "refresh_client_evidence_artifacts.py"
    if refresh_evidence.exists():
        text = refresh_evidence.read_text(encoding="utf-8")
        for token in (
            "record_client_compatibility.py",
            "record_remote_client_evidence.py",
            "build_client_compatibility_runtime_summary.py",
            "build_client_evidence_plan.py",
            "build_remote_client_evidence_request_packet.py",
            "build_anti_block_production_audit.py",
            "CLIENT_EVIDENCE_ARTIFACTS_REFRESHED",
            "production_audit_decision",
            "raw_real_client_rows_returned",
        ):
            if token in text:
                ok(checks, f"client_evidence_refresh_contains:{token}")
            else:
                fail(checks, f"client_evidence_refresh_contains:{token}", "missing")

    production_audit_source = ROOT / "ghost-access" / "build_anti_block_production_audit.py"
    if production_audit_source.exists():
        text = production_audit_source.read_text(encoding="utf-8")
        for token in (
            "PRODUCTION_CANDIDATE_GOAL_NOT_MARKED_COMPLETE",
            "PRODUCTION_CANDIDATE_READY",
            "PRODUCTION_CANDIDATE_BLOCKED",
            "remaining_before_goal_complete",
            "REMOTE_CLIENT_EVIDENCE_REQUEST_READY",
            "raw_client_rows_stored",
            "writes_production_audit",
            "CURRENT_EVIDENCE_REQUIRED_TRANSPORT",
            "CURRENT_EVIDENCE_REQUIRED_PORT",
            "required_rollout_transport_ok",
            "runtime_probe_in_current_session",
        ):
            if token in text:
                ok(checks, f"production_audit_builder_contains:{token}")
            else:
                fail(checks, f"production_audit_builder_contains:{token}", "missing")

    runtime_probe_source = ROOT / "ghost-access" / "probe_nl_client_compatibility_runtime.py"
    if runtime_probe_source.exists():
        text = runtime_probe_source.read_text(encoding="utf-8")
        for token in (
            "/client-compatibility",
            "/transport-usage",
            "NL_CLIENT_COMPAT_RUNTIME_ENDPOINT_MISSING",
            "deploy_profile_status_api_client_compatibility_endpoint",
            "publish_current_client_compatibility_contract",
            "evidence_session_contract_ok",
            "CURRENT_EVIDENCE_REQUIRED_TRANSPORT",
            "CURRENT_EVIDENCE_REQUIRED_PORT",
            "raw_ssh_config_stored",
            "raw_client_rows_stored",
        ):
            if token in text:
                ok(checks, f"client_compat_runtime_probe_contains:{token}")
            else:
                fail(checks, f"client_compat_runtime_probe_contains:{token}", "missing")

    runtime_deploy_source = ROOT / "ghost-access" / "plan_client_compatibility_runtime_deploy.py"
    if runtime_deploy_source.exists():
        text = runtime_deploy_source.read_text(encoding="utf-8")
        for token in (
            "CLIENT_COMPAT_RUNTIME_DEPLOY_DRY_RUN",
            "DEPLOY_CLIENT_COMPAT_RUNTIME",
            "RESTART_PROFILE_STATUS_API",
            "forbidden_service_restarts",
            "/opt/x0tta6bl4-mesh/scripts/profile_status_api.py",
            "/opt/x0tta6bl4-mesh/scripts/build_client_compatibility_runtime_summary.py",
            "/var/lib/ghost-access/client-compatibility/matrix.json",
            "dry_run_mutated_nl",
        ):
            if token in text:
                ok(checks, f"client_compat_runtime_deploy_contains:{token}")
            else:
                fail(checks, f"client_compat_runtime_deploy_contains:{token}", "missing")

    remote_request_source = ROOT / "ghost-access" / "build_remote_client_evidence_request_packet.py"
    if remote_request_source.exists():
        text = remote_request_source.read_text(encoding="utf-8")
        for token in (
            "REMOTE_CLIENT_EVIDENCE_REQUEST_READY",
            "minimum_reports_required",
            "tester_message",
            "operator_record_pass_command",
            "operator_reply_record_pass_command",
            "--refresh-artifacts",
            "CURRENT_EVIDENCE_SESSION_ID",
            "CURRENT_EVIDENCE_SESSION_STARTED_AT",
            "evidence_session_id",
            "evidence_session_started_at",
            "--evidence-session-id",
            "record_remote_client_evidence.py",
            "record_remote_client_evidence_reply.py",
            "safe_reply_options",
            "raw_screenshot_stored",
            "raw_logs_stored",
            "--transport {transport}",
            "--port {port",
        ):
            if token in text:
                ok(checks, f"remote_client_evidence_request_contains:{token}")
            else:
                fail(checks, f"remote_client_evidence_request_contains:{token}", "missing")

    remote_reply_source = ROOT / "ghost-access" / "record_remote_client_evidence_reply.py"
    if remote_reply_source.exists():
        text = remote_reply_source.read_text(encoding="utf-8")
        for token in (
            "REMOTE_CLIENT_EVIDENCE_REPLY_RECORDED",
            "REMOTE_CLIENT_EVIDENCE_REPLY_VALIDATED",
            "parse_reply",
            "pass connected",
            "fail no-internet",
            "raw_reply_stored",
            "artifact_refresh",
            "evidence_session_id",
            "record_remote_client_evidence.py",
            "refresh_client_evidence_artifacts.py",
            "refresh_artifacts_required",
            "record_matrix_not_requested",
            "MAX_REPLY_BYTES",
            "reply is too long",
            "validate_write_requires_sha256",
            "validate_write_reply_source",
            "--expect-request-packet-sha256 is required with --write",
            "--write requires --reply-stdin or --reply-file",
        ):
            if token in text:
                ok(checks, f"remote_client_evidence_reply_contains:{token}")
            else:
                fail(checks, f"remote_client_evidence_reply_contains:{token}", "missing")

    matrix_json = WORKSPACE / "nl-diagnostics" / "nl-anti-block-client-compatibility-matrix-2026-06-02.json"
    matrix_md = WORKSPACE / "nl-diagnostics" / "nl-anti-block-client-compatibility-matrix-2026-06-02.md"
    evidence_plan_json = WORKSPACE / "nl-diagnostics" / "nl-anti-block-client-evidence-plan-2026-06-02.json"
    evidence_plan_md = WORKSPACE / "nl-diagnostics" / "nl-anti-block-client-evidence-plan-2026-06-02.md"
    android_adb_probe_json = WORKSPACE / "nl-diagnostics" / "nl-anti-block-android-adb-probe-2026-06-02.json"
    android_adb_probe_md = WORKSPACE / "nl-diagnostics" / "nl-anti-block-android-adb-probe-2026-06-02.md"
    remote_intake_json = (
        WORKSPACE
        / "nl-diagnostics"
        / "nl-anti-block-remote-client-evidence-intake-2026-06-02.json"
    )
    remote_intake_md = (
        WORKSPACE
        / "nl-diagnostics"
        / "nl-anti-block-remote-client-evidence-intake-2026-06-02.md"
    )
    remote_request_json = (
        WORKSPACE
        / "nl-diagnostics"
        / "nl-anti-block-remote-client-evidence-request-2026-06-02.json"
    )
    remote_request_md = (
        WORKSPACE
        / "nl-diagnostics"
        / "nl-anti-block-remote-client-evidence-request-2026-06-02.md"
    )
    runtime_summary_json = (
        WORKSPACE
        / "nl-diagnostics"
        / "nl-anti-block-client-compatibility-runtime-summary-2026-06-02.json"
    )
    runtime_summary_md = (
        WORKSPACE
        / "nl-diagnostics"
        / "nl-anti-block-client-compatibility-runtime-summary-2026-06-02.md"
    )
    runtime_probe_json = (
        WORKSPACE
        / "nl-diagnostics"
        / "nl-anti-block-client-compatibility-runtime-probe-2026-06-02.json"
    )
    runtime_probe_md = (
        WORKSPACE
        / "nl-diagnostics"
        / "nl-anti-block-client-compatibility-runtime-probe-2026-06-02.md"
    )
    runtime_deploy_plan_json = (
        WORKSPACE
        / "nl-diagnostics"
        / "nl-anti-block-client-compatibility-runtime-deploy-plan-2026-06-02.json"
    )
    runtime_deploy_plan_md = (
        WORKSPACE
        / "nl-diagnostics"
        / "nl-anti-block-client-compatibility-runtime-deploy-plan-2026-06-02.md"
    )
    production_audit_json = (
        WORKSPACE / "nl-diagnostics" / "nl-anti-block-production-audit-2026-06-02.json"
    )
    production_audit_md = (
        WORKSPACE / "nl-diagnostics" / "nl-anti-block-production-audit-2026-06-02.md"
    )
    matrix_missing_requirements: list[str] | None = None
    android_probe_decision: str | None = None
    android_probe_checked_at: str | None = None
    if android_adb_probe_json.exists():
        try:
            android_probe = json.loads(android_adb_probe_json.read_text(encoding="utf-8"))
            ok(checks, "android_adb_probe_json_valid")
            android_probe_checked_at = str(android_probe.get("checked_at") or "")
            if timestamp_in_current_evidence_session(android_probe_checked_at):
                ok(checks, "android_adb_probe_current_session_timestamp")
            else:
                fail(
                    checks,
                    "android_adb_probe_current_session_timestamp",
                    "Android ADB probe checked_at must be inside current evidence session",
                )
            android_probe_decision = str(android_probe.get("decision") or "")
            if android_probe_decision:
                ok(checks, "android_adb_probe_decision_recorded", android_probe_decision)
            else:
                fail(checks, "android_adb_probe_decision_recorded", "missing decision")
            privacy = android_probe.get("privacy") or {}
            if isinstance(privacy, dict) and privacy.get("output_privacy_ok") is True:
                ok(checks, "android_adb_probe_privacy_flag")
            else:
                fail(checks, "android_adb_probe_privacy_flag", "missing output_privacy_ok=true")
            adb_context = android_probe.get("adb") or {}
            if isinstance(adb_context, dict) and adb_context.get("raw_serials_stored") is False:
                ok(checks, "android_adb_probe_serials_redacted")
            else:
                fail(checks, "android_adb_probe_serials_redacted", "raw serial redaction flag missing")
            matrix_recording = android_probe.get("matrix_recording")
            if isinstance(matrix_recording, dict) and "recorded" in matrix_recording:
                ok(checks, "android_adb_probe_matrix_recording_status_recorded")
            else:
                fail(checks, "android_adb_probe_matrix_recording_status_recorded", "missing matrix_recording")
            if android_probe_decision == "ANDROID_ADB_VPN_DATAPLANE_PASS":
                if isinstance(matrix_recording, dict) and matrix_recording.get("recorded") is True:
                    ok(checks, "android_adb_probe_pass_recorded_to_matrix")
                else:
                    fail(checks, "android_adb_probe_pass_recorded_to_matrix", "passing Android probe was not recorded")
            elif isinstance(matrix_recording, dict) and matrix_recording.get("recorded") is False:
                ok(checks, "android_adb_probe_non_pass_not_recorded", str(matrix_recording.get("reason")))
            else:
                fail(checks, "android_adb_probe_non_pass_not_recorded", "non-pass probe recording state is unclear")
        except Exception as exc:
            fail(checks, "android_adb_probe_json_valid", str(exc))
    if matrix_json.exists():
        try:
            matrix = json.loads(matrix_json.read_text(encoding="utf-8"))
            ok(checks, "client_matrix_json_valid")
            if timestamp_in_current_evidence_session(str(matrix.get("last_updated_utc") or "")):
                ok(checks, "client_matrix_current_session_timestamp")
            else:
                fail(
                    checks,
                    "client_matrix_current_session_timestamp",
                    "matrix last_updated_utc must be inside current evidence session",
                )
            current_status = (matrix.get("completion_rule") or {}).get("current_status")
            if current_status in {"complete", "not_complete"}:
                ok(checks, "client_matrix_completion_status_recorded", str(current_status))
            else:
                fail(checks, "client_matrix_completion_status_recorded", "missing complete/not_complete")
            missing_requirements = (matrix.get("completion_rule") or {}).get("missing_requirements")
            next_required_checks = (matrix.get("completion_rule") or {}).get("next_required_checks")
            if isinstance(missing_requirements, list):
                matrix_missing_requirements = [str(item) for item in missing_requirements]
                ok(checks, "client_matrix_missing_requirements_recorded", str(len(missing_requirements)))
            else:
                fail(checks, "client_matrix_missing_requirements_recorded", "missing list")
            if isinstance(next_required_checks, list):
                ok(checks, "client_matrix_next_required_checks_recorded", str(len(next_required_checks)))
            else:
                fail(checks, "client_matrix_next_required_checks_recorded", "missing list")
            evidence_session = (matrix.get("completion_rule") or {}).get("evidence_session")
            if (
                isinstance(evidence_session, dict)
                and evidence_session.get("id") == CURRENT_EVIDENCE_SESSION_ID
                and evidence_session.get("started_at") == CURRENT_EVIDENCE_SESSION_STARTED_AT
                and evidence_session.get("required_transport") == CURRENT_EVIDENCE_REQUIRED_TRANSPORT
                and evidence_session.get("required_port") == CURRENT_EVIDENCE_REQUIRED_PORT
                and set(evidence_session.get("required_for_network_types") or [])
                == {"mobile", "restricted-wifi", "work-wifi"}
                and isinstance(evidence_session.get("session_bound_requirements"), dict)
            ):
                ok(checks, "client_matrix_evidence_session_recorded")
            else:
                fail(
                    checks,
                    "client_matrix_evidence_session_recorded",
                    "missing current evidence session reality:443 rule",
                )
            rollout_checks = [
                row
                for row in next_required_checks or []
                if isinstance(row, dict)
            ]
            if all(
                row.get("transport") == CURRENT_EVIDENCE_REQUIRED_TRANSPORT
                and row.get("port") == CURRENT_EVIDENCE_REQUIRED_PORT
                for row in rollout_checks
            ):
                ok(checks, "client_matrix_next_required_checks_use_reality_443")
            else:
                fail(
                    checks,
                    "client_matrix_next_required_checks_use_reality_443",
                    "next required checks must target reality:443",
                )
            local_inventory = matrix.get("local_client_inventory")
            if isinstance(local_inventory, dict) and local_inventory.get("diagnosis"):
                ok(checks, "client_matrix_local_inventory_recorded", str(local_inventory.get("diagnosis")))
            else:
                fail(checks, "client_matrix_local_inventory_recorded", "missing local inventory diagnosis")
            copy_import = matrix.get("local_v2rayn_fallback_import_copy_test")
            if isinstance(copy_import, dict) and copy_import.get("applied_to_live_db") is False:
                ok(checks, "client_matrix_v2rayn_copy_import_recorded", str(copy_import.get("decision")))
            else:
                fail(checks, "client_matrix_v2rayn_copy_import_recorded", "missing copy import evidence")
            live_import = matrix.get("local_v2rayn_fallback_import_live")
            if (
                isinstance(live_import, dict)
                and live_import.get("applied_to_live_db") is True
                and live_import.get("restarted_v2rayn") is False
            ):
                ok(checks, "client_matrix_v2rayn_live_import_recorded", str(live_import.get("decision")))
            else:
                fail(checks, "client_matrix_v2rayn_live_import_recorded", "missing live import evidence")
            dataplane_probe = matrix.get("local_v2rayn_dataplane_probe")
            passed_transports = set()
            if isinstance(dataplane_probe, dict):
                passed_transports = {
                    str(item).lower()
                    for item in dataplane_probe.get("passed_transports") or []
                }
            if (
                isinstance(dataplane_probe, dict)
                and dataplane_probe.get("ok") is True
                and {"xhttp", "ws"}.issubset(passed_transports)
            ):
                ok(
                    checks,
                    "client_matrix_v2rayn_dataplane_probe_recorded",
                    ",".join(sorted(passed_transports)),
                )
            else:
                fail(
                    checks,
                    "client_matrix_v2rayn_dataplane_probe_recorded",
                    "missing xhttp/ws dataplane probe evidence",
                )
            decision = matrix.get("decision")
            if decision in {"CLIENT_MATRIX_COMPLETE", "CLIENT_MATRIX_PARTIAL_REAL_DEVICES_REQUIRED"}:
                ok(checks, "client_matrix_decision_known", str(decision))
            else:
                fail(checks, "client_matrix_decision_known", f"unexpected decision {decision!r}")
        except Exception as exc:
            fail(checks, "client_matrix_json_valid", str(exc))
    if runtime_summary_json.exists():
        try:
            runtime_summary = json.loads(runtime_summary_json.read_text(encoding="utf-8"))
            ok(checks, "client_compat_runtime_summary_json_valid")
            if runtime_summary.get("ok") is True:
                ok(checks, "client_compat_runtime_summary_ok")
            else:
                fail(checks, "client_compat_runtime_summary_ok", "ok must be true")
            privacy = runtime_summary.get("privacy") or {}
            if isinstance(privacy, dict) and privacy.get("output_privacy_ok") is True:
                ok(checks, "client_compat_runtime_summary_privacy_flag")
            else:
                fail(
                    checks,
                    "client_compat_runtime_summary_privacy_flag",
                    "missing output_privacy_ok=true",
                )
            if isinstance(privacy, dict) and privacy.get("raw_real_client_rows_returned") is False:
                ok(checks, "client_compat_runtime_summary_no_raw_rows")
            else:
                fail(
                    checks,
                    "client_compat_runtime_summary_no_raw_rows",
                    "raw_real_client_rows_returned must be false",
                )
            runtime_missing = runtime_summary.get("missing_requirements")
            if matrix_missing_requirements is None or runtime_missing == matrix_missing_requirements:
                ok(checks, "client_compat_runtime_summary_matches_matrix_missing")
            else:
                fail(
                    checks,
                    "client_compat_runtime_summary_matches_matrix_missing",
                    f"expected {matrix_missing_requirements}, got {runtime_missing}",
                )
            completion = runtime_summary.get("completion") or {}
            if isinstance(completion, dict) and "desktop_v2rayn" in completion:
                ok(checks, "client_compat_runtime_summary_completion_recorded")
            else:
                fail(
                    checks,
                    "client_compat_runtime_summary_completion_recorded",
                    "missing completion evidence",
                )
            evidence_session = runtime_summary.get("evidence_session") or {}
            if (
                isinstance(evidence_session, dict)
                and evidence_session.get("id") == CURRENT_EVIDENCE_SESSION_ID
                and evidence_session.get("started_at") == CURRENT_EVIDENCE_SESSION_STARTED_AT
                and evidence_session.get("required_transport")
                == CURRENT_EVIDENCE_REQUIRED_TRANSPORT
                and evidence_session.get("required_port") == CURRENT_EVIDENCE_REQUIRED_PORT
            ):
                ok(checks, "client_compat_runtime_summary_evidence_session_recorded")
            else:
                fail(
                    checks,
                    "client_compat_runtime_summary_evidence_session_recorded",
                    "runtime summary must include current reality:443 evidence session",
                )
        except Exception as exc:
            fail(checks, "client_compat_runtime_summary_json_valid", str(exc))
    if runtime_probe_json.exists():
        try:
            runtime_probe = json.loads(runtime_probe_json.read_text(encoding="utf-8"))
            ok(checks, "client_compat_runtime_probe_json_valid")
            decision = runtime_probe.get("decision")
            if decision in {
                "NL_CLIENT_COMPAT_RUNTIME_READY",
                "NL_CLIENT_COMPAT_RUNTIME_ENDPOINT_MISSING",
                "NL_CLIENT_COMPAT_RUNTIME_INCOMPLETE",
            }:
                ok(checks, "client_compat_runtime_probe_decision_known", str(decision))
            else:
                fail(
                    checks,
                    "client_compat_runtime_probe_decision_known",
                    f"unexpected decision {decision!r}",
                )
            transport = runtime_probe.get("transport_usage_endpoint") or {}
            if isinstance(transport, dict) and transport.get("ok") is True:
                ok(checks, "client_compat_runtime_probe_transport_usage_ok")
            else:
                fail(
                    checks,
                    "client_compat_runtime_probe_transport_usage_ok",
                    "transport usage endpoint is not ok",
                )
            client = runtime_probe.get("client_compatibility_endpoint") or {}
            if isinstance(client, dict) and isinstance(client.get("http_code"), int):
                ok(checks, "client_compat_runtime_probe_client_http_code_recorded", str(client.get("http_code")))
            else:
                fail(
                    checks,
                    "client_compat_runtime_probe_client_http_code_recorded",
                    "missing integer HTTP code",
                )
            if isinstance(client, dict) and client.get("evidence_session_contract_ok") is True:
                ok(checks, "client_compat_runtime_probe_current_contract")
            else:
                fail(
                    checks,
                    "client_compat_runtime_probe_current_contract",
                    "NL /client-compatibility must expose current reality:443 evidence session",
                )
            privacy = runtime_probe.get("privacy") or {}
            if isinstance(privacy, dict) and privacy.get("output_privacy_ok") is True:
                ok(checks, "client_compat_runtime_probe_privacy_flag")
            else:
                fail(
                    checks,
                    "client_compat_runtime_probe_privacy_flag",
                    "missing output_privacy_ok=true",
                )
            if (
                isinstance(privacy, dict)
                and privacy.get("raw_ssh_config_stored") is False
                and privacy.get("raw_client_rows_stored") is False
            ):
                ok(checks, "client_compat_runtime_probe_no_raw_runtime_secrets")
            else:
                fail(
                    checks,
                    "client_compat_runtime_probe_no_raw_runtime_secrets",
                    "raw ssh/client row flags missing",
                )
        except Exception as exc:
            fail(checks, "client_compat_runtime_probe_json_valid", str(exc))
    if runtime_deploy_plan_json.exists():
        try:
            runtime_deploy_plan = json.loads(runtime_deploy_plan_json.read_text(encoding="utf-8"))
            ok(checks, "client_compat_runtime_deploy_plan_json_valid")
            decision = runtime_deploy_plan.get("decision")
            if decision in {
                "CLIENT_COMPAT_RUNTIME_DEPLOY_DRY_RUN",
                "CLIENT_COMPAT_RUNTIME_ALREADY_APPLIED",
                "CLIENT_COMPAT_RUNTIME_DEPLOY_BLOCKED",
                "CLIENT_COMPAT_RUNTIME_DEPLOY_PRIVACY_BLOCKED",
            }:
                ok(checks, "client_compat_runtime_deploy_plan_decision_known", str(decision))
            else:
                fail(
                    checks,
                    "client_compat_runtime_deploy_plan_decision_known",
                    f"unexpected decision {decision!r}",
                )
            if runtime_deploy_plan.get("ok") is True:
                ok(checks, "client_compat_runtime_deploy_plan_ok")
            else:
                fail(checks, "client_compat_runtime_deploy_plan_ok", "ok must be true for dry-run packet")
            if (
                runtime_deploy_plan.get("applied_to_nl") is False
                and runtime_deploy_plan.get("dry_run_mutated_nl") is False
            ):
                ok(checks, "client_compat_runtime_deploy_plan_not_applied")
            else:
                fail(
                    checks,
                    "client_compat_runtime_deploy_plan_not_applied",
                    "dry-run artifact must not claim NL mutation",
                )
            if runtime_deploy_plan.get("confirm_required") == "DEPLOY_CLIENT_COMPAT_RUNTIME":
                ok(checks, "client_compat_runtime_deploy_plan_confirm_token")
            else:
                fail(
                    checks,
                    "client_compat_runtime_deploy_plan_confirm_token",
                    "missing deploy confirmation token",
                )
            if (
                runtime_deploy_plan.get("status_api_restart_confirm_required")
                == "RESTART_PROFILE_STATUS_API"
            ):
                ok(checks, "client_compat_runtime_deploy_plan_restart_confirm_token")
            else:
                fail(
                    checks,
                    "client_compat_runtime_deploy_plan_restart_confirm_token",
                    "missing status API restart confirmation token",
                )
            policy = runtime_deploy_plan.get("mutation_policy") or {}
            forbidden = set(policy.get("forbidden_service_restarts") or [])
            allowed_units = set(policy.get("allowed_mutation_units") or [])
            expected_forbidden = {
                "x-ui",
                "nginx",
                "telegram-bot-simple.service",
                "ghost-access-nl-xhttp.service",
                "ghost-access-nl-https-ws.service",
            }
            if expected_forbidden.issubset(forbidden) and forbidden.isdisjoint(allowed_units):
                ok(checks, "client_compat_runtime_deploy_plan_forbids_vpn_restarts")
            else:
                fail(
                    checks,
                    "client_compat_runtime_deploy_plan_forbids_vpn_restarts",
                    "forbidden restart set is incomplete or overlaps allowed units",
                )
            targets = set(policy.get("allowed_target_paths") or [])
            required_targets = {
                "/opt/x0tta6bl4-mesh/scripts/profile_status_api.py",
                "/opt/x0tta6bl4-mesh/scripts/build_client_compatibility_runtime_summary.py",
                "/var/lib/ghost-access/client-compatibility/matrix.json",
                "/var/lib/ghost-access/client-compatibility/latest.json",
                "/etc/systemd/system/ghost-access-client-compatibility-summary.service",
                "/etc/systemd/system/ghost-access-client-compatibility-summary.timer",
            }
            if required_targets.issubset(targets):
                ok(checks, "client_compat_runtime_deploy_plan_target_paths")
            else:
                fail(
                    checks,
                    "client_compat_runtime_deploy_plan_target_paths",
                    f"missing targets {sorted(required_targets - targets)}",
                )
            files = runtime_deploy_plan.get("files") or []
            if isinstance(files, list) and all(
                isinstance(row, dict) and row.get("local_exists") is True for row in files
            ):
                ok(checks, "client_compat_runtime_deploy_plan_local_files_exist")
            else:
                fail(
                    checks,
                    "client_compat_runtime_deploy_plan_local_files_exist",
                    "all deployment rows must point at existing local files",
                )
            endpoints = (
                (runtime_deploy_plan.get("remote_state") or {}).get("status_api_endpoints") or {}
            )
            if isinstance(endpoints.get("client_compatibility_http_code"), int):
                ok(
                    checks,
                    "client_compat_runtime_deploy_plan_client_http_code_recorded",
                    str(endpoints.get("client_compatibility_http_code")),
                )
            else:
                fail(
                    checks,
                    "client_compat_runtime_deploy_plan_client_http_code_recorded",
                    "missing client compatibility HTTP code",
                )
            privacy = runtime_deploy_plan.get("privacy") or {}
            if isinstance(privacy, dict) and privacy.get("output_privacy_ok") is True:
                ok(checks, "client_compat_runtime_deploy_plan_privacy_flag")
            else:
                fail(
                    checks,
                    "client_compat_runtime_deploy_plan_privacy_flag",
                    "missing output_privacy_ok=true",
                )
            if (
                isinstance(privacy, dict)
                and privacy.get("raw_commands_stored") is False
                and privacy.get("raw_ssh_config_stored") is False
                and privacy.get("raw_client_rows_stored") is False
            ):
                ok(checks, "client_compat_runtime_deploy_plan_no_raw_runtime_secrets")
            else:
                fail(
                    checks,
                    "client_compat_runtime_deploy_plan_no_raw_runtime_secrets",
                    "raw command/ssh/client row redaction flags missing",
                )
        except Exception as exc:
            fail(checks, "client_compat_runtime_deploy_plan_json_valid", str(exc))
    if remote_intake_json.exists():
        try:
            remote_intake = json.loads(remote_intake_json.read_text(encoding="utf-8"))
            ok(checks, "remote_client_evidence_intake_json_valid")
            if timestamp_in_current_evidence_session(str(remote_intake.get("generated_at") or "")):
                ok(checks, "remote_client_evidence_intake_current_session_timestamp")
            else:
                fail(
                    checks,
                    "remote_client_evidence_intake_current_session_timestamp",
                    "remote intake generated_at must be inside current evidence session",
                )
            decision = remote_intake.get("decision")
            if decision in {
                "REMOTE_CLIENT_EVIDENCE_INTAKE_READY",
                "REMOTE_CLIENT_EVIDENCE_VALIDATED",
                "REMOTE_CLIENT_EVIDENCE_DRY_RUN",
                "REMOTE_CLIENT_EVIDENCE_RECORDED",
            }:
                ok(checks, "remote_client_evidence_intake_decision_known", str(decision))
            else:
                fail(
                    checks,
                    "remote_client_evidence_intake_decision_known",
                    f"unexpected decision {decision!r}",
                )
            privacy = remote_intake.get("privacy") or {}
            if isinstance(privacy, dict) and privacy.get("output_privacy_ok") is True:
                ok(checks, "remote_client_evidence_intake_privacy_flag")
            else:
                fail(
                    checks,
                    "remote_client_evidence_intake_privacy_flag",
                    "missing output_privacy_ok=true",
                )
            if (
                isinstance(privacy, dict)
                and privacy.get("raw_reporter_identifier_stored") is False
                and privacy.get("raw_telegram_handle_stored") is False
                and privacy.get("raw_phone_stored") is False
                and privacy.get("raw_url_stored") is False
            ):
                ok(checks, "remote_client_evidence_intake_identifiers_redacted")
            else:
                fail(
                    checks,
                    "remote_client_evidence_intake_identifiers_redacted",
                    "raw reporter/handle/phone/url redaction flags missing",
                )
            recording = remote_intake.get("recording")
            if isinstance(recording, dict) and "recorded" in recording:
                ok(checks, "remote_client_evidence_intake_recording_status_recorded")
            else:
                fail(
                    checks,
                    "remote_client_evidence_intake_recording_status_recorded",
                    "missing recording status",
                )
            command = str(remote_intake.get("safe_remote_record_command_template") or "")
            if "record_remote_client_evidence.py --write --record-matrix" in command:
                ok(checks, "remote_client_evidence_intake_command_present")
            else:
                fail(
                    checks,
                    "remote_client_evidence_intake_command_present",
                    "missing safe remote record command",
                )
            summary = remote_intake.get("matrix_summary") or {}
            remote_missing = summary.get("missing_requirements") if isinstance(summary, dict) else None
            if matrix_missing_requirements is None or remote_missing == matrix_missing_requirements:
                ok(checks, "remote_client_evidence_intake_matches_matrix_missing")
            else:
                fail(
                    checks,
                    "remote_client_evidence_intake_matches_matrix_missing",
                    f"expected {matrix_missing_requirements}, got {remote_missing}",
                )
        except Exception as exc:
            fail(checks, "remote_client_evidence_intake_json_valid", str(exc))
    if remote_request_json.exists():
        try:
            remote_request = json.loads(remote_request_json.read_text(encoding="utf-8"))
            ok(checks, "remote_client_evidence_request_json_valid")
            if timestamp_in_current_evidence_session(str(remote_request.get("generated_at") or "")):
                ok(checks, "remote_client_evidence_request_current_session_timestamp")
            else:
                fail(
                    checks,
                    "remote_client_evidence_request_current_session_timestamp",
                    "remote request packet generated_at must be inside current evidence session",
                )
            decision = remote_request.get("decision")
            if decision in {
                "REMOTE_CLIENT_EVIDENCE_REQUEST_READY",
                "REMOTE_CLIENT_EVIDENCE_REQUEST_NOT_NEEDED",
            }:
                ok(checks, "remote_client_evidence_request_decision_known", str(decision))
            else:
                fail(
                    checks,
                    "remote_client_evidence_request_decision_known",
                    f"unexpected decision {decision!r}",
                )
            privacy = remote_request.get("privacy") or {}
            if isinstance(privacy, dict) and privacy.get("output_privacy_ok") is True:
                ok(checks, "remote_client_evidence_request_privacy_flag")
            else:
                fail(
                    checks,
                    "remote_client_evidence_request_privacy_flag",
                    "missing output_privacy_ok=true",
                )
            if (
                isinstance(privacy, dict)
                and privacy.get("raw_reporter_identifier_stored") is False
                and privacy.get("raw_screenshot_stored") is False
                and privacy.get("raw_logs_stored") is False
                and privacy.get("raw_url_stored") is False
            ):
                ok(checks, "remote_client_evidence_request_no_raw_identifiers")
            else:
                fail(
                    checks,
                    "remote_client_evidence_request_no_raw_identifiers",
                    "raw reporter/screenshot/log/url redaction flags missing",
                )
            hash_policy = str(remote_request.get("request_packet_hash_binding_policy") or "")
            if (
                "--expect-request-packet-sha256" in hash_policy
                and "source_sha256" in hash_policy
                and "sha256sum" in hash_policy
            ):
                ok(checks, "remote_client_evidence_request_hash_binding_policy_present")
            else:
                fail(
                    checks,
                    "remote_client_evidence_request_hash_binding_policy_present",
                    "request packet must tell operators to bind replies to the exact packet hash",
                )
            request_missing = remote_request.get("missing_requirements")
            if matrix_missing_requirements is None or request_missing == matrix_missing_requirements:
                ok(checks, "remote_client_evidence_request_matches_matrix_missing")
            else:
                fail(
                    checks,
                    "remote_client_evidence_request_matches_matrix_missing",
                    f"expected {matrix_missing_requirements}, got {request_missing}",
                )
            requests = remote_request.get("requests")
            if isinstance(requests, list):
                ok(checks, "remote_client_evidence_request_requests_recorded", str(len(requests)))
            else:
                fail(
                    checks,
                    "remote_client_evidence_request_requests_recorded",
                    "requests must be a list",
                )
                requests = []
            covered = {
                str(requirement)
                for request in requests
                if isinstance(request, dict)
                for requirement in request.get("covers_requirements") or []
            }
            if matrix_missing_requirements is None or set(matrix_missing_requirements).issubset(covered):
                ok(checks, "remote_client_evidence_request_covers_missing_requirements")
            else:
                fail(
                    checks,
                    "remote_client_evidence_request_covers_missing_requirements",
                    f"missing coverage {sorted(set(matrix_missing_requirements) - covered)}",
                )
            minimum = remote_request.get("minimum_reports_required")
            if isinstance(minimum, int) and minimum == len(requests):
                ok(checks, "remote_client_evidence_request_minimum_reports_recorded", str(minimum))
            else:
                fail(
                    checks,
                    "remote_client_evidence_request_minimum_reports_recorded",
                    "minimum_reports_required must match request count",
                )
            commands = "\n".join(
                "\n".join(
                    [
                        str(request.get("operator_record_pass_command") or ""),
                        str(request.get("operator_record_fail_command") or ""),
                    ]
                )
                for request in requests
                if isinstance(request, dict)
            )
            reply_commands = "\n".join(
                str(request.get("operator_reply_record_pass_command") or "")
                for request in requests
                if isinstance(request, dict)
            )
            direct_record_policy = str(remote_request.get("direct_record_commands_policy") or "")
            direct_record_commands_disabled = (
                "record_remote_client_evidence.py --write --record-matrix" not in commands
                and all(
                    isinstance(request, dict)
                    and not str(request.get("operator_record_pass_command") or "").strip()
                    and not str(request.get("operator_record_fail_command") or "").strip()
                    and "Direct record_remote_client_evidence.py --write commands are disabled"
                    in str(request.get("operator_record_command_policy") or "")
                    for request in requests
                )
                and "Direct record_remote_client_evidence.py --write commands are disabled"
                in direct_record_policy
                and "operator_reply_record" in direct_record_policy
                and "SHA-256" in direct_record_policy
            )
            if direct_record_commands_disabled:
                ok(checks, "remote_client_evidence_request_direct_record_commands_disabled")
            else:
                fail(
                    checks,
                    "remote_client_evidence_request_direct_record_commands_disabled",
                    "remote request packet must force short-reply hash-bound recording path",
                )
            if (
                remote_request.get("evidence_session_id") == CURRENT_EVIDENCE_SESSION_ID
                and remote_request.get("evidence_session_started_at")
                == CURRENT_EVIDENCE_SESSION_STARTED_AT
                and all(
                    isinstance(request, dict)
                    and request.get("evidence_session_id") == CURRENT_EVIDENCE_SESSION_ID
                    and request.get("evidence_session_started_at")
                    == CURRENT_EVIDENCE_SESSION_STARTED_AT
                    for request in requests
                )
            ):
                ok(checks, "remote_client_evidence_request_session_bound")
            else:
                fail(
                    checks,
                    "remote_client_evidence_request_session_bound",
                    "request packet must carry current evidence_session_id",
                )
            if all(
                isinstance(request, dict)
                and request.get("transport") == CURRENT_EVIDENCE_REQUIRED_TRANSPORT
                and request.get("port") == CURRENT_EVIDENCE_REQUIRED_PORT
                for request in requests
            ):
                ok(checks, "remote_client_evidence_request_uses_reality_443")
            else:
                fail(
                    checks,
                    "remote_client_evidence_request_uses_reality_443",
                    "all remote client requests must target reality:443",
                )
            if (
                "record_remote_client_evidence_reply.py --write --record-matrix" in reply_commands
                and "--reply-stdin" in reply_commands
                and "--expect-request-packet-sha256" in reply_commands
                and "sha256sum" in reply_commands
            ):
                ok(checks, "remote_client_evidence_request_reply_commands_present")
            else:
                fail(
                    checks,
                    "remote_client_evidence_request_reply_commands_present",
                    "missing short reply record commands with packet SHA-256 guard",
                )
            reply_options_ok = all(
                isinstance(request, dict)
                and {
                    "pass connected",
                    "fail timeout",
                    "fail import",
                    "fail no-internet",
                }.issubset(set(request.get("safe_reply_options") or []))
                for request in requests
            )
            if reply_options_ok:
                ok(checks, "remote_client_evidence_request_reply_options_present")
            else:
                fail(
                    checks,
                    "remote_client_evidence_request_reply_options_present",
                    "missing safe reply options",
                )
            first_request = next((request for request in requests if isinstance(request, dict)), None)
            if isinstance(first_request, dict) and first_request.get("request_id"):
                matrix_hash_before = sha256(matrix_json) if matrix_json.exists() else None
                request_packet_hash = sha256(remote_request_json)
                dry_run = subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / "ghost-access" / "record_remote_client_evidence_reply.py"),
                        "--request-packet",
                        str(remote_request_json),
                        "--expect-request-packet-sha256",
                        request_packet_hash,
                        "--matrix",
                        str(matrix_json),
                        "--request-id",
                        str(first_request["request_id"]),
                        "--reply-stdin",
                        "--json",
                    ],
                    cwd=str(WORKSPACE),
                    input="pass connected\n",
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                matrix_hash_after = sha256(matrix_json) if matrix_json.exists() else None
                matrix_unchanged = (
                    matrix_hash_before is not None and matrix_hash_before == matrix_hash_after
                )
                try:
                    dry_run_payload = json.loads(dry_run.stdout)
                except json.JSONDecodeError:
                    dry_run_payload = {}
                recording = dry_run_payload.get("recording") if isinstance(dry_run_payload, dict) else {}
                privacy = dry_run_payload.get("privacy") if isinstance(dry_run_payload, dict) else {}
                packet_hash_reported = (
                    dry_run_payload.get("source_request_packet_sha256")
                    if isinstance(dry_run_payload, dict)
                    else None
                )
                if matrix_unchanged:
                    ok(checks, "remote_client_evidence_reply_dry_run_keeps_matrix_unchanged")
                else:
                    fail(
                        checks,
                        "remote_client_evidence_reply_dry_run_keeps_matrix_unchanged",
                        "matrix hash changed or matrix file is missing",
                    )
                if packet_hash_reported == request_packet_hash:
                    ok(checks, "remote_client_evidence_reply_dry_run_uses_packet_hash")
                else:
                    fail(
                        checks,
                        "remote_client_evidence_reply_dry_run_uses_packet_hash",
                        f"expected {request_packet_hash}, got {packet_hash_reported}",
                    )
                if (
                    dry_run.returncode == 0
                    and dry_run_payload.get("decision") == "REMOTE_CLIENT_EVIDENCE_REPLY_VALIDATED"
                    and isinstance(recording, dict)
                    and recording.get("recorded") is False
                    and isinstance(privacy, dict)
                    and privacy.get("output_privacy_ok") is True
                    and matrix_unchanged
                    and packet_hash_reported == request_packet_hash
                ):
                    ok(checks, "remote_client_evidence_reply_dry_run_validates_without_write")
                else:
                    fail(
                        checks,
                        "remote_client_evidence_reply_dry_run_validates_without_write",
                        (
                            f"exit={dry_run.returncode} "
                            f"matrix_unchanged={matrix_unchanged} "
                            f"stdout={dry_run.stdout[-500:]} stderr={dry_run.stderr[-500:]}"
                        ),
                    )
            else:
                fail(
                    checks,
                    "remote_client_evidence_reply_dry_run_validates_without_write",
                    "missing request_id for dry-run validation",
                )
        except Exception as exc:
            fail(checks, "remote_client_evidence_request_json_valid", str(exc))
    if evidence_plan_json.exists():
        try:
            plan = json.loads(evidence_plan_json.read_text(encoding="utf-8"))
            ok(checks, "client_evidence_plan_json_valid")
            if timestamp_in_current_evidence_session(str(plan.get("generated_at") or "")):
                ok(checks, "client_evidence_plan_current_session_timestamp")
            else:
                fail(
                    checks,
                    "client_evidence_plan_current_session_timestamp",
                    "client evidence plan generated_at must be inside current evidence session",
                )
            decision = plan.get("decision")
            if decision in {"CLIENT_EVIDENCE_REQUIRED", "CLIENT_EVIDENCE_COMPLETE"}:
                ok(checks, "client_evidence_plan_decision_known", str(decision))
            else:
                fail(checks, "client_evidence_plan_decision_known", f"unexpected decision {decision!r}")
            privacy = plan.get("privacy") or {}
            if isinstance(privacy, dict) and privacy.get("output_privacy_ok") is True:
                ok(checks, "client_evidence_plan_privacy_flag")
            else:
                fail(checks, "client_evidence_plan_privacy_flag", "missing output_privacy_ok=true")
            adb_context = plan.get("adb_context") or {}
            if isinstance(adb_context, dict) and adb_context.get("raw_serials_stored") is False:
                ok(checks, "client_evidence_plan_adb_serials_redacted")
            else:
                fail(checks, "client_evidence_plan_adb_serials_redacted", "raw serial redaction flag missing")
            embedded_android_probe = plan.get("android_adb_probe")
            embedded_android_probe_decision = (
                str(embedded_android_probe.get("decision"))
                if isinstance(embedded_android_probe, dict) and embedded_android_probe.get("decision")
                else None
            )
            if embedded_android_probe_decision:
                ok(checks, "client_evidence_plan_embeds_android_adb_probe", embedded_android_probe_decision)
            else:
                fail(checks, "client_evidence_plan_embeds_android_adb_probe", "missing embedded Android ADB probe")
            if android_probe_decision is None or embedded_android_probe_decision == android_probe_decision:
                ok(checks, "client_evidence_plan_android_probe_matches_latest")
            else:
                fail(
                    checks,
                    "client_evidence_plan_android_probe_matches_latest",
                    f"expected {android_probe_decision}, got {embedded_android_probe_decision}",
                )
            embedded_checked_at = (
                str(embedded_android_probe.get("checked_at") or "")
                if isinstance(embedded_android_probe, dict)
                else ""
            )
            if (
                timestamp_in_current_evidence_session(embedded_checked_at)
                and (
                    android_probe_checked_at is None
                    or embedded_checked_at == android_probe_checked_at
                )
            ):
                ok(checks, "client_evidence_plan_android_probe_current_session")
            else:
                fail(
                    checks,
                    "client_evidence_plan_android_probe_current_session",
                    "embedded Android ADB probe must match latest current-session probe",
                )
            plan_missing = plan.get("missing_requirements")
            if matrix_missing_requirements is None or plan_missing == matrix_missing_requirements:
                ok(checks, "client_evidence_plan_matches_matrix_missing")
            else:
                fail(
                    checks,
                    "client_evidence_plan_matches_matrix_missing",
                    f"expected {matrix_missing_requirements}, got {plan_missing}",
                )
            task_requirements = {
                str(task.get("requirement"))
                for task in plan.get("required_tasks") or []
                if isinstance(task, dict)
            }
            if matrix_missing_requirements is None or set(matrix_missing_requirements).issubset(task_requirements):
                ok(checks, "client_evidence_plan_covers_missing_requirements")
            else:
                fail(
                    checks,
                    "client_evidence_plan_covers_missing_requirements",
                    f"missing task coverage for {sorted(set(matrix_missing_requirements) - task_requirements)}",
                )
            rollout_tasks = [
                task for task in plan.get("required_tasks") or [] if isinstance(task, dict)
            ]
            if all(
                task.get("transport") == CURRENT_EVIDENCE_REQUIRED_TRANSPORT
                and task.get("port") == CURRENT_EVIDENCE_REQUIRED_PORT
                for task in rollout_tasks
            ):
                ok(checks, "client_evidence_plan_tasks_use_reality_443")
            else:
                fail(
                    checks,
                    "client_evidence_plan_tasks_use_reality_443",
                    "all current evidence tasks must target reality:443",
                )
            adb_record_tasks = [
                task
                for task in plan.get("required_tasks") or []
                if isinstance(task, dict)
                and "probe_android_adb_vpn.py --write --json --record-matrix"
                in str(task.get("android_adb_probe_record_command_template") or "")
            ]
            if matrix_missing_requirements is None or len(adb_record_tasks) >= len(matrix_missing_requirements):
                ok(checks, "client_evidence_plan_adb_auto_record_commands_present", str(len(adb_record_tasks)))
            else:
                fail(
                    checks,
                    "client_evidence_plan_adb_auto_record_commands_present",
                    f"expected at least {len(matrix_missing_requirements)}, got {len(adb_record_tasks)}",
                )
            remote_record_tasks = [
                task
                for task in plan.get("required_tasks") or []
                if isinstance(task, dict)
                and "record_remote_client_evidence.py --write --record-matrix"
                in str(task.get("remote_client_evidence_record_command_template") or "")
            ]
            if matrix_missing_requirements is None or len(remote_record_tasks) >= len(matrix_missing_requirements):
                ok(checks, "client_evidence_plan_remote_record_commands_present", str(len(remote_record_tasks)))
            else:
                fail(
                    checks,
                    "client_evidence_plan_remote_record_commands_present",
                    f"expected at least {len(matrix_missing_requirements)}, got {len(remote_record_tasks)}",
                )
        except Exception as exc:
            fail(checks, "client_evidence_plan_json_valid", str(exc))
    if production_audit_json.exists():
        try:
            audit = json.loads(production_audit_json.read_text(encoding="utf-8"))
            ok(checks, "production_audit_json_valid")
            if timestamp_in_current_evidence_session(str(audit.get("generated_at") or "")):
                ok(checks, "production_audit_current_session_timestamp")
            else:
                fail(
                    checks,
                    "production_audit_current_session_timestamp",
                    "production audit generated_at must be inside current evidence session",
                )
            decision = audit.get("decision")
            if decision in {
                "PRODUCTION_CANDIDATE_GOAL_NOT_MARKED_COMPLETE",
                "PRODUCTION_CANDIDATE_READY",
                "PRODUCTION_CANDIDATE_BLOCKED",
            }:
                ok(checks, "production_audit_decision_known", str(decision))
            else:
                fail(
                    checks,
                    "production_audit_decision_known",
                    f"unexpected decision {decision!r}",
                )
            if audit.get("generator") == "services/nl-server/ghost-access/build_anti_block_production_audit.py":
                ok(checks, "production_audit_generated_by_builder")
            else:
                fail(
                    checks,
                    "production_audit_generated_by_builder",
                    "missing generated audit builder marker",
                )
            requirements = audit.get("requirements")
            if isinstance(requirements, dict) and "user_client_matrix_after_rollout" in requirements:
                ok(
                    checks,
                    "production_audit_requirements_recorded",
                    str(requirements.get("user_client_matrix_after_rollout")),
                )
            else:
                fail(
                    checks,
                    "production_audit_requirements_recorded",
                    "missing user client matrix requirement",
                )
            remaining = audit.get("remaining_before_goal_complete")
            if isinstance(remaining, list):
                ok(checks, "production_audit_remaining_recorded", str(len(remaining)))
            else:
                fail(
                    checks,
                    "production_audit_remaining_recorded",
                    "remaining_before_goal_complete must be a list",
                )
            matrix_section = audit.get("client_compatibility_matrix") or {}
            audit_missing = matrix_section.get("missing_requirements")
            if matrix_missing_requirements is None or audit_missing == matrix_missing_requirements:
                ok(checks, "production_audit_matches_matrix_missing")
            else:
                fail(
                    checks,
                    "production_audit_matches_matrix_missing",
                    f"expected {matrix_missing_requirements}, got {audit_missing}",
                )
            request_section = matrix_section.get("remote_client_evidence_request") or {}
            audit_request_missing = request_section.get("missing_requirements")
            if matrix_missing_requirements is None or audit_request_missing == matrix_missing_requirements:
                ok(checks, "production_audit_request_matches_missing")
            else:
                fail(
                    checks,
                    "production_audit_request_matches_missing",
                    f"expected {matrix_missing_requirements}, got {audit_request_missing}",
                )
            requests = request_section.get("requests") or []
            covered = {
                str(requirement)
                for request in requests
                if isinstance(request, dict)
                for requirement in request.get("covers_requirements") or []
            }
            if matrix_missing_requirements is None or set(matrix_missing_requirements).issubset(covered):
                ok(checks, "production_audit_request_covers_missing")
            else:
                fail(
                    checks,
                    "production_audit_request_covers_missing",
                    f"missing coverage {sorted(set(matrix_missing_requirements) - covered)}",
                )
            audit_reply_commands_ok = all(
                isinstance(request, dict)
                and request.get("operator_reply_record_pass_command_available") is True
                and request.get("operator_reply_record_fail_command_available") is True
                and {
                    "pass connected",
                    "fail timeout",
                    "fail import",
                    "fail no-internet",
                }.issubset(set(request.get("safe_reply_options") or []))
                for request in requests
            )
            if audit_reply_commands_ok:
                ok(checks, "production_audit_request_reply_path_recorded")
            else:
                fail(
                    checks,
                    "production_audit_request_reply_path_recorded",
                    "generated audit is missing short reply record path",
                )
            current_session = matrix_section.get("current_evidence_session") or {}
            if (
                isinstance(current_session, dict)
                and current_session.get("id") == CURRENT_EVIDENCE_SESSION_ID
                and current_session.get("started_at") == CURRENT_EVIDENCE_SESSION_STARTED_AT
                and current_session.get("required_transport") == CURRENT_EVIDENCE_REQUIRED_TRANSPORT
                and current_session.get("required_port") == CURRENT_EVIDENCE_REQUIRED_PORT
                and set(current_session.get("required_for") or [])
                == {"android_happ_or_hiddify", "mobile_network", "restricted_or_work_wifi"}
            ):
                ok(checks, "production_audit_current_evidence_session_recorded")
            else:
                fail(
                    checks,
                    "production_audit_current_evidence_session_recorded",
                    "missing current evidence session reality:443 gate",
                )
            artifact_refresh = matrix_section.get("artifact_refresh") or {}
            if (
                isinstance(artifact_refresh, dict)
                and artifact_refresh.get("writes_production_audit") is True
                and artifact_refresh.get("does_not_contact_nl") is True
                and artifact_refresh.get("does_not_restart_vpn_services") is True
            ):
                ok(checks, "production_audit_refresh_contract_recorded")
            else:
                fail(
                    checks,
                    "production_audit_refresh_contract_recorded",
                    "artifact refresh contract is missing generated audit flags",
                )
            runtime_probe_section = matrix_section.get("nl_runtime_probe") or {}
            if (
                isinstance(runtime_probe_section, dict)
                and runtime_probe_section.get("current_evidence_session_ok") is True
            ):
                ok(checks, "production_audit_runtime_probe_current_session")
            else:
                fail(
                    checks,
                    "production_audit_runtime_probe_current_session",
                    "runtime probe must be checked inside current evidence session",
                )
            if (
                isinstance(runtime_probe_section, dict)
                and runtime_probe_section.get("client_compatibility_contract_ok") is True
            ):
                ok(checks, "production_audit_runtime_probe_current_contract")
            else:
                fail(
                    checks,
                    "production_audit_runtime_probe_current_contract",
                    "audit must show NL /client-compatibility current reality:443 contract",
                )
            privacy = audit.get("privacy") or {}
            if (
                isinstance(privacy, dict)
                and privacy.get("output_privacy_ok") is True
                and privacy.get("raw_client_rows_stored") is False
                and privacy.get("raw_commands_stored") is False
            ):
                ok(checks, "production_audit_privacy_flag")
            else:
                fail(
                    checks,
                    "production_audit_privacy_flag",
                    "audit privacy flags missing",
                )
        except Exception as exc:
            fail(checks, "production_audit_json_valid", str(exc))
    for path, label in (
        (matrix_json, "client_matrix_json_privacy"),
        (matrix_md, "client_matrix_md_privacy"),
        (evidence_plan_json, "client_evidence_plan_json_privacy"),
        (evidence_plan_md, "client_evidence_plan_md_privacy"),
        (android_adb_probe_json, "android_adb_probe_json_privacy"),
        (android_adb_probe_md, "android_adb_probe_md_privacy"),
        (remote_intake_json, "remote_client_evidence_intake_json_privacy"),
        (remote_intake_md, "remote_client_evidence_intake_md_privacy"),
        (remote_request_json, "remote_client_evidence_request_json_privacy"),
        (remote_request_md, "remote_client_evidence_request_md_privacy"),
        (runtime_summary_json, "client_compat_runtime_summary_json_privacy"),
        (runtime_summary_md, "client_compat_runtime_summary_md_privacy"),
        (runtime_probe_json, "client_compat_runtime_probe_json_privacy"),
        (runtime_probe_md, "client_compat_runtime_probe_md_privacy"),
        (runtime_deploy_plan_json, "client_compat_runtime_deploy_plan_json_privacy"),
        (runtime_deploy_plan_md, "client_compat_runtime_deploy_plan_md_privacy"),
        (production_audit_json, "production_audit_json_privacy"),
        (production_audit_md, "production_audit_md_privacy"),
        (client_compat_service, "client_compat_systemd_service_privacy"),
        (client_compat_timer, "client_compat_systemd_timer_privacy"),
    ):
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        leaked = [
            name
            for name, pattern in MATRIX_SECRET_PATTERNS.items()
            if pattern.search(text)
        ]
        if leaked:
            fail(checks, label, "forbidden patterns: " + ", ".join(leaked))
        else:
            ok(checks, label)

    passed = all(item["ok"] for item in checks)
    result = {
        "ok": passed,
        "deploy_status": "local_ready_but_deploy_blocked",
        "nl_write_allowed": False,
        "checks": checks,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
