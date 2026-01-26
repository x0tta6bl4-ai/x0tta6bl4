"""
Post-Quantum Cryptography using liboqs (Open Quantum Safe).

Реальная post-quantum криптография на основе NIST-approved алгоритмов:
- Kyber (KEM) - NIST PQC Standard
- Dilithium (Signatures) - NIST PQC Standard
- Hybrid mode (Classical + PQ)

⚠️ ТРЕБУЕТ liboqs-python: pip install liboqs-python
"""
import logging
import secrets
import os
from typing import Tuple, Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

# Prevent oqs from trying to auto-install liboqs (requires git which may not be available)
# Set environment variable before import to disable auto-installation
os.environ.setdefault("OQS_DISABLE_AUTO_INSTALL", "1")

# Try to import liboqs with safe error handling
LIBOQS_AVAILABLE = False
KeyEncapsulation = None
Signature = None

try:
    # Try importing oqs - if it fails, we'll use stub
    from oqs import KeyEncapsulation, Signature
    LIBOQS_AVAILABLE = True
    logger.info("✅ liboqs-python available - Post-Quantum Cryptography enabled")
except (ImportError, RuntimeError, AttributeError) as e:
    LIBOQS_AVAILABLE = False
    # Don't log as error in staging/dev - this is expected when liboqs is not installed
    import sys
    if os.getenv("X0TTA6BL4_PRODUCTION", "false").lower() != "true":
        logger.info(f"ℹ Staging mode: liboqs-python not available ({type(e).__name__}), using stub")
    else:
        logger.warning(f"⚠️ liboqs-python not available ({type(e).__name__}: {e}). Install with: pip install liboqs-python")


class PQAlgorithm(Enum):
    """Post-Quantum Cryptography algorithms (NIST FIPS 203/204 standardized).
    
    Используются новые NIST стандартизированные имена для совместимости с liboqs 0.15.0+.
    """
    # Key Encapsulation (NIST FIPS 203 - ML-KEM)
    ML_KEM_512 = "ML-KEM-512"      # NIST Level 1
    ML_KEM_768 = "ML-KEM-768"      # NIST Level 3 (рекомендуется) - бывший Kyber768
    ML_KEM_1024 = "ML-KEM-1024"    # NIST Level 5
    
    # Digital Signatures (NIST FIPS 204 - ML-DSA)
    ML_DSA_44 = "ML-DSA-44"        # NIST Level 2 - бывший Dilithium2
    ML_DSA_65 = "ML-DSA-65"        # NIST Level 3 (рекомендуется) - бывший Dilithium3
    ML_DSA_87 = "ML-DSA-87"        # NIST Level 5 - бывший Dilithium5
    
    # Alternative signature algorithms
    FALCON_512 = "Falcon-512"
    FALCON_1024 = "Falcon-1024"
    SPHINCS_PLUS_SHA2_128F = "SPHINCS+-SHA2-128f-simple"
    SPHINCS_PLUS_SHA2_192F = "SPHINCS+-SHA2-192f-simple"
    
    # Legacy names (для обратной совместимости)
    KYBER_768 = "ML-KEM-768"       # Alias для ML-KEM-768
    DILITHIUM_3 = "ML-DSA-65"       # Alias для ML-DSA-65
    HYBRID = "hybrid"              # Classical + PQ hybrid


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


class LibOQSBackend:
    """
    Backend для post-quantum криптографии на основе liboqs.
    
    Использует реальные NIST-approved алгоритмы:
    - Kyber для Key Encapsulation (KEM)
    - Dilithium для цифровых подписей
    """
    
    def __init__(self, kem_algorithm: str = "ML-KEM-768", sig_algorithm: str = "ML-DSA-65"):
        """
        Инициализация liboqs backend.
        
        Args:
            kem_algorithm: KEM алгоритм (Kyber512, Kyber768, Kyber1024)
            sig_algorithm: Signature алгоритм (Dilithium2, Dilithium3, Dilithium5)
        """
        if not LIBOQS_AVAILABLE:
            raise ImportError(
                "liboqs-python not installed. "
                "Install with: pip install liboqs-python"
            )
        
        self.kem_algorithm = kem_algorithm
        self.sig_algorithm = sig_algorithm
        
        logger.info(f"✅ LibOQS Backend initialized: KEM={kem_algorithm}, SIG={sig_algorithm}")
    
    def generate_kem_keypair(self) -> PQKeyPair:
        """
        Генерация KEM ключевой пары (для key exchange).
        
        Returns:
            PQKeyPair с публичным и приватным ключами
        """
        kem = KeyEncapsulation(self.kem_algorithm)
        keypair_result = kem.generate_keypair()
        if isinstance(keypair_result, tuple):
            public_key, private_key = keypair_result
        else:
            # liboqs returns single bytes object, need to extract both
            public_key = keypair_result
            private_key = kem.export_secret_key()
        
        # Generate key_id from public key
        import hashlib
        key_id = hashlib.sha256(public_key).hexdigest()[:16]
        
        # Map algorithm name to enum (handle both new NIST names and legacy)
        algo_name = self.kem_algorithm
        if algo_name == "Kyber768" or algo_name == "ML-KEM-768":
            algorithm = PQAlgorithm.ML_KEM_768
        elif algo_name == "Kyber512" or algo_name == "ML-KEM-512":
            algorithm = PQAlgorithm.ML_KEM_512
        elif algo_name == "Kyber1024" or algo_name == "ML-KEM-1024":
            algorithm = PQAlgorithm.ML_KEM_1024
        else:
            # Try direct enum lookup
            try:
                algorithm = PQAlgorithm(algo_name)
            except ValueError:
                # Fallback to ML-KEM-768 if unknown
                logger.warning(f"Unknown KEM algorithm {algo_name}, using ML-KEM-768")
                algorithm = PQAlgorithm.ML_KEM_768
        
        return PQKeyPair(
            public_key=public_key,
            private_key=private_key,
            algorithm=algorithm,
            key_id=key_id
        )
    
    def kem_encapsulate(self, public_key: bytes) -> Tuple[bytes, bytes]:
        """
        Key Encapsulation Mechanism (KEM) - инкапсуляция ключа.
        
        Создаёт shared secret и ciphertext для отправки получателю.
        
        Args:
            public_key: Публичный ключ получателя
            
        Returns:
            (shared_secret, ciphertext)
        """
        kem = KeyEncapsulation(self.kem_algorithm)
        # liboqs 0.15+ API: encap_secret takes public_key as argument
        ciphertext, shared_secret = kem.encap_secret(public_key)
        
        return shared_secret, ciphertext
    
    def kem_decapsulate(self, private_key: bytes, ciphertext: bytes) -> bytes:
        """
        KEM Decapsulation - восстановление shared secret.
        
        Args:
            private_key: Приватный ключ получателя
            ciphertext: Зашифрованный shared secret
            
        Returns:
            shared_secret
        """
        kem = KeyEncapsulation(self.kem_algorithm, private_key)
        shared_secret = kem.decap_secret(ciphertext)
        
        return shared_secret
    
    def generate_signature_keypair(self) -> PQKeyPair:
        """
        Генерация ключевой пары для цифровых подписей.
        
        Returns:
            PQKeyPair с публичным и приватным ключами
        """
        sig = Signature(self.sig_algorithm)
        # liboqs generate_keypair() returns only public_key
        public_key = sig.generate_keypair()
        # Private key is stored internally, export it
        private_key = sig.export_secret_key()
        
        import hashlib
        key_id = hashlib.sha256(public_key).hexdigest()[:16]
        
        # Map algorithm name to enum (handle both new NIST names and legacy)
        algo_name = self.sig_algorithm
        if algo_name == "Dilithium3" or algo_name == "ML-DSA-65":
            algorithm = PQAlgorithm.ML_DSA_65
        elif algo_name == "Dilithium2" or algo_name == "ML-DSA-44":
            algorithm = PQAlgorithm.ML_DSA_44
        elif algo_name == "Dilithium5" or algo_name == "ML-DSA-87":
            algorithm = PQAlgorithm.ML_DSA_87
        else:
            # Try direct enum lookup
            try:
                algorithm = PQAlgorithm(algo_name)
            except ValueError:
                # Fallback to ML-DSA-65 if unknown
                logger.warning(f"Unknown signature algorithm {algo_name}, using ML-DSA-65")
                algorithm = PQAlgorithm.ML_DSA_65
        
        return PQKeyPair(
            public_key=public_key,
            private_key=private_key,
            algorithm=algorithm,
            key_id=key_id
        )
    
    def sign(self, private_key: bytes, message: bytes) -> bytes:
        """
        Подписать сообщение.
        
        Args:
            private_key: Приватный ключ
            message: Сообщение для подписи
            
        Returns:
            Цифровая подпись
        """
        sig = Signature(self.sig_algorithm, private_key)
        signature = sig.sign(message)
        
        return signature
    
    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        """
        Проверить цифровую подпись.
        
        Args:
            public_key: Публичный ключ подписанта
            message: Оригинальное сообщение
            signature: Цифровая подпись
            
        Returns:
            True если подпись валидна, False иначе
        """
        sig = Signature(self.sig_algorithm)
        is_valid = sig.verify(message, signature, public_key)
        
        return is_valid


class HybridPQEncryption:
    """
    Hybrid Classical + Post-Quantum Encryption.
    
    Комбинирует классическое шифрование (ECDH/X25519) с post-quantum (Kyber)
    для защиты от текущих и будущих угроз.
    
    Безопасность = MAX(classical, post-quantum)
    """
    
    def __init__(self, kem_algorithm: str = "Kyber768"):
        """
        Инициализация hybrid encryption.
        
        Args:
            kem_algorithm: PQC KEM алгоритм (Kyber512, Kyber768, Kyber1024)
        """
        if not LIBOQS_AVAILABLE:
            raise ImportError("liboqs-python required for hybrid encryption")
        
        self.pq_backend = LibOQSBackend(kem_algorithm=kem_algorithm)
        self.kem_algorithm = kem_algorithm
    
    def generate_hybrid_keypair(self) -> Dict[str, Any]:
        """
        Генерация гибридной ключевой пары (Classical + PQ).
        
        Returns:
            Dict с classical и post-quantum ключами
        """
        # Post-quantum keypair (Kyber)
        pq_keypair = self.pq_backend.generate_kem_keypair()
        
        # Classical keypair (X25519-like, simplified for demo)
        # В продакшене использовать cryptography.hazmat.primitives.asymmetric.x25519
        import hashlib
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
        
        Args:
            pq_public_key: Post-quantum публичный ключ
            classical_public_key: Классический публичный ключ
            
        Returns:
            (combined_secret, ciphertexts)
        """
        # PQ encapsulation (Kyber)
        pq_secret, pq_ciphertext = self.pq_backend.kem_encapsulate(pq_public_key)
        
        # Classical encapsulation (simplified - в продакшене использовать X25519)
        import hashlib
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
        
        Args:
            ciphertexts: Зашифрованные ciphertext'ы (pq, classical)
            pq_private_key: Post-quantum приватный ключ
            classical_private_key: Классический приватный ключ
            
        Returns:
            combined_secret
        """
        # PQ decapsulation
        pq_secret = self.pq_backend.kem_decapsulate(pq_private_key, ciphertexts["pq"])
        
        # Classical decapsulation
        import hashlib
        classical_random = self._classical_decrypt(ciphertexts["classical"], classical_private_key)
        classical_public_key = hashlib.sha256(classical_private_key).digest()
        classical_secret = hashlib.sha256(classical_random + classical_public_key).digest()
        
        # Combine secrets
        combined_secret = hashlib.sha256(pq_secret + classical_secret).digest()
        
        return combined_secret
    
    def _classical_encrypt(self, message: bytes, public_key: bytes) -> bytes:
        """Классическое шифрование (упрощённое для демо)."""
        import hashlib
        key = hashlib.sha256(public_key).digest()
        nonce = secrets.token_bytes(16)
        encrypted = bytes(m ^ k for m, k in zip(message, key))
        return nonce + encrypted
    
    def _classical_decrypt(self, ciphertext: bytes, private_key: bytes) -> bytes:
        """Классическое расшифрование."""
        import hashlib
        nonce = ciphertext[:16]
        encrypted = ciphertext[16:]
        public_key = hashlib.sha256(private_key).digest()
        key = hashlib.sha256(public_key).digest()
        return bytes(e ^ k for e, k in zip(encrypted, key))


class PQMeshSecurityLibOQS:
    """
    Post-Quantum Security для Mesh Network (на основе liboqs).
    
    Интегрирует реальную PQ криптографию с mesh протоколами.
    """
    
    def __init__(self, node_id: str, kem_algorithm: str = "ML-KEM-768", sig_algorithm: str = "ML-DSA-65"):
        if not LIBOQS_AVAILABLE:
            raise RuntimeError("liboqs not available. Cannot initialize PQMeshSecurityLibOQS")
        """
        Инициализация PQ mesh security.
        
        Args:
            node_id: ID узла
            kem_algorithm: KEM алгоритм (default: "ML-KEM-768", NIST FIPS 203 Level 3)
                          Legacy names supported: "Kyber512"→"ML-KEM-512", "Kyber768"→"ML-KEM-768", "Kyber1024"→"ML-KEM-1024"
            sig_algorithm: Signature алгоритм (default: "ML-DSA-65", NIST FIPS 204 Level 3)
                          Legacy names supported: "Dilithium2"→"ML-DSA-44", "Dilithium3"→"ML-DSA-65", "Dilithium5"→"ML-DSA-87"
        """
        if not LIBOQS_AVAILABLE:
            raise ImportError("liboqs-python required for PQ mesh security")
        
        # Map legacy names to NIST names
        legacy_kem_map = {"Kyber512": "ML-KEM-512", "Kyber768": "ML-KEM-768", "Kyber1024": "ML-KEM-1024"}
        legacy_sig_map = {"Dilithium2": "ML-DSA-44", "Dilithium3": "ML-DSA-65", "Dilithium5": "ML-DSA-87"}
        
        if kem_algorithm in legacy_kem_map:
            kem_algorithm = legacy_kem_map[kem_algorithm]
        if sig_algorithm in legacy_sig_map:
            sig_algorithm = legacy_sig_map[sig_algorithm]
        
        self.node_id = node_id
        self.pq_backend = LibOQSBackend(kem_algorithm=kem_algorithm, sig_algorithm=sig_algorithm)
        self.hybrid = HybridPQEncryption(kem_algorithm=kem_algorithm)
        
        # Долгосрочная ключевая пара для KEM
        self.kem_keypair = self.pq_backend.generate_kem_keypair()
        
        # Долгосрочная ключевая пара для подписей
        self.sig_keypair = self.pq_backend.generate_signature_keypair()
        
        # Сессионные ключи с peers
        self._peer_keys: Dict[str, bytes] = {}
        
        logger.info(f"✅ PQ Mesh Security initialized for {node_id}")
    
    def get_public_keys(self) -> Dict[str, str]:
        """Получить публичные ключи для sharing."""
        return {
            "node_id": self.node_id,
            "kem_public_key": self.kem_keypair.public_key.hex(),
            "sig_public_key": self.sig_keypair.public_key.hex(),
            "kem_algorithm": self.kem_keypair.algorithm.value,
            "sig_algorithm": self.sig_keypair.algorithm.value,
            "key_id": self.kem_keypair.key_id
        }
    
    async def establish_secure_channel(self, peer_id: str, peer_public_keys: Dict) -> bytes:
        """
        Установить quantum-safe канал с peer.
        
        Args:
            peer_id: ID peer'а
            peer_public_keys: Публичные ключи peer'а (kem_public_key, sig_public_key)
            
        Returns:
            shared_secret для шифрования канала
        """
        # Encapsulate к peer
        shared_secret, ciphertexts = self.hybrid.hybrid_encapsulate(
            bytes.fromhex(peer_public_keys["kem_public_key"]),
            bytes.fromhex(peer_public_keys.get("classical_public_key", "00" * 32))
        )
        
        self._peer_keys[peer_id] = shared_secret
        
        logger.info(f"✅ Established PQ-secure channel with {peer_id}")
        
        return shared_secret
    
    def sign_beacon(self, beacon_data: bytes) -> bytes:
        """
        Подписать beacon сообщение.
        
        Args:
            beacon_data: Данные beacon'а
            
        Returns:
            Цифровая подпись
        """
        signature = self.pq_backend.sign(self.sig_keypair.private_key, beacon_data)
        return signature
    
    def verify_beacon(self, beacon_data: bytes, signature: bytes, peer_public_key: bytes) -> bool:
        """
        Проверить подпись beacon'а от peer'а.
        
        Args:
            beacon_data: Данные beacon'а
            signature: Цифровая подпись
            peer_public_key: Публичный ключ peer'а
            
        Returns:
            True если подпись валидна
        """
        is_valid = self.pq_backend.verify(peer_public_key, beacon_data, signature)
        return is_valid
    
    def encrypt_for_peer(self, peer_id: str, plaintext: bytes) -> bytes:
        """Зашифровать данные для peer."""
        key = self._peer_keys.get(peer_id)
        if not key:
            raise ValueError(f"No shared key with {peer_id}")
        
        # AES-256-GCM с PQ-derived key (упрощённое для демо)
        import hashlib
        nonce = secrets.token_bytes(12)
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
        
        import hashlib
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
            "algorithm": f"hybrid_{self.kem_keypair.algorithm.value}_{self.sig_keypair.algorithm.value}",
            "pq_security_level": "NIST Level 3",
            "kem_algorithm": self.kem_keypair.algorithm.value,
            "sig_algorithm": self.sig_keypair.algorithm.value,
            "key_exchange": "quantum_safe",
            "peers_with_pq": len(self._peer_keys)
        }

