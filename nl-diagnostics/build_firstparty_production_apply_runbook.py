#!/usr/bin/env python3
"""Build secret-free first-party VPN production apply runbook evidence.

The runbook is intentionally not an executor. It binds the latest production
authorization packet to exact operator commands, rollback commands, and
post-apply validation commands. It performs only local file/hash/mode checks and
never SSHes to NL/SPB or mutates OS state.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import shlex
from typing import Any


ROOT = Path("/mnt/projects")
DIAGNOSTICS_DIR = ROOT / "nl-diagnostics"
APPROVAL_PHRASE = "APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT"
DEFAULT_REMOTE_ALIAS = "nl"
DEFAULT_REMOTE_ROOT = "/root/x0tta-firstparty-vpn"
DEFAULT_UPLINK_INTERFACE = "eth0"
DEFAULT_SERVER_BACKUP_DIR = "/var/backups/x0tta-firstparty-vpn-server"
DEFAULT_CLIENT_BACKUP_DIR = "/var/backups/x0tta-firstparty-vpn-client"
DEFAULT_LOCAL_POST_APPLY_EVIDENCE_ROOT = (
    DIAGNOSTICS_DIR / "firstparty-production-postapply-evidence"
)
LEGACY_MARKERS = (
    "x-ui",
    "xray",
    "ghost-access",
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
FIRSTPARTY_SERVICE_NAMES = {
    "x0tta-firstparty-vpn.service",
    "x0tta-firstparty-vpn-client.service",
    "x0tta-firstparty-vpn-client-config-sync.timer",
}


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


def safe_file_sha256(path: Path) -> str:
    try:
        return file_sha256(path)
    except OSError:
        return "missing"


def file_mode(path: Path) -> str:
    try:
        return f"{path.stat().st_mode & 0o777:04o}"
    except OSError:
        return "missing"


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


def q(value: object) -> str:
    return shlex.quote(str(value))


def evidence_stamp(value: str) -> str:
    safe = "".join(ch for ch in value if ch.isalnum())
    return safe or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def capture_json_command(base_command: str, output_path: Path) -> str:
    script = (
        f"mkdir -p {q(output_path.parent)} && "
        f"{base_command} | tee {q(output_path)}"
    )
    return f"bash -o pipefail -c {q(script)}"


def approval_prefix() -> str:
    return f'APPROVAL="${{APPROVAL:-}}"; test "$APPROVAL" = {q(APPROVAL_PHRASE)}'


def endpoint_from_authorization(authz: dict[str, Any]) -> dict[str, Any]:
    endpoint = authz.get("endpoint")
    return endpoint if isinstance(endpoint, dict) else {}


def path_from_authz(authz: dict[str, Any], key: str) -> Path | None:
    paths = authz.get("evidence_paths")
    if not isinstance(paths, dict):
        return None
    value = paths.get(key)
    return Path(str(value)) if value else None


def hash_from_authz(authz: dict[str, Any], key: str) -> str:
    hashes = authz.get("evidence_hashes")
    if not isinstance(hashes, dict):
        return ""
    value = hashes.get(key)
    return str(value) if isinstance(value, str) else ""


def deployment_name(apply_packet: dict[str, Any], handoff: dict[str, Any]) -> str:
    raw = str(
        handoff.get("deployment_epoch")
        or apply_packet.get("deployment_epoch")
        or "firstparty-production-handoff"
    )
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in raw)
    return safe.strip(".-") or "firstparty-production-handoff"


def command_rows(
    *,
    authorization_summary_path: Path,
    authz_hash: str,
    apply_packet_summary_path: Path,
    apply_hash: str,
    handoff_summary_path: Path,
    handoff_hash: str,
    handoff_dir: Path,
    handoff_archive: Path,
    handoff_archive_hash: str,
    handoff_manifest: Path,
    handoff_manifest_hash: str,
    remote_alias: str,
    remote_handoff_dir: str,
    host: str,
    port: int,
    server_service_name: str,
    client_service_name: str,
    server_config_target: str,
    client_config_target: str,
    uplink_interface: str,
    post_apply_evidence_paths: dict[str, str],
) -> list[dict[str, Any]]:
    remote_node = f"{remote_handoff_dir}/x0vpn_node.py"
    remote_server_config = f"{remote_handoff_dir}/server.json"
    remote_client_config = f"{remote_handoff_dir}/client.json"
    local_node = f"{remote_handoff_dir}/x0vpn_node.py"
    remote_port_check = f"ss -H -lnt '( sport = :{port} )' || true"
    server_health_base = (
        f"ssh {q(remote_alias)} "
        f"{q(f'sudo python3 {q(remote_node)} server-health --config {q(server_config_target)} --service-name {q(server_service_name)} --uplink-interface {q(uplink_interface)}')}"
    )
    client_health_base = (
        f"sudo python3 {q(local_node)} client-health --config {q(client_config_target)} "
        f"--service-name {q(client_service_name)}"
    )
    client_doctor_base = (
        f"sudo python3 {q(local_node)} client-doctor --config {q(client_config_target)} "
        f"--service-name {q(client_service_name)} --require-installed-health"
    )
    rows = [
        {
            "id": "verify_authorization_summary_hash",
            "phase": "local-precheck",
            "run_on": "operator-workstation",
            "mutation": False,
            "approval_required": False,
            "command": (
                f"test \"$(sha256sum {q(authorization_summary_path)} | awk '{{print $1}}')\" "
                f"= {q(authz_hash)}"
            ),
        },
        {
            "id": "verify_apply_packet_hash",
            "phase": "local-precheck",
            "run_on": "operator-workstation",
            "mutation": False,
            "approval_required": False,
            "command": (
                f"test \"$(sha256sum {q(apply_packet_summary_path)} | awk '{{print $1}}')\" "
                f"= {q(apply_hash)}"
            ),
        },
        {
            "id": "verify_handoff_summary_hash",
            "phase": "local-precheck",
            "run_on": "operator-workstation",
            "mutation": False,
            "approval_required": False,
            "command": (
                f"test \"$(sha256sum {q(handoff_summary_path)} | awk '{{print $1}}')\" "
                f"= {q(handoff_hash)}"
            ),
        },
        {
            "id": "verify_handoff_archive_hash_and_mode",
            "phase": "local-precheck",
            "run_on": "operator-workstation",
            "mutation": False,
            "approval_required": False,
            "command": (
                f"test \"$(stat -c '%a' {q(handoff_archive)})\" = '600' && "
                f"test \"$(sha256sum {q(handoff_archive)} | awk '{{print $1}}')\" "
                f"= {q(handoff_archive_hash)}"
            ),
        },
        {
            "id": "verify_handoff_manifest_hash_and_mode",
            "phase": "local-precheck",
            "run_on": "operator-workstation",
            "mutation": False,
            "approval_required": False,
            "command": (
                f"test \"$(stat -c '%a' {q(handoff_manifest)})\" = '600' && "
                f"test \"$(sha256sum {q(handoff_manifest)} | awk '{{print $1}}')\" "
                f"= {q(handoff_manifest_hash)}"
            ),
        },
        {
            "id": "verify_nl_port_still_free_readonly",
            "phase": "remote-readonly-precheck",
            "run_on": remote_alias,
            "mutation": False,
            "approval_required": False,
            "command": (
                f"ssh {q(remote_alias)} {q(remote_port_check)}"
            ),
        },
        {
            "id": "copy_handoff_to_nl_after_approval",
            "phase": "guarded-copy",
            "run_on": "operator-workstation",
            "mutation": True,
            "approval_required": True,
            "command": (
                f"{approval_prefix()} && "
                f"ssh {q(remote_alias)} {q('mkdir -p ' + shlex.quote(remote_handoff_dir))} && "
                f"rsync -a --chmod=D700,F600 {q(str(handoff_dir) + '/')} "
                f"{q(remote_alias + ':' + remote_handoff_dir + '/')}"
            ),
        },
        {
            "id": "install_server_service_after_approval",
            "phase": "server-apply",
            "run_on": remote_alias,
            "mutation": True,
            "approval_required": True,
            "command": (
                f"{approval_prefix()} && sudo python3 {q(remote_node)} install-server-service "
                f"--config {q(remote_server_config)} --service-name {q(server_service_name)} "
                f"--allow-os-mutation --enable-now --uplink-interface {q(uplink_interface)}"
            ),
        },
        {
            "id": "server_health_post_apply",
            "phase": "post-apply-validation",
            "run_on": "operator-workstation",
            "mutation": False,
            "approval_required": False,
            "captures_json_to": post_apply_evidence_paths["server_health_local_path"],
            "command": capture_json_command(
                server_health_base,
                Path(post_apply_evidence_paths["server_health_local_path"]),
            ),
        },
        {
            "id": "apply_client_config_after_approval",
            "phase": "client-apply",
            "run_on": "client-host",
            "mutation": True,
            "approval_required": True,
            "command": (
                f"{approval_prefix()} && sudo python3 {q(local_node)} install-client-service "
                f"--config {q(remote_client_config)} --service-name {q(client_service_name)} "
                "--allow-os-mutation --enable-now --install-config-sync "
                "--require-readiness --require-post-install-health"
            ),
        },
        {
            "id": "client_health_post_apply",
            "phase": "post-apply-validation",
            "run_on": "client-host",
            "mutation": False,
            "approval_required": False,
            "captures_json_to": post_apply_evidence_paths["client_health_local_path"],
            "command": capture_json_command(
                client_health_base,
                Path(post_apply_evidence_paths["client_health_local_path"]),
            ),
        },
        {
            "id": "client_doctor_post_apply",
            "phase": "post-apply-validation",
            "run_on": "client-host",
            "mutation": False,
            "approval_required": False,
            "captures_json_to": post_apply_evidence_paths["client_doctor_local_path"],
            "command": capture_json_command(
                client_doctor_base,
                Path(post_apply_evidence_paths["client_doctor_local_path"]),
            ),
        },
        {
            "id": "build_completion_audit_after_post_apply",
            "phase": "post-apply-validation",
            "run_on": "operator-workstation",
            "mutation": False,
            "approval_required": False,
            "command": (
                "python3 nl-diagnostics/build_firstparty_production_completion_audit.py "
                "--write --json "
                f"--server-health {q(post_apply_evidence_paths['server_health_local_path'])} "
                f"--client-health {q(post_apply_evidence_paths['client_health_local_path'])} "
                f"--client-doctor {q(post_apply_evidence_paths['client_doctor_local_path'])}"
            ),
        },
        {
            "id": "rollback_client_policy_and_service_after_approval",
            "phase": "rollback",
            "run_on": "client-host",
            "mutation": True,
            "approval_required": True,
            "command": (
                f"{approval_prefix()} && "
                f"sudo python3 {q(local_node)} client-policy-rollback "
                f"--config {q(client_config_target)} --allow-os-mutation --enable-kill-switch && "
                f"sudo python3 {q(local_node)} uninstall-client-service "
                f"--service-name {q(client_service_name)} --allow-os-mutation"
            ),
        },
        {
            "id": "rollback_server_service_after_approval",
            "phase": "rollback",
            "run_on": remote_alias,
            "mutation": True,
            "approval_required": True,
            "command": (
                f"{approval_prefix()} && sudo python3 {q(remote_node)} uninstall-server-service "
                f"--service-name {q(server_service_name)} --allow-os-mutation"
            ),
        },
    ]
    return rows


def command_texts(commands: list[dict[str, Any]]) -> list[str]:
    return [str(row.get("command") or "") for row in commands if isinstance(row, dict)]


def legacy_marker_findings(commands: list[dict[str, Any]]) -> list[str]:
    findings: list[str] = []
    for row in commands:
        command = str(row.get("command") or "").lower()
        row_id = str(row.get("id") or "unknown")
        for marker in LEGACY_MARKERS:
            if marker in command:
                findings.append(f"{row_id}:{marker}")
    return findings


def mutating_commands_have_approval_guard(commands: list[dict[str, Any]]) -> bool:
    mutating = [row for row in commands if row.get("mutation") is True]
    return bool(mutating) and all(
        row.get("approval_required") is True
        and APPROVAL_PHRASE in str(row.get("command") or "")
        and 'test "$APPROVAL"' in str(row.get("command") or "")
        for row in mutating
    )


def mutating_x0vpn_commands_have_os_mutation_flag(commands: list[dict[str, Any]]) -> bool:
    relevant = [
        row
        for row in commands
        if row.get("mutation") is True and "x0vpn_node.py" in str(row.get("command") or "")
    ]
    return bool(relevant) and all(
        "--allow-os-mutation" in str(row.get("command") or "") for row in relevant
    )


def command_ids(commands: list[dict[str, Any]]) -> set[str]:
    return {str(row.get("id") or "") for row in commands if isinstance(row, dict)}


def post_apply_commands_capture_json(
    commands: list[dict[str, Any]],
    post_apply_evidence_paths: dict[str, str],
) -> bool:
    expected = {
        "server_health_post_apply": post_apply_evidence_paths.get(
            "server_health_local_path"
        ),
        "client_health_post_apply": post_apply_evidence_paths.get(
            "client_health_local_path"
        ),
        "client_doctor_post_apply": post_apply_evidence_paths.get(
            "client_doctor_local_path"
        ),
    }
    rows = {str(row.get("id") or ""): row for row in commands if isinstance(row, dict)}
    return all(
        bool(path)
        and isinstance(rows.get(command_id), dict)
        and rows[command_id].get("captures_json_to") == path
        and "tee" in str(rows[command_id].get("command") or "")
        and str(path) in str(rows[command_id].get("command") or "")
        and "bash -o pipefail -c" in str(rows[command_id].get("command") or "")
        for command_id, path in expected.items()
    )


def build_payload(
    *,
    authorization_summary_path: Path,
    apply_packet_summary_path: Path | None = None,
    handoff_summary_path: Path | None = None,
    generated_at: str | None = None,
    remote_alias: str = DEFAULT_REMOTE_ALIAS,
    remote_root: str = DEFAULT_REMOTE_ROOT,
    uplink_interface: str = DEFAULT_UPLINK_INTERFACE,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    authz = read_json(authorization_summary_path)
    apply_packet_summary_path = apply_packet_summary_path or path_from_authz(
        authz,
        "apply_packet_summary_path",
    )
    handoff_summary_path = handoff_summary_path or path_from_authz(
        authz,
        "handoff_summary_path",
    )
    apply_packet = read_json(apply_packet_summary_path) if apply_packet_summary_path else {}
    handoff = read_json(handoff_summary_path) if handoff_summary_path else {}
    endpoint = endpoint_from_authorization(authz)

    handoff_dir = path_from_authz(authz, "handoff_dir") or Path(
        str(handoff.get("handoff_dir") or "")
    )
    handoff_archive = path_from_authz(authz, "handoff_archive") or Path(
        str(handoff.get("handoff_archive") or "")
    )
    handoff_manifest = path_from_authz(authz, "handoff_manifest") or Path(
        str(handoff.get("handoff_manifest") or "")
    )
    manifest = read_json(handoff_manifest)

    host = str(endpoint.get("host") or apply_packet.get("host") or handoff.get("host") or "")
    bind_host = str(
        endpoint.get("bind_host")
        or apply_packet.get("bind_host")
        or handoff.get("bind_host")
        or ""
    )
    port = int(endpoint.get("port") or apply_packet.get("port") or handoff.get("port") or 0)
    transport = str(
        endpoint.get("transport")
        or apply_packet.get("transport")
        or handoff.get("transport")
        or ""
    )
    deployment = deployment_name(apply_packet, handoff)
    remote_handoff_dir = f"{remote_root.rstrip('/')}/{deployment}"
    server_service_name = str(
        apply_packet.get("server_service_name")
        or handoff.get("server_service_name")
        or manifest.get("server_service_name")
        or "x0tta-firstparty-vpn.service"
    )
    client_service_name = str(
        apply_packet.get("client_service_name")
        or handoff.get("client_service_name")
        or manifest.get("client_service_name")
        or "x0tta-firstparty-vpn-client.service"
    )
    server_config_target = str(
        apply_packet.get("server_config_target")
        or manifest.get("server_config_target")
        or "/etc/x0tta-firstparty-vpn-server/server.json"
    )
    client_config_target = str(
        apply_packet.get("client_config_target")
        or manifest.get("client_config_target")
        or "/etc/x0tta-firstparty-vpn-client/client.json"
    )
    local_post_apply_evidence_dir = (
        DEFAULT_LOCAL_POST_APPLY_EVIDENCE_ROOT / evidence_stamp(generated_at)
    )
    post_apply_evidence_paths = {
        "evidence_dir": str(local_post_apply_evidence_dir),
        "server_health_local_path": str(local_post_apply_evidence_dir / "server-health.json"),
        "client_health_local_path": str(local_post_apply_evidence_dir / "client-health.json"),
        "client_doctor_local_path": str(local_post_apply_evidence_dir / "client-doctor.json"),
    }

    authz_hash = safe_file_sha256(authorization_summary_path)
    apply_hash = (
        safe_file_sha256(apply_packet_summary_path)
        if apply_packet_summary_path
        else "missing"
    )
    handoff_hash = (
        safe_file_sha256(handoff_summary_path)
        if handoff_summary_path
        else "missing"
    )
    handoff_archive_hash = safe_file_sha256(handoff_archive)
    handoff_manifest_hash = safe_file_sha256(handoff_manifest)
    commands = command_rows(
        authorization_summary_path=authorization_summary_path,
        authz_hash=authz_hash,
        apply_packet_summary_path=apply_packet_summary_path or Path("missing"),
        apply_hash=apply_hash,
        handoff_summary_path=handoff_summary_path or Path("missing"),
        handoff_hash=handoff_hash,
        handoff_dir=handoff_dir,
        handoff_archive=handoff_archive,
        handoff_archive_hash=handoff_archive_hash,
        handoff_manifest=handoff_manifest,
        handoff_manifest_hash=handoff_manifest_hash,
        remote_alias=remote_alias,
        remote_handoff_dir=remote_handoff_dir,
        host=host,
        port=port,
        server_service_name=server_service_name,
        client_service_name=client_service_name,
        server_config_target=server_config_target,
        client_config_target=client_config_target,
        uplink_interface=uplink_interface,
        post_apply_evidence_paths=post_apply_evidence_paths,
    )
    ids = command_ids(commands)
    legacy_findings = legacy_marker_findings(commands)
    authz_checks = authz.get("checks") if isinstance(authz.get("checks"), dict) else {}
    service_names = {server_service_name, client_service_name}
    checks = {
        "authorization_ok": authz.get("ok") is True,
        "authorization_approval_guarded": (
            authz.get("approval_phrase_required") == APPROVAL_PHRASE
            and authz.get("approval_present") is False
            and authz.get("production_mutation_allowed") is False
            and authz.get("manual_approval_still_required") is True
        ),
        "authorization_no_mutation": (
            authz.get("os_mutation_performed") is False
            and authz.get("no_nl_or_spb_writes_performed") is True
        ),
        "authorization_evidence_fresh": authz_checks.get("all_evidence_fresh") is True,
        "apply_packet_ok": apply_packet.get("ok") is True,
        "apply_packet_hash_bound_to_authorization": apply_hash
        == hash_from_authz(authz, "apply_packet_summary_sha256"),
        "handoff_summary_ok": handoff.get("ok") is True,
        "handoff_summary_hash_bound_to_authorization": handoff_hash
        == hash_from_authz(authz, "handoff_summary_sha256"),
        "handoff_archive_exists": handoff_archive.is_file(),
        "handoff_archive_private": file_mode(handoff_archive) == "0600",
        "handoff_archive_hash_bound_to_authorization": handoff_archive_hash
        == hash_from_authz(authz, "handoff_archive_sha256"),
        "handoff_manifest_exists": handoff_manifest.is_file(),
        "handoff_manifest_private": file_mode(handoff_manifest) == "0600",
        "handoff_manifest_hash_bound_to_authorization": handoff_manifest_hash
        == hash_from_authz(authz, "handoff_manifest_sha256"),
        "handoff_manifest_secret_free": manifest.get("secret_free") is True,
        "endpoint_external_shape": bool(host)
        and host not in {"127.0.0.1", "localhost", "0.0.0.0"}
        and bind_host not in {"127.0.0.1", "localhost"}
        and port > 0
        and bool(transport),
        "service_names_firstparty_only": service_names.issubset(FIRSTPARTY_SERVICE_NAMES),
        "precheck_commands_present": {
            "verify_authorization_summary_hash",
            "verify_apply_packet_hash",
            "verify_handoff_summary_hash",
            "verify_handoff_archive_hash_and_mode",
            "verify_handoff_manifest_hash_and_mode",
            "verify_nl_port_still_free_readonly",
        }.issubset(ids),
        "guarded_copy_command_present": "copy_handoff_to_nl_after_approval" in ids,
        "guarded_apply_commands_present": {
            "install_server_service_after_approval",
            "apply_client_config_after_approval",
        }.issubset(ids),
        "post_apply_validation_commands_present": {
            "server_health_post_apply",
            "client_health_post_apply",
            "client_doctor_post_apply",
        }.issubset(ids),
        "post_apply_evidence_paths_present": all(
            bool(post_apply_evidence_paths.get(name))
            for name in (
                "evidence_dir",
                "server_health_local_path",
                "client_health_local_path",
                "client_doctor_local_path",
            )
        ),
        "post_apply_validation_commands_capture_json": post_apply_commands_capture_json(
            commands,
            post_apply_evidence_paths,
        ),
        "completion_audit_command_present": (
            "build_completion_audit_after_post_apply" in ids
            and "build_firstparty_production_completion_audit.py" in "\n".join(command_texts(commands))
        ),
        "rollback_commands_present": {
            "rollback_client_policy_and_service_after_approval",
            "rollback_server_service_after_approval",
        }.issubset(ids),
        "mutating_commands_have_approval_guard": mutating_commands_have_approval_guard(
            commands
        ),
        "mutating_x0vpn_commands_have_allow_os_mutation": (
            mutating_x0vpn_commands_have_os_mutation_flag(commands)
        ),
        "no_legacy_service_targets_in_commands": not legacy_findings,
        "server_rollback_scope_firstparty_only": (
            "rollback_server_service_after_approval" in ids
            and server_service_name == "x0tta-firstparty-vpn.service"
        ),
        "client_rollback_scope_firstparty_only": (
            "rollback_client_policy_and_service_after_approval" in ids
            and client_service_name == "x0tta-firstparty-vpn-client.service"
        ),
        "runbook_does_not_execute_commands": True,
        "approval_not_present": True,
        "production_mutation_blocked": True,
        "os_mutation_not_performed": True,
        "no_nl_or_spb_writes_performed": True,
    }
    failed_checks = sorted(name for name, passed in checks.items() if passed is not True)
    return {
        "mode": "firstparty-production-apply-runbook-summary",
        "generated_at": generated_at,
        "ok": not failed_checks,
        "approval_phrase_required": APPROVAL_PHRASE,
        "approval_present": False,
        "production_mutation_allowed": False,
        "manual_approval_still_required": True,
        "os_mutation_performed": False,
        "no_nl_or_spb_writes_performed": True,
        "remote_alias": remote_alias,
        "remote_handoff_dir": remote_handoff_dir,
        "endpoint": {
            "host": host or "missing",
            "bind_host": bind_host or "missing",
            "port": port if port else "missing",
            "transport": transport or "missing",
        },
        "service_names": {
            "server": server_service_name,
            "client": client_service_name,
        },
        "config_targets": {
            "server": server_config_target,
            "client": client_config_target,
        },
        "post_apply_evidence_paths": post_apply_evidence_paths,
        "forbidden_legacy_targets": list(LEGACY_MARKERS),
        "evidence_paths": {
            "authorization_summary_path": str(authorization_summary_path),
            "apply_packet_summary_path": str(apply_packet_summary_path or "missing"),
            "handoff_summary_path": str(handoff_summary_path or "missing"),
            "handoff_dir": str(handoff_dir),
            "handoff_archive": str(handoff_archive),
            "handoff_manifest": str(handoff_manifest),
        },
        "evidence_hashes": {
            "authorization_summary_sha256": authz_hash,
            "apply_packet_summary_sha256": apply_hash,
            "handoff_summary_sha256": handoff_hash,
            "handoff_archive_sha256": handoff_archive_hash,
            "handoff_manifest_sha256": handoff_manifest_hash,
        },
        "handoff_archive_mode": file_mode(handoff_archive),
        "handoff_manifest_mode": file_mode(handoff_manifest),
        "commands": commands,
        "legacy_command_findings": legacy_findings,
        "failed_checks": failed_checks,
        "checks": checks,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    endpoint = payload.get("endpoint") if isinstance(payload.get("endpoint"), dict) else {}
    lines = [
        "# First-Party VPN Production Apply Runbook",
        "",
        f"generated_at: `{payload['generated_at']}`",
        f"ok: `{str(payload['ok']).lower()}`",
        f"endpoint: `{endpoint.get('transport')}://{endpoint.get('host')}:{endpoint.get('port')}`",
        f"approval_phrase_required: `{payload['approval_phrase_required']}`",
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
    lines.extend(["", "## Operator Commands", ""])
    commands = payload.get("commands") if isinstance(payload.get("commands"), list) else []
    for row in commands:
        if not isinstance(row, dict):
            continue
        lines.extend(
            [
                f"### {row.get('id')}",
                "",
                f"- phase: `{row.get('phase')}`",
                f"- run_on: `{row.get('run_on')}`",
                f"- mutation: `{bool_text(row.get('mutation'))}`",
                f"- approval_required: `{bool_text(row.get('approval_required'))}`",
                "",
                "```bash",
                str(row.get("command") or ""),
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "## Evidence",
            "",
        ]
    )
    paths = payload.get("evidence_paths") if isinstance(payload.get("evidence_paths"), dict) else {}
    for name in sorted(paths):
        lines.append(f"- {name}: `{paths[name]}`")
    post_apply_paths = (
        payload.get("post_apply_evidence_paths")
        if isinstance(payload.get("post_apply_evidence_paths"), dict)
        else {}
    )
    lines.extend(["", "## Post-Apply Evidence Files", ""])
    if post_apply_paths:
        for name in sorted(post_apply_paths):
            lines.append(f"- {name}: `{post_apply_paths[name]}`")
    else:
        lines.append("- missing")
    lines.extend(
        [
            "",
            "This runbook was generated locally and did not execute any command.",
            "Do not run mutating commands unless the explicit approval phrase is present in the current conversation.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_packet(payload: dict[str, Any], *, diagnostics_dir: Path) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = diagnostics_dir / f"firstparty-production-apply-runbook-{stamp}"
    out_dir.mkdir(parents=True, exist_ok=False)
    payload = dict(payload)
    payload["evidence_dir"] = str(out_dir)
    (out_dir / "summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (out_dir / "summary.md").write_text(render_markdown(payload), encoding="utf-8")
    return out_dir


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build first-party VPN production apply runbook evidence"
    )
    parser.add_argument("--diagnostics-dir", default=str(DIAGNOSTICS_DIR))
    parser.add_argument("--authorization-summary")
    parser.add_argument("--apply-packet-summary")
    parser.add_argument("--handoff-summary")
    parser.add_argument("--remote-alias", default=DEFAULT_REMOTE_ALIAS)
    parser.add_argument("--remote-root", default=DEFAULT_REMOTE_ROOT)
    parser.add_argument("--uplink-interface", default=DEFAULT_UPLINK_INTERFACE)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    diagnostics_dir = Path(args.diagnostics_dir)
    authorization_summary = (
        Path(args.authorization_summary)
        if args.authorization_summary
        else latest_summary("firstparty-production-authorization-*/summary.json", diagnostics_dir)
    )
    if authorization_summary is None:
        raise SystemExit("first-party production authorization summary is missing")
    payload = build_payload(
        authorization_summary_path=authorization_summary,
        apply_packet_summary_path=Path(args.apply_packet_summary)
        if args.apply_packet_summary
        else None,
        handoff_summary_path=Path(args.handoff_summary)
        if args.handoff_summary
        else None,
        remote_alias=args.remote_alias,
        remote_root=args.remote_root,
        uplink_interface=args.uplink_interface,
    )
    if args.write:
        out_dir = write_packet(payload, diagnostics_dir=diagnostics_dir)
        payload = read_json(out_dir / "summary.json")
    if args.json or not args.write:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if payload.get("ok") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
