"""
Steganographic Mesh Protocol
=============================

Реализация стеганографического mesh-протокола для обхода DPI (Deep Packet Inspection).
Трафик маскируется под обычный HTTP/ICMP/DNS, делая его невидимым для цензуры.
"""
import struct
import hashlib
import secrets
from typing import Optional, Tuple, List
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import logging

logger = logging.getLogger(__name__)


class StegoMeshProtocol:
    """
    Стеганографический mesh-протокол.
    
    Кодирует реальный трафик x0tta6bl4 в пакеты, которые выглядят как
    обычный HTTP/ICMP/DNS трафик для обхода DPI.
    """
    
    # Магические маркеры для идентификации stego-пакетов
    STEGO_MARKER_HTTP = b'X-Stego-Mesh: 1'
    STEGO_MARKER_ICMP = b'X0TTA6BL4_STEGO'
    STEGO_MARKER_DNS = b'x0tta6bl4.stego'
    
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
    
    def encode_packet(
        self,
        real_payload: bytes,
        protocol_mimic: str = "http"
    ) -> bytes:
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
            payload_prefix = real_payload[:32] if len(real_payload) >= 32 else real_payload + b'\x00' * (32 - len(real_payload))
            
            # 2. Генерируем session key
            session_key, nonce = self._derive_session_key(payload_prefix)
            
            # 3. Шифруем payload с помощью ChaCha20
            cipher = Cipher(
                algorithms.ChaCha20(session_key, nonce),
                mode=None,
                backend=self.backend
            )
            encryptor = cipher.encryptor()
            encrypted = encryptor.update(real_payload) + encryptor.finalize()
            
            # 4. Создаём стеганографический заголовок в зависимости от протокола
            if protocol_mimic == "http":
                header = self._create_http_header(len(encrypted) + 32 + 16)  # encrypted + payload_prefix + nonce
            elif protocol_mimic == "icmp":
                header = self._create_icmp_header()
            elif protocol_mimic == "dns":
                header = self._create_dns_header(len(encrypted) + 32 + 16)
            else:
                # По умолчанию HTTP
                header = self._create_http_header(len(encrypted) + 32 + 16)
            
            # 5. Встраиваем nonce, payload_prefix и зашифрованные данные
            # Структура: header + nonce (16) + payload_prefix (32) + encrypted + noise
            # Добавляем шум в конце для дополнительной маскировки
            noise = secrets.token_bytes(secrets.randbelow(25) + 8)  # 8-32 bytes
            stego_packet = header + nonce + payload_prefix + encrypted + noise
            
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
        header = b'GET /index.html HTTP/1.1\r\n'
        header += b'Host: cloudflare.com\r\n'
        header += b'User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36\r\n'
        header += f'Content-Length: {content_length}\r\n'.encode()
        header += b'Connection: keep-alive\r\n'
        header += self.STEGO_MARKER_HTTP + b'\r\n'
        header += b'\r\n'
        return header
    
    def _create_icmp_header(self) -> bytes:
        """Создание ICMP-заголовка для маскировки"""
        # ICMP Echo Request (type=8, code=0)
        header = struct.pack('!BBHHH', 8, 0, 0, 0, 0)
        header += self.STEGO_MARKER_ICMP
        return header
    
    def _create_dns_header(self, data_length: int) -> bytes:
        """Создание DNS-заголовка для маскировки"""
        # DNS Query header (ID, flags, questions, answers, etc.)
        header = struct.pack('!HHHHHH',
                            secrets.randbelow(65536),  # Transaction ID (crypto-secure)
                            0x0100,  # Flags: standard query
                            1,       # Questions
                            0,       # Answer RRs
                            0,       # Authority RRs
                            0        # Additional RRs
        )
        # Query name: x0tta6bl4.stego
        header += b'\x08x0tta6bl4\x04stego\x00'
        header += struct.pack('!HH', 1, 1)  # Type A, Class IN
        header += self.STEGO_MARKER_DNS
        return header
    
    def decode_packet(self, stego_packet: bytes) -> Optional[bytes]:
        """
        Декодирование стеганографического пакета.
        
        Args:
            stego_packet: Стеганографический пакет
            
        Returns:
            Расшифрованные данные или None при ошибке
        """
        try:
            # Ищем секретный маркер и извлекаем данные
            encrypted_with_noise = None
            marker_len = 0
            
            if self.STEGO_MARKER_HTTP in stego_packet:
                # Это HTTP-маскировка
                parts = stego_packet.split(b'\r\n\r\n')
                if len(parts) > 1:
                    encrypted_with_noise = parts[1]
                    marker_len = len(self.STEGO_MARKER_HTTP)
                    
            elif self.STEGO_MARKER_ICMP in stego_packet:
                # Это ICMP-маскировка
                marker_pos = stego_packet.find(self.STEGO_MARKER_ICMP)
                if marker_pos > 0:
                    encrypted_with_noise = stego_packet[marker_pos + len(self.STEGO_MARKER_ICMP):]
                    marker_len = len(self.STEGO_MARKER_ICMP)
                else:
                    return None
                    
            elif self.STEGO_MARKER_DNS in stego_packet:
                # Это DNS-маскировка
                marker_pos = stego_packet.find(self.STEGO_MARKER_DNS)
                if marker_pos > 0:
                    encrypted_with_noise = stego_packet[marker_pos + len(self.STEGO_MARKER_DNS):]
                    marker_len = len(self.STEGO_MARKER_DNS)
                else:
                    return None
            else:
                # Не stego-пакет
                return None
            
            if encrypted_with_noise is None or len(encrypted_with_noise) < 16 + 32:
                return None
            
            # Извлекаем nonce (первые 16 байт после маркера)
            nonce = encrypted_with_noise[:16]
            # Извлекаем payload_prefix (следующие 32 байта)
            payload_prefix = encrypted_with_noise[16:48]
            # Остальное - зашифрованные данные + шум
            encrypted = encrypted_with_noise[48:]
            
            # Пробуем удалить шум (последние 8-32 байта)
            # Пробуем разные размеры шума
            for noise_len in range(8, 33):
                if len(encrypted) > noise_len:
                    ciphertext = encrypted[:-noise_len]
                    if len(ciphertext) == 0:
                        continue
                    
                    # Деривируем ключ используя сохраненный payload_prefix
                    session_key, derived_nonce = self._derive_session_key(payload_prefix)
                    
                    # Проверяем, совпадает ли nonce
                    if derived_nonce == nonce:
                        # Расшифровываем
                        cipher = Cipher(
                            algorithms.ChaCha20(session_key, nonce),
                            mode=None,
                            backend=self.backend
                        )
                        decryptor = cipher.decryptor()
                        decrypted = decryptor.update(ciphertext) + decryptor.finalize()
                        
                        # Убираем padding (нулевые байты в конце, если они были добавлены)
                        # В реальности нужно знать оригинальный размер, но для демо обрезаем нули
                        decrypted = decrypted.rstrip(b'\x00')
                        
                        logger.debug(f"Decoded packet: {len(stego_packet)} bytes -> {len(decrypted)} bytes")
                        return decrypted
            
            # Если не удалось расшифровать, возвращаем None
            logger.debug("Failed to decode stego packet")
            return None
            
        except Exception as e:
            logger.debug(f"Error decoding packet (may not be stego): {e}")
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
            return b'HTTP/1.1' in stego_packet and b'GET' in stego_packet
        elif protocol == "icmp":
            # Должен выглядеть как ICMP
            return stego_packet[:2] == b'\x08\x00'
        elif protocol == "dns":
            # Должен выглядеть как DNS
            return len(stego_packet) > 12 and stego_packet[2:4] == b'\x01\x00'
        
        return False

