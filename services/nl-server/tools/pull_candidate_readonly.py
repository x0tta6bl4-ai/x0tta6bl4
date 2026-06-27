#!/usr/bin/env python3
"""Read NL source candidates into local quarantine, never to NL.

Default mode lists candidates only. Use --pull explicitly to read files from NL.
The script stores accepted files under services/nl-server/.quarantine/, which is
git-ignored by default.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "manifest.json"
QUARANTINE = ROOT / ".quarantine"

ALLOWED_PREFIXES = (
    "/opt/x0tta6bl4-mesh/scripts/",
    "/opt/ghost-access-bot/current/",
    "/mnt/projects/src/network/",
    "/mnt/projects/scripts/",
)

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[bytes]], ...] = (
    ("vpn_uri", re.compile(rb"(?i)\b(vless|trojan|ss)://")),
    ("private_key_block", re.compile(rb"BEGIN (RSA|OPENSSH|PRIVATE) KEY")),
    (
        "token_assignment",
        re.compile(
            rb"(?i)\b(bot_token|telegram_token|api_token|secret_token)\b\s*[:=]\s*[\"'][^\"']{8,}[\"']"
        ),
    ),
    (
        "private_key_assignment",
        re.compile(rb"(?i)\b(privateKey|private_key)\b\s*[:=]\s*[\"'][A-Za-z0-9_/\-+=]{16,}[\"']"),
    ),
    (
        "uuid_literal",
        re.compile(
            rb"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
        ),
    ),
    (
        "short_id_assignment",
        re.compile(rb"(?i)\b(shortId|short_id)\b\s*[:=]\s*[\"'][0-9a-f]{6,32}[\"']"),
    ),
)


def load_manifest() -> dict:
    with MANIFEST.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def iter_candidates(manifest: dict, component: str | None, priority: str | None) -> list[dict]:
    candidates = manifest.get("source_candidates", [])
    if component:
        candidates = [item for item in candidates if item.get("component") == component]
    if priority:
        candidates = [item for item in candidates if item.get("priority") == priority]
    return candidates


def validate_candidate(candidate: dict) -> None:
    remote_path = candidate.get("remote_path", "")
    if not remote_path.startswith(ALLOWED_PREFIXES):
        raise ValueError(f"remote path is outside the allowed source prefixes: {remote_path}")
    intended = candidate.get("intended_local_path", "")
    if not intended.startswith("services/nl-server/"):
        raise ValueError(f"intended local path is outside services/nl-server: {intended}")


def scan_for_secrets(data: bytes) -> list[str]:
    hits: list[str] = []
    for name, pattern in SECRET_PATTERNS:
        if pattern.search(data):
            hits.append(name)
    return hits


def fetch_remote_file(host: str, remote_path: str, timeout: int) -> bytes:
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
    return proc.stdout


def quarantine_path(candidate: dict, batch_id: str) -> Path:
    component = candidate["component"]
    file_name = Path(candidate["intended_local_path"]).name
    return QUARANTINE / "incoming" / batch_id / component / file_name


def write_quarantine(candidate: dict, data: bytes, batch_id: str, host: str) -> Path:
    target = quarantine_path(candidate, batch_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    os.chmod(target, 0o600)
    meta = {
        "host": host,
        "remote_path": candidate["remote_path"],
        "intended_local_path": candidate["intended_local_path"],
        "component": candidate["component"],
        "priority": candidate.get("priority"),
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "review_required": True,
        "promoted_to_source": False,
    }
    meta_path = target.with_suffix(target.suffix + ".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(meta_path, 0o600)
    return target


def safe_candidate_label(candidate: dict) -> str:
    """Return a non-secret candidate label for operator logs."""
    component = str(candidate.get("component") or "unknown")
    local_name = Path(str(candidate.get("intended_local_path") or "candidate")).name
    return f"{component}/{local_name}"


def list_candidates(candidates: list[dict]) -> None:
    for idx, item in enumerate(candidates, start=1):
        print(
            f"{idx:02d} {item.get('priority', '-'):<2} "
            f"{item.get('component', '-'):<12} "
            f"{item.get('current_gap_status', '-'):<20} "
            f"{item.get('remote_path')}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="nl", help="SSH host alias for NL")
    parser.add_argument("--component", help="Filter by manifest component")
    parser.add_argument("--priority", choices=("P1", "P2"), help="Filter by priority")
    parser.add_argument("--limit", type=int, help="Limit number of candidates")
    parser.add_argument("--pull", action="store_true", help="Read candidates from NL into quarantine")
    parser.add_argument("--timeout", type=int, default=20, help="SSH read timeout per file")
    args = parser.parse_args()

    manifest = load_manifest()
    if manifest.get("nl_write_allowed") is not False:
        raise SystemExit("Refusing to run: manifest must keep nl_write_allowed=false")

    candidates = iter_candidates(manifest, args.component, args.priority)
    if args.limit is not None:
        candidates = candidates[: args.limit]

    if not args.pull:
        list_candidates(candidates)
        print("\nDry run only. Add --pull to read files into local .quarantine/.")
        return 0

    if not candidates:
        print("No candidates selected.")
        return 0

    batch_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    accepted = 0
    blocked = 0

    for candidate in candidates:
        validate_candidate(candidate)
        remote_path = candidate["remote_path"]
        data = fetch_remote_file(args.host, remote_path, args.timeout)
        hits = scan_for_secrets(data)
        if hits:
            blocked += 1
            print(
                f"BLOCKED {safe_candidate_label(candidate)}: secret-pattern hits={len(hits)}",
                file=sys.stderr,
            )
            continue
        target = write_quarantine(candidate, data, batch_id, args.host)
        accepted += 1
        print(f"ACCEPTED {safe_candidate_label(candidate)} -> {target.relative_to(ROOT)}")

    print(f"batch={batch_id} accepted={accepted} blocked={blocked}")
    return 1 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
