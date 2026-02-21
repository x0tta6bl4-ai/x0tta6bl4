"""
x0tta6bl4 TUN Interface Handler
Handles TUN/TAP interface creation and packet I/O for mesh gateway.

Usage:
    from src.network.tun_handler import TUNInterface
    
    tun = TUNInterface("tun0")
    await tun.create()
    packet = await tun.read_packet()
"""

import os
import fcntl
import struct
import asyncio
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# TUN/TAP constants
TUNSETIFF = 0x400454ca
TUNSETPERSIST = 0x400454cb
TUNSETOWNER = 0x400454cc
TUNSETGROUP = 0x400454cd

IFF_TUN = 0x0001
IFF_TAP = 0x0002
IFF_NO_PI = 0x1000
IFF_ONE_QUEUE = 0x2000
IFF_VNET_HDR = 0x4000
IFF_TUN_EXCL = 0x8000
IFF_MULTI_QUEUE = 0x0100


class TUNInterface:
    """
    TUN interface handler for x0tta6bl4 mesh gateway.
    
    Provides async I/O for reading/writing packets to a TUN interface.
    Used for transparent traffic routing through mesh network.
    """
    
    def __init__(
        self, 
        name: str = "tun0", 
        mtu: int = 1500,
        persist: bool = False
    ):
        """
        Initialize TUN interface handler.
        
        Args:
            name: Interface name (e.g., tun0, tun1)
            mtu: Maximum transmission unit
            persist: Make interface persistent
        """
        self.name = name
        self.mtu = mtu
        self.persist = persist
        self.fd: Optional[int] = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._running = False
        
    @property
    def is_up(self) -> bool:
        """Check if interface is up."""
        return self.fd is not None and self._running
    
    async def create(self) -> bool:
        """
        Create and configure TUN interface.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Open /dev/net/tun
            tun_path = "/dev/net/tun"
            if not os.path.exists(tun_path):
                # Try to create /dev/net directory
                os.makedirs("/dev/net", exist_ok=True)
                # Create device node (requires root)
                os.mknod(tun_path, 0o666 | 0o20000, (10, 200))  # char device 10,200
            
            self.fd = os.open(tun_path, os.O_RDWR | os.O_NONBLOCK)
            
            # Create interface using ioctl
            # Pack interface name and flags
            ifr = struct.pack(
                f"16sH", 
                self.name.encode("utf-8")[:15], 
                IFF_TUN | IFF_NO_PI
            )
            
            fcntl.ioctl(self.fd, TUNSETIFF, ifr)
            
            # Make persistent if requested
            if self.persist:
                fcntl.ioctl(self.fd, TUNSETPERSIST, 1)
            
            # Configure interface using system commands
            await self._configure_interface()
            
            # Create asyncio stream reader
            loop = asyncio.get_event_loop()
            self._reader = asyncio.StreamReader()
            
            # Create protocol and transport
            protocol = asyncio.StreamReaderProtocol(self._reader)
            transport, _ = await loop.create_connection(
                lambda: protocol,
                sock=self._create_socket()
            )
            
            self._writer = asyncio.StreamWriter(
                transport, protocol, self._reader, loop
            )
            
            self._running = True
            logger.info(f"TUN interface {self.name} created successfully")
            return True
            
        except PermissionError:
            logger.error("Permission denied. Run as root or with CAP_NET_ADMIN.")
            return False
        except Exception as e:
            logger.error(f"Failed to create TUN interface: {e}")
            if self.fd is not None:
                os.close(self.fd)
                self.fd = None
            return False
    
    def _create_socket(self) -> int:
        """Create socket from file descriptor."""
        import socket
        sock = socket.socket(fileno=self.fd, family=socket.AF_UNSPEC)
        sock.setblocking(False)
        return sock.detach()
    
    async def _configure_interface(self) -> None:
        """Configure TUN interface using system commands."""
        import subprocess
        
        # Set MTU
        subprocess.run(
            ["ip", "link", "set", "dev", self.name, "mtu", str(self.mtu)],
            check=True, capture_output=True
        )
        
        # Bring up interface
        subprocess.run(
            ["ip", "link", "set", "dev", self.name, "up"],
            check=True, capture_output=True
        )
        
        logger.debug(f"Configured {self.name} with MTU {self.mtu}")
    
    async def set_address(self, local_ip: str, remote_ip: str = None) -> bool:
        """
        Set IP address on TUN interface.
        
        Args:
            local_ip: Local IP address (e.g., "10.0.0.1/32")
            remote_ip: Remote/peer IP address for point-to-point
            
        Returns:
            True if successful
        """
        import subprocess
        
        try:
            if remote_ip:
                # Point-to-point configuration
                subprocess.run(
                    ["ip", "addr", "add", local_ip, "peer", remote_ip, "dev", self.name],
                    check=True, capture_output=True
                )
            else:
                # Simple address assignment
                subprocess.run(
                    ["ip", "addr", "add", local_ip, "dev", self.name],
                    check=True, capture_output=True
                )
            
            logger.info(f"Set address {local_ip} on {self.name}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to set address: {e.stderr.decode()}")
            return False
    
    async def read_packet(self) -> Optional[bytes]:
        """
        Read a packet from TUN interface.
        
        Returns:
            Raw IP packet data, or None if no data available
        """
        if not self._reader or not self._running:
            return None
        
        try:
            # Read raw packet (no packet info header due to IFF_NO_PI)
            data = await self._reader.read(self.mtu)
            return data if data else None
        except asyncio.CancelledError:
            return None
        except Exception as e:
            logger.debug(f"Read error: {e}")
            return None
    
    async def write_packet(self, packet: bytes) -> bool:
        """
        Write a packet to TUN interface.
        
        Args:
            packet: Raw IP packet data
            
        Returns:
            True if successful
        """
        if not self._writer or not self._running:
            return False
        
        try:
            self._writer.write(packet)
            await self._writer.drain()
            return True
        except Exception as e:
            logger.debug(f"Write error: {e}")
            return False
    
    def read_packet_sync(self) -> Optional[bytes]:
        """
        Synchronously read a packet (for non-async contexts).
        
        Returns:
            Raw IP packet data, or None if no data available
        """
        if self.fd is None:
            return None
        
        try:
            import socket
            data = os.read(self.fd, self.mtu)
            return data if data else None
        except BlockingIOError:
            return None
        except Exception as e:
            logger.debug(f"Sync read error: {e}")
            return None
    
    def write_packet_sync(self, packet: bytes) -> bool:
        """
        Synchronously write a packet (for non-async contexts).
        
        Args:
            packet: Raw IP packet data
            
        Returns:
            True if successful
        """
        if self.fd is None:
            return False
        
        try:
            os.write(self.fd, packet)
            return True
        except Exception as e:
            logger.debug(f"Sync write error: {e}")
            return False
    
    def close(self) -> None:
        """Close TUN interface."""
        self._running = False
        
        if self._writer:
            try:
                self._writer.close()
            except Exception:
                pass
            self._writer = None
        
        if self.fd is not None:
            try:
                os.close(self.fd)
            except Exception:
                pass
            self.fd = None
        
        logger.info(f"TUN interface {self.name} closed")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


class IPPacketParser:
    """Parser for IP packets read from TUN interface."""
    
    @staticmethod
    def parse(packet: bytes) -> Optional[dict]:
        """
        Parse IP packet header.
        
        Args:
            packet: Raw IP packet bytes
            
        Returns:
            Dictionary with packet info, or None if invalid
        """
        if len(packet) < 20:
            return None
        
        try:
            version = packet[0] >> 4
            header_len = (packet[0] & 0x0F) * 4
            total_len = (packet[2] << 8) | packet[3]
            protocol = packet[9]
            ttl = packet[8]
            
            import socket
            
            src_ip = socket.inet_ntoa(packet[12:16])
            dst_ip = socket.inet_ntoa(packet[16:20])
            
            return {
                "version": version,
                "header_len": header_len,
                "total_len": total_len,
                "protocol": protocol,
                "ttl": ttl,
                "src_ip": src_ip,
                "dst_ip": dst_ip,
                "payload": packet[header_len:],
                "raw": packet
            }
        except Exception:
            return None
    
    @staticmethod
    def get_tcp_info(payload: bytes) -> Optional[dict]:
        """Parse TCP header from IP payload."""
        if len(payload) < 20:
            return None
        
        try:
            src_port = (payload[0] << 8) | payload[1]
            dst_port = (payload[2] << 8) | payload[3]
            seq_num = int.from_bytes(payload[4:8], "big")
            ack_num = int.from_bytes(payload[8:12], "big")
            flags = payload[13]
            
            return {
                "src_port": src_port,
                "dst_port": dst_port,
                "seq_num": seq_num,
                "ack_num": ack_num,
                "flags": {
                    "fin": bool(flags & 0x01),
                    "syn": bool(flags & 0x02),
                    "rst": bool(flags & 0x04),
                    "psh": bool(flags & 0x08),
                    "ack": bool(flags & 0x10),
                    "urg": bool(flags & 0x20),
                },
                "payload": payload[20:],
            }
        except Exception:
            return None
    
    @staticmethod
    def get_udp_info(payload: bytes) -> Optional[dict]:
        """Parse UDP header from IP payload."""
        if len(payload) < 8:
            return None
        
        try:
            src_port = (payload[0] << 8) | payload[1]
            dst_port = (payload[2] << 8) | payload[3]
            length = (payload[4] << 8) | payload[5]
            
            return {
                "src_port": src_port,
                "dst_port": dst_port,
                "length": length,
                "payload": payload[8:],
            }
        except Exception:
            return None


# Protocol constants
IPPROTO_TCP = 6
IPPROTO_UDP = 17
IPPROTO_ICMP = 1
IPPROTO_ICMPV6 = 58


async def test_tun_interface():
    """Test TUN interface creation."""
    logging.basicConfig(level=logging.DEBUG)
    
    tun = TUNInterface("tun0")
    
    try:
        if await tun.create():
            print(f"TUN interface {tun.name} created")
            
            # Set address
            await tun.set_address("10.0.0.1/32", "10.0.0.2")
            
            # Read packets
            print("Reading packets (Ctrl+C to stop)...")
            while True:
                packet = await tun.read_packet()
                if packet:
                    parsed = IPPacketParser.parse(packet)
                    if parsed:
                        print(f"Packet: {parsed['src_ip']} -> {parsed['dst_ip']} (proto: {parsed['protocol']})")
                await asyncio.sleep(0.01)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        tun.close()


if __name__ == "__main__":
    asyncio.run(test_tun_interface())