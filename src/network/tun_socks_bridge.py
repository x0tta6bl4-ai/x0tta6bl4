"""
x0tta6bl4 TUN-to-SOCKS5 Bridge
Bridges TUN interface traffic to SOCKS5 proxy for mesh routing.

This enables transparent traffic routing through x0tta6bl4 mesh network:
1. iptables marks and redirects traffic to TUN interface
2. This bridge reads packets from TUN
3. Routes packets through SOCKS5 proxy (which uses mesh network)
4. Returns responses back through TUN

Usage:
    # Start bridge
    python3 -m src.network.tun_socks_bridge --tun tun0 --socks 127.0.0.1:1080
"""

import argparse
import asyncio
import logging
import os
import signal
import socket
import struct
import sys
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from .tun_handler import TUNInterface, IPPacketParser, IPPROTO_TCP, IPPROTO_UDP

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class ConnectionInfo:
    """Active connection information."""
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    src_ip: str
    src_port: int
    dst_ip: str
    dst_port: int
    bytes_sent: int = 0
    bytes_recv: int = 0


@dataclass
class BridgeStats:
    """Bridge statistics."""
    packets_read: int = 0
    packets_written: int = 0
    bytes_sent: int = 0
    bytes_recv: int = 0
    connections_created: int = 0
    connections_active: int = 0
    errors: int = 0


class TUNSOCKSBridge:
    """
    Bridge between TUN interface and SOCKS5 proxy.
    
    Reads IP packets from TUN interface, establishes SOCKS5 connections,
    and relays data bidirectionally.
    """
    
    def __init__(
        self,
        tun_name: str = "tun0",
        socks_host: str = "127.0.0.1",
        socks_port: int = 1080,
        mtu: int = 1500
    ):
        """
        Initialize TUN-SOCKS bridge.
        
        Args:
            tun_name: TUN interface name
            socks_host: SOCKS5 proxy host
            socks_port: SOCKS5 proxy port
            mtu: Maximum transmission unit
        """
        self.tun_name = tun_name
        self.socks_host = socks_host
        self.socks_port = socks_port
        self.mtu = mtu
        
        self.tun: Optional[TUNInterface] = None
        self.stats = BridgeStats()
        self.connections: Dict[Tuple[str, int, str, int], ConnectionInfo] = {}
        self.tcp_states: Dict[Tuple[str, int], dict] = {}  # TCP state tracking
        self.running = False
        
    async def start(self) -> bool:
        """
        Start the bridge.
        
        Returns:
            True if started successfully
        """
        # Create TUN interface
        self.tun = TUNInterface(self.tun_name, self.mtu)
        
        if not await self.tun.create():
            logger.error("Failed to create TUN interface")
            return False
        
        # Set IP address
        if not await self.tun.set_address("10.0.0.1/32", "10.0.0.2"):
            logger.warning("Failed to set TUN address (may already exist)")
        
        self.running = True
        logger.info(f"TUN-SOCKS bridge started")
        logger.info(f"  TUN: {self.tun_name}")
        logger.info(f"  SOCKS5: {self.socks_host}:{self.socks_port}")
        
        # Start processing tasks
        await asyncio.gather(
            self._read_packets(),
            self._cleanup_connections(),
            return_exceptions=True
        )
        
        return True
    
    async def stop(self) -> None:
        """Stop the bridge."""
        self.running = False
        
        # Close all connections
        for conn in self.connections.values():
            try:
                conn.writer.close()
                await conn.writer.wait_closed()
            except Exception:
                pass
        
        self.connections.clear()
        
        # Close TUN
        if self.tun:
            self.tun.close()
        
        logger.info("Bridge stopped")
    
    async def _read_packets(self) -> None:
        """Read and process packets from TUN interface."""
        while self.running:
            try:
                packet = await self.tun.read_packet()
                if packet is None:
                    await asyncio.sleep(0.001)
                    continue
                
                self.stats.packets_read += 1
                
                # Parse IP packet
                ip_info = IPPacketParser.parse(packet)
                if ip_info is None:
                    continue
                
                # Route based on protocol
                if ip_info["protocol"] == IPPROTO_TCP:
                    await self._handle_tcp(ip_info)
                elif ip_info["protocol"] == IPPROTO_UDP:
                    await self._handle_udp(ip_info)
                # Ignore ICMP for now
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Packet processing error: {e}")
                self.stats.errors += 1
    
    async def _handle_tcp(self, ip_info: dict) -> None:
        """Handle TCP packet."""
        payload = ip_info["payload"]
        if len(payload) < 20:
            return
        
        tcp_info = IPPacketParser.get_tcp_info(payload)
        if tcp_info is None:
            return
        
        src_ip = ip_info["src_ip"]
        dst_ip = ip_info["dst_ip"]
        src_port = tcp_info["src_port"]
        dst_port = tcp_info["dst_port"]
        
        # Get connection key
        conn_key = (src_ip, src_port, dst_ip, dst_port)
        
        # Handle TCP flags
        flags = tcp_info["flags"]
        
        # SYN - new connection attempt
        if flags["syn"] and not flags["ack"]:
            await self._handle_tcp_syn(conn_key, ip_info, tcp_info)
        
        # FIN - connection close
        elif flags["fin"]:
            await self._handle_tcp_fin(conn_key)
        
        # RST - connection reset
        elif flags["rst"]:
            await self._handle_tcp_rst(conn_key)
        
        # Data packet
        elif conn_key in self.connections and tcp_info["payload"]:
            await self._handle_tcp_data(conn_key, tcp_info["payload"])
    
    async def _handle_tcp_syn(
        self,
        conn_key: Tuple[str, int, str, int],
        ip_info: dict,
        tcp_info: dict
    ) -> None:
        """Handle TCP SYN (new connection)."""
        src_ip, src_port, dst_ip, dst_port = conn_key
        
        logger.debug(f"TCP SYN: {src_ip}:{src_port} -> {dst_ip}:{dst_port}")
        
        try:
            # Connect through SOCKS5
            reader, writer = await asyncio.wait_for(
                self._socks5_connect(dst_ip, dst_port),
                timeout=10.0
            )
            
            # Store connection
            self.connections[conn_key] = ConnectionInfo(
                reader=reader,
                writer=writer,
                src_ip=src_ip,
                src_port=src_port,
                dst_ip=dst_ip,
                dst_port=dst_port
            )
            
            self.stats.connections_created += 1
            self.stats.connections_active += 1
            
            # Start relay task for response
            asyncio.create_task(
                self._relay_response(conn_key)
            )
            
            logger.debug(f"TCP connection established: {conn_key}")
            
        except asyncio.TimeoutError:
            logger.debug(f"TCP connection timeout: {conn_key}")
            self.stats.errors += 1
        except Exception as e:
            logger.debug(f"TCP connection failed: {e}")
            self.stats.errors += 1
    
    async def _handle_tcp_data(
        self,
        conn_key: Tuple[str, int, str, int],
        data: bytes
    ) -> None:
        """Handle TCP data packet."""
        conn = self.connections.get(conn_key)
        if conn is None:
            return
        
        try:
            conn.writer.write(data)
            await conn.writer.drain()
            conn.bytes_sent += len(data)
            self.stats.bytes_sent += len(data)
        except Exception as e:
            logger.debug(f"TCP data send error: {e}")
            await self._close_connection(conn_key)
    
    async def _handle_tcp_fin(self, conn_key: Tuple[str, int, str, int]) -> None:
        """Handle TCP FIN (connection close)."""
        logger.debug(f"TCP FIN: {conn_key}")
        await self._close_connection(conn_key)
    
    async def _handle_tcp_rst(self, conn_key: Tuple[str, int, str, int]) -> None:
        """Handle TCP RST (connection reset)."""
        logger.debug(f"TCP RST: {conn_key}")
        await self._close_connection(conn_key)
    
    async def _handle_udp(self, ip_info: dict) -> None:
        """Handle UDP packet."""
        payload = ip_info["payload"]
        if len(payload) < 8:
            return
        
        udp_info = IPPacketParser.get_udp_info(payload)
        if udp_info is None:
            return
        
        src_ip = ip_info["src_ip"]
        dst_ip = ip_info["dst_ip"]
        src_port = udp_info["src_port"]
        dst_port = udp_info["dst_port"]
        
        logger.debug(f"UDP: {src_ip}:{src_port} -> {dst_ip}:{dst_port}")
        
        # UDP is connectionless, so we use UDP associate
        # For simplicity, we'll just log it
        # Full implementation would use SOCKS5 UDP ASSOCIATE
    
    async def _socks5_connect(
        self,
        host: str,
        port: int
    ) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """
        Connect to target through SOCKS5 proxy.
        
        Args:
            host: Target host
            port: Target port
            
        Returns:
            Tuple of (reader, writer) for the connection
        """
        # Connect to SOCKS5 proxy
        reader, writer = await asyncio.open_connection(
            self.socks_host, self.socks_port
        )
        
        # SOCKS5 handshake
        # 1. Greeting
        writer.write(b"\x05\x01\x00")  # Version 5, 1 method, no auth
        await writer.drain()
        
        response = await reader.read(2)
        if len(response) < 2 or response[0] != 5 or response[1] != 0:
            writer.close()
            raise RuntimeError("SOCKS5 handshake failed")
        
        # 2. Connect request
        # Try domain name first, then IP
        try:
            # Check if it's an IP address
            socket.inet_aton(host)
            # It's an IP - use ATYP_IPV4
            request = b"\x05\x01\x00\x01"  # CONNECT, IPv4
            request += socket.inet_aton(host)
        except socket.error:
            # It's a domain - use ATYP_DOMAIN
            request = b"\x05\x01\x00\x03"  # CONNECT, domain
            request += bytes([len(host)]) + host.encode()
        
        request += struct.pack("!H", port)
        
        writer.write(request)
        await writer.drain()
        
        # 3. Read response
        response = await reader.read(10)
        if len(response) < 2 or response[1] != 0:
            writer.close()
            raise RuntimeError(f"SOCKS5 connect failed: {response[1] if len(response) > 1 else 'timeout'}")
        
        return reader, writer
    
    async def _relay_response(self, conn_key: Tuple[str, int, str, int]) -> None:
        """Relay response from SOCKS5 back to TUN."""
        conn = self.connections.get(conn_key)
        if conn is None:
            return
        
        try:
            while self.running and conn_key in self.connections:
                data = await conn.reader.read(self.mtu)
                if not data:
                    break
                
                conn.bytes_recv += len(data)
                self.stats.bytes_recv += len(data)
                
                # Build IP packet for response
                # Note: This is simplified - real implementation needs proper TCP state
                # For now, we just log the data
                logger.debug(f"Response data: {len(data)} bytes")
                
                # In a full implementation, we would:
                # 1. Build proper IP/TCP headers
                # 2. Calculate checksums
                # 3. Write to TUN interface
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug(f"Response relay error: {e}")
        finally:
            await self._close_connection(conn_key)
    
    async def _close_connection(self, conn_key: Tuple[str, int, str, int]) -> None:
        """Close a connection."""
        conn = self.connections.pop(conn_key, None)
        if conn:
            try:
                conn.writer.close()
                await conn.writer.wait_closed()
            except Exception:
                pass
            self.stats.connections_active -= 1
    
    async def _cleanup_connections(self) -> None:
        """Periodically cleanup stale connections."""
        while self.running:
            await asyncio.sleep(30)
            
            # Close connections with no activity for 60 seconds
            # (simplified - real implementation would track last activity)
            stale = []
            for key, conn in self.connections.items():
                if conn.bytes_sent == 0 and conn.bytes_recv == 0:
                    stale.append(key)
            
            for key in stale:
                await self._close_connection(key)
    
    def get_stats(self) -> dict:
        """Get bridge statistics."""
        return {
            "packets_read": self.stats.packets_read,
            "packets_written": self.stats.packets_written,
            "bytes_sent": self.stats.bytes_sent,
            "bytes_recv": self.stats.bytes_recv,
            "connections_created": self.stats.connections_created,
            "connections_active": self.stats.connections_active,
            "errors": self.stats.errors,
        }


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="x0tta6bl4 TUN-SOCKS Bridge"
    )
    parser.add_argument(
        "--tun", default="tun0",
        help="TUN interface name (default: tun0)"
    )
    parser.add_argument(
        "--socks-host", default="127.0.0.1",
        help="SOCKS5 proxy host (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--socks-port", type=int, default=1080,
        help="SOCKS5 proxy port (default: 1080)"
    )
    parser.add_argument(
        "--mtu", type=int, default=1500,
        help="MTU for TUN interface (default: 1500)"
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Enable debug logging"
    )
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Check root permissions
    if os.geteuid() != 0:
        print("ERROR: This script requires root privileges for TUN interface creation.")
        print("Run with: sudo python3 -m src.network.tun_socks_bridge")
        sys.exit(1)
    
    bridge = TUNSOCKSBridge(
        tun_name=args.tun,
        socks_host=args.socks_host,
        socks_port=args.socks_port,
        mtu=args.mtu
    )
    
    # Setup signal handlers
    loop = asyncio.get_event_loop()
    
    def signal_handler():
        logger.info("Received shutdown signal")
        asyncio.create_task(bridge.stop())
    
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)
    
    try:
        await bridge.start()
    except KeyboardInterrupt:
        pass
    finally:
        await bridge.stop()


if __name__ == "__main__":
    asyncio.run(main())