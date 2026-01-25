#!/usr/bin/env python3
"""
Mesh RPC - Remote Procedure Calls через mesh сеть.

Позволяет вызывать функции на удалённых узлах mesh сети.

Usage:
    # Сервер
    python3 examples/mesh_rpc.py server worker1 5001
    
    # Клиент
    python3 examples/mesh_rpc.py client master 5000

API Example:
    @rpc.method("add")
    async def add(a: int, b: int) -> int:
        return a + b
    
    # Вызов на удалённом узле
    result = await rpc.call("worker1", "add", a=1, b=2)
    # result = 3
"""
import asyncio
import sys
import os
import json
import uuid
import traceback
from typing import Callable, Any, Dict
from functools import wraps

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.network.mesh_node_complete import CompleteMeshNode, MeshConfig


class MeshRPC:
    """
    RPC система через mesh сеть.
    
    Регистрируйте методы через декоратор @rpc.method()
    Вызывайте на удалённых узлах через rpc.call()
    """
    
    def __init__(self, node_id: str, port: int):
        self.node_id = node_id
        self.port = port
        self.node: CompleteMeshNode = None
        
        # Зарегистрированные методы
        self._methods: Dict[str, Callable] = {}
        
        # Pending вызовы (ожидаем ответа)
        self._pending: Dict[str, asyncio.Future] = {}
        
        self._running = False
    
    async def start(self):
        """Запуск RPC сервера."""
        config = MeshConfig(
            node_id=self.node_id,
            port=self.port,
            traffic_profile="gaming"  # Low latency
        )
        
        self.node = CompleteMeshNode(config)
        
        @self.node.on_message
        async def on_message(source: str, payload: bytes):
            await self._handle_message(source, payload)
        
        @self.node.on_peer_discovered
        async def on_peer(peer_id: str):
            print(f"🟢 Peer connected: {peer_id}")
        
        await self.node.start()
        self._running = True
        
        print(f"🚀 Mesh RPC started: {self.node_id}:{self.port}")
        print(f"📋 Registered methods: {list(self._methods.keys())}")
    
    async def stop(self):
        """Остановка."""
        self._running = False
        if self.node:
            await self.node.stop()
    
    def method(self, name: str = None):
        """
        Декоратор для регистрации RPC метода.
        
        @rpc.method("add")
        async def add(a: int, b: int) -> int:
            return a + b
        """
        def decorator(func: Callable):
            method_name = name or func.__name__
            self._methods[method_name] = func
            
            @wraps(func)
            async def wrapper(*args, **kwargs):
                return await func(*args, **kwargs)
            return wrapper
        return decorator
    
    async def call(self, peer: str, method: str, **kwargs) -> Any:
        """
        Вызвать метод на удалённом узле.
        
        result = await rpc.call("worker1", "add", a=1, b=2)
        """
        call_id = str(uuid.uuid4())[:8]
        
        # Создаём future для ожидания ответа
        future = asyncio.get_event_loop().create_future()
        self._pending[call_id] = future
        
        # Формируем запрос
        request = {
            "type": "rpc_call",
            "id": call_id,
            "method": method,
            "args": kwargs
        }
        
        # Отправляем
        await self.node.send_message(peer, json.dumps(request).encode())
        
        try:
            # Ждём ответа
            result = await asyncio.wait_for(future, timeout=30.0)
            return result
        except asyncio.TimeoutError:
            self._pending.pop(call_id, None)
            raise TimeoutError(f"RPC call to {peer}.{method} timed out")
    
    async def _handle_message(self, source: str, payload: bytes):
        """Обработка RPC сообщений."""
        try:
            msg = json.loads(payload.decode())
        except:
            return
        
        msg_type = msg.get("type")
        
        if msg_type == "rpc_call":
            await self._handle_call(source, msg)
        
        elif msg_type == "rpc_response":
            await self._handle_response(msg)
    
    async def _handle_call(self, source: str, msg: dict):
        """Обработка входящего вызова."""
        call_id = msg["id"]
        method_name = msg["method"]
        args = msg.get("args", {})
        
        response = {
            "type": "rpc_response",
            "id": call_id
        }
        
        if method_name not in self._methods:
            response["error"] = f"Method not found: {method_name}"
        else:
            try:
                func = self._methods[method_name]
                result = await func(**args) if asyncio.iscoroutinefunction(func) else func(**args)
                response["result"] = result
            except Exception as e:
                response["error"] = f"{type(e).__name__}: {str(e)}"
                traceback.print_exc()
        
        # Отправляем ответ
        await self.node.send_message(source, json.dumps(response).encode())
    
    async def _handle_response(self, msg: dict):
        """Обработка ответа на вызов."""
        call_id = msg["id"]
        
        if call_id not in self._pending:
            return
        
        future = self._pending.pop(call_id)
        
        if "error" in msg:
            future.set_exception(Exception(msg["error"]))
        else:
            future.set_result(msg.get("result"))
    
    def get_peers(self):
        """Получить список peers."""
        return self.node.get_peers() if self.node else []


# === Demo Application ===

async def run_worker(node_id: str, port: int):
    """Запуск worker node с RPC методами."""
    rpc = MeshRPC(node_id, port)
    
    # Регистрируем методы
    @rpc.method("ping")
    async def ping():
        return "pong"
    
    @rpc.method("add")
    async def add(a: int, b: int) -> int:
        return a + b
    
    @rpc.method("multiply")
    async def multiply(a: int, b: int) -> int:
        return a * b
    
    @rpc.method("echo")
    async def echo(message: str) -> str:
        return f"Echo from {node_id}: {message}"
    
    @rpc.method("status")
    async def status():
        return {
            "node_id": node_id,
            "port": port,
            "methods": list(rpc._methods.keys())
        }
    
    @rpc.method("compute")
    async def compute(operation: str, values: list) -> float:
        """Сложные вычисления."""
        if operation == "sum":
            return sum(values)
        elif operation == "avg":
            return sum(values) / len(values) if values else 0
        elif operation == "max":
            return max(values) if values else 0
        elif operation == "min":
            return min(values) if values else 0
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    await rpc.start()
    
    print(f"\n🔧 Worker ready. Available methods:")
    for name in rpc._methods:
        print(f"   • {name}")
    print("\nWaiting for RPC calls... (Ctrl+C to exit)\n")
    
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        await rpc.stop()


async def run_client(node_id: str, port: int):
    """Запуск клиента для RPC вызовов."""
    rpc = MeshRPC(node_id, port)
    await rpc.start()
    
    print(f"\n🖥️ RPC Client ready")
    print("Commands:")
    print("  call <peer> <method> [args...]")
    print("  peers")
    print("  quit\n")
    
    loop = asyncio.get_event_loop()
    
    while True:
        try:
            line = await loop.run_in_executor(None, lambda: input(f"[{node_id}]> "))
            parts = line.strip().split()
            
            if not parts:
                continue
            
            cmd = parts[0].lower()
            
            if cmd == "call" and len(parts) >= 3:
                peer = parts[1]
                method = parts[2]
                
                # Парсим аргументы (key=value)
                kwargs = {}
                for arg in parts[3:]:
                    if "=" in arg:
                        key, val = arg.split("=", 1)
                        # Пробуем парсить как число или JSON
                        try:
                            val = json.loads(val)
                        except:
                            pass
                        kwargs[key] = val
                
                try:
                    print(f"📤 Calling {peer}.{method}({kwargs})...")
                    result = await rpc.call(peer, method, **kwargs)
                    print(f"📥 Result: {result}")
                except Exception as e:
                    print(f"❌ Error: {e}")
            
            elif cmd == "peers":
                peers = rpc.get_peers()
                print(f"📡 Peers: {peers or 'none'}")
            
            elif cmd in ("quit", "exit", "q"):
                break
            
            else:
                print("Usage: call <peer> <method> [key=value ...]")
                print("Example: call worker1 add a=10 b=20")
                
        except (EOFError, KeyboardInterrupt):
            break
    
    await rpc.stop()


async def main():
    if len(sys.argv) < 3:
        print(__doc__)
        print("Usage:")
        print("  python3 mesh_rpc.py server <node_id> [port]")
        print("  python3 mesh_rpc.py client <node_id> [port]")
        sys.exit(1)
    
    mode = sys.argv[1]
    node_id = sys.argv[2]
    port = int(sys.argv[3]) if len(sys.argv) > 3 else 5000
    
    if mode == "server":
        await run_worker(node_id, port)
    elif mode == "client":
        await run_client(node_id, port)
    else:
        print(f"Unknown mode: {mode}")


if __name__ == "__main__":
    asyncio.run(main())
