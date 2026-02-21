#!/usr/bin/env python3
"""
x0tta6bl4 Obfuscated SOCKS5 Proxy
SOCKS5 proxy with DPI evasion using obfuscation techniques.

Usage:
    python3 -m src.network.obfuscated_socks5 --port 1080 --method faketls

Methods:
    - faketls: TLS 1.3 handshake mimicry
    - shadowsocks: Shadowsocks AEAD encryption
    - domain_fronting: Domain fronting through CDNs
    - stegomesh: Steganographic protocol mimicry
    - hybrid: Combination of multiple methods
"""

import argparse
import asyncio
import logging
import os
import socket
import struct
from typing import Optional, Tuple

from .vpn_obfuscation_manager import (
    ObfuscationMethod,
    RotationStrategy,
    VPNObfuscationManager,
    get_vpn_obfuscator,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


class ObfuscatedSOCKS5Server:
    """
    SOCKS5 server with traffic obfuscation for DPI bypass.
    
    Features:
    - Multiple obfuscation methods (FakeTLS, Shadowsocks, etc.)
    - Rotating parameters (SNI, fingerprints)
    - Traffic shaping
    """
    
    SOCKS_VERSION = 5
    
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 1080,
        obfuscation_method: str = "faketls",
        rotation_interval: int = 300,
    ):
        self.host = host
        self.port = port
        self._server: Optional[asyncio.Server] = None
        self._running = False
        
        # Initialize obfuscation manager
        self.obfuscator = get_vpn_obfuscator()
        
        # Set obfuscation method
        method_map = {
            "none": ObfuscationMethod.NONE,
            "faketls": ObfuscationMethod.FAKETLS,
            "shadowsocks": ObfuscationMethod.SHADOWSOCKS,
            "domain_fronting": ObfuscationMethod.DOMAIN_FRONTING,
            "stegomesh": ObfuscationMethod.STEGOMESH,
            "hybrid": ObfuscationMethod.HYBRID,
        }
        
        self.obfuscator.set_obfuscation_method(
            method_map.get(obfuscation_method, ObfuscationMethod.FAKETLS)
        )
        self.obfuscator.set_rotation_strategy(RotationStrategy.TIME_BASED)
        self.obfuscator.set_rotation_interval(rotation_interval)
        
        # Statistics
        self.connections = 0
        self.bytes_sent = 0
        self.bytes_recv = 0
    
    async def start(self):
        """Start the SOCKS5 server."""
        self._server = await asyncio.start_server(
            self._handle_client, self.host, self.port
        )
        self._running = True
        
        params = self.obfuscator.get_current_parameters()
        
        logger.info("=" * 60)
        logger.info("  x0tta6bl4 OBFUSCATED SOCKS5 PROXY")
        logger.info("=" * 60)
        logger.info(f"  Listening: {self.host}:{self.port}")
        logger.info(f"  Obfuscation: {params['method']}")
        logger.info(f"  SNI: {params['sni']}")
        logger.info(f"  Fingerprint: {params['fingerprint']}")
        logger.info(f"  Rotation: {params['rotation_interval']}s")
        logger.info("=" * 60)
        logger.info(f"  Test: curl -x socks5://127.0.0.1:{self.port} https://ifconfig.me")
        logger.info("=" * 60)
        
        async with self._server:
            await self._server.serve_forever()
    
    async def stop(self):
        """Stop the server."""
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
    
    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        """Handle incoming SOCKS5 connection."""
        client_addr = writer.get_extra_info("peername")
        self.connections += 1
        
        try:
            # SOCKS5 handshake
            if not await self._socks5_handshake(reader, writer):
                return
            
            # Get target address
            target = await self._get_target_address(reader, writer)
            if not target:
                return
            
            target_host, target_port = target
            logger.info(f"🌐 {client_addr} → {target_host}:{target_port}")
            
            # Connect to target
            try:
                target_reader, target_writer = await asyncio.wait_for(
                    asyncio.open_connection(target_host, target_port), timeout=10.0
                )
            except Exception as e:
                logger.error(f"Connection failed: {e}")
                await self._send_reply(writer, 0x05)  # Connection refused
                return
            
            # Send success reply
            await self._send_reply(writer, 0x00)
            
            # Relay data with obfuscation
            await self._relay_obfuscated(
                reader, writer, target_reader, target_writer
            )
            
            target_writer.close()
            
        except Exception as e:
            logger.error(f"Client error: {e}")
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except:
                pass
    
    async def _socks5_handshake(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> bool:
        """Perform SOCKS5 handshake."""
        header = await reader.read(2)
        if len(header) < 2:
            return False
        
        version, nmethods = header[0], header[1]
        
        if version != self.SOCKS_VERSION:
            return False
        
        methods = await reader.read(nmethods)
        
        if 0x00 in methods:
            writer.write(bytes([self.SOCKS_VERSION, 0x00]))
            await writer.drain()
            return True
        else:
            writer.write(bytes([self.SOCKS_VERSION, 0xFF]))
            await writer.drain()
            return False
    
    async def _get_target_address(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> Optional[Tuple[str, int]]:
        """Parse SOCKS5 connection request."""
        header = await reader.read(4)
        if len(header) < 4:
            return None
        
        version, cmd, _, atyp = header
        
        if version != self.SOCKS_VERSION:
            return None
        
        if cmd != 0x01:
            await self._send_reply(writer, 0x07)
            return None
        
        if atyp == 0x01:  # IPv4
            addr_data = await reader.read(4)
            target_host = socket.inet_ntoa(addr_data)
        elif atyp == 0x03:  # Domain
            length = (await reader.read(1))[0]
            target_host = (await reader.read(length)).decode()
        elif atyp == 0x04:  # IPv6
            addr_data = await reader.read(16)
            target_host = socket.inet_ntop(socket.AF_INET6, addr_data)
        else:
            await self._send_reply(writer, 0x08)
            return None
        
        port_data = await reader.read(2)
        target_port = struct.unpack("!H", port_data)[0]
        
        return target_host, target_port
    
    async def _send_reply(self, writer: asyncio.StreamWriter, status: int):
        """Send SOCKS5 reply."""
        reply = bytes([
            self.SOCKS_VERSION, status, 0x00, 0x01,
            0, 0, 0, 0,  # Bind address
            0, 0,  # Bind port
        ])
        writer.write(reply)
        await writer.drain()
    
    async def _relay_obfuscated(
        self,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        target_reader: asyncio.StreamReader,
        target_writer: asyncio.StreamWriter,
    ):
        """Relay data with obfuscation applied."""
        
        async def forward_upstream():
            """Client -> Target (with obfuscation)."""
            try:
                while self._running:
                    data = await client_reader.read(8192)
                    if not data:
                        break
                    
                    # Apply obfuscation
                    obfuscated = self.obfuscator.obfuscate(data)
                    
                    target_writer.write(obfuscated)
                    await target_writer.drain()
                    
                    self.bytes_sent += len(data)
                    
            except (ConnectionResetError, BrokenPipeError):
                pass
            except Exception as e:
                logger.debug(f"Upstream error: {e}")
        
        async def forward_downstream():
            """Target -> Client (with deobfuscation)."""
            try:
                while self._running:
                    data = await target_reader.read(8192)
                    if not data:
                        break
                    
                    # Remove obfuscation
                    deobfuscated = self.obfuscator.deobfuscate(data)
                    
                    client_writer.write(deobfuscated)
                    await client_writer.drain()
                    
                    self.bytes_recv += len(deobfuscated)
                    
            except (ConnectionResetError, BrokenPipeError):
                pass
            except Exception as e:
                logger.debug(f"Downstream error: {e}")
        
        await asyncio.gather(
            forward_upstream(),
            forward_downstream(),
            return_exceptions=True,
        )
    
    def get_stats(self) -> dict:
        """Get server statistics."""
        return {
            "connections": self.connections,
            "bytes_sent": self.bytes_sent,
            "bytes_recv": self.bytes_recv,
            "obfuscation": self.obfuscator.get_current_parameters(),
        }


async def main():
    parser = argparse.ArgumentParser(
        description="x0tta6bl4 Obfuscated SOCKS5 Proxy"
    )
    parser.add_argument("--host", default="0.0.0.0", help="Listen host")
    parser.add_argument("--port", type=int, default=1080, help="Listen port")
    parser.add_argument(
        "--method",
        choices=["none", "faketls", "shadowsocks", "domain_fronting", "stegomesh", "hybrid"],
        default="faketls",
        help="Obfuscation method"
    )
    parser.add_argument(
        "--rotation",
        type=int,
        default=300,
        help="Parameter rotation interval (seconds)"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    server = ObfuscatedSOCKS5Server(
        host=args.host,
        port=args.port,
        obfuscation_method=args.method,
        rotation_interval=args.rotation,
    )
    
    try:
        await server.start()
    except KeyboardInterrupt:
        logger.info("\n🛑 Shutting down...")
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())