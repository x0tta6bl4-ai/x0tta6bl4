#!/usr/bin/env python3
"""Read sensitive NL source candidates and save redacted local review copies.

The script reads remote files into memory, redacts sensitive payloads, and writes
only redacted output under services/nl-server/redacted/. It never writes to NL and
never stores raw source locally.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
from datetime import datetime, timezone
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "manifest.json"
REDACTED_DIR = ROOT / "redacted"

ALLOWED_REMOTE_PATHS = {
    "/opt/ghost-access-bot/current/scripts/issue_offline_subscription.py",
    "/opt/ghost-access-bot/current/telegram_bot_simple.py",
}

REDACTIONS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "vpn_uri",
        re.compile(r"(?i)(?<![A-Za-z0-9_])(?:vless|trojan|ss)://[^\s\"'<>]+"),
        "<REDACTED_VPN_URI>",
    ),
    (
        "uuid",
        re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"),
        "<REDACTED_UUID>",
    ),
    (
        "private_key_block",
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL),
        "<REDACTED_PRIVATE_KEY_BLOCK>",
    ),
    (
        "token_assignment",
        re.compile(
            r"(?i)(\b(?:bot_token|telegram_token|api_token|secret_token|token)\b\s*[:=]\s*)([\"'])([^\"']{8,})([\"'])"
        ),
        r"\1\2<REDACTED_TOKEN>\4",
    ),
    (
        "private_key_assignment",
        re.compile(r"(?i)(\b(?:privateKey|private_key)\b\s*[:=]\s*)([\"'])([^\"']+)([\"'])"),
        r"\1\2<REDACTED_PRIVATE_KEY>\4",
    ),
    (
        "public_key_assignment",
        re.compile(r"(?i)(\b(?:publicKey|public_key)\b\s*[:=]\s*)([\"'])([^\"']+)([\"'])"),
        r"\1\2<REDACTED_PUBLIC_KEY>\4",
    ),
    (
        "short_id_assignment",
        re.compile(r"(?i)(\b(?:shortId|short_id)\b\s*[:=]\s*)([\"'])([0-9a-f]{4,32})([\"'])"),
        r"\1\2<REDACTED_SHORT_ID>\4",
    ),
    (
        "subscription_url_assignment",
        re.compile(r"(?i)(\b(?:subscription_url|sub_url|subscription_link)\b\s*[:=]\s*)([\"'])([^\"']+)([\"'])"),
        r"\1\2<REDACTED_SUBSCRIPTION_URL>\4",
    ),
)

POST_SCAN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("vpn_uri", re.compile(r"(?i)(?<![A-Za-z0-9_])(?:vless|trojan|ss)://")),
    ("private_key_block", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
    ("uuid", re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")),
    ("token_value_assignment", re.compile(r"(?i)\b(?:bot_token|telegram_token|api_token|secret_token|token)\b\s*[:=]\s*[\"'][^\"']{8,}[\"']")),
)


def load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def candidates_by_remote_path(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("remote_path")): item
        for item in manifest.get("source_candidates", [])
        if isinstance(item, dict)
    }


def fetch_remote_file(host: str, remote_path: str, timeout: int) -> str:
    remote_cmd = "LC_ALL=C cat -- " + shlex.quote(remote_path)
    proc = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", host, remote_cmd],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"ssh read failed for {remote_path}: {stderr}")
    return proc.stdout.decode("utf-8", errors="replace")


def redact_text(text: str) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {}
    redacted = text
    for name, pattern, replacement in REDACTIONS:
        redacted, count = pattern.subn(replacement, redacted)
        counts[name] = count
    return redacted, counts


def post_scan(text: str) -> list[str]:
    return [name for name, pattern in POST_SCAN_PATTERNS if pattern.search(text)]


def target_path(remote_path: str) -> Path:
    if remote_path.endswith("/telegram_bot_simple.py"):
        return REDACTED_DIR / "ghost-access" / "telegram_bot_simple.redacted.py"
    if remote_path.endswith("/issue_offline_subscription.py"):
        return REDACTED_DIR / "ghost-access" / "issue_offline_subscription.redacted.py"
    raise ValueError(f"unsupported remote path: {remote_path}")


def write_redacted(remote_path: str, redacted: str, counts: dict[str, int], raw_sha256: str, host: str) -> Path:
    target = target_path(remote_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# REDACTED REVIEW COPY - NOT DEPLOYABLE\n"
        f"# source: {remote_path}\n"
        "# raw content was read into memory only and not stored locally\n"
        "\n"
    )
    target.write_text(header + redacted, encoding="utf-8")
    meta = {
        "host": host,
        "remote_path": remote_path,
        "target_path": str(target.relative_to(ROOT)),
        "raw_sha256": raw_sha256,
        "redacted_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "redaction_counts": counts,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "deployable": False,
        "raw_saved_locally": False,
    }
    meta_path = target.with_suffix(target.suffix + ".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="nl")
    parser.add_argument("--remote-path", action="append", choices=sorted(ALLOWED_REMOTE_PATHS))
    parser.add_argument("--pull", action="store_true", help="Actually read and write redacted copies")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()

    manifest = load_manifest()
    if manifest.get("nl_write_allowed") is not False:
        raise SystemExit("Refusing to run: manifest must keep nl_write_allowed=false")

    selected = args.remote_path or sorted(ALLOWED_REMOTE_PATHS)
    known = candidates_by_remote_path(manifest)
    for remote_path in selected:
        if remote_path not in known:
            raise SystemExit(f"Refusing unknown manifest path: {remote_path}")

    if not args.pull:
        for remote_path in selected:
            print(f"DRY-RUN {remote_path} -> {target_path(remote_path).relative_to(ROOT)}")
        print("\nDry run only. Add --pull to read from NL and save redacted copies.")
        return 0

    written = 0
    for remote_path in selected:
        raw_text = fetch_remote_file(args.host, remote_path, args.timeout)
        raw_sha256 = hashlib.sha256(raw_text.encode("utf-8", errors="replace")).hexdigest()
        redacted, counts = redact_text(raw_text)
        residual = post_scan(redacted)
        if residual:
            print(f"BLOCKED {remote_path}: residual secret patterns={','.join(residual)}")
            continue
        target = write_redacted(remote_path, redacted, counts, raw_sha256, args.host)
        written += 1
        print(f"REDACTED {remote_path} -> {target.relative_to(ROOT)}")

    print(f"written={written}")
    return 0 if written == len(selected) else 1


if __name__ == "__main__":
    raise SystemExit(main())
