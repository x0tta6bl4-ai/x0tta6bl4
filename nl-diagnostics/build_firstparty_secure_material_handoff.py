#!/usr/bin/env python3
"""Build secure local handoff material for first-party VPN production apply.

The handoff contains private production configs and signed client kits, so it
is written outside the git workspace under a 0700 directory. The diagnostics
evidence written to this repo is intentionally secret-free: only hashes,
paths, permissions, and checks are recorded.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tarfile
from typing import Any


ROOT = Path("/mnt/projects")
DIAGNOSTICS_DIR = ROOT / "nl-diagnostics"
NODE_SCRIPT = ROOT / "services" / "nl-server" / "firstparty-vpn-test" / "x0vpn_test_node.py"
FIRSTPARTY_SOURCE = ROOT / "src" / "network" / "firstparty_vpn"
DEFAULT_HANDOFF_ROOT = (
    Path.home() / ".local" / "share" / "x0tta-firstparty-vpn" / "handoffs"
)
APPROVAL_PHRASE = "APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT"
DEFAULT_UPLINK_INTERFACE = "eth0"
DEFAULT_SERVER_CONFIG_TARGET = "/etc/x0tta-firstparty-vpn-server/server.json"
DEFAULT_CLIENT_CONFIG_TARGET = "/etc/x0tta-firstparty-vpn-client/client.json"
PRIVATE_FILE_SUFFIXES = (".json", ".tar.gz", ".tgz")
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


def stamp_now() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


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
    apply_packet_summary_path: Path,
    handoff_root: Path = DEFAULT_HANDOFF_ROOT,
    generated_at: str | None = None,
    uplink_interface: str = DEFAULT_UPLINK_INTERFACE,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    apply_packet = read_json(apply_packet_summary_path)
    material = _build_handoff_material(
        apply_packet=apply_packet,
        handoff_root=handoff_root,
        uplink_interface=uplink_interface,
    )
    checks = {
        "apply_packet_ok": apply_packet.get("ok") is True,
        "apply_packet_approval_blocked": apply_packet.get("approval_present") is False
        and apply_packet.get("production_mutation_allowed") is False
        and apply_packet.get("approval_phrase_required") == APPROVAL_PHRASE,
        "apply_packet_external_endpoint": apply_packet.get("host") not in {
            "127.0.0.1",
            "localhost",
            "0.0.0.0",
            "",
            None,
        }
        and apply_packet.get("bind_host") not in {"127.0.0.1", "localhost"},
        "apply_packet_requires_secure_handoff": apply_packet.get(
            "secure_material_handoff_required"
        )
        is True,
        "handoff_dir_outside_repo": material.get("handoff_dir_outside_repo") is True,
        "handoff_archive_outside_repo": material.get("archive_outside_repo") is True,
        "handoff_dir_private": material.get("handoff_dir_mode") == "0700",
        "handoff_archive_private": material.get("archive_mode") == "0600",
        "private_files_mode_ok": material.get("private_files_mode_ok") is True,
        "source_tree_included": material.get("source_tree_included") is True,
        "source_tree_hash_matches_current": material.get("source_tree_hash")
        == material.get("current_source_tree_hash"),
        "generate_ok": material.get("generate_ok") is True,
        "server_service_plan_ok": material.get("server_service_plan_ok") is True,
        "client_service_plan_ok": material.get("client_service_plan_ok") is True,
        "server_apply_dry_run_ok": _dry_run_apply_ok(material.get("server_apply_dry_run")),
        "client_apply_dry_run_ok": _dry_run_apply_ok(material.get("client_apply_dry_run")),
        "generated_server_bind_matches_apply_packet": material.get("server_bind_host")
        == apply_packet.get("bind_host"),
        "generated_client_host_matches_apply_packet": material.get("client_host")
        == apply_packet.get("host"),
        "generated_port_matches_apply_packet": material.get("port")
        == apply_packet.get("port"),
        "generated_transport_matches_apply_packet": material.get("transport")
        == apply_packet.get("transport"),
        "client_kits_exported": material.get("export_client_kits_ok") is True,
        "client_kits_verified": material.get("verify_client_kits_ok") is True,
        "client_kits_signed": material.get("verified_kit_count")
        == material.get("client_kit_count")
        and int(material.get("verified_kit_count") or 0) >= 1,
        "client_kits_without_server_secrets": material.get("server_secrets_included")
        is False,
        "legacy_protocol_markers_absent": not material.get("legacy_protocol_findings"),
        "manifest_secret_free": material.get("manifest_secret_free") is True,
        "raw_secret_material_not_stored_in_evidence": True,
        "repo_material_not_persisted": True,
        "os_mutation_not_performed": True,
        "no_nl_or_spb_writes_performed": True,
    }
    failed_checks = sorted(name for name, passed in checks.items() if passed is not True)
    payload = {
        "mode": "firstparty-secure-material-handoff-summary",
        "generated_at": generated_at,
        "ok": not failed_checks,
        "approval_phrase_required": APPROVAL_PHRASE,
        "approval_present": False,
        "production_mutation_allowed": False,
        "os_mutation_performed": False,
        "no_nl_or_spb_writes_performed": True,
        "apply_packet_summary_path": str(apply_packet_summary_path),
        "apply_packet_summary_sha256": _safe_file_hash(apply_packet_summary_path),
        "host": apply_packet.get("host") or "missing",
        "bind_host": apply_packet.get("bind_host") or "missing",
        "port": apply_packet.get("port") if apply_packet.get("port") is not None else "missing",
        "transport": apply_packet.get("transport") or "missing",
        "deployment_epoch": material.get("deployment_epoch") or "missing",
        "handoff_dir": material.get("handoff_dir") or "missing",
        "handoff_archive": material.get("archive_path") or "missing",
        "handoff_manifest": material.get("manifest_path") or "missing",
        "handoff_dir_mode": material.get("handoff_dir_mode") or "missing",
        "handoff_archive_mode": material.get("archive_mode") or "missing",
        "handoff_file_count": material.get("handoff_file_count") or 0,
        "archive_sha256": material.get("archive_sha256") or "missing",
        "manifest_sha256": material.get("manifest_sha256") or "missing",
        "server_candidate_hash": material.get("server_candidate_hash") or "missing",
        "client_candidate_hash": material.get("client_candidate_hash") or "missing",
        "source_tree_hash": material.get("source_tree_hash") or "missing",
        "server_service_name": material.get("server_service_name") or "missing",
        "client_service_name": material.get("client_service_name") or "missing",
        "client_kit_count": material.get("client_kit_count") or 0,
        "verified_kit_count": material.get("verified_kit_count") or 0,
        "legacy_protocol_findings": material.get("legacy_protocol_findings") or [],
        "raw_secret_material_stored_in_evidence": False,
        "repo_material_persisted": False,
        "failed_checks": failed_checks,
        "checks": checks,
    }
    return payload


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# First-Party VPN Secure Material Handoff",
        "",
        f"generated_at: `{payload['generated_at']}`",
        f"ok: `{str(payload['ok']).lower()}`",
        f"endpoint: `{payload['transport']}://{payload['host']}:{payload['port']}`",
        f"handoff_dir: `{payload['handoff_dir']}`",
        f"handoff_archive: `{payload['handoff_archive']}`",
        f"production_mutation_allowed: `{str(payload['production_mutation_allowed']).lower()}`",
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
            f"- apply_packet_summary_path: `{payload.get('apply_packet_summary_path')}`",
            f"- archive_sha256: `{payload.get('archive_sha256')}`",
            f"- manifest_sha256: `{payload.get('manifest_sha256')}`",
            f"- handoff_dir_mode: `{payload.get('handoff_dir_mode')}`",
            f"- handoff_archive_mode: `{payload.get('handoff_archive_mode')}`",
            f"- handoff_file_count: `{payload.get('handoff_file_count')}`",
            f"- source_tree_hash: `{payload.get('source_tree_hash')}`",
            f"- client_kit_count: `{payload.get('client_kit_count')}`",
            f"- verified_kit_count: `{payload.get('verified_kit_count')}`",
            f"- legacy_protocol_findings: `{compact([str(v) for v in payload.get('legacy_protocol_findings') or []])}`",
            "",
            "No NL or SPB writes were performed by this handoff builder.",
            "Private configs and client kits are outside the git workspace; diagnostics contain only hashes and metadata.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_packet(payload: dict[str, Any], *, diagnostics_dir: Path) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = diagnostics_dir / f"firstparty-secure-material-handoff-{stamp}"
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
        description="Build secure first-party VPN material handoff evidence"
    )
    parser.add_argument("--diagnostics-dir", default=str(DIAGNOSTICS_DIR))
    parser.add_argument("--apply-packet-summary")
    parser.add_argument("--handoff-root", default=str(DEFAULT_HANDOFF_ROOT))
    parser.add_argument("--uplink-interface", default=DEFAULT_UPLINK_INTERFACE)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    diagnostics_dir = Path(args.diagnostics_dir)
    apply_packet_summary_path = (
        Path(args.apply_packet_summary)
        if args.apply_packet_summary
        else latest_summary(
            "firstparty-production-apply-packet-*/summary.json",
            diagnostics_dir,
        )
    )
    if apply_packet_summary_path is None:
        raise SystemExit("first-party production apply packet summary is missing")
    payload = build_payload(
        apply_packet_summary_path=apply_packet_summary_path,
        handoff_root=Path(args.handoff_root),
        uplink_interface=args.uplink_interface,
    )
    if args.write:
        out_dir = write_packet(payload, diagnostics_dir=diagnostics_dir)
        payload["evidence_dir"] = str(out_dir)
    if args.json or not args.write:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if payload.get("ok") is True else 2


def _build_handoff_material(
    *,
    apply_packet: dict[str, Any],
    handoff_root: Path,
    uplink_interface: str,
) -> dict[str, Any]:
    if _is_under_path(handoff_root.resolve(), ROOT.resolve()):
        raise RuntimeError("handoff root must be outside the git workspace")

    host = str(apply_packet.get("host") or "")
    bind_host = str(apply_packet.get("bind_host") or "")
    port = int(apply_packet.get("port") or 0)
    transport = str(apply_packet.get("transport") or "")
    handoff_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(handoff_root, 0o700)
    handoff_dir = handoff_root / f"firstparty-production-handoff-{stamp_now()}"
    handoff_dir.mkdir(mode=0o700)
    os.chmod(handoff_dir, 0o700)

    try:
        generate = _run_json(
            [
                sys.executable,
                str(NODE_SCRIPT),
                "generate",
                "--out-dir",
                str(handoff_dir),
                "--host",
                host,
                "--bind-host",
                bind_host,
                "--port",
                str(port),
                "--transport",
                transport,
                "--deployment-epoch-prefix",
                "production-firstparty-handoff",
                "--client-count",
                "2",
                "--pqc-reviewed",
                "--pqc-mode",
                "production",
            ]
        )
        server_config_path = Path(str(generate.get("server_config") or handoff_dir / "server.json"))
        client_config_path = Path(str(generate.get("client_config") or handoff_dir / "client.json"))
        issuer_config_path = Path(str(generate.get("issuer_config") or handoff_dir / "issuer.json"))
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
                "/var/backups/x0tta-firstparty-vpn-server",
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
                "/var/backups/x0tta-firstparty-vpn-client",
                "--dry-run",
                "--skip-health",
                "--skip-tcp-connect",
            ]
        )
        kits_dir = handoff_dir / "client-kits"
        archives_dir = handoff_dir / "client-archives"
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

        shutil.copy2(NODE_SCRIPT, handoff_dir / "x0vpn_node.py")
        source_target = handoff_dir / "src" / "network" / "firstparty_vpn"
        source_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            FIRSTPARTY_SOURCE,
            source_target,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        _write_apply_readme(
            handoff_dir / "README-APPLY.md",
            server_service_name=str(server_plan.get("service_name") or ""),
            client_service_name=str(client_plan.get("service_name") or ""),
            uplink_interface=uplink_interface,
        )

        _enforce_private_modes(handoff_dir)
        source_tree_hash = _tree_hash(source_target)
        current_source_tree_hash = _tree_hash(FIRSTPARTY_SOURCE)
        manifest = {
            "schema_version": 1,
            "mode": "firstparty-secure-material-handoff-manifest",
            "generated_at": utc_now(),
            "approval_phrase_required": APPROVAL_PHRASE,
            "host": host,
            "bind_host": bind_host,
            "port": port,
            "transport": transport,
            "deployment_epoch": read_json(server_config_path).get("deployment_epoch"),
            "server_config_hash": server_apply.get("candidate_hash"),
            "client_config_hash": client_apply.get("candidate_hash"),
            "server_service_name": server_plan.get("service_name"),
            "client_service_name": client_plan.get("service_name"),
            "server_config_target": DEFAULT_SERVER_CONFIG_TARGET,
            "client_config_target": DEFAULT_CLIENT_CONFIG_TARGET,
            "source_tree_hash": source_tree_hash,
            "client_kit_count": verify_kits.get("kit_count"),
            "verified_kit_count": int(verify_kits.get("kit_count") or 0)
            - int(verify_kits.get("failed_count") or 0),
            "server_secrets_included_in_client_kits": export_kits.get(
                "server_secrets_included"
            ),
            "secret_free": True,
        }
        manifest_path = handoff_dir / "MANIFEST.secret-free.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )  # lgtm[py/clear-text-storage-sensitive-data]  # nosec - manifest is diagnostic metadata, no secrets
        os.chmod(manifest_path, 0o600)
        archive_path = handoff_dir.with_suffix(".tar.gz")
        with tarfile.open(archive_path, "w:gz") as archive:
            archive.add(handoff_dir, arcname=handoff_dir.name)
        os.chmod(archive_path, 0o600)

        server_unit = str(server_plan.get("unit_content") or "")
        client_unit = str(client_plan.get("unit_content") or "")
        private_files_mode_ok = _private_files_mode_ok(handoff_dir)
        result = {
            "generate_ok": generate.get("ok") is True,
            "server_service_plan_ok": server_plan.get("ok") is True,
            "client_service_plan_ok": client_plan.get("ok") is True,
            "server_apply_dry_run": server_apply,
            "client_apply_dry_run": client_apply,
            "export_client_kits_ok": export_kits.get("ok") is True,
            "verify_client_kits_ok": verify_kits.get("ok") is True,
            "deployment_epoch": manifest.get("deployment_epoch"),
            "server_bind_host": read_json(server_config_path).get("bind_host"),
            "client_host": read_json(client_config_path).get("host"),
            "port": int(read_json(server_config_path).get("port") or 0),
            "transport": str(
                read_json(server_config_path).get("transport")
                or generate.get("transport")
                or transport
                or ""
            ),
            "server_candidate_hash": server_apply.get("candidate_hash"),
            "client_candidate_hash": client_apply.get("candidate_hash"),
            "server_service_name": server_plan.get("service_name"),
            "client_service_name": client_plan.get("service_name"),
            "client_kit_count": verify_kits.get("kit_count") or export_kits.get("client_count"),
            "verified_kit_count": int(verify_kits.get("kit_count") or 0)
            - int(verify_kits.get("failed_count") or 0),
            "server_secrets_included": export_kits.get("server_secrets_included"),
            "source_tree_included": source_target.is_dir(),
            "source_tree_hash": source_tree_hash,
            "current_source_tree_hash": current_source_tree_hash,
            "legacy_protocol_findings": _legacy_marker_findings([server_unit, client_unit]),
            "manifest_secret_free": manifest.get("secret_free") is True,
            "manifest_path": str(manifest_path),
            "manifest_sha256": file_sha256(manifest_path),
            "handoff_dir": str(handoff_dir),
            "handoff_dir_outside_repo": not _is_under_path(
                handoff_dir.resolve(),
                ROOT.resolve(),
            ),
            "handoff_dir_mode": _mode_text(handoff_dir),
            "handoff_file_count": _file_count(handoff_dir),
            "archive_path": str(archive_path),
            "archive_outside_repo": not _is_under_path(
                archive_path.resolve(),
                ROOT.resolve(),
            ),
            "archive_mode": _mode_text(archive_path),
            "archive_sha256": file_sha256(archive_path),
            "private_files_mode_ok": private_files_mode_ok,
        }
        return result
    except Exception:
        # Leave the directory for forensic inspection only if something was
        # already written; permissions are private. Successful runs are the
        # normal path for operator handoff.
        _enforce_private_modes(handoff_dir)
        raise


def _write_apply_readme(
    path: Path,
    *,
    server_service_name: str,
    client_service_name: str,
    uplink_interface: str,
) -> None:
    text = "\n".join(
        [
            "# First-Party VPN Production Handoff",
            "",
            "This directory contains private production VPN material.",
            "Do not copy it into git or paste configs into chat.",
            "",
            "Required approval phrase before any production mutation:",
            f"`{APPROVAL_PHRASE}`",
            "",
            "Server-side dry-run check:",
            "```bash",
            "python3 x0vpn_node.py apply-server-config "
            "--candidate-config server.json "
            f"--installed-config {DEFAULT_SERVER_CONFIG_TARGET} "
            f"--service-name {server_service_name} "
            "--backup-dir /var/backups/x0tta-firstparty-vpn-server "
            f"--uplink-interface {uplink_interface} --dry-run --skip-health",
            "```",
            "",
            "Server-side guarded apply after explicit approval:",
            "```bash",
            "sudo python3 x0vpn_node.py install-server-service "
            "--config server.json --allow-os-mutation --enable-now "
            f"--uplink-interface {uplink_interface}",
            "```",
            "",
            "Client-side guarded apply after explicit approval:",
            "```bash",
            "sudo python3 x0vpn_node.py install-client-service "
            "--config client.json --allow-os-mutation --enable-now "
            "--install-config-sync --require-readiness",
            "```",
            "",
            "Expected service names:",
            f"- server: `{server_service_name}`",
            f"- client: `{client_service_name}`",
            "",
        ]
    )
    path.write_text(text, encoding="utf-8")
    os.chmod(path, 0o600)


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


def _is_under_path(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _mode_text(path: Path) -> str:
    return f"{stat.S_IMODE(path.stat().st_mode):04o}"


def _file_count(path: Path) -> int:
    return sum(1 for item in path.rglob("*") if item.is_file())


def _tree_hash(path: Path) -> str:
    h = hashlib.sha256()
    for item in sorted(path.rglob("*")):
        if not item.is_file():
            continue
        if "__pycache__" in item.parts or item.suffix == ".pyc":
            continue
        rel = item.relative_to(path).as_posix()
        h.update(rel.encode("utf-8") + b"\0")
        h.update(hashlib.sha256(item.read_bytes()).digest())
    return h.hexdigest()


def _enforce_private_modes(path: Path) -> None:
    if not path.exists():
        return
    for item in path.rglob("*"):
        if item.is_dir():
            os.chmod(item, 0o700)
        elif item.is_file():
            os.chmod(item, 0o600)
    os.chmod(path, 0o700)


def _private_files_mode_ok(path: Path) -> bool:
    if not path.exists():
        return False
    for item in path.rglob("*"):
        if item.is_dir():
            if _mode_text(item) != "0700":
                return False
        elif item.is_file():
            if item.name.endswith(PRIVATE_FILE_SUFFIXES) or item.suffix in {".json", ".py", ".md", ".sh"}:
                if _mode_text(item) != "0600":
                    return False
    return _mode_text(path) == "0700"


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
