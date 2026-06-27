"""
SPB read-only MCP server for Ghost Access operator checks.

This server intentionally talks only to the SSH alias "sb" by default and only
runs read-only commands. It must not touch NL or mutate services/files.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from datetime import datetime, timezone
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool


SSH_HOST = os.environ.get("SPB_MCP_SSH_HOST", "sb")
SSH_TIMEOUT_SECONDS = int(os.environ.get("SPB_MCP_TIMEOUT_SECONDS", "35"))

ARTIFACTS = {
    "snapshot_orchestration": "/var/lib/ghost-access/spb-snapshot-orchestration/latest.json",
    "freshness_sla": "/var/lib/ghost-access/spb-freshness-sla/latest.json",
    "telegram_cutover": "/var/lib/ghost-access/spb-telegram-final-cutover/post-write-refresh-latest.json",
    "post_write_consistency": "/var/lib/ghost-access/spb-final-cutover-post-write-consistency/latest.json",
    "traffic_policy": "/var/lib/ghost-access/spb-traffic-policy/latest.json",
    "production_db_import": "/var/lib/ghost-access/spb-production-db-import/latest.json",
    "real_device_evidence": "/var/lib/ghost-access/spb-real-device-evidence/latest.json",
    "rkn_tspu_evidence": "/var/lib/ghost-access/spb-rkn-tspu-evidence/latest.json",
    "poller_coordination": "/var/lib/ghost-access/spb-poller-coordination/latest.json",
    "cutover_command_packet": "/var/lib/ghost-access/spb-cutover-command-packet/latest.json",
    "operator_handoff_manifest": "/var/lib/ghost-access/spb-operator-handoff/manifest.json",
    "operator_handoff_simple_steps": "/var/lib/ghost-access/spb-operator-handoff/simple-next-steps.md",
}

SERVICE_GROUPS = {
    "full_stealth_snapshot": ["ghost-access-spb-full-stealth-snapshot.service"],
    "telegram_bot_candidates": [
        "ghost-access-telegram-bot.service",
        "telegram-bot.service",
        "ghost-telegram-bot.service",
    ],
}


def _ssh_script(script: str, timeout: int | None = None) -> dict[str, Any]:
    cmd = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=8",
        "-o",
        "ServerAliveInterval=5",
        "-o",
        "ServerAliveCountMax=1",
        SSH_HOST,
        "bash",
        "-s",
    ]
    try:
        result = subprocess.run(
            cmd,
            input=script,
            capture_output=True,
            text=True,
            timeout=timeout or SSH_TIMEOUT_SECONDS,
            env={**os.environ, "NO_COLOR": "1"},
        )
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout[-24000:],
            "stderr": result.stderr[-8000:],
            "ssh_host": SSH_HOST,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except subprocess.TimeoutExpired:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"SSH read-only check timed out after {timeout or SSH_TIMEOUT_SECONDS}s",
            "ssh_host": SSH_HOST,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


def _decode_json_result(raw: dict[str, Any]) -> dict[str, Any]:
    if raw["exit_code"] != 0:
        return raw
    try:
        data = json.loads(raw["stdout"])
    except json.JSONDecodeError:
        return raw
    data["_ssh"] = {
        "host": raw["ssh_host"],
        "timestamp": raw["timestamp"],
    }
    return data


async def spb_status_summary(args: dict[str, Any]) -> dict[str, Any]:
    """Return a read-only SPB Ghost Access status summary from known artifacts."""
    include_services = bool(args.get("include_services", True))
    services = SERVICE_GROUPS if include_services else {}
    script = f"""
python3 - <<'PY'
import json
import pathlib
import subprocess
from datetime import datetime, timezone

artifacts = {json.dumps(ARTIFACTS, sort_keys=True)}
service_groups = {json.dumps(services, sort_keys=True)}

def read_json(path):
    p = pathlib.Path(path)
    if not p.exists():
        return {{"exists": False, "path": path}}
    try:
        data = json.loads(p.read_text())
    except Exception as exc:
        return {{"exists": True, "path": path, "error": str(exc)}}
    compact = {{"exists": True, "path": path}}
    for key in (
        "status", "ready", "fresh", "ok", "result", "checks_passed",
        "checks_total", "total", "passed", "failed", "message",
        "policy_status", "generated_at", "timestamp",
    ):
        if key in data:
            compact[key] = data[key]
    if "summary" in data and isinstance(data["summary"], dict):
        compact["summary"] = data["summary"]
    return compact

def systemctl_show(unit):
    props = [
        "LoadState", "ActiveState", "SubState", "Result", "UnitFileState",
        "ActiveEnterTimestamp", "InactiveEnterTimestamp",
    ]
    cmd = ["systemctl", "show", unit] + [f"--property={{p}}" for p in props]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
    parsed = {{"unit": unit, "exit_code": result.returncode}}
    for line in result.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            parsed[key] = value
    if result.stderr:
        parsed["stderr"] = result.stderr[-2000:]
    return parsed

out = {{
    "host": subprocess.run(["hostname"], capture_output=True, text=True, timeout=5).stdout.strip(),
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "artifacts": {{name: read_json(path) for name, path in artifacts.items()}},
    "sentinels": {{
        "telegram_cutover": pathlib.Path("/run/ghost-access/enable-telegram-cutover").exists(),
    }},
}}

df = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, timeout=5)
out["disk_root"] = df.stdout.strip()

if service_groups:
    out["services"] = {{
        group: [systemctl_show(unit) for unit in units]
        for group, units in service_groups.items()
    }}

print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
PY
"""
    return _decode_json_result(_ssh_script(script))


def _artifact_status(summary: dict[str, Any], artifact: str) -> str | None:
    artifacts = summary.get("artifacts") if isinstance(summary.get("artifacts"), dict) else {}
    state = artifacts.get(artifact) if isinstance(artifacts.get(artifact), dict) else {}
    status = state.get("status")
    return str(status) if status is not None else None


def _derive_goal_blockers(summary: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "authoritative_production_db": {
            "artifact": "production_db_import",
            "status": _artifact_status(summary, "production_db_import"),
            "required_status": "promoted_authoritative_db",
            "blocker": "authoritative production user database on SPB",
        },
        "real_device_evidence": {
            "artifact": "real_device_evidence",
            "status": _artifact_status(summary, "real_device_evidence"),
            "required_status": "real_device_import_verified",
            "blocker": "real client-device import/connect evidence",
        },
        "rkn_tspu_evidence": {
            "artifact": "rkn_tspu_evidence",
            "status": _artifact_status(summary, "rkn_tspu_evidence"),
            "required_status": "external_live_validation_passed",
            "blocker": "external RKN/TSPU path evidence",
        },
        "telegram_poller_coordination": {
            "artifact": "poller_coordination",
            "status": _artifact_status(summary, "poller_coordination"),
            "required_status": "poller_coordination_verified",
            "blocker": "Telegram poller coordination",
        },
    }
    remaining = [
        item["blocker"]
        for item in checks.values()
        if item.get("status") != item.get("required_status")
    ]
    resolved = [
        name
        for name, item in checks.items()
        if item.get("status") == item.get("required_status")
    ]
    deferred_actions: list[str] = []
    if any(name in remaining for name in ("real client-device import/connect evidence", "external RKN/TSPU path evidence")):
        deferred_actions.append("guarded Telegram cutover execute remains blocked until real-device and RKN/TSPU gates pass")
    return {
        "remaining_blockers": remaining,
        "resolved_gates": resolved,
        "gate_checks": checks,
        "deferred_actions": deferred_actions,
    }


async def spb_goal_blockers(args: dict[str, Any]) -> dict[str, Any]:
    """Return simple SPB go-live blockers plus the current read-only summary."""
    summary = await spb_status_summary({"include_services": args.get("include_services", True)})
    blocker_state = _derive_goal_blockers(summary if isinstance(summary, dict) else {})
    return {
        "do_not_touch": ["NL server"],
        "current_scope": "SPB read-only observation through ssh sb",
        "remaining_blockers": blocker_state["remaining_blockers"],
        "resolved_gates": blocker_state["resolved_gates"],
        "gate_checks": blocker_state["gate_checks"],
        "deferred_actions": blocker_state["deferred_actions"],
        "summary": summary,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def spb_read_artifact(args: dict[str, Any]) -> dict[str, Any]:
    """Read one whitelisted SPB artifact by symbolic name."""
    artifact = args.get("artifact")
    if artifact not in ARTIFACTS:
        return {
            "error": "unknown_artifact",
            "allowed": sorted(ARTIFACTS),
        }
    max_chars = int(args.get("max_chars", 12000))
    max_chars = min(max(max_chars, 1000), 24000)
    script = f"""
python3 - <<'PY'
import pathlib
path = pathlib.Path({json.dumps(ARTIFACTS[artifact])})
if not path.exists():
    print({json.dumps('')})
else:
    print(path.read_text(errors="replace")[:{max_chars!r}])
PY
"""
    raw = _ssh_script(script, timeout=20)
    return {
        "artifact": artifact,
        "path": ARTIFACTS[artifact],
        "content": raw["stdout"],
        "exit_code": raw["exit_code"],
        "stderr": raw["stderr"],
        "ssh_host": raw["ssh_host"],
        "timestamp": raw["timestamp"],
    }


async def spb_service_status(args: dict[str, Any]) -> dict[str, Any]:
    """Return systemd status for a small whitelist of SPB service groups."""
    service_group = args.get("service_group", "full_stealth_snapshot")
    if service_group not in SERVICE_GROUPS:
        return {
            "error": "unknown_service_group",
            "allowed": sorted(SERVICE_GROUPS),
        }
    script = f"""
python3 - <<'PY'
import json
import subprocess
from datetime import datetime, timezone

units = {json.dumps(SERVICE_GROUPS[service_group])}
props = [
    "LoadState", "ActiveState", "SubState", "Result", "UnitFileState",
    "ActiveEnterTimestamp", "InactiveEnterTimestamp",
]

def show(unit):
    cmd = ["systemctl", "show", unit] + [f"--property={{p}}" for p in props]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
    parsed = {{"unit": unit, "exit_code": result.returncode}}
    for line in result.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            parsed[key] = value
    if result.stderr:
        parsed["stderr"] = result.stderr[-2000:]
    return parsed

print(json.dumps({{
    "service_group": {json.dumps(service_group)},
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "services": [show(unit) for unit in units],
}}, ensure_ascii=False, indent=2, sort_keys=True))
PY
"""
    return _decode_json_result(_ssh_script(script, timeout=20))


TOOLS = [
    Tool(
        name="spb_status_summary",
        description="Read-only SPB Ghost Access summary from whitelisted artifacts and service status. Uses ssh sb only.",
        inputSchema={
            "type": "object",
            "properties": {
                "include_services": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include read-only systemd show output for whitelisted services.",
                }
            },
        },
    ),
    Tool(
        name="spb_goal_blockers",
        description="Plain SPB go-live blockers and current read-only status. Never touches NL.",
        inputSchema={
            "type": "object",
            "properties": {
                "include_services": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include read-only systemd show output in the embedded summary.",
                }
            },
        },
    ),
    Tool(
        name="spb_read_artifact",
        description="Read one whitelisted SPB status artifact by symbolic name.",
        inputSchema={
            "type": "object",
            "required": ["artifact"],
            "properties": {
                "artifact": {
                    "type": "string",
                    "enum": sorted(ARTIFACTS),
                    "description": "Whitelisted artifact name.",
                },
                "max_chars": {
                    "type": "integer",
                    "default": 12000,
                    "description": "Maximum characters to return, capped at 24000.",
                },
            },
        },
    ),
    Tool(
        name="spb_service_status",
        description="Read-only systemd status for a whitelisted SPB service group.",
        inputSchema={
            "type": "object",
            "properties": {
                "service_group": {
                    "type": "string",
                    "enum": sorted(SERVICE_GROUPS),
                    "default": "full_stealth_snapshot",
                }
            },
        },
    ),
]

TOOL_HANDLERS = {
    "spb_status_summary": spb_status_summary,
    "spb_goal_blockers": spb_goal_blockers,
    "spb_read_artifact": spb_read_artifact,
    "spb_service_status": spb_service_status,
}

app = Server("spb-readonly-mcp")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]
    try:
        result = await handler(arguments or {})
        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
    except Exception as exc:
        return [TextContent(type="text", text=json.dumps({"error": f"{name} failed: {exc}"}))]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
