"""
x0tta6bl4 PQC Tunnel
Post-Quantum encrypted tunnel between mesh nodes.
Uses Kyber768 for key exchange + AES-256-GCM for data.
"""
from __future__ import annotations

import hashlib
import logging
import os
import struct
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from src.core.thinking.agent_thinking import AgentThinkingCoach

logger = logging.getLogger(__name__)
SIMULATED_PQC_ENV = "X0TTA6BL4_ALLOW_SIMULATED_PQC"
_TRUE_VALUES = {"1", "true", "yes", "on"}


def _simulated_pqc_allowed() -> bool:
    return os.getenv(SIMULATED_PQC_ENV, "").strip().lower() in _TRUE_VALUES


def _require_simulated_pqc_allowed() -> None:
    if not _simulated_pqc_allowed():
        raise RuntimeError(
            "liboqs is required for PQC tunnel key exchange. "
            f"Set {SIMULATED_PQC_ENV}=true only for local tests."
        )

# Try to import real PQC, fallback to simulation
try:
    import oqs

    PQC_AVAILABLE = True
    logger.info("✅ liboqs available - using real Kyber768")
except ImportError:
    PQC_AVAILABLE = False
    logger.warning("⚠️ liboqs not available - simulated PQC requires explicit opt-in")

# Try to import AES
try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF

    AES_AVAILABLE = True
except ImportError:
    AES_AVAILABLE = False


@dataclass
class PQCKeys:
    """PQC keypair for a node."""

    public_key: bytes
    private_key: bytes
    node_id: str


class PQCTunnel:
    """
    Post-Quantum Cryptographic tunnel for inter-node communication.

    Protocol:
    1. Initiator sends their public key
    2. Responder encapsulates shared secret with initiator's public key
    3. Both derive AES-256 key from shared secret
    4. All subsequent data is AES-256-GCM encrypted
    """

    KEM_ALGORITHM = "ML-KEM-768"  # NIST FIPS 203 Level 3 (legacy: "Kyber768" supported)

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.keys: Optional[PQCKeys] = None
        self.session_keys: dict = {}  # peer_id -> shared_secret
        self.thinking_coach = AgentThinkingCoach(
            agent_id=_agent_id("pqc-tunnel", node_id),
            role="security",
            capabilities=("zero-trust", "ops"),
            extra_techniques=("stride_threat_modeling",),
        )
        self.last_thinking_context: Dict[str, Any] = {}
        self._generate_keys()

    def _prepare_pqc_thinking_context(
        self,
        *,
        task_type: str,
        goal: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        context: Dict[str, Any] = {
            "task_type": task_type,
            "goal": goal,
            "kem_algorithm": self.KEM_ALGORITHM,
            "pqc_available": bool(PQC_AVAILABLE),
            "aes_available": bool(AES_AVAILABLE),
            "simulated_pqc_allowed": _simulated_pqc_allowed(),
            "node_id_hash": _hash_value(self.node_id),
            "session_count": len(self.session_keys),
            "peer_hashes": [_hash_value(peer_id) for peer_id in self.session_keys],
            "constraints": {
                "redact_private_keys": True,
                "redact_public_keys": True,
                "redact_shared_secrets": True,
                "redact_payload_bytes": True,
                "redact_raw_node_ids": True,
            },
            "safety_boundary": PQC_TUNNEL_CLAIM_BOUNDARY,
        }
        if extra:
            context.update(extra)
        self.last_thinking_context = self.thinking_coach.prepare_task(context)
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
            "claim_boundary": PQC_TUNNEL_CLAIM_BOUNDARY,
        }

    def _generate_keys(self):
        """Generate ML-KEM-768 keypair (NIST FIPS 203)."""
        self._prepare_pqc_thinking_context(
            task_type="pqc_generate_keys",
            goal="Generate local PQC key material without exposing key bytes.",
        )
        if PQC_AVAILABLE:
            # Try NIST name first, fallback to legacy if needed
            try:
                kem = oqs.KeyEncapsulation(self.KEM_ALGORITHM)
            except Exception:
                # Fallback to legacy name if NIST name not supported
                kem = oqs.KeyEncapsulation("Kyber768")
            public_key = kem.generate_keypair()
            private_key = kem.export_secret_key()
        else:
            _require_simulated_pqc_allowed()
            logger.warning("Using simulated PQC keys for local test mode only")
            private_key = os.urandom(32)
            public_key = hashlib.sha256(b"PQC_PUB_" + private_key).digest()

        self.keys = PQCKeys(
            public_key=public_key, private_key=private_key, node_id=self.node_id
        )
        self._prepare_pqc_thinking_context(
            task_type="pqc_keys_generated",
            goal="Record local PQC key generation metadata without key bytes.",
            extra={
                "public_key_length": len(public_key),
                "private_key_length": len(private_key),
            },
        )
        logger.info(
            f"🔐 PQC keys generated for {self.node_id} (ML-KEM-768, NIST FIPS 203)"
        )

    def get_public_key(self) -> bytes:
        """Get our public key for sharing with peers."""
        self._prepare_pqc_thinking_context(
            task_type="pqc_get_public_key",
            goal="Return public key bytes while keeping thinking metadata redacted.",
            extra={"public_key_length": len(self.keys.public_key)},
        )
        return self.keys.public_key

    def create_handshake_init(self) -> bytes:
        """Create handshake initiation message."""
        self._prepare_pqc_thinking_context(
            task_type="pqc_handshake_init_create",
            goal="Create handshake init without exposing node id or public key bytes.",
            extra={"public_key_length": len(self.keys.public_key)},
        )
        # Format: [node_id_len:2][node_id][public_key]
        node_id_bytes = self.node_id.encode()
        msg = struct.pack(">H", len(node_id_bytes))
        msg += node_id_bytes
        msg += self.keys.public_key
        return msg

    def process_handshake_init(self, data: bytes) -> Tuple[str, bytes, bytes]:
        """
        Process incoming handshake init, return response.

        Returns: (peer_node_id, shared_secret, response_message)
        """
        # Parse init message
        node_id_len = struct.unpack(">H", data[:2])[0]
        peer_node_id = data[2 : 2 + node_id_len].decode()
        peer_public_key = data[2 + node_id_len :]
        self._prepare_pqc_thinking_context(
            task_type="pqc_handshake_init_process",
            goal="Process peer handshake init without exposing peer id or key bytes.",
            extra={
                "peer_id_hash": _hash_value(peer_node_id),
                "message_size_bucket": _byte_count_bucket(len(data)),
                "peer_public_key_length": len(peer_public_key),
            },
        )

        # Encapsulate shared secret
        if PQC_AVAILABLE:
            kem = oqs.KeyEncapsulation(self.KEM_ALGORITHM)
            ciphertext, shared_secret = kem.encap_secret(peer_public_key)
        else:
            _require_simulated_pqc_allowed()
            # Local-test encapsulation derives a shared secret from both public keys.
            # The ciphertext contains our public key so peer can derive same secret
            ciphertext = self.keys.public_key
            shared_secret = hashlib.sha256(
                b"SHARED_" + peer_public_key + self.keys.public_key
            ).digest()

        # Create response: [node_id_len:2][node_id][ciphertext]
        node_id_bytes = self.node_id.encode()
        response = struct.pack(">H", len(node_id_bytes))
        # Derive AES key from shared secret using HKDF
        if AES_AVAILABLE:
            derived_key = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=None,
                info=b"x0tta6bl4-pqc-tunnel-v1",
            ).derive(shared_secret)
        else:
            derived_key = shared_secret

        # Store session key
        self.session_keys[peer_node_id] = derived_key
        self._prepare_pqc_thinking_context(
            task_type="pqc_handshake_init_processed",
            goal="Record responder session establishment metadata without shared secret.",
            extra={
                "peer_id_hash": _hash_value(peer_node_id),
                "ciphertext_length": len(ciphertext),
                "derived_key_length": len(derived_key),
            },
        )

        response += node_id_bytes
        response += ciphertext

        logger.info(f"🔑 PQC handshake with {peer_node_id} - shared secret established")
        return peer_node_id, shared_secret, response

    def process_handshake_response(self, data: bytes) -> Tuple[str, bytes]:
        """
        Process handshake response, derive shared secret.

        Returns: (peer_node_id, shared_secret)
        """
        # Parse response
        node_id_len = struct.unpack(">H", data[:2])[0]
        peer_node_id = data[2 : 2 + node_id_len].decode()
        ciphertext = data[2 + node_id_len :]
        self._prepare_pqc_thinking_context(
            task_type="pqc_handshake_response_process",
            goal="Process handshake response without exposing peer id or ciphertext bytes.",
            extra={
                "peer_id_hash": _hash_value(peer_node_id),
                "message_size_bucket": _byte_count_bucket(len(data)),
                "ciphertext_length": len(ciphertext),
            },
        )

        # Decapsulate shared secret
        if PQC_AVAILABLE:
            kem = oqs.KeyEncapsulation(
                self.KEM_ALGORITHM, secret_key=self.keys.private_key
            )
            shared_secret = kem.decap_secret(ciphertext)
        else:
            _require_simulated_pqc_allowed()
            # Local-test decapsulation expects ciphertext to carry the peer public key.
            peer_public_key = ciphertext
            shared_secret = hashlib.sha256(
                b"SHARED_" + self.keys.public_key + peer_public_key
            ).digest()

        # Derive AES key from shared secret using HKDF
        if AES_AVAILABLE:
            derived_key = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=None,
                info=b"x0tta6bl4-pqc-tunnel-v1",
            ).derive(shared_secret)
        else:
            derived_key = shared_secret

        # Store session key
        self.session_keys[peer_node_id] = derived_key
        self._prepare_pqc_thinking_context(
            task_type="pqc_handshake_response_processed",
            goal="Record initiator session establishment metadata without shared secret.",
            extra={
                "peer_id_hash": _hash_value(peer_node_id),
                "derived_key_length": len(derived_key),
            },
        )

        logger.info(f"🔑 PQC session established with {peer_node_id}")
        return peer_node_id, shared_secret

    def encrypt(self, data: bytes, peer_id: str) -> bytes:
        """Encrypt data for a peer using established session key."""
        self._prepare_pqc_thinking_context(
            task_type="pqc_encrypt",
            goal="Encrypt payload for an established peer without exposing payload or key bytes.",
            extra={
                "peer_id_hash": _hash_value(peer_id),
                "payload_size_bucket": _byte_count_bucket(len(data)),
                "session_present": peer_id in self.session_keys,
            },
        )
        if peer_id not in self.session_keys:
            raise ValueError(f"No session key for peer {peer_id}")

        key = self.session_keys[peer_id]

        if not AES_AVAILABLE:
            raise RuntimeError(
                "cryptography package is required for encryption. "
                "Install it with: pip install cryptography"
            )

        nonce = os.urandom(12)
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, data, None)
        return nonce + ciphertext

    def decrypt(self, data: bytes, peer_id: str) -> bytes:
        """Decrypt data from a peer using established session key."""
        self._prepare_pqc_thinking_context(
            task_type="pqc_decrypt",
            goal="Decrypt payload from an established peer without exposing ciphertext or key bytes.",
            extra={
                "peer_id_hash": _hash_value(peer_id),
                "payload_size_bucket": _byte_count_bucket(len(data)),
                "session_present": peer_id in self.session_keys,
            },
        )
        if peer_id not in self.session_keys:
            raise ValueError(f"No session key for peer {peer_id}")

        key = self.session_keys[peer_id]

        if not AES_AVAILABLE:
            raise RuntimeError(
                "cryptography package is required for decryption. "
                "Install it with: pip install cryptography"
            )

        nonce = data[:12]
        ciphertext = data[12:]
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ciphertext, None)

    def _derive_key_stream(self, key: bytes, nonce: bytes, length: int) -> bytes:
        """Derive key stream for simulated encryption."""
        stream = b""
        counter = 0
        while len(stream) < length:
            block = hashlib.sha256(key + nonce + counter.to_bytes(4, "big")).digest()
            stream += block
            counter += 1
        return stream[:length]

    def wrap_packet(self, data: bytes, peer_id: str) -> bytes:
        """Wrap a packet with PQC encryption for transmission."""
        self._prepare_pqc_thinking_context(
            task_type="pqc_wrap_packet",
            goal="Wrap encrypted packet without exposing plaintext payload.",
            extra={
                "peer_id_hash": _hash_value(peer_id),
                "payload_size_bucket": _byte_count_bucket(len(data)),
            },
        )
        encrypted = self.encrypt(data, peer_id)
        # Add header: [magic:4][length:4][encrypted_data]
        header = b"PQC1" + struct.pack(">I", len(encrypted))
        return header + encrypted

    def unwrap_packet(self, data: bytes, peer_id: str) -> bytes:
        """Unwrap a PQC-encrypted packet."""
        self._prepare_pqc_thinking_context(
            task_type="pqc_unwrap_packet",
            goal="Unwrap encrypted packet without exposing ciphertext payload.",
            extra={
                "peer_id_hash": _hash_value(peer_id),
                "packet_size_bucket": _byte_count_bucket(len(data)),
                "magic_valid": data[:4] == b"PQC1",
            },
        )
        if data[:4] != b"PQC1":
            raise ValueError("Invalid PQC packet magic")
        length = struct.unpack(">I", data[4:8])[0]
        encrypted = data[8 : 8 + length]
        return self.decrypt(encrypted, peer_id)


class PQCTunnelManager:
    """Manages PQC tunnels to multiple peers."""

    def __init__(self, node_id: str):
        self.tunnel = PQCTunnel(node_id)
        self.established_peers: set = set()
        self.thinking_coach = AgentThinkingCoach(
            agent_id=_agent_id("pqc-tunnel-manager", node_id),
            role="security",
            capabilities=("zero-trust", "ops"),
            extra_techniques=("mape_k", "stride_threat_modeling"),
        )
        self.last_thinking_context: Dict[str, Any] = {}

    def _prepare_manager_thinking_context(
        self,
        *,
        task_type: str,
        goal: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        context: Dict[str, Any] = {
            "task_type": task_type,
            "goal": goal,
            "node_id_hash": _hash_value(self.tunnel.node_id),
            "established_peer_count": len(self.established_peers),
            "established_peer_hashes": [
                _hash_value(peer_id) for peer_id in self.established_peers
            ],
            "constraints": {
                "redact_peer_ids": True,
                "redact_keys": True,
                "redact_payload_bytes": True,
                "fail_closed_on_handshake_error": True,
            },
            "safety_boundary": PQC_TUNNEL_CLAIM_BOUNDARY,
        }
        if extra:
            context.update(extra)
        self.last_thinking_context = self.thinking_coach.prepare_task(context)
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
            "tunnel": self.tunnel.get_thinking_status(),
            "claim_boundary": PQC_TUNNEL_CLAIM_BOUNDARY,
        }

    async def establish_tunnel(self, reader, writer, peer_id: str) -> bool:
        """Establish PQC tunnel with a peer (as initiator)."""
        self._prepare_manager_thinking_context(
            task_type="pqc_manager_establish_tunnel",
            goal="Establish an outbound PQC tunnel without exposing peer id.",
            extra={"peer_id_hash": _hash_value(peer_id)},
        )
        try:
            # Send handshake init
            init_msg = self.tunnel.create_handshake_init()
            writer.write(struct.pack(">I", len(init_msg)) + init_msg)
            await writer.drain()

            # Read response
            resp_len_data = await reader.read(4)
            if len(resp_len_data) < 4:
                self._prepare_manager_thinking_context(
                    task_type="pqc_manager_establish_failed",
                    goal="Record outbound PQC tunnel establishment failure.",
                    extra={
                        "peer_id_hash": _hash_value(peer_id),
                        "error_type": "ShortHandshakeResponse",
                    },
                )
                return False
            resp_len = struct.unpack(">I", resp_len_data)[0]
            resp_data = await reader.read(resp_len)

            # Process response
            peer_node_id, shared_secret = self.tunnel.process_handshake_response(
                resp_data
            )
            self.established_peers.add(peer_node_id)
            self._prepare_manager_thinking_context(
                task_type="pqc_manager_tunnel_established",
                goal="Record outbound PQC tunnel establishment metadata.",
                extra={"peer_id_hash": _hash_value(peer_node_id)},
            )

            logger.info(f"🔐 PQC tunnel established with {peer_node_id}")
            return True

        except Exception as e:
            logger.error(f"PQC tunnel establishment failed: {e}")
            self._prepare_manager_thinking_context(
                task_type="pqc_manager_establish_failed",
                goal="Record outbound PQC tunnel establishment failure.",
                extra={
                    "peer_id_hash": _hash_value(peer_id),
                    "error_type": type(e).__name__,
                },
            )
            return False

    async def accept_tunnel(self, reader, writer) -> Optional[str]:
        """Accept incoming PQC tunnel (as responder)."""
        self._prepare_manager_thinking_context(
            task_type="pqc_manager_accept_tunnel",
            goal="Accept an inbound PQC tunnel without exposing peer id.",
        )
        try:
            # Read init message
            init_len_data = await reader.read(4)
            if len(init_len_data) < 4:
                self._prepare_manager_thinking_context(
                    task_type="pqc_manager_accept_failed",
                    goal="Record inbound PQC tunnel accept failure.",
                    extra={"error_type": "ShortHandshakeInit"},
                )
                return None
            init_len = struct.unpack(">I", init_len_data)[0]
            init_data = await reader.read(init_len)

            # Process init and create response
            peer_node_id, shared_secret, response = self.tunnel.process_handshake_init(
                init_data
            )

            # Send response
            writer.write(struct.pack(">I", len(response)) + response)
            await writer.drain()

            self.established_peers.add(peer_node_id)
            self._prepare_manager_thinking_context(
                task_type="pqc_manager_tunnel_accepted",
                goal="Record inbound PQC tunnel establishment metadata.",
                extra={"peer_id_hash": _hash_value(peer_node_id)},
            )
            logger.info(f"🔐 PQC tunnel accepted from {peer_node_id}")
            return peer_node_id

        except Exception as e:
            logger.error(f"PQC tunnel accept failed: {e}")
            self._prepare_manager_thinking_context(
                task_type="pqc_manager_accept_failed",
                goal="Record inbound PQC tunnel accept failure.",
                extra={"error_type": type(e).__name__},
            )
            return None

    def encrypt_for_peer(self, data: bytes, peer_id: str) -> bytes:
        """Encrypt data for a specific peer."""
        self._prepare_manager_thinking_context(
            task_type="pqc_manager_encrypt_for_peer",
            goal="Encrypt manager payload for a peer without exposing payload or peer id.",
            extra={
                "peer_id_hash": _hash_value(peer_id),
                "payload_size_bucket": _byte_count_bucket(len(data)),
            },
        )
        return self.tunnel.wrap_packet(data, peer_id)

    def decrypt_from_peer(self, data: bytes, peer_id: str) -> bytes:
        """Decrypt data from a specific peer."""
        self._prepare_manager_thinking_context(
            task_type="pqc_manager_decrypt_from_peer",
            goal="Decrypt manager payload from a peer without exposing payload or peer id.",
            extra={
                "peer_id_hash": _hash_value(peer_id),
                "packet_size_bucket": _byte_count_bucket(len(data)),
            },
        )
        return self.tunnel.unwrap_packet(data, peer_id)

    def has_tunnel(self, peer_id: str) -> bool:
        """Check if we have an established tunnel with peer."""
        self._prepare_manager_thinking_context(
            task_type="pqc_manager_has_tunnel",
            goal="Check local PQC tunnel presence without exposing peer id.",
            extra={
                "peer_id_hash": _hash_value(peer_id),
                "present": peer_id in self.established_peers,
            },
        )
        return peer_id in self.established_peers


# Quick test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Create two nodes
    node_a = PQCTunnel("node-A")
    node_b = PQCTunnel("node-B")

    # Simulate handshake
    init_msg = node_a.create_handshake_init()
    peer_id, secret_b, response = node_b.process_handshake_init(init_msg)
    peer_id_a, secret_a = node_a.process_handshake_response(response)

    print(f"Secrets match: {secret_a == secret_b}")

    # Test encryption
    original = b"Hello, Quantum World! This is a test message."
    encrypted = node_a.encrypt(original, "node-B")
    decrypted = node_b.decrypt(encrypted, "node-A")

    print(f"Encryption works: {original == decrypted}")
    print(f"Original size: {len(original)}, Encrypted size: {len(encrypted)}")

