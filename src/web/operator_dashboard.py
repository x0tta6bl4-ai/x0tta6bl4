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


def get_stats():
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {"balance": "1000.0", "packets": 0, "uptime": 0, "earnings_today": "0.0"}


@app.route("/")
def index():
    return """
<!DOCTYPE html>
<html>
<head>
    <title>x0tta6bl4 Node Panel</title>
    <meta http-equiv="refresh" content="2">
    <style>
        body { 
            font-family: 'Courier New', monospace; 
            background: #000; 
            color: #0f0; 
            margin: 0;
            padding: 20px;
        }
        .container { max_width: 800px; margin: 0 auto; }
        .header { border-bottom: 1px solid #333; padding-bottom: 10px; margin-bottom: 20px; }
        .card { 
            border: 1px solid #333; 
            padding: 20px; 
            margin-bottom: 15px;
            background: #0a0a0a;
        }
        .metric { font-size: 2.5em; font-weight: bold; color: #fff; }
        .label { color: #666; font-size: 0.8em; text-transform: uppercase; }
        .row { display: flex; gap: 20px; }
        .col { flex: 1; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>x0tta6bl4 Node Control</h1>
            <p>Status: ONLINE | Port: 10809</p>
        </div>
        
        <div class="row">
            <div class="col card">
                <div class="label">Balance (X0T)</div>
                <div class="metric" id="balance">...</div>
            </div>
            <div class="col card">
                <div class="label">Today Earnings</div>
                <div class="metric" id="today" style="color:#0f0">...</div>
            </div>
        </div>
        
        <div class="card">
            <div class="label">Traffic Stats</div>
            <div class="row">
                <div class="col">
                    <h3>Packets</h3>
                    <div class="metric" id="packets">0</div>
                </div>
                <div class="col">
                    <h3>Uptime</h3>
                    <div class="metric" id="uptime">0s</div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        fetch('/api/stats')
            .then(r => r.json())
            .then(data => {
                document.getElementById('balance').innerText = parseFloat(data.balance).toFixed(4);
                document.getElementById('today').innerText = '+' + parseFloat(data.earnings_today).toFixed(4);
                document.getElementById('packets').innerText = data.packets_relayed;
                
                const uptime = parseInt(data.uptime);
                const h = Math.floor(uptime / 3600);
                const m = Math.floor((uptime % 3600) / 60);
                const s = uptime % 60;
                document.getElementById('uptime').innerText = `${h}h ${m}m ${s}s`;
            });
    </script>
</body>
</html>
    """


@app.route("/api/stats")
def stats():
    data = get_stats()
    return jsonify(
        {
            "node_id": data.get("node_id", "unknown"),
            "balance": data.get("balance", "0"),
            "packets_relayed": data.get("packets", 0),
            "uptime": data.get("uptime", 0),
            "earnings_today": data.get("earnings_today", "0"),
            "mesh": data.get("mesh", {}),
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
