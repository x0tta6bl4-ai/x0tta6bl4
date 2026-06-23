#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
from datetime import UTC, datetime
import json
import shutil
import sqlite3
from pathlib import Path
import re
from typing import Any, Callable
import urllib.parse
import urllib.request
import uuid


DEFAULT_DB_PATH = Path("/home/x0ttta6bl4/.local/share/v2rayN/guiConfigs/guiNDB.db")
CONFIRM_TOKEN = "SYNC_V2RAYN_FALLBACKS"
LIVE_CONFIRM_TOKEN = "SYNC_V2RAYN_FALLBACKS_LIVE_DB"
TARGET_TRANSPORTS = {"xhttp", "ws"}

FORBIDDEN_OUTPUT_PATTERNS = {
    "vpn_uri": re.compile(r"\b(?:vless|vmess|trojan|ss)://", re.IGNORECASE),
    "subscription_path": re.compile(r"/sub/[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]{8,}"),
    "uuid": re.compile(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        re.IGNORECASE,
    ),
    "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
}


class SyncError(ValueError):
    pass


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def blank_counts() -> dict[str, int]:
    return {"xhttp": 0, "ws": 0, "reality": 0, "other": 0}


def classify(network: str, security: str) -> str:
    net = (network or "").strip().lower()
    sec = (security or "").strip().lower()
    if net == "xhttp":
        return "xhttp"
    if net == "ws":
        return "ws"
    if sec == "reality":
        return "reality"
    return "other"


def decode_subscription_payload(raw: bytes) -> str:
    text = raw.decode("utf-8", "replace").strip()
    if "://" in text[:200]:
        return text
    compact = "".join(text.split())
    padding = "=" * ((4 - len(compact) % 4) % 4)
    try:
        return base64.b64decode(compact + padding).decode("utf-8", "replace")
    except Exception:
        return text


def default_fetcher(url: str, timeout: float) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "v2rayN-safe-fallback-sync-check"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(1024 * 1024)


def read_enabled_subscriptions(db_path: Path) -> list[dict[str, str]]:
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT Id, Url FROM SubItem WHERE Enabled=1").fetchall()
    return [
        {"id": str(row["Id"] or ""), "url": str(row["Url"] or "")}
        for row in rows
        if str(row["Url"] or "").strip()
    ]


def first_query(query: dict[str, list[str]], *names: str, default: str = "") -> str:
    for name in names:
        values = query.get(name)
        if values:
            return values[0]
    return default


def parse_vless_profile(line: str, *, subid: str) -> dict[str, Any] | None:
    if not line.lower().startswith("vless://"):
        return None
    parsed = urllib.parse.urlsplit(line)
    query = urllib.parse.parse_qs(parsed.query)
    network = first_query(query, "type", "network", default="tcp").lower()
    stream_security = first_query(query, "security", default="").lower()
    kind = classify(network, stream_security)
    if kind not in TARGET_TRANSPORTS:
        return None
    return {
        "IndexId": str(uuid.uuid4()),
        "ConfigType": 5,
        "ConfigVersion": 3,
        "Address": parsed.hostname or "",
        "Port": parsed.port or 0,
        "Ports": "",
        "Id": urllib.parse.unquote(parsed.username or ""),
        "AlterId": 0,
        "Security": first_query(query, "encryption", default="none"),
        "Network": network,
        "Remarks": urllib.parse.unquote(parsed.fragment or f"Ghost Access {kind.upper()}"),
        "HeaderType": first_query(query, "headerType", default="none"),
        "RequestHost": first_query(query, "host", default=""),
        "Path": first_query(query, "path", default=""),
        "StreamSecurity": stream_security,
        "AllowInsecure": first_query(query, "allowInsecure", default="false"),
        "Subid": subid,
        "IsSub": 1,
        "Flow": first_query(query, "flow", default=""),
        "Sni": first_query(query, "sni", "serverName", default=""),
        "Alpn": first_query(query, "alpn", default=""),
        "CoreType": None,
        "PreSocksPort": None,
        "Fingerprint": first_query(query, "fp", "fingerprint", default=""),
        "DisplayLog": 1,
        "PublicKey": first_query(query, "pbk", "publicKey", default=""),
        "ShortId": first_query(query, "sid", "shortId", default=""),
        "SpiderX": first_query(query, "spx", "spiderX", default=""),
        "Mldsa65Verify": first_query(query, "mldsa65Verify", default=""),
        "Extra": first_query(query, "extra", default=""),
        "MuxEnabled": None,
        "Password": "",
        "Username": "",
        "Cert": "",
        "CertSha": "",
        "EchConfigList": "",
        "EchForceQuery": "",
        "Finalmask": "",
        "ProtoExtra": first_query(query, "mode", default=""),
        "_kind": kind,
    }


def collect_candidates(
    db_path: Path,
    *,
    timeout: float,
    fetcher: Callable[[str, float], bytes] | None = None,
) -> list[dict[str, Any]]:
    fetcher = fetcher or default_fetcher
    candidates: list[dict[str, Any]] = []
    for sub in read_enabled_subscriptions(db_path):
        raw = fetcher(sub["url"], timeout)
        payload = decode_subscription_payload(raw)
        for line in payload.splitlines():
            candidate = parse_vless_profile(line.strip(), subid=sub["id"])
            if candidate:
                candidates.append(candidate)
    return candidates


def existing_fingerprints(db_path: Path) -> set[tuple[str, int, str, str, str]]:
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT Address, Port, Id, Network, StreamSecurity FROM ProfileItem"
        ).fetchall()
    return {
        (
            str(row["Address"] or ""),
            int(row["Port"] or 0),
            str(row["Id"] or ""),
            str(row["Network"] or "").lower(),
            str(row["StreamSecurity"] or "").lower(),
        )
        for row in rows
    }


def candidate_fingerprint(row: dict[str, Any]) -> tuple[str, int, str, str, str]:
    return (
        str(row.get("Address") or ""),
        int(row.get("Port") or 0),
        str(row.get("Id") or ""),
        str(row.get("Network") or "").lower(),
        str(row.get("StreamSecurity") or "").lower(),
    )


def candidate_summary(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    counts = blank_counts()
    ports: set[int] = set()
    for row in candidates:
        counts[str(row.get("_kind") or "other")] += 1
        if row.get("Port"):
            ports.add(int(row["Port"]))
    return {"counts": counts, "ports": sorted(ports), "total": len(candidates)}


def filter_missing(db_path: Path, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    known = existing_fingerprints(db_path)
    return [row for row in candidates if candidate_fingerprint(row) not in known]


def insert_candidates(db_path: Path, candidates: list[dict[str, Any]]) -> None:
    if not candidates:
        return
    columns = [
        "IndexId",
        "ConfigType",
        "ConfigVersion",
        "Address",
        "Port",
        "Ports",
        "Id",
        "AlterId",
        "Security",
        "Network",
        "Remarks",
        "HeaderType",
        "RequestHost",
        "Path",
        "StreamSecurity",
        "AllowInsecure",
        "Subid",
        "IsSub",
        "Flow",
        "Sni",
        "Alpn",
        "CoreType",
        "PreSocksPort",
        "Fingerprint",
        "DisplayLog",
        "PublicKey",
        "ShortId",
        "SpiderX",
        "Mldsa65Verify",
        "Extra",
        "MuxEnabled",
        "Password",
        "Username",
        "Cert",
        "CertSha",
        "EchConfigList",
        "EchForceQuery",
        "Finalmask",
        "ProtoExtra",
    ]
    placeholders = ",".join("?" for _ in columns)
    with sqlite3.connect(str(db_path)) as conn:
        current_sort = conn.execute("SELECT COALESCE(MAX(Sort), 0) FROM ProfileExItem").fetchone()[0] or 0
        for offset, row in enumerate(candidates, start=1):
            conn.execute(
                f"INSERT INTO ProfileItem ({','.join(columns)}) VALUES ({placeholders})",
                [row.get(column) for column in columns],
            )
            conn.execute(
                "INSERT OR REPLACE INTO ProfileExItem (IndexId, Delay, Speed, Sort, Message) VALUES (?, ?, ?, ?, ?)",
                (row["IndexId"], 0, 0.0, int(current_sort) + offset, ""),
            )
        conn.commit()


def backup_live_db(db_path: Path, backup_dir: Path | None) -> Path:
    target_dir = backup_dir or db_path.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    backup_path = target_dir / f"{db_path.name}.bak-v2rayn-fallbacks-{utc_stamp()}"
    shutil.copy2(db_path, backup_path)
    return backup_path


def validate_output(payload: dict[str, Any]) -> list[dict[str, str]]:
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    findings = []
    for name, pattern in FORBIDDEN_OUTPUT_PATTERNS.items():
        if pattern.search(rendered):
            findings.append({"kind": name})
    return findings


def build_plan(
    db_path: Path,
    *,
    timeout: float,
    fetcher: Callable[[str, float], bytes] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    candidates = collect_candidates(db_path, timeout=timeout, fetcher=fetcher)
    missing = filter_missing(db_path, candidates)
    plan = {
        "enabled_subscriptions": len(read_enabled_subscriptions(db_path)),
        "subscription_candidates": candidate_summary(candidates),
        "missing_fallback_profiles": candidate_summary(missing),
    }
    return candidates, missing, plan


def run_sync(
    db_path: Path,
    *,
    timeout: float,
    apply_to_copy: Path | None,
    apply_live: bool = False,
    backup_dir: Path | None = None,
    confirm: str,
    fetcher: Callable[[str, float], bytes] | None = None,
) -> dict[str, Any]:
    if not db_path.exists():
        raise SyncError(f"db not found: {db_path}")
    if apply_to_copy and apply_live:
        raise SyncError("--apply-to-copy and --apply-live are mutually exclusive")
    _, missing, plan = build_plan(db_path, timeout=timeout, fetcher=fetcher)
    report: dict[str, Any] = {
        "ok": True,
        "decision": "DRY_RUN",
        "source": "local_v2rayn_gui_db",
        "restarted_v2rayn": False,
        "plan": plan,
        "privacy": {
            "raw_subscription_url_stored": False,
            "raw_vpn_uri_stored": False,
            "raw_uuid_stored": False,
            "raw_address_stored": False,
        },
    }
    if apply_to_copy:
        if confirm != CONFIRM_TOKEN:
            raise SyncError(f"--confirm {CONFIRM_TOKEN} is required for --apply-to-copy")
        apply_to_copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(db_path, apply_to_copy)
        insert_candidates(apply_to_copy, missing)
        _, remaining_after_copy, _ = build_plan(apply_to_copy, timeout=timeout, fetcher=fetcher)
        report.update(
            {
                "decision": "APPLIED_TO_COPY",
                "applied_to_live_db": False,
                "restarted_v2rayn": False,
                "copy_path": str(apply_to_copy),
                "inserted_profiles": candidate_summary(missing),
                "remaining_missing_after_copy": candidate_summary(remaining_after_copy),
            }
        )
    elif apply_live:
        if confirm != LIVE_CONFIRM_TOKEN:
            raise SyncError(f"--confirm {LIVE_CONFIRM_TOKEN} is required for --apply-live")
        backup_path = backup_live_db(db_path, backup_dir)
        insert_candidates(db_path, missing)
        _, remaining_after_live, _ = build_plan(db_path, timeout=timeout, fetcher=fetcher)
        report.update(
            {
                "decision": "APPLIED_TO_LIVE_DB",
                "applied_to_live_db": True,
                "backup_path": str(backup_path),
                "inserted_profiles": candidate_summary(missing),
                "remaining_missing_after_live": candidate_summary(remaining_after_live),
            }
        )
    findings = validate_output(report)
    report["privacy"]["output_privacy_ok"] = not findings
    if findings:
        report["privacy_findings"] = findings
        report["ok"] = False
    return report


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Dry-run or copy-apply v2rayN XHTTP/WS subscription fallback import.")
    p.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    p.add_argument("--timeout", type=float, default=15.0)
    p.add_argument("--apply-to-copy", type=Path, default=None)
    p.add_argument("--apply-live", action="store_true")
    p.add_argument("--backup-dir", type=Path, default=None)
    p.add_argument("--confirm", default="")
    p.add_argument("--json", action="store_true")
    return p


def main() -> int:
    args = parser().parse_args()
    try:
        report = run_sync(
            args.db_path,
            timeout=args.timeout,
            apply_to_copy=args.apply_to_copy,
            apply_live=args.apply_live,
            backup_dir=args.backup_dir,
            confirm=args.confirm,
        )
    except SyncError as exc:
        report = {"ok": False, "error": str(exc)}
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"ok={str(report.get('ok')).lower()} decision={report.get('decision', report.get('error'))}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
