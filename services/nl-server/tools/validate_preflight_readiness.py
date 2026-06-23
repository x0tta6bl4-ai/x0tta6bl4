#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
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
    ROOT / "ghost-access" / "run_vpn_service_access_agent.py",
    ROOT / "ghost-access" / "xray_runtime_user_manager.py",
    ROOT / "ghost-access" / "xui_client_manager.py",
    ROOT / "tests" / "test_current_nl_runtime_source.py",
    ROOT / "tests" / "test_health_action_policy.py",
    ROOT / "tests" / "test_listener_and_profile_hint.py",
    ROOT / "tests" / "test_activity_sync_and_tcp_bridge.py",
    ROOT / "tests" / "test_ghost_vpn_runtime_source.py",
    ROOT / "tests" / "test_auto_monitor_source.py",
    ROOT / "tests" / "test_apply_config_auto_source.py",
    ROOT / "tests" / "test_full_stealth_config_source.py",
    ROOT / "tests" / "test_rotation_timer_source.py",
    ROOT / "tests" / "test_spb_standalone_sync_source.py",
    ROOT / "tests" / "test_templates.py",
    ROOT / "templates" / "nl-beta-2443.example.json",
    ROOT / "templates" / "nl-beta-2443.example.json.meta.json",
    WORKSPACE / "nl-diagnostics" / "nl-deploy-preflight-checklist-2026-05-27.md",
    WORKSPACE / "nl-diagnostics" / "nl-mutation-gate-design-2026-05-27.md",
]

READONLY_FORBIDDEN = re.compile(
    r"\b(systemctl|service|restart|reload|scp|rsync|install|mv|rm|cp|sqlite3)\b"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return str(path.relative_to(WORKSPACE))


def fail(checks: list[dict[str, Any]], name: str, reason: str) -> None:
    checks.append({"name": name, "ok": False, "reason": reason})


def ok(checks: list[dict[str, Any]], name: str, reason: str = "ok") -> None:
    checks.append({"name": name, "ok": True, "reason": reason})


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
