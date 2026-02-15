#!/usr/bin/env python3
"""
x0tta6bl4 Post-Quantum Cryptography Adapter
============================================

Адаптер для библиотеки liboqs, предоставляющий интерфейсы
для Kyber KEM и Dilithium signatures.
"""

from typing import Tuple

import oqs


class PQCAdapter:
    """
    Адаптер, инкапсулирующий OQS-реализации
    для KEM (Kyber) и цифровых подписей (Dilithium).
    """

    def __init__(self, kem_alg: str = "ML-KEM-768", sig_alg: str = "ML-DSA-65"):
        """
        Инициализирует адаптер с указанными алгоритмами.

        :param kem_alg: Название KEM-алгоритма (по умолчанию "ML-KEM-768", NIST FIPS 203 Level 3).
                       Поддерживаются legacy имена: "Kyber768" → "ML-KEM-768".
        :param sig_alg: Название алгоритма подписи (по умолчанию "ML-DSA-65", NIST FIPS 204 Level 3).
                       Поддерживаются legacy имена: "Dilithium3" → "ML-DSA-65".
        """
        # Map legacy names to NIST names
        legacy_kem_map = {
            "Kyber768": "ML-KEM-768",
            "Kyber512": "ML-KEM-512",
            "Kyber1024": "ML-KEM-1024",
        }
        legacy_sig_map = {
            "Dilithium2": "ML-DSA-44",
            "Dilithium3": "ML-DSA-65",
            "Dilithium5": "ML-DSA-87",
        }

        # Convert legacy names to NIST names
        if kem_alg in legacy_kem_map:
            kem_alg = legacy_kem_map[kem_alg]
        if sig_alg in legacy_sig_map:
            sig_alg = legacy_sig_map[sig_alg]

        # Try to validate algorithms, but handle API differences
        try:
            if hasattr(oqs, "get_enabled_kem_mechanisms"):
                mechanisms = oqs.get_enabled_kem_mechanisms()
                if kem_alg not in mechanisms:
                    # Try legacy name if NIST name not found
                    legacy_name = next(
                        (k for k, v in legacy_kem_map.items() if v == kem_alg), None
                    )
                    if legacy_name and legacy_name in mechanisms:
                        kem_alg = legacy_name
                    else:
                        raise RuntimeError(
                            f"KEM-алгоритм {kem_alg} не поддерживается библиотекой OQS."
                        )
            if hasattr(oqs, "get_enabled_sig_mechanisms"):
                mechanisms = oqs.get_enabled_sig_mechanisms()
                if sig_alg not in mechanisms:
                    # Try legacy name if NIST name not found
                    legacy_name = next(
                        (k for k, v in legacy_sig_map.items() if v == sig_alg), None
                    )
                    if legacy_name and legacy_name in mechanisms:
                        sig_alg = legacy_name
                    else:
                        raise RuntimeError(
                            f"Алгоритм подписи {sig_alg} не поддерживается библиотекой OQS."
                        )
        except (AttributeError, RuntimeError) as e:
            # If validation fails, try to use algorithms anyway
            # They will fail at runtime if not supported
            pass

        self.kem_alg = kem_alg
        self.sig_alg = sig_alg

    # --- Key Encapsulation Mechanism (KEM) - Kyber ---

    def kem_generate_keypair(self) -> Tuple[bytes, bytes]:
        """
        Генерирует пару ключей для Kyber KEM.

        :return: Кортеж (публичный_ключ, приватный_ключ).
        """
        with oqs.KeyEncapsulation(self.kem_alg) as kem:
            public_key = kem.generate_keypair()
            private_key = kem.export_secret_key()
            return public_key, private_key

    def kem_encapsulate(self, public_key: bytes) -> Tuple[bytes, bytes]:
        """
        Инкапсулирует разделяемый секрет с помощью публичного ключа Kyber.

        :param public_key: Публичный ключ получателя.
        :return: Кортеж (шифротекст, разделяемый_секрет).
        """
        with oqs.KeyEncapsulation(self.kem_alg) as kem:
            # The public key is passed to encap_secret, not the constructor.
            ciphertext, shared_secret = kem.encap_secret(public_key)
            return ciphertext, shared_secret

    def kem_decapsulate(self, private_key: bytes, ciphertext: bytes) -> bytes:
        """
        Декапсулирует разделяемый секрет с помощью приватного ключа Kyber.

        :param private_key: Приватный ключ получателя.
        :param ciphertext: Шифротекст для декапсуляции.
        :return: Разделяемый секрет.
        """
        with oqs.KeyEncapsulation(self.kem_alg, secret_key=private_key) as kem:
            shared_secret = kem.decap_secret(ciphertext)
            return shared_secret

    # --- Digital Signature Algorithm - Dilithium ---

    def sig_generate_keypair(self) -> Tuple[bytes, bytes]:
        """
        Генерирует пару ключей для Dilithium.

        :return: Кортеж (публичный_ключ_для_проверки, приватный_ключ_для_подписи).
        """
        with oqs.Signature(self.sig_alg) as sig:
            public_key = sig.generate_keypair()
            private_key = sig.export_secret_key()
            return public_key, private_key

    def sig_sign(self, private_key: bytes, message: bytes) -> bytes:
        """
        Подписывает сообщение с помощью приватного ключа Dilithium.

        :param private_key: Приватный ключ для подписи.
        :param message: Сообщение для подписи.
        :return: Цифровая подпись.
        """
        with oqs.Signature(self.sig_alg, secret_key=private_key) as sig:
            signature = sig.sign(message)
            return signature

    def sig_verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        """
        Проверяет цифровую подпись с помощью публичного ключа Dilithium.

        :param public_key: Публичный ключ для проверки.
        :param message: Исходное сообщение.
        :param signature: Цифровая подпись.
        :return: True, если подпись валидна, иначе False.
        """
        with oqs.Signature(self.sig_alg) as sig:
            try:
                is_valid = sig.verify(message, signature, public_key)
                return is_valid
            except oqs.MechanismNotSupportedError:
                return False
