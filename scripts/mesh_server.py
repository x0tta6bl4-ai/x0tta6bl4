#!/usr/bin/env python3
"""
x0tta6bl4 Mesh Server Node
Запуск: MESH_SHARED_KEY=<hex> python3 mesh_server.py
"""
import asyncio
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


SHARED_KEY = _load_shared_key()
PORT = int(os.getenv("MESH_PORT", "10809"))
NODE_ID = os.getenv("MESH_NODE_ID", "x0tta6bl4-server")


async def main():
    node = CompleteMeshNode(MeshConfig(
        node_id=NODE_ID,
        port=PORT,
        transport_type="ghost",
        pqc_master_key=SHARED_KEY,
        enable_pqc=False,
        enable_multicast=False,
        enable_discovery=False,
    ))

    @node.on_message
    async def on_msg(source, payload):
        log.info(f"[relay] {source}: {len(payload)} bytes — {payload[:64]!r}")

    await node.start()
    log.info(f"Mesh server '{NODE_ID}' listening on UDP:{PORT}")
    log.info(f"Key: {SHARED_KEY.hex()[:16]}...{SHARED_KEY.hex()[-8:]}")

    try:
        while True:
            await asyncio.sleep(10)
    except asyncio.CancelledError:
        pass
    finally:
        await node.stop()
        log.info("Mesh server stopped")


if __name__ == "__main__":
    asyncio.run(main())
