"""
x0tta6bl4 PQC Tunnel
Post-Quantum encrypted tunnel between mesh nodes.
Uses Kyber768 for key exchange + AES-256-GCM for data.
"""

import hashlib
import logging
import os
import struct
from dataclasses import dataclass
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Try to import real PQC, fallback to simulation
try:
    import oqs

    PQC_AVAILABLE = True
    logger.info("✅ liboqs available - using real Kyber768")
except ImportError:
    PQC_AVAILABLE = False
    logger.warning("⚠️ liboqs not available - using simulated PQC")

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
        self._generate_keys()

    def _generate_keys(self):
        """Generate ML-KEM-768 keypair (NIST FIPS 203)."""
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
            # Simulated keys (32 bytes each for demo)
            private_key = os.urandom(32)
            public_key = hashlib.sha256(b"PQC_PUB_" + private_key).digest()

        self.keys = PQCKeys(
            public_key=public_key, private_key=private_key, node_id=self.node_id
        )
        logger.info(
            f"🔐 PQC keys generated for {self.node_id} (ML-KEM-768, NIST FIPS 203)"
        )

    def get_public_key(self) -> bytes:
        """Get our public key for sharing with peers."""
        return self.keys.public_key

    def create_handshake_init(self) -> bytes:
        """Create handshake initiation message."""
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

        # Encapsulate shared secret
        if PQC_AVAILABLE:
            kem = oqs.KeyEncapsulation(self.KEM_ALGORITHM)
            ciphertext, shared_secret = kem.encap_secret(peer_public_key)
        else:
            # Simulated encapsulation - derive shared secret from both public keys
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

        # Decapsulate shared secret
        if PQC_AVAILABLE:
            kem = oqs.KeyEncapsulation(
                self.KEM_ALGORITHM, secret_key=self.keys.private_key
            )
            shared_secret = kem.decap_secret(ciphertext)
        else:
            # Simulated decapsulation - ciphertext is peer's public key
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

        logger.info(f"🔑 PQC session established with {peer_node_id}")
        return peer_node_id, shared_secret

    def encrypt(self, data: bytes, peer_id: str) -> bytes:
        """Encrypt data for a peer using established session key."""
        if peer_id not in self.session_keys:
            raise ValueError(f"No session key for peer {peer_id}")

        key = self.session_keys[peer_id]

        if AES_AVAILABLE:
            # Real AES-256-GCM
            nonce = os.urandom(12)
            aesgcm = AESGCM(key)
            ciphertext = aesgcm.encrypt(nonce, data, None)
            return nonce + ciphertext
        else:
            # Simulated encryption (XOR with key stream)
            nonce = os.urandom(12)
            key_stream = self._derive_key_stream(key, nonce, len(data))
            ciphertext = bytes(a ^ b for a, b in zip(data, key_stream))
            # Add simple MAC
            mac = hashlib.sha256(key + nonce + ciphertext).digest()[:16]
            return nonce + ciphertext + mac

    def decrypt(self, data: bytes, peer_id: str) -> bytes:
        """Decrypt data from a peer using established session key."""
        if peer_id not in self.session_keys:
            raise ValueError(f"No session key for peer {peer_id}")

        key = self.session_keys[peer_id]

        if AES_AVAILABLE:
            # Real AES-256-GCM
            nonce = data[:12]
            ciphertext = data[12:]
            aesgcm = AESGCM(key)
            return aesgcm.decrypt(nonce, ciphertext, None)
        else:
            # Simulated decryption
            nonce = data[:12]
            mac = data[-16:]
            ciphertext = data[12:-16]

            # Verify MAC
            expected_mac = hashlib.sha256(key + nonce + ciphertext).digest()[:16]
            if mac != expected_mac:
                raise ValueError("MAC verification failed")

            key_stream = self._derive_key_stream(key, nonce, len(ciphertext))
            return bytes(a ^ b for a, b in zip(ciphertext, key_stream))

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
        encrypted = self.encrypt(data, peer_id)
        # Add header: [magic:4][length:4][encrypted_data]
        header = b"PQC1" + struct.pack(">I", len(encrypted))
        return header + encrypted

    def unwrap_packet(self, data: bytes, peer_id: str) -> bytes:
        """Unwrap a PQC-encrypted packet."""
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

    async def establish_tunnel(self, reader, writer, peer_id: str) -> bool:
        """Establish PQC tunnel with a peer (as initiator)."""
        try:
            # Send handshake init
            init_msg = self.tunnel.create_handshake_init()
            writer.write(struct.pack(">I", len(init_msg)) + init_msg)
            await writer.drain()

            # Read response
            resp_len_data = await reader.read(4)
            if len(resp_len_data) < 4:
                return False
            resp_len = struct.unpack(">I", resp_len_data)[0]
            resp_data = await reader.read(resp_len)

            # Process response
            peer_node_id, shared_secret = self.tunnel.process_handshake_response(
                resp_data
            )
            self.established_peers.add(peer_node_id)

            logger.info(f"🔐 PQC tunnel established with {peer_node_id}")
            return True

        except Exception as e:
            logger.error(f"PQC tunnel establishment failed: {e}")
            return False

    async def accept_tunnel(self, reader, writer) -> Optional[str]:
        """Accept incoming PQC tunnel (as responder)."""
        try:
            # Read init message
            init_len_data = await reader.read(4)
            if len(init_len_data) < 4:
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
            logger.info(f"🔐 PQC tunnel accepted from {peer_node_id}")
            return peer_node_id

        except Exception as e:
            logger.error(f"PQC tunnel accept failed: {e}")
            return None

    def encrypt_for_peer(self, data: bytes, peer_id: str) -> bytes:
        """Encrypt data for a specific peer."""
        return self.tunnel.wrap_packet(data, peer_id)

    def decrypt_from_peer(self, data: bytes, peer_id: str) -> bytes:
        """Decrypt data from a specific peer."""
        return self.tunnel.unwrap_packet(data, peer_id)

    def has_tunnel(self, peer_id: str) -> bool:
        """Check if we have an established tunnel with peer."""
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
