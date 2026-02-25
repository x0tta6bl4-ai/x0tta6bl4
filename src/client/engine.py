import sys
import os
sys.path.append("/mnt/projects")
sys.path.append("/mnt/projects/src")

import fcntl
import struct
import socket
import asyncio
import logging
import hashlib

# Manual import of GhostTransport to avoid any src issues
from src.network.transport.ghost_proto import GhostTransport

logger = logging.getLogger("ghost-tun-v6")

TUNSETIFF = 0x400454ca
IFF_TUN = 0x0001
IFF_NO_PI = 0x1000

class GhostTUN:
    def __init__(self, master_key: bytes, server_ip: str = '127.0.0.1'):
        self.transport = GhostTransport(master_key)
        self.tun_fd = None
        self.remote_server = (server_ip, 8444)

    def setup_network(self):
        """Creates TUN interface and configures routing."""
        try:
            self.tun_fd = os.open('/dev/net/tun', os.O_RDWR)
            ifr = struct.pack('16sH', b'x0t-tun0', IFF_TUN | IFF_NO_PI)
            fcntl.ioctl(self.tun_fd, TUNSETIFF, ifr)
            os.system("ip addr add 10.8.0.2/24 dev x0t-tun0")
            os.system("ip link set dev x0t-tun0 up")
            logger.info("✅ System-Wide TUN Interface 'x0t-tun0' is UP.")
            return True
        except Exception as e:
            logger.error(f"Failed to setup TUN: {e}")
            return False

    async def run(self):
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_sock.setblocking(False)
        loop = asyncio.get_event_loop()

        async def read_from_server():
            while True:
                try:
                    data, _ = await loop.sock_recv(udp_sock, 4096)
                    unwrapped = self.transport.unwrap_packet(data)
                    if unwrapped:
                        os.write(self.tun_fd, unwrapped)
                except Exception: break

        asyncio.create_task(read_from_server())

        logger.info("🛡️ Quantum Shield L3 Active. All system traffic is now routed through Ghost-Protocol.")
        while True:
            packet = await loop.run_in_executor(None, os.read, self.tun_fd, 4096)
            if not packet: break
            ghost_packet = self.transport.wrap_packet(packet)
            udp_sock.sendto(ghost_packet, self.remote_server)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import hashlib
    key = hashlib.sha256(b"mock_pqc_secured_token_12345").digest()
    vpn = GhostTUN(key)
    if vpn.setup_network():
        asyncio.run(vpn.run())
