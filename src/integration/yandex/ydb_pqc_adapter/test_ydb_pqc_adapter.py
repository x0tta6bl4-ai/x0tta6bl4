from __future__ import annotations
# Copyright 2024 x0tta6bl4 contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Тесты для YDB PQC адаптера.
"""

import hashlib
import secrets
import socket
import struct
import threading
import time
from unittest import TestCase, mock

from src.integration.yandex.ydb_pqc_adapter import (
    ConnectionStats,
    HandshakeResult,
    HandshakeState,
    PQCConfig,
    PQCKeyExchange,
    PQCMode,
    PQCSessionCache,
    YDBPQCAdapter,
)


class TestPQCConfig(TestCase):
    """Тесты конфигурации PQC."""

    def test_default_config(self) -> None:
        """Проверка конфигурации по умолчанию."""
        with mock.patch(
            "src.integration.yandex.ydb_pqc_adapter.HAS_LIBOQS", True
        ):
            config = PQCConfig()
            self.assertEqual(config.mode, PQCMode.HYBRID_X25519_ML_KEM)
            self.assertEqual(config.kem_algorithm, "ML-KEM-768")
            self.assertEqual(config.signature_algorithm, "ML-DSA-65")
            self.assertEqual(config.handshake_timeout, 30.0)
            self.assertEqual(config.cache_ttl, 3600)
            self.assertEqual(config.max_cache_size, 1024)
            self.assertTrue(config.enable_attestation)
            self.assertTrue(config.require_peer_attestation)

    def test_custom_config(self) -> None:
        """Проверка пользовательской конфигурации."""
        with mock.patch(
            "src.integration.yandex.ydb_pqc_adapter.HAS_LIBOQS", True
        ):
            config = PQCConfig(
                mode=PQCMode.PURE_ML_KEM,
                handshake_timeout=10.0,
                cache_ttl=1800,
                max_cache_size=512,
                enable_attestation=False,
            )
            self.assertEqual(config.mode, PQCMode.PURE_ML_KEM)
            self.assertEqual(config.handshake_timeout, 10.0)
            self.assertEqual(config.cache_ttl, 1800)
            self.assertEqual(config.max_cache_size, 512)
            self.assertFalse(config.enable_attestation)


class TestPQCSessionCache(TestCase):
    """Тесты кэша сессий."""

    def setUp(self) -> None:
        """Настройка тестов."""
        self.cache = PQCSessionCache(max_size=3, ttl=60)

    def test_put_and_get(self) -> None:
        """Тест сохранения и получения из кэша."""
        secret = secrets.token_bytes(32)
        self.cache.put("peer-1", secret)

        result = self.cache.get("peer-1")
        self.assertEqual(result, secret)

    def test_cache_miss(self) -> None:
        """Тест промаха кэша."""
        result = self.cache.get("nonexistent")
        self.assertIsNone(result)

    def test_cache_ttl(self) -> None:
        """Тест истечения TTL кэша."""
        cache = PQCSessionCache(max_size=3, ttl=0)
        secret = secrets.token_bytes(32)
        cache.put("peer-1", secret)

        time.sleep(0.1)
        result = cache.get("peer-1")
        self.assertIsNone(result)

    def test_cache_eviction(self) -> None:
        """Тест вытеснения из кэша при переполнении."""
        for i in range(5):
            self.cache.put(f"peer-{i}", secrets.token_bytes(32))

        self.assertLessEqual(self.cache.size, 3)

    def test_cache_clear(self) -> None:
        """Тест очистки кэша."""
        self.cache.put("peer-1", secrets.token_bytes(32))
        self.cache.clear()

        result = self.cache.get("peer-1")
        self.assertIsNone(result)
        self.assertEqual(self.cache.size, 0)

    def test_cache_size(self) -> None:
        """Тест размера кэша."""
        self.assertEqual(self.cache.size, 0)

        self.cache.put("peer-1", secrets.token_bytes(32))
        self.assertEqual(self.cache.size, 1)

        self.cache.put("peer-2", secrets.token_bytes(32))
        self.assertEqual(self.cache.size, 2)


class TestPQCKeyExchange(TestCase):
    """Тесты обмена ключами PQC."""

    def setUp(self) -> None:
        """Настройка тестов."""
        self.config = PQCConfig(
            mode=PQCMode.HYBRID_X25519_ML_KEM
        )
        self.key_exchange = PQCKeyExchange(self.config)

    def test_generate_keypair(self) -> None:
        """Тест генерации ключевой пары."""
        public_key, secret_key = self.key_exchange.generate_keypair()

        self.assertIsInstance(public_key, bytes)
        self.assertIsInstance(secret_key, bytes)
        self.assertGreater(len(public_key), 0)
        self.assertGreater(len(secret_key), 0)

    def test_generate_signature_keypair(self) -> None:
        """Тест генерации ключевой пары подписей."""
        public_key, secret_key = (
            self.key_exchange.generate_signature_keypair()
        )

        self.assertIsInstance(public_key, bytes)
        self.assertIsInstance(secret_key, bytes)
        self.assertGreater(len(public_key), 0)
        self.assertGreater(len(secret_key), 0)

    def test_encapsulate_decapsulate(self) -> None:
        """Тест инкапсуляции и декапсуляции."""
        receiver = PQCKeyExchange(self.config)
        receiver_pub, _ = receiver.generate_keypair()

        ciphertext, shared_secret = self.key_exchange.encapsulate(
            receiver_pub
        )

        self.assertIsInstance(ciphertext, bytes)
        self.assertIsInstance(shared_secret, bytes)
        self.assertGreater(len(ciphertext), 0)
        self.assertGreater(len(shared_secret), 0)

    def test_sign_verify(self) -> None:
        """Тест подписи и верификации."""
        message = b"test message for signing"
        public_key, secret_key = (
            self.key_exchange.generate_signature_keypair()
        )

        signature = self.key_exchange.sign(message, secret_key)

        self.assertIsInstance(signature, bytes)
        self.assertGreater(len(signature), 0)

        is_valid = self.key_exchange.verify(
            message, signature, public_key
        )
        self.assertTrue(is_valid)

    def test_verify_invalid_signature(self) -> None:
        """Тест верификации невалидной подписи."""
        message = b"test message"
        public_key, secret_key = (
            self.key_exchange.generate_signature_keypair()
        )

        signature = self.key_exchange.sign(message, secret_key)

        invalid_message = b"different message"
        is_valid = self.key_exchange.verify(
            invalid_message, signature, public_key
        )
        self.assertFalse(is_valid)


class TestYDBPQCAdapter(TestCase):
    """Тесты YDB PQC адаптера."""

    def setUp(self) -> None:
        """Настройка тестов."""
        self.config = PQCConfig(
            mode=PQCMode.HYBRID_X25519_ML_KEM,
            enable_attestation=False,
            require_peer_attestation=False,
        )
        self.adapter = YDBPQCAdapter(config=self.config)

    def test_initialization(self) -> None:
        """Тест инициализации адаптера."""
        self.assertIsNotNone(self.adapter)
        self.assertEqual(
            self.adapter._config.mode, PQCMode.HYBRID_X25519_ML_KEM
        )

    def test_initialize_node(self) -> None:
        """Тест инициализации узла."""
        node_keys = self.adapter.initialize_node()

        self.assertIn("kem_public_key", node_keys)
        self.assertIn("sign_public_key", node_keys)
        self.assertIn("node_id", node_keys)

        self.assertIsInstance(node_keys["kem_public_key"], bytes)
        self.assertIsInstance(node_keys["sign_public_key"], bytes)
        self.assertIsInstance(node_keys["node_id"], bytes)

    def test_get_stats(self) -> None:
        """Тест получения статистики."""
        stats = self.adapter.get_stats()

        self.assertIsInstance(stats, ConnectionStats)
        self.assertEqual(stats.total_handshakes, 0)
        self.assertEqual(stats.successful_handshakes, 0)
        self.assertEqual(stats.failed_handshakes, 0)

    def test_clear_cache(self) -> None:
        """Тест очистки кэша."""
        self.adapter.clear_cache()
        self.assertEqual(self.adapter._session_cache.size, 0)

    def test_derive_session_keys(self) -> None:
        """Тест производства сессионных ключей."""
        shared_secret = secrets.token_bytes(32)
        keys = self.adapter.derive_session_keys(shared_secret)

        self.assertIn("encryption", keys)
        self.assertIn("mac", keys)
        self.assertIn("iv", keys)

        for key in keys.values():
            self.assertIsInstance(key, bytes)
            self.assertEqual(len(key), 32)

    def test_derive_session_keys_with_context(self) -> None:
        """Тест производства ключей с контекстом."""
        shared_secret = secrets.token_bytes(32)
        context = b"custom-context"

        keys1 = self.adapter.derive_session_keys(shared_secret, context)
        keys2 = self.adapter.derive_session_keys(shared_secret, context)

        self.assertEqual(keys1, keys2)

        keys3 = self.adapter.derive_session_keys(
            shared_secret, b"different-context"
        )
        self.assertNotEqual(keys1, keys3)

    def test_create_ssl_context(self) -> None:
        """Тест создания SSL контекста."""
        context = self.adapter.create_ssl_context()

        self.assertIsNotNone(context)
        self.assertEqual(context.protocol, ssl.PROTOCOL_TLS_CLIENT)

    def test_perform_handshake_cached(self) -> None:
        """Тест рукопожатия с кэшированием."""
        shared_secret = secrets.token_bytes(32)
        self.adapter._session_cache.put("peer-1", shared_secret)

        mock_socket = mock.MagicMock(spec=socket.socket)
        result = self.adapter.perform_handshake(
            mock_socket, peer_id="peer-1"
        )

        self.assertEqual(result.state, HandshakeState.COMPLETED)
        self.assertEqual(result.shared_secret, shared_secret)
        self.assertEqual(self.adapter.get_stats().cache_hits, 1)


class TestHandshakeResult(TestCase):
    """Тесты результата рукопожатия."""

    def test_default_values(self) -> None:
        """Тест значений по умолчанию."""
        result = HandshakeResult(state=HandshakeState.INIT)

        self.assertEqual(result.state, HandshakeState.INIT)
        self.assertIsNone(result.shared_secret)
        self.assertIsNone(result.ciphertext)
        self.assertIsNone(result.encapsulated_key)
        self.assertIsNone(result.attestation_signature)
        self.assertIsNone(result.peer_attestation)
        self.assertIsNone(result.mode_used)
        self.assertEqual(result.duration_ms, 0.0)
        self.assertIsNone(result.error)


if __name__ == "__main__":
    import unittest

    unittest.main()

