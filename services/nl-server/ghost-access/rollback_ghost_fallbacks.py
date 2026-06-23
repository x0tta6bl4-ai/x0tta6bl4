#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence


DEFAULT_ENV_PATH = Path("/opt/ghost-access-bot/shared/.env")
DEFAULT_BOT_SERVICE = "telegram-bot-simple.service"
CONFIRM_TOKEN = "ROLLBACK_GHOST_FALLBACKS"
SERVICE_STOP_CONFIRM_TOKEN = "STOP_GHOST_FALLBACK_SERVICES"

FALLBACK_ENV_UPDATES = {
    "EXPOSE_FALLBACK_TRANSPORTS": "0",
    "ENABLE_GHOST_XHTTP_FALLBACK": "0",
    "ENABLE_GHOST_HTTPS_WS_FALLBACK": "0",
}
FALLBACK_SERVICE_UNITS = [
    "ghost-access-nl-xhttp-sync.timer",
    "ghost-access-nl-https-ws-sync.timer",
    "ghost-access-nl-xhttp.service",
    "ghost-access-nl-https-ws.service",
]
FULL_ROLLBACK_EXTRA_UNITS = [
    "ghost-access-transport-usage-evidence.timer",
]
SAFETY_UNITS = [
    "x-ui",
    DEFAULT_BOT_SERVICE,
]


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


Runner = Callable[[Sequence[str]], CommandResult]


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


def now_stamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def parse_env_lines(lines: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def update_env_lines(lines: list[str], updates: dict[str, str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for line in lines:
        if "=" not in line or line.lstrip().startswith("#"):
            result.append(line)
            continue
        key, _value = line.split("=", 1)
        key = key.strip()
        if key in updates:
            result.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            result.append(line)
    for key, value in updates.items():
        if key not in seen:
            result.append(f"{key}={value}")
    return result


def read_env(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []


def unit_status(unit: str, runner: Runner) -> str:
    result = runner(["systemctl", "is-active", unit])
    status = (result.stdout or "").strip()
    if status:
        return status
    return "unknown" if result.returncode else "active"


def current_service_status(runner: Runner, mode: str) -> dict[str, str]:
    units = [DEFAULT_BOT_SERVICE, *FALLBACK_SERVICE_UNITS]
    if mode == "full":
        units.extend(FULL_ROLLBACK_EXTRA_UNITS)
    return {unit: unit_status(unit, runner) for unit in units}


def safety_checks(runner: Runner) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for unit in SAFETY_UNITS:
        status = unit_status(unit, runner)
        checks.append(
            {
                "check": f"{unit}_active",
                "unit": unit,
                "status": status,
                "ok": status == "active",
            }
        )
    return checks


def target_units_for_mode(mode: str) -> list[str]:
    if mode == "delivery-only":
        return []
    units = list(FALLBACK_SERVICE_UNITS)
    if mode == "full":
        units.extend(FULL_ROLLBACK_EXTRA_UNITS)
    return units


def build_plan(env_path: Path, mode: str, runner: Runner = default_runner) -> dict[str, Any]:
    env_values = parse_env_lines(read_env(env_path))
    managed_current = {
        key: env_values.get(key, "<missing>") for key in FALLBACK_ENV_UPDATES
    }
    target_units = target_units_for_mode(mode)
    steps: list[dict[str, Any]] = [
        {
            "action": "backup_env",
            "path": str(env_path),
            "reason": "allow restoring previous subscription delivery flags",
        },
        {
            "action": "set_env_flags",
            "path": str(env_path),
            "values": dict(FALLBACK_ENV_UPDATES),
            "effect": "new subscription payloads stop exposing Ghost XHTTP/WS fallbacks",
        },
        {
            "action": "restart_service",
            "unit": DEFAULT_BOT_SERVICE,
            "effect": "bot reloads subscription delivery flags",
        },
    ]
    for unit in target_units:
        steps.append(
            {
                "action": "disable_now",
                "unit": unit,
                "effect": "stop fallback runtime unit",
            }
        )

    warnings = [
        "dry-run is read-only; use --apply with explicit confirmation to mutate NL",
        "delivery-only rollback keeps existing fallback services running to avoid dropping current fallback sessions",
    ]
    if target_units:
        warnings.append(
            "service-stop/full rollback can break users currently connected through XHTTP/WS"
        )

    return {
        "mode": mode,
        "env_path": str(env_path),
        "current_env_flags": managed_current,
        "target_env_flags": dict(FALLBACK_ENV_UPDATES),
        "service_status": current_service_status(runner, mode),
        "safety_checks": safety_checks(runner),
        "steps": steps,
        "warnings": warnings,
    }


def write_env_atomic(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def apply_plan(
    env_path: Path,
    mode: str,
    *,
    confirm: str | None,
    service_stop_confirm: str | None,
    skip_safety_checks: bool,
    runner: Runner = default_runner,
) -> dict[str, Any]:
    plan = build_plan(env_path, mode, runner)
    errors: list[str] = []
    if confirm != CONFIRM_TOKEN:
        errors.append(f"--confirm must be {CONFIRM_TOKEN}")
    if mode in {"stop-services", "full"} and service_stop_confirm != SERVICE_STOP_CONFIRM_TOKEN:
        errors.append(f"--service-stop-confirm must be {SERVICE_STOP_CONFIRM_TOKEN}")
    if not skip_safety_checks:
        failed = [item for item in plan["safety_checks"] if not item.get("ok")]
        if failed:
            errors.append("safety checks failed: " + ", ".join(item["check"] for item in failed))
    if errors:
        return {
            "decision": "ROLLBACK_BLOCKED",
            "ok": False,
            "errors": errors,
            "plan": plan,
        }

    backup_path = env_path.with_name(f"{env_path.name}.bak-ghost-fallback-rollback-{now_stamp()}")
    if env_path.exists():
        shutil.copy2(env_path, backup_path)
    else:
        backup_path.write_text("", encoding="utf-8")

    updated = update_env_lines(read_env(env_path), FALLBACK_ENV_UPDATES)
    write_env_atomic(env_path, updated)

    commands: list[dict[str, Any]] = []
    restart = runner(["systemctl", "restart", DEFAULT_BOT_SERVICE])
    commands.append(
        {
            "command": ["systemctl", "restart", DEFAULT_BOT_SERVICE],
            "returncode": restart.returncode,
        }
    )
    for unit in target_units_for_mode(mode):
        result = runner(["systemctl", "disable", "--now", unit])
        commands.append(
            {
                "command": ["systemctl", "disable", "--now", unit],
                "returncode": result.returncode,
            }
        )

    verify = build_plan(env_path, mode, runner)
    ok = all(item["returncode"] == 0 for item in commands)
    return {
        "decision": "ROLLBACK_APPLIED" if ok else "ROLLBACK_APPLIED_WITH_ERRORS",
        "ok": ok,
        "backup_path": str(backup_path),
        "commands": commands,
        "post_apply": verify,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Safely roll back Ghost XHTTP/WS fallback delivery on NL."
    )
    parser.add_argument("--env", type=Path, default=DEFAULT_ENV_PATH)
    parser.add_argument(
        "--mode",
        choices=("delivery-only", "stop-services", "full"),
        default="delivery-only",
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm")
    parser.add_argument("--service-stop-confirm")
    parser.add_argument("--skip-safety-checks", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.apply:
        payload = apply_plan(
            args.env,
            args.mode,
            confirm=args.confirm,
            service_stop_confirm=args.service_stop_confirm,
            skip_safety_checks=args.skip_safety_checks,
        )
    else:
        payload = {
            "decision": "ROLLBACK_DRY_RUN",
            "ok": True,
            "apply_required": True,
            "confirm_required": CONFIRM_TOKEN,
            "service_stop_confirm_required": (
                SERVICE_STOP_CONFIRM_TOKEN if args.mode in {"stop-services", "full"} else None
            ),
            "plan": build_plan(args.env, args.mode),
        }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(payload["decision"])
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
