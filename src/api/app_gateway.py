from __future__ import annotations
import asyncio
import json
import os
import time
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from typing import Any, Dict

app = FastAPI(title="GHOST-CORE App API")

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MESH_STATS_FILE = Path(".tmp/mesh_stats.json")
ECONOMY_FILE = Path(".tmp/economy_state.json")
STARTED_AT_MONOTONIC = time.monotonic()


def _read_json_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _uptime_seconds() -> int:
    return max(0, int(time.monotonic() - STARTED_AT_MONOTONIC))


@app.get("/api/status")
async def get_status():
    """Сводный статус системы для дашборда."""
    stats = _read_json_file(MESH_STATS_FILE)
    econ = _read_json_file(ECONOMY_FILE)

    return {
        "node_id": stats.get("node_id", "GHOST-NODE"),
        "uptime": _uptime_seconds(),
        "protocol": "x0tta6bl4_pulse v4.1",
        "coherence": stats.get("pulse_coherence", "100.0%"),
        "shield_hits": stats.get("dropped_probes", 0),
        "balance": econ.get("balance", "0"),
        "daily": econ.get("daily_earnings", "0"),
        "gen": stats.get("evolution_gen", 1),
        "status": stats.get("pulse_status", "NORMAL"),
        "peers": stats.get("peers", []),
        "peer_count": stats.get("peer_count", 0),
    }


@app.get("/api/peers")
async def get_peers():
    """Список пиров mesh-сети."""
    stats = _read_json_file(MESH_STATS_FILE)
    return {
        "node_id": stats.get("node_id", "GHOST-NODE"),
        "peers": stats.get("peers", []),
        "peer_count": stats.get("peer_count", 0),
    }

@app.post("/api/control/{action}")
async def control_system(action: str, params: Dict = None):
    """Управление системой через веб-интерфейс."""
    params = params or {}
    cmd_file = Path(".tmp/pulse_cmd.json")

    if action == "switch_profile":
        target = params.get("profile", "teams")
        with open(cmd_file, "w") as f:
            json.dump({"action": "switch_profile", "target": target}, f)
        return {"status": "ok", "msg": f"Pulse shifted to {target}"}

    if action == "start_vpn":
        peer = params.get("peer")
        with open(cmd_file, "w") as f:
            json.dump({"action": "start_vpn", "peer_id": peer}, f)
        return {"status": "ok", "msg": "VPN Activation requested"}

    raise HTTPException(status_code=400, detail="Unknown action")

@app.websocket("/ws/pulse")
async def pulse_stream(websocket: WebSocket):
    """Стрим 'Пульса' (наносекундных интервалов) для осциллографа."""
    await websocket.accept()
    try:
        while True:
            # В реальности мы бы читали из eBPF кольцевого буфера
            # Для UI симулируем текущий поток на основе профиля
            data = {
                "ts": time.time(),
                "interval_ns": int(40_000_000 + (os.urandom(1)[0] * 1000)), # ~40ms base
                "amplitude": 0.5 + (os.urandom(1)[0] / 512.0)
            }
            await websocket.send_json(data)
            await asyncio.sleep(0.04) # Match teams timing
    except Exception as e:
        print(f"WS Disconnected: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8083)

