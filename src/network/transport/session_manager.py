from __future__ import annotations
import os
import json
import logging
import hashlib
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from typing import Dict

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
            self.master_secret = self._derive_env_or_ephemeral_secret()

        self.cipher = ChaCha20Poly1305(self.master_secret)

    @staticmethod
    def _production_mode() -> bool:
        return os.getenv("X0TTA6BL4_PRODUCTION", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    @classmethod
    def _derive_env_or_ephemeral_secret(cls) -> bytes:
        raw_secret = os.getenv("GHOST_NODE_SECRET")
        if raw_secret:
            master_secret = raw_secret.encode()[:32]
            return master_secret.ljust(32, b"\0")

        if cls._production_mode():
            raise RuntimeError(
                "GHOST_NODE_SECRET is required when .tmp/pqc_identity.txt is absent "
                "and X0TTA6BL4_PRODUCTION is enabled"
            )

        logger.warning(
            "GHOST_NODE_SECRET is not set and .tmp/pqc_identity.txt is absent; "
            "using an ephemeral session encryption key"
        )
        return os.urandom(32)

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

