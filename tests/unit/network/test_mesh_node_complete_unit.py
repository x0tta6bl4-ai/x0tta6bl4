import os

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")


def test_mesh_node_complete_import() -> None:
    import src.network.mesh_node_complete as mod

    assert mod is not None


import asyncio
from typing import List, Tuple

import pytest

from src.network.mesh_node_complete import CompleteMeshNode, MeshConfig
from src.network.transport.ghost_proto import GhostTransport


class _DummyTransport:
    def __init__(self) -> None:
        self.sent: List[Tuple[bytes, tuple]] = []

    async def send_to(self, data: bytes, address: tuple) -> bool:
        self.sent.append((data, address))
        return True


@pytest.mark.asyncio
async def test_ghost_router_send_queues_until_handshake() -> None:
    node = CompleteMeshNode(
        MeshConfig(
            node_id="node-a",
            transport_type="ghost",
            enable_discovery=False,
        )
    )
    node._transport = _DummyTransport()
    node._peer_addresses["node-b"] = ("127.0.0.1", 5002)

    async def _fake_handshake(peer_id: str) -> None:
        await asyncio.sleep(0)

    node._initiate_pqc_handshake = _fake_handshake  # type: ignore[method-assign]

    result = await node._router_send(b"plain-payload", "node-b")

    assert result is True
    assert node._pending_packets["node-b"] == [b"plain-payload"]
    assert node._transport.sent == []


@pytest.mark.asyncio
async def test_flush_pending_packets_wraps_and_sends() -> None:
    node = CompleteMeshNode(
        MeshConfig(
            node_id="node-a",
            transport_type="ghost",
            enable_discovery=False,
        )
    )
    node._transport = _DummyTransport()
    node._peer_addresses["node-b"] = ("127.0.0.1", 5002)
    node._pending_packets["node-b"] = [b"first", b"second"]
    node._ghost_transports["node-b"] = GhostTransport(b"k" * 32)

    await node._flush_pending_packets("node-b")

    assert "node-b" not in node._pending_packets
    assert len(node._transport.sent) == 2
    sent_payloads = [payload for payload, _ in node._transport.sent]
    assert sent_payloads[0] != b"first"
    assert sent_payloads[1] != b"second"
