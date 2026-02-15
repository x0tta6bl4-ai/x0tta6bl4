#!/usr/bin/env python3
"""
x0tta6bl4 Hybrid TLS Module (ECDHE + Kyber)
=============================================

Гибридный key exchange для mesh heartbeats, использующий реальные PQC-алгоритмы.
Комбинирует классическую криптографию (ECDHE) с post-quantum (Kyber и Dilithium).

Использование:
    from src.security.pqc.hybrid_tls import HybridTLSContext, hybrid_handshake, hybrid_encrypt, hybrid_decrypt
"""

import os
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .pqc_adapter import PQCAdapter


@dataclass
class KeyMaterial:
    """Материал ключей для гибридного обмена"""

    ecc_private_bytes: bytes
    ecc_public_bytes: bytes
    kem_public_key: bytes
    kem_private_key: bytes
    sig_public_key: bytes
    sig_private_key: bytes


class HybridTLSContext:
    """Контекст для гибридного TLS (ECDHE + ML-KEM-768 KEM + ML-DSA-65 Signature, NIST FIPS 203/204)."""

    def __init__(
        self,
        role: str = "peer",
        kem_alg: str = "ML-KEM-768",
        sig_alg: str = "ML-DSA-65",
    ):
        self.role = role
        self.pqc_adapter = PQCAdapter(kem_alg, sig_alg)

        # Классические ключи (ECC)
        self.ecc_private_key = ec.generate_private_key(
            ec.SECP256R1(), default_backend()
        )
        self.ecc_public_key = self.ecc_private_key.public_key()

        # Ключи для KEM (Kyber)
        self.kem_public_key, self.kem_private_key = (
            self.pqc_adapter.kem_generate_keypair()
        )

        # Ключи для подписи (Dilithium)
        self.sig_public_key, self.sig_private_key = (
            self.pqc_adapter.sig_generate_keypair()
        )

        self.session_key: Optional[bytes] = None
        self.peer_ecc_public_key: Optional[ec.EllipticCurvePublicKey] = None
        self.peer_kem_public_key: Optional[bytes] = None
        self.peer_sig_public_key: Optional[bytes] = None

    def get_public_bundle(self) -> Dict[str, bytes]:
        """Возвращает бандл с публичными ключами в формате PEM/hex."""
        ecc_pem = self.ecc_public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return {
            "ecc_public": ecc_pem,
            "kem_public": self.kem_public_key,
            "sig_public": self.sig_public_key,
        }

    def set_peer_public_bundle(self, bundle: Dict[str, bytes]):
        """Устанавливает публичные ключи пира из бандла."""
        self.peer_ecc_public_key = serialization.load_pem_public_key(
            bundle["ecc_public"], default_backend()
        )
        self.peer_kem_public_key = bundle["kem_public"]
        self.peer_sig_public_key = bundle["sig_public"]

    def compute_session_key(self, encapsulation: Optional[bytes] = None) -> bytes:
        """
        Вычисляет сессионный ключ.
        - Сервер использует инкапсуляцию от клиента.
        - Клиент создает инкапсуляцию.
        """
        if not self.peer_ecc_public_key or not self.peer_kem_public_key:
            raise ValueError("Peer public keys not set")

        # 1. Классический ECDHE секрет
        ecdhe_secret = self.ecc_private_key.exchange(
            ec.ECDH(), self.peer_ecc_public_key
        )

        # 2. Post-quantum Kyber KEM секрет
        if self.role == "server" and encapsulation:
            # Сервер декапсулирует секрет, полученный от клиента
            kyber_secret = self.pqc_adapter.kem_decapsulate(
                self.kem_private_key, encapsulation
            )
        else:
            # Клиент инкапсулирует секрет для сервера
            _, kyber_secret = self.pqc_adapter.kem_encapsulate(self.peer_kem_public_key)

        # 3. Комбинирование секретов через HKDF
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


def hybrid_handshake(
    client_ctx: HybridTLSContext, server_ctx: HybridTLSContext
) -> Tuple[bytes, bytes]:
    """Выполняет полное гибридное рукопожатие."""
    client_pub_bundle = client_ctx.get_public_bundle()
    server_pub_bundle = server_ctx.get_public_bundle()

    # Обмен публичными ключами
    client_ctx.set_peer_public_bundle(server_pub_bundle)
    server_ctx.set_peer_public_bundle(client_pub_bundle)

    # Клиент инкапсулирует секрет для сервера
    ciphertext, client_kyber_secret = client_ctx.pqc_adapter.kem_encapsulate(
        server_ctx.kem_public_key
    )

    # Клиент вычисляет свой сессионный ключ
    client_ecdhe = client_ctx.ecc_private_key.exchange(
        ec.ECDH(), server_ctx.ecc_public_key
    )
    client_combined = client_ecdhe + client_kyber_secret
    client_session_key = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=None, info=b"x0tta6bl4-hybrid-tls-v1"
    ).derive(client_combined)
    client_ctx.session_key = client_session_key

    # Сервер вычисляет свой сессионный ключ
    server_ecdhe = server_ctx.ecc_private_key.exchange(
        ec.ECDH(), client_ctx.ecc_public_key
    )
    server_kyber_secret = server_ctx.pqc_adapter.kem_decapsulate(
        server_ctx.kem_private_key, ciphertext
    )
    server_combined = server_ecdhe + server_kyber_secret
    server_session_key = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=None, info=b"x0tta6bl4-hybrid-tls-v1"
    ).derive(server_combined)
    server_ctx.session_key = server_session_key

    assert client_session_key == server_session_key, "Session keys do not match!"
    return client_session_key, server_session_key


def hybrid_sign(ctx: HybridTLSContext, message: bytes) -> bytes:
    """Подписывает сообщение с помощью ключа подписи контекста."""
    return ctx.pqc_adapter.sig_sign(ctx.sig_private_key, message)


def hybrid_verify(ctx: HybridTLSContext, message: bytes, signature: bytes) -> bool:
    """Проверяет подпись сообщения, используя публичный ключ подписи пира."""
    if not ctx.peer_sig_public_key:
        raise ValueError("Peer signature public key not set")
    return ctx.pqc_adapter.sig_verify(ctx.peer_sig_public_key, message, signature)


def hybrid_encrypt(session_key: bytes, plaintext: bytes) -> bytes:
    nonce = os.urandom(12)
    cipher = Cipher(
        algorithms.AES(session_key), modes.GCM(nonce), backend=default_backend()
    )
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(plaintext) + encryptor.finalize()
    return nonce + ciphertext + encryptor.tag


def hybrid_decrypt(session_key: bytes, encrypted_data: bytes) -> bytes:
    nonce = encrypted_data[:12]
    tag = encrypted_data[-16:]
    ciphertext = encrypted_data[12:-16]
    cipher = Cipher(
        algorithms.AES(session_key), modes.GCM(nonce, tag), backend=default_backend()
    )
    decryptor = cipher.decryptor()
    return decryptor.update(ciphertext) + decryptor.finalize()


def measure_handshake_overhead() -> float:
    """Измеряет производительность полного гибридного рукопожатия."""
    start = time.time()
    client = HybridTLSContext("client")
    server = HybridTLSContext("server")
    hybrid_handshake(client, server)
    elapsed = (time.time() - start) * 1000
    return elapsed
