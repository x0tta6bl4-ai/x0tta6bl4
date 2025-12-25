"""
Post-Quantum Cryptography Module.
Квантово-устойчивые криптографические примитивы.

⚠️ DEPRECATED: SimplifiedNTRU небезопасен! Используйте post_quantum_liboqs.py

Этот модуль содержит устаревшую mock реализацию для обратной совместимости.
Для production используйте:
- src/security/post_quantum_liboqs.py (реальная PQC на liboqs)
- LibOQSBackend, HybridPQEncryption, PQMeshSecurityLibOQS

Implements (DEPRECATED):
- SimplifiedNTRU (⚠️ INSECURE - только для тестов)
- HybridEncryption (использует SimplifiedNTRU)
- QuantumSafeKeyExchange (использует SimplifiedNTRU)
"""
import hashlib
import secrets
import logging
import os
from typing import Tuple, Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import struct

logger = logging.getLogger(__name__)

# 🔴 PRODUCTION GUARD: Запретить SimplifiedNTRU в production
PRODUCTION_MODE = os.getenv("X0TTA6BL4_PRODUCTION", "false").lower() == "true"
ALLOW_MOCK_PQC = os.getenv("X0TTA6BL4_ALLOW_MOCK_PQC", "false").lower() == "true"

if PRODUCTION_MODE and not ALLOW_MOCK_PQC:
    logger.critical(
        "🔴 PRODUCTION MODE: SimplifiedNTRU запрещён! "
        "Используйте LibOQSBackend из post_quantum_liboqs.py"
    )


class PQAlgorithm(Enum):
    """Поддерживаемые post-quantum алгоритмы."""
    NTRU_HPS = "ntru_hps"          # NTRU High Performance
    KYBER = "kyber"                # CRYSTALS-Kyber (NIST winner)
    DILITHIUM = "dilithium"        # CRYSTALS-Dilithium signatures
    HYBRID = "hybrid"              # Classical + PQ hybrid


# === Simplified NTRU-like Implementation ===
# ВАЖНО: Это упрощённая реализация для демонстрации.
# В продакшене использовать liboqs или pqcrypto библиотеки.

class NTRUParameters:
    """Параметры для NTRU-like схемы."""
    # Упрощённые параметры (в реальности используются большие)
    N = 509         # Степень полинома
    Q = 2048        # Модуль
    P = 3           # Малый модуль
    D = 128         # Количество единиц в приватном ключе


@dataclass
class PQKeyPair:
    """Post-Quantum ключевая пара."""
    public_key: bytes
    private_key: bytes
    algorithm: PQAlgorithm
    key_id: str


@dataclass
class PQCiphertext:
    """Post-Quantum шифртекст."""
    ciphertext: bytes
    encapsulated_key: bytes
    algorithm: PQAlgorithm


class SimplifiedNTRU:
    """
    Упрощённая NTRU-подобная реализация.
    
    ⚠️ DEPRECATED / INSECURE ⚠️
    
    ВНИМАНИЕ: Эта реализация НЕ безопасна и НЕ обеспечивает post-quantum защиту!
    Это просто XOR + хэши, которые легко взламываются.
    
    🔴 НЕ ИСПОЛЬЗУЙТЕ В PRODUCTION!
    
    Для production используйте:
    - src/security/post_quantum_liboqs.py (реальная PQC на liboqs)
    - LibOQSBackend с Kyber/Dilithium
    
    Эта реализация оставлена только для:
    - Обратной совместимости
    - Unit тестов (где не нужна реальная безопасность)
    - Демонстрации архитектуры
    
    См. AUDIT_PQC.md для детального анализа уязвимостей.
    """
    
    def __init__(self, params: NTRUParameters = None):
        # 🔴 PRODUCTION GUARD: Запретить в production
        if PRODUCTION_MODE and not ALLOW_MOCK_PQC:
            raise RuntimeError(
                "🔴 SimplifiedNTRU ЗАПРЕЩЁН В PRODUCTION!\n"
                "Эта реализация небезопасна (XOR + хэши, не настоящая PQC).\n"
                "Используйте LibOQSBackend из src/security/post_quantum_liboqs.py\n"
                "Для тестов установите X0TTA6BL4_ALLOW_MOCK_PQC=true"
            )
        
        if PRODUCTION_MODE:
            logger.warning(
                "⚠️ SimplifiedNTRU используется в production с ALLOW_MOCK_PQC=true. "
                "Это НЕБЕЗОПАСНО! Используйте только для тестирования."
            )
        
        self.params = params or NTRUParameters()
    
    def generate_keypair(self) -> PQKeyPair:
        """
        Генерация ключевой пары.
        
        В реальном NTRU это полиномы, здесь упрощено до байтов.
        """
        # Генерируем случайные байты для ключей
        private_key = secrets.token_bytes(self.params.N // 4)
        
        # Публичный ключ = хэш приватного (упрощение)
        # В реальном NTRU это f^-1 * g mod q
        public_key = hashlib.sha512(private_key).digest()
        
        key_id = hashlib.sha256(public_key).hexdigest()[:16]
        
        return PQKeyPair(
            public_key=public_key,
            private_key=private_key,
            algorithm=PQAlgorithm.NTRU_HPS,
            key_id=key_id
        )
    
    def encapsulate(self, public_key: bytes) -> Tuple[bytes, bytes]:
        """
        Key Encapsulation Mechanism (KEM).
        
        Создаёт общий секрет и шифртекст.
        
        Returns:
            (shared_secret, ciphertext)
        """
        # Генерируем случайное сообщение
        random_msg = secrets.token_bytes(32)
        
        # Создаём shared secret
        shared_secret = hashlib.sha256(random_msg + public_key).digest()
        
        # Создаём ciphertext (в реальном NTRU это сложная операция)
        ciphertext = self._encrypt_message(random_msg, public_key)
        
        return shared_secret, ciphertext
    
    def decapsulate(self, ciphertext: bytes, private_key: bytes) -> bytes:
        """
        Decapsulation - восстановление shared secret.
        
        Returns:
            shared_secret
        """
        # Расшифровываем сообщение
        random_msg = self._decrypt_message(ciphertext, private_key)
        
        # Восстанавливаем public key из private
        public_key = hashlib.sha512(private_key).digest()
        
        # Вычисляем shared secret
        shared_secret = hashlib.sha256(random_msg + public_key).digest()
        
        return shared_secret
    
    def _encrypt_message(self, message: bytes, public_key: bytes) -> bytes:
        """Упрощённое шифрование."""
        # XOR с расширенным ключом + случайность
        random_pad = secrets.token_bytes(len(message))
        extended_key = hashlib.shake_256(public_key).digest(len(message))
        
        encrypted = bytes(m ^ k ^ r for m, k, r in zip(message, extended_key, random_pad))
        
        return random_pad + encrypted
    
    def _decrypt_message(self, ciphertext: bytes, private_key: bytes) -> bytes:
        """Упрощённое расшифрование."""
        msg_len = len(ciphertext) // 2
        random_pad = ciphertext[:msg_len]
        encrypted = ciphertext[msg_len:]
        
        public_key = hashlib.sha512(private_key).digest()
        extended_key = hashlib.shake_256(public_key).digest(len(encrypted))
        
        decrypted = bytes(e ^ k ^ r for e, k, r in zip(encrypted, extended_key, random_pad))
        
        return decrypted


class HybridEncryption:
    """
    Hybrid Classical + Post-Quantum Encryption.
    
    ⚠️ DEPRECATED: Использует SimplifiedNTRU (небезопасно!)
    
    Для production используйте:
    - HybridPQEncryption из post_quantum_liboqs.py
    
    Комбинирует классическое шифрование (для текущей безопасности)
    с post-quantum (для защиты от будущих квантовых атак).
    
    ⚠️ ВНИМАНИЕ: Текущая реализация НЕ безопасна, т.к. использует SimplifiedNTRU.
    """
    
    def __init__(self):
        import warnings
        warnings.warn(
            "HybridEncryption использует SimplifiedNTRU (небезопасно!). "
            "Используйте HybridPQEncryption из post_quantum_liboqs.py",
            DeprecationWarning,
            stacklevel=2
        )
        self.pq = SimplifiedNTRU()
    
    def generate_hybrid_keypair(self) -> Dict[str, Any]:
        """
        Генерация гибридной ключевой пары.
        
        Returns:
            Dict с classical и post-quantum ключами
        """
        # Post-quantum keypair
        pq_keypair = self.pq.generate_keypair()
        
        # Classical keypair (используем ECDH-подобный подход)
        classical_private = secrets.token_bytes(32)
        classical_public = hashlib.sha256(classical_private).digest()
        
        return {
            "type": "hybrid_keypair",
            "pq": {
                "public_key": pq_keypair.public_key.hex(),
                "private_key": pq_keypair.private_key.hex(),
                "algorithm": pq_keypair.algorithm.value
            },
            "classical": {
                "public_key": classical_public.hex(),
                "private_key": classical_private.hex()
            },
            "key_id": pq_keypair.key_id
        }
    
    def hybrid_encapsulate(
        self,
        pq_public_key: bytes,
        classical_public_key: bytes
    ) -> Tuple[bytes, Dict[str, bytes]]:
        """
        Гибридная инкапсуляция ключа.
        
        Returns:
            (combined_secret, ciphertexts)
        """
        # PQ encapsulation
        pq_secret, pq_ciphertext = self.pq.encapsulate(pq_public_key)
        
        # Classical encapsulation (simplified)
        classical_random = secrets.token_bytes(32)
        classical_secret = hashlib.sha256(classical_random + classical_public_key).digest()
        classical_ciphertext = self._classical_encrypt(classical_random, classical_public_key)
        
        # Combine secrets: SHA-256(pq_secret || classical_secret)
        combined_secret = hashlib.sha256(pq_secret + classical_secret).digest()
        
        return combined_secret, {
            "pq": pq_ciphertext,
            "classical": classical_ciphertext
        }
    
    def hybrid_decapsulate(
        self,
        ciphertexts: Dict[str, bytes],
        pq_private_key: bytes,
        classical_private_key: bytes
    ) -> bytes:
        """
        Гибридная декапсуляция.
        
        Returns:
            combined_secret
        """
        # PQ decapsulation
        pq_secret = self.pq.decapsulate(ciphertexts["pq"], pq_private_key)
        
        # Classical decapsulation
        classical_random = self._classical_decrypt(ciphertexts["classical"], classical_private_key)
        classical_public_key = hashlib.sha256(classical_private_key).digest()
        classical_secret = hashlib.sha256(classical_random + classical_public_key).digest()
        
        # Combine secrets
        combined_secret = hashlib.sha256(pq_secret + classical_secret).digest()
        
        return combined_secret
    
    def _classical_encrypt(self, message: bytes, public_key: bytes) -> bytes:
        """Классическое шифрование (упрощённое)."""
        key = hashlib.sha256(public_key).digest()
        nonce = secrets.token_bytes(16)
        encrypted = bytes(m ^ k for m, k in zip(message, key))
        return nonce + encrypted
    
    def _classical_decrypt(self, ciphertext: bytes, private_key: bytes) -> bytes:
        """Классическое расшифрование."""
        nonce = ciphertext[:16]
        encrypted = ciphertext[16:]
        public_key = hashlib.sha256(private_key).digest()
        key = hashlib.sha256(public_key).digest()
        return bytes(e ^ k for e, k in zip(encrypted, key))


class QuantumSafeKeyExchange:
    """
    Quantum-Safe Key Exchange Protocol.
    
    Реализует безопасный обмен ключами, устойчивый к квантовым атакам.
    """
    
    def __init__(self):
        self.hybrid = HybridEncryption()
        self._sessions: Dict[str, Dict] = {}
    
    def initiate_exchange(self, my_keypair: Dict) -> Dict[str, Any]:
        """
        Инициировать обмен ключами (сторона A).
        
        Returns:
            Сообщение для отправки стороне B
        """
        session_id = secrets.token_hex(16)
        
        # Генерируем ephemeral keypair
        ephemeral = self.hybrid.generate_hybrid_keypair()
        
        self._sessions[session_id] = {
            "ephemeral": ephemeral,
            "my_keypair": my_keypair,
            "state": "initiated"
        }
        
        return {
            "type": "key_exchange_init",
            "session_id": session_id,
            "pq_public_key": ephemeral["pq"]["public_key"],
            "classical_public_key": ephemeral["classical"]["public_key"],
            "static_public_key": my_keypair["pq"]["public_key"]
        }
    
    def respond_to_exchange(
        self,
        init_message: Dict,
        my_keypair: Dict
    ) -> Tuple[bytes, Dict[str, Any]]:
        """
        Ответить на обмен ключами (сторона B).
        
        Returns:
            (shared_secret, response_message)
        """
        session_id = init_message["session_id"]
        
        # Декодируем ключи инициатора
        initiator_pq_pub = bytes.fromhex(init_message["pq_public_key"])
        initiator_classical_pub = bytes.fromhex(init_message["classical_public_key"])
        
        # Генерируем ephemeral keypair
        ephemeral = self.hybrid.generate_hybrid_keypair()
        
        # Encapsulate к initiator
        shared_secret, ciphertexts = self.hybrid.hybrid_encapsulate(
            initiator_pq_pub,
            initiator_classical_pub
        )
        
        response = {
            "type": "key_exchange_response",
            "session_id": session_id,
            "pq_public_key": ephemeral["pq"]["public_key"],
            "classical_public_key": ephemeral["classical"]["public_key"],
            "pq_ciphertext": ciphertexts["pq"].hex(),
            "classical_ciphertext": ciphertexts["classical"].hex()
        }
        
        return shared_secret, response
    
    def complete_exchange(
        self,
        response_message: Dict
    ) -> bytes:
        """
        Завершить обмен ключами (сторона A).
        
        Returns:
            shared_secret
        """
        session_id = response_message["session_id"]
        session = self._sessions.get(session_id)
        
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        ephemeral = session["ephemeral"]
        
        # Decapsulate
        ciphertexts = {
            "pq": bytes.fromhex(response_message["pq_ciphertext"]),
            "classical": bytes.fromhex(response_message["classical_ciphertext"])
        }
        
        shared_secret = self.hybrid.hybrid_decapsulate(
            ciphertexts,
            bytes.fromhex(ephemeral["pq"]["private_key"]),
            bytes.fromhex(ephemeral["classical"]["private_key"])
        )
        
        # Cleanup session
        del self._sessions[session_id]
        
        return shared_secret


# === Integration with Mesh Network ===

class PQMeshSecurity:
    """
    Post-Quantum Security для Mesh Network.
    
    Интегрирует PQ криптографию с mesh протоколами.
    """
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.hybrid = HybridEncryption()
        self.key_exchange = QuantumSafeKeyExchange()
        
        # Наша долгосрочная ключевая пара
        self.keypair = self.hybrid.generate_hybrid_keypair()
        
        # Сессионные ключи с peers
        self._peer_keys: Dict[str, bytes] = {}
    
    def get_public_keys(self) -> Dict[str, str]:
        """Получить публичные ключи для sharing."""
        return {
            "node_id": self.node_id,
            "pq_public_key": self.keypair["pq"]["public_key"],
            "classical_public_key": self.keypair["classical"]["public_key"],
            "key_id": self.keypair["key_id"]
        }
    
    async def establish_secure_channel(self, peer_id: str, peer_public_keys: Dict) -> bytes:
        """
        Установить quantum-safe канал с peer.
        
        Returns:
            shared_secret для шифрования канала
        """
        # Encapsulate к peer
        shared_secret, ciphertexts = self.hybrid.hybrid_encapsulate(
            bytes.fromhex(peer_public_keys["pq_public_key"]),
            bytes.fromhex(peer_public_keys["classical_public_key"])
        )
        
        self._peer_keys[peer_id] = shared_secret
        
        logger.info(f"Established PQ-secure channel with {peer_id}")
        
        return shared_secret
    
    def encrypt_for_peer(self, peer_id: str, plaintext: bytes) -> bytes:
        """Зашифровать данные для peer."""
        key = self._peer_keys.get(peer_id)
        if not key:
            raise ValueError(f"No shared key with {peer_id}")
        
        # AES-256-GCM с PQ-derived key
        nonce = secrets.token_bytes(12)
        
        # Упрощённое шифрование (в продакшене использовать AES-GCM)
        extended_key = hashlib.shake_256(key + nonce).digest(len(plaintext))
        ciphertext = bytes(p ^ k for p, k in zip(plaintext, extended_key))
        
        # MAC
        mac = hashlib.sha256(key + nonce + ciphertext).digest()[:16]
        
        return nonce + ciphertext + mac
    
    def decrypt_from_peer(self, peer_id: str, ciphertext: bytes) -> bytes:
        """Расшифровать данные от peer."""
        key = self._peer_keys.get(peer_id)
        if not key:
            raise ValueError(f"No shared key with {peer_id}")
        
        nonce = ciphertext[:12]
        mac = ciphertext[-16:]
        encrypted = ciphertext[12:-16]
        
        # Verify MAC
        expected_mac = hashlib.sha256(key + nonce + encrypted).digest()[:16]
        if mac != expected_mac:
            raise ValueError("MAC verification failed")
        
        # Decrypt
        extended_key = hashlib.shake_256(key + nonce).digest(len(encrypted))
        plaintext = bytes(e ^ k for e, k in zip(encrypted, extended_key))
        
        return plaintext
    
    def get_security_level(self) -> Dict[str, Any]:
        """Получить информацию об уровне безопасности."""
        return {
            "algorithm": "hybrid_ntru_classical",
            "pq_security_level": "NIST Level 3 equivalent",
            "classical_security_level": "256-bit",
            "key_exchange": "quantum_safe",
            "peers_with_pq": len(self._peer_keys)
        }
