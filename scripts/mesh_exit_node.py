#!/usr/bin/env python3
"""
x0tta6bl4 Mesh Exit Node (minimal SOCKS5 exit)
Запуск: python3 mesh_exit_node.py
Слушает TCP:10810 — принимает SOCKS5 от entry node, проксирует в интернет.
"""
import asyncio
import ipaddress
import logging
import os
import socket
import struct

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger("exit-node")

HOST = os.getenv("EXIT_BIND_HOST", "0.0.0.0")
PORT = int(os.getenv("EXIT_BIND_PORT", "10810"))
CONNECT_TIMEOUT_SEC = float(os.getenv("EXIT_CONNECT_TIMEOUT_SEC", "10"))
READ_TIMEOUT_SEC = float(os.getenv("EXIT_READ_TIMEOUT_SEC", "10"))
ALLOW_PRIVATE_TARGETS = os.getenv("EXIT_ALLOW_PRIVATE_TARGETS", "0").lower() in {
    "1",
    "true",
    "yes",
}


async def relay(reader, writer, label=""):
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except Exception:
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def _read_exactly(reader: asyncio.StreamReader, n: int) -> bytes:
    return await asyncio.wait_for(reader.readexactly(n), timeout=READ_TIMEOUT_SEC)


def _is_blocked_target(host: str) -> bool:
    if ALLOW_PRIVATE_TARGETS:
        return False
    host_lower = host.strip().lower()
    if host_lower in {"localhost", "localhost.localdomain"}:
        return True
    try:
        ip_obj = ipaddress.ip_address(host_lower)
    except ValueError:
        return False
    return (
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_unspecified
        or ip_obj.is_reserved
    )


async def _read_socks5_request(reader: asyncio.StreamReader) -> tuple[str, int]:
    req = await _read_exactly(reader, 4)
    ver, cmd, rsv, atyp = req
    if ver != 5:
        raise ValueError("Invalid SOCKS version")
    if cmd != 1:
        raise ValueError("Only CONNECT is supported")
    if rsv != 0:
        raise ValueError("Invalid reserved byte")

    if atyp == 1:
        raw = await _read_exactly(reader, 6)
        host = socket.inet_ntoa(raw[:4])
        port = struct.unpack("!H", raw[4:6])[0]
    elif atyp == 3:
        dlen = (await _read_exactly(reader, 1))[0]
        if dlen == 0:
            raise ValueError("Invalid domain length")
        host = (await _read_exactly(reader, dlen)).decode(errors="ignore")
        port = struct.unpack("!H", await _read_exactly(reader, 2))[0]
    elif atyp == 4:
        raw = await _read_exactly(reader, 18)
        host = str(ipaddress.IPv6Address(raw[:16]))
        port = struct.unpack("!H", raw[16:18])[0]
    else:
        raise ValueError("Unsupported address type")

    return host, port


async def handle_socks5(reader, writer):
    peer = writer.get_extra_info('peername')
    try:
        # SOCKS5 auth negotiation
        hdr = await _read_exactly(reader, 2)
        if len(hdr) < 2 or hdr[0] != 5:
            writer.close()
            return
        nmethods = hdr[1]
        methods = await _read_exactly(reader, nmethods)
        if 0x00 not in methods:
            writer.write(b"\x05\xff")
            await writer.drain()
            writer.close()
            return
        # No auth
        writer.write(b"\x05\x00")
        await writer.drain()

        # Read CONNECT request
        try:
            host, port = await _read_socks5_request(reader)
        except ValueError:
            writer.write(b"\x05\x08\x00\x01\x00\x00\x00\x00\x00\x00")
            await writer.drain()
            writer.close()
            return

        if _is_blocked_target(host):
            log.warning("[%s] blocked private target %s:%s", peer[0], host, port)
            writer.write(b"\x05\x02\x00\x01\x00\x00\x00\x00\x00\x00")
            await writer.drain()
            writer.close()
            return

        log.info(f"[{peer[0]}] → {host}:{port}")

        try:
            r_reader, r_writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=CONNECT_TIMEOUT_SEC,
            )
        except Exception as e:
            log.warning(f"Connect failed {host}:{port}: {e}")
            writer.write(b"\x05\x05\x00\x01\x00\x00\x00\x00\x00\x00")
            await writer.drain()
            writer.close()
            return

        # Success response
        writer.write(b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00")
        await writer.drain()

        # Bidirectional relay
        await asyncio.gather(
            relay(reader, r_writer, "up"),
            relay(r_reader, writer, "dn"),
        )

    except Exception as e:
        log.debug(f"SOCKS5 handler error: {e}")
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def main():
    server = await asyncio.start_server(handle_socks5, HOST, PORT)
    log.info(f"Exit node SOCKS5 listening on TCP {HOST}:{PORT}")
    if not ALLOW_PRIVATE_TARGETS:
        log.info("Private/loopback targets are blocked (set EXIT_ALLOW_PRIVATE_TARGETS=1 to override)")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
