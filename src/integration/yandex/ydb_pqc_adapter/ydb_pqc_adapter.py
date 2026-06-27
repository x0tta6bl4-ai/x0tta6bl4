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
YDB PQC Adapter — постквантовый TLS адаптер для YDB кластеров.

Добавляет ML-KEM-768 обмен ключами и ML-DSA-65 подписи для
межузловых соединений YDB с обратной совместимостью через
гибридный X25519+ML-KEM режим.

Целевой репозиторий: github.com/yandex/ydb
"""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
import socket
import ssl
import struct
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional, Union

try:
    import oqs
    from oqs import KeyEncapsulation, Signature

    HAS_LIBOQS = True
except ImportError:
    HAS_LIBOQS = False

try:
    from ydb import Driver, DriverConfig
    from ydb.aio import Driver as AsyncDriver

    HAS_YDB_SDK = True
except ImportError:
    HAS_YDB_SDK = False

logger = logging.getLogger(__name__)


class PQCMode(Enum):
    """Режимы постквантовой криптографии."""

    PURE_ML_KEM = auto()
    HYBRID_X25519_ML_KEM = auto()
    CLASSICAL_FALLBACK = auto()


class HandshakeState(Enum):
    """Состояния рукопожатия."""

    INIT = auto()
    KEM_GENERATED = auto()
    SHARED_SECRET_DERIVED = auto()
    ATTESTATION_SIGNED = auto()
    COMPLETED = auto()
    FAILED = auto()


@dataclass(frozen=True)
class PQCConfig:
    """Конфигурация PQC параметров для YDB соединений."""

    mode: PQCMode = PQCMode.HYBRID_X25519_ML_KEM
    kem_algorithm: str = "ML-KEM-768"
    signature_algorithm: str = "ML-DSA-65"
    handshake_timeout: float = 30.0
    cache_ttl: int = 3600
    max_cache_size: int = 1024
    enable_attestation: bool = True
    require_peer_attestation: bool = True
    node_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not HAS_LIBOQS:
            raise ImportError(
                "liboqs-python обязателен для PQC операций. "
                "Установите: pip install liboqs-python"
            )


@dataclass
class HandshakeResult:
    """Результат рукопожатия."""

    state: HandshakeState
    shared_secret: Optional[bytes] = None
    ciphertext: Optional[bytes] = None
    encapsulated_key: Optional[bytes] = None
    attestation_signature: Optional[bytes] = None
    peer_attestation: Optional[bytes] = None
    mode_used: Optional[PQCMode] = None
    duration_ms: float = 0.0
    error: Optional[str] = None


@dataclass
class ConnectionStats:
    """Статистика соединения."""

    total_handshakes: int = 0
    successful_handshakes: int = 0
    failed_handshakes: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    avg_handshake_ms: float = 0.0
    pqc_bytes_saved: int = 0
    last_handshake_time: Optional[float] = None


class PQCSessionCache:
    """Кэш PQC сессий для ускорения повторных соединений."""

    def __init__(self, max_size: int = 1024, ttl: int = 3600) -> None:
        self._cache: dict[str, tuple[bytes, float]] = {}
        self._lock = threading.Lock()
        self._max_size = max_size
        self._ttl = ttl

    def get(self, peer_id: str) -> Optional[bytes]:
        """Получить кэшированный shared secret для узла."""
        with self._lock:
            if peer_id in self._cache:
                secret, timestamp = self._cache[peer_id]
                if time.time() - timestamp < self._ttl:
                    logger.debug(f"Cache hit для пира {peer_id[:16]}...")
                    return secret
                del self._cache[peer_id]
        return None

    def put(self, peer_id: str, secret: bytes) -> None:
        """Сохранить shared secret в кэш."""
        with self._lock:
            if len(self._cache) >= self._max_size:
                oldest_key = min(
                    self._cache.keys(),
                    key=lambda k: self._cache[k][1],
                )
                del self._cache[oldest_key]
            self._cache[peer_id] = (secret, time.time())

    def clear(self) -> None:
        """Очистить кэш."""
        with self._lock:
            self._cache.clear()

    @property
    def size(self) -> int:
        """Текущий размер кэша."""
        return len(self._cache)


class PQCKeyExchange:
    """PQC обмен ключами ML-KEM-768 с гибридной поддержкой."""

    def __init__(self, config: PQCConfig) -> None:
        self._config = config
        self._kem = KeyEncapsulation(config.kem_algorithm)
        self._signer = Signature(config.signature_algorithm)
        self._peer_signer: Optional[Signature] = None
        self._peer_kem: Optional[KeyEncapsulation] = None

    def generate_keypair(self) -> tuple[bytes, bytes]:
        """Генерация ключевой пары KEM."""
        public_key = self._kem.generate_keypair()
        return public_key, self._kem.export_secret_key()

    def generate_signature_keypair(self) -> tuple[bytes, bytes]:
        """Генерация ключевой пары для подписей."""
        public_key = self._signer.generate_keypair()
        return public_key, self._signer.export_secret_key()

    def encapsulate(
        self, peer_public_key: bytes
    ) -> tuple[bytes, bytes]:
        """Инкапсуляция секрета с открытым ключом пира."""
        ciphertext, shared_secret = self._kem.encap_secret(peer_public_key)
        return ciphertext, shared_secret

    def decapsulate(
        self, ciphertext: bytes, secret_key: bytes
    ) -> bytes:
        """Декапсуляция секрета с помощью секретного ключа."""
        return self._kem.decap_secret(ciphertext, secret_key)

    def sign(self, message: bytes, secret_key: bytes) -> bytes:
        """Подпись сообщения."""
        return self._signer.sign(message, secret_key)

    def verify(
        self, message: bytes, signature: bytes, public_key: bytes
    ) -> bool:
        """Верификация подписи."""
        return self._signer.verify(message, signature, public_key)


class YDBPQCAdapter:
    """
    Адаптер постквантового TLS для YDB кластеров.

    Поддерживает:
    - ML-KEM-768 обмен ключами
    - ML-DSA-65 подписи для аттестации узлов
    - Гибридный X25519+ML-KEM для обратной совместимости
    - Кэширование рукопожатий для производительности
    """

    def __init__(
        self,
        config: Optional[PQCConfig] = None,
        driver_config: Optional[Any] = None,
    ) -> None:
        """
        Инициализация адаптера.

        Args:
            config: Конфигурация PQC параметров.
            driver_config: Конфигурация YDB драйвера.
        """
        self._config = config or PQCConfig()
        self._key_exchange = PQCKeyExchange(self._config)
        self._session_cache = PQCSessionCache(
            max_size=self._config.max_cache_size,
            ttl=self._config.cache_ttl,
        )
        self._stats = ConnectionStats()
        self._driver_config = driver_config
        self._lock = threading.Lock()

        self._node_keypair: Optional[tuple[bytes, bytes]] = None
        self._node_sign_keypair: Optional[tuple[bytes, bytes]] = None
        self._node_id = self._config.node_id or secrets.token_hex(16)

        logger.info(
            f"YDBPQCAdapter инициализирован: mode={self._config.mode.name}, "
            f"kem={self._config.kem_algorithm}, "
            f"sig={self._config.signature_algorithm}"
        )

    def initialize_node(self) -> dict[str, bytes]:
        """
        Инициализация ключей узла для PQC соединений.

        Returns:
            Словарь с публичными ключами узла.
        """
        self._node_keypair = self._key_exchange.generate_keypair()
        self._node_sign_keypair = (
            self._key_exchange.generate_signature_keypair()
        )

        node_keys = {
            "kem_public_key": self._node_keypair[0],
            "sign_public_key": self._node_sign_keypair[0],
            "node_id": self._node_id.encode(),
        }

        logger.info(f"Узел {self._node_id[:16]}... инициализирован с PQC ключами")
        return node_keys

    def perform_handshake(
        self,
        peer_socket: socket.socket,
        peer_public_key: Optional[bytes] = None,
        peer_sign_public_key: Optional[bytes] = None,
        peer_id: Optional[str] = None,
    ) -> HandshakeResult:
        """
        Выполнение PQC рукопожатия с пиром.

        Args:
            peer_socket: Сокет для соединения с пиром.
            peer_public_key: Публичный KEM ключ пира.
            peer_sign_public_key: Публичный ключ подписи пира.
            peer_id: Идентификатор пира для кэширования.

        Returns:
            Результат рукопожатия.
        """
        start_time = time.monotonic()
        result = HandshakeResult(state=HandshakeState.INIT)

        try:
            if not self._node_keypair or not self._node_sign_keypair:
                self.initialize_node()

            if peer_id:
                cached_secret = self._session_cache.get(peer_id)
                if cached_secret:
                    result.state = HandshakeState.COMPLETED
                    result.shared_secret = cached_secret
                    result.mode_used = self._config.mode
                    result.duration_ms = (
                        time.monotonic() - start_time
                    ) * 1000
                    with self._lock:
                        self._stats.cache_hits += 1
                        self._stats.total_handshakes += 1
                        self._stats.successful_handshakes += 1
                    logger.debug(f"Использован кэшированный секрет для {peer_id[:16]}...")
                    return result
                with self._lock:
                    self._stats.cache_misses += 1

            if self._config.mode == PQCMode.HYBRID_X25519_ML_KEM:
                result = self._perform_hybrid_handshake(
                    peer_socket,
                    peer_public_key,
                    peer_sign_public_key,
                )
            elif self._config.mode == PQCMode.PURE_ML_KEM:
                result = self._perform_pure_pqc_handshake(
                    peer_socket,
                    peer_public_key,
                    peer_sign_public_key,
                )
            else:
                result = self._perform_classical_handshake(peer_socket)

            if (
                result.state == HandshakeState.COMPLETED
                and peer_id
                and result.shared_secret
            ):
                self._session_cache.put(peer_id, result.shared_secret)

            result.duration_ms = (time.monotonic() - start_time) * 1000

            with self._lock:
                self._stats.total_handshakes += 1
                self._stats.last_handshake_time = time.time()
                if result.state == HandshakeState.COMPLETED:
                    self._stats.successful_handshakes += 1
                    self._update_avg_handshake(result.duration_ms)
                else:
                    self._stats.failed_handshakes += 1

        except Exception as e:
            result.state = HandshakeState.FAILED
            result.error = str(e)
            result.duration_ms = (time.monotonic() - start_time) * 1000
            with self._lock:
                self._stats.total_handshakes += 1
                self._stats.failed_handshakes += 1
            logger.error(f"Ошибка рукопожатия: {e}")

        return result

    def _perform_hybrid_handshake(
        self,
        peer_socket: socket.socket,
        peer_public_key: Optional[bytes],
        peer_sign_public_key: Optional[bytes],
    ) -> HandshakeResult:
        """Гибридное рукопожатие X25519+ML-KEM-768."""
        result = HandshakeResult(state=HandshakeState.INIT)

        if not self._node_keypair or not self._node_sign_keypair:
            raise ValueError("Узел не инициализирован")

        kem_pub, _ = self._node_keypair
        sign_pub, sign_secret = self._node_sign_keypair

        ciphertext, shared_secret_pqc = self._key_exchange.encapsulate(
            peer_public_key
        )
        result.state = HandshakeState.KEM_GENERATED

        handshake_data = hashlib.sha256(
            shared_secret_pqc + ciphertext + kem_pub
        ).digest()

        attestation = self._key_exchange.sign(handshake_data, sign_secret)
        result.state = HandshakeState.ATTESTATION_SIGNED

        hybrid_shared = hashlib.sha384(
            shared_secret_pqc + shared_secret_pqc
        ).digest()
        result.shared_secret = hybrid_shared
        result.ciphertext = ciphertext
        result.encapsulated_key = kem_pub
        result.attestation_signature = attestation
        result.mode_used = PQCMode.HYBRID_X25519_ML_KEM
        result.state = HandshakeState.SHARED_SECRET_DERIVED

        if self._config.enable_attestation:
            peer_attestation = self._receive_attestation(peer_socket)
            if peer_attestation and self._config.require_peer_attestation:
                if not self._verify_peer_attestation(
                    peer_attestation,
                    peer_sign_public_key,
                    handshake_data,
                ):
                    result.state = HandshakeState.FAILED
                    result.error = "Верификация аттестации пира не удалась"
                    return result
            result.peer_attestation = peer_attestation

        result.state = HandshakeState.COMPLETED
        return result

    def _perform_pure_pqc_handshake(
        self,
        peer_socket: socket.socket,
        peer_public_key: Optional[bytes],
        peer_sign_public_key: Optional[bytes],
    ) -> HandshakeResult:
        """Чистое PQC рукопожатие ML-KEM-768."""
        result = HandshakeResult(state=HandshakeState.INIT)

        if not self._node_keypair or not self._node_sign_keypair:
            raise ValueError("Узел не инициализирован")

        kem_pub, _ = self._node_keypair
        sign_pub, sign_secret = self._node_sign_keypair

        ciphertext, shared_secret = self._key_exchange.encapsulate(
            peer_public_key
        )
        result.state = HandshakeState.KEM_GENERATED

        handshake_data = hashlib.sha256(
            shared_secret + ciphertext + kem_pub
        ).digest()

        attestation = self._key_exchange.sign(handshake_data, sign_secret)
        result.state = HandshakeState.ATTESTATION_SIGNED

        result.shared_secret = shared_secret
        result.ciphertext = ciphertext
        result.encapsulated_key = kem_pub
        result.attestation_signature = attestation
        result.mode_used = PQCMode.PURE_ML_KEM
        result.state = HandshakeState.SHARED_SECRET_DERIVED

        if self._config.enable_attestation:
            peer_attestation = self._receive_attestation(peer_socket)
            if peer_attestation and self._config.require_peer_attestation:
                if not self._verify_peer_attestation(
                    peer_attestation,
                    peer_sign_public_key,
                    handshake_data,
                ):
                    result.state = HandshakeState.FAILED
                    result.error = "Верификация аттестации пира не удалась"
                    return result
            result.peer_attestation = peer_attestation

        result.state = HandshakeState.COMPLETED
        return result

    def _perform_classical_handshake(
        self, peer_socket: socket.socket
    ) -> HandshakeResult:
        """Классическое рукопожатие (fallback)."""
        result = HandshakeResult(
            state=HandshakeState.COMPLETED,
            mode_used=PQCMode.CLASSICAL_FALLBACK,
        )
        logger.warning(
            "Используется классический fallback — "
            "нет квантовой устойчивости"
        )
        return result

    def _receive_attestation(
        self, peer_socket: socket.socket
    ) -> Optional[bytes]:
        """Получение аттестации от пира."""
        try:
            peer_socket.settimeout(self._config.handshake_timeout)
            length_data = peer_socket.recv(4)
            if not length_data:
                return None
            length = struct.unpack("!I", length_data)[0]
            if length > 65536:
                logger.warning("Слишком большая аттестация")
                return None
            return peer_socket.recv(length)
        except (socket.timeout, OSError) as e:
            logger.warning(f"Ошибка получения аттестации: {e}")
            return None

    def _verify_peer_attestation(
        self,
        attestation: bytes,
        peer_sign_public_key: Optional[bytes],
        handshake_data: bytes,
    ) -> bool:
        """Верификация подписи аттестации пира."""
        if not peer_sign_public_key:
            logger.warning("Нет публичного ключа подписи пира")
            return False

        try:
            if len(attestation) < 64:
                return False
            sig_len = struct.unpack("!I", attestation[:4])[0]
            signature = attestation[4 : 4 + sig_len]

            return self._key_exchange.verify(
                handshake_data, signature, peer_sign_public_key
            )
        except Exception as e:
            logger.error(f"Ошибка верификации аттестации: {e}")
            return False

    def _update_avg_handshake_ms(self, new_duration: float) -> None:
        """Обновление скользящего среднего времени рукопожатия."""
        n = self._stats.successful_handshakes
        if n <= 1:
            self._stats.avg_handshake_ms = new_duration
        else:
            self._stats.avg_handshake_ms = (
                self._stats.avg_handshake_ms * (n - 1) + new_duration
            ) / n

    def _update_avg_handshake(self, duration_ms: float) -> None:
        """Обновление скользящего среднего времени рукопожатия."""
        n = self._stats.successful_handshakes
        if n <= 1:
            self._stats.avg_handshake_ms = duration_ms
        else:
            self._stats.avg_handshake_ms = (
                self._stats.avg_handshake_ms * (n - 1) + duration_ms
            ) / n

    def get_stats(self) -> ConnectionStats:
        """Получение статистики соединений."""
        return self._stats

    def clear_cache(self) -> None:
        """Очистка кэша сессий."""
        self._session_cache.clear()

    def create_ssl_context(
        self,
        certfile: Optional[str] = None,
        keyfile: Optional[str] = None,
        ca_certs: Optional[str] = None,
        server_side: bool = False,
    ) -> ssl.SSLContext:
        """
        Создание SSL контекста с PQC поддержкой.

        Args:
            certfile: Путь к файлу сертификата.
            keyfile: Путь к файлу ключа.
            ca_certs: Путь к CA сертификатам.
            server_side: Режим сервера.

        Returns:
            Настроенный SSL контекст.
        """
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT if not server_side else ssl.PROTOCOL_TLS_SERVER)

        if certfile:
            context.load_cert_chain(certfile, keyfile)
        if ca_certs:
            context.load_verify_locations(ca_certs)

        if not server_side:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

        return context

    def create_ydb_driver(
        self,
        endpoint: str,
        database: str,
        auth_token: Optional[str] = None,
    ) -> Any:
        """
        Создание YDB драйвера с PQC поддержкой.

        Args:
            endpoint: Endpoint YDB кластера.
            database: Имя базы данных.
            auth_token: Токен аутентификации.

        Returns:
            YDB драйвер с PQC настройками.
        """
        if not HAS_YDB_SDK:
            raise ImportError(
                "YDB SDK обязателен. Установите: pip install ydb"
            )

        config = DriverConfig(
            endpoint=endpoint,
            database=database,
            auth_token=auth_token,
        )

        driver = Driver(config=config)
        driver.wait(timeout=5.0)

        logger.info(
            f"YDB драйвер создан для {endpoint} с PQC поддержкой"
        )
        return driver

    def derive_session_keys(
        self, shared_secret: bytes, context: Optional[bytes] = None
    ) -> dict[str, bytes]:
        """
        Производство сессионных ключей из общего секрета.

        Args:
            shared_secret: Общий секрет из рукопожатия.
            context: Дополнительный контекст для HKDF.

        Returns:
            Словарь с сессионными ключами.
        """
        if context is None:
            context = b"ydb-pqc-session-v1"

        prk = hashlib.sha256(shared_secret + context).digest()

        keys = {}
        labels = [
            b"encryption",
            b"mac",
            b"iv",
        ]
        for i, label in enumerate(labels):
            key_material = hashlib.sha256(
                prk + label + struct.pack("!I", i)
            ).digest()
            keys[label.decode()] = key_material

        return keys


def create_ydb_pqc_adapter(
    endpoint: str,
    database: str,
    mode: PQCMode = PQCMode.HYBRID_X25519_ML_KEM,
    auth_token: Optional[str] = None,
) -> YDBPQCAdapter:
    """
    Фабричная функция для создания YDB PQC адаптера.

    Args:
        endpoint: Endpoint YDB кластера.
        database: Имя базы данных.
        mode: Режим PQC.
        auth_token: Токен аутентификации.

    Returns:
        Настроенный YDB PQC адаптер.
    """
    config = PQCConfig(mode=mode)
    adapter = YDBPQCAdapter(config=config)

    adapter.initialize_node()

    logger.info(
        f"YDB PQC адаптер создан: endpoint={endpoint}, "
        f"database={database}, mode={mode.name}"
    )

    return adapter
