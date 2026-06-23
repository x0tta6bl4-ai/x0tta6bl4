#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import random
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import tempfile
import time
from typing import Any


DEFAULT_DB_PATH = Path("/home/x0ttta6bl4/.local/share/v2rayN/guiConfigs/guiNDB.db")
DEFAULT_XRAY_BIN = Path("/home/x0ttta6bl4/.local/share/v2rayN/bin/xray/xray")
DEFAULT_TARGET_URL = "https://www.gstatic.com/generate_204"
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


@dataclass(frozen=True)
class Profile:
    transport: str
    address: str
    port: int
    user_id: str
    encryption: str
    flow: str
    stream_security: str
    request_host: str
    path: str
    sni: str
    alpn: str
    fingerprint: str
    public_key: str
    short_id: str
    spider_x: str
    proto_extra: str


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_profiles(db_path: Path, transports: set[str] | None = None) -> list[Profile]:
    transports = transports or TARGET_TRANSPORTS
    placeholders = ",".join("?" for _ in transports)
    query = (
        "SELECT Network, Address, Port, Id, Security, Flow, StreamSecurity, "
        "RequestHost, Path, Sni, Alpn, Fingerprint, PublicKey, ShortId, SpiderX, ProtoExtra "
        f"FROM ProfileItem WHERE lower(Network) IN ({placeholders}) ORDER BY lower(Network), Port"
    )
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, sorted(transports)).fetchall()
    profiles: list[Profile] = []
    for row in rows:
        profiles.append(
            Profile(
                transport=str(row["Network"] or "").lower(),
                address=str(row["Address"] or ""),
                port=int(row["Port"] or 0),
                user_id=str(row["Id"] or ""),
                encryption=str(row["Security"] or "none"),
                flow=str(row["Flow"] or ""),
                stream_security=str(row["StreamSecurity"] or "tls"),
                request_host=str(row["RequestHost"] or ""),
                path=str(row["Path"] or ""),
                sni=str(row["Sni"] or ""),
                alpn=str(row["Alpn"] or ""),
                fingerprint=str(row["Fingerprint"] or ""),
                public_key=str(row["PublicKey"] or ""),
                short_id=str(row["ShortId"] or ""),
                spider_x=str(row["SpiderX"] or ""),
                proto_extra=str(row["ProtoExtra"] or ""),
            )
        )
    return profiles


def pick_socks_port() -> int:
    return random.randint(23080, 24999)


def tls_settings(profile: Profile) -> dict[str, Any]:
    settings: dict[str, Any] = {
        "serverName": profile.sni or profile.request_host or profile.address,
        "allowInsecure": False,
    }
    if profile.fingerprint:
        settings["fingerprint"] = profile.fingerprint
    if profile.alpn:
        settings["alpn"] = [part.strip() for part in profile.alpn.split(",") if part.strip()]
    return settings


def stream_settings(profile: Profile) -> dict[str, Any]:
    settings: dict[str, Any] = {
        "network": profile.transport,
        "security": profile.stream_security or "tls",
        "tlsSettings": tls_settings(profile),
    }
    if profile.transport == "ws":
        ws: dict[str, Any] = {"path": profile.path or "/"}
        if profile.request_host:
            ws["headers"] = {"Host": profile.request_host}
        settings["wsSettings"] = ws
    elif profile.transport == "xhttp":
        xhttp: dict[str, Any] = {"path": profile.path or "/"}
        if profile.request_host:
            xhttp["host"] = profile.request_host
        if profile.proto_extra:
            xhttp["mode"] = profile.proto_extra
        settings["xhttpSettings"] = xhttp
    return settings


def build_xray_config(profile: Profile, socks_port: int) -> dict[str, Any]:
    user: dict[str, Any] = {
        "id": profile.user_id,
        "encryption": profile.encryption or "none",
    }
    if profile.flow:
        user["flow"] = profile.flow
    return {
        "log": {"loglevel": "warning"},
        "inbounds": [
            {
                "tag": "socks",
                "listen": "127.0.0.1",
                "port": socks_port,
                "protocol": "socks",
                "settings": {"auth": "noauth", "udp": True},
            }
        ],
        "outbounds": [
            {
                "tag": "proxy",
                "protocol": "vless",
                "settings": {
                    "vnext": [
                        {
                            "address": profile.address,
                            "port": profile.port,
                            "users": [user],
                        }
                    ]
                },
                "streamSettings": stream_settings(profile),
            }
        ],
        "routing": {
            "domainStrategy": "AsIs",
            "rules": [{"type": "field", "network": "tcp,udp", "outboundTag": "proxy"}],
        },
    }


def run_profile_probe(
    profile: Profile,
    *,
    xray_bin: Path,
    target_url: str,
    timeout: float,
) -> dict[str, Any]:
    socks_port = pick_socks_port()
    with tempfile.TemporaryDirectory(prefix="v2rayn-fallback-probe-") as tmpdir:
        config_path = Path(tmpdir) / "client.json"
        stderr_path = Path(tmpdir) / "xray.stderr.log"
        config_path.write_text(json.dumps(build_xray_config(profile, socks_port), ensure_ascii=False), encoding="utf-8")
        stderr_fh = stderr_path.open("w", encoding="utf-8")
        proc = subprocess.Popen(
            [str(xray_bin), "run", "-config", str(config_path)],
            stdout=subprocess.DEVNULL,
            stderr=stderr_fh,
        )
        try:
            time.sleep(1.2)
            if proc.poll() is not None:
                return {
                    "transport": profile.transport,
                    "port": profile.port,
                    "ok": False,
                    "error_type": "xray_start_failed",
                }
            curl = subprocess.run(
                [
                    "curl",
                    "-4",
                    "-s",
                    "-o",
                    "/dev/null",
                    "-w",
                    "code=%{http_code} total=%{time_total}",
                    "--proxy",
                    f"socks5h://127.0.0.1:{socks_port}",
                    "--max-time",
                    str(timeout),
                    target_url,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            metrics: dict[str, str] = {}
            for part in (curl.stdout or "").strip().split():
                if "=" in part:
                    key, value = part.split("=", 1)
                    metrics[key] = value
            code = int(metrics.get("code", "0") or 0)
            return {
                "transport": profile.transport,
                "port": profile.port,
                "ok": curl.returncode == 0 and 200 <= code < 500,
                "http_code": code,
                "total_s": float(metrics.get("total", "0") or 0),
                "error_type": None if curl.returncode == 0 else "curl_failed",
            }
        finally:
            proc.terminate()
            stderr_fh.close()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()


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
    xray_bin: Path = DEFAULT_XRAY_BIN,
    target_url: str = DEFAULT_TARGET_URL,
    timeout: float = 15.0,
) -> dict[str, Any]:
    if not db_path.exists():
        return {"ok": False, "error": "v2rayn_db_missing"}
    if not xray_bin.exists():
        return {"ok": False, "error": "xray_bin_missing"}
    profiles = load_profiles(db_path)
    results = [
        run_profile_probe(profile, xray_bin=xray_bin, target_url=target_url, timeout=timeout)
        for profile in profiles
    ]
    passed = {str(item.get("transport")) for item in results if item.get("ok")}
    payload: dict[str, Any] = {
        "ok": bool(results) and all(bool(item.get("ok")) for item in results),
        "checked_at": utc_now(),
        "source": "local_v2rayn_db_profiles_with_v2rayn_bundled_xray",
        "target_url_class": "https_generate_204",
        "profile_count": len(profiles),
        "passed_transports": sorted(passed),
        "results": results,
        "privacy": {
            "raw_vpn_uri_stored": False,
            "raw_uuid_stored": False,
            "raw_address_stored": False,
            "raw_sni_stored": False,
            "raw_path_stored": False,
        },
    }
    findings = validate_output(payload)
    payload["privacy"]["output_privacy_ok"] = not findings
    if findings:
        payload["privacy_findings"] = findings
        payload["ok"] = False
    return payload


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Probe imported v2rayN XHTTP/WS profiles through bundled Xray without printing secrets.")
    p.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    p.add_argument("--xray-bin", type=Path, default=DEFAULT_XRAY_BIN)
    p.add_argument("--target-url", default=DEFAULT_TARGET_URL)
    p.add_argument("--timeout", type=float, default=15.0)
    p.add_argument("--json", action="store_true")
    return p


def main() -> int:
    args = parser().parse_args()
    report = build_report(
        args.db_path,
        xray_bin=args.xray_bin,
        target_url=args.target_url,
        timeout=args.timeout,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"ok={str(report.get('ok')).lower()} passed={','.join(report.get('passed_transports', []))}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
