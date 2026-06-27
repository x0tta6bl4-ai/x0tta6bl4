#!/usr/bin/env python3
"""
Mesh Monitor - Real-time мониторинг mesh сети.

Usage:
    python3 examples/mesh_monitor.py monitor 5000
    
Показывает:
- Подключённые peers
- Таблицу маршрутизации
- Статистику пакетов
- Сетевую топологию
"""
import asyncio
import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.network.mesh_node_complete import CompleteMeshNode, MeshConfig


class MeshMonitor:
    """Real-time mesh network monitor."""
    
    REFRESH_INTERVAL = 2.0  # секунды
    
    def __init__(self, node_id: str, port: int):
        self.node_id = node_id
        self.port = port
        self.node: CompleteMeshNode = None
        
        # История событий
        self._events: list = []
        self._max_events = 20
        
        # Topology data from other nodes
        self._topology: dict = {}
        
        self._running = False
    
    async def start(self):
        """Запуск монитора."""
        config = MeshConfig(
            node_id=self.node_id,
            port=self.port,
            traffic_profile="none"
        )
        
        self.node = CompleteMeshNode(config)
        
        @self.node.on_message
        async def on_message(source: str, payload: bytes):
            await self._handle_message(source, payload)
        
        @self.node.on_peer_discovered
        async def on_peer(peer_id: str):
            self._add_event(f"🟢 {peer_id} joined")
            # Запрашиваем топологию у нового peer
            await self._request_topology(peer_id)
        
        @self.node.on_peer_lost
        async def on_lost(peer_id: str):
            self._add_event(f"🔴 {peer_id} left")
            self._topology.pop(peer_id, None)
        
        await self.node.start()
        self._running = True
        
        # Запускаем UI loop
        await self._monitor_loop()
    
    async def _handle_message(self, source: str, payload: bytes):
        """Обработка сообщений."""
        try:
            msg = json.loads(payload.decode())
            
            if msg.get("type") == "topology_request":
                # Отвечаем своей топологией
                await self._send_topology(source)
            
            elif msg.get("type") == "topology_response":
                # Сохраняем топологию peer
                self._topology[source] = msg.get("data", {})
            
            else:
                self._add_event(f"📨 {source}: {payload[:50]}")
                
        except json.JSONDecodeError:
            self._add_event(f"📨 {source}: {payload[:50]}")
    
    async def _request_topology(self, peer: str):
        """Запросить топологию у peer."""
        msg = json.dumps({"type": "topology_request"}).encode()
        await self.node.send_message(peer, msg)
    
    async def _send_topology(self, peer: str):
        """Отправить свою топологию."""
        msg = json.dumps({
            "type": "topology_response",
            "data": {
                "peers": self.node.get_peers(),
                "routes": {k: v.hop_count for k, v in self.node.get_routes().items()}
            }
        }).encode()
        await self.node.send_message(peer, msg)
    
    def _add_event(self, event: str):
        """Добавить событие в историю."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._events.append(f"[{timestamp}] {event}")
        if len(self._events) > self._max_events:
            self._events.pop(0)
    
    async def _monitor_loop(self):
        """Основной цикл мониторинга."""
        try:
            while self._running:
                self._render()
                await asyncio.sleep(self.REFRESH_INTERVAL)
        except KeyboardInterrupt:
            pass
        finally:
            await self.node.stop()
    
    def _render(self):
        """Отрисовка UI."""
        # Clear screen
        print("\033[2J\033[H", end="")
        
        stats = self.node.get_stats()
        routes = self.node.get_routes()
        peers = self.node.get_peers()
        
        # Header
        print("╔" + "═"*58 + "╗")
        print(f"║{'x0tta6bl4 MESH MONITOR':^58}║")
        print("╠" + "═"*58 + "╣")
        print(f"║ Node: {self.node_id:<20} Port: {self.port:<20}║")
        print(f"║ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S'):<40}║")
        print("╠" + "═"*58 + "╣")
        
        # Peers
        print(f"║ {'PEERS (' + str(len(peers)) + ')':^56} ║")
        print("╟" + "─"*58 + "╢")
        if peers:
            for peer in peers[:5]:
                route = routes.get(peer)
                hops = f"{route.hop_count} hop" if route else "?"
                age = f"{route.age:.0f}s" if route else "?"
                print(f"║   • {peer:<20} {hops:<10} age: {age:<12}║")
        else:
            print(f"║   {'No peers connected':^52}║")
        
        # Routes
        print("╠" + "═"*58 + "╣")
        print(f"║ {'ROUTING TABLE (' + str(len(routes)) + ')':^56} ║")
        print("╟" + "─"*58 + "╢")
        if routes:
            for dest, route in list(routes.items())[:5]:
                via = f"via {route.next_hop}" if route.next_hop != dest else "direct"
                print(f"║   {dest:<15} → {via:<25} ({route.hop_count}h)║")
        else:
            print(f"║   {'No routes':^52}║")
        
        # Statistics
        print("╠" + "═"*58 + "╣")
        print(f"║ {'STATISTICS':^56} ║")
        print("╟" + "─"*58 + "╢")
        if 'routing' in stats:
            r = stats['routing']
            print(f"║   Packets sent:      {r.get('packets_sent', 0):<32}║")
            print(f"║   Packets received:  {r.get('packets_received', 0):<32}║")
            print(f"║   Packets forwarded: {r.get('packets_forwarded', 0):<32}║")
            print(f"║   Routes discovered: {r.get('routes_discovered', 0):<32}║")
        
        # Topology Map
        print("╠" + "═"*58 + "╣")
        print(f"║ {'NETWORK TOPOLOGY':^56} ║")
        print("╟" + "─"*58 + "╢")
        
        # Собираем все известные узлы
        all_nodes = {self.node_id}
        all_nodes.update(peers)
        for peer, topo in self._topology.items():
            all_nodes.update(topo.get("peers", []))
        
        if len(all_nodes) > 1:
            # Простая визуализация
            nodes_str = " ←→ ".join(sorted(all_nodes)[:4])
            print(f"║   {nodes_str:^52}║")
        else:
            print(f"║   {'[' + self.node_id + '] (alone)':^52}║")
        
        # Events
        print("╠" + "═"*58 + "╣")
        print(f"║ {'RECENT EVENTS':^56} ║")
        print("╟" + "─"*58 + "╢")
        if self._events:
            for event in self._events[-5:]:
                print(f"║   {event:<54}║")
        else:
            print(f"║   {'No events yet':^52}║")
        
        # Footer
        print("╠" + "═"*58 + "╣")
        print(f"║ {'Press Ctrl+C to exit':^56} ║")
        print("╚" + "═"*58 + "╝")


async def main():
    if len(sys.argv) < 2:
        print("Usage: python3 mesh_monitor.py <node_id> [port]")
        sys.exit(1)
    
    node_id = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
    
    monitor = MeshMonitor(node_id, port)
    await monitor.start()


if __name__ == "__main__":
    asyncio.run(main())
