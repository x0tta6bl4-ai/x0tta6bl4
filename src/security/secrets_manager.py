import os
import logging
from typing import Optional, Dict, Any
import hvac

logger = logging.getLogger(__name__)

class SecretsManager:
    """
    Unified secrets management for MaaS Enterprise.
    Prioritizes HashiCorp Vault, falls back to Environment Variables.
    """
    
    def __init__(self):
        self.vault_url = os.getenv("VAULT_ADDR")
        self.vault_token = os.getenv("VAULT_TOKEN")
        self.mount_point = os.getenv("VAULT_MOUNT_POINT", "secret")
        self.client = None
        self._enabled = False
        
        if self.vault_url and self.vault_token:
            try:
                self.client = hvac.Client(url=self.vault_url, token=self.vault_token)
                if self.client.is_authenticated():
                    self._enabled = True
                    logger.info(f"🔐 Vault connected at {self.vault_url}")
                else:
                    logger.warning("⚠️ Vault authentication failed")
            except Exception as e:
                logger.error(f"❌ Failed to connect to Vault: {e}")

    def get_secret(self, path: str, key: str = "value") -> Optional[str]:
        """Retrieve a secret string."""
        if self._enabled and self.client:
            try:
                # Standard KV v2 path
                response = self.client.secrets.kv.v2.read_secret_version(
                    mount_point=self.mount_point,
                    path=path
                )
                return response["data"]["data"].get(key)
            except Exception as e:
                logger.debug(f"Vault miss for {path}: {e}")
        
        # Fallback: Environment Variable (path converted to UPPER_SNAKE_CASE)
        env_key = f"{path.upper().replace('/', '_')}_{key.upper()}"
        return os.getenv(env_key)

    def set_secret(self, path: str, secret_data: Dict[str, Any]) -> bool:
        """Store a secret (Vault only)."""
        if self._enabled and self.client:
            try:
                self.client.secrets.kv.v2.create_or_update_secret(
                    mount_point=self.mount_point,
                    path=path,
                    secret=secret_data
                )
                return True
            except Exception as e:
                logger.error(f"Failed to write to Vault {path}: {e}")
        return False

    def get_pqc_keypair(self, key_id: str) -> tuple[Optional[bytes], Optional[bytes]]:
        """
        Retrieve PQC keypair (public, private) bytes.
        Expects Vault data to contain 'public_hex' and 'private_hex'.
        """
        pub_hex = self.get_secret(f"pqc/{key_id}", "public_hex")
        priv_hex = self.get_secret(f"pqc/{key_id}", "private_hex")
        
        if pub_hex and priv_hex:
            return bytes.fromhex(pub_hex), bytes.fromhex(priv_hex)
        return None, None

    def store_pqc_keypair(self, key_id: str, public_key: bytes, private_key: bytes) -> bool:
        """Store PQC keypair."""
        return self.set_secret(f"pqc/{key_id}", {
            "public_hex": public_key.hex(),
            "private_hex": private_key.hex()
        })

# Global instance
secrets_manager = SecretsManager()
