#!/usr/bin/env python3
"""Run and verify retained dataplane evidence against a private non-loopback target.

This is an authorized local-operator harness. It starts one temporary TCP
listener on a private non-loopback address owned by this host, runs the bounded
operator evidence runner against that target, and validates that the retained
EventBus/proof-gate artifacts stay redacted and do not promote customer,
external-reachability, traffic, DPI, settlement, SLO, or production claims.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import socket
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.ops import run_dataplane_delivery_operator_evidence as operator_evidence


SCHEMA = "x0tta6bl4.dataplane_delivery_private_target_operator_run.v1"
DECISION_RETAINED = "DATAPLANE_PRIVATE_TARGET_OPERATOR_RUN_RETAINED"
DECISION_BLOCKED = "DATAPLANE_PRIVATE_TARGET_OPERATOR_RUN_BLOCKED"
DECISION_GAPS = "DATAPLANE_PRIVATE_TARGET_OPERATOR_RUN_GAPS"
DEFAULT_OUTPUT_JSON = Path(
    ".tmp/validation-shards/dataplane-delivery-private-target-operator-run-current.json"
)
DEFAULT_OPERATOR_OUTPUT_JSON = Path(
    ".tmp/validation-shards/dataplane-delivery-private-target-operator-evidence-current.json"
)
DEFAULT_PROOF_GATE_OUTPUT_JSON = Path(
    ".tmp/validation-shards/cross-plane-proof-gate-current.json"
)
CLAIM_BOUNDARY = (
    "Private-target dataplane operator-run verifier. It retains one redacted "
    "local/private non-loopback TCP probe EventBus event and proof-gate report "
    "from an authorized local harness only. It does not prove customer traffic, "
    "external reachability, DPI bypass, settlement finality, production SLOs, "
    "or production readiness."
)

ServerFactory = Callable[[str], tuple[Any, Any, int]]
OperatorRunner = Callable[..., dict[str, Any]]


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def is_private_non_loopback_target(host: str) -> bool:
    try:
        address = ipaddress.ip_address(str(host).strip())
    except ValueError:
        return False
    return bool(
        address.version == 4
        and address.is_private
        and not address.is_loopback
        and not address.is_link_local
        and not address.is_unspecified
        and not address.is_multicast
    )


def _candidate_private_hosts() -> list[str]:
    candidates: list[str] = []
    try:
        result = subprocess.run(
            ["ip", "-4", "-o", "addr", "show", "scope", "global"],
            check=False,
            text=True,
            capture_output=True,
            timeout=5,
        )
    except Exception:
        result = None
    if result is not None and result.returncode == 0:
        for line in result.stdout.splitlines():
            parts = line.split()
            if "inet" not in parts:
                continue
            value = parts[parts.index("inet") + 1].split("/", 1)[0]
            if is_private_non_loopback_target(value):
                candidates.append(value)

    try:
        for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            value = item[4][0]
            if is_private_non_loopback_target(value):
                candidates.append(value)
    except OSError:
        pass

    return list(dict.fromkeys(candidates))


def _serve_one_private_connection(host: str) -> tuple[socket.socket, threading.Thread, int]:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, 0))  # lgtm[py/bind-socket-all-network-interfaces]
    server.listen(1)
    port = int(server.getsockname()[1])

    def _accept_once() -> None:
        try:
            server.settimeout(5.0)
            conn, _addr = server.accept()
            with conn:
                conn.settimeout(1.0)
                try:
                    conn.recv(1)
                except (TimeoutError, socket.timeout):
                    pass
        finally:
            server.close()

    thread = threading.Thread(target=_accept_once, daemon=True)
    thread.start()
    return server, thread, port


def _target_summary(host: str, *, candidates_count: int) -> dict[str, Any]:
    return {
        "host_hash": sha256_text(host) if host else None,
        "host_present": bool(host),
        "private_non_loopback": bool(host and is_private_non_loopback_target(host)),
        "candidate_private_targets_count": max(0, candidates_count),
        "raw_target_redacted": True,
    }


def _validate_operator_report(
    report: Mapping[str, Any],
    *,
    raw_target: str,
) -> list[str]:
    failures: list[str] = []
    summary = _mapping(report.get("summary"))
    collector = _mapping(report.get("collector"))
    proof_gate = _mapping(report.get("proof_gate"))
    selected_event = _mapping(proof_gate.get("selected_event"))
    rendered = json.dumps(report, ensure_ascii=False, sort_keys=True)

    if report.get("decision") != operator_evidence.DECISION_RETAINED:
        failures.append("operator_evidence_not_retained")
    if report.get("ok") is not True:
        failures.append("operator_evidence_not_ok")
    if summary.get("operator_run_evidence_retained") is not True:
        failures.append("operator_run_evidence_not_retained")
    if summary.get("opens_socket") is not True:
        failures.append("operator_socket_not_opened")
    if summary.get("writes_eventbus") is not True:
        failures.append("operator_eventbus_not_written")
    if summary.get("writes_validation_artifacts") is not True:
        failures.append("operator_artifacts_not_written")
    if summary.get("raw_targets_redacted") is not True:
        failures.append("operator_target_not_redacted")
    if summary.get("customer_traffic_claimed") is not False:
        failures.append("operator_overclaimed_customer_traffic")
    if summary.get("traffic_delivery_claimed") is not False:
        failures.append("operator_overclaimed_traffic_delivery")
    if summary.get("production_readiness_claimed") is not False:
        failures.append("operator_overclaimed_production_readiness")
    if collector.get("raw_target_redacted") is not True:
        failures.append("collector_target_not_redacted")
    if proof_gate.get("artifact_valid") is not True:
        failures.append("proof_gate_artifact_not_valid")
    if selected_event.get("dataplane_confirmed") is not True:
        failures.append("selected_event_dataplane_not_confirmed")
    if selected_event.get("restored_dataplane_claim_allowed") is not True:
        failures.append("selected_event_restored_dataplane_not_allowed")
    if selected_event.get("traffic_delivery_claim_allowed") is not False:
        failures.append("selected_event_overclaimed_traffic_delivery")
    if selected_event.get("customer_traffic_claim_allowed") is not False:
        failures.append("selected_event_overclaimed_customer_traffic")
    if selected_event.get("production_readiness_claim_allowed") is not False:
        failures.append("selected_event_overclaimed_production_readiness")
    if selected_event.get("redacted") is not True:
        failures.append("selected_event_not_redacted")
    if raw_target and raw_target in rendered:
        failures.append("raw_target_leaked")
    return failures


def build_report(
    root: Path,
    *,
    target_host: str = "",
    target_label: str = "private-target-operator-run",
    timeout_s: float = 2.0,
    allow_private_target_probe: bool = False,
    output_json: Path = DEFAULT_OUTPUT_JSON,
    operator_output_json: Path = DEFAULT_OPERATOR_OUTPUT_JSON,
    proof_gate_output_json: Path = DEFAULT_PROOF_GATE_OUTPUT_JSON,
    host_candidates: Sequence[str] | None = None,
    server_factory: ServerFactory = _serve_one_private_connection,
    operator_runner: OperatorRunner = operator_evidence.build_report,
) -> dict[str, Any]:
    root = root.resolve()
    candidates = list(host_candidates) if host_candidates is not None else _candidate_private_hosts()
    host = str(target_host or "").strip() or (candidates[0] if candidates else "")
    output_json = output_json if output_json.is_absolute() else root / output_json
    operator_output_json = (
        operator_output_json if operator_output_json.is_absolute() else root / operator_output_json
    )
    proof_gate_output_json = (
        proof_gate_output_json
        if proof_gate_output_json.is_absolute()
        else root / proof_gate_output_json
    )
    blockers: list[str] = []
    if not host:
        blockers.append("private_non_loopback_target_missing")
    elif not is_private_non_loopback_target(host):
        blockers.append("private_non_loopback_target_required")
    if not allow_private_target_probe:
        blockers.append("allow_private_target_probe_required")

    base = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "decision": DECISION_BLOCKED,
        "ok": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "target": _target_summary(host, candidates_count=len(candidates)),
        "summary": {
            "private_non_loopback_target": bool(
                host and is_private_non_loopback_target(host)
            ),
            "server_started": False,
            "operator_run_attempted": False,
            "operator_run_evidence_retained": False,
            "eventbus_evidence_recognized_by_proof_gate": False,
            "raw_targets_redacted": True,
            "customer_traffic_claimed": False,
            "external_reachability_claimed": False,
            "dpi_bypass_claimed": False,
            "settlement_finality_claimed": False,
            "traffic_delivery_claimed": False,
            "production_readiness_claimed": False,
        },
        "artifacts": {
            "output_json": str(output_json),
            "operator_output_json": str(operator_output_json),
            "proof_gate_output_json": str(proof_gate_output_json),
        },
        "operator_evidence": None,
        "blockers": blockers,
        "safe_local_input_steps": [
            "Run only on a host-owned private non-loopback address.",
            "Use --allow-private-target-probe only inside an authorized local environment.",
            "Do not paste private targets, packet captures, tokens, or subscriber data into chat.",
        ],
    }
    if blockers:
        return base

    server, thread, port = server_factory(host)
    base["summary"]["server_started"] = True
    try:
        operator_report = operator_runner(
            root,
            target_host=host,
            target_port=str(port),
            target_label=target_label,
            timeout_s=timeout_s,
            allow_operator_probe=True,
            output_json=operator_output_json,
            proof_gate_output_json=proof_gate_output_json,
        )
        base["summary"]["operator_run_attempted"] = True
        try:
            thread.join(timeout=5.0)
        except AttributeError:
            pass
    finally:
        try:
            server.close()
        except OSError:
            pass

    failures = _validate_operator_report(operator_report, raw_target=host)
    retained = not failures
    operator_summary = _mapping(operator_report.get("summary"))
    base["operator_evidence"] = {
        "decision": operator_report.get("decision"),
        "ok": operator_report.get("ok") is True,
        "operator_run_evidence_retained": (
            operator_summary.get("operator_run_evidence_retained") is True
        ),
        "eventbus_evidence_recognized_by_proof_gate": (
            operator_summary.get("eventbus_evidence_recognized_by_proof_gate") is True
        ),
        "raw_targets_redacted": operator_summary.get("raw_targets_redacted") is True,
    }
    base["summary"]["operator_run_evidence_retained"] = retained
    base["summary"]["eventbus_evidence_recognized_by_proof_gate"] = retained
    base["decision"] = DECISION_RETAINED if retained else DECISION_GAPS
    base["ok"] = retained
    base["blockers"] = failures
    return base


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--target-host", default="")
    parser.add_argument("--target-label", default="private-target-operator-run")
    parser.add_argument("--timeout-s", type=float, default=2.0)
    parser.add_argument("--allow-private-target-probe", action="store_true")
    parser.add_argument("--require-retained", action="store_true")
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument(
        "--operator-output-json",
        type=Path,
        default=DEFAULT_OPERATOR_OUTPUT_JSON,
    )
    parser.add_argument(
        "--proof-gate-output-json",
        type=Path,
        default=DEFAULT_PROOF_GATE_OUTPUT_JSON,
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(
        args.root,
        target_host=args.target_host,
        target_label=args.target_label,
        timeout_s=args.timeout_s,
        allow_private_target_probe=args.allow_private_target_probe,
        output_json=args.output_json,
        operator_output_json=args.operator_output_json,
        proof_gate_output_json=args.proof_gate_output_json,
    )
    output_json = args.output_json
    if not output_json.is_absolute():
        output_json = args.root.resolve() / output_json
    if report.get("summary", {}).get("operator_run_attempted") is True or args.output_json:
        _write_json(output_json, report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"decision={report['decision']}")
        print(f"ok={report['ok']}")
        for blocker in report["blockers"]:
            print(f"- {blocker}")
    return 0 if report["ok"] or not args.require_retained else 1


if __name__ == "__main__":
    raise SystemExit(main())
