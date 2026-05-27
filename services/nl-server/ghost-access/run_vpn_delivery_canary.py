#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import sqlite3
import subprocess
import tempfile
import time
import uuid
from pathlib import Path


DEFAULT_DB_PATH = Path("/etc/x-ui/x-ui.db")
DEFAULT_RUNTIME_CONFIG_PATH = Path("/usr/local/x-ui/bin/config.json")
DEFAULT_RUNTIME_USER_MANAGER = Path("/opt/ghost-access-bot/current/scripts/xray_runtime_user_manager.py")
DEFAULT_INBOUND_PORT = 443
DEFAULT_TARGET_URL = "https://www.gstatic.com/generate_204"
DEFAULT_TIMEOUT = 12.0
DEFAULT_EMAIL = "ghost-monitor-canary@local"
DEFAULT_UUID = str(uuid.uuid5(uuid.NAMESPACE_DNS, "ghost-access-vpn-monitor"))
DEFAULT_ENV_FILE = Path("/opt/ghost-access-bot/shared/.env")


def _env(name: str, default: str = "") -> str:
    value = (os.environ.get(name) or "").strip()
    return value if value else default


PORT_PREFERRED_SERVER_NAMES = {
    443: lambda: [
        _env("REALITY_SNI", "eh.vk.com"),
        "eh.vk.com",
        "login.vk.com",
        "api.vk.com",
        "vk.com",
    ],
    2083: lambda: [
        _env("SECONDARY_REALITY_SNI"),
        "docs.docker.com",
        "hub.docker.com",
        "www.docker.com",
        "docs.oracle.com",
        "www.oracle.com",
    ],
    39829: lambda: [
        _env("LEGACY_REALITY_SNI", "google.com"),
        "google.com",
        "www.google.com",
        "dl.google.com",
    ],
}

PORT_PREFERRED_SHORT_IDS = {
    443: lambda: [_env("REALITY_SHORT_ID", "b2c4"), "b2c4"],
    2083: lambda: [_env("SECONDARY_REALITY_SHORT_ID")],
    39829: lambda: [_env("LEGACY_REALITY_SHORT_ID", "18e154a0558d9263")],
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a real VLESS/Reality canary through a temporary local Xray client.")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--runtime-config-path", type=Path, default=DEFAULT_RUNTIME_CONFIG_PATH)
    parser.add_argument("--runtime-user-manager", type=Path, default=DEFAULT_RUNTIME_USER_MANAGER)
    parser.add_argument("--inbound-port", type=int, default=DEFAULT_INBOUND_PORT)
    parser.add_argument("--target-url", default=DEFAULT_TARGET_URL)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--email", default=DEFAULT_EMAIL)
    parser.add_argument("--uuid", default=DEFAULT_UUID)
    parser.add_argument("--xray-bin", default=shutil.which("xray") or "/usr/local/x-ui/bin/xray")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    return parser


def _preferred_candidates(port: int, mapping: dict[int, callable]) -> list[str]:
    factory = mapping.get(port)
    if not factory:
        return []
    return [item for item in factory() if item]


def _pick_preferred_value(values: list[str], preferred: list[str]) -> str:
    for candidate in preferred:
        if candidate in values:
            return candidate
    return values[0] if values else ""


def _pick_preferred_fingerprint(inbound_port: int) -> str:
    if inbound_port == 2083:
        return _env("SECONDARY_REALITY_FINGERPRINT", _env("REALITY_FINGERPRINT", "qq"))
    if inbound_port == 39829:
        return _env("LEGACY_REALITY_FINGERPRINT", _env("REALITY_FINGERPRINT", "qq"))
    return _env("REALITY_FINGERPRINT", "qq")


def _load_inbound_profile(db_path: Path, inbound_port: int) -> dict:
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, port, remark, settings, stream_settings FROM inbounds WHERE port=? ORDER BY id LIMIT 1",
            (inbound_port,),
        ).fetchone()
        if not row:
            raise RuntimeError(f"inbound on port {inbound_port} not found")
        settings = json.loads(row["settings"] or "{}")
        stream = json.loads(row["stream_settings"] or "{}")
        return {
            "id": int(row["id"]),
            "port": int(row["port"]),
            "remark": row["remark"] or "",
            "settings": settings,
            "stream": stream,
        }


def _ensure_canary_client(db_path: Path, inbound_port: int, client_uuid: str, email: str) -> dict:
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, settings, stream_settings FROM inbounds WHERE port=? ORDER BY id LIMIT 1",
            (inbound_port,),
        ).fetchone()
        if not row:
            raise RuntimeError(f"inbound on port {inbound_port} not found")
        settings = json.loads(row["settings"] or "{}")
        clients = settings.get("clients") or []
        found = False
        for client in clients:
            if client.get("email") == email:
                client["id"] = client_uuid
                client["enable"] = True
                client["flow"] = client.get("flow") or "xtls-rprx-vision"
                found = True
                break
        if not found:
            clients.append(
                {
                    "id": client_uuid,
                    "email": email,
                    "enable": True,
                    "flow": "xtls-rprx-vision",
                    "limitIp": 0,
                    "totalGB": 0,
                    "expiryTime": 0,
                    "reset": 0,
                    "tgId": 0,
                    "subId": f"canary{random.randint(100000, 999999)}",
                    "comment": "vpn-delivery-canary",
                }
            )
        settings["clients"] = clients
        conn.execute("UPDATE inbounds SET settings=? WHERE id=?", (json.dumps(settings, ensure_ascii=False), int(row["id"])))
        conn.commit()
        stream = json.loads(row["stream_settings"] or "{}")
    return {
        "id": int(row["id"]),
        "stream": stream,
    }


def _load_runtime_api(runtime_config_path: Path, inbound_port: int) -> tuple[str, str]:
    config = json.loads(runtime_config_path.read_text(encoding="utf-8"))
    api_server = ""
    inbound_tag = ""
    for inbound in config.get("inbounds", []):
        tag = inbound.get("tag") or ""
        port = inbound.get("port")
        if tag == "api" and inbound.get("listen") and port:
            api_server = f"{inbound.get('listen')}:{port}"
        if port == inbound_port and tag:
            inbound_tag = tag
    if not api_server or not inbound_tag:
        raise RuntimeError("runtime api or inbound tag not found")
    return api_server, inbound_tag


def _read_env_value(env_file: Path, key: str) -> str:
    if not env_file.exists():
        return ""
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return ""


def _runtime_add(runtime_user_manager: Path, api_server: str, inbound_tag: str, email: str, client_uuid: str) -> None:
    cmd = [
        "python3",
        str(runtime_user_manager),
        "--server",
        api_server,
        "add-user",
        "--tag",
        inbound_tag,
        "--email",
        email,
        "--uuid",
        client_uuid,
        "--flow",
        "xtls-rprx-vision",
    ]
    completed = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    output = (completed.stdout or "").strip()
    if completed.returncode == 0:
        return
    if "already exists" in output.lower():
        return
    raise RuntimeError(output or f"runtime add failed rc={completed.returncode}")


def _pick_local_socks_port() -> int:
    return random.randint(21080, 22999)


def _build_client_config(
    server_host: str,
    inbound_port: int,
    stream: dict,
    public_key: str,
    client_uuid: str,
    socks_port: int,
) -> dict:
    reality = stream.get("realitySettings") or {}
    server_names = reality.get("serverNames") or []
    short_ids = reality.get("shortIds") or []
    server_name = _pick_preferred_value(
        server_names, _preferred_candidates(inbound_port, PORT_PREFERRED_SERVER_NAMES)
    )
    short_id = _pick_preferred_value(
        short_ids, _preferred_candidates(inbound_port, PORT_PREFERRED_SHORT_IDS)
    )
    fingerprint = _pick_preferred_fingerprint(inbound_port)
    return {
        "log": {"loglevel": "warning"},
        "inbounds": [
            {
                "tag": "socks",
                "port": socks_port,
                "listen": "127.0.0.1",
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
                            "address": server_host,
                            "port": inbound_port,
                            "users": [
                                {
                                    "id": client_uuid,
                                    "encryption": "none",
                                    "flow": "xtls-rprx-vision",
                                }
                            ],
                        }
                    ]
                },
                "streamSettings": {
                    "network": stream.get("network", "tcp"),
                    "security": "reality",
                    "realitySettings": {
                        "show": False,
                        "fingerprint": fingerprint,
                        "serverName": server_name,
                        "publicKey": public_key,
                        "shortId": short_id,
                        "spiderX": "/",
                    },
                },
            }
        ],
        "routing": {
            "domainStrategy": "AsIs",
            "rules": [
                {"type": "field", "network": "tcp,udp", "outboundTag": "proxy"},
            ],
        },
    }


def _run_client_probe(xray_bin: str, config: dict, target_url: str, timeout: float) -> dict:
    with tempfile.TemporaryDirectory(prefix="ghost-vpn-canary-") as tmpdir:
        config_path = Path(tmpdir) / "client.json"
        stderr_path = Path(tmpdir) / "xray.stderr.log"
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        stderr_fh = stderr_path.open("w", encoding="utf-8")
        proc = subprocess.Popen(
            [xray_bin, "run", "-config", str(config_path)],
            stdout=subprocess.DEVNULL,
            stderr=stderr_fh,
        )
        try:
            time.sleep(1.2)
            socks_port = config["inbounds"][0]["port"]
            if proc.poll() is not None:
                stderr_fh.flush()
                return {"ok": False, "error": stderr_path.read_text(encoding="utf-8").strip() or f"xray-exit={proc.returncode}"}
            warmup = subprocess.run(
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
                    str(min(timeout, 8.0)),
                    target_url,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
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
            if curl.returncode != 0:
                stderr_fh.flush()
                xray_err = stderr_path.read_text(encoding="utf-8").strip()
                return {"ok": False, "error": (curl.stderr or curl.stdout).strip() or xray_err or f"curl exited {curl.returncode}"}
            metrics = {}
            for part in (curl.stdout or "").strip().split():
                if "=" in part:
                    key, value = part.split("=", 1)
                    metrics[key] = value
            warmup_metrics = {}
            for part in (warmup.stdout or "").strip().split():
                if "=" in part:
                    key, value = part.split("=", 1)
                    warmup_metrics[key] = value
            code = int(metrics.get("code", "0"))
            return {
                "ok": 200 <= code < 500,
                "http_code": code,
                "total_s": float(metrics.get("total", "0") or 0),
                "warmup_http_code": int(warmup_metrics.get("code", "0") or 0),
                "warmup_total_s": float(warmup_metrics.get("total", "0") or 0),
                "error": None,
            }
        finally:
            proc.terminate()
            stderr_fh.close()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()


def main() -> int:
    args = _parser().parse_args()
    inbound = _load_inbound_profile(args.db_path, args.inbound_port)
    _ensure_canary_client(args.db_path, args.inbound_port, args.uuid, args.email)
    api_server, inbound_tag = _load_runtime_api(args.runtime_config_path, args.inbound_port)
    _runtime_add(args.runtime_user_manager, api_server, inbound_tag, args.email, args.uuid)
    socks_port = _pick_local_socks_port()
    reality = inbound["stream"].get("realitySettings") or {}
    reality_settings = reality.get("settings") or {}
    public_key = (
        reality.get("publicKey")
        or reality_settings.get("publicKey")
        or _read_env_value(args.env_file, "REALITY_PUBLIC_KEY")
    )
    config = _build_client_config("127.0.0.1", args.inbound_port, inbound["stream"], public_key, args.uuid, socks_port)
    result = _run_client_probe(args.xray_bin, config, args.target_url, args.timeout)
    payload = {
        "ok": bool(result.get("ok")),
        "target_url": args.target_url,
        "http_code": result.get("http_code"),
        "total_s": result.get("total_s"),
        "error": result.get("error"),
        "inbound_port": args.inbound_port,
        "inbound_id": inbound["id"],
        "remark": inbound["remark"],
        "email": args.email,
        "fingerprint": _pick_preferred_fingerprint(args.inbound_port),
        "server_name": _pick_preferred_value(
            (inbound["stream"].get("realitySettings") or {}).get("serverNames") or [],
            _preferred_candidates(args.inbound_port, PORT_PREFERRED_SERVER_NAMES),
        ),
        "short_id": _pick_preferred_value(
            (inbound["stream"].get("realitySettings") or {}).get("shortIds") or [],
            _preferred_candidates(args.inbound_port, PORT_PREFERRED_SHORT_IDS),
        ),
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
