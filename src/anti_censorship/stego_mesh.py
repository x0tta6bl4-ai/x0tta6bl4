"""
Steganographic Mesh Protocol
=============================

Реализация стеганографического mesh-протокола для обхода DPI (Deep Packet Inspection).
Трафик маскируется под обычный HTTP/ICMP/DNS, делая его невидимым для цензуры.
"""

import hashlib
import logging
import secrets
import struct
from typing import List, Optional, Tuple

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

logger = logging.getLogger(__name__)


class StegoMeshProtocol:
    """
    Стеганографический mesh-протокол.

    Кодирует реальный трафик x0tta6bl4 в пакеты, которые выглядят как
    обычный HTTP/ICMP/DNS трафик для обхода DPI.
    """

    # Магические маркеры для идентификации stego-пакетов
    STEGO_MARKER_HTTP = b"X-Stego-Mesh: 1"
    STEGO_MARKER_ICMP = b"X0TTA6BL4_STEGO"
    STEGO_MARKER_DNS = b"x0tta6bl4.stego"

    def __init__(self, master_key: bytes):
        """
        Инициализация протокола.

        Args:
            master_key: Мастер-ключ для шифрования (32 байта)
        """
        if len(master_key) < 32:
            raise ValueError("Master key must be at least 32 bytes")

        self.master_key = master_key[:32]
        self.backend = default_backend()

        logger.info("StegoMeshProtocol initialized")

    def _derive_session_key(self, payload_prefix: bytes) -> Tuple[bytes, bytes]:
        """
        Генерация session key из master key.

        Args:
            payload_prefix: Первые 32 байта payload для уникальности

        Returns:
            Tuple[session_key, nonce]
        """
        # Используем SHAKE-128 для генерации ключа и nonce детерминированно
        seed = self.master_key + payload_prefix[:32]
        shake = hashlib.shake_128(seed)

        # Генерируем session key (32 байта)
        session_key = shake.digest(32)

        # Генерируем nonce детерминированно (16 байт)
        nonce = shake.digest(16)

        return session_key, nonce

    def encode_packet(self, real_payload: bytes, protocol_mimic: str = "http") -> bytes:
        """
        Кодирование реального пакета в стеганографический.

        Args:
            real_payload: Реальные данные для передачи
            protocol_mimic: Протокол для маскировки ("http", "icmp", "dns")

        Returns:
            Стеганографический пакет, выглядящий как обычный трафик
        """
        try:
            # 1. Подготавливаем payload prefix для деривации ключа
            # Используем первые 32 байта payload (или дополняем до 32 байт)
            payload_prefix = (
                real_payload[:32]
                if len(real_payload) >= 32
                else real_payload + b"\x00" * (32 - len(real_payload))
            )

            # 2. Генерируем session key
            session_key, nonce = self._derive_session_key(payload_prefix)

            # 3. Шифруем payload с помощью ChaCha20
            cipher = Cipher(
                algorithms.ChaCha20(session_key, nonce), mode=None, backend=self.backend
            )
            encryptor = cipher.encryptor()
            encrypted = encryptor.update(real_payload) + encryptor.finalize()

            # 3.5. Lower entropy by using Base64 encoding for the encrypted part
            # This makes it look more like text/standard data and less like random bits
            import base64
            encoded_payload = base64.b64encode(nonce + payload_prefix + encrypted)

            # 4. Создаём стеганографический заголовок в зависимости от протокола
            if protocol_mimic == "http":
                header = self._create_http_header(len(encoded_payload))
            elif protocol_mimic == "icmp":
                header = self._create_icmp_header()
            elif protocol_mimic == "dns":
                header = self._create_dns_header(len(encoded_payload))
            else:
                header = self._create_http_header(len(encoded_payload))

            # 5. Встраиваем закодированные данные
            noise = secrets.token_bytes(secrets.randbelow(10) + 2)
            stego_packet = header + encoded_payload + noise

            logger.debug(
                f"Encoded packet: {len(real_payload)} bytes -> "
                f"{len(stego_packet)} bytes (mimic={protocol_mimic})"
            )

            return stego_packet

        except Exception as e:
            logger.error(f"Error encoding packet: {e}", exc_info=True)
            raise

    def _create_http_header(self, content_length: int) -> bytes:
        """Создание HTTP-заголовка для маскировки"""
        header = b"GET /index.html HTTP/1.1\r\n"
        header += b"Host: cloudflare.com\r\n"
        header += b"User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36\r\n"
        header += f"Content-Length: {content_length}\r\n".encode()
        header += b"Connection: keep-alive\r\n"
        header += self.STEGO_MARKER_HTTP + b"\r\n"
        header += b"\r\n"
        return header

    def _create_icmp_header(self) -> bytes:
        """Создание ICMP-заголовка для маскировки (RFC 792)"""
        # ICMP Echo Request: Type(8), Code(0), Checksum(0), ID, Sequence
        import time
        header = struct.pack("!BBHHH", 8, 0, 0, secrets.randbelow(65535), 1)
        # Add standard ICMP data: timestamp (8 bytes) + dummy data
        ts = struct.pack("!Q", int(time.time() * 1000))
        header += ts + b"abcdefghijklmnopqrstuvw" # Standard payload size padding
        header += self.STEGO_MARKER_ICMP
        return header

    def _create_dns_header(self, data_length: int) -> bytes:
        """Создание DNS-заголовка для маскировки"""
        # DNS Query header (ID, flags, questions, answers, etc.)
        header = struct.pack(
            "!HHHHHH",
            secrets.randbelow(65535) + 1,  # Transaction ID
            0x0100,  # Flags: standard query
            1,  # Questions
            0,
            0,
            0,
        )
        # Query name: stego.x0tta6bl4.mesh
        header += b"\x05stego\x08x0tta6bl4\x04mesh\x00"
        header += struct.pack("!HH", 1, 1)  # Type A, Class IN
        return header

    def decode_packet(self, stego_packet: bytes) -> Optional[bytes]:
        """
        Декодирование стеганографического пакета.
        """
        import base64
        try:
            encoded_data = None
            if self.STEGO_MARKER_HTTP in stego_packet:
                parts = stego_packet.split(b"\r\n\r\n")
                if len(parts) > 1:
                    encoded_data = parts[1]
            elif self.STEGO_MARKER_ICMP in stego_packet:
                marker_pos = stego_packet.find(self.STEGO_MARKER_ICMP)
                encoded_data = stego_packet[marker_pos + len(self.STEGO_MARKER_ICMP):]
            elif self.STEGO_MARKER_DNS in stego_packet:
                marker_pos = stego_packet.find(self.STEGO_MARKER_DNS)
                encoded_data = stego_packet[marker_pos + len(self.STEGO_MARKER_DNS):]
            
            if not encoded_data:
                # Try fallback: just find anything that looks like base64 after headers
                return None

            # Handle noise and base64 decoding
            # In production, we would use a more robust way to find the end of base64
            # For now, we try to strip noise from the end until base64 decodes
            for i in range(len(encoded_data), 10, -1):
                try:
                    candidate = encoded_data[:i]
                    decoded = base64.b64decode(candidate)
                    if len(decoded) < 48: continue
                    
                    nonce = decoded[:16]
                    payload_prefix = decoded[16:48]
                    ciphertext = decoded[48:]
                    
                    session_key, _ = self._derive_session_key(payload_prefix)
                    cipher = Cipher(algorithms.ChaCha20(session_key, nonce), mode=None, backend=self.backend)
                    decryptor = cipher.decryptor()
                    return (decryptor.update(ciphertext) + decryptor.finalize()).rstrip(b"\x00")
                except:
                    continue
            return None
        except Exception as e:
            logger.debug(f"Decode error: {e}")
            return None

    def test_dpi_evasion(self, payload: bytes, protocol: str = "http") -> bool:
        """
        Тест обхода DPI.

        Args:
            payload: Тестовые данные
            protocol: Протокол для маскировки

        Returns:
            True если пакет выглядит как обычный трафик
        """
        stego_packet = self.encode_packet(payload, protocol)

        # Проверяем, что пакет выглядит как обычный трафик
        if protocol == "http":
            # Должен выглядеть как HTTP
            return b"HTTP/1.1" in stego_packet and b"GET" in stego_packet
        elif protocol == "icmp":
            # Должен выглядеть как ICMP
            return stego_packet[:2] == b"\x08\x00"
        elif protocol == "dns":
            # Должен выглядеть как DNS
            return len(stego_packet) > 12 and stego_packet[2:4] == b"\x01\x00"

        return False
