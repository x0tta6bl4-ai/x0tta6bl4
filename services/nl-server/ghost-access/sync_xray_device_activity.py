#!/usr/bin/env python3
"""Sync Ghost Access device activity from Xray access.log into SQLite.

Expected by telegram_bot_simple.py:

- `--once` performs one pass and exits with JSON on stdout
- default mode loops forever
- `--full-rescan` ignores the saved cursor once
- stdout is reserved for machine-readable JSON summaries
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GHOST_DB_PATH = ROOT / "x0tta6bl4.db"
SHARED_GHOST_DB_PATH = Path("/opt/ghost-access-bot/shared/x0tta6bl4.db")
DEFAULT_STATE_FILE_PATH = Path("/var/lib/ghost-access/xray_access_sync_state.json")

if not os.getenv("GHOST_ACCESS_DB_PATH"):
    if SHARED_GHOST_DB_PATH.exists():
        os.environ["GHOST_ACCESS_DB_PATH"] = str(SHARED_GHOST_DB_PATH)
    else:
        os.environ["GHOST_ACCESS_DB_PATH"] = str(DEFAULT_GHOST_DB_PATH)

sys.path.insert(0, str(ROOT))

from database import record_device_seen_by_email  # noqa: E402


DEFAULT_LOG_PATH = Path(os.getenv("XRAY_ACCESS_LOG_PATH", "/var/log/xray/access.log"))
DEFAULT_XUI_DB_PATH = Path(os.getenv("XUI_DB_PATH", "/etc/x-ui/x-ui.db"))
DEFAULT_STATE_PATH = Path(
    os.getenv(
        "DEVICE_ACTIVITY_STATE_FILE",
        str(DEFAULT_STATE_FILE_PATH if DEFAULT_STATE_FILE_PATH.parent.exists() else (ROOT / ".runtime" / "xray_access_sync_state.json")),
    )
)
DEFAULT_INTERVAL = int(os.getenv("DEVICE_ACTIVITY_SYNC_INTERVAL_SECONDS", "60"))
THINKING_CONTRACT = {
    "role": "xray_device_activity_sync_agent",
    "techniques": [
        "framing",
        "mape_k",
        "causal_analysis",
        "zero_trust_review",
    ],
    "safety_boundary": "sync only derived device activity; do not print raw secrets",
}

EMAIL_PATTERNS = (
    re.compile(r"\[(?P<email>[^\]\s]+)\s*->"),
    re.compile(r'email="?((?P<email>[^"\s]+))"?'),
    re.compile(r"\b(?P<email>[\w.\-+]+@[\w.\-]+)\b"),
)

IP_PATTERNS = (
    re.compile(r"(?:tcp|udp):(?P<ip>\d{1,3}(?:\.\d{1,3}){3})"),
    re.compile(r"\bfrom\s+(?P<ip>\d{1,3}(?:\.\d{1,3}){3})\b"),
    re.compile(r"\b(?P<ip>\d{1,3}(?:\.\d{1,3}){3})\:\d+\b"),
)

TIME_PATTERNS = (
    "%Y/%m/%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync Xray access log into Ghost Access devices.")
    parser.add_argument("--once", action="store_true", help="Process one pass and exit.")
    parser.add_argument("--full-rescan", action="store_true", help="Ignore saved cursor for this run.")
    parser.add_argument("--log-path", "--access-log", dest="log_path", default=str(DEFAULT_LOG_PATH))
    parser.add_argument("--state-file", default=str(DEFAULT_STATE_PATH))
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL)
    return parser.parse_args()


def _load_state(path: Path) -> dict:
    if not path.exists():
        return {"offset": 0, "inode": None, "updated_at": None}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"offset": 0, "inode": None, "updated_at": None}


def _save_state(path: Path, offset: int, inode: int | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "offset": offset,
                "inode": inode,
                "updated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            },
            ensure_ascii=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _extract_email(line: str) -> str | None:
    for pattern in EMAIL_PATTERNS:
        match = pattern.search(line)
        if match:
            return match.group("email")
    return None


def _extract_ip(line: str) -> str | None:
    for pattern in IP_PATTERNS:
        match = pattern.search(line)
        if match:
            return match.group("ip")
    return None


def _extract_seen_at(line: str) -> datetime:
    line = line.strip()
    for pattern in TIME_PATTERNS:
        try:
            probe = line[:19]
            return datetime.strptime(probe, pattern)
        except Exception:
            continue
    match = re.search(r"(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})", line)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y/%m/%d %H:%M:%S")
        except Exception:
            pass
    return datetime.now()


def _parse_xui_last_online(value: int | None) -> datetime | None:
    if not value:
        return None
    try:
        # x-ui stores Unix epoch in milliseconds.
        return datetime.fromtimestamp(int(value) / 1000, tz=UTC).replace(tzinfo=None)
    except Exception:
        return None


def _extract_latest_ip(raw_ips: str | None) -> str | None:
    if not raw_ips:
        return None
    try:
        parsed = json.loads(raw_ips)
        if isinstance(parsed, list) and parsed:
            return str(parsed[-1])
    except Exception:
        pass
    return None


def _thinking_context(task_type: str, goal: str, constraints: dict | None = None) -> dict:
    return {
        "contract": THINKING_CONTRACT,
        "applied": {
            "framing": {
                "problem": task_type,
                "goal": goal,
                "constraints": constraints or {},
                "safety_boundary": THINKING_CONTRACT["safety_boundary"],
            },
            "mape_k": ["monitor-log", "analyze-lines", "plan-cursor", "execute-sync", "knowledge-state"],
        },
    }


def _sync_from_xui_db(xui_db_path: Path) -> tuple[int, int, int]:
    if not xui_db_path.exists():
        return 0, 0, 0

    matched = 0
    updated = 0
    errors = 0

    try:
        with sqlite3.connect(xui_db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT ct.email, ct.last_online, ip.ips
                FROM client_traffics ct
                LEFT JOIN inbound_client_ips ip ON ip.client_email = ct.email
                WHERE ct.enable = 1 AND ct.last_online > 0 AND ct.email IS NOT NULL AND ct.email != ''
                """
            ).fetchall()
    except Exception:
        return 0, 0, 1

    for row in rows:
        matched += 1
        seen_at = _parse_xui_last_online(row["last_online"])
        if not seen_at:
            continue
        source_ip = _extract_latest_ip(row["ips"])
        try:
            if record_device_seen_by_email(row["email"], source_ip=source_ip, seen_at=seen_at):
                updated += 1
        except Exception:
            errors += 1

    return matched, updated, errors


def run_once(log_path: Path, state_path: Path, full_rescan: bool) -> tuple[int, dict]:
    if not log_path.exists():
        payload = {
            "ok": True,
            "log_path": str(log_path),
            "state_file": str(state_path),
            "matched": 0,
            "updated": 0,
            "skipped": 0,
            "offset": 0,
            "warning": "access log missing",
            "thinking": _thinking_context(
                "xray_device_activity_sync",
                "Handle a missing access log without failing the runtime loop.",
                {"full_rescan": full_rescan},
            ),
        }
        return 0, payload

    state = _load_state(state_path)
    stat = log_path.stat()
    inode = int(stat.st_ino)
    offset = 0 if full_rescan or state.get("inode") != inode else int(state.get("offset", 0) or 0)
    offset = max(0, min(offset, stat.st_size))

    matched = 0
    updated = 0
    skipped = 0
    errors = 0
    last_error = None

    with log_path.open("r", encoding="utf-8", errors="replace") as fh:
        fh.seek(offset)
        for raw_line in fh:
            line = raw_line.strip()
            if not line:
                continue

            email = _extract_email(line)
            if not email:
                skipped += 1
                continue

            matched += 1
            source_ip = _extract_ip(line)
            seen_at = _extract_seen_at(line)

            try:
                if record_device_seen_by_email(email, source_ip=source_ip, seen_at=seen_at):
                    updated += 1
                else:
                    skipped += 1
            except Exception as exc:
                errors += 1
                skipped += 1
                last_error = f"{type(exc).__name__}: {exc}"

        new_offset = fh.tell()

    _save_state(state_path, new_offset, inode)

    xui_matched, xui_updated, xui_errors = _sync_from_xui_db(DEFAULT_XUI_DB_PATH)
    matched += xui_matched
    updated += xui_updated
    errors += xui_errors

    payload = {
        "ok": True,
        "log_path": str(log_path),
        "xui_db_path": str(DEFAULT_XUI_DB_PATH),
        "state_file": str(state_path),
        "matched": matched,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "xui_matched": xui_matched,
        "xui_updated": xui_updated,
        "xui_errors": xui_errors,
        "reason": "ok" if errors == 0 else "partial-errors",
        "last_error": last_error,
        "offset": new_offset,
        "full_rescan": full_rescan,
        "thinking": _thinking_context(
            "xray_device_activity_sync",
            "Sync Xray and x-ui activity into Ghost Access device records.",
            {
                "full_rescan": full_rescan,
                "matched": matched,
                "errors": errors,
            },
        ),
    }
    return 0, payload


def main() -> int:
    args = parse_args()
    log_path = Path(args.log_path)
    state_path = Path(args.state_file)

    if args.once or args.full_rescan:
        code, payload = run_once(log_path, state_path, args.full_rescan)
        print(json.dumps(payload, ensure_ascii=True))
        return code

    while True:
        code, payload = run_once(log_path, state_path, False)
        print(json.dumps(payload, ensure_ascii=True), flush=True)
        if code != 0:
            return code
        time.sleep(max(5, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
