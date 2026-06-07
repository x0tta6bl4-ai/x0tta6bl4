#!/bin/bash
# VPN status dashboard: connections, proxy health, packet loss
VPN_SERVER="${VPN_SERVER:-89.125.1.107}"
VPN_PORT="${VPN_PORT:-443}"
SOCKS_HOST="${VPN_SOCKS_HOST:-127.0.0.1}"
SOCKS_PORT_SOURCE="env"
BOOT_VALIDATION_RESULT="${VPN_BOOT_VALIDATE_RESULT_FILE:-/var/log/x0tta6bl4/vpn_boot_validation.last}"
SKIP_BOOT_VALIDATION="${VPN_STATUS_SKIP_BOOT_VALIDATION:-0}"
STRICT_CHECK=0
NO_COLOR=0
JSON_MODE=0

for arg in "$@"; do
    case "$arg" in
        --check)
            STRICT_CHECK=1
            NO_COLOR=1
            ;;
        --json)
            JSON_MODE=1
            NO_COLOR=1
            ;;
        --no-color)
            NO_COLOR=1
            ;;
        -h|--help)
            echo "Usage: $0 [--check] [--json] [--no-color]"
            echo "  --check     reproducible health-check mode; exits 1 on hard failures"
            echo "  --json      emit machine-readable state contract JSON; exits 1 on hard failures"
            echo "  --no-color  disable ANSI color output"
            exit 0
            ;;
        *)
            echo "Unknown argument: $arg" >&2
            exit 2
            ;;
    esac
done

detect_socks_port() {
    VPN_SOCKS_HOST="$SOCKS_HOST" python3 - <<'PY'
import os
import socket
import sys

host = os.environ.get("VPN_SOCKS_HOST", "127.0.0.1")
ports = []
for value in (
    os.environ.get("VPN_SOCKS_PORT"),
    os.environ.get("SOCKS_PORT"),
    os.environ.get("VPN_SOCKS_PORT_CANDIDATES", "10818,10918,10808,10809,10924,40467,1080"),
):
    if not value:
        continue
    for raw in value.replace(";", ",").split(","):
        raw = raw.strip()
        if not raw:
            continue
        try:
            port = int(raw)
        except ValueError:
            continue
        if 0 < port < 65536 and port not in ports:
            ports.append(port)

for port in ports:
    try:
        with socket.create_connection((host, port), timeout=1.0) as s:
            s.send(b"\x05\x01\x00")
            if s.recv(2) == b"\x05\x00":
                print(port)
                sys.exit(0)
    except OSError:
        pass

sys.exit(1)
PY
}

if [ -n "${VPN_SOCKS_PORT:-}" ]; then
    SOCKS_PORT="$VPN_SOCKS_PORT"
else
    SOCKS_PORT_SOURCE="auto"
    SOCKS_PORT="$(detect_socks_port 2>/dev/null || echo 10918)"
fi

if [ "$JSON_MODE" -eq 1 ]; then
    CHILD_OUTPUT="$(VPN_STATUS_JSON_CHILD=1 "$0" --check --no-color 2>&1)"
    CHILD_STATUS=$?
    VPN_STATUS_OUTPUT="$CHILD_OUTPUT" VPN_STATUS_EXIT_CODE="$CHILD_STATUS" python3 - <<'PY'
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

text = os.environ.get("VPN_STATUS_OUTPUT", "")
exit_code = int(os.environ.get("VPN_STATUS_EXIT_CODE", "0") or "0")
lines = [line.rstrip() for line in text.splitlines()]

result_line = next((line for line in reversed(lines) if line.startswith("Result: ")), "")
failures = 0
warnings = 0
raw_result = "UNKNOWN"
match = re.search(r"Result:\s+(PASS|FAIL)(?:\s+\(failures=(\d+)\s+warnings=(\d+)\)|\s+\(warnings=(\d+)\))", result_line)
if match:
    raw_result = match.group(1)
    if raw_result == "FAIL":
        failures = int(match.group(2) or 0)
        warnings = int(match.group(3) or 0)
    else:
        warnings = int(match.group(4) or 0)
elif exit_code:
    raw_result = "FAIL"
    failures = 1

warning_lines = [line.strip() for line in lines if "⚠" in line]
problem_lines = [line.strip() for line in lines if "✗" in line]
evidence_lines = [line.strip() for line in lines if "✓" in line]

def safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

def bool_from_text(value):
    return str(value).strip().lower() == "true"

def parse_utc_datetime(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)

def freshness_payload(value, max_age_seconds):
    parsed = parse_utc_datetime(value)
    if parsed is None:
        return {
            "generated_at": value if isinstance(value, str) and value else None,
            "age_seconds": None,
            "max_age_seconds": max_age_seconds,
            "stale_after": None,
            "seconds_until_stale": None,
            "fresh": False,
            "freshness_status": "missing_or_invalid",
            "refresh_required": True,
        }
    age_seconds = int((datetime.now(timezone.utc) - parsed).total_seconds())
    stale_after = parsed.timestamp() + max_age_seconds
    stale_after_iso = datetime.fromtimestamp(stale_after, timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )
    if age_seconds < 0:
        freshness_status = "future"
        seconds_until_stale = None
    elif age_seconds <= max_age_seconds:
        freshness_status = "fresh"
        seconds_until_stale = max_age_seconds - age_seconds
    else:
        freshness_status = "stale"
        seconds_until_stale = 0
    return {
        "generated_at": parsed.isoformat().replace("+00:00", "Z"),
        "age_seconds": age_seconds,
        "max_age_seconds": max_age_seconds,
        "stale_after": stale_after_iso,
        "seconds_until_stale": seconds_until_stale,
        "fresh": freshness_status == "fresh",
        "freshness_status": freshness_status,
        "refresh_required": freshness_status != "fresh",
    }

def contains_sensitive_request_text(value):
    if not isinstance(value, str) or not value.strip():
        return True
    patterns = (
        r"\b(?:vless|vmess|trojan|ss)://",
        r"/sub/[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]{8,}",
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b",
        r"\bhttps?://",
        r"@[A-Za-z0-9_]{4,}",
        r"\+\d[\d .()_-]{8,}\d\b",
    )
    return any(re.search(pattern, value, re.IGNORECASE) for pattern in patterns)

def tester_message_contract_is_ok(value, allowed_replies):
    if contains_sensitive_request_text(value):
        return False
    text = " ".join(value.lower().split())
    required_phrases = (
        "reply only with",
        "do not send",
        "profile links",
        "subscription links",
        "uuid",
        "ip address",
        "screenshots",
        "logs",
    )
    return all(reply in text for reply in allowed_replies) and all(
        phrase in text for phrase in required_phrases
    )

def evidence_freshness(value):
    max_age_seconds = safe_int(os.environ.get("VPN_CLIENT_EVIDENCE_MAX_AGE_SECONDS"), 86400)
    return freshness_payload(value, max_age_seconds)

def read_remote_request_packet_summary() -> dict:
    path = Path(
        os.environ.get(
            "VPN_REMOTE_CLIENT_EVIDENCE_REQUEST_FILE",
            "/mnt/projects/nl-diagnostics/nl-anti-block-remote-client-evidence-request-2026-06-02.json",
        )
    )
    max_age_seconds = safe_int(
        os.environ.get("VPN_REMOTE_CLIENT_EVIDENCE_REQUEST_MAX_AGE_SECONDS"),
        86400,
    )
    min_collection_window_seconds = safe_int(
        os.environ.get("VPN_REMOTE_CLIENT_EVIDENCE_MIN_COLLECTION_WINDOW_SECONDS"),
        3600,
    )
    base = {
        "source": str(path),
        "source_sha256": None,
        "source_size_bytes": 0,
        "available": False,
        "status": "missing_or_unreadable",
        "packet_id": None,
        "decision": "unknown",
        "generated_at": None,
        "age_seconds": None,
        "max_age_seconds": max_age_seconds,
        "stale_after": None,
        "seconds_until_stale": None,
        "min_collection_window_seconds": min_collection_window_seconds,
        "expires_soon": False,
        "fresh": False,
        "freshness_status": "missing",
        "refresh_required": True,
        "request_count": 0,
        "declared_request_count": 0,
        "request_count_matches": False,
        "minimum_reports_required": None,
        "missing_requirements": [],
        "privacy_ok": False,
        "safe_reply_options_ok": False,
        "request_shape_ok": False,
        "production_profile_ok": False,
        "tester_messages_safe": False,
        "tester_messages_contract_ok": False,
        "reply_record_commands_hash_guard_ok": False,
        "reply_validate_commands_hash_guard_ok": False,
        "reply_commands_hash_guard_ok": False,
        "collection_ready": False,
        "collection_blockers": ["request_packet_missing_or_unreadable"],
        "requests": [],
    }
    try:
        raw_packet = path.read_bytes()
        payload = json.loads(raw_packet.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return base
    if not isinstance(payload, dict):
        return base

    requests = []
    allowed_replies = {"pass connected", "fail timeout", "fail import", "fail no-internet"}
    safe_reply_options_ok = True
    request_shape_ok = True
    production_profile_ok = True
    tester_messages_safe = True
    tester_messages_contract_ok = True
    reply_record_commands_hash_guard_ok = True
    reply_validate_commands_hash_guard_ok = True
    expected_transport = os.environ.get("VPN_DISTRIBUTABLE_TRANSPORT", "reality").strip().lower()
    expected_port = safe_int(os.environ.get("VPN_DISTRIBUTABLE_PORT"), 443)
    for row in payload.get("requests") or []:
        if not isinstance(row, dict):
            request_shape_ok = False
            production_profile_ok = False
            tester_messages_safe = False
            tester_messages_contract_ok = False
            reply_record_commands_hash_guard_ok = False
            reply_validate_commands_hash_guard_ok = False
            continue
        request_id = str(row.get("request_id") or "")
        client = str(row.get("client") or "")
        network_type = str(row.get("network_type") or "")
        transport = str(row.get("transport") or "").strip().lower()
        port = row.get("port") if isinstance(row.get("port"), int) else None
        request_production_profile_ok = transport == expected_transport and port == expected_port
        if not request_production_profile_ok:
            production_profile_ok = False
        covers_requirements = [
            str(item)
            for item in (row.get("covers_requirements") or [])
            if isinstance(item, str)
        ]
        tester_message = str(row.get("tester_message") or "").strip()
        tester_message_safe = not contains_sensitive_request_text(tester_message)
        tester_message_contract = tester_message_contract_is_ok(
            tester_message,
            allowed_replies,
        )
        options = [
            str(option)
            for option in (row.get("safe_reply_options") or [])
            if isinstance(option, str)
        ]
        if set(options) != allowed_replies:
            safe_reply_options_ok = False
        if not request_id or not client or not network_type or not transport or port is None:
            request_shape_ok = False
        if not covers_requirements:
            request_shape_ok = False
        if not tester_message_safe:
            tester_messages_safe = False
        if not tester_message_contract:
            tester_messages_contract_ok = False
        record_commands = [
            str(row.get("operator_reply_record_pass_command") or ""),
            str(row.get("operator_reply_record_fail_command") or ""),
        ]
        validate_commands = [
            str(row.get("operator_reply_validate_pass_command") or ""),
            str(row.get("operator_reply_validate_fail_command") or ""),
        ]
        record_hash_guard_ok = all(
            "--expect-request-packet-sha256" in command
            and "sha256sum" in command
            and "--reply-stdin" in command
            for command in record_commands
        )
        validate_hash_guard_ok = all(
            "--expect-request-packet-sha256" in command
            and "sha256sum" in command
            and "--reply-stdin" in command
            and "--write" not in command
            and "--record-matrix" not in command
            and "--refresh-artifacts" not in command
            for command in validate_commands
        )
        if not record_hash_guard_ok:
            reply_record_commands_hash_guard_ok = False
        if not validate_hash_guard_ok:
            reply_validate_commands_hash_guard_ok = False
        requests.append(
            {
                "request_id": request_id,
                "client": client,
                "network_type": network_type,
                "transport": transport,
                "port": port,
                "production_profile_ok": request_production_profile_ok,
                "covers_requirements": covers_requirements,
                "tester_message": tester_message if tester_message_safe else None,
                "tester_message_safe": tester_message_safe,
                "tester_message_contract_ok": tester_message_contract,
                "safe_reply_options": options,
                "reply_record_commands_hash_guard_ok": record_hash_guard_ok,
                "reply_validate_commands_hash_guard_ok": validate_hash_guard_ok,
            }
        )

    if not requests:
        safe_reply_options_ok = False
        request_shape_ok = False
        production_profile_ok = False
        tester_messages_safe = False
        tester_messages_contract_ok = False
        reply_record_commands_hash_guard_ok = False
        reply_validate_commands_hash_guard_ok = False
    declared_request_count = safe_int(payload.get("request_count"), len(requests))
    request_count_matches = declared_request_count == len(requests)
    freshness = freshness_payload(payload.get("generated_at"), max_age_seconds)
    privacy = payload.get("privacy") if isinstance(payload.get("privacy"), dict) else {}
    privacy_ok = privacy.get("output_privacy_ok") is True
    missing_requirements = [
        str(item)
        for item in (payload.get("missing_requirements") or [])
        if isinstance(item, str)
    ]
    decision = str(payload.get("decision") or "unknown")
    expires_soon = (
        freshness["fresh"]
        and isinstance(freshness["seconds_until_stale"], int)
        and freshness["seconds_until_stale"] < min_collection_window_seconds
    )
    collection_blockers = []
    if decision != "REMOTE_CLIENT_EVIDENCE_REQUEST_READY":
        collection_blockers.append("decision_not_ready")
    if not freshness["fresh"]:
        collection_blockers.append("request_packet_not_fresh")
    if expires_soon:
        collection_blockers.append("request_packet_expiring_soon")
    if declared_request_count <= 0:
        collection_blockers.append("request_count_zero")
    if not request_count_matches:
        collection_blockers.append("request_count_mismatch")
    if not privacy_ok:
        collection_blockers.append("privacy_not_confirmed")
    if not safe_reply_options_ok:
        collection_blockers.append("safe_reply_options_incomplete_or_unsafe")
    if not request_shape_ok:
        collection_blockers.append("request_shape_invalid")
    if not production_profile_ok:
        collection_blockers.append("request_profile_not_distributable")
    if not tester_messages_safe:
        collection_blockers.append("tester_messages_missing_or_unsafe")
    elif not tester_messages_contract_ok:
        collection_blockers.append("tester_messages_contract_incomplete")
    if not reply_record_commands_hash_guard_ok:
        collection_blockers.append("reply_record_commands_missing_packet_hash_guard")
    if not reply_validate_commands_hash_guard_ok:
        collection_blockers.append("reply_validate_commands_missing_packet_hash_guard")
    collection_ready = not collection_blockers
    status = "ready" if collection_ready else "refresh_required"

    return {
        **base,
        **freshness,
        "source_sha256": hashlib.sha256(raw_packet).hexdigest(),
        "source_size_bytes": len(raw_packet),
        "available": True,
        "status": status,
        "packet_id": str(payload.get("packet_id") or ""),
        "decision": decision,
        "request_count": len(requests),
        "declared_request_count": declared_request_count,
        "request_count_matches": request_count_matches,
        "min_collection_window_seconds": min_collection_window_seconds,
        "expires_soon": expires_soon,
        "minimum_reports_required": payload.get("minimum_reports_required"),
        "missing_requirements": missing_requirements,
        "privacy_ok": privacy_ok,
        "safe_reply_options_ok": safe_reply_options_ok,
        "request_shape_ok": request_shape_ok,
        "production_profile_ok": production_profile_ok,
        "expected_transport": expected_transport,
        "expected_port": expected_port,
        "tester_messages_safe": tester_messages_safe,
        "tester_messages_contract_ok": tester_messages_contract_ok,
        "reply_record_commands_hash_guard_ok": reply_record_commands_hash_guard_ok,
        "reply_validate_commands_hash_guard_ok": reply_validate_commands_hash_guard_ok,
        "reply_commands_hash_guard_ok": (
            reply_record_commands_hash_guard_ok and reply_validate_commands_hash_guard_ok
        ),
        "collection_ready": collection_ready,
        "collection_blockers": collection_blockers,
        "requests": requests,
    }

def read_client_evidence_status() -> dict:
    path = Path(
        os.environ.get(
            "VPN_CLIENT_EVIDENCE_STATUS_FILE",
            "/mnt/projects/nl-diagnostics/vpn-production-candidate-goal-2026-06-02.json",
        )
    )
    remote_request_packet = read_remote_request_packet_summary()
    base = {
        "source": str(path),
        "status": "unknown",
        "goal_decision": "unknown",
        "goal_complete": False,
        "generated_at": None,
        "age_seconds": None,
        "max_age_seconds": safe_int(os.environ.get("VPN_CLIENT_EVIDENCE_MAX_AGE_SECONDS"), 86400),
        "stale_after": None,
        "seconds_until_stale": None,
        "fresh": False,
        "freshness_status": "missing",
        "refresh_required": True,
        "requirements_passed": None,
        "requirements_total": None,
        "blocked_requirement": None,
        "missing_requirements": [],
        "remote_request_ready": False,
        "remote_request_contract_ready": False,
        "remote_request_privacy_ok": False,
        "remote_request_freshness_policy_ok": False,
        "remote_request_record_commands_use_stdin": False,
        "remote_request_validate_commands_no_write": False,
        "remote_request_safe_reply_options_ok": False,
        "safe_remote_request_collection_ready": False,
        "collection_blockers": ["client_evidence_status_missing_or_unreadable"],
        "remote_request_count": 0,
        "remote_request_packet": remote_request_packet,
        "operator_action": "refresh_client_evidence_status",
        "next_step": "client evidence status file is missing or unreadable",
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
    }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return base
    if not isinstance(payload, dict):
        return base
    freshness = evidence_freshness(payload.get("generated_at"))

    requirements = payload.get("requirements") or []
    blocked = None
    for row in requirements:
        if isinstance(row, dict) and row.get("id") == "ANTIBLOCK-CLIENTS-01":
            blocked = row
            break
    if blocked is None:
        blocked = next(
            (row for row in requirements if isinstance(row, dict) and not row.get("ok")),
            None,
        )

    evidence = blocked.get("evidence") if isinstance(blocked, dict) else []
    evidence_values = {}
    if isinstance(evidence, list):
        for item in evidence:
            if isinstance(item, str) and "=" in item:
                key, value = item.split("=", 1)
                evidence_values[key.strip()] = value.strip()

    status = "complete" if payload.get("goal_complete") is True else "incomplete"
    if isinstance(blocked, dict) and not blocked.get("ok"):
        status = str(blocked.get("status") or "incomplete")

    missing = []
    raw_missing = evidence_values.get("missing_requirements", "")
    if raw_missing and raw_missing != "none":
        missing = [item.strip() for item in raw_missing.split(",") if item.strip()]
    remote_request_count = safe_int(evidence_values.get("remote_request_count"))
    remote_request_ready = bool_from_text(evidence_values.get("remote_request_ready"))
    remote_request_contract_ready = bool_from_text(
        evidence_values.get("remote_request_contract_ready")
    )
    remote_request_privacy_ok = bool_from_text(evidence_values.get("remote_request_privacy_ok"))
    remote_request_freshness_policy_ok = bool_from_text(
        evidence_values.get("remote_request_freshness_policy_ok")
    )
    remote_request_record_commands_use_stdin = bool_from_text(
        evidence_values.get("remote_request_record_commands_use_stdin")
    )
    remote_request_validate_commands_no_write = bool_from_text(
        evidence_values.get("remote_request_validate_commands_no_write")
    )
    remote_request_safe_reply_options_ok = bool_from_text(
        evidence_values.get("remote_request_safe_reply_options_ok")
    )
    collection_blockers = []
    if not freshness["fresh"]:
        collection_blockers.append("client_evidence_not_fresh")
    if not remote_request_ready:
        collection_blockers.append("remote_request_not_ready")
    if remote_request_count <= 0:
        collection_blockers.append("remote_request_count_zero")
    if not remote_request_packet["collection_ready"]:
        collection_blockers.append("remote_request_packet_not_ready")
    if not remote_request_contract_ready:
        collection_blockers.append("remote_request_contract_not_ready")
    if not remote_request_privacy_ok:
        collection_blockers.append("remote_request_privacy_not_confirmed")
    if not remote_request_freshness_policy_ok:
        collection_blockers.append("remote_request_freshness_policy_not_confirmed")
    if not remote_request_record_commands_use_stdin:
        collection_blockers.append("record_commands_do_not_use_stdin")
    if not remote_request_validate_commands_no_write:
        collection_blockers.append("validate_commands_may_write")
    if not remote_request_safe_reply_options_ok:
        collection_blockers.append("remote_request_safe_reply_options_not_confirmed")
    safe_remote_request_collection_ready = not collection_blockers
    if payload.get("goal_complete") is True:
        operator_action = "observe"
    elif not freshness["fresh"]:
        operator_action = "refresh_client_evidence_status"
    elif safe_remote_request_collection_ready:
        operator_action = "collect_remote_client_replies"
    elif remote_request_ready:
        operator_action = "refresh_remote_request_packet"
    elif missing:
        operator_action = "build_remote_request_packet"
    else:
        operator_action = "operator_review"

    return {
        **base,
        **freshness,
        "status": status,
        "goal_decision": str(payload.get("decision") or "unknown"),
        "goal_complete": payload.get("goal_complete") is True,
        "requirements_passed": payload.get("requirements_passed"),
        "requirements_total": payload.get("requirements_total"),
        "blocked_requirement": blocked.get("id") if isinstance(blocked, dict) else None,
        "missing_requirements": missing,
        "remote_request_ready": remote_request_ready,
        "remote_request_contract_ready": remote_request_contract_ready,
        "remote_request_privacy_ok": remote_request_privacy_ok,
        "remote_request_freshness_policy_ok": remote_request_freshness_policy_ok,
        "remote_request_record_commands_use_stdin": remote_request_record_commands_use_stdin,
        "remote_request_validate_commands_no_write": remote_request_validate_commands_no_write,
        "remote_request_safe_reply_options_ok": remote_request_safe_reply_options_ok,
        "safe_remote_request_collection_ready": safe_remote_request_collection_ready,
        "collection_blockers": collection_blockers,
        "remote_request_count": remote_request_count,
        "remote_request_packet": remote_request_packet,
        "operator_action": operator_action,
        "next_step": (
            str(blocked.get("next_step"))
            if isinstance(blocked, dict) and blocked.get("next_step")
            else "no blocked client evidence requirement"
        ),
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
    }

def read_subscription_payload_status() -> dict:
    path = Path(
        os.environ.get(
            "VPN_SUBSCRIPTION_PAYLOAD_STATUS_FILE",
            "/mnt/projects/nl-diagnostics/nl-live-subscription-payload-latest.json",
        )
    )
    max_age_seconds = safe_int(
        os.environ.get("VPN_SUBSCRIPTION_PAYLOAD_MAX_AGE_SECONDS"),
        1800,
    )
    expected_ports = {
        safe_int(item)
        for item in os.environ.get("VPN_SUBSCRIPTION_EXPECTED_PORTS", "443,2083").split(",")
        if item.strip()
    }
    expected_ports.discard(0)
    base = {
        "source": str(path),
        "source_sha256": None,
        "source_size_bytes": 0,
        "available": False,
        "status": "missing",
        "decision": "unknown",
        "ok": False,
        "generated_at": None,
        "age_seconds": None,
        "max_age_seconds": max_age_seconds,
        "stale_after": None,
        "seconds_until_stale": None,
        "fresh": False,
        "freshness_status": "missing",
        "refresh_required": True,
        "checked_subscription_count": 0,
        "candidate_subscription_count": 0,
        "expected_ports": sorted(expected_ports),
        "ports": [],
        "transport_counts": {},
        "failures": ["subscription_payload_status_missing_or_unreadable"],
        "privacy_ok": False,
        "raw_tokens_printed": False,
        "raw_profile_uris_printed": False,
        "raw_uuid_printed": False,
        "raw_host_printed": False,
        "expired_error_check": {
            "available": False,
            "ok": False,
            "status": "missing",
            "checked_subscription_count": 0,
            "candidate_subscription_count": 0,
            "status_counts": {},
            "max_profile_count": 0,
            "ports_seen": [],
            "failures": ["expired_error_check_missing"],
            "privacy_ok": False,
            "raw_tokens_or_uris_printed": False,
        },
        "anti_dpi": {
            "available": False,
            "status": "missing",
            "ready": False,
            "primary_reality_443_ready": False,
            "secondary_reality_port_ready": False,
            "reality_only": False,
            "legacy_transports_absent": False,
            "checked_subscription_count": 0,
            "ready_subscription_count": 0,
            "primary_reality_443_ready_count": 0,
            "secondary_reality_port_ready_count": 0,
            "all_checked_have_primary_reality_443": False,
            "all_checked_have_secondary_reality_port": False,
            "recommended_port_order": [],
            "status_counts": {},
            "warning_counts": {},
            "blocker_counts": {},
            "warnings": [],
            "blockers": ["anti_dpi_subscription_payload_status_missing"],
            "privacy_ok": False,
            "raw_tokens_or_uris_printed": False,
            "raw_uuid_printed": False,
            "raw_host_printed": False,
        },
        "operator_action": "refresh_subscription_payload_status",
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
    }
    try:
        raw_status = path.read_bytes()
        payload = json.loads(raw_status.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return base
    if not isinstance(payload, dict):
        return base

    freshness = freshness_payload(payload.get("generated_at"), max_age_seconds)
    ports = sorted(
        {
            int(port)
            for port in (payload.get("ports") or [])
            if isinstance(port, int) or str(port).isdigit()
        }
    )
    transport_counts = (
        payload.get("transport_counts")
        if isinstance(payload.get("transport_counts"), dict)
        else {}
    )
    failures = [
        str(item)
        for item in (payload.get("failures") or [])
        if isinstance(item, str)
    ]
    privacy = payload.get("privacy") if isinstance(payload.get("privacy"), dict) else {}
    privacy_ok = (
        privacy.get("raw_tokens_printed") is False
        and privacy.get("raw_profile_uris_printed") is False
        and privacy.get("raw_uuid_printed") is False
        and privacy.get("raw_host_printed") is False
    )
    expired_raw = (
        payload.get("expired_error_check")
        if isinstance(payload.get("expired_error_check"), dict)
        else {}
    )
    expired_failures = [
        str(item)
        for item in (expired_raw.get("failures") or [])
        if isinstance(item, str)
    ]
    expired_ports_seen = sorted(
        {
            int(port)
            for port in (expired_raw.get("ports_seen") or [])
            if isinstance(port, int) or str(port).isdigit()
        }
    )
    expired_status_counts = (
        expired_raw.get("status_counts")
        if isinstance(expired_raw.get("status_counts"), dict)
        else {}
    )
    expired_error_check = {
        "available": bool(expired_raw),
        "ok": expired_raw.get("ok") is True,
        "status": str(expired_raw.get("status") or "missing"),
        "checked_subscription_count": safe_int(expired_raw.get("checked_subscription_count")),
        "candidate_subscription_count": safe_int(expired_raw.get("candidate_subscription_count")),
        "status_counts": {
            str(key): safe_int(value) for key, value in expired_status_counts.items()
        },
        "max_profile_count": safe_int(expired_raw.get("max_profile_count")),
        "ports_seen": expired_ports_seen,
        "failures": expired_failures,
        "privacy_ok": expired_raw.get("raw_tokens_or_uris_printed") is False,
        "raw_tokens_or_uris_printed": expired_raw.get("raw_tokens_or_uris_printed") is True,
    }
    unexpected_ports = [port for port in ports if expected_ports and port not in expected_ports]
    disallowed_transports = [
        key
        for key, value in transport_counts.items()
        if key != "reality" and safe_int(value) > 0
    ]
    checked_subscription_count = safe_int(payload.get("checked_subscription_count"))
    candidate_subscription_count = safe_int(payload.get("candidate_subscription_count"))
    guard_failures = list(failures)
    if payload.get("ok") is not True:
        guard_failures.append("subscription_payload_check_not_ok")
    if not freshness["fresh"]:
        guard_failures.append("subscription_payload_status_not_fresh")
    if checked_subscription_count <= 0:
        guard_failures.append("subscription_payload_no_active_subscriptions_checked")
    if unexpected_ports:
        guard_failures.append("subscription_payload_unexpected_ports")
    if disallowed_transports:
        guard_failures.append("subscription_payload_disallowed_transports")
    if not privacy_ok:
        guard_failures.append("subscription_payload_privacy_not_confirmed")
    if not expired_error_check["available"]:
        guard_failures.append("subscription_payload_expired_error_check_missing")
    elif not expired_error_check["ok"]:
        guard_failures.append("subscription_payload_expired_error_check_not_ok")
    if expired_error_check["max_profile_count"] > 0:
        guard_failures.append("subscription_payload_expired_subscription_returned_profile")
    if expired_error_check["ports_seen"]:
        guard_failures.append("subscription_payload_expired_subscription_returned_ports")
    if not expired_error_check["privacy_ok"]:
        guard_failures.append("subscription_payload_expired_error_privacy_not_confirmed")

    anti_dpi_raw = payload.get("anti_dpi") if isinstance(payload.get("anti_dpi"), dict) else {}
    anti_dpi_warnings = sorted(
        {
            str(item)
            for item in (anti_dpi_raw.get("warnings") or [])
            if isinstance(item, str)
        }
    )
    anti_dpi_blockers = sorted(
        {
            str(item)
            for item in (anti_dpi_raw.get("blockers") or [])
            if isinstance(item, str)
        }
    )
    anti_dpi_warning_counts_raw = (
        anti_dpi_raw.get("warning_counts")
        if isinstance(anti_dpi_raw.get("warning_counts"), dict)
        else {}
    )
    anti_dpi_blocker_counts_raw = (
        anti_dpi_raw.get("blocker_counts")
        if isinstance(anti_dpi_raw.get("blocker_counts"), dict)
        else {}
    )
    anti_dpi_status_counts_raw = (
        anti_dpi_raw.get("status_counts")
        if isinstance(anti_dpi_raw.get("status_counts"), dict)
        else {}
    )
    anti_dpi_recommended_port_order = [
        port
        for port in (
            safe_int(item)
            for item in (anti_dpi_raw.get("recommended_port_order") or [])
        )
        if port > 0
    ]
    if not anti_dpi_recommended_port_order:
        for port in (443, 2083):
            if port in ports and port not in anti_dpi_recommended_port_order:
                anti_dpi_recommended_port_order.append(port)

    if anti_dpi_raw:
        anti_dpi_available = True
        anti_dpi_status = str(anti_dpi_raw.get("status") or "unknown")
        anti_dpi_ready = anti_dpi_raw.get("ready") is True
        anti_dpi_primary_ready = (
            anti_dpi_raw.get("all_checked_have_primary_reality_443") is True
            or anti_dpi_raw.get("primary_reality_443_ready") is True
        )
        anti_dpi_secondary_ready = (
            anti_dpi_raw.get("all_checked_have_secondary_reality_port") is True
            or anti_dpi_raw.get("secondary_reality_port_ready") is True
        )
        anti_dpi_ready_count = safe_int(anti_dpi_raw.get("ready_subscription_count"))
        anti_dpi_primary_ready_count = safe_int(anti_dpi_raw.get("primary_reality_443_ready_count"))
        anti_dpi_secondary_ready_count = safe_int(anti_dpi_raw.get("secondary_reality_port_ready_count"))
        anti_dpi_checked_count = safe_int(
            anti_dpi_raw.get("checked_subscription_count"),
            checked_subscription_count,
        )
        anti_dpi_reality_only = (
            anti_dpi_raw.get("reality_only") is True
            if "reality_only" in anti_dpi_raw
            else not disallowed_transports and checked_subscription_count > 0
        )
        anti_dpi_legacy_absent = (
            anti_dpi_raw.get("legacy_transports_absent") is True
            if "legacy_transports_absent" in anti_dpi_raw
            else not disallowed_transports
        )
        anti_dpi_privacy_ok = (
            anti_dpi_raw.get("raw_tokens_or_uris_printed") is False
            and anti_dpi_raw.get("raw_uuid_printed") is False
            and anti_dpi_raw.get("raw_host_printed") is False
        )
    else:
        anti_dpi_available = False
        anti_dpi_checked_count = checked_subscription_count
        anti_dpi_ready_count = checked_subscription_count if not guard_failures else 0
        anti_dpi_primary_ready_count = checked_subscription_count if 443 in ports else 0
        anti_dpi_secondary_ready_count = checked_subscription_count if 2083 in ports else 0
        anti_dpi_primary_ready = checked_subscription_count > 0 and 443 in ports
        anti_dpi_secondary_ready = checked_subscription_count > 0 and 2083 in ports
        anti_dpi_reality_only = checked_subscription_count > 0 and not disallowed_transports
        anti_dpi_legacy_absent = not disallowed_transports
        anti_dpi_privacy_ok = privacy_ok
        if not anti_dpi_primary_ready:
            anti_dpi_blockers.append("anti_dpi_primary_reality_443_missing")
        if not anti_dpi_reality_only:
            anti_dpi_blockers.append("anti_dpi_legacy_transports_in_subscription")
        if unexpected_ports:
            anti_dpi_blockers.append("anti_dpi_unexpected_ports_in_subscription")
        if not anti_dpi_secondary_ready and checked_subscription_count > 0:
            anti_dpi_warnings.append("anti_dpi_secondary_reality_port_missing")
        anti_dpi_warnings.append("anti_dpi_detail_missing_from_payload_check")
        anti_dpi_status = (
            "unsafe"
            if anti_dpi_blockers
            else "ready_with_warnings"
            if anti_dpi_warnings
            else "ready"
        )
        anti_dpi_ready = anti_dpi_status in {"ready", "ready_with_warnings"}

    anti_dpi_blockers = sorted(set(anti_dpi_blockers))
    anti_dpi_warnings = sorted(set(anti_dpi_warnings))
    anti_dpi = {
        "available": anti_dpi_available,
        "status": anti_dpi_status,
        "ready": anti_dpi_ready,
        "primary_reality_443_ready": anti_dpi_primary_ready,
        "secondary_reality_port_ready": anti_dpi_secondary_ready,
        "reality_only": anti_dpi_reality_only,
        "legacy_transports_absent": anti_dpi_legacy_absent,
        "checked_subscription_count": anti_dpi_checked_count,
        "ready_subscription_count": anti_dpi_ready_count,
        "primary_reality_443_ready_count": anti_dpi_primary_ready_count,
        "secondary_reality_port_ready_count": anti_dpi_secondary_ready_count,
        "all_checked_have_primary_reality_443": anti_dpi_primary_ready,
        "all_checked_have_secondary_reality_port": anti_dpi_secondary_ready,
        "recommended_port_order": anti_dpi_recommended_port_order,
        "status_counts": {
            str(key): safe_int(value) for key, value in anti_dpi_status_counts_raw.items()
        },
        "warning_counts": {
            str(key): safe_int(value) for key, value in anti_dpi_warning_counts_raw.items()
        },
        "blocker_counts": {
            str(key): safe_int(value) for key, value in anti_dpi_blocker_counts_raw.items()
        },
        "warnings": anti_dpi_warnings,
        "blockers": anti_dpi_blockers,
        "privacy_ok": anti_dpi_privacy_ok,
        "raw_tokens_or_uris_printed": anti_dpi_raw.get("raw_tokens_or_uris_printed") is True,
        "raw_uuid_printed": anti_dpi_raw.get("raw_uuid_printed") is True,
        "raw_host_printed": anti_dpi_raw.get("raw_host_printed") is True,
    }
    if anti_dpi_status == "unsafe":
        guard_failures.append("subscription_payload_anti_dpi_not_ready")
    if not anti_dpi_privacy_ok:
        guard_failures.append("subscription_payload_anti_dpi_privacy_not_confirmed")
    guard_failures = sorted(set(guard_failures))
    if not guard_failures:
        status = "safe"
        operator_action = "observe"
    elif not freshness["fresh"]:
        status = "stale"
        operator_action = "refresh_subscription_payload_status"
    else:
        status = "unsafe"
        operator_action = "fix_subscription_payload_before_user_rotation"

    return {
        **base,
        **freshness,
        "source_sha256": hashlib.sha256(raw_status).hexdigest(),
        "source_size_bytes": len(raw_status),
        "available": True,
        "status": status,
        "decision": str(payload.get("decision") or "unknown"),
        "ok": payload.get("ok") is True,
        "checked_subscription_count": checked_subscription_count,
        "candidate_subscription_count": candidate_subscription_count,
        "expected_ports": sorted(expected_ports),
        "ports": ports,
        "unexpected_ports": unexpected_ports,
        "transport_counts": {str(key): safe_int(value) for key, value in transport_counts.items()},
        "disallowed_transports": disallowed_transports,
        "failures": guard_failures,
        "privacy_ok": privacy_ok,
        "raw_tokens_printed": privacy.get("raw_tokens_printed") is True,
        "raw_profile_uris_printed": privacy.get("raw_profile_uris_printed") is True,
        "raw_uuid_printed": privacy.get("raw_uuid_printed") is True,
        "raw_host_printed": privacy.get("raw_host_printed") is True,
        "expired_error_check": expired_error_check,
        "anti_dpi": anti_dpi,
        "operator_action": operator_action,
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
    }

def read_transport_usage_status() -> dict:
    path = Path(
        os.environ.get(
            "VPN_TRANSPORT_USAGE_STATUS_FILE",
            "/mnt/projects/nl-diagnostics/nl-transport-usage-latest.json",
        )
    )
    max_age_seconds = safe_int(
        os.environ.get("VPN_TRANSPORT_USAGE_MAX_AGE_SECONDS"),
        900,
    )
    base = {
        "source": str(path),
        "source_sha256": None,
        "source_size_bytes": 0,
        "available": False,
        "status": "missing",
        "decision": "unknown",
        "ok": False,
        "generated_at": None,
        "age_seconds": None,
        "max_age_seconds": max_age_seconds,
        "stale_after": None,
        "seconds_until_stale": None,
        "fresh": False,
        "freshness_status": "missing",
        "refresh_required": True,
        "findings": [],
        "summary": {
            "recent_window_minutes": None,
            "severity": "unknown",
            "attention_scope": "unknown",
            "restart_relevant": False,
            "proxy_requests": 0,
            "dataplane_events": 0,
            "max_unique_proxy_source_count": 0,
            "aggregate_unique_proxy_source_count": 0,
            "attention_unique_proxy_source_count": 0,
            "operator_action": "collect_transport_usage_evidence",
        },
        "recent_window_minutes": None,
        "severity": "unknown",
        "attention_scope": "unknown",
        "restart_relevant": False,
        "proxy_requests": 0,
        "dataplane_events": 0,
        "max_unique_proxy_source_count": 0,
        "aggregate_unique_proxy_source_count": 0,
        "attention_unique_proxy_source_count": 0,
        "operator_action": "collect_transport_usage_evidence",
        "privacy_ok": False,
        "raw_identifiers_stored": False,
        "raw_ip_stored": False,
        "raw_email_stored": False,
        "raw_target_host_stored": False,
        "windows": {},
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
    }
    try:
        raw_status = path.read_bytes()
        payload = json.loads(raw_status.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return base
    if not isinstance(payload, dict):
        return base

    freshness = freshness_payload(payload.get("generated_at"), max_age_seconds)
    privacy = payload.get("privacy") if isinstance(payload.get("privacy"), dict) else {}
    privacy_ok = (
        privacy.get("raw_identifiers_stored") is False
        and privacy.get("raw_ip_stored") is False
        and privacy.get("raw_nginx_source_ip_stored") is not True
        and privacy.get("raw_email_stored") is False
        and privacy.get("raw_target_host_stored") is False
        and privacy.get("raw_user_agent_stored") is not True
    )
    findings = [
        str(item)
        for item in (payload.get("findings") or [])
        if isinstance(item, str)
    ]
    raw_summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    summary = {
        "recent_window_minutes": safe_int(raw_summary.get("recent_window_minutes")),
        "severity": str(raw_summary.get("severity") or "unknown"),
        "attention_scope": str(raw_summary.get("attention_scope") or "unknown"),
        "restart_relevant": raw_summary.get("restart_relevant") is True,
        "proxy_requests": safe_int(raw_summary.get("proxy_requests")),
        "dataplane_events": safe_int(raw_summary.get("dataplane_events")),
        "max_unique_proxy_source_count": safe_int(raw_summary.get("max_unique_proxy_source_count")),
        "aggregate_unique_proxy_source_count": safe_int(raw_summary.get("aggregate_unique_proxy_source_count")),
        "attention_unique_proxy_source_count": safe_int(raw_summary.get("attention_unique_proxy_source_count")),
        "operator_action": str(raw_summary.get("operator_action") or ""),
    }
    windows: dict[str, object] = {}
    raw_windows = payload.get("windows") if isinstance(payload.get("windows"), dict) else {}
    for window_name, window in raw_windows.items():
        if not isinstance(window, dict):
            continue
        health = (
            window.get("legacy_transport_health")
            if isinstance(window.get("legacy_transport_health"), dict)
            else {}
        )
        transports = {}
        raw_transports = health.get("transports") if isinstance(health.get("transports"), dict) else {}
        for transport_name, transport in raw_transports.items():
            if not isinstance(transport, dict):
                continue
            transports[str(transport_name)] = {
                "status": str(transport.get("status") or "unknown"),
                "attention_scope": str(transport.get("attention_scope") or "unknown"),
                "restart_relevant": transport.get("restart_relevant") is True,
                "proxy_requests": safe_int(transport.get("proxy_requests")),
                "proxy_4xx": safe_int(transport.get("proxy_4xx")),
                "proxy_5xx": safe_int(transport.get("proxy_5xx")),
                "unique_proxy_source_count": safe_int(transport.get("unique_proxy_source_count")),
                "proxy_method_counts": {
                    str(key): safe_int(value)
                    for key, value in (transport.get("proxy_method_counts") or {}).items()
                }
                if isinstance(transport.get("proxy_method_counts"), dict)
                else {},
                "proxy_user_agent_family_counts": {
                    str(key): safe_int(value)
                    for key, value in (transport.get("proxy_user_agent_family_counts") or {}).items()
                }
                if isinstance(transport.get("proxy_user_agent_family_counts"), dict)
                else {},
                "dataplane_events": safe_int(transport.get("dataplane_events")),
                "unique_client_count": safe_int(transport.get("unique_client_count")),
                "last_proxy_seen_at": transport.get("last_proxy_seen_at"),
                "last_dataplane_seen_at": transport.get("last_dataplane_seen_at"),
                "findings": [
                    str(item)
                    for item in (transport.get("findings") or [])
                    if isinstance(item, str)
                ],
            }
        windows[str(window_name)] = {
            "status": str(health.get("status") or "unknown"),
            "ok": health.get("ok") is True,
            "severity": str(health.get("severity") or "unknown"),
            "attention_scope": str(health.get("attention_scope") or "unknown"),
            "restart_relevant": health.get("restart_relevant") is True,
            "proxy_requests": safe_int(health.get("proxy_requests")),
            "dataplane_events": safe_int(health.get("dataplane_events")),
            "max_unique_proxy_source_count": safe_int(health.get("max_unique_proxy_source_count")),
            "aggregate_unique_proxy_source_count": safe_int(health.get("aggregate_unique_proxy_source_count")),
            "attention_unique_proxy_source_count": safe_int(health.get("attention_unique_proxy_source_count")),
            "operator_action": str(health.get("operator_action") or ""),
            "findings": [
                str(item)
                for item in (health.get("findings") or [])
                if isinstance(item, str)
            ],
            "transports": transports,
        }

    if not freshness["fresh"]:
        status = "stale"
        operator_action = "refresh_transport_usage_evidence"
    elif payload.get("ok") is True and not findings:
        status = "safe"
        operator_action = "observe"
    else:
        status = "attention"
        operator_action = str(
            summary.get("operator_action")
            or payload.get("operator_action")
            or "check_legacy_clients_and_migrate_to_reality"
        )

    return {
        **base,
        **freshness,
        "source_sha256": hashlib.sha256(raw_status).hexdigest(),
        "source_size_bytes": len(raw_status),
        "available": True,
        "status": status,
        "decision": str(payload.get("decision") or "unknown"),
        "ok": payload.get("ok") is True,
        "findings": sorted(set(findings)),
        "summary": summary,
        "recent_window_minutes": summary["recent_window_minutes"],
        "severity": summary["severity"],
        "attention_scope": summary["attention_scope"],
        "restart_relevant": summary["restart_relevant"],
        "proxy_requests": summary["proxy_requests"],
        "dataplane_events": summary["dataplane_events"],
        "max_unique_proxy_source_count": summary["max_unique_proxy_source_count"],
        "aggregate_unique_proxy_source_count": summary["aggregate_unique_proxy_source_count"],
        "attention_unique_proxy_source_count": summary["attention_unique_proxy_source_count"],
        "operator_action": operator_action,
        "privacy_ok": privacy_ok,
        "raw_identifiers_stored": privacy.get("raw_identifiers_stored") is True,
        "raw_ip_stored": privacy.get("raw_ip_stored") is True,
        "raw_email_stored": privacy.get("raw_email_stored") is True,
        "raw_target_host_stored": privacy.get("raw_target_host_stored") is True,
        "windows": windows,
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
    }

def read_legacy_migration_status() -> dict:
    path = Path(
        os.environ.get(
            "VPN_LEGACY_MIGRATION_PACKET_FILE",
            "/mnt/projects/nl-diagnostics/nl-legacy-client-migration-packet-2026-06-05.json",
        )
    )
    max_age_seconds = safe_int(
        os.environ.get("VPN_LEGACY_MIGRATION_MAX_AGE_SECONDS"),
        86400,
    )
    base = {
        "source": str(path),
        "source_sha256": None,
        "source_size_bytes": 0,
        "available": False,
        "status": "missing",
        "decision": "unknown",
        "operator_action": "build_legacy_client_migration_packet",
        "generated_at": None,
        "age_seconds": None,
        "max_age_seconds": max_age_seconds,
        "stale_after": None,
        "seconds_until_stale": None,
        "fresh": False,
        "freshness_status": "missing",
        "refresh_required": True,
        "ready": False,
        "target_audience": {
            "active_subscription_count": 0,
            "expired_users_excluded": 0,
            "users_with_devices": 0,
            "raw_user_ids_printed": False,
            "raw_chat_ids_printed": False,
        },
        "safe_reply_options": [],
        "privacy_ok": False,
        "send_policy": {
            "automatic_broadcast_allowed": False,
            "manual_operator_review_required": True,
        },
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
    }
    try:
        raw_status = path.read_bytes()
        payload = json.loads(raw_status.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return base
    if not isinstance(payload, dict):
        return base

    freshness = freshness_payload(payload.get("generated_at"), max_age_seconds)
    privacy = payload.get("privacy") if isinstance(payload.get("privacy"), dict) else {}
    privacy_ok = (
        privacy.get("raw_user_ids_printed") is False
        and privacy.get("raw_chat_ids_printed") is False
        and privacy.get("raw_tokens_printed") is False
        and privacy.get("raw_subscription_urls_printed") is False
        and privacy.get("raw_vpn_uris_printed") is False
        and privacy.get("raw_uuid_printed") is False
        and privacy.get("raw_ip_printed") is False
        and privacy.get("raw_telegram_handle_printed") is False
    )
    audience = payload.get("target_audience") if isinstance(payload.get("target_audience"), dict) else {}
    migration = (
        payload.get("migration_request")
        if isinstance(payload.get("migration_request"), dict)
        else {}
    )
    send_policy = payload.get("send_policy") if isinstance(payload.get("send_policy"), dict) else {}
    decision = str(payload.get("decision") or "unknown")
    ready = (
        decision == "LEGACY_CLIENT_MIGRATION_PACKET_READY"
        and freshness["fresh"]
        and privacy_ok
    )
    if ready:
        status = "ready"
    elif not freshness["fresh"]:
        status = "stale"
    elif decision.endswith("_BLOCKED_SUBSCRIPTION_UNSAFE") or not privacy_ok:
        status = "blocked"
    else:
        status = "not_ready"
    return {
        **base,
        **freshness,
        "source_sha256": hashlib.sha256(raw_status).hexdigest(),
        "source_size_bytes": len(raw_status),
        "available": True,
        "status": status,
        "decision": decision,
        "operator_action": str(payload.get("operator_action") or base["operator_action"]),
        "ready": ready,
        "target_audience": {
            "active_subscription_count": safe_int(audience.get("active_subscription_count")),
            "expired_users_excluded": safe_int(audience.get("expired_users_excluded")),
            "users_with_devices": safe_int(audience.get("users_with_devices")),
            "raw_user_ids_printed": audience.get("raw_user_ids_printed") is True,
            "raw_chat_ids_printed": audience.get("raw_chat_ids_printed") is True,
        },
        "safe_reply_options": [
            str(item)
            for item in (migration.get("safe_reply_options") or [])
            if isinstance(item, str)
        ],
        "privacy_ok": privacy_ok,
        "send_policy": {
            "automatic_broadcast_allowed": send_policy.get("automatic_broadcast_allowed") is True,
            "manual_operator_review_required": send_policy.get("manual_operator_review_required") is True,
        },
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
    }

def read_legacy_migration_replies_status() -> dict:
    path = Path(
        os.environ.get(
            "VPN_LEGACY_MIGRATION_REPLIES_FILE",
            "/mnt/projects/nl-diagnostics/nl-legacy-client-migration-replies-2026-06-05.json",
        )
    )
    max_age_seconds = safe_int(
        os.environ.get("VPN_LEGACY_MIGRATION_REPLIES_MAX_AGE_SECONDS"),
        86400,
    )
    base = {
        "source": str(path),
        "source_sha256": None,
        "source_size_bytes": 0,
        "available": False,
        "status": "missing",
        "operator_action": "collect_legacy_migration_replies",
        "generated_at": None,
        "age_seconds": None,
        "max_age_seconds": max_age_seconds,
        "stale_after": None,
        "seconds_until_stale": None,
        "fresh": False,
        "freshness_status": "missing",
        "refresh_required": True,
        "total_replies": 0,
        "done_updated_count": 0,
        "failure_count": 0,
        "reply_counts": {},
        "result_counts": {},
        "symptom_counts": {},
        "packet_sha256": None,
        "privacy_ok": False,
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
    }
    try:
        raw_status = path.read_bytes()
        payload = json.loads(raw_status.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return base
    if not isinstance(payload, dict):
        return base

    freshness = freshness_payload(payload.get("generated_at"), max_age_seconds)
    privacy = payload.get("privacy") if isinstance(payload.get("privacy"), dict) else {}
    privacy_ok = (
        privacy.get("raw_user_ids_stored") is False
        and privacy.get("raw_chat_ids_stored") is False
        and privacy.get("raw_tokens_stored") is False
        and privacy.get("raw_subscription_urls_stored") is False
        and privacy.get("raw_vpn_uris_stored") is False
        and privacy.get("raw_uuid_stored") is False
        and privacy.get("raw_ip_stored") is False
        and privacy.get("raw_telegram_handle_stored") is False
    )
    packet = payload.get("packet") if isinstance(payload.get("packet"), dict) else {}
    status = str(payload.get("status") or "unknown")
    if not freshness["fresh"]:
        status = "stale"
        operator_action = "refresh_legacy_migration_reply_summary"
    elif not privacy_ok:
        status = "blocked_privacy"
        operator_action = "remove_sensitive_legacy_migration_reply_summary"
    else:
        operator_action = str(payload.get("operator_action") or "collect_legacy_migration_replies")
    return {
        **base,
        **freshness,
        "source_sha256": hashlib.sha256(raw_status).hexdigest(),
        "source_size_bytes": len(raw_status),
        "available": True,
        "status": status,
        "operator_action": operator_action,
        "total_replies": safe_int(payload.get("total_replies")),
        "done_updated_count": safe_int(payload.get("done_updated_count")),
        "failure_count": safe_int(payload.get("failure_count")),
        "reply_counts": {
            str(key): safe_int(value)
            for key, value in (payload.get("reply_counts") or {}).items()
        }
        if isinstance(payload.get("reply_counts"), dict)
        else {},
        "result_counts": {
            str(key): safe_int(value)
            for key, value in (payload.get("result_counts") or {}).items()
        }
        if isinstance(payload.get("result_counts"), dict)
        else {},
        "symptom_counts": {
            str(key): safe_int(value)
            for key, value in (payload.get("symptom_counts") or {}).items()
        }
        if isinstance(payload.get("symptom_counts"), dict)
        else {},
        "packet_sha256": packet.get("sha256") if isinstance(packet.get("sha256"), str) else None,
        "privacy_ok": privacy_ok,
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
    }

def read_legacy_migration_progress_status() -> dict:
    path = Path(
        os.environ.get(
            "VPN_LEGACY_MIGRATION_PROGRESS_FILE",
            "/mnt/projects/nl-diagnostics/nl-legacy-client-migration-progress-2026-06-05.json",
        )
    )
    max_age_seconds = safe_int(
        os.environ.get("VPN_LEGACY_MIGRATION_PROGRESS_MAX_AGE_SECONDS"),
        86400,
    )
    base = {
        "source": str(path),
        "source_sha256": None,
        "source_size_bytes": 0,
        "available": False,
        "status": "missing",
        "operator_action": "collect_legacy_migration_progress",
        "generated_at": None,
        "age_seconds": None,
        "max_age_seconds": max_age_seconds,
        "stale_after": None,
        "seconds_until_stale": None,
        "fresh": False,
        "freshness_status": "missing",
        "refresh_required": True,
        "sent_at": None,
        "sent_count": 0,
        "target_active_subscription_count": 0,
        "active_users_with_subscription_pull_since_message": 0,
        "active_users_with_device_activity_since_message": 0,
        "active_users_with_any_progress_since_message": 0,
        "active_users_with_subscription_and_device_progress_since_message": 0,
        "done_updated_count": 0,
        "failure_count": 0,
        "privacy_ok": False,
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
    }
    try:
        raw_status = path.read_bytes()
        payload = json.loads(raw_status.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return base
    if not isinstance(payload, dict):
        return base

    freshness = freshness_payload(payload.get("generated_at"), max_age_seconds)
    privacy = payload.get("privacy") if isinstance(payload.get("privacy"), dict) else {}
    privacy_ok = (
        privacy.get("raw_user_ids_stored") is False
        and privacy.get("raw_chat_ids_stored") is False
        and privacy.get("raw_tokens_stored") is False
        and privacy.get("raw_subscription_urls_stored") is False
        and privacy.get("raw_vpn_uris_stored") is False
        and privacy.get("raw_uuid_stored") is False
        and privacy.get("raw_ip_stored") is False
        and privacy.get("raw_telegram_handle_stored") is False
    )
    status = str(payload.get("status") or "unknown")
    if not freshness["fresh"]:
        status = "stale"
        operator_action = "refresh_legacy_migration_progress"
    elif not privacy_ok:
        status = "blocked_privacy"
        operator_action = "remove_sensitive_legacy_migration_progress"
    else:
        operator_action = str(payload.get("operator_action") or "collect_legacy_migration_progress")
    packet = payload.get("packet") if isinstance(payload.get("packet"), dict) else {}
    message_send = payload.get("message_send") if isinstance(payload.get("message_send"), dict) else {}
    replies = payload.get("replies") if isinstance(payload.get("replies"), dict) else {}
    db_progress = payload.get("db_progress") if isinstance(payload.get("db_progress"), dict) else {}
    subscription = (
        db_progress.get("subscription_refresh")
        if isinstance(db_progress.get("subscription_refresh"), dict)
        else {}
    )
    device = (
        db_progress.get("device_activity")
        if isinstance(db_progress.get("device_activity"), dict)
        else {}
    )
    combined = (
        db_progress.get("combined")
        if isinstance(db_progress.get("combined"), dict)
        else {}
    )
    return {
        **base,
        **freshness,
        "source_sha256": hashlib.sha256(raw_status).hexdigest(),
        "source_size_bytes": len(raw_status),
        "available": True,
        "status": status,
        "operator_action": operator_action,
        "sent_at": payload.get("sent_at") if isinstance(payload.get("sent_at"), str) else None,
        "sent_count": safe_int(message_send.get("sent_count")),
        "target_active_subscription_count": safe_int(packet.get("target_active_subscription_count")),
        "active_users_with_subscription_pull_since_message": safe_int(
            subscription.get("active_users_with_subscription_pull_since_message")
        ),
        "active_users_with_device_activity_since_message": safe_int(
            device.get("active_users_with_device_activity_since_message")
        ),
        "active_users_with_any_progress_since_message": safe_int(
            combined.get("active_users_with_any_progress_since_message")
        ),
        "active_users_with_subscription_and_device_progress_since_message": safe_int(
            combined.get("active_users_with_subscription_and_device_progress_since_message")
        ),
        "done_updated_count": safe_int(replies.get("done_updated_count")),
        "failure_count": safe_int(replies.get("failure_count")),
        "privacy_ok": privacy_ok,
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
    }

def read_legacy_no_progress_nudge_status(
    *,
    file_env: str = "VPN_LEGACY_NO_PROGRESS_NUDGE_FILE",
    default_file: str = "/mnt/projects/nl-diagnostics/nl-legacy-no-progress-nudge-2026-06-05.json",
    max_age_env: str = "VPN_LEGACY_NO_PROGRESS_NUDGE_MAX_AGE_SECONDS",
    default_max_age_seconds: int = 86400,
) -> dict:
    path = Path(
        os.environ.get(
            file_env,
            default_file,
        )
    )
    max_age_seconds = safe_int(
        os.environ.get(max_age_env),
        default_max_age_seconds,
    )
    cooldown_hours = float(os.environ.get("VPN_LEGACY_NO_PROGRESS_NUDGE_COOLDOWN_HOURS", "12") or 12)
    cooldown_seconds = int(cooldown_hours * 3600)
    base = {
        "source": str(path),
        "source_sha256": None,
        "source_size_bytes": 0,
        "available": False,
        "status": "missing",
        "decision": "unknown",
        "operator_action": "observe_or_prepare_no_progress_nudge",
        "generated_at": None,
        "age_seconds": None,
        "max_age_seconds": max_age_seconds,
        "stale_after": None,
        "seconds_until_stale": None,
        "fresh": False,
        "freshness_status": "missing",
        "refresh_required": True,
        "cooldown_hours": cooldown_hours,
        "cooldown_active": False,
        "next_nudge_allowed_at": None,
        "active_user_count": 0,
        "progress_user_count": 0,
        "reply_user_count": 0,
        "no_progress_candidate_count": 0,
        "selected_user_count": 0,
        "sent_count": 0,
        "failed_count": 0,
        "blocked_count": 0,
        "privacy_ok": False,
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
    }
    try:
        raw_status = path.read_bytes()
        payload = json.loads(raw_status.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return base
    if not isinstance(payload, dict):
        return base

    freshness = freshness_payload(payload.get("generated_at"), max_age_seconds)
    privacy = payload.get("privacy") if isinstance(payload.get("privacy"), dict) else {}
    privacy_ok = (
        privacy.get("raw_user_ids_printed") is False
        and privacy.get("raw_chat_ids_printed") is False
        and privacy.get("raw_tokens_printed") is False
        and privacy.get("raw_subscription_urls_printed") is False
        and privacy.get("raw_vpn_uris_printed") is False
        and privacy.get("raw_uuid_printed") is False
        and privacy.get("raw_ip_printed") is False
        and privacy.get("raw_telegram_handle_printed") is False
    )
    decision = str(payload.get("decision") or "unknown")
    if not freshness["fresh"]:
        status = "stale"
        operator_action = "refresh_no_progress_nudge_status"
    elif not privacy_ok:
        status = "blocked_privacy"
        operator_action = "remove_sensitive_no_progress_nudge_status"
    elif decision == "LEGACY_NO_PROGRESS_NUDGE_SENT":
        status = "sent"
        operator_action = "monitor_remaining_client_replies_and_legacy_transport"
    elif decision == "LEGACY_NO_PROGRESS_NUDGE_DRY_RUN":
        status = "dry_run"
        operator_action = "review_no_progress_nudge_dry_run"
    else:
        status = "unknown"
        operator_action = "observe_or_prepare_no_progress_nudge"
    generated_at = parse_utc_datetime(payload.get("generated_at"))
    cooldown_active = False
    next_nudge_allowed_at = None
    if decision == "LEGACY_NO_PROGRESS_NUDGE_SENT" and generated_at is not None and cooldown_seconds > 0:
        next_ts = generated_at.timestamp() + cooldown_seconds
        next_nudge_allowed_at = datetime.fromtimestamp(
            next_ts, timezone.utc
        ).isoformat().replace("+00:00", "Z")
        cooldown_active = datetime.now(timezone.utc).timestamp() < next_ts
    return {
        **base,
        **freshness,
        "source_sha256": hashlib.sha256(raw_status).hexdigest(),
        "source_size_bytes": len(raw_status),
        "available": True,
        "status": status,
        "decision": decision,
        "operator_action": operator_action,
        "cooldown_active": cooldown_active,
        "next_nudge_allowed_at": next_nudge_allowed_at,
        "active_user_count": safe_int(payload.get("active_user_count")),
        "progress_user_count": safe_int(payload.get("progress_user_count")),
        "reply_user_count": safe_int(payload.get("reply_user_count")),
        "no_progress_candidate_count": safe_int(payload.get("no_progress_candidate_count")),
        "selected_user_count": safe_int(payload.get("selected_user_count")),
        "sent_count": safe_int(payload.get("sent_count")),
        "failed_count": safe_int(payload.get("failed_count")),
        "blocked_count": safe_int(payload.get("blocked_count")),
        "privacy_ok": privacy_ok,
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
    }

def read_legacy_no_progress_nudge_dry_run_status() -> dict:
    return read_legacy_no_progress_nudge_status(
        file_env="VPN_LEGACY_NO_PROGRESS_NUDGE_DRY_RUN_FILE",
        default_file="/mnt/projects/nl-diagnostics/nl-legacy-no-progress-nudge-dry-run-latest.json",
        max_age_env="VPN_LEGACY_NO_PROGRESS_NUDGE_DRY_RUN_MAX_AGE_SECONDS",
        default_max_age_seconds=1800,
    )

def combine_operator_action(server_action: str, client_action: str) -> str:
    if server_action == "local_soft_heal":
        return "local_soft_heal_before_client_evidence"
    if server_action == "operator_review":
        return "operator_review"
    if client_action == "collect_remote_client_replies":
        return "observe_server_collect_client_replies"
    if client_action == "refresh_remote_request_packet":
        return "observe_server_refresh_remote_request_packet"
    if client_action == "build_remote_request_packet":
        return "observe_server_build_remote_request_packet"
    if client_action == "refresh_client_evidence_status":
        return "observe_server_refresh_client_evidence_status"
    if client_action == "observe":
        return "observe"
    return "observe_server_operator_review"

def build_restart_guard(
    *,
    restart_recommended: bool,
    restart_scope: str,
    restart_reason: str,
    overall_status: str,
    transport_status: str,
    server_operator_action: str,
    client_evidence_status: dict,
) -> dict:
    external_client_blocker = (
        client_evidence_status.get("status") == "blocked_external_evidence"
    )
    transport_healthy = overall_status in {"ok", "advisory"} and transport_status == "healthy"
    blocked_scopes = ["full_server", "nl", "spb", "x-ui"]
    allowed_manual_restart_scopes = []
    blocked_reasons = []
    operator_rule = "do_not_restart"

    if restart_recommended and restart_scope != "none":
        allowed_manual_restart_scopes = [restart_scope]
        operator_rule = "manual_scoped_restart_only"
    else:
        blocked_scopes = ["xray", *blocked_scopes]
        if transport_healthy:
            blocked_reasons.append("transport_healthy")
        if external_client_blocker:
            blocked_reasons.append("external_client_evidence_pending")
        if not blocked_reasons:
            blocked_reasons.append("restart_not_proven_necessary")

    if server_operator_action == "operator_review" and not restart_recommended:
        operator_rule = "operator_review_before_restart"
    elif server_operator_action == "local_soft_heal" and not restart_recommended:
        operator_rule = "local_soft_heal_without_restart"

    return {
        "automatic_restart_allowed": False,
        "guard_status": (
            "manual_scoped_restart_allowed" if allowed_manual_restart_scopes else "restart_blocked"
        ),
        "operator_rule": operator_rule,
        "restart_recommended": restart_recommended,
        "restart_scope": restart_scope,
        "restart_reason": restart_reason,
        "allowed_manual_restart_scopes": allowed_manual_restart_scopes,
        "blocked_restart_scopes": blocked_scopes,
        "blocked_reasons": blocked_reasons,
        "transport_healthy": transport_healthy,
        "external_client_evidence_pending": external_client_blocker,
        "requires_explicit_operator_action": bool(allowed_manual_restart_scopes),
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "spb_mutation_allowed": False,
    }

def build_user_connectivity_verification(
    *,
    subscription_payload_status: dict,
    transport_usage_status: dict,
    legacy_migration_replies_status: dict,
    legacy_migration_progress_status: dict,
    legacy_no_progress_nudge_status: dict,
    legacy_no_progress_nudge_dry_run_status: dict,
) -> dict:
    dry_run_usable = (
        legacy_no_progress_nudge_dry_run_status.get("status") == "dry_run"
        and legacy_no_progress_nudge_dry_run_status.get("fresh") is True
        and legacy_no_progress_nudge_dry_run_status.get("privacy_ok") is True
    )
    migration_evidence_available = (
        legacy_migration_progress_status.get("available") is True
        or legacy_migration_replies_status.get("available") is True
        or legacy_no_progress_nudge_status.get("available") is True
        or legacy_no_progress_nudge_dry_run_status.get("available") is True
    )
    target_active_count = max(
        safe_int(legacy_migration_progress_status.get("target_active_subscription_count")),
        safe_int(legacy_no_progress_nudge_status.get("active_user_count")),
        safe_int(legacy_no_progress_nudge_dry_run_status.get("active_user_count"))
        if dry_run_usable
        else 0,
        safe_int(subscription_payload_status.get("checked_subscription_count"))
        if migration_evidence_available
        else 0,
    )
    done_updated_count = safe_int(legacy_migration_replies_status.get("done_updated_count"))
    failure_reply_count = safe_int(legacy_migration_replies_status.get("failure_count"))
    total_replies = safe_int(legacy_migration_replies_status.get("total_replies"))
    any_progress_count = safe_int(
        legacy_migration_progress_status.get("active_users_with_any_progress_since_message")
    )
    device_activity_count = safe_int(
        legacy_migration_progress_status.get("active_users_with_device_activity_since_message")
    )
    subscription_pull_count = safe_int(
        legacy_migration_progress_status.get("active_users_with_subscription_pull_since_message")
    )
    subscription_and_device_count = safe_int(
        legacy_migration_progress_status.get(
            "active_users_with_subscription_and_device_progress_since_message"
        )
    )
    dry_run_progress_count = (
        safe_int(legacy_no_progress_nudge_dry_run_status.get("progress_user_count"))
        if dry_run_usable
        else 0
    )
    positive_signal_count = max(
        done_updated_count,
        any_progress_count,
        device_activity_count,
        dry_run_progress_count,
    )
    unconfirmed_by_reply_count = max(target_active_count - done_updated_count, 0)
    unverified_by_any_signal_count = max(target_active_count - positive_signal_count, 0)
    no_progress_candidate_count = (
        safe_int(legacy_no_progress_nudge_dry_run_status.get("no_progress_candidate_count"))
        if dry_run_usable
        else safe_int(legacy_no_progress_nudge_status.get("no_progress_candidate_count"))
    )
    cooldown_active = legacy_no_progress_nudge_status.get("cooldown_active") is True
    next_nudge_allowed_at = legacy_no_progress_nudge_status.get("next_nudge_allowed_at")
    transport_single_stale_legacy = (
        transport_usage_status.get("severity") == "single_source_stale_legacy"
        and transport_usage_status.get("aggregate_unique_proxy_source_count") == 1
    )
    legacy_transport_still_polling = transport_usage_status.get("status") == "attention"
    migration_progress_fresh = legacy_migration_progress_status.get("fresh") is True
    migration_replies_fresh = legacy_migration_replies_status.get("fresh") is True
    privacy_ok = (
        subscription_payload_status.get("privacy_ok") is True
        and transport_usage_status.get("privacy_ok") is True
        and legacy_migration_replies_status.get("privacy_ok") is True
        and legacy_migration_progress_status.get("privacy_ok") is True
        and (
            legacy_no_progress_nudge_dry_run_status.get("privacy_ok") is True
            if legacy_no_progress_nudge_dry_run_status.get("available") is True
            else True
        )
    )

    blockers: list[str] = []
    if target_active_count <= 0:
        blockers.append("target_active_user_count_missing")
    if not migration_progress_fresh:
        blockers.append("migration_progress_not_fresh")
    if not migration_replies_fresh:
        blockers.append("migration_replies_not_fresh")
    if subscription_payload_status.get("status") != "safe":
        blockers.append("subscription_payload_not_safe")
    if not privacy_ok:
        blockers.append("privacy_not_confirmed")
    if done_updated_count < target_active_count:
        blockers.append("not_all_users_confirmed_by_reply")
    if unverified_by_any_signal_count > 0:
        blockers.append("some_active_users_without_progress_signal")
    if legacy_transport_still_polling:
        blockers.append("legacy_transport_still_polling")
    if failure_reply_count > 0:
        blockers.append("user_failure_replies_seen")

    if target_active_count <= 0:
        status = "not_evaluated"
        operator_action = "collect_user_connectivity_target"
    elif done_updated_count >= target_active_count and failure_reply_count == 0 and privacy_ok:
        status = "verified_by_user_replies"
        operator_action = "observe"
    elif positive_signal_count >= target_active_count and failure_reply_count == 0:
        status = "all_targets_have_indirect_progress"
        operator_action = "collect_user_replies_for_full_verification"
    elif positive_signal_count > 0:
        status = "partial_user_progress"
        if cooldown_active:
            operator_action = "wait_for_replies_and_monitor_until_nudge_cooldown"
        elif no_progress_candidate_count > 0:
            operator_action = "send_no_progress_nudge_after_operator_review"
        else:
            operator_action = "collect_user_replies"
    else:
        status = "no_user_connectivity_evidence"
        if cooldown_active:
            operator_action = "wait_for_replies_and_monitor_until_nudge_cooldown"
        else:
            operator_action = "send_no_progress_nudge_after_operator_review"

    return {
        "status": status,
        "user_connectivity_proven": status == "verified_by_user_replies",
        "proven": status == "verified_by_user_replies",
        "target_active_user_count": target_active_count,
        "target_active_users": target_active_count,
        "confirmed_by_reply_count": done_updated_count,
        "failure_reply_count": failure_reply_count,
        "total_reply_count": total_replies,
        "positive_signal_count": positive_signal_count,
        "positive_user_signals": positive_signal_count,
        "dry_run_progress_count": dry_run_progress_count,
        "any_progress_count": any_progress_count,
        "device_activity_count": device_activity_count,
        "subscription_pull_count": subscription_pull_count,
        "subscription_and_device_count": subscription_and_device_count,
        "unconfirmed_by_reply_count": unconfirmed_by_reply_count,
        "unverified_by_any_signal_count": unverified_by_any_signal_count,
        "no_progress_candidate_count": no_progress_candidate_count,
        "no_progress_candidate_source": "dry_run" if dry_run_usable else "last_apply",
        "cooldown_active": cooldown_active,
        "next_nudge_allowed_at": next_nudge_allowed_at if isinstance(next_nudge_allowed_at, str) else None,
        "legacy_transport_still_polling": legacy_transport_still_polling,
        "legacy_transport_severity": str(transport_usage_status.get("severity") or "unknown"),
        "single_stale_legacy_source": transport_single_stale_legacy,
        "legacy_migration_progress_fresh": migration_progress_fresh,
        "legacy_migration_progress_stale_after": legacy_migration_progress_status.get("stale_after")
        if isinstance(legacy_migration_progress_status.get("stale_after"), str)
        else None,
        "legacy_migration_progress_seconds_until_stale": legacy_migration_progress_status.get(
            "seconds_until_stale"
        ),
        "legacy_migration_replies_fresh": migration_replies_fresh,
        "legacy_migration_replies_stale_after": legacy_migration_replies_status.get("stale_after")
        if isinstance(legacy_migration_replies_status.get("stale_after"), str)
        else None,
        "legacy_migration_replies_seconds_until_stale": legacy_migration_replies_status.get(
            "seconds_until_stale"
        ),
        "blockers": sorted(set(blockers)),
        "operator_action": operator_action,
        "privacy_ok": privacy_ok,
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
    }

def build_anti_dpi_readiness(
    *,
    subscription_payload_status: dict,
    transport_usage_status: dict,
    client_evidence_status: dict,
) -> dict:
    anti_dpi = (
        subscription_payload_status.get("anti_dpi")
        if isinstance(subscription_payload_status.get("anti_dpi"), dict)
        else {}
    )
    blockers: list[str] = []
    warnings: list[str] = []

    subscription_safe = subscription_payload_status.get("status") == "safe"
    subscription_fresh = subscription_payload_status.get("fresh") is True
    anti_dpi_ready = anti_dpi.get("ready") is True
    primary_ready = anti_dpi.get("primary_reality_443_ready") is True
    secondary_ready = anti_dpi.get("secondary_reality_port_ready") is True
    reality_only = anti_dpi.get("reality_only") is True
    transport_privacy_ok = (
        transport_usage_status.get("privacy_ok") is True
        if transport_usage_status.get("available") is True
        else True
    )
    privacy_ok = (
        subscription_payload_status.get("privacy_ok") is True
        and anti_dpi.get("privacy_ok") is True
        and transport_privacy_ok
    )
    legacy_transport_attention = transport_usage_status.get("status") == "attention"
    restart_relevant_legacy = transport_usage_status.get("restart_relevant") is True
    external_evidence_complete = client_evidence_status.get("goal_complete") is True
    remote_collection_ready = client_evidence_status.get("safe_remote_request_collection_ready") is True

    if not subscription_safe:
        blockers.append("subscription_payload_not_safe")
    if not subscription_fresh:
        blockers.append("subscription_payload_not_fresh")
    if not anti_dpi_ready:
        blockers.append("anti_dpi_subscription_profiles_not_ready")
    if not primary_ready:
        blockers.append("anti_dpi_primary_reality_443_missing")
    if not reality_only:
        blockers.append("anti_dpi_subscription_not_reality_only")
    if not privacy_ok:
        blockers.append("privacy_not_confirmed")
    if transport_usage_status.get("available") is not True:
        warnings.append("transport_usage_evidence_missing")
    if restart_relevant_legacy:
        blockers.append("legacy_transport_restart_relevant_error_seen")

    if not secondary_ready:
        warnings.append("anti_dpi_secondary_reality_port_missing")
    if legacy_transport_attention:
        warnings.append("legacy_transport_still_polling")
    if not external_evidence_complete:
        warnings.append("external_provider_coverage_not_fully_verified")
    if remote_collection_ready and not external_evidence_complete:
        warnings.append("remote_client_replies_ready_to_collect")

    blockers.extend(
        str(item)
        for item in (anti_dpi.get("blockers") or [])
        if isinstance(item, str)
    )
    warnings.extend(
        str(item)
        for item in (anti_dpi.get("warnings") or [])
        if isinstance(item, str)
    )

    blockers = sorted(set(blockers))
    warnings = sorted(set(warnings))
    distribution_ready = (
        subscription_safe
        and subscription_fresh
        and anti_dpi_ready
        and primary_ready
        and reality_only
        and privacy_ok
        and not restart_relevant_legacy
    )
    coverage_proven = distribution_ready and external_evidence_complete and not legacy_transport_attention
    recommended_ports = [
        port
        for port in (
            safe_int(item)
            for item in (anti_dpi.get("recommended_port_order") or [])
        )
        if port > 0
    ]
    subscription_ports = [
        port
        for port in (
            safe_int(item)
            for item in (subscription_payload_status.get("ports") or [])
        )
        if port > 0
    ]

    if blockers:
        status = "blocked"
        operator_action = "fix_anti_dpi_subscription_or_privacy_before_rotation"
    elif coverage_proven:
        status = "ready"
        operator_action = "observe"
    else:
        status = "attention"
        if legacy_transport_attention:
            operator_action = str(
                transport_usage_status.get("operator_action")
                or "migrate_legacy_clients_to_reality"
            )
        elif remote_collection_ready:
            operator_action = "collect_remote_client_replies"
        elif not secondary_ready:
            operator_action = "add_or_verify_secondary_reality_port"
        else:
            operator_action = "collect_external_provider_coverage_evidence"

    return {
        "status": status,
        "distribution_ready": distribution_ready,
        "all_provider_coverage_proven": coverage_proven,
        "subscription_safe": subscription_safe,
        "subscription_fresh": subscription_fresh,
        "anti_dpi_subscription_ready": anti_dpi_ready,
        "primary_reality_443_ready": primary_ready,
        "secondary_reality_port_ready": secondary_ready,
        "reality_only": reality_only,
        "legacy_transport_attention": legacy_transport_attention,
        "legacy_transport_severity": str(transport_usage_status.get("severity") or "unknown"),
        "restart_relevant_legacy": restart_relevant_legacy,
        "external_evidence_complete": external_evidence_complete,
        "remote_collection_ready": remote_collection_ready,
        "recommended_port_order": recommended_ports,
        "recommended_ports": recommended_ports,
        "ports": subscription_ports,
        "checked_subscription_count": safe_int(
            anti_dpi.get("checked_subscription_count"),
            safe_int(subscription_payload_status.get("checked_subscription_count")),
        ),
        "ready_subscription_count": safe_int(anti_dpi.get("ready_subscription_count")),
        "blockers": blockers,
        "warnings": warnings,
        "operator_action": operator_action,
        "privacy_ok": privacy_ok,
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "automatic_restart_allowed": False,
    }

def build_next_safe_action(
    *,
    restart_guard: dict,
    subscription_payload_status: dict,
    transport_usage_status: dict,
    anti_dpi_readiness: dict,
    user_connectivity_verification: dict,
    legacy_no_progress_nudge_status: dict,
    legacy_no_progress_nudge_dry_run_status: dict,
    overall_operator_action: str,
) -> dict:
    blocked_actions = ["restart_x-ui", "restart_nl_server", "full_server_restart"]

    def readonly_refresh_actions(*, include_subscription_payload: bool = False, include_dry_run: bool = False) -> list[str]:
        actions: list[str] = []
        if include_subscription_payload:
            actions.append("refresh_subscription_payload_status")
        if transport_usage_status.get("fresh") is not True:
            actions.append("collect_transport_usage_evidence")
        if user_connectivity_verification.get("legacy_migration_progress_fresh") is not True:
            actions.append("collect_legacy_migration_progress")
        if user_connectivity_verification.get("legacy_migration_replies_fresh") is not True:
            actions.append("collect_legacy_migration_replies")
        if include_dry_run:
            actions.append("refresh_no_progress_nudge_dry_run")
        return actions

    immediate_readonly_actions = readonly_refresh_actions()
    operator_review_required = True
    user_message_allowed_after_review = False
    earliest_mutation_at = None

    dry_run_available = legacy_no_progress_nudge_dry_run_status.get("available") is True
    dry_run_fresh = legacy_no_progress_nudge_dry_run_status.get("fresh") is True
    dry_run_stale_after = (
        legacy_no_progress_nudge_dry_run_status.get("stale_after")
        if isinstance(legacy_no_progress_nudge_dry_run_status.get("stale_after"), str)
        else None
    )
    dry_run_ready = (
        dry_run_available
        and legacy_no_progress_nudge_dry_run_status.get("status") == "dry_run"
        and dry_run_fresh
        and legacy_no_progress_nudge_dry_run_status.get("privacy_ok") is True
    )
    dry_run_refresh_required = dry_run_available and not dry_run_ready
    subscription_payload_fresh = subscription_payload_status.get("fresh") is True
    subscription_payload_stale_after = (
        subscription_payload_status.get("stale_after")
        if isinstance(subscription_payload_status.get("stale_after"), str)
        else None
    )
    transport_usage_fresh = transport_usage_status.get("fresh") is True
    transport_usage_stale_after = (
        transport_usage_status.get("stale_after")
        if isinstance(transport_usage_status.get("stale_after"), str)
        else None
    )
    legacy_migration_progress_fresh = (
        user_connectivity_verification.get("legacy_migration_progress_fresh") is True
    )
    legacy_migration_progress_stale_after = (
        user_connectivity_verification.get("legacy_migration_progress_stale_after")
        if isinstance(
            user_connectivity_verification.get("legacy_migration_progress_stale_after"),
            str,
        )
        else None
    )
    legacy_migration_replies_fresh = (
        user_connectivity_verification.get("legacy_migration_replies_fresh") is True
    )
    legacy_migration_replies_stale_after = (
        user_connectivity_verification.get("legacy_migration_replies_stale_after")
        if isinstance(
            user_connectivity_verification.get("legacy_migration_replies_stale_after"),
            str,
        )
        else None
    )
    cooldown_active_for_action = user_connectivity_verification.get("cooldown_active") is True
    no_progress_count_for_action = safe_int(
        user_connectivity_verification.get("no_progress_candidate_count")
    )
    deferred_readonly_actions: list[str] = []

    if restart_guard.get("guard_status") == "manual_scoped_restart_allowed":
        action = "manual_scoped_restart_after_operator_review"
        reason = str(restart_guard.get("restart_reason") or "restart explicitly recommended")
        blocked_actions = ["restart_x-ui", "restart_nl_server", "full_server_restart"]
        immediate_readonly_actions = ["capture_pre_restart_evidence"]
    elif subscription_payload_status.get("status") in {"stale", "missing"}:
        action = "refresh_subscription_payload_status"
        reason = "active subscription payload status is stale or missing"
        immediate_readonly_actions = readonly_refresh_actions(include_subscription_payload=True)
    elif subscription_payload_status.get("status") == "unsafe":
        action = "fix_subscription_payload_before_user_rotation"
        reason = "active subscription payload is unsafe"
    elif anti_dpi_readiness.get("distribution_ready") is not True:
        action = str(
            anti_dpi_readiness.get("operator_action")
            or "fix_anti_dpi_subscription_or_privacy_before_rotation"
        )
        reason = "anti-DPI distribution is not ready"
    elif dry_run_refresh_required:
        action = "refresh_no_progress_nudge_dry_run"
        reason = "no-progress dry-run candidate summary is stale"
        immediate_readonly_actions = readonly_refresh_actions(include_dry_run=True)
    elif user_connectivity_verification.get("user_connectivity_proven") is not True:
        earliest_mutation_at = user_connectivity_verification.get("next_nudge_allowed_at")
        if cooldown_active_for_action:
            action = "wait_for_nudge_cooldown_and_collect_readonly_evidence"
            reason = "no-progress nudge cooldown is active"
            blocked_actions.append("send_duplicate_no_progress_nudge_before_cooldown")
        elif no_progress_count_for_action > 0 and not dry_run_ready:
            action = "refresh_no_progress_nudge_dry_run"
            reason = "fresh no-progress dry-run is required before user nudge"
            user_message_allowed_after_review = False
            immediate_readonly_actions = readonly_refresh_actions(include_dry_run=True)
        elif no_progress_count_for_action > 0 and immediate_readonly_actions:
            action = "refresh_readonly_evidence_before_user_nudge"
            reason = "fresh read-only evidence is required before user nudge"
            user_message_allowed_after_review = False
        elif no_progress_count_for_action > 0:
            action = "review_and_send_no_progress_nudge"
            reason = "some active users still have no progress signal"
            user_message_allowed_after_review = True
        elif anti_dpi_readiness.get("remote_collection_ready") is True:
            action = "collect_remote_client_replies"
            reason = "external provider coverage is not fully verified"
        else:
            action = "collect_user_replies"
            reason = "user connectivity is not fully verified"
    elif transport_usage_status.get("status") == "attention":
        action = str(
            transport_usage_status.get("operator_action")
            or "monitor_legacy_transport"
        )
        reason = "legacy transport attention remains after user connectivity proof"
        operator_review_required = False
    else:
        action = "observe"
        reason = "distribution and user connectivity are verified"
        operator_review_required = False
        immediate_readonly_actions = []

    parsed_earliest_mutation = parse_utc_datetime(earliest_mutation_at)

    def valid_through_earliest_mutation(*, fresh: bool, stale_after: str | None) -> bool:
        if not fresh:
            return False
        if parsed_earliest_mutation is None:
            return True
        parsed_stale_after = parse_utc_datetime(stale_after)
        return parsed_stale_after is not None and parsed_stale_after >= parsed_earliest_mutation

    dry_run_valid_through_earliest_mutation = valid_through_earliest_mutation(
        fresh=dry_run_ready,
        stale_after=dry_run_stale_after,
    )
    transport_usage_valid_through_earliest_mutation = valid_through_earliest_mutation(
        fresh=transport_usage_fresh,
        stale_after=transport_usage_stale_after,
    )
    legacy_migration_progress_valid_through_earliest_mutation = valid_through_earliest_mutation(
        fresh=legacy_migration_progress_fresh,
        stale_after=legacy_migration_progress_stale_after,
    )
    legacy_migration_replies_valid_through_earliest_mutation = valid_through_earliest_mutation(
        fresh=legacy_migration_replies_fresh,
        stale_after=legacy_migration_replies_stale_after,
    )
    if (
        cooldown_active_for_action
        and no_progress_count_for_action > 0
        and transport_usage_fresh
        and not transport_usage_valid_through_earliest_mutation
    ):
        deferred_readonly_actions.append(
            "refresh_transport_usage_evidence_before_user_nudge"
        )
    if (
        cooldown_active_for_action
        and no_progress_count_for_action > 0
        and legacy_migration_progress_fresh
        and not legacy_migration_progress_valid_through_earliest_mutation
    ):
        deferred_readonly_actions.append(
            "collect_legacy_migration_progress_before_user_nudge"
        )
    if (
        cooldown_active_for_action
        and no_progress_count_for_action > 0
        and legacy_migration_replies_fresh
        and not legacy_migration_replies_valid_through_earliest_mutation
    ):
        deferred_readonly_actions.append(
            "collect_legacy_migration_replies_before_user_nudge"
        )
    if (
        cooldown_active_for_action
        and no_progress_count_for_action > 0
        and dry_run_ready
        and not dry_run_valid_through_earliest_mutation
    ):
        deferred_readonly_actions.append(
            "refresh_no_progress_nudge_dry_run_before_user_nudge"
        )
    subscription_payload_valid_through_earliest_mutation = valid_through_earliest_mutation(
        fresh=subscription_payload_fresh,
        stale_after=subscription_payload_stale_after,
    )
    if (
        cooldown_active_for_action
        and no_progress_count_for_action > 0
        and subscription_payload_status.get("status") == "safe"
        and subscription_payload_fresh
        and not subscription_payload_valid_through_earliest_mutation
    ):
        deferred_readonly_actions.append(
            "refresh_subscription_payload_status_before_user_nudge"
        )

    earliest_mutation_seconds_until = (
        max(int((parsed_earliest_mutation - datetime.now(timezone.utc)).total_seconds()), 0)
        if parsed_earliest_mutation is not None
        else None
    )

    return {
        "action": action,
        "reason": reason,
        "overall_operator_action": overall_operator_action,
        "operator_review_required": operator_review_required,
        "automatic_restart_allowed": False,
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "user_message_allowed_after_review": user_message_allowed_after_review,
        "earliest_mutation_at": earliest_mutation_at if isinstance(earliest_mutation_at, str) else None,
        "earliest_mutation_seconds_until": earliest_mutation_seconds_until,
        "blocked_actions": sorted(set(blocked_actions)),
        "immediate_readonly_actions": immediate_readonly_actions,
        "deferred_readonly_actions": deferred_readonly_actions,
        "restart_guard_status": str(restart_guard.get("guard_status") or "unknown"),
        "restart_scope": str(restart_guard.get("restart_scope") or "none"),
        "subscription_status": str(subscription_payload_status.get("status") or "unknown"),
        "subscription_payload_fresh": subscription_payload_fresh,
        "subscription_payload_stale_after": subscription_payload_stale_after,
        "subscription_payload_seconds_until_stale": subscription_payload_status.get(
            "seconds_until_stale"
        ),
        "subscription_payload_valid_through_earliest_mutation": (
            subscription_payload_valid_through_earliest_mutation
        ),
        "transport_usage_fresh": transport_usage_fresh,
        "transport_usage_stale_after": transport_usage_stale_after,
        "transport_usage_seconds_until_stale": transport_usage_status.get(
            "seconds_until_stale"
        ),
        "transport_usage_valid_through_earliest_mutation": (
            transport_usage_valid_through_earliest_mutation
        ),
        "legacy_migration_progress_fresh": legacy_migration_progress_fresh,
        "legacy_migration_progress_stale_after": legacy_migration_progress_stale_after,
        "legacy_migration_progress_seconds_until_stale": (
            user_connectivity_verification.get(
                "legacy_migration_progress_seconds_until_stale"
            )
        ),
        "legacy_migration_progress_valid_through_earliest_mutation": (
            legacy_migration_progress_valid_through_earliest_mutation
        ),
        "legacy_migration_replies_fresh": legacy_migration_replies_fresh,
        "legacy_migration_replies_stale_after": legacy_migration_replies_stale_after,
        "legacy_migration_replies_seconds_until_stale": (
            user_connectivity_verification.get(
                "legacy_migration_replies_seconds_until_stale"
            )
        ),
        "legacy_migration_replies_valid_through_earliest_mutation": (
            legacy_migration_replies_valid_through_earliest_mutation
        ),
        "anti_dpi_distribution_ready": anti_dpi_readiness.get("distribution_ready") is True,
        "user_connectivity_proven": user_connectivity_verification.get("user_connectivity_proven") is True,
        "legacy_transport_status": str(transport_usage_status.get("status") or "unknown"),
        "legacy_transport_restart_relevant": transport_usage_status.get("restart_relevant") is True,
        "cooldown_active": user_connectivity_verification.get("cooldown_active") is True,
        "no_progress_candidate_count": safe_int(
            user_connectivity_verification.get("no_progress_candidate_count")
        ),
        "no_progress_dry_run_available": dry_run_available,
        "no_progress_dry_run_fresh": dry_run_fresh,
        "no_progress_dry_run_ready_for_apply": dry_run_ready,
        "no_progress_dry_run_valid_through_earliest_mutation": dry_run_valid_through_earliest_mutation,
        "no_progress_dry_run_generated_at": legacy_no_progress_nudge_dry_run_status.get("generated_at")
        if isinstance(legacy_no_progress_nudge_dry_run_status.get("generated_at"), str)
        else None,
        "no_progress_dry_run_stale_after": dry_run_stale_after,
        "no_progress_dry_run_seconds_until_stale": legacy_no_progress_nudge_dry_run_status.get(
            "seconds_until_stale"
        ),
    }

overall_status = "critical" if failures else ("advisory" if warnings else "ok")
joined_problems = "\n".join(problem_lines).lower()
joined_warnings = "\n".join(warning_lines).lower()

if failures:
    if any(token in joined_problems for token in ("route loop", "socks5 unreachable", "xray not running", "x0tta-node.service not active", "singbox_tun not found", "boot validation fail")):
        failure_domain = "local_client"
    elif "critical packet loss" in joined_problems:
        failure_domain = "external_network"
    else:
        failure_domain = "unknown"
elif warnings:
    if "packet loss" in joined_warnings and "no packet loss" not in joined_warnings:
        failure_domain = "external_network"
    elif any(token in joined_warnings for token in ("watchdog", "boot validation", "x0tta-node")):
        failure_domain = "local_client"
    else:
        failure_domain = "none"
else:
    failure_domain = "none"

if overall_status in {"ok", "advisory"}:
    recommended_action = "observe"
elif failure_domain == "local_client":
    recommended_action = "local_soft_heal"
elif failure_domain == "external_network":
    recommended_action = "operator_review"
else:
    recommended_action = "operator_review"

restart_recommended = False
restart_scope = "none"
restart_reason = "transport healthy or restart not proven necessary"
server_operator_action = "observe_server"
if recommended_action == "local_soft_heal":
    server_operator_action = "local_soft_heal"
elif recommended_action == "operator_review":
    server_operator_action = "operator_review"
if failures and any("xray not running" in problem.lower() for problem in problem_lines):
    restart_recommended = True
    restart_scope = "xray"
    restart_reason = "xray process is missing"

transport_status = "healthy"
if failures:
    transport_status = "unhealthy"
elif warnings:
    transport_status = "advisory"

server_match = re.search(r"Server:\s*([0-9.]+):(\d+)\s+\|\s+SOCKS5:\s*([^:]+):(\d+)\s+\(([^)]+)\)", text)
tcp_match = re.search(r"ESTAB=\s*(\d+)\s+FIN-WAIT-2=\s*(\d+)\s+CLOSE-WAIT=\s*(\d+)", text)
loss_match = re.search(r"(?:Critical packet loss|High packet loss|Packet loss):\s*(\d+)%", text)
exit_ip_match = re.search(r"exit IP (?:is VPN server|differs from VPN server):\s*([0-9.]+)", text)

packet_loss_percent = None
if "No packet loss" in text:
    packet_loss_percent = 0
elif loss_match:
    packet_loss_percent = int(loss_match.group(1))

client_evidence_status = read_client_evidence_status()
subscription_payload_status = read_subscription_payload_status()
transport_usage_status = read_transport_usage_status()
legacy_migration_status = read_legacy_migration_status()
legacy_migration_replies_status = read_legacy_migration_replies_status()
legacy_migration_progress_status = read_legacy_migration_progress_status()
legacy_no_progress_nudge_status = read_legacy_no_progress_nudge_status()
legacy_no_progress_nudge_dry_run_status = read_legacy_no_progress_nudge_dry_run_status()
user_connectivity_verification = build_user_connectivity_verification(
    subscription_payload_status=subscription_payload_status,
    transport_usage_status=transport_usage_status,
    legacy_migration_replies_status=legacy_migration_replies_status,
    legacy_migration_progress_status=legacy_migration_progress_status,
    legacy_no_progress_nudge_status=legacy_no_progress_nudge_status,
    legacy_no_progress_nudge_dry_run_status=legacy_no_progress_nudge_dry_run_status,
)
anti_dpi_readiness = build_anti_dpi_readiness(
    subscription_payload_status=subscription_payload_status,
    transport_usage_status=transport_usage_status,
    client_evidence_status=client_evidence_status,
)
overall_operator_action = combine_operator_action(
    server_operator_action,
    str(client_evidence_status.get("operator_action") or "operator_review"),
)
if subscription_payload_status.get("status") == "unsafe":
    overall_operator_action = "operator_review_subscription_payload"
elif transport_usage_status.get("status") == "attention":
    if legacy_migration_status.get("status") == "ready":
        if legacy_migration_replies_status.get("status") in {
            "partial_client_replies",
            "all_reported_updated_by_count",
        }:
            overall_operator_action = str(
                legacy_migration_replies_status.get("operator_action")
                or "continue_collecting_legacy_migration_replies"
            )
        elif legacy_migration_progress_status.get("status") in {
            "migration_progress_seen",
            "migration_partial_signal_seen",
            "all_active_device_activity_seen_after_message",
        }:
            overall_operator_action = str(
                legacy_migration_progress_status.get("operator_action")
                or "monitor_remaining_client_replies_and_legacy_transport"
            )
        else:
            overall_operator_action = str(
                legacy_migration_status.get("operator_action")
                or "ask_legacy_clients_to_refresh_reality_profile"
            )
    else:
        overall_operator_action = str(
            transport_usage_status.get("operator_action")
            or "check_legacy_clients_and_migrate_to_reality"
        )
restart_guard = build_restart_guard(
    restart_recommended=restart_recommended,
    restart_scope=restart_scope,
    restart_reason=restart_reason,
    overall_status=overall_status,
    transport_status=transport_status,
    server_operator_action=server_operator_action,
    client_evidence_status=client_evidence_status,
)

payload = {
    "schema_version": 1,
    "source": "scripts/vpn_status.sh",
    "raw_result": raw_result,
    "overall_status": overall_status,
    "transport_status": transport_status,
    "application_status": "healthy" if failures == 0 else "unhealthy",
    "provider_status": "not_evaluated",
    "failure_domain": failure_domain,
    "recommended_action": recommended_action,
    "mutation_allowed": False,
    "local_mutation_allowed": False,
    "nl_mutation_allowed": False,
    "automatic_restart_allowed": False,
    "restart_recommended": restart_recommended,
    "restart_scope": restart_scope,
    "restart_reason": restart_reason,
    "restart_guard": restart_guard,
    "server_operator_action": server_operator_action,
    "overall_operator_action": overall_operator_action,
    "exit_code": exit_code,
    "failures": failures,
    "warnings": warnings,
    "problems": problem_lines,
    "warnings_detail": warning_lines,
    "evidence": evidence_lines,
    "client_evidence": client_evidence_status,
    "subscription_payload": subscription_payload_status,
    "transport_usage": transport_usage_status,
    "legacy_migration": legacy_migration_status,
    "legacy_migration_replies": legacy_migration_replies_status,
    "legacy_migration_progress": legacy_migration_progress_status,
    "legacy_no_progress_nudge": legacy_no_progress_nudge_status,
    "legacy_no_progress_nudge_dry_run": legacy_no_progress_nudge_dry_run_status,
    "user_connectivity": user_connectivity_verification,
    "user_connectivity_verification": user_connectivity_verification,
    "anti_dpi_readiness": anti_dpi_readiness,
}

if subscription_payload_status.get("status") == "unsafe":
    payload["overall_status"] = "advisory" if payload["overall_status"] == "ok" else payload["overall_status"]
    payload["recommended_action"] = "operator_review"
    payload["warnings_detail"].append("⚠ subscription payload canary reports unsafe active subscription output")
    payload["warnings"] = len(payload["warnings_detail"])
elif transport_usage_status.get("status") == "attention":
    payload["overall_status"] = "advisory" if payload["overall_status"] == "ok" else payload["overall_status"]
    payload["recommended_action"] = "operator_review"
    payload["warnings_detail"].append("transport usage evidence reports legacy transport attention")
    payload["warnings"] = len(payload["warnings_detail"])
    if legacy_migration_status.get("status") == "ready":
        if legacy_migration_replies_status.get("status") in {
            "partial_client_replies",
            "all_reported_updated_by_count",
        }:
            payload["overall_operator_action"] = str(
                legacy_migration_replies_status.get("operator_action")
                or "continue_collecting_legacy_migration_replies"
            )
        elif legacy_migration_progress_status.get("status") in {
            "migration_progress_seen",
            "migration_partial_signal_seen",
            "all_active_device_activity_seen_after_message",
        }:
            payload["overall_operator_action"] = str(
                legacy_migration_progress_status.get("operator_action")
                or "monitor_remaining_client_replies_and_legacy_transport"
            )
        else:
            payload["overall_operator_action"] = str(
                legacy_migration_status.get("operator_action")
                or "ask_legacy_clients_to_refresh_reality_profile"
            )
    else:
        payload["overall_operator_action"] = str(
            transport_usage_status.get("operator_action")
            or "check_legacy_clients_and_migrate_to_reality"
        )
elif transport_usage_status.get("status") == "stale":
    payload["overall_status"] = "advisory" if payload["overall_status"] == "ok" else payload["overall_status"]
    payload["recommended_action"] = "operator_review"
    payload["warnings_detail"].append("transport usage evidence is stale")
    payload["warnings"] = len(payload["warnings_detail"])
    payload["overall_operator_action"] = "refresh_transport_usage_evidence"

if (
    subscription_payload_status.get("available") is True
    and anti_dpi_readiness.get("status") in {"blocked", "attention"}
    and not user_connectivity_verification.get("user_connectivity_proven")
):
    payload["overall_status"] = "advisory" if payload["overall_status"] == "ok" else payload["overall_status"]
    payload["recommended_action"] = "operator_review"
    payload["warnings_detail"].append("anti-DPI readiness is not fully verified")
    payload["warnings"] = len(payload["warnings_detail"])
    if anti_dpi_readiness.get("status") == "blocked":
        payload["overall_operator_action"] = str(
            anti_dpi_readiness.get("operator_action")
            or "fix_anti_dpi_subscription_or_privacy_before_rotation"
        )
    elif payload.get("overall_operator_action") in {"observe", "observe_server_operator_review"}:
        payload["overall_operator_action"] = str(
            anti_dpi_readiness.get("operator_action")
            or "collect_external_provider_coverage_evidence"
        )

if user_connectivity_verification.get("target_active_user_count", 0) > 0 and not user_connectivity_verification.get("user_connectivity_proven"):
    payload["overall_status"] = "advisory" if payload["overall_status"] == "ok" else payload["overall_status"]
    payload["recommended_action"] = "operator_review"
    payload["warnings_detail"].append("user connectivity is not fully verified by replies")
    payload["warnings"] = len(payload["warnings_detail"])
    if payload.get("overall_operator_action") in {"observe", "observe_server_operator_review"}:
        payload["overall_operator_action"] = str(
            user_connectivity_verification.get("operator_action") or "collect_user_replies"
        )

payload["next_safe_action"] = build_next_safe_action(
    restart_guard=payload["restart_guard"],
    subscription_payload_status=subscription_payload_status,
    transport_usage_status=transport_usage_status,
    anti_dpi_readiness=anti_dpi_readiness,
    user_connectivity_verification=user_connectivity_verification,
    legacy_no_progress_nudge_status=legacy_no_progress_nudge_status,
    legacy_no_progress_nudge_dry_run_status=legacy_no_progress_nudge_dry_run_status,
    overall_operator_action=str(payload.get("overall_operator_action") or "operator_review"),
)

if server_match:
    payload.update(
        {
            "vpn_server": server_match.group(1),
            "vpn_port": int(server_match.group(2)),
            "socks_host": server_match.group(3),
            "socks_port": int(server_match.group(4)),
            "socks_port_source": server_match.group(5),
        }
    )

if tcp_match:
    payload["tcp_connections"] = {
        "established": int(tcp_match.group(1)),
        "fin_wait_2": int(tcp_match.group(2)),
        "close_wait": int(tcp_match.group(3)),
    }

if packet_loss_percent is not None:
    payload["packet_loss_percent"] = packet_loss_percent
if exit_ip_match:
    payload["exit_ip"] = exit_ip_match.group(1)

if raw_result == "UNKNOWN" and not failures:
    payload["overall_status"] = "critical"
    payload["failure_domain"] = "unknown"
    payload["recommended_action"] = "operator_review"
    payload["overall_operator_action"] = "operator_review"
    payload["restart_guard"] = build_restart_guard(
        restart_recommended=False,
        restart_scope="none",
        restart_reason="vpn_status result could not be parsed",
        overall_status="critical",
        transport_status=payload.get("transport_status", "unknown"),
        server_operator_action="operator_review",
        client_evidence_status=client_evidence_status,
    )
    payload["problems"].append("Unable to parse vpn_status result line")

print(json.dumps(payload, indent=2, sort_keys=True))
PY
    exit "$CHILD_STATUS"
fi

# Colors
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
if [ "$NO_COLOR" -eq 1 ]; then
    RED=''; GREEN=''; YELLOW=''; CYAN=''; BOLD=''; NC=''
fi

FAIL_COUNT=0
WARN_COUNT=0

ok()   { echo -e "  ${GREEN}✓${NC} $*"; }
warn() { WARN_COUNT=$((WARN_COUNT + 1)); echo -e "  ${YELLOW}⚠${NC} $*"; }
fail() { FAIL_COUNT=$((FAIL_COUNT + 1)); echo -e "  ${RED}✗${NC} $*"; }

echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━ VPN Status ━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  Server: ${BOLD}$VPN_SERVER:$VPN_PORT${NC}  |  SOCKS5: ${BOLD}$SOCKS_HOST:$SOCKS_PORT${NC} ($SOCKS_PORT_SOURCE)"
echo -e "${CYAN}──────────────────────────────────────────────────────────────${NC}"

# 1. xray process
echo -e "\n${BOLD}[1] xray Process${NC}"
XRAY_PID=$(pgrep -f "xray run" 2>/dev/null | head -1 || true)
if [ -n "$XRAY_PID" ]; then
    XRAY_MEM=$(ps -o rss= -p "$XRAY_PID" 2>/dev/null | awk '{printf "%.1f MB", $1/1024}' || echo "?")
    ok "Running (PID $XRAY_PID, mem: $XRAY_MEM)"
else
    fail "xray not running"
fi

# 2. x0tta-node health loop
echo -e "\n${BOLD}[2] x0tta-node Health Loop${NC}"
if systemctl is-active --quiet x0tta-node.service 2>/dev/null; then
    ok "x0tta-node.service active"
elif systemctl is-active --quiet x0tta-vpn-watchdog.service 2>/dev/null; then
    warn "x0tta-node.service not active; watchdog is active, treating health loop as advisory"
else
    fail "x0tta-node.service not active"
fi

NODE_LOG=$(journalctl -u x0tta-node.service --no-pager --since "2 minutes ago" -n 40 2>/dev/null | grep "Network OK" | tail -1 || true)
if echo "$NODE_LOG" | grep -q "proxy=OK"; then
    ok "Recent health loop OK: $(sed 's/.*Network OK/Network OK/' <<< "$NODE_LOG")"
elif [ -n "$NODE_LOG" ]; then
    warn "Recent x0tta-node health loop did not confirm proxy OK: $NODE_LOG"
else
    warn "No recent x0tta-node Network OK log found"
fi

# 3. sing-box / TUN interface
echo -e "\n${BOLD}[3] TUN Interface${NC}"
if ip link show singbox_tun &>/dev/null; then
    TUN_ADDR=$(ip addr show singbox_tun 2>/dev/null | grep "inet " | awk '{print $2}' || echo "?")
    ok "singbox_tun up — addr: $TUN_ADDR"
else
    fail "singbox_tun not found"
fi

# 4. TCP connection states
echo -e "\n${BOLD}[4] TCP Connections to $VPN_SERVER${NC}"
SS_OUT=$(ss -tn "dst $VPN_SERVER" 2>/dev/null || true)
FW2=$(echo "$SS_OUT" | grep -c "FIN-WAIT-2" || true)
CW=$(echo "$SS_OUT"  | grep -c "CLOSE-WAIT" || true)
EST=$(echo "$SS_OUT" | grep -c "ESTAB"       || true)

echo "  ESTAB=${BOLD}$EST${NC}  FIN-WAIT-2=${BOLD}$FW2${NC}  CLOSE-WAIT=${BOLD}$CW${NC}"
[ "$EST"  -gt 0  ] && ok "Active connections: $EST"
[ "$FW2"  -ge 50 ] && fail "FIN-WAIT-2 critical: $FW2 (threshold 50)" || \
[ "$FW2"  -ge 10 ] && warn "FIN-WAIT-2 elevated: $FW2" || \
[ "$FW2"  -gt 0  ] && ok "FIN-WAIT-2 nominal: $FW2"
[ "$CW"   -ge 30 ] && fail "CLOSE-WAIT critical: $CW" || \
[ "$CW"   -gt 0  ] && warn "CLOSE-WAIT: $CW"

ROUTE_OUT=$(ip route get "$VPN_SERVER" 2>/dev/null | head -1 || true)
if echo "$ROUTE_OUT" | grep -q "singbox_tun"; then
    fail "Route loop risk: VPN server currently resolves via singbox_tun: $ROUTE_OUT"
elif [ -n "$ROUTE_OUT" ]; then
    ok "Route to VPN server bypasses tunnel: $ROUTE_OUT"
else
    fail "Cannot resolve route to VPN server"
fi

# 5. SOCKS5 proxy health
echo -e "\n${BOLD}[5] SOCKS5 Proxy Health${NC}"
PROXY_RESULT=$(python3 -c "
import socket, time, sys
try:
    t0 = time.monotonic()
    with socket.create_connection(('$SOCKS_HOST', $SOCKS_PORT), timeout=3) as s:
        s.send(b'\x05\x01\x00')
        resp = s.recv(2)
        lat = (time.monotonic() - t0) * 1000
        if resp == b'\x05\x00':
            print(f'OK {lat:.0f}')
        else:
            print(f'FAIL_RESP {resp.hex()}')
except Exception as e:
    print(f'FAIL_CONN {e}')
" 2>/dev/null)

if [[ "$PROXY_RESULT" == OK* ]]; then
    LAT="${PROXY_RESULT#OK }"
    ok "SOCKS5 alive — handshake latency: ${LAT}ms"
else
    fail "SOCKS5 unreachable: $PROXY_RESULT"
fi

# 6. External IP check through proxy
echo -e "\n${BOLD}[6] External Connectivity${NC}"
EXT_IP=$(curl -s --max-time 8 --proxy "socks5h://$SOCKS_HOST:$SOCKS_PORT" https://api.ipify.org 2>/dev/null || true)
if [[ "$EXT_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    if [ "$EXT_IP" = "$VPN_SERVER" ]; then
        ok "Internet reachable via VPN — exit IP is VPN server: ${BOLD}$EXT_IP${NC}"
    else
        warn "Internet reachable, but exit IP differs from VPN server: $EXT_IP"
    fi
else
    fail "Cannot reach internet through proxy"
fi

# 7. Packet loss
echo -e "\n${BOLD}[7] Packet Loss to VPN Server${NC}"
PING_OUT=$(ping -c 5 -W 2 -q "$VPN_SERVER" 2>/dev/null || true)
LOSS=$(echo "$PING_OUT" | grep -oP '\d+(?=% packet loss)' || echo "?")
RTT=$(echo "$PING_OUT"  | grep -oP 'rtt.*= \K[\d.]+(?=/)' || echo "?")
if [ "$LOSS" = "0" ]; then
    ok "No packet loss | RTT min: ${RTT}ms"
elif [ "$LOSS" = "?" ]; then
    warn "Ping unavailable"
elif [ "$LOSS" -ge 50 ]; then
    fail "Critical packet loss: ${LOSS}%"
elif [ "$LOSS" -ge 20 ]; then
    warn "High packet loss: ${LOSS}%"
else
    warn "Packet loss: ${LOSS}%"
fi

# 8. Watchdog metrics (if running)
echo -e "\n${BOLD}[8] Watchdog Metrics${NC}"
WD_OUT=$(curl -s --max-time 2 http://127.0.0.1:9091/metrics 2>/dev/null || true)
if [ -n "$WD_OUT" ]; then
    HEAL_CNT=$(echo "$WD_OUT" | grep "^vpn_heal_total " | awk '{print $2}' || echo "?")
    CHK_CNT=$(echo  "$WD_OUT" | grep "^vpn_checks_total " | awk '{print $2}' || echo "?")
    ok "Watchdog running — checks: $CHK_CNT, heals: $HEAL_CNT"
else
    warn "Watchdog not running (start: python3 src/network/vpn_watchdog.py)"
fi

# 9. Post-boot validation evidence
echo -e "\n${BOLD}[9] Post-Boot Validation${NC}"
if [ "$SKIP_BOOT_VALIDATION" = "1" ]; then
    warn "Boot validation evidence skipped by VPN_STATUS_SKIP_BOOT_VALIDATION=1"
else
    if systemctl is-enabled --quiet x0tta-vpn-boot-validate.timer 2>/dev/null; then
        ok "x0tta-vpn-boot-validate.timer enabled"
    else
        warn "x0tta-vpn-boot-validate.timer not enabled"
    fi

    CURRENT_BOOT_ID=$(cat /proc/sys/kernel/random/boot_id 2>/dev/null || echo "")
    if [ -r "$BOOT_VALIDATION_RESULT" ]; then
        BV_STATUS=$(grep '^status=' "$BOOT_VALIDATION_RESULT" | tail -1 | cut -d= -f2- || true)
        BV_BOOT_ID=$(grep '^boot_id=' "$BOOT_VALIDATION_RESULT" | tail -1 | cut -d= -f2- || true)
        BV_TIMESTAMP=$(grep '^timestamp=' "$BOOT_VALIDATION_RESULT" | tail -1 | cut -d= -f2- || true)
        BV_DETAIL=$(grep '^detail=' "$BOOT_VALIDATION_RESULT" | tail -1 | cut -d= -f2- || true)

        if [ "$BV_BOOT_ID" = "$CURRENT_BOOT_ID" ] && [ "$BV_STATUS" = "PASS" ]; then
            ok "Boot validation PASS for current boot — $BV_TIMESTAMP ($BV_DETAIL)"
        elif [ "$BV_BOOT_ID" = "$CURRENT_BOOT_ID" ] && [ "$BV_STATUS" = "FAIL" ]; then
            fail "Boot validation FAIL for current boot — $BV_TIMESTAMP ($BV_DETAIL)"
        elif [ -n "$BV_STATUS" ]; then
            warn "Boot validation result is not for current boot — status=$BV_STATUS timestamp=$BV_TIMESTAMP"
        else
            warn "Boot validation result is unreadable: $BOOT_VALIDATION_RESULT"
        fi
    else
        warn "Boot validation result not found: $BOOT_VALIDATION_RESULT"
    fi
fi

echo -e "\n${CYAN}──────────────────────────────────────────────────────────────${NC}"
echo -e "  Quick actions:"
echo -e "    ${YELLOW}bash scripts/vpn_heal.sh${NC}           — emergency heal"
echo -e "    ${YELLOW}python3 src/network/vpn_watchdog.py${NC} — start watchdog"
echo -e "    ${YELLOW}curl --proxy socks5h://$SOCKS_HOST:$SOCKS_PORT https://api.ipify.org${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

if [ "$FAIL_COUNT" -eq 0 ]; then
    echo "Result: PASS (warnings=$WARN_COUNT)"
else
    echo "Result: FAIL (failures=$FAIL_COUNT warnings=$WARN_COUNT)"
fi

if [ "$STRICT_CHECK" -eq 1 ] && [ "$FAIL_COUNT" -gt 0 ]; then
    exit 1
fi

exit 0
