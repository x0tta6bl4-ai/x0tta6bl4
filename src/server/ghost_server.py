import sys
import os
sys.path.append("/mnt/projects")
sys.path.append("/mnt/projects/src")

import fcntl
import struct
import socket
import asyncio
import logging

# Manual import of GhostTransport to avoid any src issues
from src.network.transport.ghost_proto import GhostTransport

logger = logging.getLogger("ghost-server-l3")

TUNSETIFF = 0x400454ca
IFF_TUN = 0x0001
IFF_NO_PI = 0x1000

class GhostL3Server:
    def __init__(self, host='0.0.0.0', port=8444, master_key=b"default_key"):
        self.host = host
        self.port = port
        self.transport = GhostTransport(master_key)
        self.tun_fd = None
        self.client_addr = None

    def setup_tun(self):
        """Creates TUN interface and enables NAT on the server."""
        try:
            self.tun_fd = os.open('/dev/net/tun', os.O_RDWR)
            ifr = struct.pack('16sH', b'x0t-srv0', IFF_TUN | IFF_NO_PI)
            fcntl.ioctl(self.tun_fd, TUNSETIFF, ifr)
            os.system("ip addr add 10.8.0.1/24 dev x0t-srv0")
            os.system("ip link set dev x0t-srv0 up")
            os.system("echo 1 > /proc/sys/net/ipv4/ip_forward")
            os.system("iptables -t nat -A POSTROUTING -s 10.8.0.0/24 -o eth0 -j MASQUERADE")
            logger.info("✅ Server L3 TUN configured.")
        except Exception as e:
            logger.error(f"Failed to setup server TUN: {e}")

    async def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self.host, self.port))
        sock.setblocking(False)
        loop = asyncio.get_event_loop()

        async def tun_to_client():
            while True:
                try:
                    packet = await loop.run_in_executor(None, os.read, self.tun_fd, 4096)
                    if self.client_addr:
                        wrapped = self.transport.wrap_packet(packet)
                        sock.sendto(wrapped, self.client_addr)
                except: break

        asyncio.create_task(tun_to_client())

        while True:
            data, addr = await loop.sock_recvfrom(sock, 4096)
            self.client_addr = addr
            unwrapped = self.transport.unwrap_packet(data)
            if unwrapped:
                os.write(self.tun_fd, unwrapped)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import hashlib
    key = hashlib.sha256(b"mock_pqc_secured_token_12345").digest()
    srv = GhostL3Server(master_key=key)
    srv.setup_tun()
    asyncio.run(srv.run())
