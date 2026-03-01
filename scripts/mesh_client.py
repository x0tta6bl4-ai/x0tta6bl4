#!/usr/bin/env python3
"""
x0tta6bl4 Mesh Client — Ghost transport + SOCKS5 VPN

Запуск: MESH_SHARED_KEY=<hex> python3 scripts/mesh_client.py

Поднимает два сервиса:
1. CompleteMeshNode (Ghost/ChaCha20-Poly1305) → VPS:10809 UDP
   — демонстрирует работу нашего mesh протокола
2. SOCKS5 proxy на 127.0.0.1:1081
   — туннелирует трафик через VPS exit node (показывает IP 89.125.1.107)

Тест: curl -x socks5://127.0.0.1:1081 https://api.ipify.org
"""
import asyncio
import ipaddress
import logging
import os
import sys
from pathlib import Path

# Resolve project root dynamically instead of hardcoded absolute path.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

from src.network.mesh_node_complete import CompleteMeshNode, MeshConfig

def _load_shared_key() -> bytes:
    raw = os.getenv("MESH_SHARED_KEY", "").strip()
    if not raw:
        raise SystemExit("MESH_SHARED_KEY is required (hex string, e.g. 32-byte key)")
    try:
        key = bytes.fromhex(raw)
    except ValueError as exc:
        raise SystemExit(f"MESH_SHARED_KEY must be valid hex: {exc}") from exc
    if len(key) < 16:
        raise SystemExit("MESH_SHARED_KEY is too short; expected >= 16 bytes")
    return key


SERVER_IP = os.getenv("MESH_SERVER_IP", "89.125.1.107")
SERVER_GHOST_PORT = int(os.getenv("MESH_SERVER_GHOST_PORT", "10809"))
SERVER_SOCKS_PORT = int(os.getenv("MESH_SERVER_SOCKS_PORT", "10810"))
SERVER_ID = os.getenv("MESH_SERVER_ID", "x0tta6bl4-server")
CLIENT_NODE_ID = os.getenv("MESH_CLIENT_NODE_ID", "x0tta6bl4-client")
CLIENT_GHOST_PORT = int(os.getenv("MESH_CLIENT_GHOST_PORT", "6100"))
SHARED_KEY = _load_shared_key()
LOCAL_SOCKS_PORT = int(os.getenv("SOCKS_PORT", "1081"))
CONNECT_TIMEOUT_SEC = float(os.getenv("SOCKS_CONNECT_TIMEOUT_SEC", "10"))
READ_TIMEOUT_SEC = float(os.getenv("SOCKS_READ_TIMEOUT_SEC", "10"))
# Physical interface IP to bypass TUN routing when connecting to VPS.
# Set to "" or omit to use default routing.
LOCAL_BIND_IP = os.getenv("LOCAL_BIND_IP", "192.168.0.101")


# ─── SOCKS5 relay through VPS exit node ───────────────────────────────────────

async def relay(reader, writer):
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


async def _read_socks5_connect_request(reader: asyncio.StreamReader) -> bytes:
    req = await _read_exactly(reader, 4)
    ver, cmd, rsv, atyp = req
    if ver != 5:
        raise ValueError("Invalid SOCKS version")
    if cmd != 1:
        raise ValueError("Only CONNECT is supported")
    if rsv != 0:
        raise ValueError("Invalid reserved byte")

    if atyp == 1:
        addr_port = await _read_exactly(reader, 6)
    elif atyp == 3:
        dlen = (await _read_exactly(reader, 1))[0]
        if dlen == 0:
            raise ValueError("Invalid domain length")
        addr_port = bytes([dlen]) + await _read_exactly(reader, dlen + 2)
    elif atyp == 4:
        addr_port = await _read_exactly(reader, 18)
    else:
        raise ValueError("Unsupported address type")
    return req + addr_port


def _is_private_target(connect_req: bytes) -> bool:
    atyp = connect_req[3]
    if atyp == 1:
        host = str(ipaddress.ip_address(connect_req[4:8]))
    elif atyp == 4:
        host = str(ipaddress.ip_address(connect_req[4:20]))
    elif atyp == 3:
        dlen = connect_req[4]
        host = connect_req[5 : 5 + dlen].decode(errors="ignore").strip().lower()
        # Domain names are not checked for private ranges at this layer.
        return host in {"localhost", "localhost.localdomain"}
    else:
        return False

    ip_obj = ipaddress.ip_address(host)
    return (
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_unspecified
        or ip_obj.is_reserved
    )


async def _read_socks5_reply(reader: asyncio.StreamReader) -> tuple[bytes, int]:
    head = await _read_exactly(reader, 4)
    ver, rep, rsv, atyp = head
    if ver != 5 or rsv != 0:
        raise ValueError("Invalid SOCKS5 reply")

    if atyp == 1:
        tail = await _read_exactly(reader, 6)
    elif atyp == 3:
        dlen = (await _read_exactly(reader, 1))[0]
        tail = bytes([dlen]) + await _read_exactly(reader, dlen + 2)
    elif atyp == 4:
        tail = await _read_exactly(reader, 18)
    else:
        raise ValueError("Unsupported SOCKS5 reply address type")
    return head + tail, rep


async def handle_client(reader, writer):
    """Accept SOCKS5 from browser → forward to VPS exit node."""
    peer = writer.get_extra_info('peername')
    try:
        # 1. Read client SOCKS5 greeting
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
        writer.write(b"\x05\x00")
        await writer.drain()

        # 2. Read CONNECT request (variable length)
        connect_req = await _read_socks5_connect_request(reader)
        if _is_private_target(connect_req):
            log.warning("Blocked private/loopback SOCKS target from %s", peer)
            writer.write(b"\x05\x02\x00\x01\x00\x00\x00\x00\x00\x00")
            await writer.drain()
            writer.close()
            return

        # 3. Connect to VPS exit node (bind to physical interface to bypass TUN)
        try:
            local_addr = (LOCAL_BIND_IP, 0) if LOCAL_BIND_IP else None
            vps_r, vps_w = await asyncio.wait_for(
                asyncio.open_connection(SERVER_IP, SERVER_SOCKS_PORT,
                                        local_addr=local_addr),
                timeout=CONNECT_TIMEOUT_SEC
            )
        except Exception as e:
            log.error(f"VPS exit node unreachable: {e}")
            writer.write(b"\x05\x05\x00\x01\x00\x00\x00\x00\x00\x00")
            await writer.drain()
            writer.close()
            return

        # 4. Do SOCKS5 handshake with VPS exit node
        vps_w.write(b"\x05\x01\x00")  # no-auth
        await vps_w.drain()
        vps_resp = await _read_exactly(vps_r, 2)
        if len(vps_resp) < 2 or vps_resp[1] != 0:
            log.error(f"VPS SOCKS5 auth failed: {vps_resp!r}")
            writer.write(b"\x05\x05\x00\x01\x00\x00\x00\x00\x00\x00")
            await writer.drain()
            writer.close()
            vps_w.close()
            return

        # 5. Forward CONNECT request to VPS
        vps_w.write(connect_req)
        await vps_w.drain()

        # 6. Get VPS response and forward to client
        vps_connect_resp, rep = await _read_socks5_reply(vps_r)
        writer.write(vps_connect_resp)
        await writer.drain()

        if rep != 0:
            log.warning(f"VPS connect failed for request")
            writer.close()
            vps_w.close()
            return

        # 7. Relay data bidirectionally
        await asyncio.gather(
            relay(reader, vps_w),
            relay(vps_r, writer),
        )

    except Exception as e:
        log.debug(f"Client handler error: {e}")
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def start_local_socks5():
    """Start local SOCKS5 that routes through VPS exit node."""
    server = await asyncio.start_server(
        handle_client, '127.0.0.1', LOCAL_SOCKS_PORT
    )
    log.info(f"Local SOCKS5 VPN proxy: 127.0.0.1:{LOCAL_SOCKS_PORT}")
    log.info(f"  → Routing through VPS exit node {SERVER_IP}:{SERVER_SOCKS_PORT}")
    return server


# ─── Ghost transport mesh node ─────────────────────────────────────────────────

async def start_ghost_node():
    """Start CompleteMeshNode with Ghost transport to VPS."""
    node = CompleteMeshNode(MeshConfig(
        node_id=CLIENT_NODE_ID,
        port=CLIENT_GHOST_PORT,
        transport_type="ghost",
        pqc_master_key=SHARED_KEY,
        enable_pqc=False,
        enable_multicast=False,
        enable_discovery=False,
        bootstrap_nodes=[(SERVER_IP, SERVER_GHOST_PORT)],
    ))

    @node.on_message
    async def on_server_msg(source, payload):
        log.info(f"[Ghost] received from {source}: {payload[:64]!r}")

    await node.start()
    node._peer_addresses[SERVER_ID] = (SERVER_IP, SERVER_GHOST_PORT)
    log.info(f"Ghost mesh node started → {SERVER_ID} at {SERVER_IP}:{SERVER_GHOST_PORT}")

    # Send test message
    await asyncio.sleep(1)
    success = await node.send_message(SERVER_ID, b"x0tta6bl4 mesh online - Ghost/ChaCha20")
    log.info(f"[Ghost] test message sent: {success}")

    return node


# ─── Main ──────────────────────────────────────────────────────────────────────

async def main():
    log.info("=" * 60)
    log.info("x0tta6bl4 Mesh Client starting...")
    log.info("Ghost key length: %d bytes", len(SHARED_KEY))
    log.info("=" * 60)

    # Start Ghost node
    ghost_node = await start_ghost_node()

    # Start local SOCKS5 VPN
    socks_server = await start_local_socks5()

    log.info("")
    log.info("✅ Ready!")
    log.info(f"   VPN:  curl -x socks5://127.0.0.1:{LOCAL_SOCKS_PORT} https://api.ipify.org")
    log.info(f"   Expected IP: {SERVER_IP}")

    try:
        async with socks_server:
            await socks_server.serve_forever()
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        await ghost_node.stop()
        log.info("Mesh client stopped")


if __name__ == "__main__":
    asyncio.run(main())
