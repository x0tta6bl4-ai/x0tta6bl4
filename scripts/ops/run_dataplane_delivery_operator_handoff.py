#!/usr/bin/env python3
"""Build a safe local handoff for dataplane-delivery operator probes.

This command is read-only. It validates operator-provided target metadata and
prints the exact local commands needed to collect bounded EventBus evidence.
It never opens a socket, writes EventBus events, or promotes customer traffic,
external reachability, DPI bypass, settlement finality, production SLO, or
production readiness claims by itself.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import shlex
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "x0tta6bl4.dataplane_delivery_operator_handoff.v1"
DECISION_READY = "DATAPLANE_DELIVERY_OPERATOR_HANDOFF_READY"
DECISION_BLOCKED = "DATAPLANE_DELIVERY_OPERATOR_HANDOFF_BLOCKED_ON_OPERATOR"
CLAIM_BOUNDARY = (
    "Read-only operator handoff for bounded dataplane-delivery evidence. It "
    "can make the next local probe commands explicit, but it does not prove customer traffic, "
    "external reachability, DPI bypass, settlement finality, "
    "production SLOs, or production readiness."
)
COLLECT_COMMAND = (
    'python3 scripts/ops/collect_dataplane_delivery_eventbus_evidence.py --root . '
    '--host "$X0T_DATAPLANE_PROBE_HOST" --port "$X0T_DATAPLANE_PROBE_PORT" '
    "--allow-local-probe --write-event --json"
)
PROOF_GATE_COMMAND = (
    "python3 scripts/ops/run_cross_plane_proof_gate.py --claim dataplane_delivery "
    "--json --output-json .tmp/validation-shards/cross-plane-proof-gate-current.json"
)
RETENTION_COMMAND = (
    "python3 scripts/ops/verify_cross_plane_proof_gate_retention.py "
    "--require-valid --json"
)
OPERATOR_EVIDENCE_COMMAND = (
    'python3 scripts/ops/run_dataplane_delivery_operator_evidence.py --root . '
    '--target-host "$X0T_DATAPLANE_PROBE_HOST" '
    '--target-port "$X0T_DATAPLANE_PROBE_PORT" '
    "--allow-operator-probe --require-retained --json"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--target-host",
        default=os.environ.get("X0T_DATAPLANE_PROBE_HOST", ""),
        help="Private, loopback, or link-local target host. Defaults to env.",
    )
    parser.add_argument(
        "--target-port",
        default=os.environ.get("X0T_DATAPLANE_PROBE_PORT", ""),
        help="Target TCP port. Defaults to env.",
    )
    parser.add_argument(
        "--target-label",
        default=os.environ.get("X0T_DATAPLANE_PROBE_LABEL", "operator-target"),
    )
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def is_localish_target(host: str) -> bool:
    normalized = host.strip().lower()
    if normalized == "localhost":
        return True
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        return False
    return address.is_loopback or address.is_private or address.is_link_local


def parse_port(value: Any) -> tuple[int | None, list[str]]:
    try:
        port = int(str(value).strip())
    except (TypeError, ValueError):
        return None, ["target_port_required_or_invalid"]
    if not 1 <= port <= 65535:
        return None, ["target_port_out_of_range"]
    return port, []


def _python_command_entrypoint(command: str) -> str:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return ""
    if len(tokens) >= 2 and tokens[0].startswith("python") and tokens[1].endswith(".py"):
        return tokens[1]
    return ""


def _shell_redirection_placeholder(command: str) -> str:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return "unparseable command"
    for token in tokens:
        if token.startswith("<") or token.startswith(">") or token.endswith(">"):
            return token
    return ""


def operator_command_checks(root: Path) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for action_id, command in (
        ("collect_dataplane_delivery_eventbus_evidence", COLLECT_COMMAND),
        ("run_cross_plane_proof_gate", PROOF_GATE_COMMAND),
        ("verify_cross_plane_proof_gate_retention", RETENTION_COMMAND),
        ("run_dataplane_delivery_operator_evidence", OPERATOR_EVIDENCE_COMMAND),
    ):
        entrypoint = _python_command_entrypoint(command)
        redirection = _shell_redirection_placeholder(command)
        checks.append(
            {
                "action_id": action_id,
                "command": command,
                "expected_entrypoint": entrypoint,
                "entrypoint_exists": bool(entrypoint and (root / entrypoint).is_file()),
                "shell_redirection_placeholder": redirection,
                "shell_redirection_placeholder_detected": bool(redirection),
            }
        )
    return checks


def build_report(
    root: Path,
    *,
    target_host: str = "",
    target_port: Any = "",
    target_label: str = "operator-target",
) -> dict[str, Any]:
    root = root.resolve()
    host = str(target_host or "").strip()
    port, port_errors = parse_port(target_port)
    blockers: list[str] = []
    if not host:
        blockers.append("target_host_required")
    elif not is_localish_target(host):
        blockers.append("target_must_be_loopback_private_or_link_local")
    blockers.extend(port_errors)

    checks = operator_command_checks(root)
    command_surface_ready = all(
        check.get("entrypoint_exists") is True
        and check.get("shell_redirection_placeholder_detected") is False
        for check in checks
    )
    if not command_surface_ready:
        blockers.append("operator_command_surface_not_ready")

    ready = not blockers
    return {
        "schema": SCHEMA,
        "timestamp_utc": utc_now(),
        "decision": DECISION_READY if ready else DECISION_BLOCKED,
        "ready_for_operator_run": ready,
        "mutates_runtime": False,
        "runs_probe": False,
        "writes_eventbus": False,
        "target": {
            "label": str(target_label or "operator-target"),
            "host_hash": sha256_text(host) if host else None,
            "host_present": bool(host),
            "port": port,
            "target_is_localish": bool(host and is_localish_target(host)),
            "raw_target_redacted": True,
        },
        "blockers": blockers,
        "operator_env_vars": [
            "X0T_DATAPLANE_PROBE_HOST",
            "X0T_DATAPLANE_PROBE_PORT",
            "X0T_DATAPLANE_PROBE_LABEL",
        ],
        "operator_commands": [
            {
                "id": "collect_dataplane_delivery_eventbus_evidence",
                "status": "READY" if ready else "OPERATOR_INPUT_REQUIRED",
                "command": COLLECT_COMMAND,
                "writes_eventbus": True,
                "runs_probe": True,
            },
            {
                "id": "run_cross_plane_proof_gate",
                "status": "READY" if ready else "WAITING_FOR_EVENTBUS_EVIDENCE",
                "command": PROOF_GATE_COMMAND,
                "writes_retained_artifact": True,
            },
            {
                "id": "verify_cross_plane_proof_gate_retention",
                "status": "READY" if ready else "WAITING_FOR_RETAINED_ARTIFACT",
                "command": RETENTION_COMMAND,
                "runs_probe": False,
            },
            {
                "id": "run_dataplane_delivery_operator_evidence",
                "status": "READY" if ready else "OPERATOR_INPUT_REQUIRED",
                "command": OPERATOR_EVIDENCE_COMMAND,
                "writes_eventbus": True,
                "writes_retained_artifact": True,
                "runs_probe": True,
            },
        ],
        "operator_command_checks": checks,
        "safe_local_input_steps": [
            "Set X0T_DATAPLANE_PROBE_HOST locally to a loopback, private, or link-local host.",
            "Set X0T_DATAPLANE_PROBE_PORT locally to the TCP port to probe.",
            "Run this handoff with --require-ready before collecting EventBus evidence.",
            "Run the listed collect/proof-gate/retention commands locally; do not paste private targets into chat.",
        ],
        "claim_boundary": CLAIM_BOUNDARY,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(
        args.root,
        target_host=args.target_host,
        target_port=args.target_port,
        target_label=args.target_label,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"decision={report['decision']}")
        print(f"ready_for_operator_run={report['ready_for_operator_run']}")
        for blocker in report["blockers"]:
            print(f"- {blocker}")
    return 0 if report["ready_for_operator_run"] or not args.require_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
