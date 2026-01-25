# x0tta6bl4 Mesh Network

## 🚀 Quick Start

### 3 терминала - 2 минуты до работающей сети

**Terminal 1:**
```bash
python3 examples/mesh_chat.py alice 5001
```

**Terminal 2:**
```bash
python3 examples/mesh_chat.py bob 5002
```

**Terminal 3:**
```bash
python3 examples/mesh_chat.py charlie 5003
```

Через 2-3 секунды узлы найдут друг друга!

```
[alice]> Hello everyone!
✓ Sent to 2 peer(s)

[bob]: Hello everyone!
[charlie]: Hello everyone!
```

## 📦 Architecture

```
┌─────────────────────────────────────────────────────┐
│           x0tta6bl4 MESH NETWORK STACK              │
├─────────────────────────────────────────────────────┤
│                                                     │
│  📱 Application Layer                               │
│     └─ CompleteMeshNode API                        │
│        • send_message(dest, payload)               │
│        • broadcast(payload)                        │
│        • on_message callback                       │
│                                                     │
│  🗺️ Routing Layer (AODV-like)                       │
│     └─ MeshRouter                                  │
│        • Reactive route discovery                  │
│        • Multi-hop forwarding                      │
│        • Loop prevention (TTL, seq numbers)        │
│                                                     │
│  🔍 Discovery Layer                                 │
│     └─ MeshDiscovery                               │
│        • UDP Multicast (LAN)                       │
│        • Bootstrap nodes                           │
│        • Kademlia DHT                              │
│                                                     │
│  📡 Transport Layer                                 │
│     └─ ShapedUDPTransport                          │
│        • Traffic Shaping (gaming, voice, video)    │
│        • Obfuscation (XOR, FakeTLS, Shadowsocks)   │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## 🔧 API Usage

### Basic Node

```python
from src.network.mesh_node_complete import CompleteMeshNode, MeshConfig

# Создаём node
config = MeshConfig(
    node_id="my-node",
    port=5000,
    traffic_profile="gaming",  # Low latency
    obfuscation="xor"          # Anti-censorship
)

node = CompleteMeshNode(config)

# Callback для входящих сообщений
@node.on_message
async def handle(source: str, payload: bytes):
    print(f"Message from {source}: {payload}")

# Запускаем
await node.start()

# Отправляем сообщение (автоматический routing)
await node.send_message("bob", b"Hello Bob!")

# Broadcast всем peers
await node.broadcast(b"Hello everyone!")

# Получаем информацию
peers = node.get_peers()      # ["bob", "charlie"]
routes = node.get_routes()    # {dest: RouteEntry}
stats = node.get_stats()      # Full statistics
```

### Quick Start Helper

```python
from src.network.mesh_node_complete import create_mesh_node

# Одна строка для запуска
node = await create_mesh_node("alice", 5001)
await node.send_message("bob", b"Hello!")
```

## 🗺️ Routing Protocol

AODV-like реактивная маршрутизация:

1. **Route Request (RREQ)**: Broadcast запрос маршрута
2. **Route Reply (RREP)**: Unicast ответ с маршрутом
3. **Data Forwarding**: Multi-hop пересылка
4. **Route Error (RERR)**: Уведомление о broken links

### Пример Multi-hop

```
Alice ──► Bob ──► Charlie
   │              ▲
   └──────────────┘
   (routing via Bob)
```

Если Alice не видит Charlie напрямую:
1. Alice broadcast RREQ для Charlie
2. Bob получает RREQ, пересылает дальше
3. Charlie отвечает RREP через Bob
4. Alice узнаёт маршрут: Charlie via Bob (2 hops)
5. DATA пакеты идут: Alice → Bob → Charlie

## 🔒 Security Layers

| Layer | Protection |
|-------|------------|
| **XOR** | Basic obfuscation |
| **FakeTLS** | Looks like HTTPS |
| **Shadowsocks** | ChaCha20-Poly1305 encryption |
| **Domain Fronting** | CDN masking |
| **Traffic Shaping** | DPI evasion |

## 📊 Traffic Profiles

```python
# Gaming - минимальная латентность (10-33ms intervals)
traffic_profile="gaming"

# VoIP - стабильные 20ms intervals
traffic_profile="voice_call"

# Streaming - burst patterns
traffic_profile="video_streaming"

# Web browsing - random patterns
traffic_profile="web_browsing"
```

## 🐳 Docker Deployment

```bash
# Запуск 4-узловой сети
./scripts/mesh-test.sh up

# Статус
./scripts/mesh-test.sh status

# Логи
./scripts/mesh-test.sh logs node-alpha

# Остановка
./scripts/mesh-test.sh down
```

## 📈 Monitoring

- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3001

## ✅ Tests

```bash
# Unit tests
python3 -m pytest tests/unit/network/ -v

# Integration tests (включая multi-hop)
python3 -m pytest tests/integration/test_mesh_routing.py -v

# All tests
python3 -m pytest tests/ -v --ignore=tests/performance
```

## 📁 File Structure

```
src/network/
├── mesh_node_complete.py    # Full-featured node
├── mesh_node.py             # Basic node (legacy)
├── routing/
│   ├── __init__.py
│   └── mesh_router.py       # AODV routing
├── discovery/
│   ├── __init__.py
│   └── protocol.py          # Multicast + DHT
├── transport/
│   ├── __init__.py
│   ├── udp_shaped.py        # UDP + shaping
│   └── websocket_shaped.py  # WebSocket
└── obfuscation/
    ├── __init__.py
    ├── base.py              # Transport manager
    ├── faketls.py           # FakeTLS
    ├── shadowsocks.py       # Shadowsocks
    └── traffic_shaping.py   # DPI evasion

examples/
└── mesh_chat.py             # Demo chat app

docker/
├── docker-compose.mesh.yml  # 4-node network
└── mesh-node/
    ├── Dockerfile
    └── entrypoint.py
```

## 🎯 Use Cases

1. **P2P Messaging** - Приватный чат без серверов
2. **File Sharing** - Распределённая передача файлов
3. **IoT Networks** - Mesh между устройствами
4. **Censorship Bypass** - Обход блокировок
5. **Emergency Networks** - Связь без инфраструктуры
