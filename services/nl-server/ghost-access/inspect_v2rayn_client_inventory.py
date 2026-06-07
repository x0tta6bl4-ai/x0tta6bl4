#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
from datetime import UTC, datetime
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Callable
import urllib.parse
import urllib.request


DEFAULT_DB_PATH = Path("/home/x0ttta6bl4/.local/share/v2rayN/guiConfigs/guiNDB.db")
DEFAULT_TIMEOUT = 15.0

FORBIDDEN_OUTPUT_PATTERNS = {
    "vpn_uri": re.compile(r"\b(?:vless|vmess|trojan|ss)://", re.IGNORECASE),
    "subscription_path": re.compile(r"/sub/[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]{8,}"),
    "uuid": re.compile(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        re.IGNORECASE,
    ),
    "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
}


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def classify_profile(*, network: str, stream_security: str) -> str:
    net = (network or "").strip().lower()
    security = (stream_security or "").strip().lower()
    if net == "xhttp":
        return "xhttp"
    if net == "ws":
        return "ws"
    if security == "reality":
        return "reality"
    return "other"


def blank_counts() -> dict[str, int]:
    return {"reality": 0, "xhttp": 0, "ws": 0, "other": 0}


def inspect_profile_inventory(db_path: Path) -> dict[str, Any]:
    counts = blank_counts()
    ports: set[int] = set()
    total = 0
    subscription_rows = 0
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT Network, Port, StreamSecurity, IsSub FROM ProfileItem"
        ).fetchall()
    for row in rows:
        total += 1
        if int(row["IsSub"] or 0) == 1:
            subscription_rows += 1
        kind = classify_profile(
            network=str(row["Network"] or ""),
            stream_security=str(row["StreamSecurity"] or ""),
        )
        counts[kind] += 1
        if row["Port"]:
            ports.add(int(row["Port"]))
    return {
        "profile_rows": total,
        "subscription_profile_rows": subscription_rows,
        "counts": counts,
        "ports": sorted(ports),
    }


def read_enabled_subscription_urls(db_path: Path) -> list[str]:
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT Url FROM SubItem WHERE Enabled=1").fetchall()
    return [str(row["Url"] or "").strip() for row in rows if str(row["Url"] or "").strip()]


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


def parse_subscription_payload(text: str) -> dict[str, Any]:
    counts = blank_counts()
    ports: set[int] = set()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        lower = line.lower()
        kind = "other"
        if lower.startswith("vless://"):
            parsed = urllib.parse.urlsplit(line)
            query = urllib.parse.parse_qs(parsed.query)
            network = (query.get("type") or query.get("network") or [""])[0]
            security = (query.get("security") or [""])[0]
            kind = classify_profile(network=network, stream_security=security)
            if parsed.port:
                ports.add(int(parsed.port))
        counts[kind] += 1
    return {
        "line_count": len(lines),
        "counts": counts,
        "ports": sorted(ports),
    }


def fetch_subscription_summaries(
    urls: list[str],
    *,
    timeout: float,
    fetcher: Callable[[str, float], bytes] | None = None,
) -> dict[str, Any]:
    if fetcher is None:
        fetcher = default_fetcher
    summaries = []
    aggregate_counts = blank_counts()
    aggregate_ports: set[int] = set()
    for url in urls:
        item: dict[str, Any] = {"fetch_ok": False}
        try:
            text = decode_subscription_payload(fetcher(url, timeout))
            parsed = parse_subscription_payload(text)
            item.update({"fetch_ok": True, **parsed})
            for key, value in parsed["counts"].items():
                aggregate_counts[key] += int(value)
            aggregate_ports.update(int(port) for port in parsed["ports"])
        except Exception as exc:
            item.update({"error_type": type(exc).__name__})
        summaries.append(item)
    return {
        "enabled_subscriptions": len(urls),
        "fetches": summaries,
        "aggregate": {
            "counts": aggregate_counts,
            "ports": sorted(aggregate_ports),
        },
    }


def default_fetcher(url: str, timeout: float) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "v2rayN-safe-aggregate-check"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(1024 * 1024)


def derive_diagnosis(profile_inventory: dict[str, Any], subscription_inventory: dict[str, Any]) -> str:
    local_counts = profile_inventory.get("counts") or {}
    remote_counts = ((subscription_inventory.get("aggregate") or {}).get("counts") or {})
    if remote_counts.get("xhttp", 0) > 0 and local_counts.get("xhttp", 0) == 0:
        return "subscription_has_xhttp_but_local_v2rayn_db_has_no_xhttp"
    if remote_counts.get("ws", 0) > 0 and local_counts.get("ws", 0) == 0:
        return "subscription_has_ws_but_local_v2rayn_db_has_no_ws"
    if local_counts.get("xhttp", 0) > 0 or local_counts.get("ws", 0) > 0:
        return "local_v2rayn_db_contains_fallback_profiles"
    return "fallback_client_inventory_not_present"


def validate_output(payload: dict[str, Any]) -> list[dict[str, str]]:
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    findings = []
    for name, pattern in FORBIDDEN_OUTPUT_PATTERNS.items():
        if pattern.search(rendered):
            findings.append({"kind": name})
    return findings


def build_report(
    db_path: Path,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    fetch_subscriptions: bool = True,
    fetcher: Callable[[str, float], bytes] | None = None,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "checked_at": utc_now(),
        "source": "local_v2rayn_gui_db",
        "db_present": db_path.exists(),
        "privacy": {
            "raw_subscription_url_stored": False,
            "raw_vpn_uri_stored": False,
            "raw_uuid_stored": False,
            "raw_address_stored": False,
        },
    }
    if not db_path.exists():
        report["ok"] = False
        report["error"] = "v2rayn_db_missing"
        return report

    profile_inventory = inspect_profile_inventory(db_path)
    urls = read_enabled_subscription_urls(db_path)
    subscription_inventory = (
        fetch_subscription_summaries(urls, timeout=timeout, fetcher=fetcher)
        if fetch_subscriptions
        else {"enabled_subscriptions": len(urls), "fetches": [], "aggregate": {"counts": blank_counts(), "ports": []}}
    )
    report.update(
        {
            "ok": True,
            "profile_inventory": profile_inventory,
            "subscription_inventory": subscription_inventory,
            "diagnosis": derive_diagnosis(profile_inventory, subscription_inventory),
        }
    )
    findings = validate_output(report)
    report["privacy"]["output_privacy_ok"] = not findings
    if findings:
        report["privacy_findings"] = findings
    return report


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Inspect local v2rayN profile inventory without printing secrets.")
    p.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    p.add_argument("--skip-subscription-fetch", action="store_true")
    p.add_argument("--json", action="store_true")
    return p


def main() -> int:
    args = parser().parse_args()
    report = build_report(
        args.db_path,
        timeout=args.timeout,
        fetch_subscriptions=not args.skip_subscription_fetch,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"ok={str(report.get('ok')).lower()} diagnosis={report.get('diagnosis', report.get('error'))}")
    return 0 if report.get("ok") and (report.get("privacy") or {}).get("output_privacy_ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
