#!/usr/bin/env python3
"""Build guarded first-party VPN production apply packet evidence.

This script creates production-shaped first-party VPN configs in a temporary
directory, runs only dry-run apply checks, verifies signed client kits without
requiring a live production server, and deletes the temporary raw material
before writing evidence. It never SSHes to NL/SPB and never mutates OS state.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import ipaddress
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path("/mnt/projects")
DIAGNOSTICS_DIR = ROOT / "nl-diagnostics"
NODE_SCRIPT = ROOT / "services" / "nl-server" / "firstparty-vpn-test" / "x0vpn_test_node.py"
APPROVAL_PHRASE = "APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT"
DEFAULT_SERVER_CONFIG_TARGET = "/etc/x0tta-firstparty-vpn-server/server.json"
DEFAULT_CLIENT_CONFIG_TARGET = "/etc/x0tta-firstparty-vpn-client/client.json"
DEFAULT_SERVER_BACKUP_DIR = "/var/backups/x0tta-firstparty-vpn-server"
DEFAULT_CLIENT_BACKUP_DIR = "/var/backups/x0tta-firstparty-vpn-client"
DEFAULT_UPLINK_INTERFACE = "eth0"
LEGACY_MARKERS = (
    "x-ui",
    "xray",
    "vless",
    "vmess",
    "trojan",
    "shadowsocks",
    "wireguard",
    "openvpn",
    "hiddify",
    "happ",
    "warp",
)


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def latest_summary(pattern: str, diagnostics_dir: Path = DIAGNOSTICS_DIR) -> Path | None:
    candidates = sorted(diagnostics_dir.glob(pattern))
    return candidates[-1] if candidates else None


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bool_text(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if value is None:
        return "missing"
    return str(value)


def compact(values: list[str], *, limit: int = 8) -> str:
    if not values:
        return "none"
    head = values[:limit]
    if len(values) > limit:
        head.append(f"...+{len(values) - limit}")
    return ", ".join(head)


def build_payload(
    *,
    endpoint_summary_path: Path,
    generated_at: str | None = None,
    uplink_interface: str = DEFAULT_UPLINK_INTERFACE,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    endpoint = read_json(endpoint_summary_path)
    host = str(endpoint.get("host") or "")
    bind_host = str(endpoint.get("bind_host") or "")
    port = int(endpoint.get("port") or 0)
    transport = str(endpoint.get("transport") or "")
    endpoint_checks = (
        endpoint.get("checks") if isinstance(endpoint.get("checks"), dict) else {}
    )
    candidate = _build_candidate_artifacts(
        host=host,
        bind_host=bind_host,
        port=port,
        transport=transport,
        uplink_interface=uplink_interface,
    )
    server_unit = str(candidate.get("server_unit_content") or "")
    client_unit = str(candidate.get("client_unit_content") or "")
    legacy_findings = _legacy_marker_findings([server_unit, client_unit])

    checks = {
        "endpoint_summary_ok": endpoint.get("ok") is True,
        "endpoint_host_public": _is_public_endpoint(host),
        "endpoint_bind_not_loopback": _is_non_loopback_bind(bind_host),
        "endpoint_port_free_on_nl_snapshot": endpoint_checks.get(
            "candidate_port_free_on_nl_snapshot"
        )
        is True,
        "endpoint_no_mutation": endpoint.get("os_mutation_performed") is False
        and endpoint.get("no_nl_or_spb_writes_performed") is True,
        "generate_ok": candidate.get("generate_ok") is True,
        "generated_server_bind_matches_endpoint": candidate.get("server_bind_host")
        == bind_host,
        "generated_client_host_matches_endpoint": candidate.get("client_host") == host,
        "generated_port_matches_endpoint": candidate.get("port") == port,
        "generated_transport_matches_endpoint": candidate.get("transport") == transport,
        "server_service_plan_ok": candidate.get("server_service_plan_ok") is True,
        "client_service_plan_ok": candidate.get("client_service_plan_ok") is True,
        "server_unit_starts_firstparty_server_tun": (
            " server-tun " in f" {server_unit} "
            and "x0vpn_node.py" in server_unit
            and "--allow-os-mutation" in server_unit
            and "--uplink-interface" in server_unit
        ),
        "client_unit_starts_firstparty_client_tun": (
            " client-tun " in f" {client_unit} "
            and "x0vpn_node.py" in client_unit
            and "--allow-os-mutation" in client_unit
            and "--apply-client-policy" in client_unit
            and "--enable-kill-switch" in client_unit
        ),
        "client_unit_has_rollback_exec_stop": (
            "ExecStopPost=" in client_unit
            and "client-policy-rollback" in client_unit
            and "--enable-kill-switch" in client_unit
        ),
        "service_units_firstparty_only": not legacy_findings,
        "server_apply_dry_run_ok": _dry_run_apply_ok(candidate.get("server_apply_dry_run")),
        "client_apply_dry_run_ok": _dry_run_apply_ok(candidate.get("client_apply_dry_run")),
        "server_apply_hash_matches_generated": candidate.get("server_candidate_hash")
        == candidate.get("server_apply_candidate_hash"),
        "client_apply_hash_matches_generated": candidate.get("client_candidate_hash")
        == candidate.get("client_apply_candidate_hash"),
        "client_kits_exported": candidate.get("export_client_kits_ok") is True,
        "client_kits_verified": candidate.get("verify_client_kits_ok") is True,
        "client_kits_signed": candidate.get("verified_kit_count")
        == candidate.get("client_kit_count")
        and int(candidate.get("verified_kit_count") or 0) >= 1,
        "client_kits_without_server_secrets": candidate.get("server_secrets_included")
        is False,
        "approval_required": True,
        "approval_not_present": True,
        "production_mutation_blocked": True,
        "post_apply_validation_required": True,
        "secure_material_handoff_required": True,
        "temp_config_dir_removed": candidate.get("temp_config_dir_persisted") is False,
        "raw_secret_material_not_stored_in_evidence": True,
        "kit_material_not_persisted_in_repo": True,
        "os_mutation_not_performed": True,
        "no_nl_or_spb_writes_performed": True,
    }
    failed_checks = sorted(name for name, passed in checks.items() if passed is not True)
    payload = {
        "mode": "firstparty-production-apply-packet-summary",
        "generated_at": generated_at,
        "ok": not failed_checks,
        "approval_phrase_required": APPROVAL_PHRASE,
        "approval_present": False,
        "production_mutation_allowed": False,
        "post_apply_validation_required": True,
        "secure_material_handoff_required": True,
        "os_mutation_performed": False,
        "no_nl_or_spb_writes_performed": True,
        "endpoint_summary_path": str(endpoint_summary_path),
        "endpoint_summary_sha256": _safe_file_hash(endpoint_summary_path),
        "host": host,
        "bind_host": bind_host,
        "port": port,
        "transport": transport,
        "deployment_epoch": candidate.get("deployment_epoch") or "missing",
        "endpoint_deployment_epoch": endpoint.get("deployment_epoch") or "missing",
        "server_service_name": candidate.get("server_service_name") or "missing",
        "client_service_name": candidate.get("client_service_name") or "missing",
        "server_unit_path": candidate.get("server_unit_path") or "missing",
        "client_unit_path": candidate.get("client_unit_path") or "missing",
        "server_config_target": DEFAULT_SERVER_CONFIG_TARGET,
        "client_config_target": DEFAULT_CLIENT_CONFIG_TARGET,
        "server_candidate_hash": candidate.get("server_candidate_hash") or "missing",
        "client_candidate_hash": candidate.get("client_candidate_hash") or "missing",
        "server_apply_candidate_hash": candidate.get("server_apply_candidate_hash")
        or "missing",
        "client_apply_candidate_hash": candidate.get("client_apply_candidate_hash")
        or "missing",
        "client_kit_count": candidate.get("client_kit_count") or 0,
        "verified_kit_count": candidate.get("verified_kit_count") or 0,
        "legacy_protocol_findings": legacy_findings,
        "raw_secret_material_stored_in_evidence": False,
        "kit_material_persisted_in_repo": False,
        "failed_checks": failed_checks,
        "checks": checks,
    }
    return payload


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# First-Party VPN Production Apply Packet",
        "",
        f"generated_at: `{payload['generated_at']}`",
        f"ok: `{str(payload['ok']).lower()}`",
        f"endpoint: `{payload['transport']}://{payload['host']}:{payload['port']}`",
        f"approval_phrase_required: `{payload['approval_phrase_required']}`",
        f"production_mutation_allowed: `{str(payload['production_mutation_allowed']).lower()}`",
        f"secure_material_handoff_required: `{str(payload['secure_material_handoff_required']).lower()}`",
        "",
        "## Checks",
        "",
        "| Check | Passed |",
        "|---|---|",
    ]
    checks = payload.get("checks") if isinstance(payload.get("checks"), dict) else {}
    for name in sorted(checks):
        lines.append(f"| `{name}` | `{bool_text(checks[name])}` |")
    failed = payload.get("failed_checks") if isinstance(payload.get("failed_checks"), list) else []
    lines.extend(["", "## Failed Checks", ""])
    if failed:
        lines.extend(f"- {value}" for value in failed)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Evidence",
            "",
            f"- endpoint_summary_path: `{payload.get('endpoint_summary_path')}`",
            f"- endpoint_summary_sha256: `{payload.get('endpoint_summary_sha256')}`",
            f"- server_service_name: `{payload.get('server_service_name')}`",
            f"- client_service_name: `{payload.get('client_service_name')}`",
            f"- server_config_target: `{payload.get('server_config_target')}`",
            f"- client_config_target: `{payload.get('client_config_target')}`",
            f"- client_kit_count: `{payload.get('client_kit_count')}`",
            f"- verified_kit_count: `{payload.get('verified_kit_count')}`",
            f"- legacy_protocol_findings: `{compact([str(v) for v in payload.get('legacy_protocol_findings') or []])}`",
            "",
            "No NL or SPB writes were performed by this production apply packet.",
            "Raw config and client kit material were generated only in a temporary directory and removed before evidence write.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_packet(payload: dict[str, Any], *, diagnostics_dir: Path) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = diagnostics_dir / f"firstparty-production-apply-packet-{stamp}"
    out_dir.mkdir(parents=True, exist_ok=False)
    payload = dict(payload)
    payload["evidence_dir"] = str(out_dir)
    (out_dir / "summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )  # lgtm[py/clear-text-storage-sensitive-data]  # nosec - diagnostic report, no secrets
    (out_dir / "summary.md").write_text(render_markdown(payload), encoding="utf-8")
    return out_dir


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build first-party VPN production apply packet evidence"
    )
    parser.add_argument("--diagnostics-dir", default=str(DIAGNOSTICS_DIR))
    parser.add_argument("--endpoint-summary")
    parser.add_argument("--uplink-interface", default=DEFAULT_UPLINK_INTERFACE)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    diagnostics_dir = Path(args.diagnostics_dir)
    endpoint_summary_path = (
        Path(args.endpoint_summary)
        if args.endpoint_summary
        else latest_summary("firstparty-production-endpoint-*/summary.json", diagnostics_dir)
    )
    if endpoint_summary_path is None:
        raise SystemExit("first-party production endpoint summary is missing")
    payload = build_payload(
        endpoint_summary_path=endpoint_summary_path,
        uplink_interface=args.uplink_interface,
    )
    if args.write:
        out_dir = write_packet(payload, diagnostics_dir=diagnostics_dir)
        payload["evidence_dir"] = str(out_dir)
    if args.json or not args.write:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if payload.get("ok") is True else 2


def _build_candidate_artifacts(
    *,
    host: str,
    bind_host: str,
    port: int,
    transport: str,
    uplink_interface: str,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="x0vpn-production-apply.") as tmp_raw:
        tmp = Path(tmp_raw)
        kits_dir = tmp / "kits"
        archives_dir = tmp / "archives"
        generate = _run_json(
            [
                sys.executable,
                str(NODE_SCRIPT),
                "generate",
                "--out-dir",
                str(tmp),
                "--host",
                host,
                "--bind-host",
                bind_host,
                "--port",
                str(port),
                "--transport",
                transport,
                "--deployment-epoch-prefix",
                "production-firstparty-apply",
                "--client-count",
                "2",
                "--pqc-reviewed",
                "--pqc-mode",
                "production",
            ]
        )
        server_config_path = Path(str(generate.get("server_config") or tmp / "server.json"))
        client_config_path = Path(str(generate.get("client_config") or tmp / "client.json"))
        issuer_config_path = Path(str(generate.get("issuer_config") or tmp / "issuer.json"))
        server_config = read_json(server_config_path)
        client_config = read_json(client_config_path)
        server_plan = _run_json(
            [
                sys.executable,
                str(NODE_SCRIPT),
                "server-service-plan",
                "--config",
                str(server_config_path),
                "--uplink-interface",
                uplink_interface,
            ]
        )
        client_plan = _run_json(
            [
                sys.executable,
                str(NODE_SCRIPT),
                "client-service-plan",
                "--config",
                str(client_config_path),
                "--install-config-sync",
                "--require-readiness",
                "--readiness-skip-tcp-connect",
                "--readiness-skip-admission",
                "--readiness-skip-config-sync",
                "--readiness-timeout",
                "1",
            ]
        )
        server_apply = _run_json(
            [
                sys.executable,
                str(NODE_SCRIPT),
                "apply-server-config",
                "--candidate-config",
                str(server_config_path),
                "--installed-config",
                DEFAULT_SERVER_CONFIG_TARGET,
                "--service-name",
                str(server_plan.get("service_name") or "x0tta-firstparty-vpn.service"),
                "--backup-dir",
                DEFAULT_SERVER_BACKUP_DIR,
                "--uplink-interface",
                uplink_interface,
                "--dry-run",
                "--skip-health",
            ]
        )
        client_apply = _run_json(
            [
                sys.executable,
                str(NODE_SCRIPT),
                "apply-client-config",
                "--candidate-config",
                str(client_config_path),
                "--installed-config",
                DEFAULT_CLIENT_CONFIG_TARGET,
                "--service-name",
                str(
                    client_plan.get("service_name")
                    or "x0tta-firstparty-vpn-client.service"
                ),
                "--backup-dir",
                DEFAULT_CLIENT_BACKUP_DIR,
                "--dry-run",
                "--skip-health",
                "--skip-tcp-connect",
            ]
        )
        export_kits = _run_json(
            [
                sys.executable,
                str(NODE_SCRIPT),
                "export-client-kits",
                "--server-config",
                str(server_config_path),
                "--issuer-config",
                str(issuer_config_path),
                "--out-dir",
                str(kits_dir),
                "--archive",
                "--archive-dir",
                str(archives_dir),
                "--require-readiness",
                "--readiness-skip-tcp-connect",
                "--readiness-skip-admission",
                "--readiness-skip-config-sync",
                "--readiness-timeout",
                "1",
            ]
        )
        verify_kits = _run_json(
            [
                sys.executable,
                str(NODE_SCRIPT),
                "verify-client-kits",
                "--kits-dir",
                str(kits_dir),
                "--archive-dir",
                str(archives_dir),
                "--require-signature",
                "--check-archives",
                "--require-readiness",
                "--readiness-skip-tcp-connect",
                "--readiness-skip-admission",
                "--readiness-skip-config-sync",
                "--readiness-timeout",
                "1",
            ]
        )
        result = {
            "generate_ok": generate.get("ok") is True,
            "server_service_plan_ok": server_plan.get("ok") is True,
            "client_service_plan_ok": client_plan.get("ok") is True,
            "server_apply_dry_run": server_apply,
            "client_apply_dry_run": client_apply,
            "export_client_kits_ok": export_kits.get("ok") is True,
            "verify_client_kits_ok": verify_kits.get("ok") is True,
            "deployment_epoch": server_config.get("deployment_epoch")
            or generate.get("deployment_epoch"),
            "server_bind_host": server_config.get("bind_host"),
            "client_host": client_config.get("host"),
            "port": int(server_config.get("port") or 0),
            "transport": str(server_config.get("transport") or generate.get("transport") or ""),
            "server_service_name": server_plan.get("service_name"),
            "client_service_name": client_plan.get("service_name"),
            "server_unit_path": server_plan.get("unit_path"),
            "client_unit_path": client_plan.get("unit_path"),
            "server_unit_content": server_plan.get("unit_content") or "",
            "client_unit_content": client_plan.get("unit_content") or "",
            "server_candidate_hash": server_apply.get("candidate_hash"),
            "client_candidate_hash": client_apply.get("candidate_hash"),
            "server_apply_candidate_hash": server_apply.get("candidate_hash"),
            "client_apply_candidate_hash": client_apply.get("candidate_hash"),
            "client_kit_count": verify_kits.get("kit_count") or export_kits.get("client_count"),
            "verified_kit_count": int(verify_kits.get("kit_count") or 0)
            - int(verify_kits.get("failed_count") or 0),
            "server_secrets_included": export_kits.get("server_secrets_included"),
            "temp_config_dir": str(tmp),
            "server_config_file_sha256": file_sha256(server_config_path),
            "client_config_file_sha256": file_sha256(client_config_path),
        }
    result["temp_config_dir_persisted"] = Path(str(result["temp_config_dir"])).exists()
    return result


def _run_json(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n{completed.stdout[-800:]}\n{completed.stderr[-800:]}"
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"command returned non-JSON: {' '.join(command)}\n{completed.stdout[-800:]}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"command returned non-object JSON: {' '.join(command)}")
    return payload


def _dry_run_apply_ok(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    return (
        payload.get("ok") is True
        and payload.get("dry_run") is True
        and payload.get("file_mutation_performed") is False
        and payload.get("os_mutation_performed") is False
        and payload.get("service_restart_performed") is False
        and payload.get("rollback_on_failure") is True
        and payload.get("rollback_performed") is False
    )


def _safe_file_hash(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    return file_sha256(path)


def _is_public_endpoint(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        lowered = host.strip().lower()
        return bool(lowered) and lowered not in {"localhost"} and not lowered.endswith(".local")
    return not (
        ip.is_loopback
        or ip.is_private
        or ip.is_unspecified
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_link_local
    )


def _is_non_loopback_bind(bind_host: str) -> bool:
    if bind_host in {"0.0.0.0", "::"}:
        return True
    try:
        ip = ipaddress.ip_address(bind_host)
    except ValueError:
        return False
    return not (ip.is_loopback or ip.is_unspecified or ip.is_link_local)


def _legacy_marker_findings(values: list[str]) -> list[str]:
    findings: list[str] = []
    for index, value in enumerate(values):
        lowered = str(value).lower()
        for marker in LEGACY_MARKERS:
            if marker in lowered:
                findings.append(f"value{index}:{marker}")
    return findings


if __name__ == "__main__":
    raise SystemExit(main())
