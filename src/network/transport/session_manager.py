import os
import json
import logging
import hashlib
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from typing import Dict, Optional

logger = logging.getLogger("pulse-session-manager")

class SessionPersistence:
    """
    Управление состоянием сессий x0tta6bl4_pulse.
    Сохраняет ключи и параметры потоков (SSRC, Seq) в зашифрованном виде.
    """

    def __init__(self, storage_path: str = ".tmp/pulse_sessions.bin"):
        self.storage_path = Path(storage_path)

        # Security Hardening: Derive master key from PQC identity if available
        id_path = Path(".tmp/pqc_identity.txt")
        if id_path.exists():
            with open(id_path, "rb") as f:
                self.master_secret = hashlib.sha256(f.read()).digest()
        else:
            self.master_secret = os.getenv("GHOST_NODE_SECRET", "fallback_entropy_!!!!").encode()[:32]
            if len(self.master_secret) < 32:
                self.master_secret = self.master_secret.ljust(32, b'\0')

        self.cipher = ChaCha20Poly1305(self.master_secret)

    def save_sessions(self, sessions: Dict):
        """Шифрование и сохранение всех активных сессий."""
        try:
            data = json.dumps(sessions).encode()
            nonce = os.urandom(12)
            encrypted = self.cipher.encrypt(nonce, data, None)

            with open(self.storage_path, "wb") as f:
                f.write(nonce + encrypted)
            logger.info(f"💾 Persisted {len(sessions)} sessions to disk.")
        except Exception as e:
            logger.error(f"Failed to persist sessions: {e}")

    def load_sessions(self) -> Dict:
        """Загрузка и дешифровка сессий."""
        if not self.storage_path.exists():
            return {}

        try:
            with open(self.storage_path, "rb") as f:
                raw = f.read()

            nonce = raw[:12]
            ciphertext = raw[12:]
            decrypted = self.cipher.decrypt(nonce, ciphertext, None)

            sessions = json.loads(decrypted.decode())
            logger.info(f"🔓 Restored {len(sessions)} sessions from disk.")
            return sessions
        except Exception as e:
            logger.warning(f"Could not restore sessions (maybe secret changed): {e}")
            return {}

    def clear(self):
        if self.storage_path.exists():
            self.storage_path.unlink()
