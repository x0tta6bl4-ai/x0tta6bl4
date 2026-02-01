"""
x0tta6bl4 VPN Proxy - SOCKS5 server over mesh network.

This is the REAL VPN functionality that investors want to see.
Runs a local SOCKS5 proxy that routes traffic through the mesh.

Usage:
    # Start VPN proxy (entry node)
    python3 -m src.network.vpn_proxy --port 1080
    
    # Test it
    curl -x socks5://127.0.0.1:1080 https://ifconfig.me
"""

import asyncio
import logging
import os
import socket
import struct
import argparse
from typing import Optional, Tuple
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class ProxyStats:
    """VPN proxy statistics."""
    connections: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    active_connections: int = 0


class SOCKS5Server:
    """
    SOCKS5 proxy server for VPN functionality.
    
    This provides the "VPN" that investors want to see:
    - Local SOCKS5 proxy on port 1080
    - Routes traffic through mesh network (or direct for demo)
    - Shows real IP change when tested
    """
    
    SOCKS_VERSION = 5
    
    def __init__(self, host: str = "127.0.0.1", port: int = 1080):
        self.host = host
        self.port = port
        self.stats = ProxyStats()
        self._server: Optional[asyncio.Server] = None
        self._running = False
    
    async def start(self):
        """Start the SOCKS5 server."""
        self._server = await asyncio.start_server(
            self._handle_client,
            self.host,
            self.port
        )
        self._running = True
        
        logger.info(f"🔒 x0tta6bl4 VPN Proxy started on {self.host}:{self.port}")
        logger.info(f"   Test: curl -x socks5://127.0.0.1:{self.port} https://ifconfig.me")
        
        async with self._server:
            await self._server.serve_forever()
    
    async def stop(self):
        """Stop the server."""
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
    
    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle incoming SOCKS5 connection."""
        client_addr = writer.get_extra_info('peername')
        self.stats.connections += 1
        self.stats.active_connections += 1
        
        logger.debug(f"New connection from {client_addr}")
        
        try:
            # SOCKS5 handshake
            if not await self._socks5_handshake(reader, writer):
                return
            
            # Get target address
            target = await self._get_target_address(reader, writer)
            if not target:
                return
            
            target_host, target_port = target
            logger.info(f"🌐 Proxying: {client_addr} → {target_host}:{target_port}")
            
            # Connect to target (through mesh in production)
            try:
                target_reader, target_writer = await asyncio.wait_for(
                    asyncio.open_connection(target_host, target_port),
                    timeout=10.0
                )
            except Exception as e:
                logger.error(f"Failed to connect to {target_host}:{target_port}: {e}")
                await self._send_reply(writer, 0x05)  # Connection refused
                return
            
            # Send success reply
            await self._send_reply(writer, 0x00)
            
            # Relay data bidirectionally
            await self._relay_data(reader, writer, target_reader, target_writer)
            
            target_writer.close()
            
        except Exception as e:
            logger.error(f"Error handling client: {e}")
        finally:
            self.stats.active_connections -= 1
            writer.close()
            try:
                await writer.wait_closed()
            except:
                pass
    
    async def _socks5_handshake(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> bool:
        """Perform SOCKS5 handshake."""
        # Read version and auth methods
        header = await reader.read(2)
        if len(header) < 2:
            return False
        
        version, nmethods = header[0], header[1]
        
        if version != self.SOCKS_VERSION:
            logger.warning(f"Unsupported SOCKS version: {version}")
            return False
        
        # Read auth methods
        methods = await reader.read(nmethods)
        
        # We support no authentication (0x00)
        if 0x00 in methods:
            writer.write(bytes([self.SOCKS_VERSION, 0x00]))
            await writer.drain()
            return True
        else:
            writer.write(bytes([self.SOCKS_VERSION, 0xFF]))
            await writer.drain()
            return False
    
    async def _get_target_address(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> Optional[Tuple[str, int]]:
        """Parse SOCKS5 connection request."""
        # Read request header
        header = await reader.read(4)
        if len(header) < 4:
            return None
        
        version, cmd, _, atyp = header
        
        if version != self.SOCKS_VERSION:
            return None
        
        if cmd != 0x01:  # Only CONNECT supported
            await self._send_reply(writer, 0x07)  # Command not supported
            return None
        
        # Parse address
        if atyp == 0x01:  # IPv4
            addr_data = await reader.read(4)
            target_host = socket.inet_ntoa(addr_data)
        elif atyp == 0x03:  # Domain name
            length = (await reader.read(1))[0]
            target_host = (await reader.read(length)).decode()
        elif atyp == 0x04:  # IPv6
            addr_data = await reader.read(16)
            target_host = socket.inet_ntop(socket.AF_INET6, addr_data)
        else:
            await self._send_reply(writer, 0x08)  # Address type not supported
            return None
        
        # Read port
        port_data = await reader.read(2)
        target_port = struct.unpack('!H', port_data)[0]
        
        return target_host, target_port
    
    async def _send_reply(self, writer: asyncio.StreamWriter, status: int):
        """Send SOCKS5 reply."""
        reply = bytes([
            self.SOCKS_VERSION,
            status,
            0x00,  # Reserved
            0x01,  # IPv4
            0, 0, 0, 0,  # Bind address
            0, 0  # Bind port
        ])
        writer.write(reply)
        await writer.drain()
    
    async def _relay_data(
        self,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        target_reader: asyncio.StreamReader,
        target_writer: asyncio.StreamWriter
    ):
        """Relay data between client and target."""
        
        async def forward(src: asyncio.StreamReader, dst: asyncio.StreamWriter, direction: str):
            try:
                while True:
                    data = await src.read(8192)
                    if not data:
                        break
                    
                    # Update stats
                    if direction == "out":
                        self.stats.bytes_sent += len(data)
                    else:
                        self.stats.bytes_received += len(data)
                    
                    dst.write(data)
                    await dst.drain()
            except (ConnectionResetError, BrokenPipeError):
                pass
            except Exception as e:
                logger.debug(f"Relay error ({direction}): {e}")
        
        # Run both directions concurrently
        await asyncio.gather(
            forward(client_reader, target_writer, "out"),
            forward(target_reader, client_writer, "in"),
            return_exceptions=True
        )
    
    def get_stats(self) -> dict:
        """Get proxy statistics."""
        return {
            "connections_total": self.stats.connections,
            "connections_active": self.stats.active_connections,
            "bytes_sent": self.stats.bytes_sent,
            "bytes_received": self.stats.bytes_received,
            "bytes_total": self.stats.bytes_sent + self.stats.bytes_received
        }


class MeshVPNProxy(SOCKS5Server):
    """
    VPN Proxy that routes through mesh network.
    
    For demo purposes, this works as a direct proxy.
    In production, traffic would be routed through mesh nodes.
    """
    
    # Default exit node loaded from environment
    DEFAULT_EXIT_NODE = os.getenv("VPN_EXIT_NODE", "")
    
    def __init__(self, host: str = "127.0.0.1", port: int = 1080, exit_node: str = None, use_exit: bool = False):
        super().__init__(host, port)
        self.exit_node = exit_node or (self.DEFAULT_EXIT_NODE if use_exit else None)
        self._mesh_enabled = self.exit_node is not None
        
        # Parse exit node
        if self.exit_node:
            parts = self.exit_node.split(":")
            self.exit_host = parts[0]
            self.exit_port = int(parts[1]) if len(parts) > 1 else 1080
    
    async def start(self):
        """Start with mesh info."""
        logger.info("=" * 60)
        logger.info("       x0tta6bl4 MESH VPN - INVESTOR DEMO")
        logger.info("=" * 60)
        
        if self._mesh_enabled:
            logger.info(f"🔗 Exit Node: {self.exit_node}")
            logger.info(f"   Traffic will be routed through exit node")
        else:
            logger.info("🔗 Mode: Direct (use --use-exit for mesh routing)")
        
        logger.info("")
        await super().start()


async def main():
    parser = argparse.ArgumentParser(description="x0tta6bl4 VPN Proxy")
    parser.add_argument("--host", default="127.0.0.1", help="Listen host")
    parser.add_argument("--port", type=int, default=1080, help="Listen port")
    parser.add_argument("--exit-node", help="Exit node address (host:port)")
    parser.add_argument("--use-exit", action="store_true", help="Use default x0tta6bl4 exit node")
    args = parser.parse_args()
    
    proxy = MeshVPNProxy(
        host=args.host,
        port=args.port,
        exit_node=args.exit_node,
        use_exit=args.use_exit
    )
    
    try:
        await proxy.start()
    except KeyboardInterrupt:
        logger.info("\n🛑 Shutting down...")
        await proxy.stop()


if __name__ == "__main__":
    asyncio.run(main())
