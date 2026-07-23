#!/usr/bin/env python3
"""
scripts/manage_mesh.py
======================
Interactive control panel to monitor mesh nodes, inject anomalies,
trigger MAPE-K self-healing, and manage the local Docker-compose stack.
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.request

DASHBOARD_URL = "http://127.0.0.1:10899"
COMPOSE_FILE = "deploy/docker-compose/compose.yaml"


def call_api(endpoint: str, data: dict = None) -> dict:
    """Helper to query the dashboard gateway API."""
    url = f"{DASHBOARD_URL}{endpoint}"
    try:
        if data is not None:
            req = urllib.request.Request(
                url,
                data=json.dumps(data).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
        else:
            req = urllib.request.Request(url, headers={"User-Agent": "x0tta6bl4-CLI"})

        with urllib.request.urlopen(req, timeout=2.0) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        print(f"Error communicating with dashboard server at {url}: {e}")
        print("Make sure the dashboard server is running (python3 dashboard/server.py)")
        sys.exit(1)


def get_compose_status():
    """Run docker compose ps to view container states."""
    try:
        res = subprocess.run(
            ["docker", "compose", "-f", COMPOSE_FILE, "ps", "--format", "json"],
            capture_output=True,
            text=True,
            check=True
        )
        # Parse output line by line or as JSON array
        lines = res.stdout.strip().splitlines()
        containers = []
        for line in lines:
            try:
                containers.append(json.loads(line))
            except Exception:
                pass
        return containers
    except Exception as e:
        print(f"Could not read docker-compose status: {e}")
        return []


def show_status(args):
    """Monitor command: lists containers, SPIRE state, and live metrics."""
    print("\n=== 🐳 DOCKER COMPOSE MESH STATUS ===")
    containers = get_compose_status()
    if not containers:
        print("No running mesh containers found.")
    else:
        for c in containers:
            name = c.get("Name", "unknown")
            state = c.get("State", "unknown")
            status = c.get("Status", "unknown")
            print(f"- {name:<20} Status: {state:<10} ({status})")

    print("\n=== 📊 LIVE TELEMETRY METRICS (API) ===")
    metrics_data = call_api("/api/metrics")
    nodes = metrics_data.get("nodes", {})
    
    print(f"{'Node ID':<15} | {'Docker Status':<12} | {'Loss (%)':<10} | {'Latency (ms)':<12}")
    print("-" * 60)
    for node_id, data in nodes.items():
        status = data.get("status", "unknown")
        loss = data.get("loss", 0.0)
        latency = data.get("latency", 0.0)
        
        status_color = ""
        if status == "attacked":
            status_color = "⚠️  ATTACKED"
        elif status == "stable":
            status_color = "🟢 STABLE"
        elif status == "offline":
            status_color = "🔴 OFFLINE"
            
        print(f"{node_id:<15} | {status_color:<12} | {loss:<10.2f} | {latency:<12.2f}")
    print()


def inject_anomaly(args):
    """Attack command: Injects loss/latency anomalies into the node."""
    node = args.node
    print(f"Injecting network anomalies on node: {node}...")
    res = call_api("/api/anomaly", {"node": node, "action": "attack"})
    if res.get("status") == "success":
        print(f"🚨 Anomaly injected successfully! Status: ATTACKED.")
        print(f"Check your dashboard: {DASHBOARD_URL}/mesh_mapek_dashboard.html")
    else:
        print("Failed to inject anomaly.")


def heal_anomaly(args):
    """Heal command: Clears anomalies, triggering MAPE-K restoration simulation."""
    node = args.node
    print(f"Triggering MAPE-K self-healing on node: {node}...")
    res = call_api("/api/anomaly", {"node": node, "action": "heal"})
    if res.get("status") == "success":
        print(f"✅ Self-healing completed! State restored to STABLE.")
        print(f"Check your dashboard: {DASHBOARD_URL}/mesh_mapek_dashboard.html")
    else:
        print("Failed to heal node.")


def stop_all(args):
    """Stop command: Stops all containers and kills the dashboard server."""
    print("Stopping local Docker-compose stack...")
    subprocess.run(["docker", "compose", "-f", COMPOSE_FILE, "down"])
    
    print("Stopping dashboard server listening on port 10899...")
    # Find process listening on port 10899 and kill it
    try:
        res = subprocess.run(
            ["fuser", "-k", "10899/tcp"],
            capture_output=True,
            text=True
        )
        print("Dashboard server stopped.")
    except Exception:
        pass
    print("Mesh stack stopped successfully.")


def main():
    parser = argparse.ArgumentParser(
        description="Interactive mesh network control panel CLI."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Status subcommand
    subparsers.add_parser("status", help="Show current containers and live metrics.")

    # Attack subcommand
    attack_parser = subparsers.add_parser("attack", help="Inject network anomaly to a node.")
    attack_parser.add_argument(
        "--node", default="node-c", help="Target Node ID (e.g. node-a, node-c)"
    )

    # Heal subcommand
    heal_parser = subparsers.add_parser("heal", help="Trigger MAPE-K self-healing on a node.")
    heal_parser.add_argument(
        "--node", default="node-c", help="Target Node ID (e.g. node-a, node-c)"
    )

    # Stop subcommand
    subparsers.add_parser("stop", help="Down the docker stack and close dashboard gateway.")

    args = parser.parse_args()

    if args.command == "status":
        show_status(args)
    elif args.command == "attack":
        inject_anomaly(args)
    elif args.command == "heal":
        heal_anomaly(args)
    elif args.command == "stop":
        stop_all(args)


if __name__ == "__main__":
    main()
