
import asyncio
import os
import socket

import pytest
from src.network.mesh_node_complete import CompleteMeshNode, MeshConfig


def _udp_socket_available() -> bool:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.close()
        return True
    except PermissionError:
        return False


pytestmark = [
    pytest.mark.skipif(
        not _udp_socket_available(),
        reason="UDP sockets are not permitted in this environment",
    ),
    pytest.mark.usefixtures("real_oqs"),
]


@pytest.mark.asyncio
async def test_ghost_communication_real_flow():
    """
    Интеграционный тест: проверка передачи сообщения между двумя узлами
    с использованием Ghost Transport (WebRTC Mimicry).
    """
    master_key = os.urandom(32)
    
    # 1. Настройка узлов с включенным Ghost
    alice_config = MeshConfig(
        node_id="alice", 
        port=6001, 
        transport_type="ghost", 
        pqc_master_key=master_key
    )
    bob_config = MeshConfig(
        node_id="bob", 
        port=6002, 
        transport_type="ghost", 
        pqc_master_key=master_key
    )
    
    alice = CompleteMeshNode(alice_config)
    bob = CompleteMeshNode(bob_config)
    
    received_messages = []
    
    @bob.on_message
    async def handle_alice_msg(source, payload):
        received_messages.append(payload)
        print(f"Bob received: {payload.decode()}")

    await alice.start()
    await bob.start()
    
    # Имитируем ручное обнаружение (так как multicast может быть выключен в sandbox)
    alice._peer_addresses["bob"] = ("127.0.0.1", 6002)
    bob._peer_addresses["alice"] = ("127.0.0.1", 6001)
    
    # 2. Отправка сообщения (пройдет через Ghost Wrap -> UDP -> Ghost Unwrap)
    test_msg = b"Ghost is alive and PQC-ready"
    success = await alice.send_message("bob", test_msg)
    
    # Даем время на доставку
    await asyncio.sleep(0.5)
    
    try:
        assert success is True
        assert len(received_messages) == 1
        assert received_messages[0] == test_msg
        print("✅ INTEGRATION SUCCESS: Ghost transport is working in the core node!")
    finally:
        await alice.stop()
        await bob.stop()

if __name__ == "__main__":
    asyncio.run(test_ghost_communication_real_flow())
