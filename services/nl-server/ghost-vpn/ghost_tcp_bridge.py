#!/usr/bin/env python3
"""
Ghost VPN TCP-to-UDP Bridge (VPS side)
======================================
Accepts TCP connections on port 4434 and relays each
length-prefixed frame as a UDP datagram to the local
Ghost VPN server on UDP :4433.

Responses from the server are relayed back over TCP.

Deploy on VPS alongside ghost-vpn.service:
    python3 scripts/ghost_tcp_bridge.py &

Frame format:  [2-byte big-endian length][payload]
"""

import asyncio
import logging
import os
import struct

logger = logging.getLogger("GhostTCP-Bridge")

LISTEN_PORT = int(os.getenv("GHOST_TCP_PORT", "4434"))
UDP_TARGET = ("127.0.0.1", int(os.getenv("GHOST_UDP_PORT", "4433")))


class UDPRelay(asyncio.DatagramProtocol):
    """Relay UDP responses back to the TCP writer."""

    def __init__(self, tcp_writer: asyncio.StreamWriter):
        self.transport = None
        self._writer = tcp_writer

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data: bytes, addr):
        if self._writer.is_closing():
            return
        frame = struct.pack("!H", len(data)) + data
        self._writer.write(frame)


async def handle_client(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
):
    peer = writer.get_extra_info("peername")
    logger.info("TCP client connected: %s", peer)

    loop = asyncio.get_running_loop()
    relay = UDPRelay(writer)
    udp_transport, _ = await loop.create_datagram_endpoint(
        lambda: relay, remote_addr=UDP_TARGET
    )

    try:
        while True:
            header = await reader.readexactly(2)
            length = struct.unpack("!H", header)[0]
            if length == 0 or length > 65535:
                break
            data = await reader.readexactly(length)
            udp_transport.sendto(data)
    except (asyncio.IncompleteReadError, ConnectionError, OSError):
        pass
    finally:
        logger.info("TCP client disconnected: %s", peer)
        udp_transport.close()
        writer.close()
        await writer.wait_closed()


async def main():
    server = await asyncio.start_server(
        handle_client, "0.0.0.0", LISTEN_PORT
    )
    logger.info("Ghost TCP Bridge listening on :%d → UDP %s", LISTEN_PORT, UDP_TARGET)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
    )
    asyncio.run(main())
