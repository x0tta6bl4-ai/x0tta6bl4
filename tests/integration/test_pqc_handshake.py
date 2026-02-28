
import asyncio
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
async def test_pqc_handshake_and_ghost_flow():
    """
    Интеграционный тест: проверка динамического PQC рукопожатия
    и последующей передачи зашифрованных данных.
    """
    # Настройка узлов БЕЗ предустановленных ключей
    alice_config = MeshConfig(
        node_id="alice", 
        port=7001, 
        transport_type="ghost"
    )
    bob_config = MeshConfig(
        node_id="bob", 
        port=7002, 
        transport_type="ghost"
    )
    
    alice = CompleteMeshNode(alice_config)
    bob = CompleteMeshNode(bob_config)
    
    received_messages = []
    
    @bob.on_message
    async def handle_alice_msg(source, payload):
        received_messages.append(payload)
        print(f"Bob received securely: {payload.decode()}")

    await alice.start()
    await bob.start()
    
    # Имитируем обнаружение
    alice._peer_addresses["bob"] = ("127.0.0.1", 7002)
    bob._peer_addresses["alice"] = ("127.0.0.1", 7001)
    
    # 1. Первая попытка отправить сообщение должна запустить Handshake
    test_msg = b"PQC Handshake is the future"
    await alice.send_message("bob", test_msg)
    
    # Даем время на Handshake + повторную отправку
    # (send_message в текущей реализации делает повтор через 0.4с при поиске роута)
    await asyncio.sleep(1.5)
    
    try:
        # Проверяем, что ключи установились
        assert "bob" in alice._session_keys, "Alice failed to establish session key"
        assert "alice" in bob._session_keys, "Bob failed to establish session key"
        
        # Проверяем доставку сообщения
        assert len(received_messages) == 1
        assert received_messages[0] == test_msg
        print(f"✅ PQC HANDSHAKE SUCCESS: Session key len = {len(alice._session_keys['bob'])} bytes")
    finally:
        await alice.stop()
        await bob.stop()

if __name__ == "__main__":
    asyncio.run(test_pqc_handshake_and_ghost_flow())
