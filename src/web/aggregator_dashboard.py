import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

import requests
from flask import Flask, jsonify

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("FLASK_SECRET_KEY is required for session security")


def _load_nodes_from_env() -> List[Dict[str, str]]:
    """Load nodes from MESH_NODES environment variable."""
    nodes_env = os.getenv("MESH_NODES", "")
    nodes = []
    if nodes_env:
        for node_str in nodes_env.split(","):
            parts = node_str.strip().split("|")
            if len(parts) >= 2:
                nodes.append({"name": parts[0], "url": parts[1]})
    return nodes or [{"name": "Local", "url": "http://127.0.0.1:8080"}]


NODES: List[Dict[str, str]] = _load_nodes_from_env()


def check_node(node: Dict[str, str]) -> Optional[Dict[str, Any]]:
    try:
        r = requests.get(f"{node['url']}/api/stats", timeout=2)
        data = r.json()
        data["status"] = "ONLINE"
        data["name"] = node["name"]
        data["url"] = node["url"]
        return data
    except:
        return {
            "name": node["name"],
            "url": node["url"],
            "status": "OFFLINE",
            "balance": "0",
            "packets_relayed": 0,
            "uptime": 0,
            "earnings_today": "0",
        }


@app.route("/")
def index():
    return """
<!DOCTYPE html>
<html>
<head>
    <title>x0tta6bl4 MESH NETWORK</title>
    <meta http-equiv="refresh" content="3">
    <style>
        body { font-family: monospace; background: #000; color: #0f0; padding: 20px; margin: 0; }
        h1 { text-align: center; border-bottom: 2px solid #0f0; padding-bottom: 10px; margin-bottom: 30px; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .section { border: 1px solid #333; padding: 15px; background: #0a0a0a; }
        .section h2 { margin-top: 0; color: #0f0; font-size: 1em; border-bottom: 1px solid #333; padding-bottom: 5px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { border: 1px solid #222; padding: 8px; text-align: left; font-size: 0.9em; }
        th { color: #666; }
        .online { color: #0f0; }
        .offline { color: #f00; }
        .stats { display: flex; justify-content: space-around; text-align: center; margin: 20px 0; }
        .stat { padding: 10px; }
        .stat-value { font-size: 2em; color: #fff; }
        .stat-label { color: #666; font-size: 0.8em; }
        .topology { padding: 20px; text-align: center; }
        .node-box { display: inline-block; border: 2px solid #0f0; padding: 10px 20px; margin: 5px; }
        .arrow { color: #0f0; margin: 0 10px; }
    </style>
</head>
<body>
    <h1>🌐 x0tta6bl4 MESH NETWORK COMMAND CENTER</h1>
    
    <div class="stats" id="stats">Loading...</div>
    
    <div class="grid">
        <div class="section">
            <h2>📡 ACTIVE NODES</h2>
            <div id="nodes">Loading...</div>
        </div>
        <div class="section">
            <h2>🔗 MESH TOPOLOGY</h2>
            <div id="topology" class="topology">Loading...</div>
        </div>
    </div>
    
    <script>
        fetch('/api/network')
            .then(r => r.json())
            .then(data => {
                let totalPackets = 0, totalBalance = 0, onlineCount = 0;
                
                // Nodes table
                let nodesHtml = '<table><tr><th>ID</th><th>STATUS</th><th>PACKETS</th><th>PEERS</th></tr>';
                data.nodes.forEach(n => {
                    const status = n.status === 'ONLINE' ? 'online' : 'offline';
                    const peers = n.mesh?.alive_peers || 0;
                    nodesHtml += `<tr>
                        <td>${n.name}</td>
                        <td class="${status}">${n.status}</td>
                        <td>${n.packets_relayed}</td>
                        <td>${peers}</td>
                    </tr>`;
                    if(n.status === 'ONLINE') {
                        totalPackets += n.packets_relayed;
                        totalBalance += parseFloat(n.balance);
                        onlineCount++;
                    }
                });
                nodesHtml += '</table>';
                document.getElementById('nodes').innerHTML = nodesHtml;
                
                // Stats
                document.getElementById('stats').innerHTML = `
                    <div class="stat"><div class="stat-value">${onlineCount}/${data.nodes.length}</div><div class="stat-label">NODES ONLINE</div></div>
                    <div class="stat"><div class="stat-value">${totalPackets.toLocaleString()}</div><div class="stat-label">TOTAL PACKETS</div></div>
                    <div class="stat"><div class="stat-value">${totalBalance.toFixed(2)}</div><div class="stat-label">NETWORK X0T</div></div>
                `;
                
                // Topology
                let topoHtml = '<div style="margin-bottom:20px">Traffic Flow:</div>';
                topoHtml += '<div class="node-box">CLIENT</div>';
                data.nodes.filter(n => n.status === 'ONLINE').forEach((n, i) => {
                    topoHtml += '<span class="arrow">→</span>';
                    topoHtml += `<div class="node-box">${n.name.split(' ')[0]}</div>`;
                });
                topoHtml += '<span class="arrow">→</span><div class="node-box">INTERNET</div>';
                document.getElementById('topology').innerHTML = topoHtml;
            });
    </script>
</body>
</html>
    """


@app.route("/api/network")
def network():
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(check_node, NODES))
    return jsonify({"nodes": results})


if __name__ == "__main__":
    print("Starting Aggregator on http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000)
