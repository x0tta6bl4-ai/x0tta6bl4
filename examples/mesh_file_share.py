#!/usr/bin/env python3
"""
Mesh File Share - P2P обмен файлами через mesh сеть.

Usage:
    python3 examples/mesh_file_share.py alice 5001
    
Commands:
    /send <peer> <file>  - отправить файл
    /list                - показать полученные файлы
    /peers               - показать peers
"""
import asyncio
import sys
import os
import base64
import hashlib
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.network.mesh_node_complete import CompleteMeshNode, MeshConfig


class FileTransfer:
    """Протокол передачи файлов."""
    
    CHUNK_SIZE = 32 * 1024  # 32KB chunks
    
    @staticmethod
    def create_file_header(filename: str, size: int, checksum: str) -> bytes:
        """Создать заголовок файла."""
        header = {
            "type": "file_header",
            "filename": filename,
            "size": size,
            "checksum": checksum,
            "chunks": (size + FileTransfer.CHUNK_SIZE - 1) // FileTransfer.CHUNK_SIZE
        }
        return json.dumps(header).encode()
    
    @staticmethod
    def create_chunk(filename: str, index: int, data: bytes) -> bytes:
        """Создать chunk файла."""
        chunk = {
            "type": "file_chunk",
            "filename": filename,
            "index": index,
            "data": base64.b64encode(data).decode()
        }
        return json.dumps(chunk).encode()
    
    @staticmethod
    def parse_message(data: bytes) -> dict:
        """Распарсить сообщение."""
        try:
            return json.loads(data.decode())
        except:
            return {"type": "text", "content": data.decode()}


class MeshFileShare:
    """P2P File Sharing через mesh."""
    
    def __init__(self, node_id: str, port: int):
        self.node_id = node_id
        self.port = port
        self.node: CompleteMeshNode = None
        
        # Директория для файлов
        self.download_dir = Path(f"./mesh_downloads_{node_id}")
        self.download_dir.mkdir(exist_ok=True)
        
        # Входящие файлы
        self._incoming: dict = {}  # filename -> {chunks: [], total: int, checksum: str}
        
        self._running = False
    
    async def start(self):
        """Запуск."""
        print(f"\n{'='*60}")
        print(f"  x0tta6bl4 MESH FILE SHARE")
        print(f"{'='*60}")
        print(f"  Node:     {self.node_id}")
        print(f"  Port:     {self.port}")
        print(f"  Downloads: {self.download_dir}")
        print(f"{'='*60}\n")
        
        config = MeshConfig(
            node_id=self.node_id,
            port=self.port,
            traffic_profile="file_download"
        )
        
        self.node = CompleteMeshNode(config)
        
        @self.node.on_message
        async def on_message(source: str, payload: bytes):
            await self._handle_message(source, payload)
        
        @self.node.on_peer_discovered
        async def on_peer(peer_id: str):
            print(f"🟢 {peer_id} connected")
            self._prompt()
        
        await self.node.start()
        
        print("Type /help for commands\n")
        self._running = True
        
        await self._input_loop()
    
    async def _handle_message(self, source: str, payload: bytes):
        """Обработка входящего сообщения."""
        msg = FileTransfer.parse_message(payload)
        
        if msg["type"] == "file_header":
            # Начало передачи файла
            filename = msg["filename"]
            self._incoming[filename] = {
                "chunks": [None] * msg["chunks"],
                "total": msg["chunks"],
                "size": msg["size"],
                "checksum": msg["checksum"],
                "source": source,
                "received": 0
            }
            print(f"\n📥 Receiving file from {source}: {filename} ({msg['size']} bytes)")
            self._prompt()
            
        elif msg["type"] == "file_chunk":
            filename = msg["filename"]
            if filename in self._incoming:
                info = self._incoming[filename]
                chunk_data = base64.b64decode(msg["data"])
                info["chunks"][msg["index"]] = chunk_data
                info["received"] += 1
                
                # Progress
                progress = info["received"] / info["total"] * 100
                print(f"\r📥 {filename}: {progress:.0f}%", end="", flush=True)
                
                # Завершено?
                if info["received"] == info["total"]:
                    await self._save_file(filename)
    
    async def _save_file(self, filename: str):
        """Сохранить полученный файл."""
        info = self._incoming.pop(filename)
        
        # Собираем файл
        file_data = b"".join(info["chunks"])
        
        # Проверяем checksum
        checksum = hashlib.md5(file_data).hexdigest()
        if checksum != info["checksum"]:
            print(f"\n❌ Checksum mismatch for {filename}!")
            return
        
        # Сохраняем
        filepath = self.download_dir / filename
        filepath.write_bytes(file_data)
        
        print(f"\n✅ File saved: {filepath}")
        self._prompt()
    
    async def send_file(self, peer: str, filepath: str):
        """Отправить файл."""
        path = Path(filepath)
        
        if not path.exists():
            print(f"❌ File not found: {filepath}")
            return
        
        if peer not in self.node.get_peers():
            print(f"❌ Peer not found: {peer}")
            return
        
        file_data = path.read_bytes()
        filename = path.name
        checksum = hashlib.md5(file_data).hexdigest()
        
        print(f"📤 Sending {filename} to {peer}...")
        
        # Отправляем header
        header = FileTransfer.create_file_header(filename, len(file_data), checksum)
        await self.node.send_message(peer, header)
        
        # Отправляем chunks
        total_chunks = (len(file_data) + FileTransfer.CHUNK_SIZE - 1) // FileTransfer.CHUNK_SIZE
        
        for i in range(total_chunks):
            start = i * FileTransfer.CHUNK_SIZE
            end = min(start + FileTransfer.CHUNK_SIZE, len(file_data))
            chunk_data = file_data[start:end]
            
            chunk = FileTransfer.create_chunk(filename, i, chunk_data)
            await self.node.send_message(peer, chunk)
            
            progress = (i + 1) / total_chunks * 100
            print(f"\r📤 {filename}: {progress:.0f}%", end="", flush=True)
            
            await asyncio.sleep(0.01)  # Небольшая пауза
        
        print(f"\n✅ File sent: {filename}")
    
    def _prompt(self):
        print(f"[{self.node_id}]> ", end="", flush=True)
    
    async def _input_loop(self):
        loop = asyncio.get_event_loop()
        
        while self._running:
            try:
                line = await loop.run_in_executor(None, lambda: input(f"[{self.node_id}]> "))
                await self._handle_input(line.strip())
            except (EOFError, KeyboardInterrupt):
                break
        
        await self.node.stop()
    
    async def _handle_input(self, line: str):
        if not line:
            return
        
        parts = line.split()
        cmd = parts[0].lower()
        
        if cmd == "/send":
            if len(parts) < 3:
                print("Usage: /send <peer> <file>")
                return
            await self.send_file(parts[1], " ".join(parts[2:]))
        
        elif cmd == "/list":
            files = list(self.download_dir.glob("*"))
            if files:
                print(f"\n📁 Downloaded files ({len(files)}):")
                for f in files:
                    print(f"  • {f.name} ({f.stat().st_size} bytes)")
            else:
                print("📁 No files downloaded yet")
            print()
        
        elif cmd == "/peers":
            peers = self.node.get_peers()
            print(f"\n📡 Peers ({len(peers)}): {', '.join(peers) or 'none'}\n")
        
        elif cmd == "/help":
            print("""
Commands:
  /send <peer> <file>  - Send file to peer
  /list                - List downloaded files
  /peers               - Show connected peers
  /quit                - Exit
""")
        
        elif cmd in ("/quit", "/q"):
            self._running = False


async def main():
    if len(sys.argv) < 2:
        print("Usage: python3 mesh_file_share.py <node_id> [port]")
        sys.exit(1)
    
    node_id = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
    
    app = MeshFileShare(node_id, port)
    await app.start()


if __name__ == "__main__":
    asyncio.run(main())
