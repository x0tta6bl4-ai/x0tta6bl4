import asyncio
import psutil
import time
import sys
import os
import json
from aiohttp import web
import aiohttp

# Путь к ядру
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from brain_core.consciousness import ConsciousnessEngine

# КОНФИГУРАЦИЯ
MY_PORT = 9091
PEERS = [
    "http://89.125.1.107:9091",  # Node 1 (Master)
    "http://77.83.245.27:9091",  # Node 2
    "http://62.133.60.252:9091", # Node 3
    "http://89.125.1.107:9094"   # Node 4 (Local Dev via Tunnel)
]

# Глобальное состояние
engine = ConsciousnessEngine()
latest_metrics = {}
peer_status = {}

async def get_system_metrics():
    """Сбор данных с железа"""
    try:
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent
        # Эмуляция латенси (потом заменим на пинг)
        latency = 85.0 
        return {
            'cpu_percent': cpu,
            'memory_percent': mem,
            'latency_ms': latency,
            'packet_loss': 0.0,
            'mesh_connectivity': len([p for p, s in peer_status.items() if s]),
            'frequency_hz': 108.0
        }
    except Exception:
        return {}

async def background_brain_loop(app):
    """Главный цикл сознания"""
    global latest_metrics
    print("🧠 Brain Loop Started")
    
    while True:
        raw = await get_system_metrics()
        if raw:
            # Считаем Phi
            metrics = engine.get_consciousness_metrics(raw)
            
            # Обновляем глобальное состояние для API
            latest_metrics = {
                "phi_ratio": metrics.phi_ratio,
                "state": metrics.state.value,
                "cpu": raw['cpu_percent'],
                "ram": raw['memory_percent'],
                "peers_online": raw['mesh_connectivity'],
                "timestamp": time.time()
            }
            
            # Лог в консоль
            icon = "🟢" if metrics.state.value == "HARMONIC" else "🟡"
            print(f"{icon} [{metrics.state.value}] Phi: {metrics.phi_ratio:.3f} | Peers: {latest_metrics['peers_online']}")
            
        await asyncio.sleep(15)

async def background_peer_discovery(app):
    """Опрос соседей"""
    print("📡 Peer Discovery Started")
    async with aiohttp.ClientSession() as session:
        while True:
            for peer in PEERS:
                # Не пингуем сами себя (нужно бы IP проверить, но пока просто skip errors)
                try:
                    async with session.get(f"{peer}/metrics", timeout=2) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            peer_status[peer] = True
                            # print(f"  ✅ Peer {peer} is alive (Phi: {data.get('phi_ratio')})")
                        else:
                            peer_status[peer] = False
                except Exception:
                    peer_status[peer] = False
            
            await asyncio.sleep(30)

# --- API HANDLERS ---

async def handle_metrics(request):
    """Отдает метрики в JSON"""
    return web.json_response(latest_metrics)

async def handle_health(request):
    return web.Response(text="OK")

# --- MAIN ---

async def init_app():
    app = web.Application()
    app.add_routes([
        web.get('/metrics', handle_metrics),
        web.get('/health', handle_health)
    ])
    
    # Запускаем фоновые задачи
    app.cleanup_ctx.append(start_background_tasks)
    return app

async def start_background_tasks(app):
    app['brain'] = asyncio.create_task(background_brain_loop(app))
    app['discovery'] = asyncio.create_task(background_peer_discovery(app))
    yield
    app['brain'].cancel()
    app['discovery'].cancel()
    await app['brain']
    await app['discovery']

if __name__ == '__main__':
    web.run_app(init_app(), port=MY_PORT)
