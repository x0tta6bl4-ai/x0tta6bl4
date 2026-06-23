#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any


DEFAULT_XUI_DB = Path("/etc/x-ui/x-ui.db")
DEFAULT_CONFIG = Path("/etc/ghost-access/nl-https-ws-8443.json")
DEFAULT_XRAY_BIN = Path("/usr/local/x-ui/bin/xray-linux-amd64.real")
DEFAULT_SERVICE = "ghost-access-nl-https-ws.service"
DEFAULT_SOURCE_PORTS = (443, 2083, 39829)


def parse_ports(raw: str | None, default: tuple[int, ...] = DEFAULT_SOURCE_PORTS) -> list[int]:
    if not raw:
        return list(default)
    ports: list[int] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            port = int(chunk)
        except ValueError:
            continue
        if 0 < port <= 65535:
            ports.append(port)
    return sorted(set(ports)) or list(default)


def load_enabled_clients(db_path: Path, source_ports: list[int]) -> list[dict[str, Any]]:
    clients: dict[str, dict[str, Any]] = {}
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        placeholders = ",".join("?" for _ in source_ports)
        rows = conn.execute(
            f"SELECT port, settings FROM inbounds WHERE port IN ({placeholders})",
            source_ports,
        ).fetchall()

    for row in rows:
        try:
            settings = json.loads(row["settings"] or "{}")
        except json.JSONDecodeError:
            continue
        for client in settings.get("clients", []):
            client_id = str(client.get("id") or "").strip()
            try:
                uuid.UUID(client_id)
            except ValueError:
                continue
            if client.get("enable") is False:
                continue
            email = str(client.get("email") or f"ghost-ws-{client_id[:8]}")[:80]
            clients[client_id] = {
                "id": client_id,
                "email": email,
                "level": int(client.get("level") or 0),
            }

    return [clients[key] for key in sorted(clients)]


def build_stream_settings(network: str, path: str, mode: str) -> dict[str, Any]:
    if network == "ws":
        return {
            "network": "ws",
            "security": "none",
            "wsSettings": {"path": path},
        }
    if network == "xhttp":
        return {
            "network": "xhttp",
            "security": "none",
            "xhttpSettings": {"path": path, "mode": mode},
        }
    raise ValueError(f"unsupported network: {network}")


def build_config(
    clients: list[dict[str, Any]],
    *,
    listen: str,
    port: int,
    path: str,
    network: str,
    mode: str,
    tag: str,
) -> dict[str, Any]:
    return {
        "log": {
            "loglevel": "warning",
            "access": f"/var/log/ghost-access/{tag}-access.log",
            "error": f"/var/log/ghost-access/{tag}-error.log",
        },
        "inbounds": [
            {
                "tag": tag,
                "listen": listen,
                "port": port,
                "protocol": "vless",
                "settings": {"clients": clients, "decryption": "none"},
                "streamSettings": build_stream_settings(network, path, mode),
                "sniffing": {
                    "enabled": True,
                    "destOverride": ["http", "tls", "quic"],
                    "routeOnly": False,
                },
            }
        ],
        "outbounds": [
            {"tag": "direct", "protocol": "freedom"},
            {"tag": "block", "protocol": "blackhole"},
        ],
        "routing": {
            "rules": [
                {
                    "type": "field",
                    "ip": ["geoip:private"],
                    "outboundTag": "block",
                }
            ]
        },
    }


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def validate_config(xray_bin: Path, config_path: Path) -> None:
    subprocess.run(
        [str(xray_bin), "run", "-test", "-config", str(config_path)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=20,
    )


def write_validated_config(path: Path, text: str, *, xray_bin: Path, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=str(path.parent),
        suffix=".json",
        delete=False,
    ) as fh:
        fh.write(text)
        tmp = Path(fh.name)
    try:
        tmp.chmod(mode)
        validate_config(xray_bin, tmp)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def restart_service(service: str) -> None:
    subprocess.run(
        ["systemctl", "restart", service],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=20,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync Ghost HTTPS WS clients from x-ui DB.")
    parser.add_argument("--xui-db", type=Path, default=DEFAULT_XUI_DB)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--xray-bin", type=Path, default=DEFAULT_XRAY_BIN)
    parser.add_argument("--service", default=DEFAULT_SERVICE)
    parser.add_argument("--source-ports", default=",".join(str(port) for port in DEFAULT_SOURCE_PORTS))
    parser.add_argument("--listen", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=10085)
    parser.add_argument("--path", default="/ghost-ws")
    parser.add_argument("--network", choices=("ws", "xhttp"), default="ws")
    parser.add_argument("--mode", default="auto")
    parser.add_argument("--tag", default="")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--restart-service", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    clients = load_enabled_clients(args.xui_db, parse_ports(args.source_ports))
    tag = args.tag or f"ghost-https-{args.network}"
    payload = build_config(
        clients,
        listen=args.listen,
        port=args.port,
        path=args.path,
        network=args.network,
        mode=args.mode,
        tag=tag,
    )
    rendered = canonical_json(payload)
    existing = args.config.read_text(encoding="utf-8") if args.config.exists() else ""
    changed = rendered != existing

    result: dict[str, Any] = {
        "changed": changed,
        "client_count": len(clients),
        "config": str(args.config),
        "service": args.service,
        "applied": False,
        "service_restarted": False,
    }

    if args.apply and changed:
        write_validated_config(args.config, rendered, xray_bin=args.xray_bin)
        result["applied"] = True
        if args.restart_service:
            restart_service(args.service)
            result["service_restarted"] = True
    elif not changed and args.apply:
        validate_config(args.xray_bin, args.config)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            f"changed={str(changed).lower()} clients={len(clients)} "
            f"applied={str(result['applied']).lower()} "
            f"service_restarted={str(result['service_restarted']).lower()}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
