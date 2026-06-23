#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
from typing import Any, Callable, Sequence


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[1]

DEFAULT_JSON_OUT = Path(
    "nl-diagnostics/nl-anti-block-client-compatibility-runtime-deploy-plan-2026-06-02.json"
)
DEFAULT_MARKDOWN_OUT = Path(
    "nl-diagnostics/nl-anti-block-client-compatibility-runtime-deploy-plan-2026-06-02.md"
)

CONFIRM_TOKEN = "DEPLOY_CLIENT_COMPAT_RUNTIME"
STATUS_API_RESTART_CONFIRM_TOKEN = "RESTART_PROFILE_STATUS_API"

PROFILE_STATUS_UNIT = "x0tta6bl4-profile-status-api.service"
CLIENT_COMPAT_SERVICE = "ghost-access-client-compatibility-summary.service"
CLIENT_COMPAT_TIMER = "ghost-access-client-compatibility-summary.timer"
LOCAL_STATUS_BASE = "http://127.0.0.1:9472"

OBSERVED_UNITS = [
    "x-ui",
    "nginx",
    "telegram-bot-simple.service",
    "ghost-access-nl-xhttp.service",
    "ghost-access-nl-https-ws.service",
    PROFILE_STATUS_UNIT,
]

FORBIDDEN_SERVICE_RESTARTS = [
    "x-ui",
    "nginx",
    "telegram-bot-simple.service",
    "ghost-access-nl-xhttp.service",
    "ghost-access-nl-https-ws.service",
    "ghost-access-nl-xhttp-sync.timer",
    "ghost-access-nl-https-ws-sync.timer",
]

ALLOWED_MUTATION_UNITS = [
    PROFILE_STATUS_UNIT,
    CLIENT_COMPAT_SERVICE,
    CLIENT_COMPAT_TIMER,
]

FORBIDDEN_PATTERNS = {
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


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


@dataclass(frozen=True)
class DeployFile:
    component: str
    local_path: Path
    remote_path: str
    mode: str
    remote_owner: str = "root"
    remote_group: str = "root"
    runtime_generated: bool = False


Runner = Callable[[Sequence[str]], CommandResult]


DEPLOY_FILES = [
    DeployFile(
        "profile_status_api",
        ROOT / "mesh-runtime" / "profile_status_api.py",
        "/opt/x0tta6bl4-mesh/scripts/profile_status_api.py",
        "0644",
    ),
    DeployFile(
        "client_compat_runtime_summary_builder",
        ROOT / "ghost-access" / "build_client_compatibility_runtime_summary.py",
        "/opt/x0tta6bl4-mesh/scripts/build_client_compatibility_runtime_summary.py",
        "0644",
    ),
    DeployFile(
        "client_compat_matrix",
        WORKSPACE / "nl-diagnostics" / "nl-anti-block-client-compatibility-matrix-2026-06-02.json",
        "/var/lib/ghost-access/client-compatibility/matrix.json",
        "0600",
    ),
    DeployFile(
        "client_compat_summary_seed",
        WORKSPACE
        / "nl-diagnostics"
        / "nl-anti-block-client-compatibility-runtime-summary-2026-06-02.json",
        "/var/lib/ghost-access/client-compatibility/latest.json",
        "0600",
        runtime_generated=True,
    ),
    DeployFile(
        "client_compat_systemd_service",
        ROOT / "systemd" / CLIENT_COMPAT_SERVICE,
        f"/etc/systemd/system/{CLIENT_COMPAT_SERVICE}",
        "0644",
    ),
    DeployFile(
        "client_compat_systemd_timer",
        ROOT / "systemd" / CLIENT_COMPAT_TIMER,
        f"/etc/systemd/system/{CLIENT_COMPAT_TIMER}",
        "0644",
    ),
]


class DeployPlanError(ValueError):
    pass


def default_runner(args: Sequence[str]) -> CommandResult:
    completed = subprocess.run(
        list(args),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
        timeout=20,
    )
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return str(path.relative_to(WORKSPACE))


def ssh_command(host: str, remote_command: str) -> list[str]:
    return [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=8",
        host,
        remote_command,
    ]


def run_ssh(host: str, remote_command: str, runner: Runner) -> CommandResult:
    return runner(ssh_command(host, remote_command))


def remote_stdout(host: str, remote_command: str, runner: Runner) -> str:
    result = run_ssh(host, remote_command, runner)
    if result.returncode != 0:
        return ""
    return (result.stdout or "").strip()


def unit_active(host: str, unit: str, runner: Runner) -> str:
    status = remote_stdout(host, f"systemctl is-active {shlex.quote(unit)} 2>/dev/null || true", runner)
    return status or "unknown"


def path_present(host: str, remote_path: str, runner: Runner) -> bool:
    result = run_ssh(host, f"test -e {shlex.quote(remote_path)}", runner)
    return result.returncode == 0


def remote_sha256(host: str, remote_path: str, runner: Runner) -> str | None:
    quoted = shlex.quote(remote_path)
    command = f"sha256sum {quoted} 2>/dev/null | awk '{{print $1}}' || true"
    value = remote_stdout(host, command, runner)
    return value if re.fullmatch(r"[0-9a-f]{64}", value) else None


def http_code(host: str, endpoint_path: str, runner: Runner) -> int:
    command = (
        f"curl -sS -o /dev/null -w '%{{http_code}}' "
        f"--max-time 3 {LOCAL_STATUS_BASE}{endpoint_path} || true"
    )
    value = remote_stdout(host, command, runner)
    try:
        return int(value)
    except ValueError:
        return 0


def file_rows(host: str, runner: Runner) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in DEPLOY_FILES:
        exists = item.local_path.exists()
        local_hash = sha256(item.local_path) if exists else None
        remote_hash = remote_sha256(host, item.remote_path, runner)
        remote_present = path_present(host, item.remote_path, runner)
        remote_matches_local = remote_hash == local_hash if local_hash else False
        rows.append(
            {
                "component": item.component,
                "local_path": rel(item.local_path),
                "remote_path": item.remote_path,
                "mode": item.mode,
                "runtime_generated": item.runtime_generated,
                "local_exists": exists,
                "local_sha256": local_hash,
                "remote_present": remote_present,
                "remote_sha256_known": remote_hash is not None,
                "remote_matches_local": remote_matches_local,
                "remote_ok": remote_present
                and (remote_matches_local or item.runtime_generated),
            }
        )
    return rows


def build_remote_state(host: str, runner: Runner) -> dict[str, Any]:
    return {
        "observed_units": {unit: unit_active(host, unit, runner) for unit in OBSERVED_UNITS},
        "status_api_endpoints": {
            "transport_usage_http_code": http_code(host, "/transport-usage", runner),
            "client_compatibility_http_code": http_code(host, "/client-compatibility", runner),
        },
    }


def build_steps() -> list[dict[str, Any]]:
    return [
        {
            "step": "preflight",
            "action": "read current unit state and endpoint HTTP codes",
            "mutates_nl": False,
        },
        {
            "step": "backup",
            "action": "create timestamped remote backups for changed target files",
            "mutates_nl": True,
            "scope": "allowed target files only",
        },
        {
            "step": "install_files",
            "action": "copy reviewed local source/artifacts into their target paths",
            "mutates_nl": True,
            "scope": "profile status API, client compatibility publisher, matrix, summary, systemd unit/timer",
        },
        {
            "step": "systemd_reload",
            "action": "reload systemd manager configuration",
            "mutates_nl": True,
            "scope": "systemd metadata only",
        },
        {
            "step": "enable_timer",
            "action": "enable and start client compatibility summary timer",
            "mutates_nl": True,
            "scope": CLIENT_COMPAT_TIMER,
        },
        {
            "step": "run_summary_once",
            "action": "clear old failed state and run the client compatibility summary publisher once",
            "mutates_nl": True,
            "scope": CLIENT_COMPAT_SERVICE,
        },
        {
            "step": "restart_status_api",
            "action": "restart profile status API so /client-compatibility route becomes live",
            "mutates_nl": True,
            "scope": PROFILE_STATUS_UNIT,
            "extra_confirmation_required": STATUS_API_RESTART_CONFIRM_TOKEN,
        },
        {
            "step": "postflight",
            "action": "read /transport-usage and /client-compatibility HTTP codes",
            "mutates_nl": False,
        },
    ]


def build_plan(host: str, runner: Runner | None = None) -> dict[str, Any]:
    runner = runner or default_runner
    files = file_rows(host, runner)
    remote_state = build_remote_state(host, runner)
    missing = [row["local_path"] for row in files if not row["local_exists"]]
    endpoint_code = (remote_state.get("status_api_endpoints") or {}).get(
        "client_compatibility_http_code"
    )
    remote_matches_local = bool(files) and all(
        row.get("local_exists") is True and row.get("remote_ok") is True
        for row in files
    )
    decision = (
        "CLIENT_COMPAT_RUNTIME_DEPLOY_BLOCKED"
        if missing
        else "CLIENT_COMPAT_RUNTIME_ALREADY_APPLIED"
        if endpoint_code == 200 and remote_matches_local
        else "CLIENT_COMPAT_RUNTIME_DEPLOY_DRY_RUN"
    )
    plan = {
        "plan_id": "nl-anti-block-client-compatibility-runtime-deploy-plan-2026-06-02",
        "generated_at": utc_now(),
        "decision": decision,
        "ok": not missing,
        "apply_required": decision != "CLIENT_COMPAT_RUNTIME_ALREADY_APPLIED",
        "applied_to_nl": False,
        "dry_run_mutated_nl": False,
        "ssh_host_label": host,
        "confirm_required": CONFIRM_TOKEN,
        "status_api_restart_confirm_required": STATUS_API_RESTART_CONFIRM_TOKEN,
        "current_blocker": (
            "nl_client_compatibility_endpoint_missing"
            if endpoint_code == 404
            else "none"
            if decision == "CLIENT_COMPAT_RUNTIME_ALREADY_APPLIED"
            else "nl_client_compatibility_runtime_incomplete"
        ),
        "local_missing_files": missing,
        "files": files,
        "remote_state": remote_state,
        "steps": build_steps(),
        "mutation_policy": {
            "default_mode": "dry_run",
            "dry_run_mutates_nl": False,
            "apply_requires_confirm": CONFIRM_TOKEN,
            "status_api_restart_requires_confirm": STATUS_API_RESTART_CONFIRM_TOKEN,
            "allowed_mutation_units": list(ALLOWED_MUTATION_UNITS),
            "forbidden_service_restarts": list(FORBIDDEN_SERVICE_RESTARTS),
            "will_not_touch": [
                "x-ui config/database",
                "nginx config",
                "telegram bot service/env",
                "Ghost XHTTP fallback service",
                "Ghost HTTPS WS fallback service",
                "subscription tokens or VPN profile URIs",
            ],
            "allowed_target_paths": [item.remote_path for item in DEPLOY_FILES],
        },
        "privacy": {
            "output_privacy_ok": True,
            "raw_ssh_config_stored": False,
            "raw_ip_stored": False,
            "raw_subscription_url_stored": False,
            "raw_vpn_uri_stored": False,
            "raw_uuid_stored": False,
            "raw_email_stored": False,
            "raw_phone_stored": False,
            "raw_telegram_handle_stored": False,
            "raw_client_rows_stored": False,
            "raw_commands_stored": False,
        },
    }
    findings = privacy_findings(plan)
    if findings:
        plan["ok"] = False
        plan["decision"] = "CLIENT_COMPAT_RUNTIME_DEPLOY_PRIVACY_BLOCKED"
        plan["privacy"]["output_privacy_ok"] = False
        plan["privacy_findings"] = findings
    return plan


def privacy_findings(payload: dict[str, Any]) -> list[dict[str, str]]:
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return [
        {"kind": name}
        for name, pattern in FORBIDDEN_PATTERNS.items()
        if pattern.search(rendered)
    ]


def mutation_call_allowed(args: Sequence[str]) -> bool:
    rendered = " ".join(str(part) for part in args)
    return not any(
        re.search(rf"\bsystemctl\s+(restart|reload|stop|disable|enable|start).*{re.escape(unit)}\b", rendered)
        for unit in FORBIDDEN_SERVICE_RESTARTS
    )


def run_apply_commands(
    host: str,
    *,
    runner: Runner,
    restart_status_api: bool,
) -> list[dict[str, Any]]:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    remote_stage = f"/tmp/x0tta6bl4-client-compat-runtime-deploy-{stamp}"
    commands: list[dict[str, Any]] = []

    def record(label: str, args: Sequence[str]) -> bool:
        if not mutation_call_allowed(args):
            commands.append({"label": label, "returncode": 99, "allowed": False})
            return False
        result = runner(args)
        commands.append(
            {
                "label": label,
                "returncode": result.returncode,
                "allowed": True,
            }
        )
        return result.returncode == 0

    record("create_remote_stage", ssh_command(host, f"install -d -m 0700 {shlex.quote(remote_stage)}"))
    for item in DEPLOY_FILES:
        staged = f"{remote_stage}/{item.local_path.name}"
        record(
            f"upload:{item.component}",
            [
                "scp",
                "-q",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=8",
                str(item.local_path),
                f"{host}:{staged}",
            ],
        )
        remote_dir = shlex.quote(str(Path(item.remote_path).parent))
        remote_path = shlex.quote(item.remote_path)
        staged_path = shlex.quote(staged)
        backup = shlex.quote(f"{item.remote_path}.bak-client-compat-{stamp}")
        install_cmd = (
            f"install -d -m 0755 -o root -g root {remote_dir} && "
            f"if test -e {remote_path}; then cp -a {remote_path} {backup}; fi && "
            f"install -m {item.mode} -o {shlex.quote(item.remote_owner)} "
            f"-g {shlex.quote(item.remote_group)} {staged_path} {remote_path}"
        )
        record(f"install:{item.component}", ssh_command(host, install_cmd))
    record("systemd_daemon_reload", ssh_command(host, "systemctl daemon-reload"))
    record(
        "enable_client_compat_timer",
        ssh_command(host, f"systemctl enable --now {CLIENT_COMPAT_TIMER}"),
    )
    record(
        "reset_failed_client_compat_summary",
        ssh_command(host, f"systemctl reset-failed {CLIENT_COMPAT_SERVICE} || true"),
    )
    record(
        "run_client_compat_summary_once",
        ssh_command(host, f"systemctl start {CLIENT_COMPAT_SERVICE}"),
    )
    if restart_status_api:
        record("restart_profile_status_api", ssh_command(host, f"systemctl restart {PROFILE_STATUS_UNIT}"))
    record("remove_remote_stage", ssh_command(host, f"rm -rf {shlex.quote(remote_stage)}"))
    return commands


def apply_plan(
    host: str,
    *,
    confirm: str | None,
    restart_status_api: bool,
    status_api_restart_confirm: str | None,
    runner: Runner | None = None,
) -> dict[str, Any]:
    runner = runner or default_runner
    plan = build_plan(host, runner)
    errors: list[str] = []
    if confirm != CONFIRM_TOKEN:
        errors.append(f"--confirm must be {CONFIRM_TOKEN}")
    if restart_status_api and status_api_restart_confirm != STATUS_API_RESTART_CONFIRM_TOKEN:
        errors.append(f"--status-api-restart-confirm must be {STATUS_API_RESTART_CONFIRM_TOKEN}")
    if not plan.get("ok"):
        errors.append(f"dry-run plan is not ok: {plan.get('decision')}")
    if errors:
        return {
            "decision": "CLIENT_COMPAT_RUNTIME_DEPLOY_BLOCKED",
            "ok": False,
            "errors": errors,
            "plan": plan,
        }

    commands = run_apply_commands(host, runner=runner, restart_status_api=restart_status_api)
    ok = all(command.get("returncode") == 0 and command.get("allowed") is True for command in commands)
    post_apply = build_plan(host, runner)
    return {
        "decision": "CLIENT_COMPAT_RUNTIME_DEPLOY_APPLIED"
        if ok
        else "CLIENT_COMPAT_RUNTIME_DEPLOY_APPLIED_WITH_ERRORS",
        "ok": ok,
        "commands": commands,
        "post_apply": post_apply,
        "privacy": {
            "output_privacy_ok": True,
            "raw_commands_stored": False,
            "raw_ip_stored": False,
            "raw_vpn_uri_stored": False,
            "raw_subscription_url_stored": False,
        },
    }


def markdown_cell(value: Any) -> str:
    if value is None:
        text = ""
    elif isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, (list, tuple)):
        text = ", ".join(markdown_cell(item) for item in value)
    elif isinstance(value, dict):
        text = ", ".join(f"{key}={markdown_cell(nested)}" for key, nested in value.items())
    else:
        text = str(value)
    return text.replace("|", "\\|").replace("\n", " ").strip()


def render_markdown(payload: dict[str, Any]) -> str:
    units = ((payload.get("remote_state") or {}).get("observed_units") or {})
    endpoints = ((payload.get("remote_state") or {}).get("status_api_endpoints") or {})
    lines = [
        "# NL Anti-Block Client Compatibility Runtime Deploy Plan - 2026-06-02",
        "",
        "## Decision",
        "",
        f"`{markdown_cell(payload.get('decision'))}`",
        "",
        "Dry-run deploy packet. It does not copy files, restart services, reload systemd, enable timers, change x-ui, change nginx, change the bot, or touch fallback services unless explicit apply confirmation is used later.",
        "",
        "## Runtime State",
        "",
        "| Item | Status |",
        "| --- | --- |",
        f"| /transport-usage | HTTP {markdown_cell(endpoints.get('transport_usage_http_code'))} |",
        f"| /client-compatibility | HTTP {markdown_cell(endpoints.get('client_compatibility_http_code'))} |",
    ]
    for unit in OBSERVED_UNITS:
        lines.append(f"| {markdown_cell(unit)} | {markdown_cell(units.get(unit))} |")
    lines.extend(
        [
            "",
            "## Target Files",
            "",
            "| Component | Remote Target | Local Exists | Remote Matches Local |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in payload.get("files") or []:
        if not isinstance(row, dict):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    markdown_cell(row.get("component")),
                    markdown_cell(row.get("remote_path")),
                    markdown_cell(row.get("local_exists")),
                    markdown_cell(row.get("remote_matches_local")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Mutation Policy",
            "",
            f"- Apply requires `{CONFIRM_TOKEN}`.",
            f"- Profile status API restart additionally requires `{STATUS_API_RESTART_CONFIRM_TOKEN}`.",
            "- Forbidden restarts: "
            + markdown_cell((payload.get("mutation_policy") or {}).get("forbidden_service_restarts")),
            "- Allowed units: "
            + markdown_cell((payload.get("mutation_policy") or {}).get("allowed_mutation_units")),
            "",
        ]
    )
    return "\n".join(lines)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(payload), encoding="utf-8")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Dry-run-first deploy packet for NL /client-compatibility runtime support."
    )
    p.add_argument("--ssh-host", default="nl")
    p.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    p.add_argument("--markdown-out", type=Path, default=DEFAULT_MARKDOWN_OUT)
    p.add_argument("--write", action="store_true")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--confirm")
    p.add_argument("--restart-status-api", action="store_true")
    p.add_argument("--status-api-restart-confirm")
    p.add_argument("--json", action="store_true")
    return p


def run(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.apply:
            payload = apply_plan(
                args.ssh_host,
                confirm=args.confirm,
                restart_status_api=args.restart_status_api,
                status_api_restart_confirm=args.status_api_restart_confirm,
            )
        else:
            payload = build_plan(args.ssh_host)
        if args.write:
            write_json(args.json_out, payload)
            write_markdown(args.markdown_out, payload)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(f"ok={str(payload.get('ok')).lower()} decision={payload.get('decision')}")
        return 0 if payload.get("ok") else 1
    except DeployPlanError as exc:
        payload = {"ok": False, "error": str(exc)}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(f"ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(run())
