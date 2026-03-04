#!/usr/bin/env python3
"""Preflight and smoke checks for x0tta mesh operator operations."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Sequence

DEFAULT_NAMESPACE = "x0tta-mesh-system"
DEFAULT_RELEASE = "x0tta-mesh"
DEFAULT_WAIT_SECONDS = 180
MESH_CRD = "meshclusters.x0tta6bl4.io"


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    details: str


Runner = Callable[[Sequence[str], int], CommandResult]
Which = Callable[[str], str | None]


def _run_command(command: Sequence[str], timeout: int = 30) -> CommandResult:
    try:
        completed = subprocess.run(
            list(command),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        tool = command[0] if command else "unknown"
        return CommandResult(returncode=127, stdout="", stderr=f"command not found: {tool}")
    except subprocess.TimeoutExpired:
        rendered = " ".join(command)
        return CommandResult(returncode=124, stdout="", stderr=f"timeout after {timeout}s: {rendered}")

    return CommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout.strip(),
        stderr=completed.stderr.strip(),
    )


def _check_tool(tool: str, which: Which) -> CheckResult:
    if "/" in tool:
        candidate = Path(tool)
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return CheckResult(name=f"tool:{tool}", ok=True, details=str(candidate))
        return CheckResult(name=f"tool:{tool}", ok=False, details="path is not executable")

    path = which(tool)
    if path:
        return CheckResult(name=f"tool:{tool}", ok=True, details=path)
    return CheckResult(name=f"tool:{tool}", ok=False, details="not found in PATH")


def _check_current_context(kubectl: str, run: Runner) -> CheckResult:
    result = run([kubectl, "config", "current-context"], 15)
    if result.returncode != 0:
        details = result.stderr or result.stdout or "kubectl current-context failed"
        return CheckResult(name="kubectl-context", ok=False, details=details)
    if not result.stdout:
        return CheckResult(name="kubectl-context", ok=False, details="no current context configured")
    return CheckResult(name="kubectl-context", ok=True, details=result.stdout)


def _check_cluster_reachable(kubectl: str, run: Runner) -> CheckResult:
    result = run([kubectl, "cluster-info"], 45)
    if result.returncode == 0:
        return CheckResult(name="cluster-reachable", ok=True, details="kubectl cluster-info succeeded")
    details = result.stderr or result.stdout or "kubectl cluster-info failed"
    return CheckResult(name="cluster-reachable", ok=False, details=details)


def _check_namespace(kubectl: str, namespace: str, run: Runner) -> CheckResult:
    result = run([kubectl, "get", "namespace", namespace, "-o", "name"], 20)
    if result.returncode == 0:
        details = result.stdout or f"namespace/{namespace}"
        return CheckResult(name="namespace", ok=True, details=details)
    details = result.stderr or result.stdout or f"namespace {namespace} not found"
    return CheckResult(name="namespace", ok=False, details=details)


def _check_crd(kubectl: str, run: Runner) -> CheckResult:
    result = run([kubectl, "get", "crd", MESH_CRD, "-o", "name"], 20)
    if result.returncode == 0:
        details = result.stdout or MESH_CRD
        return CheckResult(name="mesh-crd", ok=True, details=details)
    details = result.stderr or result.stdout or f"crd {MESH_CRD} not found"
    return CheckResult(name="mesh-crd", ok=False, details=details)


def _check_rollout(
    kubectl: str,
    namespace: str,
    deployment: str,
    wait_seconds: int,
    run: Runner,
) -> CheckResult:
    result = run(
        [
            kubectl,
            "rollout",
            "status",
            f"deployment/{deployment}",
            "-n",
            namespace,
            f"--timeout={wait_seconds}s",
        ],
        wait_seconds + 15,
    )
    if result.returncode == 0:
        details = result.stdout or f"deployment/{deployment} available"
        return CheckResult(name="rollout", ok=True, details=details)
    details = result.stderr or result.stdout or f"rollout failed for deployment/{deployment}"
    return CheckResult(name="rollout", ok=False, details=details)


def _check_metrics_service(kubectl: str, namespace: str, service: str, run: Runner) -> CheckResult:
    result = run([kubectl, "get", "svc", service, "-n", namespace, "-o", "name"], 20)
    if result.returncode == 0:
        details = result.stdout or f"service/{service}"
        return CheckResult(name="metrics-service", ok=True, details=details)
    details = result.stderr or result.stdout or f"service {service} not found"
    return CheckResult(name="metrics-service", ok=False, details=details)


def _check_ready_replicas(kubectl: str, namespace: str, deployment: str, run: Runner) -> CheckResult:
    result = run(
        [
            kubectl,
            "get",
            "deployment",
            deployment,
            "-n",
            namespace,
            "-o",
            "jsonpath={.status.readyReplicas}",
        ],
        20,
    )
    if result.returncode != 0:
        details = result.stderr or result.stdout or f"deployment {deployment} not found"
        return CheckResult(name="ready-replicas", ok=False, details=details)

    ready_value = result.stdout.strip()
    if not ready_value:
        return CheckResult(name="ready-replicas", ok=False, details="readyReplicas is empty")

    try:
        ready = int(ready_value)
    except ValueError:
        return CheckResult(name="ready-replicas", ok=False, details=f"invalid readyReplicas: {ready_value}")

    if ready <= 0:
        return CheckResult(name="ready-replicas", ok=False, details=f"readyReplicas={ready}")
    return CheckResult(name="ready-replicas", ok=True, details=f"readyReplicas={ready}")


def run_preflight(
    *,
    require_cluster: bool,
    kubectl: str = "kubectl",
    run: Runner = _run_command,
    which: Which = shutil.which,
) -> list[CheckResult]:
    checks: list[CheckResult] = [
        _check_tool(kubectl, which),
        _check_current_context(kubectl, run),
    ]
    if require_cluster:
        checks.append(_check_cluster_reachable(kubectl, run))
    return checks


def run_smoke(
    *,
    namespace: str,
    release: str,
    wait_seconds: int,
    kubectl: str = "kubectl",
    run: Runner = _run_command,
) -> list[CheckResult]:
    deployment = f"{release}-x0tta-mesh-operator"
    service = f"{release}-x0tta-mesh-operator-metrics"
    return [
        _check_namespace(kubectl, namespace, run),
        _check_crd(kubectl, run),
        _check_rollout(kubectl, namespace, deployment, wait_seconds, run),
        _check_metrics_service(kubectl, namespace, service, run),
        _check_ready_replicas(kubectl, namespace, deployment, run),
    ]


def _checks_ok(checks: list[CheckResult]) -> bool:
    return all(check.ok for check in checks)


def _render_text(checks: list[CheckResult]) -> str:
    lines = []
    for check in checks:
        status = "PASS" if check.ok else "FAIL"
        lines.append(f"[{status}] {check.name}: {check.details}")
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="x0tta mesh operator health checks")
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight_parser = subparsers.add_parser("preflight", help="Validate local kubectl preconditions")
    preflight_parser.add_argument(
        "--require-cluster",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Require kubectl cluster-info to succeed (default: true)",
    )
    preflight_parser.add_argument(
        "--kubectl",
        default=os.environ.get("MESH_OPERATOR_KUBECTL", "kubectl"),
        help="kubectl executable or wrapper path",
    )
    preflight_parser.add_argument("--output", choices=("text", "json"), default="text")

    smoke_parser = subparsers.add_parser("smoke", help="Validate deployed mesh operator resources")
    smoke_parser.add_argument("--namespace", default=DEFAULT_NAMESPACE)
    smoke_parser.add_argument("--release", default=DEFAULT_RELEASE)
    smoke_parser.add_argument("--wait-seconds", type=int, default=DEFAULT_WAIT_SECONDS)
    smoke_parser.add_argument(
        "--kubectl",
        default=os.environ.get("MESH_OPERATOR_KUBECTL", "kubectl"),
        help="kubectl executable or wrapper path",
    )
    smoke_parser.add_argument("--output", choices=("text", "json"), default="text")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "preflight":
        checks = run_preflight(require_cluster=args.require_cluster, kubectl=args.kubectl)
    elif args.command == "smoke":
        if args.wait_seconds <= 0:
            parser.error("--wait-seconds must be greater than 0")
        checks = run_smoke(
            namespace=args.namespace,
            release=args.release,
            wait_seconds=args.wait_seconds,
            kubectl=args.kubectl,
        )
    else:
        parser.error(f"unsupported command: {args.command}")
        return 2

    ok = _checks_ok(checks)
    if args.output == "json":
        payload = {
            "ok": ok,
            "checks": [asdict(check) for check in checks],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(_render_text(checks))

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
