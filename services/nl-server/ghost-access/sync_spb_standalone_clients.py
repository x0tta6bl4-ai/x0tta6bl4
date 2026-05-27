#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path


def run_text(cmd: list[str]) -> str:
    result = subprocess.run(cmd, check=True, text=True, capture_output=True)
    return result.stdout


def fetch_active_uuids(nl_alias: str, db_path: str) -> list[str]:
    query = """
WITH active_users AS (
  SELECT user_id, vpn_uuid
  FROM users
  WHERE vpn_uuid IS NOT NULL
    AND expires_at IS NOT NULL
    AND datetime(expires_at) > datetime('now')
),
active_devices AS (
  SELECT d.vpn_uuid
  FROM devices d
  JOIN active_users u ON u.user_id = d.user_id
  WHERE d.status = 'active'
),
fallback_users AS (
  SELECT vpn_uuid
  FROM active_users
  WHERE user_id NOT IN (SELECT user_id FROM devices WHERE status = 'active')
),
active_offline AS (
  SELECT vpn_uuid
  FROM offline_subscriptions
  WHERE datetime(expires_at) > datetime('now')
)
SELECT DISTINCT vpn_uuid
FROM (
  SELECT vpn_uuid FROM active_devices
  UNION
  SELECT vpn_uuid FROM fallback_users
  UNION
  SELECT vpn_uuid FROM active_offline
)
WHERE vpn_uuid IS NOT NULL AND vpn_uuid != ''
ORDER BY vpn_uuid;
"""
    cmd = [
        "ssh",
        nl_alias,
        f"sqlite3 {shlex.quote(db_path)} {shlex.quote(query)}",
    ]
    rows = run_text(cmd).splitlines()
    return [row.strip() for row in rows if row.strip()]


def push_clients_to_spb(spb_alias: str, port: int, uuids: list[str], flow: str) -> None:
    clients = [{"id": uuid, "flow": flow} for uuid in uuids]
    clients_b64 = subprocess.run(
        ["python3", "-c", "import base64, json, sys; print(base64.b64encode(json.dumps(json.load(sys.stdin)).encode()).decode())"],
        input=json.dumps(clients),
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    remote = f"""python3 - <<'PY'
import base64, json
from pathlib import Path
cfg_path=Path("/usr/local/etc/xray/config.json")
cfg=json.loads(cfg_path.read_text())
clients=json.loads(base64.b64decode("{clients_b64}"))
updated=False
for inbound in cfg.get("inbounds", []):
    if int(inbound.get("port") or 0) == {port}:
        inbound.setdefault("settings", {{}})["clients"] = clients
        updated=True
        break
if not updated:
    raise SystemExit("entry port not found")
cfg_path.write_text(json.dumps(cfg, ensure_ascii=True, indent=2) + "\\n")
PY
xray -test -config /usr/local/etc/xray/config.json >/dev/null
systemctl restart xray
systemctl is-active xray
"""
    subprocess.run(["ssh", spb_alias, remote], check=True, text=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync active Ghost Access UUIDs into SPB standalone xray entry")
    parser.add_argument("--nl-alias", default="nl")
    parser.add_argument("--spb-alias", default="sb")
    parser.add_argument("--db-path", default="/opt/ghost-access-bot/shared/x0tta6bl4.db")
    parser.add_argument("--port", type=int, default=443)
    parser.add_argument("--flow", default="xtls-rprx-vision")
    args = parser.parse_args()

    uuids = fetch_active_uuids(args.nl_alias, args.db_path)
    if not uuids:
        raise SystemExit("no active UUIDs found")
    push_clients_to_spb(args.spb_alias, args.port, uuids, args.flow)
    print(json.dumps({"port": args.port, "synced": len(uuids), "sample": uuids[:10]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
