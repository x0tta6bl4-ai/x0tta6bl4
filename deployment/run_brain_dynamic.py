import asyncio
import psutil
import time
import sys
import os
import json
from aiohttp import web
import aiohttp

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from brain_core.consciousness import ConsciousnessEngine

# --- КОНФИГУРАЦИЯ ---
MY_PORT = 9092
BOOTSTRAP_NODE = "http://89.125.1.107:9092"  # Маяк
DB_FILE = "/opt/x0tta6bl4/peers.json"        # Чтобы не забыть пиров после рестарта

# --- ГЛОБАЛЬНОЕ СОСТОЯНИЕ ---
engine = ConsciousnessEngine()
latest_metrics = {}
known_peers = set()  # Множество уникальных адресов (set)

# Добавляем Маяк в известные пиры сразу (чтобы даже Маяк знал сам себя или соседей)
if BOOTSTRAP_NODE not in known_peers:
    known_peers.add(BOOTSTRAP_NODE)

# --- ФУНКЦИИ РАБОТЫ С ДИСКОМ ---
def load_peers():
    global known_peers
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r') as f:
                peers = json.load(f)
                known_peers.update(peers)
            print(f"📂 Loaded {len(known_peers)} peers from disk")
        except Exception as e:
            print(f"⚠️ Failed to load peers: {e}")

def save_peers():
    try:
        with open(DB_FILE, 'w') as f:
            json.dump(list(known_peers), f)
    except Exception as e:
        print(f"⚠️ Failed to save peers: {e}")

# --- СБОР МЕТРИК ---
async def get_system_metrics():
    try:
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent
        latency = 85.0 
        return {
            'cpu_percent': cpu,
            'memory_percent': mem,
            'latency_ms': latency,
            'packet_loss': 0.0,
            'mesh_connectivity': len(known_peers),
            'frequency_hz': 108.0
        }
    except Exception:
        return {}

# --- API HANDLERS ---

async def handle_register(request):
    """Принимаем заявку от нового узла"""
    try:
        data = await request.json()
        new_peer = data.get('url')
        
        if new_peer and new_peer not in known_peers:
            print(f"👋 NEW NODE JOINED: {new_peer}")
            known_peers.add(new_peer)
            save_peers()
            
        # Отдаем ему наш список, чтобы он тоже знал всех
        return web.json_response({"status": "welcome", "peers": list(known_peers)})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)

async def handle_metrics(request):
    return web.json_response(latest_metrics)

async def handle_peers_list(request):
    return web.json_response({"peers": list(known_peers)})

# --- ФОНОВЫЕ ЗАДАЧИ ---

async def task_join_network(app):
    """Стучимся к Маяку при старте"""
    # Определяем свой внешний IP (хак для простоты, в проде лучше конфиг)
    # Для демо просто берем IP из запроса, но здесь мы клиент.
    # Пусть Маяк определяет наш IP. 
    # Пока шлем "я тут", а Маяк пусть сам парсит IP из request.remote (сложнее).
    # Проще: Пытаемся определить свой IP через внешний сервис или конфиг.
    
    # ВРЕМЕННОЕ РЕШЕНИЕ: Мы просто регистрируем известные нам IP
    # В идеале каждый узел должен знать свой Public IP.
    pass

async def task_brain_loop(app):
    global latest_metrics
    print("🧠 Brain Loop Started")
    
    while True:
        raw = await get_system_metrics()
        if raw:
            metrics = engine.get_consciousness_metrics(raw)
            latest_metrics = {
                "phi_ratio": metrics.phi_ratio,
                "state": metrics.state.value,
                "cpu": raw['cpu_percent'],
                "peers_count": len(known_peers),
                "timestamp": time.time()
            }
            
            # Попытка регистрации на Маяке (каждую минуту, чтобы поддерживать актуальность)
            # Мы должны знать свой URL. Для простоты пока хардкод в deploy скрипте, 
            # который создаст файл config.json с URL узла.
            
        await asyncio.sleep(15)

async def task_sync_peers(app):
    """Синхронизация списков с соседями"""
    print("🔄 Sync Peers Started")
    async with aiohttp.ClientSession() as session:
        while True:
            # 1. Читаем свой конфиг (какой у меня IP?)
            my_url = None
            if os.path.exists("/opt/x0tta6bl4/my_url.txt"):
                with open("/opt/x0tta6bl4/my_url.txt", "r") as f:
                    my_url = f.read().strip()
            
            current_peers = list(known_peers)
            for peer in current_peers:
                if peer == my_url: continue # Не стучимся к себе
                
                try:
                    # Регистрируемся у пира + получаем его список
                    payload = {"url": my_url} if my_url else {}
                    async with session.post(f"{peer}/register", json=payload, timeout=5) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            new_peers = data.get('peers', [])
                            for p in new_peers:
                                if p and p not in known_peers:
                                    known_peers.add(p)
                                    print(f"  ➕ Discovered new peer via gossip: {p}")
                            save_peers()
                except Exception:
                    pass # Пир недоступен
            
            await asyncio.sleep(30)

import aiohttp_cors

# --- MAIN ---

import base64

# --- КОНФИГУРАЦИЯ VPN (Individual per Node) ---
# ЗАПОЛНИТЕ ЭТО РЕАЛЬНЫМИ ДАННЫМИ ИЗ X-UI КАЖДОГО СЕРВЕРА
NODES_INFO = [
    {
        "ip": "89.125.1.107", 
        "name": "🇪🇺 EU-Central (Brain)",
        "port": 443,
        "pbk": "REPLACE_WITH_REAL_KEY_NODE_1",
        "sid": "1234aa",
        "sni": "yahoo.com",
        "fp": "chrome",
        "flow": "xtls-rprx-vision",
        "security": "reality"
    },
    {
        "ip": "77.83.245.27", 
        "name": "🇪🇺 EU-West (Worker)",
        "port": 443,
        "pbk": "REPLACE_WITH_REAL_KEY_NODE_2",
        "sid": "1234bb",
        "sni": "google.com",
        "fp": "chrome",
        "flow": "xtls-rprx-vision",
        "security": "reality"
    },
    {
        "ip": "62.133.60.252", 
        "name": "🇷🇺 RU-North (Stealth)",
        "port": 443,
        "pbk": "REPLACE_WITH_REAL_KEY_NODE_3",
        "sid": "1234cc",
        "sni": "yandex.ru",
        "fp": "chrome",
        "flow": "xtls-rprx-vision",
        "security": "reality"
    }
]

async def handle_subscription(request):
    """Генерация единой подписки для клиента"""
    try:
        user_uuid = request.match_info.get('uuid', '')
        if not user_uuid:
            return web.Response(text="UUID required", status=400)
            
        configs = []
        
        # Генерируем VLESS ссылку для каждого узла
        for node in NODES_INFO:
            # Формат: vless://uuid@ip:port?params#Name
            vless = (
                f"vless://{user_uuid}@{node['ip']}:{node['port']}"
                f"?type=tcp&security={node['security']}"
                f"&pbk={node['pbk']}&fp={node['fp']}"
                f"&sni={node['sni']}&sid={node['sid']}"
                f"&flow={node['flow']}"
                f"#{node['name']}"
            )
            configs.append(vless)
            
        # Объединяем и кодируем в Base64 (стандарт подписок)
        plain_text = "\n".join(configs)
        b64_config = base64.b64encode(plain_text.encode('utf-8')).decode('utf-8')
        
        return web.Response(text=b64_config, content_type="text/plain")
        
    except Exception as e:
        return web.Response(text=str(e), status=500)

async def init_app():
    load_peers()
    app = web.Application()
    
    # Настройка CORS
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
            )
    })
    
    # Маршруты с CORS
    metrics_resource = cors.add(app.router.add_resource("/metrics"))
    cors.add(metrics_resource.add_route("GET", handle_metrics))
    
    register_resource = cors.add(app.router.add_resource("/register"))
    cors.add(register_resource.add_route("POST", handle_register))
    
    peers_resource = cors.add(app.router.add_resource("/peers"))
    cors.add(peers_resource.add_route("GET", handle_peers_list))
    
    # ПОДПИСКА (Единый вход)
    sub_resource = cors.add(app.router.add_resource("/sub/{uuid}"))
    cors.add(sub_resource.add_route("GET", handle_subscription))
    
    app.cleanup_ctx.append(start_background_tasks)
    return app

async def start_background_tasks(app):
    app['brain'] = asyncio.create_task(task_brain_loop(app))
    app['sync'] = asyncio.create_task(task_sync_peers(app))
    yield
    app['brain'].cancel()
    app['sync'].cancel()

if __name__ == '__main__':
    web.run_app(init_app(), port=MY_PORT)
