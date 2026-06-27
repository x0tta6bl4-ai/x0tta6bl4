#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


DEFAULT_PACKET_PATH = Path("nl-diagnostics/nl-legacy-client-migration-packet-2026-06-05.json")
DEFAULT_JSON_OUT = Path("nl-diagnostics/nl-legacy-client-migration-replies-2026-06-05.json")
DEFAULT_MARKDOWN_OUT = Path("nl-diagnostics/nl-legacy-client-migration-replies-2026-06-05.md")
MAX_REPLY_BYTES = 64
ALLOWED_REPLIES = {
    "done updated": ("done", "updated"),
    "fail import": ("fail", "import"),
    "fail timeout": ("fail", "timeout"),
    "fail no-internet": ("fail", "no-internet"),
}
REPORTER_LABEL_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")

FORBIDDEN_REPLY_PATTERNS = {
    "vpn_uri": re.compile(r"\b(?:vless|vmess|trojan|ss)://", re.IGNORECASE),
    "subscription_path": re.compile(r"/sub/[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]{8,}"),
    "uuid": re.compile(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        re.IGNORECASE,
    ),
    "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    "ipv4": re.compile(
        r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"
    ),
    "http_url": re.compile(r"\bhttps?://", re.IGNORECASE),
    "telegram_handle": re.compile(r"@[A-Za-z0-9_]{4,}"),
    "phone": re.compile(r"\+\d[\d .()_-]{8,}\d\b"),
}


class LegacyMigrationReplyError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json_with_source(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except FileNotFoundError as exc:
        raise LegacyMigrationReplyError(f"required JSON artifact missing: {path}") from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise LegacyMigrationReplyError(f"{path} is not valid UTF-8 JSON: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise LegacyMigrationReplyError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise LegacyMigrationReplyError(f"{path} must be a JSON object")
    return payload, {
        "path": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def validate_expected_sha256(actual_sha256: str, expected_sha256: str) -> None:
    expected = (expected_sha256 or "").strip().lower()
    if not expected:
        return
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise LegacyMigrationReplyError("--expect-packet-sha256 must be a 64-character hex digest")
    if actual_sha256.lower() != expected:
        raise LegacyMigrationReplyError(
            "migration packet sha256 mismatch: "
            f"expected={expected}, actual={actual_sha256.lower()}"
        )


def secret_findings(value: Any, *, path: str = "$") -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            findings.extend(secret_findings(nested, path=f"{path}.{key}"))
        return findings
    if isinstance(value, list):
        for index, nested in enumerate(value):
            findings.extend(secret_findings(nested, path=f"{path}[{index}]"))
        return findings
    if not isinstance(value, str):
        return findings
    for name, pattern in FORBIDDEN_REPLY_PATTERNS.items():
        match = pattern.search(value)
        if match:
            findings.append({"path": path, "kind": name, "sample": match.group(0)[:80]})
    return findings


def parse_reply(reply: str) -> dict[str, str]:
    if len((reply or "").encode("utf-8")) > MAX_REPLY_BYTES:
        raise LegacyMigrationReplyError(f"reply is too long: max_bytes={MAX_REPLY_BYTES}")
    findings = secret_findings(reply)
    if findings:
        details = ", ".join(f"{item['path']}:{item['kind']}" for item in findings[:5])
        raise LegacyMigrationReplyError(f"unsafe tester reply: {details}")
    normalized = " ".join((reply or "").strip().lower().replace("_", "-").split())
    if normalized not in ALLOWED_REPLIES:
        raise LegacyMigrationReplyError(
            "reply must be exactly one of: done updated, fail import, fail timeout, fail no-internet"
        )
    result, symptom = ALLOWED_REPLIES[normalized]
    return {"reply": normalized, "result": result, "symptom": symptom}


def validate_reporter_label(value: str) -> str:
    label = (value or "").strip().lower()
    if not REPORTER_LABEL_RE.fullmatch(label):
        raise LegacyMigrationReplyError(
            "--reporter-label must match ^[a-z0-9][a-z0-9_-]{0,39}$ and must not contain private identifiers"
        )
    findings = secret_findings(label)
    if findings:
        raise LegacyMigrationReplyError("--reporter-label contains private identifier-like text")
    return label


def read_reply_from_args(args: argparse.Namespace) -> str:
    sources = [bool(args.reply), args.reply_file is not None, bool(args.reply_stdin)]
    if sum(1 for value in sources if value) != 1:
        raise LegacyMigrationReplyError("provide exactly one reply source: --reply, --reply-file, or --reply-stdin")
    if args.reply_file is not None:
        try:
            return args.reply_file.read_text(encoding="utf-8")
        except OSError as exc:
            raise LegacyMigrationReplyError(f"cannot read reply file: {args.reply_file}") from exc
    if args.reply_stdin:
        return sys.stdin.read()
    return str(args.reply)


def validate_packet(packet: dict[str, Any]) -> None:
    if packet.get("decision") != "LEGACY_CLIENT_MIGRATION_PACKET_READY":
        raise LegacyMigrationReplyError("migration packet is not ready")
    send_policy = packet.get("send_policy") if isinstance(packet.get("send_policy"), dict) else {}
    if send_policy.get("automatic_broadcast_allowed") is True:
        raise LegacyMigrationReplyError("migration packet unexpectedly allows automatic broadcast")
    privacy = packet.get("privacy") if isinstance(packet.get("privacy"), dict) else {}
    privacy_flags = [
        "raw_user_ids_printed",
        "raw_chat_ids_printed",
        "raw_tokens_printed",
        "raw_subscription_urls_printed",
        "raw_vpn_uris_printed",
        "raw_uuid_printed",
        "raw_ip_printed",
        "raw_telegram_handle_printed",
    ]
    if any(privacy.get(flag) is not False for flag in privacy_flags):
        raise LegacyMigrationReplyError("migration packet privacy flags are not clean")


def load_existing(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"events": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LegacyMigrationReplyError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise LegacyMigrationReplyError(f"{path} must be a JSON object")
    events = payload.get("events")
    if not isinstance(events, list):
        payload["events"] = []
    return payload


def build_summary(
    *,
    packet: dict[str, Any],
    packet_source: dict[str, Any],
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    counts = Counter(str(event.get("reply") or "") for event in events)
    result_counts = Counter(str(event.get("result") or "") for event in events)
    symptom_counts = Counter(str(event.get("symptom") or "") for event in events)
    target = packet.get("target_audience") if isinstance(packet.get("target_audience"), dict) else {}
    active_count = int(target.get("active_subscription_count") or 0)
    done_count = int(counts.get("done updated", 0))
    if done_count <= 0:
        status = "no_client_replies"
        operator_action = "send_or_collect_legacy_migration_replies"
    elif active_count and done_count >= active_count:
        status = "all_reported_updated_by_count"
        operator_action = "refresh_transport_usage_evidence"
    else:
        status = "partial_client_replies"
        operator_action = "continue_collecting_legacy_migration_replies"
    return {
        "schema_version": 1,
        "source": "record_legacy_client_migration_reply.py",
        "generated_at": utc_now(),
        "status": status,
        "operator_action": operator_action,
        "packet": {
            "source": packet_source["path"],
            "sha256": packet_source["sha256"],
            "decision": packet.get("decision"),
            "target_active_subscription_count": active_count,
        },
        "total_replies": len(events),
        "done_updated_count": done_count,
        "failure_count": int(result_counts.get("fail", 0)),
        "reply_counts": dict(sorted(counts.items())),
        "result_counts": dict(sorted(result_counts.items())),
        "symptom_counts": dict(sorted(symptom_counts.items())),
        "events": events,
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
    }


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# NL Legacy Client Migration Replies",
        "",
        f"- Status: `{summary['status']}`",
        f"- Operator action: `{summary['operator_action']}`",
        f"- Total replies: `{summary['total_replies']}`",
        f"- Done updated: `{summary['done_updated_count']}`",
        f"- Failures: `{summary['failure_count']}`",
        f"- Packet SHA-256: `{summary['packet']['sha256']}`",
        "",
        "## Reply Counts",
        "",
    ]
    for reply, count in (summary.get("reply_counts") or {}).items():
        lines.append(f"- `{reply}`: `{count}`")
    return "\n".join(lines) + "\n"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def validate_write_requires_sha256(args: argparse.Namespace) -> None:
    if args.write and not str(args.expect_packet_sha256 or "").strip():
        raise LegacyMigrationReplyError("--expect-packet-sha256 is required with --write")


def validate_write_reply_source(args: argparse.Namespace) -> None:
    if args.write and args.reply:
        raise LegacyMigrationReplyError("--write requires --reply-stdin or --reply-file; do not persist replies from --reply")


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record a privacy-safe legacy migration short reply.")
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--markdown-out", type=Path, default=DEFAULT_MARKDOWN_OUT)
    parser.add_argument("--reporter-label", default="anonymous-legacy-client")
    parser.add_argument("--reply")
    parser.add_argument("--reply-file", type=Path)
    parser.add_argument("--reply-stdin", action="store_true")
    parser.add_argument("--expect-packet-sha256", default="")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    validate_write_requires_sha256(args)
    validate_write_reply_source(args)
    packet, packet_source = load_json_with_source(args.packet)
    validate_expected_sha256(packet_source["sha256"], args.expect_packet_sha256)
    validate_packet(packet)
    parsed_reply = parse_reply(read_reply_from_args(args))
    reporter_label = validate_reporter_label(args.reporter_label)
    event = {
        "recorded_at": utc_now(),
        "reporter_label": reporter_label,
        **parsed_reply,
        "raw_reply_stored": False,
        "raw_user_id_stored": False,
        "raw_chat_id_stored": False,
    }

    existing = load_existing(args.json_out)
    events = [
        event
        for event in existing.get("events", [])
        if isinstance(event, dict)
    ]
    events.append(event)
    summary = build_summary(packet=packet, packet_source=packet_source, events=events)
    findings = secret_findings(summary)
    if findings:
        raise LegacyMigrationReplyError(
            "refusing to write unsafe migration reply summary: "
            + ", ".join(f"{item['path']}:{item['kind']}" for item in findings[:5])
        )

    if args.write:
        write_text(args.json_out, json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        write_text(args.markdown_out, render_markdown(summary))
    if args.json or not args.write:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except LegacyMigrationReplyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
