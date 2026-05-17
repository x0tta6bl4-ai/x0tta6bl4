#!/usr/bin/env python3
"""Safe-by-default pilot launcher.

This tool is a transport/runtime plan runner. It must never mutate local or
remote state unless the operator passes --apply-live and the explicit
confirmation token. The default mode is a dry-run plan suitable for handoff and
review.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [PILOT-LAUNCH] - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

ROOT = Path(os.getenv("X0TTA6BL4_ROOT", "/mnt/projects"))
CONTRACTS_DIR = ROOT / "src/dao/contracts"
CONFIRM_TOKEN = "LIVE_PILOT_MUTATION"
PILOT_HOSTS = ("nl", "sb")
REMOTE_AGENT_CMD = (
    "export PYTHONPATH=/tmp/x0t_pilot; "
    "export MAAS_URL=http://127.0.0.1:8012/api/v1/maas; "
    "nohup python3 -m src.agent.headless > /tmp/agent.log 2>&1 &"
)


@dataclass(frozen=True)
class LauncherStep:
    name: str
    argv: tuple[str, ...]
    cwd: Path
    live: bool = False
    background: bool = False
    env: dict[str, str] | None = None
    stdout_path: Path | None = None


def _plan_result(step: LauncherStep) -> dict:
    return {
        "name": step.name,
        "status": "dry-run",
        "argv": list(step.argv),
        "cwd": str(step.cwd),
        "live": step.live,
        "background": step.background,
    }


def _run_step(step: LauncherStep, apply_live: bool) -> dict:
    if step.live and not apply_live:
        return _plan_result(step)

    stdout_handle = None
    try:
        if step.background:
            if step.stdout_path is not None:
                step.stdout_path.parent.mkdir(parents=True, exist_ok=True)
                stdout_handle = step.stdout_path.open("w", encoding="utf-8")
                stdout = stdout_handle
                stderr = subprocess.STDOUT
            else:
                stdout = subprocess.DEVNULL
                stderr = subprocess.DEVNULL

            subprocess.Popen(
                list(step.argv),
                cwd=step.cwd,
                env=step.env,
                stdout=stdout,
                stderr=stderr,
            )
            return {"name": step.name, "status": "started", "argv": list(step.argv)}

        completed = subprocess.run(
            list(step.argv),
            cwd=step.cwd,
            env=step.env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"name": step.name, "status": "failed", "error": "timed out"}
    except OSError as exc:
        return {"name": step.name, "status": "failed", "error": str(exc)}
    finally:
        if stdout_handle is not None:
            stdout_handle.close()

    return {
        "name": step.name,
        "status": "ok" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "stdout": completed.stdout[-1000:],
        "stderr": completed.stderr[-1000:],
    }


def build_plan(root: Path = ROOT, hosts: Sequence[str] = PILOT_HOSTS) -> list[LauncherStep]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root)

    steps: list[LauncherStep] = [
        LauncherStep(
            name="start_hardhat",
            argv=("npx", "hardhat", "node", "--hostname", "127.0.0.1"),
            cwd=root / "src/dao/contracts",
            live=True,
            background=True,
        ),
        LauncherStep(
            name="stop_existing_maas",
            argv=("pkill", "-9", "-f", "maas_light_entrypoint"),
            cwd=root,
            live=True,
        ),
        LauncherStep(
            name="start_control_plane",
            argv=("python3", "-u", "maas_light_entrypoint.py"),
            cwd=root,
            env=env,
            live=True,
            background=True,
            stdout_path=root / "maas_intel.log",
        ),
    ]

    for host in hosts:
        steps.extend(
            [
                LauncherStep(
                    name=f"tunnel_{host}",
                    argv=(
                        "ssh",
                        "-f",
                        "-N",
                        "-o",
                        "ControlMaster=auto",
                        "-o",
                        f"ControlPath=/tmp/ssh-{host}",
                        "-o",
                        "ServerAliveInterval=10",
                        "-R",
                        "8012:127.0.0.1:8012",
                        host,
                    ),
                    cwd=root,
                    live=True,
                ),
                LauncherStep(
                    name=f"prepare_remote_{host}",
                    argv=("ssh", host, "mkdir -p /tmp/x0t_pilot/src"),
                    cwd=root,
                    live=True,
                ),
                LauncherStep(
                    name=f"sync_{host}",
                    argv=("rsync", "-avz", "src/", f"{host}:/tmp/x0t_pilot/src/"),
                    cwd=root,
                    live=True,
                ),
                LauncherStep(
                    name=f"start_agent_{host}",
                    argv=("ssh", host, REMOTE_AGENT_CMD),
                    cwd=root,
                    live=True,
                ),
            ]
        )

    return steps


def run_plan(
    *,
    apply_live: bool = False,
    confirm: str = "",
    root: Path = ROOT,
    hosts: Sequence[str] = PILOT_HOSTS,
    sleep_seconds: float = 0.0,
) -> list[dict]:
    if apply_live and confirm != CONFIRM_TOKEN:
        raise ValueError(f"--apply-live requires --confirm {CONFIRM_TOKEN}")

    results = []
    for step in build_plan(root=root, hosts=hosts):
        logger.info("%s %s", "RUN" if apply_live else "PLAN", step.name)
        results.append(_run_step(step, apply_live=apply_live))
        if apply_live and sleep_seconds > 0 and step.name in {
            "start_hardhat",
            "start_control_plane",
        }:
            time.sleep(sleep_seconds)

    return results


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply-live", action="store_true", help="execute live-mutating steps")
    parser.add_argument("--confirm", default="", help=f"must equal {CONFIRM_TOKEN} with --apply-live")
    parser.add_argument("--host", action="append", choices=PILOT_HOSTS, help="host to include; repeatable")
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument("--output", choices=("text", "json"), default="text")
    return parser.parse_args(argv)


def _result_payload(results: list[dict], *, apply_live: bool, hosts: Sequence[str]) -> dict:
    failed = [item for item in results if item["status"] == "failed"]
    return {
        "ok": not failed,
        "mode": "apply-live" if apply_live else "dry-run",
        "hosts": list(hosts),
        "results": results,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    hosts = tuple(args.host) if args.host else PILOT_HOSTS
    try:
        results = run_plan(
            apply_live=args.apply_live,
            confirm=args.confirm,
            hosts=hosts,
            sleep_seconds=args.sleep_seconds,
        )
    except ValueError as exc:
        logger.error("%s", exc)
        return 2

    payload = _result_payload(results, apply_live=args.apply_live, hosts=hosts)
    if args.output == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for item in results:
            logger.info("%s: %s", item["name"], item["status"])

    if not payload["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
