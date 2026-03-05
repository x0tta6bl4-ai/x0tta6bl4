import os
import time
import struct
import socket
import pytest
import logging
from src.network.ebpf.pqc_xdp_loader import PQCXDPLoader
from src.security.pqc.kem import PQCKeyExchange
from src.security.pqc.dsa import PQCDigitalSignature

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Структура заголовка mesh_pqc_header (из xdp_pqc_verify.c)
# struct mesh_pqc_header {
#     __u8  session_id[16];   
#     __u32 packet_seq;       
#     __u8  mac[8];           
#     __u16 payload_len;      
#     __u8  payload[];        
# };
PQC_HDR_FORMAT = "!16sI8sH"
PQC_HDR_SIZE = struct.calcsize(PQC_HDR_FORMAT)

def create_pqc_packet(session_id, seq, mac, payload):
    header = struct.pack(PQC_HDR_FORMAT, session_id, seq, mac, len(payload))
    return header + payload

def is_root():
    return os.getuid() == 0

@pytest.mark.skipif(not is_root(), reason="Требуются привилегии root для работы с eBPF")
def test_ebpf_pqc_fastpath_performance():
    """
    Бенчмарк производительности eBPF Fast-Path для PQC MaaS.
    """
    interface = "lo"
    try:
        loader = PQCXDPLoader(interface=interface)
    except Exception as e:
        pytest.skip(f"eBPF не поддерживается в данной среде: {e}")

    # 1. Симуляция PQC Handshake (как в реальной MaaS сессии)
    PQCKeyExchange(algorithm="Kyber768")
    PQCDigitalSignature(algorithm="Dilithium3")
    
    session_id = os.urandom(16)
    mac_key = os.urandom(16) # Упрощенно: ключ получен из KEM
    
    # Регистрируем сессию в eBPF карте
    # Примечание: в реальной системе это делает PQCXDPLoader.sync_with_gateway()
    # Здесь мы имитируем это напрямую для теста
    session_info = {
        "mac_key": mac_key,
        "peer_id_hash": struct.unpack("Q", os.urandom(8))[0],
        "verified": 1,
        "timestamp": int(time.time()),
        "last_seq": 0,
        "window_bitmap": 0
    }
    loader.update_pqc_sessions({session_id: session_info})

    logger.info(f"🚀 Сессия {session_id.hex()} загружена в eBPF")

    # 2. Генерация трафика
    num_packets = 10000
    payload = b"X" * 100
    packets = []
    
    for i in range(num_packets):
        # В реальном тесте мы бы считали SipHash-2-4 здесь для каждого пакета,
        # но для замера latency eBPF достаточно корректных структур.
        packets.append(create_pqc_packet(session_id, i+1, b"\x00"*8, payload))

    # 3. Замер пропускной способности
    start_time = time.time()
    
    # Отправляем пакеты через RAW socket на порт 26970
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dest = ("127.0.0.1", 26970)
    
    for pkt in packets:
        sock.sendto(pkt, dest)
        
    end_time = time.time()
    duration = end_time - start_time
    pps = num_packets / duration

    logger.info(f"📊 Пропускная способность (через userspace sendto): {pps:.2f} pkts/sec")
    
    # 4. Проверка статистики eBPF
    stats = loader.get_pqc_stats()
    logger.info(f"📈 Статистика eBPF: {stats}")

    # Ожидаем, что большинство пакетов попали в eBPF и были обработаны
    # (даже если MAC не совпал, они должны быть учтены в STATS_TOTAL_PACKETS)
    assert stats.get("total_packets", 0) > 0

    loader.cleanup()
    logger.info("🏁 Бенчмарк завершен")

if __name__ == "__main__":
    import os
    test_ebpf_pqc_fastpath_performance()
