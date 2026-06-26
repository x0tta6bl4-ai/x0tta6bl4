from __future__ import annotations
import os
import hashlib
import logging
from typing import Optional, Dict, Any
import hvac

from src.core.thinking.agent_thinking import AgentThinkingCoach

logger = logging.getLogger(__name__)


def _safe_hash(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def _safe_count_bucket(value: int) -> str:
    if value <= 0:
        return "0"
    if value <= 3:
        return "1-3"
    if value <= 10:
        return "4-10"
    if value <= 100:
        return "11-100"
    return "100+"


def _safe_number_band(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "non_numeric"
    if value < 0:
        return "negative"
    if value == 0:
        return "0"
    if value <= 32:
        return "1-32"
    if value <= 128:
        return "33-128"
    if value <= 1024:
        return "129-1024"
    return "1024+"


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
        self.thinking_coach = AgentThinkingCoach(
            agent_id=f"secrets-manager:{_safe_hash(self.vault_url)}",
            role="security",
            capabilities=("zero-trust", "ops"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "secrets_manager_init",
                "goal": "Initialize secret retrieval safely",
                "signals": {
                    "vault_url_hash": _safe_hash(self.vault_url),
                    "vault_token_present": bool(self.vault_token),
                    "mount_point_hash": _safe_hash(self.mount_point),
                    "vault_enabled": False,
                },
                "safety_boundary": (
                    "Keep Vault token, raw Vault URL, secret paths, secret keys, "
                    "secret values, and PQC key bytes out of thinking context."
                ),
            }
        )
        
        if self.vault_url and self.vault_token:
            try:
                self.client = hvac.Client(url=self.vault_url, token=self.vault_token)
                if self.client.is_authenticated():
                    self._enabled = True
                    self._record_thinking(
                        "secrets_manager_vault_connected",
                        "Connect to Vault for secret retrieval safely",
                        {
                            "vault_url_hash": _safe_hash(self.vault_url),
                            "mount_point_hash": _safe_hash(self.mount_point),
                            "vault_enabled": True,
                        },
                    )
                    logger.info(f"🔐 Vault connected at {self.vault_url}")
                else:
                    self._record_thinking(
                        "secrets_manager_vault_auth_failed",
                        "Record Vault authentication failure safely",
                        {
                            "vault_url_hash": _safe_hash(self.vault_url),
                            "mount_point_hash": _safe_hash(self.mount_point),
                            "vault_enabled": False,
                        },
                    )
                    logger.warning("⚠️ Vault authentication failed")
            except (ValueError, TypeError, RuntimeError, OSError) as e:
                self._record_thinking(
                    "secrets_manager_vault_connect_failed",
                    "Record Vault connection failure safely",
                    {
                        "vault_url_hash": _safe_hash(self.vault_url),
                        "error_type": type(e).__name__,
                        "vault_enabled": False,
                    },
                )
                logger.error(f"❌ Failed to connect to Vault: {e}")

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not hasattr(self, "thinking_coach"):
            self.thinking_coach = AgentThinkingCoach(
                agent_id=f"secrets-manager:{_safe_hash(getattr(self, 'vault_url', ''))}",
                role="security",
                capabilities=("zero-trust", "ops"),
            )
            self.last_thinking_context = self.thinking_coach.prepare_task(
                {
                    "task_type": "secrets_manager_lazy_init",
                    "goal": "Initialize secret retrieval thinking state lazily",
                    "signals": {
                        "vault_url_hash": _safe_hash(getattr(self, "vault_url", "")),
                        "mount_point_hash": _safe_hash(
                            getattr(self, "mount_point", "")
                        ),
                        "vault_enabled": bool(getattr(self, "_enabled", False)),
                    },
                    "safety_boundary": (
                        "Keep Vault token, raw Vault URL, secret paths, secret keys, "
                        "secret values, and PQC key bytes out of thinking context."
                    ),
                }
            )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "redact_vault_token": True,
                    "redact_vault_url": True,
                    "redact_secret_paths": True,
                    "redact_secret_keys": True,
                    "redact_secret_values": True,
                    "redact_pqc_key_bytes": True,
                    "preserve_secret_source_decision": True,
                },
                "safety_boundary": "Use hashes, counts, booleans, source labels, and size bands.",
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    def get_secret(self, path: str, key: str = "value") -> Optional[str]:
        """Retrieve a secret string."""
        if self._enabled and self.client:
            try:
                # Standard KV v2 path
                response = self.client.secrets.kv.v2.read_secret_version(
                    mount_point=self.mount_point,
                    path=path
                )
                value = response["data"]["data"].get(key)
                self._record_thinking(
                    "secret_retrieved",
                    "Retrieve secret from Vault safely",
                    {
                        "path_hash": _safe_hash(path),
                        "key_hash": _safe_hash(key),
                        "source": "vault",
                        "hit": value is not None,
                        "vault_enabled": True,
                    },
                )
                return value
            except (ValueError, TypeError, RuntimeError, OSError) as e:
                self._record_thinking(
                    "secret_retrieve_vault_miss",
                    "Fall back after Vault secret miss safely",
                    {
                        "path_hash": _safe_hash(path),
                        "key_hash": _safe_hash(key),
                        "source": "vault",
                        "error_type": type(e).__name__,
                        "vault_enabled": True,
                    },
                )
                logger.debug(f"Vault miss for {path}: {e}")
        
        # Fallback: Environment Variable (path converted to UPPER_SNAKE_CASE)
        env_key = f"{path.upper().replace('/', '_')}_{key.upper()}"
        value = os.getenv(env_key)
        self._record_thinking(
            "secret_retrieved",
            "Retrieve secret from environment fallback safely",
            {
                "path_hash": _safe_hash(path),
                "key_hash": _safe_hash(key),
                "env_key_hash": _safe_hash(env_key),
                "source": "environment",
                "hit": value is not None,
                "vault_enabled": self._enabled,
            },
        )
        return value

    def set_secret(self, path: str, secret_data: Dict[str, Any]) -> bool:
        """Store a secret (Vault only)."""
        if self._enabled and self.client:
            try:
                self.client.secrets.kv.v2.create_or_update_secret(
                    mount_point=self.mount_point,
                    path=path,
                    secret=secret_data
                )
                self._record_thinking(
                    "secret_stored",
                    "Store secret in Vault safely",
                    {
                        "path_hash": _safe_hash(path),
                        "secret_key_count_bucket": _safe_count_bucket(
                            len(secret_data)
                        ),
                        "secret_key_hashes": [
                            _safe_hash(key) for key in sorted(secret_data.keys())[:20]
                        ],
                        "success": True,
                    },
                )
                return True
            except (ValueError, TypeError, RuntimeError, OSError) as e:
                self._record_thinking(
                    "secret_store_failed",
                    "Record Vault secret write failure safely",
                    {
                        "path_hash": _safe_hash(path),
                        "secret_key_count_bucket": _safe_count_bucket(
                            len(secret_data)
                        ),
                        "error_type": type(e).__name__,
                    },
                )
                logger.error(f"Failed to write to Vault {path}: {e}")
        self._record_thinking(
            "secret_store_skipped",
            "Skip secret store without Vault safely",
            {
                "path_hash": _safe_hash(path),
                "secret_key_count_bucket": _safe_count_bucket(len(secret_data)),
                "vault_enabled": self._enabled,
            },
        )
        return False

    def get_pqc_keypair(self, key_id: str) -> tuple[Optional[bytes], Optional[bytes]]:
        """
        Retrieve PQC keypair (public, private) bytes.
        Expects Vault data to contain 'public_hex' and 'private_hex'.
        """
        pub_hex = self.get_secret(f"pqc/{key_id}", "public_hex")
        priv_hex = self.get_secret(f"pqc/{key_id}", "private_hex")
        
        if pub_hex and priv_hex:
            self._record_thinking(
                "pqc_keypair_retrieved",
                "Retrieve PQC keypair safely",
                {
                    "key_id_hash": _safe_hash(key_id),
                    "public_hex_length_band": _safe_number_band(len(pub_hex)),
                    "private_hex_length_band": _safe_number_band(len(priv_hex)),
                    "hit": True,
                },
            )
            return bytes.fromhex(pub_hex), bytes.fromhex(priv_hex)
        self._record_thinking(
            "pqc_keypair_retrieved",
            "Report missing PQC keypair safely",
            {
                "key_id_hash": _safe_hash(key_id),
                "public_present": bool(pub_hex),
                "private_present": bool(priv_hex),
                "hit": False,
            },
        )
        return None, None

    def store_pqc_keypair(self, key_id: str, public_key: bytes, private_key: bytes) -> bool:
        """Store PQC keypair."""
        stored = self.set_secret(f"pqc/{key_id}", {
            "public_hex": public_key.hex(),
            "private_hex": private_key.hex()
        })
        self._record_thinking(
            "pqc_keypair_stored",
            "Store PQC keypair safely",
            {
                "key_id_hash": _safe_hash(key_id),
                "public_key_length_band": _safe_number_band(len(public_key)),
                "private_key_length_band": _safe_number_band(len(private_key)),
                "success": stored,
            },
        )
        return stored

# Global instance
secrets_manager = SecretsManager()

