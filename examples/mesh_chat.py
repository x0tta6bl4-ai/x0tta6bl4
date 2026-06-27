#!/usr/bin/env python3
"""
Mesh Chat - P2P чат через x0tta6bl4 mesh сеть.

Usage:
    Terminal 1: python3 examples/mesh_chat.py alice 5001
    Terminal 2: python3 examples/mesh_chat.py bob 5002
    Terminal 3: python3 examples/mesh_chat.py charlie 5003

Commands:
    /peers   - показать подключённых пиров
    /routes  - показать таблицу маршрутизации
    /stats   - показать статистику
    /help    - показать справку
    /quit    - выйти
"""
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.network.mesh_node_complete import CompleteMeshNode, MeshConfig


class MeshChat:
    """Интерактивный P2P чат через mesh сеть."""
    
    def __init__(self, node_id: str, port: int):
        self.node_id = node_id
        self.port = port
        self.node: CompleteMeshNode = None
        self._running = False
    
    async def start(self):
        """Запустить чат."""
        print(f"\n{'='*60}")
        print(f"  x0tta6bl4 MESH CHAT")
        print(f"{'='*60}")
        print(f"  Node ID: {self.node_id}")
        print(f"  Port:    {self.port}")
        print(f"{'='*60}\n")
        
        # Создаём mesh node
        config = MeshConfig(
            node_id=self.node_id,
            port=self.port,
            traffic_profile="gaming",  # Low latency
            obfuscation="xor"
        )
        
        self.node = CompleteMeshNode(config)
        
        # Callbacks
        @self.node.on_message
        async def on_message(source: str, payload: bytes):
            try:
                message = payload.decode('utf-8')
                print(f"\r\n[{source}]: {message}")
                print(f"[{self.node_id}]> ", end="", flush=True)
            except Exception:
                pass
        
        @self.node.on_peer_discovered
        async def on_peer(peer_id: str):
            print(f"\r\n🟢 {peer_id} joined the mesh")
            print(f"[{self.node_id}]> ", end="", flush=True)
        
        @self.node.on_peer_lost
        async def on_lost(peer_id: str):
            print(f"\r\n🔴 {peer_id} left the mesh")
            print(f"[{self.node_id}]> ", end="", flush=True)
        
        await self.node.start()
        
        print("Discovering peers...")
        print("Type /help for commands\n")
        
        self._running = True
        
        # Запускаем input loop
        await self._input_loop()
    
    async def _input_loop(self):
        """Цикл ввода."""
        loop = asyncio.get_event_loop()
        
        while self._running:
            try:
                # Читаем ввод асинхронно
                line = await loop.run_in_executor(
                    None,
                    lambda: input(f"[{self.node_id}]> ")
                )
                
                if not line:
                    continue
                
                await self._handle_input(line.strip())
                
            except EOFError:
                break
            except KeyboardInterrupt:
                print("\n")
                break
        
        await self.stop()
    
    async def _handle_input(self, line: str):
        """Обработка ввода."""
        if line.startswith("/"):
            await self._handle_command(line)
        else:
            await self._send_message(line)
    
    async def _handle_command(self, cmd: str):
        """Обработка команды."""
        parts = cmd.split()
        command = parts[0].lower()
        
        if command == "/peers":
            peers = self.node.get_peers()
            if peers:
                print(f"\n📡 Connected peers ({len(peers)}):")
                for peer in peers:
                    print(f"  • {peer}")
            else:
                print("\n📡 No peers connected yet")
            print()
        
        elif command == "/routes":
            routes = self.node.get_routes()
            if routes:
                print(f"\n🗺️ Routing table ({len(routes)} entries):")
                for dest, route in routes.items():
                    via = f"via {route.next_hop}" if route.next_hop != dest else "direct"
                    print(f"  ✓ {dest}: {via} (hops={route.hop_count}, age={route.age:.1f}s)")
            else:
                print("\n🗺️ Routing table empty")
            print()
        
        elif command == "/stats":
            stats = self.node.get_stats()
            print(f"\n📊 Statistics:")
            print(f"  Node ID: {stats['node_id']}")
            print(f"  Port:    {stats['port']}")
            print(f"  Peers:   {stats['peers_count']}")
            if 'routing' in stats:
                r = stats['routing']
                print(f"  Packets sent:      {r.get('packets_sent', 0)}")
                print(f"  Packets received:  {r.get('packets_received', 0)}")
                print(f"  Packets forwarded: {r.get('packets_forwarded', 0)}")
            print()
        
        elif command == "/msg":
            # Private message: /msg bob Hello Bob!
            if len(parts) < 3:
                print("Usage: /msg <peer> <message>")
                return
            
            target = parts[1]
            message = " ".join(parts[2:])
            
            if await self.node.send_message(target, message.encode('utf-8')):
                print(f"✓ Sent to {target}")
            else:
                print(f"✗ Failed to send to {target}")
        
        elif command == "/help":
            print("""
Commands:
  /peers   - Show connected peers
  /routes  - Show routing table
  /stats   - Show statistics
  /msg <peer> <text> - Send private message
  /help    - Show this help
  /quit    - Exit chat

To send a message to all peers, just type and press Enter.
""")
        
        elif command in ("/quit", "/exit", "/q"):
            self._running = False
        
        else:
            print(f"Unknown command: {command}")
            print("Type /help for available commands")
    
    async def _send_message(self, message: str):
        """Отправить сообщение всем peers."""
        peers = self.node.get_peers()
        
        if not peers:
            print("No peers connected. Waiting for discovery...")
            return
        
        payload = message.encode('utf-8')
        sent = 0
        
        for peer in peers:
            if await self.node.send_message(peer, payload):
                sent += 1
        
        if sent > 0:
            print(f"✓ Sent to {sent} peer(s)")
        else:
            print("✗ Failed to send message")
    
    async def stop(self):
        """Остановить чат."""
        if self.node:
            await self.node.stop()
        print("Goodbye!")


async def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("Usage: python3 mesh_chat.py <node_id> [port]")
        print("\nExample:")
        print("  python3 mesh_chat.py alice 5001")
        print("  python3 mesh_chat.py bob 5002")
        sys.exit(1)
    
    node_id = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
    
    chat = MeshChat(node_id, port)
    await chat.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
