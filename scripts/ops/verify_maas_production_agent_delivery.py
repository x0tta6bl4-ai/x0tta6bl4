#!/usr/bin/env python3
"""Run a real Go-agent control-loop smoke against a running MaaS API."""

import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

import requests

SCHEMA = "x0tta6bl4.maas_production_agent_delivery_smoke.v2"
READY_DECISION = "MAAS_PRODUCTION_AGENT_DELIVERY_SMOKE_READY"
BLOCKED_DECISION = "MAAS_PRODUCTION_AGENT_DELIVERY_SMOKE_BLOCKED"

def run_verification(api_url: str, work_dir: str):
    started = time.monotonic()
    work_path = Path(work_dir)
    work_path.mkdir(parents=True, exist_ok=True)
    
    node_id = f"prod-agent-{uuid.uuid4().hex[:8]}"
    report = {
        "schema": SCHEMA,
        "ready": False,
        "stages": [],
        "node_id": node_id
    }

    def add_stage(name, ok, details=None):
        report["stages"].append({"name": name, "ok": ok, "details": details})
        return ok

    # 1. Health check
    try:
        resp = requests.get(f"{api_url}/health", timeout=5)
        if not add_stage("health_check", resp.status_code == 200, resp.json()):
            return report
    except Exception as e:
        add_stage("health_check", False, str(e))
        return report

    # 2. Register
    email = f"test-{uuid.uuid4().hex[:8]}@smoke.test"
    try:
        resp = requests.post(
            f"{api_url}/api/v1/maas/auth/register",
            json={"email": email, "password": "password123", "name": "Smoke Test"},
            timeout=10
        )
        if not add_stage("register", resp.status_code in (200, 201), resp.json()):
            return report
        token = resp.json()["access_token"]
    except Exception as e:
        add_stage("register", False, str(e))
        return report

    # 3. Deploy Mesh
    try:
        resp = requests.post(
            f"{api_url}/api/v1/maas/mesh/deploy",
            json={"name": "Smoke Mesh", "nodes": 1, "pqc_enabled": False},
            headers={"X-API-Key": token},
            timeout=60
        )
        if not add_stage("deploy", resp.status_code in (200, 201), resp.json()):
            return report
        mesh_id = resp.json()["mesh_id"]
        enrollment_token = resp.json()["join_config"].get("token") or resp.json()["join_config"].get("enrollment_token")
    except Exception as e:
        add_stage("deploy", False, str(e))
        return report

    # 4. Start Agent
    agent_bin = Path("x0t-agent-smoke")
    config_path = work_path / "agent.yaml"
    config_path.write_text(f"""
node_id: "{node_id}"
api_endpoint: "{api_url}"
join_token: "{enrollment_token}"
mesh_id: "{mesh_id}"
listen_port: 8099
heartbeat_interval_sec: 1
""", encoding="utf-8")

    agent_proc = subprocess.Popen(
        [str(agent_bin.resolve()), "--config", str(config_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    
    def cleanup():
        agent_proc.terminate()
        try:
            agent_proc.wait(timeout=5)
        except:
            agent_proc.kill()

    # 5. Wait for approval
    approved = False
    for _ in range(20):
        time.sleep(2)
        resp = requests.post(
            f"{api_url}/api/v1/maas/{mesh_id}/nodes/{node_id}/approve",
            headers={"X-API-Key": token},
            timeout=5
        )
        if resp.status_code == 200:
            approved = True
            break
    
    if not add_stage("approve", approved):
        cleanup()
        return report

    # 6. Wait for heartbeat
    healthy = False
    import sqlite3
    db_path = os.environ.get("DATABASE_URL", "").replace("sqlite:///", "")
    if not db_path: db_path = "maas_prod_smoke_final_v5.db" # Fallback

    for _ in range(20):
        time.sleep(2)
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            res = cursor.execute("SELECT last_seen FROM mesh_nodes WHERE id=?", (node_id,)).fetchone()
            if res and res[0]:
                healthy = True
                conn.close()
                break
            conn.close()
        except Exception as e:
            print(f"DB check error: {e}")
    
    if not add_stage("heartbeat", healthy):
        cleanup()
        return report

    # 7. Heal
    cleanup()
    time.sleep(2)
    resp = requests.post(
        f"{api_url}/api/v1/maas/{mesh_id}/nodes/{node_id}/heal",
        headers={"X-API-Key": token},
        timeout=30
    )
    add_stage("heal", resp.status_code == 200, resp.json())
    
    if resp.status_code == 200:
        report["ready"] = True
    
    return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="http://localhost:8088")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        res = run_verification(args.api_url, tmp)
        print(json.dumps(res, indent=2))
        sys.exit(0 if res["ready"] else 1)
