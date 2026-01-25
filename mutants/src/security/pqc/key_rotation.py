"""
PQC Key Rotation с Backup и Recovery.

Автоматическая ротация PQC ключей с сохранением старых для recovery.
"""
import logging
import time
import json
import hashlib
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import os

logger = logging.getLogger(__name__)

# Try to import liboqs
try:
    from oqs import KeyEncapsulation, Signature
    LIBOQS_AVAILABLE = True
except ImportError:
    LIBOQS_AVAILABLE = False
    logger.warning("⚠️ liboqs not available - key rotation disabled")


@dataclass
class KeyRotationRecord:
    """Запись о ротации ключа."""
    key_id: str
    algorithm: str  # "Kyber768", "Dilithium3", etc.
    public_key: bytes
    private_key_encrypted: bytes  # Encrypted with master key
    created_at: float
    rotated_at: Optional[float] = None
    is_active: bool = True
    backup_location: Optional[str] = None  # Path to backup file


@dataclass
class KeyRotationConfig:
    """Конфигурация ротации ключей."""
    rotation_interval: float = 86400.0  # 24 hours
    backup_retention: float = 604800.0  # 7 days
    max_backups: int = 10
    backup_path: str = "/var/lib/x0tta6bl4/keys/backups"
    master_key_path: str = "/var/lib/x0tta6bl4/keys/master.key"


class PQCKeyRotation:
    """
    PQC Key Rotation Manager.
    
    Features:
    - Автоматическая ротация ключей (KEM и Signatures)
    - Backup старых ключей (encrypted)
    - Recovery из backup
    - Key history tracking
    """
    
    def __init__(
        self,
        node_id: str,
        config: Optional[KeyRotationConfig] = None,
        master_key: Optional[bytes] = None
    ):
        """
        Инициализация Key Rotation Manager.
        
        Args:
            node_id: ID узла
            config: Конфигурация ротации
            master_key: Master key для шифрования backup (генерируется если None)
        """
        if not LIBOQS_AVAILABLE:
            raise ImportError("liboqs-python required for key rotation")
        
        self.node_id = node_id
        self.config = config or KeyRotationConfig()
        
        # Generate or use provided master key
        if master_key:
            self.master_key = master_key
        else:
            import secrets
            self.master_key = secrets.token_bytes(32)
            # Save master key (in production, use KMS/Vault)
            self._save_master_key()
        
        # Key history
        self._key_history: Dict[str, List[KeyRotationRecord]] = {
            "kem": [],
            "signature": []
        }
        
        # Current active keys
        self._current_kem_key: Optional[KeyRotationRecord] = None
        self._current_sig_key: Optional[KeyRotationRecord] = None
        
        # Initialize backup directory
        Path(self.config.backup_path).mkdir(parents=True, exist_ok=True)
        
        logger.info(f"✅ PQC Key Rotation initialized for {node_id}")
    
    def _save_master_key(self):
        """Сохранить master key (в production использовать KMS/Vault)."""
        master_key_path = Path(self.config.master_key_path)
        master_key_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Encrypt master key with node-specific secret
        import secrets
        import hashlib
        node_secret = hashlib.sha256(f"{self.node_id}:x0tta6bl4".encode()).digest()
        
        # Simple XOR encryption (в production использовать proper encryption)
        encrypted = bytes(m ^ s for m, s in zip(self.master_key, node_secret))
        
        master_key_path.write_bytes(encrypted)
        os.chmod(master_key_path, 0o600)  # Read-only for owner
        logger.info(f"✅ Master key saved to {master_key_path}")
    
    def _load_master_key(self) -> bytes:
        """Загрузить master key."""
        master_key_path = Path(self.config.master_key_path)
        
        if not master_key_path.exists():
            raise FileNotFoundError(f"Master key not found: {master_key_path}")
        
        encrypted = master_key_path.read_bytes()
        
        # Decrypt
        import hashlib
        node_secret = hashlib.sha256(f"{self.node_id}:x0tta6bl4".encode()).digest()
        master_key = bytes(e ^ s for e, s in zip(encrypted, node_secret))
        
        return master_key
    
    def generate_kem_keypair(self, algorithm: str = "ML-KEM-768") -> Tuple[bytes, bytes]:
        """Генерировать KEM ключевую пару (NIST FIPS 203).
        
        Args:
            algorithm: KEM алгоритм (default: "ML-KEM-768", legacy: "Kyber768" supported)
        """
        # Map legacy names to NIST names
        if algorithm == "Kyber768":
            algorithm = "ML-KEM-768"
        elif algorithm == "Kyber512":
            algorithm = "ML-KEM-512"
        elif algorithm == "Kyber1024":
            algorithm = "ML-KEM-1024"
        
        kem = KeyEncapsulation(algorithm)
        public_key, private_key = kem.generate_keypair()
        return public_key, private_key
    
    def generate_signature_keypair(self, algorithm: str = "ML-DSA-65") -> Tuple[bytes, bytes]:
        """Генерировать signature ключевую пару (NIST FIPS 204).
        
        Args:
            algorithm: Signature алгоритм (default: "ML-DSA-65", legacy: "Dilithium3" supported)
        """
        # Map legacy names to NIST names
        if algorithm == "Dilithium2":
            algorithm = "ML-DSA-44"
        elif algorithm == "Dilithium3":
            algorithm = "ML-DSA-65"
        elif algorithm == "Dilithium5":
            algorithm = "ML-DSA-87"
        
        sig = Signature(algorithm)
        public_key, private_key = sig.generate_keypair()
        return public_key, private_key
    
    def rotate_kem_key(self, algorithm: str = "ML-KEM-768") -> KeyRotationRecord:
        """
        Ротировать KEM ключ.
        
        Returns:
            Новый KeyRotationRecord
        """
        # Generate new keypair
        public_key, private_key = self.generate_kem_keypair(algorithm)
        
        # Encrypt private key
        encrypted_private = self._encrypt_key(private_key)
        
        # Create record
        key_id = hashlib.sha256(public_key).hexdigest()[:16]
        record = KeyRotationRecord(
            key_id=key_id,
            algorithm=algorithm,
            public_key=public_key,
            private_key_encrypted=encrypted_private,
            created_at=time.time(),
            is_active=True
        )
        
        # Backup old key if exists
        if self._current_kem_key:
            self._backup_key(self._current_kem_key, "kem")
            self._current_kem_key.rotated_at = time.time()
            self._current_kem_key.is_active = False
        
        # Update current key
        self._current_kem_key = record
        self._key_history["kem"].append(record)
        
        logger.info(f"✅ KEM key rotated: {key_id} (algorithm: {algorithm})")
        
        return record
    
    def rotate_signature_key(self, algorithm: str = "ML-DSA-65") -> KeyRotationRecord:
        """
        Ротировать signature ключ.
        
        Returns:
            Новый KeyRotationRecord
        """
        # Generate new keypair
        public_key, private_key = self.generate_signature_keypair(algorithm)
        
        # Encrypt private key
        encrypted_private = self._encrypt_key(private_key)
        
        # Create record
        key_id = hashlib.sha256(public_key).hexdigest()[:16]
        record = KeyRotationRecord(
            key_id=key_id,
            algorithm=algorithm,
            public_key=public_key,
            private_key_encrypted=encrypted_private,
            created_at=time.time(),
            is_active=True
        )
        
        # Backup old key if exists
        if self._current_sig_key:
            self._backup_key(self._current_sig_key, "signature")
            self._current_sig_key.rotated_at = time.time()
            self._current_sig_key.is_active = False
        
        # Update current key
        self._current_sig_key = record
        self._key_history["signature"].append(record)
        
        logger.info(f"✅ Signature key rotated: {key_id} (algorithm: {algorithm})")
        
        return record
    
    def _encrypt_key(self, key: bytes) -> bytes:
        """Зашифровать ключ с master key."""
        import hashlib
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend
        
        # Derive encryption key from master key
        encryption_key = hashlib.sha256(self.master_key + b"key_encryption").digest()[:32]
        
        # AES-256-GCM encryption
        nonce = os.urandom(12)
        cipher = Cipher(
            algorithms.AES(encryption_key),
            modes.GCM(nonce),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(key) + encryptor.finalize()
        
        return nonce + encryptor.tag + ciphertext
    
    def _decrypt_key(self, encrypted_key: bytes) -> bytes:
        """Расшифровать ключ с master key."""
        import hashlib
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend
        
        # Derive decryption key
        decryption_key = hashlib.sha256(self.master_key + b"key_encryption").digest()[:32]
        
        # Extract nonce, tag, ciphertext
        nonce = encrypted_key[:12]
        tag = encrypted_key[12:28]
        ciphertext = encrypted_key[28:]
        
        # AES-256-GCM decryption
        cipher = Cipher(
            algorithms.AES(decryption_key),
            modes.GCM(nonce, tag),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        key = decryptor.update(ciphertext) + decryptor.finalize()
        
        return key
    
    def _backup_key(self, record: KeyRotationRecord, key_type: str):
        """Сохранить ключ в backup."""
        backup_file = Path(self.config.backup_path) / f"{key_type}_{record.key_id}_{int(record.created_at)}.json"
        
        # Create backup record (without private key in plaintext)
        backup_data = {
            "key_id": record.key_id,
            "algorithm": record.algorithm,
            "public_key": record.public_key.hex(),
            "private_key_encrypted": record.private_key_encrypted.hex(),
            "created_at": record.created_at,
            "rotated_at": record.rotated_at,
            "key_type": key_type
        }
        
        backup_file.write_text(json.dumps(backup_data, indent=2))
        record.backup_location = str(backup_file)
        
        logger.info(f"✅ Key backed up: {backup_file}")
        
        # Cleanup old backups
        self._cleanup_old_backups(key_type)
    
    def _cleanup_old_backups(self, key_type: str):
        """Удалить старые backup'ы."""
        backup_dir = Path(self.config.backup_path)
        backups = sorted(
            backup_dir.glob(f"{key_type}_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        # Keep only max_backups
        for backup in backups[self.config.max_backups:]:
            backup.unlink()
            logger.debug(f"🗑️ Deleted old backup: {backup}")
    
    def recover_key(self, key_id: str, key_type: str) -> Optional[KeyRotationRecord]:
        """
        Восстановить ключ из backup.
        
        Args:
            key_id: ID ключа для восстановления
            key_type: "kem" или "signature"
            
        Returns:
            KeyRotationRecord или None если не найден
        """
        backup_dir = Path(self.config.backup_path)
        backups = backup_dir.glob(f"{key_type}_{key_id}_*.json")
        
        for backup_file in backups:
            try:
                backup_data = json.loads(backup_file.read_text())
                
                record = KeyRotationRecord(
                    key_id=backup_data["key_id"],
                    algorithm=backup_data["algorithm"],
                    public_key=bytes.fromhex(backup_data["public_key"]),
                    private_key_encrypted=bytes.fromhex(backup_data["private_key_encrypted"]),
                    created_at=backup_data["created_at"],
                    rotated_at=backup_data.get("rotated_at"),
                    is_active=False,  # Recovered keys are not active
                    backup_location=str(backup_file)
                )
                
                logger.info(f"✅ Key recovered from backup: {key_id}")
                return record
                
            except Exception as e:
                logger.error(f"Failed to recover key from {backup_file}: {e}")
        
        logger.warning(f"⚠️ Key not found in backups: {key_id}")
        return None
    
    def get_current_kem_key(self) -> Optional[KeyRotationRecord]:
        """Получить текущий активный KEM ключ."""
        return self._current_kem_key
    
    def get_current_sig_key(self) -> Optional[KeyRotationRecord]:
        """Получить текущий активный signature ключ."""
        return self._current_sig_key
    
    def get_key_history(self, key_type: str) -> List[KeyRotationRecord]:
        """Получить историю ротации ключей."""
        return self._key_history.get(key_type, []).copy()
    
    def should_rotate(self) -> Tuple[bool, bool]:
        """
        Проверить, нужно ли ротировать ключи.
        
        Returns:
            (should_rotate_kem, should_rotate_sig)
        """
        now = time.time()
        
        should_rotate_kem = False
        should_rotate_sig = False
        
        if self._current_kem_key:
            age = now - self._current_kem_key.created_at
            should_rotate_kem = age >= self.config.rotation_interval
        
        if self._current_sig_key:
            age = now - self._current_sig_key.created_at
            should_rotate_sig = age >= self.config.rotation_interval
        
        return should_rotate_kem, should_rotate_sig

