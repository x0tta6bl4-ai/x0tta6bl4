"""
x0tta6bl4 TUN-to-SOCKS5 Bridge
Bridges TUN interface traffic to SOCKS5 proxy for mesh routing.

This enables transparent traffic routing through x0tta6bl4 mesh network:
1. iptables marks and redirects traffic to TUN interface
2. This bridge reads packets from TUN
3. Routes packets through SOCKS5 proxy (which uses mesh network)
4. Returns responses back through TUN

Usage:
    python3 -m src.network.tun_socks_bridge --tun tun0 --socks-host 127.0.0.1 --socks-port 1080
"""

import argparse
import asyncio
import logging
import os
import signal
import socket
import struct
import sys
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from .tun_handler import IPPROTO_TCP, IPPROTO_UDP, IPPacketParser, TUNInterface

try:
    from src.anti_censorship.obfuscation import ObfuscationConfig, TrafficObfuscator
except Exception:  # pragma: no cover - optional dependency
    ObfuscationConfig = None
    TrafficObfuscator = None


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
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
    and relays data bidirectionally. Optional XOR/padding obfuscation can be
    enabled for proxy-side payload transfer.
    """

    def __init__(
        self,
        tun_name: str = "tun0",
        socks_host: str = "127.0.0.1",
        socks_port: int = 1080,
        mtu: int = 1500,
        obfuscation_key: Optional[str] = None,
    ):
        self.tun_name = tun_name
        self.socks_host = socks_host
        self.socks_port = socks_port
        self.mtu = mtu

        self.obfuscator = None
        if obfuscation_key:
            if ObfuscationConfig is None or TrafficObfuscator is None:
                logger.warning("Obfuscation requested but module is unavailable")
            else:
                config = ObfuscationConfig(xor_key=obfuscation_key, use_padding=True)
                self.obfuscator = TrafficObfuscator(config)
                logger.info("Traffic obfuscation enabled for TUN-SOCKS bridge")

        self.tun: Optional[TUNInterface] = None
        self.stats = BridgeStats()
        self.connections: Dict[Tuple[str, int, str, int], ConnectionInfo] = {}
        self.running = False

    async def start(self) -> bool:
        """
        Start the bridge.

        Returns:
            True if started successfully.
        """
        self.tun = TUNInterface(self.tun_name, self.mtu)

        if not await self.tun.create():
            logger.error("Failed to create TUN interface")
            return False

        if not await self.tun.set_address("10.0.0.1/32", "10.0.0.2"):
            logger.warning("Failed to set TUN address (may already exist)")

        self.running = True
        logger.info("TUN-SOCKS bridge started")
        logger.info("  TUN: %s", self.tun_name)
        logger.info("  SOCKS5: %s:%s", self.socks_host, self.socks_port)

        await asyncio.gather(
            self._read_packets(),
            self._cleanup_connections(),
            return_exceptions=True,
        )
        return True

    async def stop(self) -> None:
        """Stop the bridge and close resources."""
        self.running = False

        for conn in list(self.connections.values()):
            try:
                conn.writer.close()
                await conn.writer.wait_closed()
            except Exception:
                pass

        self.connections.clear()

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

                ip_info = IPPacketParser.parse(packet)
                if ip_info is None:
                    continue

                if ip_info["protocol"] == IPPROTO_TCP:
                    await self._handle_tcp(ip_info)
                elif ip_info["protocol"] == IPPROTO_UDP:
                    await self._handle_udp(ip_info)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug("Packet processing error: %s", exc)
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
        conn_key = (src_ip, src_port, dst_ip, dst_port)

        flags = tcp_info["flags"]
        if flags["syn"] and not flags["ack"]:
            await self._handle_tcp_syn(conn_key)
        elif flags["fin"]:
            await self._handle_tcp_fin(conn_key)
        elif flags["rst"]:
            await self._handle_tcp_rst(conn_key)
        elif conn_key in self.connections and tcp_info["payload"]:
            await self._handle_tcp_data(conn_key, tcp_info["payload"])

    async def _handle_tcp_syn(self, conn_key: Tuple[str, int, str, int]) -> None:
        """Handle TCP SYN (new connection)."""
        src_ip, src_port, dst_ip, dst_port = conn_key
        logger.debug("TCP SYN: %s:%s -> %s:%s", src_ip, src_port, dst_ip, dst_port)

        try:
            reader, writer = await asyncio.wait_for(
                self._socks5_connect(dst_ip, dst_port),
                timeout=10.0,
            )
        except asyncio.TimeoutError:
            logger.debug("TCP connection timeout: %s", conn_key)
            self.stats.errors += 1
            return
        except Exception as exc:
            logger.debug("TCP connection failed: %s", exc)
            self.stats.errors += 1
            return

        self.connections[conn_key] = ConnectionInfo(
            reader=reader,
            writer=writer,
            src_ip=src_ip,
            src_port=src_port,
            dst_ip=dst_ip,
            dst_port=dst_port,
        )
        self.stats.connections_created += 1
        self.stats.connections_active += 1
        asyncio.create_task(self._relay_response(conn_key))
        logger.debug("TCP connection established: %s", conn_key)

    async def _handle_tcp_data(self, conn_key: Tuple[str, int, str, int], data: bytes) -> None:
        """Handle TCP payload toward SOCKS endpoint."""
        conn = self.connections.get(conn_key)
        if conn is None:
            return

        try:
            outbound = self.obfuscator.obfuscate(data) if self.obfuscator else data
            conn.writer.write(outbound)
            await conn.writer.drain()
            conn.bytes_sent += len(outbound)
            self.stats.bytes_sent += len(outbound)
        except Exception as exc:
            logger.debug("TCP data send error: %s", exc)
            await self._close_connection(conn_key)

    async def _handle_tcp_fin(self, conn_key: Tuple[str, int, str, int]) -> None:
        """Handle TCP FIN."""
        logger.debug("TCP FIN: %s", conn_key)
        await self._close_connection(conn_key)

    async def _handle_tcp_rst(self, conn_key: Tuple[str, int, str, int]) -> None:
        """Handle TCP RST."""
        logger.debug("TCP RST: %s", conn_key)
        await self._close_connection(conn_key)

    async def _handle_udp(self, ip_info: dict) -> None:
        """Handle UDP packet (currently telemetry-only)."""
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
        logger.debug("UDP: %s:%s -> %s:%s", src_ip, src_port, dst_ip, dst_port)

    async def _socks5_connect(self, host: str, port: int) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """Connect to target through SOCKS5 proxy."""
        reader, writer = await asyncio.open_connection(self.socks_host, self.socks_port)

        # Greeting: VER=5, NMETHODS=1, METHOD=NOAUTH
        writer.write(b"\x05\x01\x00")
        await writer.drain()

        response = await reader.read(2)
        if len(response) < 2 or response[0] != 5 or response[1] != 0:
            writer.close()
            raise RuntimeError("SOCKS5 handshake failed")

        # CONNECT request
        try:
            socket.inet_aton(host)
            request = b"\x05\x01\x00\x01" + socket.inet_aton(host)  # IPv4
        except OSError:
            host_bytes = host.encode()
            request = b"\x05\x01\x00\x03" + bytes([len(host_bytes)]) + host_bytes  # domain
        request += struct.pack("!H", port)
        writer.write(request)
        await writer.drain()

        response = await reader.read(10)
        if len(response) < 2 or response[1] != 0:
            writer.close()
            code = response[1] if len(response) > 1 else "timeout"
            raise RuntimeError(f"SOCKS5 connect failed: {code}")

        return reader, writer

    async def _relay_response(self, conn_key: Tuple[str, int, str, int]) -> None:
        """Relay response from SOCKS5 back to TUN side."""
        conn = self.connections.get(conn_key)
        if conn is None:
            return

        try:
            while self.running and conn_key in self.connections:
                data = await conn.reader.read(self.mtu)
                if not data:
                    break
                inbound = self.obfuscator.deobfuscate(data) if self.obfuscator else data
                conn.bytes_recv += len(inbound)
                self.stats.bytes_recv += len(inbound)
                # In full implementation: craft TCP/IP packet and write to TUN.
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.debug("Response relay error: %s", exc)
        finally:
            await self._close_connection(conn_key)

    async def _close_connection(self, conn_key: Tuple[str, int, str, int]) -> None:
        """Close active connection by key."""
        conn = self.connections.pop(conn_key, None)
        if not conn:
            return
        try:
            conn.writer.close()
            await conn.writer.wait_closed()
        except Exception:
            pass
        self.stats.connections_active -= 1

    async def _cleanup_connections(self) -> None:
        """Periodically close stale connections."""
        while self.running:
            await asyncio.sleep(30)
            stale_keys = []
            for key, conn in self.connections.items():
                if conn.bytes_sent == 0 and conn.bytes_recv == 0:
                    stale_keys.append(key)
            for key in stale_keys:
                await self._close_connection(key)

    def get_stats(self) -> dict:
        """Return current bridge statistics."""
        return {
            "packets_read": self.stats.packets_read,
            "packets_written": self.stats.packets_written,
            "bytes_sent": self.stats.bytes_sent,
            "bytes_recv": self.stats.bytes_recv,
            "connections_created": self.stats.connections_created,
            "connections_active": self.stats.connections_active,
            "errors": self.stats.errors,
        }


async def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="x0tta6bl4 TUN-SOCKS Bridge")
    parser.add_argument("--tun", default="tun0", help="TUN interface name (default: tun0)")
    parser.add_argument("--socks-host", default="127.0.0.1", help="SOCKS5 host (default: 127.0.0.1)")
    parser.add_argument("--socks-port", type=int, default=1080, help="SOCKS5 port (default: 1080)")
    parser.add_argument("--mtu", type=int, default=1500, help="TUN MTU (default: 1500)")
    parser.add_argument(
        "--obfuscation-key",
        default=None,
        help="Optional XOR key for payload obfuscation toward proxy transport",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    if os.geteuid() != 0:
        print("ERROR: This script requires root privileges for TUN interface creation.")
        print("Run with: sudo python3 -m src.network.tun_socks_bridge")
        sys.exit(1)

    bridge = TUNSOCKSBridge(
        tun_name=args.tun,
        socks_host=args.socks_host,
        socks_port=args.socks_port,
        mtu=args.mtu,
        obfuscation_key=args.obfuscation_key,
    )

    loop = asyncio.get_event_loop()

    def _signal_handler() -> None:
        logger.info("Received shutdown signal")
        asyncio.create_task(bridge.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    try:
        await bridge.start()
    except KeyboardInterrupt:
        pass
    finally:
        await bridge.stop()


if __name__ == "__main__":
    asyncio.run(main())
