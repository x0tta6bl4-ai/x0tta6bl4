#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
from collections import Counter
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


DEFAULT_PACKET_PATH = Path("/var/lib/ghost-access/legacy-migration/latest.json")
DEFAULT_JSON_OUT = Path("/var/lib/ghost-access/legacy-migration/replies.json")
DEFAULT_MARKDOWN_OUT = Path("/var/lib/ghost-access/legacy-migration/replies.md")
DEFAULT_UNIT = "telegram-bot-simple.service"
CONFIRM_TEXT = "COLLECT_CURRENT_LEGACY_REPLIES"
MAX_REPLY_BYTES = 64
ALLOWED_REPLIES = {
    "done updated": ("done", "updated"),
    "fail import": ("fail", "import"),
    "fail timeout": ("fail", "timeout"),
    "fail no-internet": ("fail", "no-internet"),
}

FALLBACK_LINE_RE = re.compile(
    r"incoming fallback text=(?P<reply>(?:'[^']*'|\"[^\"]*\"|None)) "
    r"from chat_id=(?P<chat_id>\d+) user_id=(?P<user_id>\d+)"
)
FORBIDDEN_PATTERNS = {
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


class LegacyMigrationJournalReplyError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json_with_source(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except FileNotFoundError as exc:
        raise LegacyMigrationJournalReplyError(f"required JSON artifact missing: {path}") from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise LegacyMigrationJournalReplyError(f"{path} is not valid UTF-8 JSON: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise LegacyMigrationJournalReplyError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise LegacyMigrationJournalReplyError(f"{path} must be a JSON object")
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
        raise LegacyMigrationJournalReplyError("--expect-packet-sha256 must be a 64-character hex digest")
    if actual_sha256.lower() != expected:
        raise LegacyMigrationJournalReplyError(
            "migration packet sha256 mismatch: "
            f"expected={expected}, actual={actual_sha256.lower()}"
        )


def validate_write_args(args: argparse.Namespace) -> None:
    if not args.write:
        return
    has_expected_sha = bool(str(args.expect_packet_sha256 or "").strip())
    if not has_expected_sha and args.confirm_current_packet != CONFIRM_TEXT:
        raise LegacyMigrationJournalReplyError(
            f"--write requires --expect-packet-sha256 or --confirm-current-packet {CONFIRM_TEXT}"
        )


def validate_packet(packet: dict[str, Any]) -> None:
    if packet.get("decision") != "LEGACY_CLIENT_MIGRATION_PACKET_READY":
        raise LegacyMigrationJournalReplyError("migration packet is not ready")
    privacy = packet.get("privacy") if isinstance(packet.get("privacy"), dict) else {}
    flags = [
        "raw_user_ids_printed",
        "raw_chat_ids_printed",
        "raw_tokens_printed",
        "raw_subscription_urls_printed",
        "raw_vpn_uris_printed",
        "raw_uuid_printed",
        "raw_ip_printed",
        "raw_telegram_handle_printed",
    ]
    if any(privacy.get(flag) is not False for flag in flags):
        raise LegacyMigrationJournalReplyError("migration packet privacy flags are not clean")


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
    for name, pattern in FORBIDDEN_PATTERNS.items():
        match = pattern.search(value)
        if match:
            findings.append({"path": path, "kind": name, "sample": match.group(0)[:80]})
    return findings


def parse_reply(reply: str) -> dict[str, str]:
    if len((reply or "").encode("utf-8")) > MAX_REPLY_BYTES:
        raise LegacyMigrationJournalReplyError(f"reply is too long: max_bytes={MAX_REPLY_BYTES}")
    findings = secret_findings(reply)
    if findings:
        details = ", ".join(f"{item['path']}:{item['kind']}" for item in findings[:5])
        raise LegacyMigrationJournalReplyError(f"unsafe migration reply: {details}")
    normalized = " ".join((reply or "").strip().lower().replace("_", "-").split())
    if normalized not in ALLOWED_REPLIES:
        raise LegacyMigrationJournalReplyError("reply is not a legacy migration short reply")
    result, symptom = ALLOWED_REPLIES[normalized]
    return {"reply": normalized, "result": result, "symptom": symptom}


def reporter_label(*, packet_sha256: str, user_id: str) -> str:
    digest = hashlib.sha256(f"{packet_sha256}:{user_id}".encode("utf-8")).hexdigest()[:16]
    return f"legacy-client-{digest}"


def parse_journal_line(line: str, *, packet_sha256: str, order: int) -> tuple[dict[str, Any] | None, str | None]:
    match = FALLBACK_LINE_RE.search(line)
    if not match:
        return None, None
    try:
        raw_reply = ast.literal_eval(match.group("reply"))
    except (SyntaxError, ValueError):
        return None, "invalid_repr"
    if not isinstance(raw_reply, str):
        return None, "missing_text"
    try:
        parsed = parse_reply(raw_reply)
    except LegacyMigrationJournalReplyError as exc:
        if "unsafe" in str(exc):
            return None, "unsafe_reply"
        return None, "unrelated_text"
    return {
        "observed_order": order,
        "reporter_label": reporter_label(
            packet_sha256=packet_sha256,
            user_id=match.group("user_id"),
        ),
        **parsed,
        "raw_reply_stored": False,
        "raw_user_id_stored": False,
        "raw_chat_id_stored": False,
    }, None


def read_journal(*, unit: str, since: str, max_lines: int) -> str:
    command = [
        "journalctl",
        "-u",
        unit,
        "--since",
        since,
        "--no-pager",
        "-n",
        str(max_lines),
    ]
    completed = subprocess.run(
        command,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise LegacyMigrationJournalReplyError(
            f"journalctl failed for {unit}: exit_code={completed.returncode}"
        )
    return completed.stdout


def collect_events_from_text(journal_text: str, *, packet_sha256: str) -> tuple[list[dict[str, Any]], dict[str, int]]:
    latest_by_reporter: dict[str, dict[str, Any]] = {}
    stats: Counter[str] = Counter()
    for order, line in enumerate(journal_text.splitlines(), start=1):
        event, ignored_reason = parse_journal_line(line, packet_sha256=packet_sha256, order=order)
        if event is None:
            if ignored_reason:
                stats[f"ignored_{ignored_reason}"] += 1
            continue
        stats["accepted_reply_lines"] += 1
        latest_by_reporter[event["reporter_label"]] = event
    events = sorted(latest_by_reporter.values(), key=lambda item: int(item.get("observed_order") or 0))
    return events, dict(sorted(stats.items()))


def build_summary(
    *,
    packet: dict[str, Any],
    packet_source: dict[str, Any],
    events: list[dict[str, Any]],
    collection_stats: dict[str, int],
    since: str,
) -> dict[str, Any]:
    counts = Counter(str(event.get("reply") or "") for event in events)
    result_counts = Counter(str(event.get("result") or "") for event in events)
    symptom_counts = Counter(str(event.get("symptom") or "") for event in events)
    target = packet.get("target_audience") if isinstance(packet.get("target_audience"), dict) else {}
    active_count = int(target.get("active_subscription_count") or 0)
    done_count = int(counts.get("done updated", 0))
    if done_count <= 0 and not events:
        status = "no_client_replies"
        operator_action = "collect_legacy_migration_replies"
    elif active_count and done_count >= active_count:
        status = "all_reported_updated_by_count"
        operator_action = "refresh_transport_usage_evidence"
    else:
        status = "partial_client_replies"
        operator_action = "continue_collecting_legacy_migration_replies"
    return {
        "schema_version": 1,
        "source": "collect_legacy_migration_replies_from_bot_journal.py",
        "generated_at": utc_now(),
        "status": status,
        "operator_action": operator_action,
        "collection": {
            "source": "systemd_journal",
            "since": since,
            "stats": collection_stats,
            "dedupe": "latest_reply_per_pseudonymous_reporter",
        },
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
        f"- Journal since: `{summary['collection']['since']}`",
        "",
        "## Reply Counts",
        "",
    ]
    for reply, count in (summary.get("reply_counts") or {}).items():
        lines.append(f"- `{reply}`: `{count}`")
    if not (summary.get("reply_counts") or {}):
        lines.append("- none")
    return "\n".join(lines) + "\n"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def default_since(packet: dict[str, Any]) -> str:
    generated_at = str(packet.get("generated_at") or "").strip()
    if generated_at:
        return generated_at.replace("T", " ").replace("Z", " UTC")
    return "24 hours ago"


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Collect privacy-safe legacy migration replies from bot journal."
    )
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--markdown-out", type=Path, default=DEFAULT_MARKDOWN_OUT)
    parser.add_argument("--journal-file", type=Path)
    parser.add_argument("--unit", default=DEFAULT_UNIT)
    parser.add_argument("--since", default="")
    parser.add_argument("--max-lines", type=int, default=5000)
    parser.add_argument("--expect-packet-sha256", default="")
    parser.add_argument("--confirm-current-packet", default="")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    validate_write_args(args)
    packet, packet_source = load_json_with_source(args.packet)
    validate_expected_sha256(packet_source["sha256"], args.expect_packet_sha256)
    validate_packet(packet)
    since = args.since.strip() or default_since(packet)
    if args.journal_file is not None:
        try:
            journal_text = args.journal_file.read_text(encoding="utf-8")
        except OSError as exc:
            raise LegacyMigrationJournalReplyError(f"cannot read journal file: {args.journal_file}") from exc
    else:
        journal_text = read_journal(
            unit=str(args.unit),
            since=since,
            max_lines=max(1, int(args.max_lines or 1)),
        )
    events, collection_stats = collect_events_from_text(
        journal_text,
        packet_sha256=packet_source["sha256"],
    )
    summary = build_summary(
        packet=packet,
        packet_source=packet_source,
        events=events,
        collection_stats=collection_stats,
        since=since,
    )
    findings = secret_findings(summary)
    if findings:
        raise LegacyMigrationJournalReplyError(
            "refusing to write unsafe migration reply journal summary: "
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
    except LegacyMigrationJournalReplyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
