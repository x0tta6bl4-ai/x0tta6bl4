#!/usr/bin/env python3
"""
Ghost Pulse VPN — Advanced x0tta6bl4 Transport
==============================================

Production-ready VPN with Ghost Pulse Transport.
Combines ChaCha20-Poly1305 AEAD with deterministic timing profiles.

Environment Variables:
    VPN_ENCRYPTION_KEY: 32-byte key (base64)
    VPN_SERVER: Server IP (for client mode)
    VPN_PORT: UDP port (default: 9999)
    PULSE_MODE: timing profile (corporate/whitelist, default: corporate)
    PULSE_SEED: deterministic seed (default: 20260521)
"""

import argparse
import asyncio
import base64
import fcntl
import logging
import os
import socket
import struct
import subprocess
import sys
from typing import Optional

# Import the new transport
try:
    from src.network.transport.ghost_pulse_transport import GhostPulseTransport
except ImportError:
    # Fallback for standalone deployment
    sys.path.append(os.getcwd())
    from src.network.transport.ghost_pulse_transport import GhostPulseTransport

logger = logging.getLogger("ghost-pulse-vpn")

# Constants
TUNSETIFF = 0x400454ca
IFF_TUN = 0x0001
IFF_NO_PI = 0x1000

def _run_command_safely(cmd: list) -> bool:
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {' '.join(cmd)} - {e.stderr.decode().strip()}")
        return False

def _get_config():
    key_b64 = os.getenv("VPN_ENCRYPTION_KEY")
    if not key_b64:
        raise ValueError("VPN_ENCRYPTION_KEY is required")
    key = base64.b64decode(key_b64)

    server_ip = os.getenv("VPN_SERVER", "127.0.0.1")
    port = int(os.getenv("VPN_PORT", "9999"))

    mode = os.getenv("PULSE_MODE", "corporate")
    seed_str = os.getenv("PULSE_SEED", "20260521")
    try:
        seed = int(seed_str)
    except ValueError:
        seed = abs(hash(seed_str))

    return key, server_ip, port, mode, seed

async def start_vpn(is_server: bool):
    try:
        key, server_ip, port, mode, seed = _get_config()
    except Exception as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)

    transport = GhostPulseTransport(key, mode=mode, pulse_seed=seed)

    tun_name = b'x0t-srv0' if is_server else b'x0t-tun0'
    tun_interface = tun_name.decode()

    try:
        # TUN Setup
        tun_fd = os.open('/dev/net/tun', os.O_RDWR)
        ifr = struct.pack('16sH', tun_name, IFF_TUN | IFF_NO_PI)
        fcntl.ioctl(tun_fd, TUNSETIFF, ifr)

        addr = "10.10.0.1" if is_server else "10.10.0.2"
        commands = [
            ["ip", "addr", "add", f"{addr}/24", "dev", tun_interface],
            ["ip", "link", "set", "dev", tun_interface, "up"],
        ]

        if is_server:
            commands.extend([
                ["sysctl", "-w", "net.ipv4.ip_forward=1"],
                ["iptables", "-t", "nat", "-A", "POSTROUTING",
                 "-s", "10.10.0.0/24", "-o", "eth0", "-j", "MASQUERADE"],
            ])

        for cmd in commands:
            _run_command_safely(cmd)

        # UDP Setup
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if is_server:
            sock.bind(('0.0.0.0', port))
        sock.setblocking(False)
        loop = asyncio.get_event_loop()
        client_addr = None

        async def tun_to_udp():
            nonlocal client_addr
            while True:
                try:
                    packet = await loop.run_in_executor(None, os.read, tun_fd, 4096)
                    # Apply Pulse timing before sending
                    await transport.wait_for_pulse()

                    wrapped = transport.wrap_packet(packet)
                    target = (server_ip, port) if not is_server else client_addr
                    if target:
                        sock.sendto(wrapped, target)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.debug(f"tun_to_udp error: {e}")

        async def udp_to_tun():
            nonlocal client_addr
            while True:
                try:
                    data, addr = await loop.sock_recvfrom(sock, 4096)
                    if is_server:
                        client_addr = addr

                    unwrapped = transport.unwrap_packet(data)
                    if unwrapped:
                        os.write(tun_fd, unwrapped)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.debug(f"udp_to_tun error: {e}")

        logger.info(f"Ghost Pulse VPN {'Server' if is_server else 'Client'} ACTIVE")
        logger.info(f"Mode: {mode}, Port: {port}")

        await asyncio.gather(tun_to_udp(), udp_to_tun())

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["server", "client"], default="client", nargs="?")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    asyncio.run(start_vpn(is_server=(args.mode == "server")))
