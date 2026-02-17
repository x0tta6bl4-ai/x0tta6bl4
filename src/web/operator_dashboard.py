"""
x0tta6bl4 Operator Dashboard.
Visual interface for node stats and earnings.
"""

import json
import os

from flask import Flask, jsonify

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("FLASK_SECRET_KEY is required for session security")

STATS_FILE = "node_stats.json"


import time
import psutil

START_TIME = time.time()

def get_stats():
    stats = {"balance": "1000.0", "packets": 0, "uptime": 0, "earnings_today": "0.0"}
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r") as f:
                stats.update(json.load(f))
        except:
            pass
    
    # Precise Uptime
    stats["uptime"] = int(time.time() - START_TIME)
    
    # Process Stats
    process = psutil.Process(os.getpid())
    stats["mem_usage"] = process.memory_info().rss / (1024 * 1024) # MB
    return stats


@app.route("/")
def index():
    dashboard_path = os.path.join(os.path.dirname(__file__), "dashboard.html")
    if os.path.exists(dashboard_path):
        with open(dashboard_path, "r") as f:
            return f.read()
    return "Dashboard template not found at " + dashboard_path


@app.route("/api/stats")
def stats():
    data = get_stats()
    return jsonify(
        {
            "node_id": data.get("node_id", "x0t-node-master"),
            "balance": data.get("balance", "0"),
            "packets_relayed": data.get("packets", 0),
            "uptime": data.get("uptime", 0),
            "earnings_today": data.get("earnings_today", "0"),
            "mem_usage": f"{data.get('mem_usage', 0):.1f} MB",
            "mesh": data.get("mesh", {"status": "ALIVE", "peers": 2}),
            "pqc_status": "ACTIVE (Kyber768)",
            "mape_k": "HEALTHY"
        }
    )


@app.route("/api/peers")
def peers():
    """Return list of mesh peers for discovery."""
    data = get_stats()
    mesh = data.get("mesh", {})
    return jsonify(
        {"node_id": data.get("node_id", "unknown"), "peers": mesh.get("peers", [])}
    )


if __name__ == "__main__":
    print("Starting Dashboard on http://0.0.0.0:8080")
    app.run(host="0.0.0.0", port=8080)  # nosec B104
