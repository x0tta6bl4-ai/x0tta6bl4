#!/usr/bin/env python3
"""
x0tta6bl4 Hybrid TLS Module (ECDHE + Kyber)
=============================================

Симуляция гибридного key exchange для mesh heartbeats.
Комбинирует классическую криптографию (ECDHE) с post-quantum (Kyber).

Без зависимостей на liboqs — чистая Python с симуляцией PQC.

Использование:
    from src.security.pqc.hybrid_tls import HybridTLSContext, hybrid_handshake, hybrid_encrypt, hybrid_decrypt
"""

import os
import time
from typing import Tuple, Dict, Optional
from dataclasses import dataclass
from enum import Enum
import hashlib
import hmac
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


class KyberSimSize(Enum):
    """Симуляция Kyber KEM размеров"""
    KYBER_512 = 512      # 32 bytes shared secret
    KYBER_768 = 768      # 32 bytes shared secret
    KYBER_1024 = 1024    # 32 bytes shared secret


@dataclass
class KeyMaterial:
    """Материал ключей для гибридного обмена"""
    ecc_private_bytes: bytes      # ECDHE private key (PEM)
    ecc_public_bytes: bytes       # ECDHE public key (PEM)
    kyber_public_seed: bytes      # Simulated Kyber public key (32 bytes)
    kyber_private_seed: bytes     # Simulated Kyber private key (64 bytes)


class PQCSimulator:
    """Симулятор post-quantum KEM (Kyber-подобный)."""

    @staticmethod
    def generate_keypair(size: KyberSimSize = KyberSimSize.KYBER_768) -> Tuple[bytes, bytes]:
        private_key = os.urandom(64)
        public_key = hashlib.sha256(private_key).digest()
        return public_key, private_key

    @staticmethod
    def encapsulate(public_key: bytes) -> Tuple[bytes, bytes]:
        shared_secret = os.urandom(32)
        ciphertext = hmac.new(public_key, shared_secret, hashlib.sha256).digest()
        return ciphertext, shared_secret

    @staticmethod
    def decapsulate(private_key: bytes, ciphertext: bytes, sender_public_key: bytes) -> Optional[bytes]:
        shared_secret = hashlib.sha256(private_key + ciphertext).digest()
        return shared_secret


class HybridTLSContext:
    """Контекст для гибридного TLS (ECDHE + Kyber KEM)."""

    def __init__(self, role: str = "peer"):
        self.role = role
        self.ecc_private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
        self.ecc_public_key = self.ecc_private_key.public_key()
        self.kyber_public_key, self.kyber_private_key = PQCSimulator.generate_keypair()
        self.session_key: Optional[bytes] = None
        self.peer_ecc_public_key: Optional[ec.EllipticCurvePublicKey] = None
        self.peer_kyber_public_key: Optional[bytes] = None

    def get_public_keys_pem(self) -> Dict[str, bytes]:
        ecc_pem = self.ecc_public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return {
            "ecc_public": ecc_pem,
            "kyber_public": self.kyber_public_key.hex().encode(),
        }

    def set_peer_public_keys(self, ecc_pem: bytes, kyber_hex: bytes):
        self.peer_ecc_public_key = serialization.load_pem_public_key(ecc_pem, default_backend())
        self.peer_kyber_public_key = bytes.fromhex(kyber_hex.decode())

    def compute_session_key(self) -> bytes:
        if not self.peer_ecc_public_key or not self.peer_kyber_public_key:
            raise ValueError("Peer public keys not set")

        # Классический ECDHE секрет
        ecdhe_secret = self.ecc_private_key.exchange(ec.ECDH(), self.peer_ecc_public_key)

        # PQC-секрет: детерминированная симметричная функция от пары публичных Kyber ключей
        # Обе стороны знают self.kyber_public_key и peer_kyber_public_key,
        # поэтому получают одинаковый kyber_secret.
        pubs = [self.kyber_public_key, self.peer_kyber_public_key]
        pubs.sort()
        kyber_secret = hashlib.sha256(pubs[0] + pubs[1]).digest()

        combined = ecdhe_secret + kyber_secret
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b"x0tta6bl4-hybrid-tls-v1",
            backend=default_backend(),
        )
        session_key = hkdf.derive(combined)
        self.session_key = session_key
        return session_key


def hybrid_handshake(client_ctx: HybridTLSContext, server_ctx: HybridTLSContext) -> bytes:
    client_pub = client_ctx.get_public_keys_pem()
    server_pub = server_ctx.get_public_keys_pem()

    client_ctx.set_peer_public_keys(server_pub["ecc_public"], server_pub["kyber_public"])
    server_ctx.set_peer_public_keys(client_pub["ecc_public"], client_pub["kyber_public"])

    client_key = client_ctx.compute_session_key()
    server_key = server_ctx.compute_session_key()

    assert client_key == server_key, "Session keys do not match!"
    return client_key


def hybrid_encrypt(session_key: bytes, plaintext: bytes) -> bytes:
    nonce = hashlib.sha256(b"nonce" + session_key).digest()[:12]
    cipher = Cipher(algorithms.AES(session_key), modes.GCM(nonce), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(plaintext) + encryptor.finalize()
    tag = encryptor.tag
    return nonce + ciphertext + tag


def hybrid_decrypt(session_key: bytes, encrypted_data: bytes) -> bytes:
    nonce = encrypted_data[:12]
    ciphertext = encrypted_data[12:-16]
    tag = encrypted_data[-16:]
    cipher = Cipher(algorithms.AES(session_key), modes.GCM(nonce, tag), backend=default_backend())
    decryptor = cipher.decryptor()
    plaintext = decryptor.update(ciphertext) + decryptor.finalize()
    return plaintext


def measure_handshake_overhead() -> float:
    client = HybridTLSContext("client")
    server = HybridTLSContext("server")
    start = time.time()
    hybrid_handshake(client, server)
    elapsed = (time.time() - start) * 1000
    return elapsed
