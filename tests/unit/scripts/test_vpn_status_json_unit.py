"""Unit tests for scripts/vpn_status.sh JSON output."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
import socket
import subprocess
import threading


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "vpn_status.sh"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


class SocksProbeServer:
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen()
        self.port = int(self._sock.getsockname()[1])
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        self._sock.settimeout(0.2)
        while not self._stop.is_set():
            try:
                conn, _addr = self._sock.accept()
            except TimeoutError:
                continue
            except OSError:
                break
            with conn:
                try:
                    conn.recv(3)
                    conn.sendall(b"\x05\x00")
                except OSError:
                    pass

    def close(self) -> None:
        self._stop.set()
        self._sock.close()
        self._thread.join(timeout=1)


def _make_fake_path(tmp_path: Path) -> Path:
    bindir = tmp_path / "bin"
    bindir.mkdir()

    _write_executable(
        bindir / "pgrep",
        "#!/bin/sh\n[ \"${VPN_STATUS_TEST_XRAY_RUNNING:-1}\" = \"1\" ] && printf '1234\\n'\n",
    )
    _write_executable(
        bindir / "ps",
        "#!/bin/sh\nprintf '10240\\n'\n",
    )
    _write_executable(
        bindir / "systemctl",
        """#!/bin/sh
if [ "$1" = "is-active" ] && [ "$2" = "--quiet" ] && [ "$3" = "x0tta-node.service" ]; then
  [ "${VPN_STATUS_TEST_NODE_ACTIVE:-1}" = "1" ]
  exit $?
fi
if [ "$1" = "is-active" ] && [ "$2" = "--quiet" ] && [ "$3" = "x0tta-vpn-watchdog.service" ]; then
  [ "${VPN_STATUS_TEST_WATCHDOG_ACTIVE:-1}" = "1" ]
  exit $?
fi
exit 0
""",
    )
    _write_executable(
        bindir / "journalctl",
        "#!/bin/sh\nprintf 'Network OK | latency=25.0ms | proxy=OK | FIN-WAIT-2=0\\n'\n",
    )
    _write_executable(
        bindir / "ip",
        """#!/bin/sh
case "$*" in
  "link show singbox_tun") exit 0 ;;
  "addr show singbox_tun") printf '    inet 172.18.0.1/30 scope global singbox_tun\\n' ;;
  route\\ get*)
    if [ "${VPN_STATUS_TEST_ROUTE_LOOP:-0}" = "1" ]; then
      printf '89.125.1.107 via 172.18.0.2 dev singbox_tun table 2022\\n'
    else
      printf '89.125.1.107 via 192.168.0.1 dev enp8s0 src 192.168.0.104\\n'
    fi
    ;;
esac
""",
    )
    _write_executable(
        bindir / "ss",
        """#!/bin/sh
if [ "$1" = "-tn" ]; then
  printf 'ESTAB 0 0 192.168.0.104:50000 89.125.1.107:443\\n'
fi
""",
    )
    _write_executable(
        bindir / "curl",
        """#!/bin/sh
case "$*" in
  *9091*) printf 'vpn_heal_total 0\\nvpn_checks_total 12\\n' ;;
  *) printf '89.125.1.107' ;;
esac
""",
    )
    _write_executable(
        bindir / "ping",
        """#!/bin/sh
printf '5 packets transmitted, 5 received, 0%% packet loss, time 4004ms\\n'
printf 'rtt min/avg/max/mdev = 67.144/67.500/68.000/0.100 ms\\n'
""",
    )
    _write_executable(
        bindir / "cat",
        """#!/bin/sh
if [ "$1" = "/proc/sys/kernel/random/boot_id" ]; then
  printf 'test-boot-id\\n'
else
  /bin/cat "$@"
fi
""",
    )
    return bindir


def _ready_remote_request_packet(generated_at: str = "2026-06-02T04:00:00Z") -> dict:
    def reply_record_command(request_id: str, reply: str) -> str:
        return (
            f"printf '%s\\n' \"{reply}\" | "
            "python3 services/nl-server/ghost-access/record_remote_client_evidence_reply.py "
            "--write --record-matrix --refresh-artifacts "
            "--expect-request-packet-sha256 \"$(sha256sum "
            "nl-diagnostics/nl-anti-block-remote-client-evidence-request-2026-06-02.json "
            "| awk '{print $1}')\" "
            f"--request-id {request_id} --reply-stdin --json"
        )

    def reply_validate_command(request_id: str, reply: str) -> str:
        return (
            f"printf '%s\\n' \"{reply}\" | "
            "python3 services/nl-server/ghost-access/record_remote_client_evidence_reply.py "
            "--expect-request-packet-sha256 \"$(sha256sum "
            "nl-diagnostics/nl-anti-block-remote-client-evidence-request-2026-06-02.json "
            "| awk '{print $1}')\" "
            f"--request-id {request_id} --reply-stdin --json"
        )

    return {
        "packet_id": "nl-anti-block-remote-client-evidence-request-2026-06-02",
        "generated_at": generated_at,
        "decision": "REMOTE_CLIENT_EVIDENCE_REQUEST_READY",
        "missing_requirements": [
            "android_happ_or_hiddify",
            "mobile_network",
            "restricted_or_work_wifi",
        ],
        "minimum_reports_required": 2,
        "request_count": 2,
        "requests": [
            {
                "request_id": "remote-client-evidence-1",
                "client": "Happ",
                "network_type": "mobile",
                "transport": "reality",
                "port": 443,
                "covers_requirements": ["android_happ_or_hiddify", "mobile_network"],
                "tester_message": (
                    "Test remote-client-evidence-1: use Happ or Hiddify on mobile data, "
                    "not Wi-Fi. Select the active Ghost Access Reality profile on port 443. "
                    "Reply only with: pass connected, fail timeout, fail import, or "
                    "fail no-internet. Do not send profile links, subscription links, "
                    "QR codes, UUIDs, IP addresses, usernames, phone numbers, handles, "
                    "screenshots, or logs."
                ),
                "operator_reply_record_pass_command": reply_record_command(
                    "remote-client-evidence-1",
                    "pass connected",
                ),
                "operator_reply_validate_pass_command": reply_validate_command(
                    "remote-client-evidence-1",
                    "pass connected",
                ),
                "operator_reply_record_fail_command": reply_record_command(
                    "remote-client-evidence-1",
                    "fail timeout",
                ),
                "operator_reply_validate_fail_command": reply_validate_command(
                    "remote-client-evidence-1",
                    "fail timeout",
                ),
                "safe_reply_options": [
                    "pass connected",
                    "fail timeout",
                    "fail import",
                    "fail no-internet",
                ],
            },
            {
                "request_id": "remote-client-evidence-2",
                "client": "any",
                "network_type": "work-wifi",
                "transport": "reality",
                "port": 443,
                "covers_requirements": ["restricted_or_work_wifi"],
                "tester_message": (
                    "Test remote-client-evidence-2: use Happ or Hiddify on restricted "
                    "or work Wi-Fi. Select the active Ghost Access Reality profile on port 443. "
                    "Reply only with: pass connected, fail timeout, fail import, or "
                    "fail no-internet. Do not send profile links, subscription links, "
                    "QR codes, UUIDs, IP addresses, usernames, phone numbers, handles, "
                    "screenshots, or logs."
                ),
                "operator_reply_record_pass_command": reply_record_command(
                    "remote-client-evidence-2",
                    "pass connected",
                ),
                "operator_reply_validate_pass_command": reply_validate_command(
                    "remote-client-evidence-2",
                    "pass connected",
                ),
                "operator_reply_record_fail_command": reply_record_command(
                    "remote-client-evidence-2",
                    "fail timeout",
                ),
                "operator_reply_validate_fail_command": reply_validate_command(
                    "remote-client-evidence-2",
                    "fail timeout",
                ),
                "safe_reply_options": [
                    "pass connected",
                    "fail timeout",
                    "fail import",
                    "fail no-internet",
                ],
            },
        ],
        "privacy": {
            "output_privacy_ok": True,
            "raw_subscription_url_stored": False,
            "raw_vpn_uri_stored": False,
            "raw_uuid_stored": False,
        },
    }


def _run_json(
    tmp_path: Path,
    route_loop: bool = False,
    *,
    node_active: bool = True,
    watchdog_active: bool = True,
    client_evidence_status: dict | None = None,
    client_evidence_max_age_seconds: int | None = None,
    remote_request_packet: dict | None = None,
    remote_request_max_age_seconds: int | None = None,
    remote_request_min_collection_window_seconds: int | None = None,
    subscription_payload_status: dict | None = None,
    subscription_payload_max_age_seconds: int | None = None,
    transport_usage_status: dict | None = None,
    transport_usage_max_age_seconds: int | None = None,
    legacy_migration_status: dict | None = None,
    legacy_migration_max_age_seconds: int | None = None,
    legacy_migration_replies_status: dict | None = None,
    legacy_migration_replies_max_age_seconds: int | None = None,
    legacy_migration_progress_status: dict | None = None,
    legacy_migration_progress_max_age_seconds: int | None = None,
    legacy_no_progress_nudge_status: dict | None = None,
    legacy_no_progress_nudge_dry_run_status: dict | None = None,
    legacy_no_progress_nudge_max_age_seconds: int | None = None,
    legacy_no_progress_nudge_dry_run_max_age_seconds: int | None = None,
    legacy_no_progress_nudge_cooldown_hours: float | None = None,
    xray_running: bool = True,
) -> subprocess.CompletedProcess[str]:
    socks = SocksProbeServer()
    try:
        bindir = _make_fake_path(tmp_path)
        boot_result = tmp_path / "boot.last"
        boot_result.write_text(
            "status=PASS\nboot_id=test-boot-id\ntimestamp=2026-05-27T00:00:00Z\ndetail=test\n",
            encoding="utf-8",
        )
        client_evidence_file = tmp_path / "client-evidence-status.json"
        if client_evidence_status is not None:
            client_evidence_file.write_text(
                json.dumps(client_evidence_status),
                encoding="utf-8",
            )
        remote_request_file = tmp_path / "remote-client-evidence-request.json"
        if remote_request_packet is not None:
            remote_request_file.write_text(
                json.dumps(remote_request_packet),
                encoding="utf-8",
            )
        subscription_payload_file = tmp_path / "subscription-payload-status.json"
        if subscription_payload_status is not None:
            subscription_payload_file.write_text(
                json.dumps(subscription_payload_status),
                encoding="utf-8",
            )
        transport_usage_file = tmp_path / "transport-usage-status.json"
        if transport_usage_status is not None:
            transport_usage_file.write_text(
                json.dumps(transport_usage_status),
                encoding="utf-8",
            )
        legacy_migration_file = tmp_path / "legacy-migration-packet.json"
        if legacy_migration_status is not None:
            legacy_migration_file.write_text(
                json.dumps(legacy_migration_status),
                encoding="utf-8",
            )
        legacy_migration_replies_file = tmp_path / "legacy-migration-replies.json"
        if legacy_migration_replies_status is not None:
            legacy_migration_replies_file.write_text(
                json.dumps(legacy_migration_replies_status),
                encoding="utf-8",
            )
        legacy_migration_progress_file = tmp_path / "legacy-migration-progress.json"
        if legacy_migration_progress_status is not None:
            legacy_migration_progress_file.write_text(
                json.dumps(legacy_migration_progress_status),
                encoding="utf-8",
            )
        legacy_no_progress_nudge_file = tmp_path / "legacy-no-progress-nudge.json"
        if legacy_no_progress_nudge_status is not None:
            legacy_no_progress_nudge_file.write_text(
                json.dumps(legacy_no_progress_nudge_status),
                encoding="utf-8",
            )
        legacy_no_progress_nudge_dry_run_file = tmp_path / "legacy-no-progress-nudge-dry-run.json"
        if legacy_no_progress_nudge_dry_run_status is not None:
            legacy_no_progress_nudge_dry_run_file.write_text(
                json.dumps(legacy_no_progress_nudge_dry_run_status),
                encoding="utf-8",
            )
        env = {
            **os.environ,
            "PATH": f"{bindir}:{os.environ['PATH']}",
            "VPN_SOCKS_PORT": str(socks.port),
            "VPN_BOOT_VALIDATE_RESULT_FILE": str(boot_result),
            "VPN_CLIENT_EVIDENCE_STATUS_FILE": str(client_evidence_file),
            "VPN_REMOTE_CLIENT_EVIDENCE_REQUEST_FILE": str(remote_request_file),
            "VPN_SUBSCRIPTION_PAYLOAD_STATUS_FILE": str(subscription_payload_file),
            "VPN_TRANSPORT_USAGE_STATUS_FILE": str(transport_usage_file),
            "VPN_LEGACY_MIGRATION_PACKET_FILE": str(legacy_migration_file),
            "VPN_LEGACY_MIGRATION_REPLIES_FILE": str(legacy_migration_replies_file),
            "VPN_LEGACY_MIGRATION_PROGRESS_FILE": str(legacy_migration_progress_file),
            "VPN_LEGACY_NO_PROGRESS_NUDGE_FILE": str(legacy_no_progress_nudge_file),
            "VPN_LEGACY_NO_PROGRESS_NUDGE_DRY_RUN_FILE": str(
                legacy_no_progress_nudge_dry_run_file
            ),
            "VPN_STATUS_TEST_ROUTE_LOOP": "1" if route_loop else "0",
            "VPN_STATUS_TEST_NODE_ACTIVE": "1" if node_active else "0",
            "VPN_STATUS_TEST_WATCHDOG_ACTIVE": "1" if watchdog_active else "0",
            "VPN_STATUS_TEST_XRAY_RUNNING": "1" if xray_running else "0",
        }
        if client_evidence_max_age_seconds is not None:
            env["VPN_CLIENT_EVIDENCE_MAX_AGE_SECONDS"] = str(client_evidence_max_age_seconds)
        if remote_request_max_age_seconds is not None:
            env["VPN_REMOTE_CLIENT_EVIDENCE_REQUEST_MAX_AGE_SECONDS"] = str(
                remote_request_max_age_seconds
            )
        if remote_request_min_collection_window_seconds is not None:
            env["VPN_REMOTE_CLIENT_EVIDENCE_MIN_COLLECTION_WINDOW_SECONDS"] = str(
                remote_request_min_collection_window_seconds
            )
        if subscription_payload_max_age_seconds is not None:
            env["VPN_SUBSCRIPTION_PAYLOAD_MAX_AGE_SECONDS"] = str(
                subscription_payload_max_age_seconds
            )
        if transport_usage_max_age_seconds is not None:
            env["VPN_TRANSPORT_USAGE_MAX_AGE_SECONDS"] = str(
                transport_usage_max_age_seconds
            )
        if legacy_migration_max_age_seconds is not None:
            env["VPN_LEGACY_MIGRATION_MAX_AGE_SECONDS"] = str(
                legacy_migration_max_age_seconds
            )
        if legacy_migration_replies_max_age_seconds is not None:
            env["VPN_LEGACY_MIGRATION_REPLIES_MAX_AGE_SECONDS"] = str(
                legacy_migration_replies_max_age_seconds
            )
        if legacy_migration_progress_max_age_seconds is not None:
            env["VPN_LEGACY_MIGRATION_PROGRESS_MAX_AGE_SECONDS"] = str(
                legacy_migration_progress_max_age_seconds
            )
        if legacy_no_progress_nudge_max_age_seconds is not None:
            env["VPN_LEGACY_NO_PROGRESS_NUDGE_MAX_AGE_SECONDS"] = str(
                legacy_no_progress_nudge_max_age_seconds
            )
        if legacy_no_progress_nudge_dry_run_max_age_seconds is not None:
            env["VPN_LEGACY_NO_PROGRESS_NUDGE_DRY_RUN_MAX_AGE_SECONDS"] = str(
                legacy_no_progress_nudge_dry_run_max_age_seconds
            )
        if legacy_no_progress_nudge_cooldown_hours is not None:
            env["VPN_LEGACY_NO_PROGRESS_NUDGE_COOLDOWN_HOURS"] = str(
                legacy_no_progress_nudge_cooldown_hours
            )
        return subprocess.run(
            ["bash", str(SCRIPT), "--json"],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=20,
        )
    finally:
        socks.close()


def test_vpn_status_json_success(tmp_path: Path) -> None:
    proc = _run_json(tmp_path)
    assert proc.returncode == 0, proc.stderr

    payload = json.loads(proc.stdout)
    assert payload["overall_status"] == "ok"
    assert payload["failure_domain"] == "none"
    assert payload["recommended_action"] == "observe"
    assert payload["automatic_restart_allowed"] is False
    assert payload["restart_recommended"] is False
    assert payload["restart_scope"] == "none"
    assert payload["restart_guard"]["guard_status"] == "restart_blocked"
    assert payload["restart_guard"]["operator_rule"] == "do_not_restart"
    assert payload["restart_guard"]["automatic_restart_allowed"] is False
    assert payload["restart_guard"]["allowed_manual_restart_scopes"] == []
    assert payload["restart_guard"]["blocked_restart_scopes"] == [
        "xray",
        "full_server",
        "nl",
        "spb",
        "x-ui",
    ]
    assert payload["restart_guard"]["blocked_reasons"] == ["transport_healthy"]
    assert payload["restart_guard"]["transport_healthy"] is True
    assert payload["restart_guard"]["external_client_evidence_pending"] is False
    assert payload["restart_guard"]["requires_explicit_operator_action"] is False
    assert payload["server_operator_action"] == "observe_server"
    assert payload["overall_operator_action"] == "observe_server_refresh_client_evidence_status"
    assert payload["mutation_allowed"] is False
    assert payload["nl_mutation_allowed"] is False
    assert payload["vpn_port"] == 443
    assert payload["packet_loss_percent"] == 0
    assert payload["client_evidence"]["status"] == "unknown"
    assert payload["client_evidence"]["fresh"] is False
    assert payload["client_evidence"]["freshness_status"] == "missing"
    assert payload["client_evidence"]["refresh_required"] is True
    assert payload["client_evidence"]["stale_after"] is None
    assert payload["client_evidence"]["seconds_until_stale"] is None
    assert payload["client_evidence"]["operator_action"] == "refresh_client_evidence_status"
    assert payload["client_evidence"]["mutation_allowed"] is False
    assert payload["client_evidence"]["collection_blockers"] == [
        "client_evidence_status_missing_or_unreadable"
    ]
    assert payload["client_evidence"]["remote_request_packet"]["available"] is False
    assert payload["client_evidence"]["remote_request_packet"]["source_sha256"] is None
    assert payload["client_evidence"]["remote_request_packet"]["source_size_bytes"] == 0
    assert payload["client_evidence"]["remote_request_packet"]["collection_ready"] is False
    assert payload["client_evidence"]["remote_request_packet"]["refresh_required"] is True
    assert payload["client_evidence"]["remote_request_packet"]["stale_after"] is None
    assert payload["client_evidence"]["remote_request_packet"]["seconds_until_stale"] is None
    assert payload["client_evidence"]["remote_request_packet"]["expires_soon"] is False
    assert payload["client_evidence"]["remote_request_packet"]["collection_blockers"] == [
        "request_packet_missing_or_unreadable"
    ]
    assert payload["subscription_payload"]["status"] == "missing"
    assert payload["subscription_payload"]["available"] is False


def test_vpn_status_json_reports_safe_subscription_payload_snapshot(tmp_path: Path) -> None:
    proc = _run_json(
        tmp_path,
        subscription_payload_status={
            "generated_at": "2026-06-05T10:40:33Z",
            "ok": True,
            "decision": "LIVE_SUBSCRIPTION_PAYLOAD_SAFE",
            "checked_subscription_count": 14,
            "candidate_subscription_count": 14,
            "ports": [443, 2083],
            "transport_counts": {"reality": 76},
            "failures": [],
            "expired_error_check": {
                "ok": True,
                "status": "safe",
                "checked_subscription_count": 13,
                "candidate_subscription_count": 13,
                "status_counts": {"403": 13},
                "max_profile_count": 0,
                "ports_seen": [],
                "failures": [],
                "raw_tokens_or_uris_printed": False,
            },
            "privacy": {
                "raw_tokens_printed": False,
                "raw_profile_uris_printed": False,
                "raw_uuid_printed": False,
                "raw_host_printed": False,
            },
        },
        subscription_payload_max_age_seconds=999999999,
    )
    assert proc.returncode == 0, proc.stderr

    payload = json.loads(proc.stdout)
    subscription = payload["subscription_payload"]
    assert subscription["status"] == "safe"
    assert subscription["available"] is True
    assert subscription["fresh"] is True
    assert subscription["ports"] == [443, 2083]
    assert subscription["transport_counts"] == {"reality": 76}
    assert subscription["failures"] == []
    assert subscription["expired_error_check"]["available"] is True
    assert subscription["expired_error_check"]["ok"] is True
    assert subscription["expired_error_check"]["status_counts"] == {"403": 13}
    assert subscription["expired_error_check"]["max_profile_count"] == 0
    assert subscription["expired_error_check"]["ports_seen"] == []
    assert subscription["privacy_ok"] is True
    assert subscription["anti_dpi"]["status"] == "ready_with_warnings"
    assert subscription["anti_dpi"]["primary_reality_443_ready"] is True
    assert subscription["anti_dpi"]["secondary_reality_port_ready"] is True
    assert subscription["anti_dpi"]["reality_only"] is True
    anti_dpi = payload["anti_dpi_readiness"]
    assert anti_dpi["status"] == "attention"
    assert anti_dpi["distribution_ready"] is True
    assert anti_dpi["all_provider_coverage_proven"] is False
    assert anti_dpi["recommended_ports"] == [443, 2083]
    assert anti_dpi["ports"] == [443, 2083]
    assert "external_provider_coverage_not_fully_verified" in anti_dpi["warnings"]
    assert payload["recommended_action"] == "operator_review"


def test_vpn_status_json_refreshes_stale_subscription_payload_before_action(
    tmp_path: Path,
) -> None:
    proc = _run_json(
        tmp_path,
        subscription_payload_status={
            "generated_at": "2026-01-01T00:00:00Z",
            "ok": True,
            "decision": "LIVE_SUBSCRIPTION_PAYLOAD_SAFE",
            "checked_subscription_count": 14,
            "candidate_subscription_count": 14,
            "ports": [443, 2083],
            "transport_counts": {"reality": 76},
            "failures": [],
            "expired_error_check": {
                "ok": True,
                "status": "safe",
                "checked_subscription_count": 13,
                "candidate_subscription_count": 13,
                "status_counts": {"403": 13},
                "max_profile_count": 0,
                "ports_seen": [],
                "failures": [],
                "raw_tokens_or_uris_printed": False,
            },
            "anti_dpi": {
                "status": "ready",
                "ready": True,
                "reality_only": True,
                "legacy_transports_absent": True,
                "checked_subscription_count": 14,
                "ready_subscription_count": 14,
                "primary_reality_443_ready_count": 14,
                "secondary_reality_port_ready_count": 14,
                "all_checked_have_primary_reality_443": True,
                "all_checked_have_secondary_reality_port": True,
                "recommended_port_order": [443, 2083],
                "blockers": [],
                "warnings": [],
                "raw_tokens_or_uris_printed": False,
                "raw_uuid_printed": False,
                "raw_host_printed": False,
            },
            "privacy": {
                "raw_tokens_printed": False,
                "raw_profile_uris_printed": False,
                "raw_uuid_printed": False,
                "raw_host_printed": False,
            },
        },
        subscription_payload_max_age_seconds=1,
    )
    assert proc.returncode == 0, proc.stderr

    payload = json.loads(proc.stdout)
    subscription = payload["subscription_payload"]
    assert subscription["status"] == "stale"
    assert subscription["fresh"] is False
    assert subscription["operator_action"] == "refresh_subscription_payload_status"
    assert "subscription_payload_status_not_fresh" in subscription["failures"]
    next_action = payload["next_safe_action"]
    assert next_action["action"] == "refresh_subscription_payload_status"
    assert next_action["reason"] == "active subscription payload status is stale or missing"
    assert next_action["user_message_allowed_after_review"] is False
    assert next_action["automatic_restart_allowed"] is False
    assert next_action["immediate_readonly_actions"] == [
        "refresh_subscription_payload_status",
        "collect_transport_usage_evidence",
        "collect_legacy_migration_progress",
        "collect_legacy_migration_replies",
    ]
    assert "restart_x-ui" in next_action["blocked_actions"]


def test_vpn_status_json_flags_expired_subscription_profiles_without_restart(
    tmp_path: Path,
) -> None:
    proc = _run_json(
        tmp_path,
        subscription_payload_status={
            "generated_at": "2026-06-05T10:40:33Z",
            "ok": False,
            "decision": "LIVE_SUBSCRIPTION_PAYLOAD_UNSAFE",
            "checked_subscription_count": 14,
            "candidate_subscription_count": 14,
            "ports": [443, 2083],
            "transport_counts": {"reality": 76},
            "failures": ["expired:expired_subscription_returned_vpn_profile"],
            "expired_error_check": {
                "ok": False,
                "status": "unsafe",
                "checked_subscription_count": 1,
                "candidate_subscription_count": 1,
                "status_counts": {"200": 1},
                "max_profile_count": 1,
                "ports_seen": [1],
                "failures": ["expired_subscription_returned_vpn_profile"],
                "raw_tokens_or_uris_printed": False,
            },
            "privacy": {
                "raw_tokens_printed": False,
                "raw_profile_uris_printed": False,
                "raw_uuid_printed": False,
                "raw_host_printed": False,
            },
        },
        subscription_payload_max_age_seconds=999999999,
    )
    assert proc.returncode == 0, proc.stderr

    payload = json.loads(proc.stdout)
    subscription = payload["subscription_payload"]
    assert subscription["status"] == "unsafe"
    assert "subscription_payload_expired_error_check_not_ok" in subscription["failures"]
    assert "subscription_payload_expired_subscription_returned_profile" in subscription["failures"]
    assert "subscription_payload_expired_subscription_returned_ports" in subscription["failures"]
    assert payload["overall_status"] == "advisory"
    assert payload["recommended_action"] == "operator_review"
    assert payload["restart_recommended"] is False


def test_vpn_status_json_flags_legacy_transport_attention_without_restart(
    tmp_path: Path,
) -> None:
    proc = _run_json(
        tmp_path,
        transport_usage_status={
            "generated_at": "2026-06-05T12:17:49Z",
            "ok": False,
            "decision": "TRANSPORT_USAGE_ATTENTION",
            "operator_action": "check_legacy_clients_and_migrate_to_reality",
            "summary": {
                "recent_window_minutes": 60,
                "status": "attention",
                "severity": "single_source_stale_legacy",
                "attention_scope": "single_proxy_source",
                "restart_relevant": False,
                "proxy_requests": 65,
                "dataplane_events": 0,
                "max_unique_proxy_source_count": 1,
                "aggregate_unique_proxy_source_count": 1,
                "attention_unique_proxy_source_count": 1,
                "operator_action": "monitor_single_stale_legacy_source_after_migration",
            },
            "findings": [
                "60m:ghost_xhttp:legacy_proxy_4xx_seen",
                "60m:ghost_xhttp:legacy_proxy_requests_without_dataplane",
            ],
            "privacy": {
                "raw_identifiers_stored": False,
                "raw_ip_stored": False,
                "raw_nginx_source_ip_stored": False,
                "raw_email_stored": False,
                "raw_target_host_stored": False,
                "raw_user_agent_stored": False,
            },
            "windows": {
                "60m": {
                    "legacy_transport_health": {
                        "ok": False,
                        "status": "attention",
                        "severity": "single_source_stale_legacy",
                        "attention_scope": "single_proxy_source",
                        "restart_relevant": False,
                        "proxy_requests": 65,
                        "dataplane_events": 0,
                        "max_unique_proxy_source_count": 1,
                        "aggregate_unique_proxy_source_count": 1,
                        "attention_unique_proxy_source_count": 1,
                        "operator_action": "monitor_single_stale_legacy_source_after_migration",
                        "findings": [
                            "ghost_xhttp:legacy_proxy_4xx_seen",
                            "ghost_xhttp:legacy_proxy_requests_without_dataplane",
                        ],
                        "transports": {
                            "ghost_xhttp": {
                                "status": "legacy_attention",
                                "attention_scope": "single_proxy_source",
                                "restart_relevant": False,
                                "proxy_requests": 65,
                                "proxy_4xx": 65,
                                "proxy_5xx": 0,
                                "unique_proxy_source_count": 1,
                                "proxy_method_counts": {"GET": 65},
                                "proxy_user_agent_family_counts": {"xray": 65},
                                "dataplane_events": 0,
                                "unique_client_count": 0,
                                "last_proxy_seen_at": "2026-06-05T12:17:22Z",
                                "last_dataplane_seen_at": None,
                                "findings": [
                                    "legacy_proxy_requests_without_dataplane",
                                    "legacy_proxy_4xx_seen",
                                ],
                            }
                        },
                    }
                }
            },
        },
        transport_usage_max_age_seconds=999999999,
    )
    assert proc.returncode == 0, proc.stderr

    payload = json.loads(proc.stdout)
    transport_usage = payload["transport_usage"]
    assert transport_usage["status"] == "attention"
    assert transport_usage["fresh"] is True
    assert transport_usage["privacy_ok"] is True
    assert transport_usage["severity"] == "single_source_stale_legacy"
    assert transport_usage["summary"]["severity"] == "single_source_stale_legacy"
    assert transport_usage["attention_scope"] == "single_proxy_source"
    assert transport_usage["summary"]["attention_scope"] == "single_proxy_source"
    assert transport_usage["restart_relevant"] is False
    assert transport_usage["summary"]["restart_relevant"] is False
    assert transport_usage["recent_window_minutes"] == 60
    assert transport_usage["proxy_requests"] == 65
    assert transport_usage["dataplane_events"] == 0
    assert transport_usage["aggregate_unique_proxy_source_count"] == 1
    assert transport_usage["attention_unique_proxy_source_count"] == 1
    assert transport_usage["windows"]["60m"]["transports"]["ghost_xhttp"]["proxy_4xx"] == 65
    assert transport_usage["windows"]["60m"]["transports"]["ghost_xhttp"]["unique_proxy_source_count"] == 1
    assert transport_usage["windows"]["60m"]["transports"]["ghost_xhttp"]["proxy_method_counts"] == {"GET": 65}
    assert transport_usage["windows"]["60m"]["transports"]["ghost_xhttp"]["proxy_user_agent_family_counts"] == {"xray": 65}
    assert transport_usage["windows"]["60m"]["transports"]["ghost_xhttp"]["attention_scope"] == "single_proxy_source"
    assert transport_usage["windows"]["60m"]["transports"]["ghost_xhttp"]["restart_relevant"] is False
    assert payload["overall_status"] == "advisory"
    assert payload["recommended_action"] == "operator_review"
    assert payload["overall_operator_action"] == "monitor_single_stale_legacy_source_after_migration"
    assert payload["restart_recommended"] is False
    assert payload["restart_scope"] == "none"


def test_vpn_status_json_surfaces_ready_legacy_migration_packet(
    tmp_path: Path,
) -> None:
    proc = _run_json(
        tmp_path,
        transport_usage_status={
            "generated_at": "2026-06-05T12:17:49Z",
            "ok": False,
            "decision": "TRANSPORT_USAGE_ATTENTION",
            "operator_action": "check_legacy_clients_and_migrate_to_reality",
            "findings": ["60m:ghost_xhttp:legacy_proxy_4xx_seen"],
            "privacy": {
                "raw_identifiers_stored": False,
                "raw_ip_stored": False,
                "raw_email_stored": False,
                "raw_target_host_stored": False,
            },
            "windows": {
                "60m": {
                    "legacy_transport_health": {
                        "ok": False,
                        "status": "attention",
                        "findings": ["ghost_xhttp:legacy_proxy_4xx_seen"],
                        "transports": {},
                    }
                }
            },
        },
        transport_usage_max_age_seconds=999999999,
        legacy_migration_status={
            "generated_at": "2026-06-05T12:40:00Z",
            "decision": "LEGACY_CLIENT_MIGRATION_PACKET_READY",
            "operator_action": "ask_legacy_clients_to_refresh_reality_profile",
            "target_audience": {
                "active_subscription_count": 14,
                "expired_users_excluded": 13,
                "users_with_devices": 27,
                "raw_user_ids_printed": False,
                "raw_chat_ids_printed": False,
            },
            "migration_request": {
                "safe_reply_options": [
                    "done updated",
                    "fail import",
                    "fail timeout",
                    "fail no-internet",
                ],
            },
            "send_policy": {
                "automatic_broadcast_allowed": False,
                "manual_operator_review_required": True,
            },
            "privacy": {
                "raw_user_ids_printed": False,
                "raw_chat_ids_printed": False,
                "raw_tokens_printed": False,
                "raw_subscription_urls_printed": False,
                "raw_vpn_uris_printed": False,
                "raw_uuid_printed": False,
                "raw_ip_printed": False,
                "raw_telegram_handle_printed": False,
            },
        },
        legacy_migration_max_age_seconds=999999999,
    )
    assert proc.returncode == 0, proc.stderr

    payload = json.loads(proc.stdout)
    migration = payload["legacy_migration"]
    assert migration["status"] == "ready"
    assert migration["ready"] is True
    assert migration["target_audience"]["active_subscription_count"] == 14
    assert migration["safe_reply_options"] == [
        "done updated",
        "fail import",
        "fail timeout",
        "fail no-internet",
    ]
    assert payload["overall_status"] == "advisory"
    assert payload["overall_operator_action"] == "ask_legacy_clients_to_refresh_reality_profile"
    assert payload["restart_recommended"] is False
    assert payload["restart_scope"] == "none"


def test_vpn_status_json_surfaces_partial_legacy_migration_replies(
    tmp_path: Path,
) -> None:
    proc = _run_json(
        tmp_path,
        transport_usage_status={
            "generated_at": "2026-06-05T12:17:49Z",
            "ok": False,
            "decision": "TRANSPORT_USAGE_ATTENTION",
            "operator_action": "check_legacy_clients_and_migrate_to_reality",
            "findings": ["60m:ghost_xhttp:legacy_proxy_4xx_seen"],
            "privacy": {
                "raw_identifiers_stored": False,
                "raw_ip_stored": False,
                "raw_email_stored": False,
                "raw_target_host_stored": False,
            },
            "windows": {},
        },
        transport_usage_max_age_seconds=999999999,
        legacy_migration_status={
            "generated_at": "2026-06-05T12:40:00Z",
            "decision": "LEGACY_CLIENT_MIGRATION_PACKET_READY",
            "operator_action": "ask_legacy_clients_to_refresh_reality_profile",
            "target_audience": {
                "active_subscription_count": 14,
                "expired_users_excluded": 13,
                "users_with_devices": 27,
                "raw_user_ids_printed": False,
                "raw_chat_ids_printed": False,
            },
            "migration_request": {
                "safe_reply_options": ["done updated", "fail import"],
            },
            "send_policy": {
                "automatic_broadcast_allowed": False,
                "manual_operator_review_required": True,
            },
            "privacy": {
                "raw_user_ids_printed": False,
                "raw_chat_ids_printed": False,
                "raw_tokens_printed": False,
                "raw_subscription_urls_printed": False,
                "raw_vpn_uris_printed": False,
                "raw_uuid_printed": False,
                "raw_ip_printed": False,
                "raw_telegram_handle_printed": False,
            },
        },
        legacy_migration_max_age_seconds=999999999,
        legacy_migration_replies_status={
            "generated_at": "2026-06-05T12:50:00Z",
            "status": "partial_client_replies",
            "operator_action": "continue_collecting_legacy_migration_replies",
            "packet": {"sha256": "a" * 64},
            "total_replies": 1,
            "done_updated_count": 1,
            "failure_count": 0,
            "reply_counts": {"done updated": 1},
            "result_counts": {"done": 1},
            "symptom_counts": {"updated": 1},
            "privacy": {
                "raw_user_ids_stored": False,
                "raw_chat_ids_stored": False,
                "raw_tokens_stored": False,
                "raw_subscription_urls_stored": False,
                "raw_vpn_uris_stored": False,
                "raw_uuid_stored": False,
                "raw_ip_stored": False,
                "raw_telegram_handle_stored": False,
            },
        },
        legacy_migration_replies_max_age_seconds=999999999,
    )
    assert proc.returncode == 0, proc.stderr

    payload = json.loads(proc.stdout)
    replies = payload["legacy_migration_replies"]
    assert replies["status"] == "partial_client_replies"
    assert replies["total_replies"] == 1
    assert replies["done_updated_count"] == 1
    assert replies["reply_counts"] == {"done updated": 1}
    assert replies["privacy_ok"] is True
    assert payload["overall_operator_action"] == "continue_collecting_legacy_migration_replies"
    assert payload["restart_recommended"] is False
    assert payload["restart_scope"] == "none"


def test_vpn_status_json_surfaces_legacy_migration_progress_before_replies(
    tmp_path: Path,
) -> None:
    proc = _run_json(
        tmp_path,
        transport_usage_status={
            "generated_at": "2026-06-05T12:17:49Z",
            "ok": False,
            "decision": "TRANSPORT_USAGE_ATTENTION",
            "operator_action": "check_legacy_clients_and_migrate_to_reality",
            "findings": ["60m:ghost_xhttp:legacy_proxy_4xx_seen"],
            "privacy": {
                "raw_identifiers_stored": False,
                "raw_ip_stored": False,
                "raw_email_stored": False,
                "raw_target_host_stored": False,
            },
            "windows": {},
        },
        transport_usage_max_age_seconds=999999999,
        legacy_migration_status={
            "generated_at": "2026-06-05T12:40:00Z",
            "decision": "LEGACY_CLIENT_MIGRATION_PACKET_READY",
            "operator_action": "ask_legacy_clients_to_refresh_reality_profile",
            "target_audience": {
                "active_subscription_count": 14,
                "expired_users_excluded": 13,
                "users_with_devices": 27,
                "raw_user_ids_printed": False,
                "raw_chat_ids_printed": False,
            },
            "migration_request": {
                "safe_reply_options": ["done updated", "fail import"],
            },
            "send_policy": {
                "automatic_broadcast_allowed": False,
                "manual_operator_review_required": True,
            },
            "privacy": {
                "raw_user_ids_printed": False,
                "raw_chat_ids_printed": False,
                "raw_tokens_printed": False,
                "raw_subscription_urls_printed": False,
                "raw_vpn_uris_printed": False,
                "raw_uuid_printed": False,
                "raw_ip_printed": False,
                "raw_telegram_handle_printed": False,
            },
        },
        legacy_migration_max_age_seconds=999999999,
        legacy_migration_progress_status={
            "generated_at": "2026-06-05T13:55:00Z",
            "status": "migration_progress_seen",
            "operator_action": "monitor_remaining_client_replies_and_legacy_transport",
            "sent_at": "2026-06-05T13:27:02Z",
            "packet": {"target_active_subscription_count": 14},
            "message_send": {"sent_count": 14},
            "replies": {"done_updated_count": 0, "failure_count": 0},
            "db_progress": {
                "subscription_refresh": {
                    "active_users_with_subscription_pull_since_message": 1,
                },
                "device_activity": {
                    "active_users_with_device_activity_since_message": 6,
                },
                "combined": {
                    "active_users_with_any_progress_since_message": 6,
                    "active_users_with_subscription_and_device_progress_since_message": 1,
                },
            },
            "privacy": {
                "raw_user_ids_stored": False,
                "raw_chat_ids_stored": False,
                "raw_tokens_stored": False,
                "raw_subscription_urls_stored": False,
                "raw_vpn_uris_stored": False,
                "raw_uuid_stored": False,
                "raw_ip_stored": False,
                "raw_telegram_handle_stored": False,
            },
        },
        legacy_migration_progress_max_age_seconds=999999999,
    )
    assert proc.returncode == 0, proc.stderr

    payload = json.loads(proc.stdout)
    progress = payload["legacy_migration_progress"]
    assert progress["status"] == "migration_progress_seen"
    assert progress["sent_count"] == 14
    assert progress["active_users_with_device_activity_since_message"] == 6
    assert progress["privacy_ok"] is True
    verification = payload["user_connectivity_verification"]
    assert payload["user_connectivity"] == verification
    assert verification["status"] == "partial_user_progress"
    assert verification["user_connectivity_proven"] is False
    assert verification["proven"] is False
    assert verification["target_active_user_count"] == 14
    assert verification["target_active_users"] == 14
    assert verification["positive_signal_count"] == 6
    assert verification["positive_user_signals"] == 6
    assert verification["confirmed_by_reply_count"] == 0
    assert verification["unconfirmed_by_reply_count"] == 14
    assert verification["unverified_by_any_signal_count"] == 8
    assert "not_all_users_confirmed_by_reply" in verification["blockers"]
    assert "some_active_users_without_progress_signal" in verification["blockers"]
    assert "legacy_transport_still_polling" in verification["blockers"]
    assert payload["overall_operator_action"] == "monitor_remaining_client_replies_and_legacy_transport"
    assert payload["restart_recommended"] is False
    assert payload["restart_scope"] == "none"


def test_vpn_status_json_marks_user_connectivity_verified_only_after_all_replies(
    tmp_path: Path,
) -> None:
    proc = _run_json(
        tmp_path,
        subscription_payload_status={
            "generated_at": "2026-06-05T15:00:00Z",
            "ok": True,
            "decision": "LIVE_SUBSCRIPTION_PAYLOAD_SAFE",
            "checked_subscription_count": 2,
            "candidate_subscription_count": 2,
            "ports": [443, 2083],
            "transport_counts": {"reality": 4},
            "failures": [],
            "expired_error_check": {
                "ok": True,
                "status": "expired_checked",
                "checked_subscription_count": 1,
                "candidate_subscription_count": 1,
                "status_counts": {"403": 1},
                "max_profile_count": 0,
                "ports_seen": [],
                "failures": [],
                "raw_tokens_or_uris_printed": False,
            },
            "privacy": {
                "raw_tokens_printed": False,
                "raw_profile_uris_printed": False,
                "raw_uuid_printed": False,
                "raw_host_printed": False,
            },
        },
        subscription_payload_max_age_seconds=999999999,
        transport_usage_status={
            "generated_at": "2026-06-05T15:00:00Z",
            "ok": True,
            "decision": "TRANSPORT_USAGE_OK",
            "operator_action": "observe",
            "findings": [],
            "summary": {
                "recent_window_minutes": 15,
                "status": "ok",
                "severity": "none",
                "attention_scope": "none",
                "restart_relevant": False,
                "proxy_requests": 0,
                "dataplane_events": 0,
                "max_unique_proxy_source_count": 0,
                "aggregate_unique_proxy_source_count": 0,
                "attention_unique_proxy_source_count": 0,
                "operator_action": "observe",
            },
            "privacy": {
                "raw_identifiers_stored": False,
                "raw_ip_stored": False,
                "raw_nginx_source_ip_stored": False,
                "raw_email_stored": False,
                "raw_target_host_stored": False,
                "raw_user_agent_stored": False,
            },
            "windows": {},
        },
        transport_usage_max_age_seconds=999999999,
        legacy_migration_progress_status={
            "generated_at": "2026-06-05T15:00:00Z",
            "status": "all_active_device_activity_seen_after_message",
            "operator_action": "observe",
            "sent_at": "2026-06-05T13:27:02Z",
            "packet": {"target_active_subscription_count": 2},
            "message_send": {"sent_count": 2},
            "replies": {"done_updated_count": 2, "failure_count": 0},
            "db_progress": {
                "subscription_refresh": {
                    "active_users_with_subscription_pull_since_message": 2,
                },
                "device_activity": {
                    "active_users_with_device_activity_since_message": 2,
                },
                "combined": {
                    "active_users_with_any_progress_since_message": 2,
                    "active_users_with_subscription_and_device_progress_since_message": 2,
                },
            },
            "privacy": {
                "raw_user_ids_stored": False,
                "raw_chat_ids_stored": False,
                "raw_tokens_stored": False,
                "raw_subscription_urls_stored": False,
                "raw_vpn_uris_stored": False,
                "raw_uuid_stored": False,
                "raw_ip_stored": False,
                "raw_telegram_handle_stored": False,
            },
        },
        legacy_migration_progress_max_age_seconds=999999999,
        legacy_migration_replies_status={
            "generated_at": "2026-06-05T15:00:00Z",
            "status": "all_reported_updated_by_count",
            "operator_action": "observe",
            "total_replies": 2,
            "done_updated_count": 2,
            "failure_count": 0,
            "reply_counts": {"done updated": 2},
            "result_counts": {"pass": 2},
            "symptom_counts": {},
            "packet": {"sha256": "abc123"},
            "privacy": {
                "raw_user_ids_stored": False,
                "raw_chat_ids_stored": False,
                "raw_tokens_stored": False,
                "raw_subscription_urls_stored": False,
                "raw_vpn_uris_stored": False,
                "raw_uuid_stored": False,
                "raw_ip_stored": False,
                "raw_telegram_handle_stored": False,
            },
        },
        legacy_migration_replies_max_age_seconds=999999999,
    )
    assert proc.returncode == 0, proc.stderr

    payload = json.loads(proc.stdout)
    verification = payload["user_connectivity_verification"]
    assert verification["status"] == "verified_by_user_replies"
    assert verification["user_connectivity_proven"] is True
    assert verification["proven"] is True
    assert verification["target_active_user_count"] == 2
    assert verification["target_active_users"] == 2
    assert verification["confirmed_by_reply_count"] == 2
    assert verification["positive_signal_count"] == 2
    assert verification["positive_user_signals"] == 2
    assert verification["unconfirmed_by_reply_count"] == 0
    assert verification["unverified_by_any_signal_count"] == 0
    assert verification["blockers"] == []
    assert verification["operator_action"] == "observe"
    assert payload["overall_status"] == "ok"
    assert payload["recommended_action"] == "observe"
    assert payload["restart_recommended"] is False


def test_vpn_status_json_surfaces_legacy_no_progress_nudge_cooldown(
    tmp_path: Path,
) -> None:
    now = datetime.now(UTC).replace(microsecond=0)
    fresh_at = (now - timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    last_send_at = (now - timedelta(hours=6)).isoformat().replace("+00:00", "Z")
    next_nudge_at = (now + timedelta(hours=6)).isoformat().replace("+00:00", "Z")
    proc = _run_json(
        tmp_path,
        subscription_payload_status={
            "generated_at": fresh_at,
            "ok": True,
            "decision": "LIVE_SUBSCRIPTION_PAYLOAD_SAFE",
            "checked_subscription_count": 14,
            "candidate_subscription_count": 14,
            "ports": [443, 2083],
            "transport_counts": {"reality": 76},
            "failures": [],
            "expired_error_check": {
                "ok": True,
                "status": "safe",
                "checked_subscription_count": 13,
                "candidate_subscription_count": 13,
                "status_counts": {"403": 13},
                "max_profile_count": 0,
                "ports_seen": [],
                "failures": [],
                "raw_tokens_or_uris_printed": False,
            },
            "anti_dpi": {
                "status": "ready",
                "ready": True,
                "reality_only": True,
                "legacy_transports_absent": True,
                "checked_subscription_count": 14,
                "ready_subscription_count": 14,
                "primary_reality_443_ready_count": 14,
                "secondary_reality_port_ready_count": 14,
                "all_checked_have_primary_reality_443": True,
                "all_checked_have_secondary_reality_port": True,
                "recommended_port_order": [443, 2083],
                "blockers": [],
                "warnings": [],
                "raw_tokens_or_uris_printed": False,
                "raw_uuid_printed": False,
                "raw_host_printed": False,
            },
            "privacy": {
                "raw_tokens_printed": False,
                "raw_profile_uris_printed": False,
                "raw_uuid_printed": False,
                "raw_host_printed": False,
            },
        },
        subscription_payload_max_age_seconds=999999999,
        legacy_no_progress_nudge_status={
            "generated_at": last_send_at,
            "decision": "LEGACY_NO_PROGRESS_NUDGE_SENT",
            "mode": "apply",
            "active_user_count": 14,
            "progress_user_count": 7,
            "reply_user_count": 0,
            "no_progress_candidate_count": 7,
            "selected_user_count": 7,
            "sent_count": 7,
            "failed_count": 0,
            "blocked_count": 0,
            "privacy": {
                "raw_user_ids_printed": False,
                "raw_chat_ids_printed": False,
                "raw_tokens_printed": False,
                "raw_subscription_urls_printed": False,
                "raw_vpn_uris_printed": False,
                "raw_uuid_printed": False,
                "raw_ip_printed": False,
                "raw_telegram_handle_printed": False,
            },
        },
        legacy_no_progress_nudge_dry_run_status={
            "generated_at": fresh_at,
            "decision": "LEGACY_NO_PROGRESS_NUDGE_DRY_RUN",
            "mode": "dry_run",
            "active_user_count": 14,
            "progress_user_count": 10,
            "reply_user_count": 0,
            "no_progress_candidate_count": 4,
            "selected_user_count": 0,
            "sent_count": 0,
            "failed_count": 0,
            "blocked_count": 0,
            "privacy": {
                "raw_user_ids_printed": False,
                "raw_chat_ids_printed": False,
                "raw_tokens_printed": False,
                "raw_subscription_urls_printed": False,
                "raw_vpn_uris_printed": False,
                "raw_uuid_printed": False,
                "raw_ip_printed": False,
                "raw_telegram_handle_printed": False,
            },
        },
        legacy_no_progress_nudge_max_age_seconds=999999999,
        legacy_no_progress_nudge_dry_run_max_age_seconds=999999999,
        legacy_no_progress_nudge_cooldown_hours=12,
    )
    assert proc.returncode == 0, proc.stderr

    payload = json.loads(proc.stdout)
    nudge = payload["legacy_no_progress_nudge"]
    assert nudge["status"] == "sent"
    assert nudge["sent_count"] == 7
    assert nudge["no_progress_candidate_count"] == 7
    assert nudge["cooldown_active"] is True
    assert nudge["next_nudge_allowed_at"] == next_nudge_at
    assert nudge["privacy_ok"] is True
    assert nudge["operator_action"] == "monitor_remaining_client_replies_and_legacy_transport"
    dry_run = payload["legacy_no_progress_nudge_dry_run"]
    assert dry_run["status"] == "dry_run"
    assert dry_run["fresh"] is True
    assert dry_run["max_age_seconds"] == 999999999
    assert dry_run["no_progress_candidate_count"] == 4
    assert dry_run["cooldown_active"] is False
    assert dry_run["next_nudge_allowed_at"] is None
    verification = payload["user_connectivity_verification"]
    assert verification["dry_run_progress_count"] == 10
    assert verification["positive_signal_count"] == 10
    assert verification["no_progress_candidate_count"] == 4
    assert verification["no_progress_candidate_source"] == "dry_run"
    next_action = payload["next_safe_action"]
    assert next_action["action"] == "wait_for_nudge_cooldown_and_collect_readonly_evidence"
    assert next_action["earliest_mutation_at"] == next_nudge_at
    assert next_action["earliest_mutation_seconds_until"] is not None
    assert 0 < next_action["earliest_mutation_seconds_until"] <= 6 * 60 * 60
    assert next_action["no_progress_candidate_count"] == 4
    assert next_action["no_progress_dry_run_available"] is True
    assert next_action["no_progress_dry_run_fresh"] is True
    assert next_action["no_progress_dry_run_ready_for_apply"] is True
    assert next_action["no_progress_dry_run_valid_through_earliest_mutation"] is True
    assert next_action["no_progress_dry_run_generated_at"] == fresh_at
    assert next_action["no_progress_dry_run_seconds_until_stale"] is not None
    assert next_action["automatic_restart_allowed"] is False
    assert "send_duplicate_no_progress_nudge_before_cooldown" in next_action["blocked_actions"]
    assert "restart_x-ui" in next_action["blocked_actions"]
    assert next_action["immediate_readonly_actions"] == [
        "collect_transport_usage_evidence",
        "collect_legacy_migration_progress",
        "collect_legacy_migration_replies",
    ]
    assert payload["restart_recommended"] is False
    assert payload["restart_scope"] == "none"


def test_vpn_status_json_omits_immediate_refreshes_when_cooldown_evidence_is_fresh(
    tmp_path: Path,
) -> None:
    now = datetime.now(UTC).replace(microsecond=0)
    fresh_at = (now - timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    last_send_at = (now - timedelta(hours=6)).isoformat().replace("+00:00", "Z")
    proc = _run_json(
        tmp_path,
        subscription_payload_status={
            "generated_at": fresh_at,
            "ok": True,
            "decision": "LIVE_SUBSCRIPTION_PAYLOAD_SAFE",
            "checked_subscription_count": 14,
            "candidate_subscription_count": 14,
            "ports": [443, 2083],
            "transport_counts": {"reality": 76},
            "failures": [],
            "expired_error_check": {
                "ok": True,
                "status": "safe",
                "checked_subscription_count": 13,
                "candidate_subscription_count": 13,
                "status_counts": {"403": 13},
                "max_profile_count": 0,
                "ports_seen": [],
                "failures": [],
                "raw_tokens_or_uris_printed": False,
            },
            "anti_dpi": {
                "status": "ready",
                "ready": True,
                "reality_only": True,
                "legacy_transports_absent": True,
                "checked_subscription_count": 14,
                "ready_subscription_count": 14,
                "primary_reality_443_ready_count": 14,
                "secondary_reality_port_ready_count": 14,
                "all_checked_have_primary_reality_443": True,
                "all_checked_have_secondary_reality_port": True,
                "recommended_port_order": [443, 2083],
                "blockers": [],
                "warnings": [],
                "raw_tokens_or_uris_printed": False,
                "raw_uuid_printed": False,
                "raw_host_printed": False,
            },
            "privacy": {
                "raw_tokens_printed": False,
                "raw_profile_uris_printed": False,
                "raw_uuid_printed": False,
                "raw_host_printed": False,
            },
        },
        subscription_payload_max_age_seconds=1800,
        transport_usage_status={
            "generated_at": fresh_at,
            "decision": "TRANSPORT_USAGE_ATTENTION",
            "ok": False,
            "operator_action": "monitor_single_stale_legacy_source_after_migration",
            "findings": ["ghost_xhttp:legacy_proxy_4xx_seen"],
            "summary": {
                "recent_window_minutes": 15,
                "severity": "single_source_stale_legacy",
                "attention_scope": "single_proxy_source",
                "restart_relevant": False,
                "proxy_requests": 17,
                "dataplane_events": 0,
                "max_unique_proxy_source_count": 1,
                "aggregate_unique_proxy_source_count": 1,
                "attention_unique_proxy_source_count": 1,
                "operator_action": "monitor_single_stale_legacy_source_after_migration",
            },
            "privacy": {
                "raw_identifiers_stored": False,
                "raw_ip_stored": False,
                "raw_email_stored": False,
                "raw_target_host_stored": False,
            },
        },
        transport_usage_max_age_seconds=900,
        legacy_migration_replies_status={
            "generated_at": fresh_at,
            "status": "no_client_replies",
            "operator_action": "collect_legacy_migration_replies",
            "total_replies": 0,
            "done_updated_count": 0,
            "failure_count": 0,
            "reply_counts": {},
            "result_counts": {},
            "symptom_counts": {},
            "packet": {"sha256": "packet-sha"},
            "privacy": {
                "raw_user_ids_stored": False,
                "raw_chat_ids_stored": False,
                "raw_tokens_stored": False,
                "raw_subscription_urls_stored": False,
                "raw_vpn_uris_stored": False,
                "raw_uuid_stored": False,
                "raw_ip_stored": False,
                "raw_telegram_handle_stored": False,
            },
        },
        legacy_migration_replies_max_age_seconds=1800,
        legacy_migration_progress_status={
            "generated_at": fresh_at,
            "status": "migration_progress_seen",
            "operator_action": "monitor_remaining_client_replies_and_legacy_transport",
            "sent_at": last_send_at,
            "packet": {"target_active_subscription_count": 14},
            "message_send": {"sent_count": 14},
            "replies": {"done_updated_count": 0, "failure_count": 0},
            "db_progress": {
                "subscription_refresh": {
                    "active_users_with_subscription_pull_since_message": 5
                },
                "device_activity": {
                    "active_users_with_device_activity_since_message": 9
                },
                "combined": {
                    "active_users_with_any_progress_since_message": 10,
                    "active_users_with_subscription_and_device_progress_since_message": 4,
                },
            },
            "privacy": {
                "raw_user_ids_stored": False,
                "raw_chat_ids_stored": False,
                "raw_tokens_stored": False,
                "raw_subscription_urls_stored": False,
                "raw_vpn_uris_stored": False,
                "raw_uuid_stored": False,
                "raw_ip_stored": False,
                "raw_telegram_handle_stored": False,
            },
        },
        legacy_migration_progress_max_age_seconds=1800,
        legacy_no_progress_nudge_status={
            "generated_at": last_send_at,
            "decision": "LEGACY_NO_PROGRESS_NUDGE_SENT",
            "mode": "apply",
            "active_user_count": 14,
            "progress_user_count": 7,
            "reply_user_count": 0,
            "no_progress_candidate_count": 7,
            "selected_user_count": 7,
            "sent_count": 7,
            "failed_count": 0,
            "blocked_count": 0,
            "privacy": {
                "raw_user_ids_printed": False,
                "raw_chat_ids_printed": False,
                "raw_tokens_printed": False,
                "raw_subscription_urls_printed": False,
                "raw_vpn_uris_printed": False,
                "raw_uuid_printed": False,
                "raw_ip_printed": False,
                "raw_telegram_handle_printed": False,
            },
        },
        legacy_no_progress_nudge_dry_run_status={
            "generated_at": fresh_at,
            "decision": "LEGACY_NO_PROGRESS_NUDGE_DRY_RUN",
            "mode": "dry_run",
            "active_user_count": 14,
            "progress_user_count": 10,
            "reply_user_count": 0,
            "no_progress_candidate_count": 4,
            "selected_user_count": 0,
            "sent_count": 0,
            "failed_count": 0,
            "blocked_count": 0,
            "privacy": {
                "raw_user_ids_printed": False,
                "raw_chat_ids_printed": False,
                "raw_tokens_printed": False,
                "raw_subscription_urls_printed": False,
                "raw_vpn_uris_printed": False,
                "raw_uuid_printed": False,
                "raw_ip_printed": False,
                "raw_telegram_handle_printed": False,
            },
        },
        legacy_no_progress_nudge_max_age_seconds=999999999,
        legacy_no_progress_nudge_dry_run_max_age_seconds=1800,
        legacy_no_progress_nudge_cooldown_hours=12,
    )
    assert proc.returncode == 0, proc.stderr

    payload = json.loads(proc.stdout)
    verification = payload["user_connectivity_verification"]
    assert verification["legacy_migration_progress_fresh"] is True
    assert verification["legacy_migration_replies_fresh"] is True
    next_action = payload["next_safe_action"]
    assert next_action["action"] == "wait_for_nudge_cooldown_and_collect_readonly_evidence"
    assert next_action["earliest_mutation_seconds_until"] is not None
    assert 0 < next_action["earliest_mutation_seconds_until"] <= 6 * 60 * 60
    assert next_action["immediate_readonly_actions"] == []
    assert next_action["transport_usage_fresh"] is True
    assert next_action["transport_usage_valid_through_earliest_mutation"] is False
    assert next_action["legacy_migration_progress_fresh"] is True
    assert next_action["legacy_migration_progress_valid_through_earliest_mutation"] is False
    assert next_action["legacy_migration_replies_fresh"] is True
    assert next_action["legacy_migration_replies_valid_through_earliest_mutation"] is False
    assert next_action["deferred_readonly_actions"] == [
        "refresh_transport_usage_evidence_before_user_nudge",
        "collect_legacy_migration_progress_before_user_nudge",
        "collect_legacy_migration_replies_before_user_nudge",
        "refresh_no_progress_nudge_dry_run_before_user_nudge",
        "refresh_subscription_payload_status_before_user_nudge",
    ]


def test_vpn_status_json_refreshes_stale_no_progress_dry_run_before_user_nudge(
    tmp_path: Path,
) -> None:
    proc = _run_json(
        tmp_path,
        subscription_payload_status={
            "generated_at": "2026-06-05T14:28:51Z",
            "ok": True,
            "decision": "LIVE_SUBSCRIPTION_PAYLOAD_SAFE",
            "checked_subscription_count": 14,
            "candidate_subscription_count": 14,
            "ports": [443, 2083],
            "transport_counts": {"reality": 76},
            "failures": [],
            "expired_error_check": {
                "ok": True,
                "status": "safe",
                "checked_subscription_count": 13,
                "candidate_subscription_count": 13,
                "status_counts": {"403": 13},
                "max_profile_count": 0,
                "ports_seen": [],
                "failures": [],
                "raw_tokens_or_uris_printed": False,
            },
            "anti_dpi": {
                "status": "ready",
                "ready": True,
                "reality_only": True,
                "legacy_transports_absent": True,
                "checked_subscription_count": 14,
                "ready_subscription_count": 14,
                "primary_reality_443_ready_count": 14,
                "secondary_reality_port_ready_count": 14,
                "all_checked_have_primary_reality_443": True,
                "all_checked_have_secondary_reality_port": True,
                "recommended_port_order": [443, 2083],
                "blockers": [],
                "warnings": [],
                "raw_tokens_or_uris_printed": False,
                "raw_uuid_printed": False,
                "raw_host_printed": False,
            },
            "privacy": {
                "raw_tokens_printed": False,
                "raw_profile_uris_printed": False,
                "raw_uuid_printed": False,
                "raw_host_printed": False,
            },
        },
        subscription_payload_max_age_seconds=999999999,
        legacy_no_progress_nudge_status={
            "generated_at": "2026-06-01T00:00:00Z",
            "decision": "LEGACY_NO_PROGRESS_NUDGE_SENT",
            "mode": "apply",
            "active_user_count": 14,
            "progress_user_count": 7,
            "reply_user_count": 0,
            "no_progress_candidate_count": 7,
            "selected_user_count": 7,
            "sent_count": 7,
            "failed_count": 0,
            "blocked_count": 0,
            "privacy": {
                "raw_user_ids_printed": False,
                "raw_chat_ids_printed": False,
                "raw_tokens_printed": False,
                "raw_subscription_urls_printed": False,
                "raw_vpn_uris_printed": False,
                "raw_uuid_printed": False,
                "raw_ip_printed": False,
                "raw_telegram_handle_printed": False,
            },
        },
        legacy_no_progress_nudge_dry_run_status={
            "generated_at": "2026-01-01T00:00:00Z",
            "decision": "LEGACY_NO_PROGRESS_NUDGE_DRY_RUN",
            "mode": "dry_run",
            "active_user_count": 14,
            "progress_user_count": 10,
            "reply_user_count": 0,
            "no_progress_candidate_count": 4,
            "selected_user_count": 0,
            "sent_count": 0,
            "failed_count": 0,
            "blocked_count": 0,
            "privacy": {
                "raw_user_ids_printed": False,
                "raw_chat_ids_printed": False,
                "raw_tokens_printed": False,
                "raw_subscription_urls_printed": False,
                "raw_vpn_uris_printed": False,
                "raw_uuid_printed": False,
                "raw_ip_printed": False,
                "raw_telegram_handle_printed": False,
            },
        },
        legacy_no_progress_nudge_max_age_seconds=999999999,
        legacy_no_progress_nudge_dry_run_max_age_seconds=1800,
    )
    assert proc.returncode == 0, proc.stderr

    payload = json.loads(proc.stdout)
    dry_run = payload["legacy_no_progress_nudge_dry_run"]
    assert dry_run["status"] == "stale"
    assert dry_run["fresh"] is False
    assert dry_run["cooldown_active"] is False
    assert dry_run["next_nudge_allowed_at"] is None
    verification = payload["user_connectivity_verification"]
    assert verification["no_progress_candidate_count"] == 7
    assert verification["no_progress_candidate_source"] == "last_apply"
    next_action = payload["next_safe_action"]
    assert next_action["action"] == "refresh_no_progress_nudge_dry_run"
    assert next_action["reason"] == "no-progress dry-run candidate summary is stale"
    assert next_action["user_message_allowed_after_review"] is False
    assert next_action["automatic_restart_allowed"] is False
    assert "refresh_no_progress_nudge_dry_run" in next_action["immediate_readonly_actions"]
    assert "restart_x-ui" in next_action["blocked_actions"]
    assert next_action["no_progress_dry_run_available"] is True
    assert next_action["no_progress_dry_run_fresh"] is False
    assert next_action["no_progress_dry_run_ready_for_apply"] is False
    assert next_action["no_progress_dry_run_valid_through_earliest_mutation"] is False


def test_vpn_status_json_requires_fresh_dry_run_before_user_nudge(
    tmp_path: Path,
) -> None:
    proc = _run_json(
        tmp_path,
        subscription_payload_status={
            "generated_at": "2026-06-05T14:28:51Z",
            "ok": True,
            "decision": "LIVE_SUBSCRIPTION_PAYLOAD_SAFE",
            "checked_subscription_count": 14,
            "candidate_subscription_count": 14,
            "ports": [443, 2083],
            "transport_counts": {"reality": 76},
            "failures": [],
            "expired_error_check": {
                "ok": True,
                "status": "safe",
                "checked_subscription_count": 13,
                "candidate_subscription_count": 13,
                "status_counts": {"403": 13},
                "max_profile_count": 0,
                "ports_seen": [],
                "failures": [],
                "raw_tokens_or_uris_printed": False,
            },
            "anti_dpi": {
                "status": "ready",
                "ready": True,
                "reality_only": True,
                "legacy_transports_absent": True,
                "checked_subscription_count": 14,
                "ready_subscription_count": 14,
                "primary_reality_443_ready_count": 14,
                "secondary_reality_port_ready_count": 14,
                "all_checked_have_primary_reality_443": True,
                "all_checked_have_secondary_reality_port": True,
                "recommended_port_order": [443, 2083],
                "blockers": [],
                "warnings": [],
                "raw_tokens_or_uris_printed": False,
                "raw_uuid_printed": False,
                "raw_host_printed": False,
            },
            "privacy": {
                "raw_tokens_printed": False,
                "raw_profile_uris_printed": False,
                "raw_uuid_printed": False,
                "raw_host_printed": False,
            },
        },
        subscription_payload_max_age_seconds=999999999,
        legacy_no_progress_nudge_status={
            "generated_at": "2026-06-05T14:28:51Z",
            "decision": "LEGACY_NO_PROGRESS_NUDGE_SENT",
            "mode": "apply",
            "active_user_count": 14,
            "progress_user_count": 7,
            "reply_user_count": 0,
            "no_progress_candidate_count": 7,
            "selected_user_count": 7,
            "sent_count": 7,
            "failed_count": 0,
            "blocked_count": 0,
            "privacy": {
                "raw_user_ids_printed": False,
                "raw_chat_ids_printed": False,
                "raw_tokens_printed": False,
                "raw_subscription_urls_printed": False,
                "raw_vpn_uris_printed": False,
                "raw_uuid_printed": False,
                "raw_ip_printed": False,
                "raw_telegram_handle_printed": False,
            },
        },
        legacy_no_progress_nudge_max_age_seconds=999999999,
        legacy_no_progress_nudge_cooldown_hours=0,
    )
    assert proc.returncode == 0, proc.stderr

    payload = json.loads(proc.stdout)
    next_action = payload["next_safe_action"]
    assert next_action["action"] == "refresh_no_progress_nudge_dry_run"
    assert next_action["reason"] == "fresh no-progress dry-run is required before user nudge"
    assert next_action["user_message_allowed_after_review"] is False
    assert next_action["no_progress_candidate_count"] == 7
    assert next_action["no_progress_dry_run_available"] is False
    assert next_action["no_progress_dry_run_fresh"] is False
    assert next_action["no_progress_dry_run_ready_for_apply"] is False
    assert next_action["no_progress_dry_run_valid_through_earliest_mutation"] is False
    assert "refresh_no_progress_nudge_dry_run" in next_action["immediate_readonly_actions"]


def test_vpn_status_json_requires_fresh_readonly_evidence_before_user_nudge(
    tmp_path: Path,
) -> None:
    now = datetime.now(UTC).replace(microsecond=0)
    fresh_at = (now - timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    old_send_at = (now - timedelta(hours=13)).isoformat().replace("+00:00", "Z")
    proc = _run_json(
        tmp_path,
        subscription_payload_status={
            "generated_at": fresh_at,
            "ok": True,
            "decision": "LIVE_SUBSCRIPTION_PAYLOAD_SAFE",
            "checked_subscription_count": 14,
            "candidate_subscription_count": 14,
            "ports": [443, 2083],
            "transport_counts": {"reality": 76},
            "failures": [],
            "expired_error_check": {
                "ok": True,
                "status": "safe",
                "checked_subscription_count": 13,
                "candidate_subscription_count": 13,
                "status_counts": {"403": 13},
                "max_profile_count": 0,
                "ports_seen": [],
                "failures": [],
                "raw_tokens_or_uris_printed": False,
            },
            "anti_dpi": {
                "status": "ready",
                "ready": True,
                "reality_only": True,
                "legacy_transports_absent": True,
                "checked_subscription_count": 14,
                "ready_subscription_count": 14,
                "primary_reality_443_ready_count": 14,
                "secondary_reality_port_ready_count": 14,
                "all_checked_have_primary_reality_443": True,
                "all_checked_have_secondary_reality_port": True,
                "recommended_port_order": [443, 2083],
                "blockers": [],
                "warnings": [],
                "raw_tokens_or_uris_printed": False,
                "raw_uuid_printed": False,
                "raw_host_printed": False,
            },
            "privacy": {
                "raw_tokens_printed": False,
                "raw_profile_uris_printed": False,
                "raw_uuid_printed": False,
                "raw_host_printed": False,
            },
        },
        subscription_payload_max_age_seconds=1800,
        legacy_no_progress_nudge_status={
            "generated_at": old_send_at,
            "decision": "LEGACY_NO_PROGRESS_NUDGE_SENT",
            "mode": "apply",
            "active_user_count": 14,
            "progress_user_count": 7,
            "reply_user_count": 0,
            "no_progress_candidate_count": 7,
            "selected_user_count": 7,
            "sent_count": 7,
            "failed_count": 0,
            "blocked_count": 0,
            "privacy": {
                "raw_user_ids_printed": False,
                "raw_chat_ids_printed": False,
                "raw_tokens_printed": False,
                "raw_subscription_urls_printed": False,
                "raw_vpn_uris_printed": False,
                "raw_uuid_printed": False,
                "raw_ip_printed": False,
                "raw_telegram_handle_printed": False,
            },
        },
        legacy_no_progress_nudge_dry_run_status={
            "generated_at": fresh_at,
            "decision": "LEGACY_NO_PROGRESS_NUDGE_DRY_RUN",
            "mode": "dry_run",
            "active_user_count": 14,
            "progress_user_count": 10,
            "reply_user_count": 0,
            "no_progress_candidate_count": 4,
            "selected_user_count": 0,
            "sent_count": 0,
            "failed_count": 0,
            "blocked_count": 0,
            "privacy": {
                "raw_user_ids_printed": False,
                "raw_chat_ids_printed": False,
                "raw_tokens_printed": False,
                "raw_subscription_urls_printed": False,
                "raw_vpn_uris_printed": False,
                "raw_uuid_printed": False,
                "raw_ip_printed": False,
                "raw_telegram_handle_printed": False,
            },
        },
        legacy_no_progress_nudge_max_age_seconds=999999999,
        legacy_no_progress_nudge_dry_run_max_age_seconds=1800,
        legacy_no_progress_nudge_cooldown_hours=12,
    )
    assert proc.returncode == 0, proc.stderr

    payload = json.loads(proc.stdout)
    next_action = payload["next_safe_action"]
    assert next_action["action"] == "refresh_readonly_evidence_before_user_nudge"
    assert next_action["reason"] == "fresh read-only evidence is required before user nudge"
    assert next_action["user_message_allowed_after_review"] is False
    assert "collect_transport_usage_evidence" in next_action["immediate_readonly_actions"]
    assert "collect_legacy_migration_progress" in next_action["immediate_readonly_actions"]
    assert "collect_legacy_migration_replies" in next_action["immediate_readonly_actions"]
    assert next_action["no_progress_candidate_count"] == 4
    assert next_action["no_progress_dry_run_ready_for_apply"] is True
    assert next_action["cooldown_active"] is False


def test_vpn_status_json_warns_when_dry_run_expires_before_cooldown(
    tmp_path: Path,
) -> None:
    now = datetime.now(UTC).replace(microsecond=0)
    last_send_at = (now - timedelta(hours=6)).isoformat().replace("+00:00", "Z")
    dry_run_at = (now - timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    proc = _run_json(
        tmp_path,
        subscription_payload_status={
            "generated_at": dry_run_at,
            "ok": True,
            "decision": "LIVE_SUBSCRIPTION_PAYLOAD_SAFE",
            "checked_subscription_count": 14,
            "candidate_subscription_count": 14,
            "ports": [443, 2083],
            "transport_counts": {"reality": 76},
            "failures": [],
            "expired_error_check": {
                "ok": True,
                "status": "safe",
                "checked_subscription_count": 13,
                "candidate_subscription_count": 13,
                "status_counts": {"403": 13},
                "max_profile_count": 0,
                "ports_seen": [],
                "failures": [],
                "raw_tokens_or_uris_printed": False,
            },
            "anti_dpi": {
                "status": "ready",
                "ready": True,
                "reality_only": True,
                "legacy_transports_absent": True,
                "checked_subscription_count": 14,
                "ready_subscription_count": 14,
                "primary_reality_443_ready_count": 14,
                "secondary_reality_port_ready_count": 14,
                "all_checked_have_primary_reality_443": True,
                "all_checked_have_secondary_reality_port": True,
                "recommended_port_order": [443, 2083],
                "blockers": [],
                "warnings": [],
                "raw_tokens_or_uris_printed": False,
                "raw_uuid_printed": False,
                "raw_host_printed": False,
            },
            "privacy": {
                "raw_tokens_printed": False,
                "raw_profile_uris_printed": False,
                "raw_uuid_printed": False,
                "raw_host_printed": False,
            },
        },
        subscription_payload_max_age_seconds=999999999,
        legacy_no_progress_nudge_status={
            "generated_at": last_send_at,
            "decision": "LEGACY_NO_PROGRESS_NUDGE_SENT",
            "mode": "apply",
            "active_user_count": 14,
            "progress_user_count": 7,
            "reply_user_count": 0,
            "no_progress_candidate_count": 7,
            "selected_user_count": 7,
            "sent_count": 7,
            "failed_count": 0,
            "blocked_count": 0,
            "privacy": {
                "raw_user_ids_printed": False,
                "raw_chat_ids_printed": False,
                "raw_tokens_printed": False,
                "raw_subscription_urls_printed": False,
                "raw_vpn_uris_printed": False,
                "raw_uuid_printed": False,
                "raw_ip_printed": False,
                "raw_telegram_handle_printed": False,
            },
        },
        legacy_no_progress_nudge_dry_run_status={
            "generated_at": dry_run_at,
            "decision": "LEGACY_NO_PROGRESS_NUDGE_DRY_RUN",
            "mode": "dry_run",
            "active_user_count": 14,
            "progress_user_count": 10,
            "reply_user_count": 0,
            "no_progress_candidate_count": 4,
            "selected_user_count": 0,
            "sent_count": 0,
            "failed_count": 0,
            "blocked_count": 0,
            "privacy": {
                "raw_user_ids_printed": False,
                "raw_chat_ids_printed": False,
                "raw_tokens_printed": False,
                "raw_subscription_urls_printed": False,
                "raw_vpn_uris_printed": False,
                "raw_uuid_printed": False,
                "raw_ip_printed": False,
                "raw_telegram_handle_printed": False,
            },
        },
        legacy_no_progress_nudge_max_age_seconds=999999999,
        legacy_no_progress_nudge_dry_run_max_age_seconds=1800,
        legacy_no_progress_nudge_cooldown_hours=12,
    )
    assert proc.returncode == 0, proc.stderr

    payload = json.loads(proc.stdout)
    next_action = payload["next_safe_action"]
    assert next_action["action"] == "wait_for_nudge_cooldown_and_collect_readonly_evidence"
    assert next_action["no_progress_dry_run_ready_for_apply"] is True
    assert next_action["no_progress_dry_run_valid_through_earliest_mutation"] is False
    assert next_action["deferred_readonly_actions"] == [
        "refresh_no_progress_nudge_dry_run_before_user_nudge"
    ]


def test_vpn_status_json_warns_when_subscription_payload_expires_before_cooldown(
    tmp_path: Path,
) -> None:
    now = datetime.now(UTC).replace(microsecond=0)
    last_send_at = (now - timedelta(hours=6)).isoformat().replace("+00:00", "Z")
    fresh_at = (now - timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    proc = _run_json(
        tmp_path,
        subscription_payload_status={
            "generated_at": fresh_at,
            "ok": True,
            "decision": "LIVE_SUBSCRIPTION_PAYLOAD_SAFE",
            "checked_subscription_count": 14,
            "candidate_subscription_count": 14,
            "ports": [443, 2083],
            "transport_counts": {"reality": 76},
            "failures": [],
            "expired_error_check": {
                "ok": True,
                "status": "safe",
                "checked_subscription_count": 13,
                "candidate_subscription_count": 13,
                "status_counts": {"403": 13},
                "max_profile_count": 0,
                "ports_seen": [],
                "failures": [],
                "raw_tokens_or_uris_printed": False,
            },
            "anti_dpi": {
                "status": "ready",
                "ready": True,
                "reality_only": True,
                "legacy_transports_absent": True,
                "checked_subscription_count": 14,
                "ready_subscription_count": 14,
                "primary_reality_443_ready_count": 14,
                "secondary_reality_port_ready_count": 14,
                "all_checked_have_primary_reality_443": True,
                "all_checked_have_secondary_reality_port": True,
                "recommended_port_order": [443, 2083],
                "blockers": [],
                "warnings": [],
                "raw_tokens_or_uris_printed": False,
                "raw_uuid_printed": False,
                "raw_host_printed": False,
            },
            "privacy": {
                "raw_tokens_printed": False,
                "raw_profile_uris_printed": False,
                "raw_uuid_printed": False,
                "raw_host_printed": False,
            },
        },
        subscription_payload_max_age_seconds=1800,
        legacy_no_progress_nudge_status={
            "generated_at": last_send_at,
            "decision": "LEGACY_NO_PROGRESS_NUDGE_SENT",
            "mode": "apply",
            "active_user_count": 14,
            "progress_user_count": 7,
            "reply_user_count": 0,
            "no_progress_candidate_count": 7,
            "selected_user_count": 7,
            "sent_count": 7,
            "failed_count": 0,
            "blocked_count": 0,
            "privacy": {
                "raw_user_ids_printed": False,
                "raw_chat_ids_printed": False,
                "raw_tokens_printed": False,
                "raw_subscription_urls_printed": False,
                "raw_vpn_uris_printed": False,
                "raw_uuid_printed": False,
                "raw_ip_printed": False,
                "raw_telegram_handle_printed": False,
            },
        },
        legacy_no_progress_nudge_dry_run_status={
            "generated_at": fresh_at,
            "decision": "LEGACY_NO_PROGRESS_NUDGE_DRY_RUN",
            "mode": "dry_run",
            "active_user_count": 14,
            "progress_user_count": 10,
            "reply_user_count": 0,
            "no_progress_candidate_count": 4,
            "selected_user_count": 0,
            "sent_count": 0,
            "failed_count": 0,
            "blocked_count": 0,
            "privacy": {
                "raw_user_ids_printed": False,
                "raw_chat_ids_printed": False,
                "raw_tokens_printed": False,
                "raw_subscription_urls_printed": False,
                "raw_vpn_uris_printed": False,
                "raw_uuid_printed": False,
                "raw_ip_printed": False,
                "raw_telegram_handle_printed": False,
            },
        },
        legacy_no_progress_nudge_max_age_seconds=999999999,
        legacy_no_progress_nudge_dry_run_max_age_seconds=999999999,
        legacy_no_progress_nudge_cooldown_hours=12,
    )
    assert proc.returncode == 0, proc.stderr

    payload = json.loads(proc.stdout)
    next_action = payload["next_safe_action"]
    assert next_action["action"] == "wait_for_nudge_cooldown_and_collect_readonly_evidence"
    assert next_action["subscription_payload_fresh"] is True
    assert next_action["subscription_payload_valid_through_earliest_mutation"] is False
    assert next_action["no_progress_dry_run_valid_through_earliest_mutation"] is True
    assert next_action["deferred_readonly_actions"] == [
        "refresh_subscription_payload_status_before_user_nudge"
    ]


def test_vpn_status_json_flags_unsafe_subscription_payload_without_restart(
    tmp_path: Path,
) -> None:
    proc = _run_json(
        tmp_path,
        subscription_payload_status={
            "generated_at": "2026-06-05T10:40:33Z",
            "ok": False,
            "decision": "LIVE_SUBSCRIPTION_PAYLOAD_UNSAFE",
            "checked_subscription_count": 3,
            "candidate_subscription_count": 3,
            "ports": [443, 8443],
            "transport_counts": {"reality": 1, "xhttp": 2},
            "failures": ["subscription_disallowed_transport"],
            "privacy": {
                "raw_tokens_printed": False,
                "raw_profile_uris_printed": False,
                "raw_uuid_printed": False,
                "raw_host_printed": False,
            },
        },
        subscription_payload_max_age_seconds=999999999,
    )
    assert proc.returncode == 0, proc.stderr

    payload = json.loads(proc.stdout)
    subscription = payload["subscription_payload"]
    assert subscription["status"] == "unsafe"
    assert subscription["operator_action"] == "fix_subscription_payload_before_user_rotation"
    assert "subscription_payload_disallowed_transports" in subscription["failures"]
    assert "subscription_payload_unexpected_ports" in subscription["failures"]
    assert "subscription_payload_anti_dpi_not_ready" in subscription["failures"]
    assert subscription["disallowed_transports"] == ["xhttp"]
    anti_dpi = payload["anti_dpi_readiness"]
    assert anti_dpi["status"] == "blocked"
    assert anti_dpi["distribution_ready"] is False
    assert "anti_dpi_subscription_not_reality_only" in anti_dpi["blockers"]
    assert payload["overall_status"] == "advisory"
    assert payload["recommended_action"] == "operator_review"
    assert payload["overall_operator_action"] == "fix_anti_dpi_subscription_or_privacy_before_rotation"
    assert payload["restart_recommended"] is False
    assert payload["restart_scope"] == "none"


def test_vpn_status_json_reports_external_client_evidence_blocker(tmp_path: Path) -> None:
    proc = _run_json(
        tmp_path,
        client_evidence_status={
            "generated_at": "2026-06-02T04:00:00Z",
            "decision": "VPN_PRODUCTION_CANDIDATE_GOAL_NOT_COMPLETE",
            "goal_complete": False,
            "requirements_passed": 5,
            "requirements_total": 6,
            "requirements": [
                {
                    "id": "ANTIBLOCK-CLIENTS-01",
                    "status": "blocked_external_evidence",
                    "ok": False,
                    "evidence": [
                        "missing_requirements=android_happ_or_hiddify, mobile_network, restricted_or_work_wifi",
                        "remote_request_ready=true",
                        "remote_request_contract_ready=true",
                        "remote_request_privacy_ok=true",
                        "remote_request_freshness_policy_ok=true",
                        "remote_request_record_commands_use_stdin=true",
                        "remote_request_validate_commands_no_write=true",
                        "remote_request_safe_reply_options_ok=true",
                        "remote_request_count=2",
                    ],
                    "next_step": "collect privacy-safe remote client replies",
                }
            ],
        },
        client_evidence_max_age_seconds=999999999,
        remote_request_packet=_ready_remote_request_packet(),
        remote_request_max_age_seconds=999999999,
    )
    assert proc.returncode == 0, proc.stderr

    payload = json.loads(proc.stdout)
    assert payload["overall_status"] == "ok"
    assert payload["recommended_action"] == "observe"
    assert payload["restart_recommended"] is False
    assert payload["restart_scope"] == "none"
    assert payload["server_operator_action"] == "observe_server"
    assert payload["overall_operator_action"] == "observe_server_collect_client_replies"
    assert payload["restart_guard"]["guard_status"] == "restart_blocked"
    assert payload["restart_guard"]["operator_rule"] == "do_not_restart"
    assert payload["restart_guard"]["blocked_reasons"] == [
        "transport_healthy",
        "external_client_evidence_pending",
    ]
    assert payload["restart_guard"]["external_client_evidence_pending"] is True
    assert payload["restart_guard"]["allowed_manual_restart_scopes"] == []
    client_evidence = payload["client_evidence"]
    assert client_evidence["blocked_requirement"] == "ANTIBLOCK-CLIENTS-01"
    assert client_evidence["fresh"] is True
    assert client_evidence["freshness_status"] == "fresh"
    assert client_evidence["refresh_required"] is False
    assert client_evidence["generated_at"] == "2026-06-02T04:00:00Z"
    assert client_evidence["stale_after"] is not None
    assert client_evidence["seconds_until_stale"] > 0
    assert client_evidence["goal_complete"] is False
    assert client_evidence["goal_decision"] == "VPN_PRODUCTION_CANDIDATE_GOAL_NOT_COMPLETE"
    assert client_evidence["missing_requirements"] == [
        "android_happ_or_hiddify",
        "mobile_network",
        "restricted_or_work_wifi",
    ]
    assert client_evidence["mutation_allowed"] is False
    assert client_evidence["next_step"] == "collect privacy-safe remote client replies"
    assert client_evidence["nl_mutation_allowed"] is False
    assert client_evidence["remote_request_count"] == 2
    packet = client_evidence["remote_request_packet"]
    packet_path = tmp_path / "remote-client-evidence-request.json"
    packet_bytes = packet_path.read_bytes()
    assert packet["source"] == str(packet_path)
    assert packet["source_sha256"] == hashlib.sha256(packet_bytes).hexdigest()
    assert packet["source_size_bytes"] == len(packet_bytes)
    assert packet["available"] is True
    assert packet["status"] == "ready"
    assert packet["packet_id"] == "nl-anti-block-remote-client-evidence-request-2026-06-02"
    assert packet["decision"] == "REMOTE_CLIENT_EVIDENCE_REQUEST_READY"
    assert packet["generated_at"] == "2026-06-02T04:00:00Z"
    assert packet["fresh"] is True
    assert packet["refresh_required"] is False
    assert packet["stale_after"] is not None
    assert packet["seconds_until_stale"] > 0
    assert packet["min_collection_window_seconds"] == 3600
    assert packet["expires_soon"] is False
    assert packet["request_count"] == 2
    assert packet["declared_request_count"] == 2
    assert packet["request_count_matches"] is True
    assert packet["privacy_ok"] is True
    assert packet["safe_reply_options_ok"] is True
    assert packet["request_shape_ok"] is True
    assert packet["tester_messages_safe"] is True
    assert packet["tester_messages_contract_ok"] is True
    assert packet["reply_record_commands_hash_guard_ok"] is True
    assert packet["reply_validate_commands_hash_guard_ok"] is True
    assert packet["reply_commands_hash_guard_ok"] is True
    assert packet["collection_ready"] is True
    assert packet["collection_blockers"] == []
    assert [row["request_id"] for row in packet["requests"]] == [
        "remote-client-evidence-1",
        "remote-client-evidence-2",
    ]
    assert all(row["reply_record_commands_hash_guard_ok"] for row in packet["requests"])
    assert all(row["reply_validate_commands_hash_guard_ok"] for row in packet["requests"])
    assert all(row["tester_message_safe"] for row in packet["requests"])
    assert all(row["tester_message_contract_ok"] for row in packet["requests"])
    assert packet["requests"][0]["tester_message"].startswith("Test remote-client-evidence-1")
    assert packet["requests"][1]["tester_message"].startswith("Test remote-client-evidence-2")
    assert client_evidence["remote_request_ready"] is True
    assert client_evidence["remote_request_contract_ready"] is True
    assert client_evidence["remote_request_privacy_ok"] is True
    assert client_evidence["remote_request_freshness_policy_ok"] is True
    assert client_evidence["remote_request_record_commands_use_stdin"] is True
    assert client_evidence["remote_request_validate_commands_no_write"] is True
    assert client_evidence["remote_request_safe_reply_options_ok"] is True
    assert client_evidence["safe_remote_request_collection_ready"] is True
    assert client_evidence["collection_blockers"] == []
    assert client_evidence["operator_action"] == "collect_remote_client_replies"
    assert client_evidence["requirements_passed"] == 5
    assert client_evidence["requirements_total"] == 6
    assert client_evidence["source"] == str(tmp_path / "client-evidence-status.json")
    assert client_evidence["status"] == "blocked_external_evidence"


def test_vpn_status_json_refuses_safe_collection_without_request_packet(tmp_path: Path) -> None:
    proc = _run_json(
        tmp_path,
        client_evidence_status={
            "generated_at": "2026-06-02T04:00:00Z",
            "decision": "VPN_PRODUCTION_CANDIDATE_GOAL_NOT_COMPLETE",
            "goal_complete": False,
            "requirements": [
                {
                    "id": "ANTIBLOCK-CLIENTS-01",
                    "status": "blocked_external_evidence",
                    "ok": False,
                    "evidence": [
                        "missing_requirements=mobile_network",
                        "remote_request_ready=true",
                        "remote_request_contract_ready=true",
                        "remote_request_privacy_ok=true",
                        "remote_request_freshness_policy_ok=true",
                        "remote_request_record_commands_use_stdin=true",
                        "remote_request_validate_commands_no_write=true",
                        "remote_request_safe_reply_options_ok=true",
                        "remote_request_count=2",
                    ],
                    "next_step": "collect privacy-safe remote client replies",
                }
            ],
        },
        client_evidence_max_age_seconds=999999999,
    )
    assert proc.returncode == 0, proc.stderr

    payload = json.loads(proc.stdout)
    client_evidence = payload["client_evidence"]
    assert client_evidence["remote_request_ready"] is True
    assert client_evidence["remote_request_packet"]["available"] is False
    assert client_evidence["remote_request_packet"]["collection_ready"] is False
    assert client_evidence["remote_request_packet"]["collection_blockers"] == [
        "request_packet_missing_or_unreadable"
    ]
    assert client_evidence["safe_remote_request_collection_ready"] is False
    assert client_evidence["collection_blockers"] == ["remote_request_packet_not_ready"]
    assert client_evidence["operator_action"] == "refresh_remote_request_packet"
    assert payload["overall_operator_action"] == "observe_server_refresh_remote_request_packet"


def test_vpn_status_json_refuses_packet_that_is_expiring_too_soon(
    tmp_path: Path,
) -> None:
    proc = _run_json(
        tmp_path,
        client_evidence_status={
            "generated_at": "2026-06-02T04:00:00Z",
            "decision": "VPN_PRODUCTION_CANDIDATE_GOAL_NOT_COMPLETE",
            "goal_complete": False,
            "requirements": [
                {
                    "id": "ANTIBLOCK-CLIENTS-01",
                    "status": "blocked_external_evidence",
                    "ok": False,
                    "evidence": [
                        "missing_requirements=mobile_network",
                        "remote_request_ready=true",
                        "remote_request_contract_ready=true",
                        "remote_request_privacy_ok=true",
                        "remote_request_freshness_policy_ok=true",
                        "remote_request_record_commands_use_stdin=true",
                        "remote_request_validate_commands_no_write=true",
                        "remote_request_safe_reply_options_ok=true",
                        "remote_request_count=2",
                    ],
                    "next_step": "collect privacy-safe remote client replies",
                }
            ],
        },
        client_evidence_max_age_seconds=999999999,
        remote_request_packet=_ready_remote_request_packet(),
        remote_request_max_age_seconds=999999999,
        remote_request_min_collection_window_seconds=999999999,
    )
    assert proc.returncode == 0, proc.stderr

    payload = json.loads(proc.stdout)
    client_evidence = payload["client_evidence"]
    packet = client_evidence["remote_request_packet"]
    assert packet["fresh"] is True
    assert packet["expires_soon"] is True
    assert packet["collection_ready"] is False
    assert packet["collection_blockers"] == ["request_packet_expiring_soon"]
    assert client_evidence["safe_remote_request_collection_ready"] is False
    assert client_evidence["collection_blockers"] == ["remote_request_packet_not_ready"]
    assert client_evidence["operator_action"] == "refresh_remote_request_packet"
    assert payload["overall_operator_action"] == "observe_server_refresh_remote_request_packet"


def test_vpn_status_json_refuses_packet_without_reply_command_hash_guard(
    tmp_path: Path,
) -> None:
    packet = _ready_remote_request_packet()
    packet["requests"][0][
        "operator_reply_record_pass_command"
    ] = (
        "printf '%s\\n' \"pass connected\" | "
        "python3 services/nl-server/ghost-access/record_remote_client_evidence_reply.py "
        "--write --record-matrix --refresh-artifacts "
        "--request-id remote-client-evidence-1 --reply-stdin --json"
    )
    proc = _run_json(
        tmp_path,
        client_evidence_status={
            "generated_at": "2026-06-02T04:00:00Z",
            "decision": "VPN_PRODUCTION_CANDIDATE_GOAL_NOT_COMPLETE",
            "goal_complete": False,
            "requirements": [
                {
                    "id": "ANTIBLOCK-CLIENTS-01",
                    "status": "blocked_external_evidence",
                    "ok": False,
                    "evidence": [
                        "missing_requirements=mobile_network",
                        "remote_request_ready=true",
                        "remote_request_contract_ready=true",
                        "remote_request_privacy_ok=true",
                        "remote_request_freshness_policy_ok=true",
                        "remote_request_record_commands_use_stdin=true",
                        "remote_request_validate_commands_no_write=true",
                        "remote_request_safe_reply_options_ok=true",
                        "remote_request_count=2",
                    ],
                    "next_step": "collect privacy-safe remote client replies",
                }
            ],
        },
        client_evidence_max_age_seconds=999999999,
        remote_request_packet=packet,
        remote_request_max_age_seconds=999999999,
    )
    assert proc.returncode == 0, proc.stderr

    payload = json.loads(proc.stdout)
    client_evidence = payload["client_evidence"]
    packet_summary = client_evidence["remote_request_packet"]
    assert packet_summary["available"] is True
    assert packet_summary["reply_record_commands_hash_guard_ok"] is False
    assert packet_summary["reply_validate_commands_hash_guard_ok"] is True
    assert packet_summary["reply_commands_hash_guard_ok"] is False
    assert packet_summary["requests"][0]["reply_record_commands_hash_guard_ok"] is False
    assert packet_summary["collection_ready"] is False
    assert packet_summary["collection_blockers"] == [
        "reply_record_commands_missing_packet_hash_guard"
    ]
    assert client_evidence["safe_remote_request_collection_ready"] is False
    assert client_evidence["collection_blockers"] == ["remote_request_packet_not_ready"]
    assert client_evidence["operator_action"] == "refresh_remote_request_packet"


def test_vpn_status_json_refuses_packet_with_incomplete_safe_reply_options(
    tmp_path: Path,
) -> None:
    packet = _ready_remote_request_packet()
    packet["requests"][0]["safe_reply_options"] = ["pass connected"]
    proc = _run_json(
        tmp_path,
        client_evidence_status={
            "generated_at": "2026-06-02T04:00:00Z",
            "decision": "VPN_PRODUCTION_CANDIDATE_GOAL_NOT_COMPLETE",
            "goal_complete": False,
            "requirements": [
                {
                    "id": "ANTIBLOCK-CLIENTS-01",
                    "status": "blocked_external_evidence",
                    "ok": False,
                    "evidence": [
                        "missing_requirements=mobile_network",
                        "remote_request_ready=true",
                        "remote_request_contract_ready=true",
                        "remote_request_privacy_ok=true",
                        "remote_request_freshness_policy_ok=true",
                        "remote_request_record_commands_use_stdin=true",
                        "remote_request_validate_commands_no_write=true",
                        "remote_request_safe_reply_options_ok=true",
                        "remote_request_count=2",
                    ],
                    "next_step": "collect privacy-safe remote client replies",
                }
            ],
        },
        client_evidence_max_age_seconds=999999999,
        remote_request_packet=packet,
        remote_request_max_age_seconds=999999999,
    )
    assert proc.returncode == 0, proc.stderr

    payload = json.loads(proc.stdout)
    client_evidence = payload["client_evidence"]
    packet_summary = client_evidence["remote_request_packet"]
    assert packet_summary["available"] is True
    assert packet_summary["safe_reply_options_ok"] is False
    assert packet_summary["collection_ready"] is False
    assert packet_summary["collection_blockers"] == [
        "safe_reply_options_incomplete_or_unsafe"
    ]
    assert client_evidence["safe_remote_request_collection_ready"] is False
    assert client_evidence["collection_blockers"] == ["remote_request_packet_not_ready"]
    assert client_evidence["operator_action"] == "refresh_remote_request_packet"


def test_vpn_status_json_refuses_packet_with_missing_or_unsafe_tester_message(
    tmp_path: Path,
) -> None:
    packet = _ready_remote_request_packet()
    packet["requests"][0]["tester_message"] = ""
    packet["requests"][1]["tester_message"] = (
        "Test remote-client-evidence-2: send result to https://example.test"
    )
    proc = _run_json(
        tmp_path,
        client_evidence_status={
            "generated_at": "2026-06-02T04:00:00Z",
            "decision": "VPN_PRODUCTION_CANDIDATE_GOAL_NOT_COMPLETE",
            "goal_complete": False,
            "requirements": [
                {
                    "id": "ANTIBLOCK-CLIENTS-01",
                    "status": "blocked_external_evidence",
                    "ok": False,
                    "evidence": [
                        "missing_requirements=mobile_network",
                        "remote_request_ready=true",
                        "remote_request_contract_ready=true",
                        "remote_request_privacy_ok=true",
                        "remote_request_freshness_policy_ok=true",
                        "remote_request_record_commands_use_stdin=true",
                        "remote_request_validate_commands_no_write=true",
                        "remote_request_safe_reply_options_ok=true",
                        "remote_request_count=2",
                    ],
                    "next_step": "collect privacy-safe remote client replies",
                }
            ],
        },
        client_evidence_max_age_seconds=999999999,
        remote_request_packet=packet,
        remote_request_max_age_seconds=999999999,
    )
    assert proc.returncode == 0, proc.stderr

    payload = json.loads(proc.stdout)
    client_evidence = payload["client_evidence"]
    packet_summary = client_evidence["remote_request_packet"]
    assert packet_summary["available"] is True
    assert packet_summary["tester_messages_safe"] is False
    assert packet_summary["requests"][0]["tester_message_safe"] is False
    assert packet_summary["requests"][0]["tester_message"] is None
    assert packet_summary["requests"][1]["tester_message_safe"] is False
    assert packet_summary["requests"][1]["tester_message"] is None
    assert packet_summary["collection_ready"] is False
    assert packet_summary["collection_blockers"] == [
        "tester_messages_missing_or_unsafe"
    ]
    assert client_evidence["safe_remote_request_collection_ready"] is False
    assert client_evidence["collection_blockers"] == ["remote_request_packet_not_ready"]
    assert client_evidence["operator_action"] == "refresh_remote_request_packet"


def test_vpn_status_json_refuses_packet_with_incomplete_tester_message_contract(
    tmp_path: Path,
) -> None:
    packet = _ready_remote_request_packet()
    packet["requests"][0]["tester_message"] = (
        "Test remote-client-evidence-1: use Happ on mobile data. "
        "Reply with pass connected."
    )
    proc = _run_json(
        tmp_path,
        client_evidence_status={
            "generated_at": "2026-06-02T04:00:00Z",
            "decision": "VPN_PRODUCTION_CANDIDATE_GOAL_NOT_COMPLETE",
            "goal_complete": False,
            "requirements": [
                {
                    "id": "ANTIBLOCK-CLIENTS-01",
                    "status": "blocked_external_evidence",
                    "ok": False,
                    "evidence": [
                        "missing_requirements=mobile_network",
                        "remote_request_ready=true",
                        "remote_request_contract_ready=true",
                        "remote_request_privacy_ok=true",
                        "remote_request_freshness_policy_ok=true",
                        "remote_request_record_commands_use_stdin=true",
                        "remote_request_validate_commands_no_write=true",
                        "remote_request_safe_reply_options_ok=true",
                        "remote_request_count=2",
                    ],
                    "next_step": "collect privacy-safe remote client replies",
                }
            ],
        },
        client_evidence_max_age_seconds=999999999,
        remote_request_packet=packet,
        remote_request_max_age_seconds=999999999,
    )
    assert proc.returncode == 0, proc.stderr

    payload = json.loads(proc.stdout)
    client_evidence = payload["client_evidence"]
    packet_summary = client_evidence["remote_request_packet"]
    assert packet_summary["available"] is True
    assert packet_summary["tester_messages_safe"] is True
    assert packet_summary["tester_messages_contract_ok"] is False
    assert packet_summary["requests"][0]["tester_message_safe"] is True
    assert packet_summary["requests"][0]["tester_message_contract_ok"] is False
    assert packet_summary["requests"][0]["tester_message"].startswith(
        "Test remote-client-evidence-1"
    )
    assert packet_summary["requests"][1]["tester_message_contract_ok"] is True
    assert packet_summary["collection_ready"] is False
    assert packet_summary["collection_blockers"] == [
        "tester_messages_contract_incomplete"
    ]
    assert client_evidence["safe_remote_request_collection_ready"] is False
    assert client_evidence["collection_blockers"] == ["remote_request_packet_not_ready"]
    assert client_evidence["operator_action"] == "refresh_remote_request_packet"


def test_vpn_status_json_tolerates_malformed_client_evidence_count(tmp_path: Path) -> None:
    proc = _run_json(
        tmp_path,
        client_evidence_status={
            "generated_at": "2026-06-02T04:00:00Z",
            "decision": "VPN_PRODUCTION_CANDIDATE_GOAL_NOT_COMPLETE",
            "goal_complete": False,
            "requirements": [
                {
                    "id": "ANTIBLOCK-CLIENTS-01",
                    "status": "blocked_external_evidence",
                    "ok": False,
                    "evidence": [
                        "missing_requirements=mobile_network",
                        "remote_request_ready=true",
                        "remote_request_count=not-a-number",
                    ],
                    "next_step": "collect privacy-safe remote client replies",
                }
            ],
        },
        client_evidence_max_age_seconds=999999999,
    )
    assert proc.returncode == 0, proc.stderr

    payload = json.loads(proc.stdout)
    assert payload["overall_status"] == "ok"
    assert payload["client_evidence"]["status"] == "blocked_external_evidence"
    assert payload["client_evidence"]["remote_request_ready"] is True
    assert payload["client_evidence"]["remote_request_count"] == 0
    assert payload["client_evidence"]["safe_remote_request_collection_ready"] is False
    assert "remote_request_count_zero" in payload["client_evidence"]["collection_blockers"]
    assert "remote_request_packet_not_ready" in payload["client_evidence"]["collection_blockers"]
    assert payload["client_evidence"]["operator_action"] == "refresh_remote_request_packet"
    assert payload["client_evidence"]["missing_requirements"] == ["mobile_network"]


def test_vpn_status_json_marks_stale_client_evidence_without_failing_server_health(
    tmp_path: Path,
) -> None:
    proc = _run_json(
        tmp_path,
        client_evidence_status={
            "generated_at": "2026-01-01T00:00:00Z",
            "decision": "VPN_PRODUCTION_CANDIDATE_GOAL_NOT_COMPLETE",
            "goal_complete": False,
            "requirements": [
                {
                    "id": "ANTIBLOCK-CLIENTS-01",
                    "status": "blocked_external_evidence",
                    "ok": False,
                    "evidence": [
                        "missing_requirements=mobile_network",
                        "remote_request_ready=true",
                        "remote_request_contract_ready=true",
                        "remote_request_privacy_ok=true",
                        "remote_request_freshness_policy_ok=true",
                        "remote_request_record_commands_use_stdin=true",
                        "remote_request_validate_commands_no_write=true",
                        "remote_request_safe_reply_options_ok=true",
                        "remote_request_count=2",
                    ],
                    "next_step": "refresh client evidence before acting",
                }
            ],
        },
        client_evidence_max_age_seconds=1,
    )
    assert proc.returncode == 0, proc.stderr

    payload = json.loads(proc.stdout)
    assert payload["overall_status"] == "ok"
    assert payload["client_evidence"]["status"] == "blocked_external_evidence"
    assert payload["client_evidence"]["fresh"] is False
    assert payload["client_evidence"]["freshness_status"] == "stale"
    assert payload["client_evidence"]["refresh_required"] is True
    assert payload["client_evidence"]["stale_after"] == "2026-01-01T00:00:01Z"
    assert payload["client_evidence"]["seconds_until_stale"] == 0
    assert payload["client_evidence"]["remote_request_count"] == 2
    assert payload["client_evidence"]["safe_remote_request_collection_ready"] is False
    assert "client_evidence_not_fresh" in payload["client_evidence"]["collection_blockers"]
    assert payload["client_evidence"]["operator_action"] == "refresh_client_evidence_status"
    assert payload["client_evidence"]["next_step"] == "refresh client evidence before acting"


def test_vpn_status_json_blocks_non_distributable_remote_request_profile(
    tmp_path: Path,
) -> None:
    packet = _ready_remote_request_packet()
    packet["requests"][0]["transport"] = "xhttp"
    packet["requests"][0]["port"] = 8443
    packet["requests"][0]["tester_message"] = (
        "Test remote-client-evidence-1: use Happ or Hiddify on mobile data, "
        "not Wi-Fi. Select the Ghost Access XHTTP fallback on port 8443. "
        "Reply only with: pass connected, fail timeout, fail import, or "
        "fail no-internet. Do not send profile links, subscription links, "
        "QR codes, UUIDs, IP addresses, usernames, phone numbers, handles, "
        "screenshots, or logs."
    )
    proc = _run_json(
        tmp_path,
        client_evidence_status={
            "generated_at": "2026-06-02T04:00:00Z",
            "decision": "VPN_PRODUCTION_CANDIDATE_GOAL_NOT_COMPLETE",
            "goal_complete": False,
            "requirements": [
                {
                    "id": "ANTIBLOCK-CLIENTS-01",
                    "status": "blocked_external_evidence",
                    "ok": False,
                    "evidence": [
                        "missing_requirements=mobile_network",
                        "remote_request_ready=true",
                        "remote_request_contract_ready=true",
                        "remote_request_privacy_ok=true",
                        "remote_request_freshness_policy_ok=true",
                        "remote_request_record_commands_use_stdin=true",
                        "remote_request_validate_commands_no_write=true",
                        "remote_request_safe_reply_options_ok=true",
                        "remote_request_count=2",
                    ],
                    "next_step": "collect privacy-safe remote client replies",
                }
            ],
        },
        client_evidence_max_age_seconds=999999999,
        remote_request_packet=packet,
        remote_request_max_age_seconds=999999999,
    )
    assert proc.returncode == 0, proc.stderr

    payload = json.loads(proc.stdout)
    packet_summary = payload["client_evidence"]["remote_request_packet"]
    assert packet_summary["expected_transport"] == "reality"
    assert packet_summary["expected_port"] == 443
    assert packet_summary["production_profile_ok"] is False
    assert packet_summary["requests"][0]["production_profile_ok"] is False
    assert packet_summary["requests"][1]["production_profile_ok"] is True
    assert packet_summary["collection_ready"] is False
    assert packet_summary["collection_blockers"] == ["request_profile_not_distributable"]
    assert payload["client_evidence"]["safe_remote_request_collection_ready"] is False
    assert payload["client_evidence"]["collection_blockers"] == ["remote_request_packet_not_ready"]
    assert payload["client_evidence"]["operator_action"] == "refresh_remote_request_packet"


def test_vpn_status_json_route_loop_is_local_client_failure(tmp_path: Path) -> None:
    proc = _run_json(tmp_path, route_loop=True)
    assert proc.returncode == 1

    payload = json.loads(proc.stdout)
    assert payload["overall_status"] == "critical"
    assert payload["failure_domain"] == "local_client"
    assert payload["recommended_action"] == "local_soft_heal"
    assert payload["restart_recommended"] is False
    assert payload["restart_scope"] == "none"
    assert payload["server_operator_action"] == "local_soft_heal"
    assert payload["overall_operator_action"] == "local_soft_heal_before_client_evidence"
    assert payload["restart_guard"]["guard_status"] == "restart_blocked"
    assert payload["restart_guard"]["operator_rule"] == "local_soft_heal_without_restart"
    assert payload["restart_guard"]["blocked_reasons"] == ["restart_not_proven_necessary"]
    assert payload["restart_guard"]["allowed_manual_restart_scopes"] == []
    assert any("Route loop risk" in problem for problem in payload["problems"])


def test_vpn_status_json_recommends_scoped_restart_only_when_xray_missing(
    tmp_path: Path,
) -> None:
    proc = _run_json(tmp_path, xray_running=False)
    assert proc.returncode == 1

    payload = json.loads(proc.stdout)
    assert payload["overall_status"] == "critical"
    assert payload["failure_domain"] == "local_client"
    assert payload["recommended_action"] == "local_soft_heal"
    assert payload["automatic_restart_allowed"] is False
    assert payload["restart_recommended"] is True
    assert payload["restart_scope"] == "xray"
    assert payload["restart_reason"] == "xray process is missing"
    assert payload["overall_operator_action"] == "local_soft_heal_before_client_evidence"
    assert payload["restart_guard"]["guard_status"] == "manual_scoped_restart_allowed"
    assert payload["restart_guard"]["operator_rule"] == "manual_scoped_restart_only"
    assert payload["restart_guard"]["allowed_manual_restart_scopes"] == ["xray"]
    assert payload["restart_guard"]["blocked_restart_scopes"] == [
        "full_server",
        "nl",
        "spb",
        "x-ui",
    ]
    assert payload["restart_guard"]["blocked_reasons"] == []
    assert payload["restart_guard"]["requires_explicit_operator_action"] is True
    assert any("xray not running" in problem.lower() for problem in payload["problems"])


def test_vpn_status_json_node_inactive_is_advisory_when_watchdog_active(
    tmp_path: Path,
) -> None:
    proc = _run_json(tmp_path, node_active=False, watchdog_active=True)
    assert proc.returncode == 0, proc.stderr

    payload = json.loads(proc.stdout)
    assert payload["overall_status"] == "advisory"
    assert payload["transport_status"] == "advisory"
    assert payload["failure_domain"] == "local_client"
    assert payload["recommended_action"] == "observe"
    assert payload["problems"] == []
    assert any("x0tta-node.service not active" in warning for warning in payload["warnings_detail"])
