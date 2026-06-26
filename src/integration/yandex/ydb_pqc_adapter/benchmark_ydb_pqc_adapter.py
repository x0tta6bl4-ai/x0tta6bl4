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
Бенчмарк для YDB PQC адаптера.

Замеряет время рукопожатия, размеры ключей и производительность кэширования.
"""

import secrets
import statistics
import time
from typing import Optional

from src.integration.yandex.ydb_pqc_adapter import (
    PQCConfig,
    PQCKeyExchange,
    PQCMode,
    PQCSessionCache,
    YDBPQCAdapter,
)


def benchmark_key_generation(
    iterations: int = 100,
) -> dict[str, float]:
    """Бенчмарк генерации ключей."""
    config = PQCConfig(mode=PQCMode.HYBRID_X25519_ML_KEM)
    key_exchange = PQCKeyExchange(config)

    kem_times = []
    sign_times = []

    for _ in range(iterations):
        start = time.perf_counter()
        key_exchange.generate_keypair()
        kem_times.append(time.perf_counter() - start)

        start = time.perf_counter()
        key_exchange.generate_signature_keypair()
        sign_times.append(time.perf_counter() - start)

    return {
        "kem_keygen_avg_ms": statistics.mean(kem_times) * 1000,
        "kem_keygen_p95_ms": sorted(kem_times)[int(0.95 * len(kem_times))] * 1000,
        "sign_keygen_avg_ms": statistics.mean(sign_times) * 1000,
        "sign_keygen_p95_ms": sorted(sign_times)[int(0.95 * len(sign_times))] * 1000,
    }


def benchmark_encapsulation(
    iterations: int = 100,
) -> dict[str, float]:
    """Бенчмарк инкапсуляции."""
    config = PQCConfig(mode=PQCMode.HYBRID_X25519_ML_KEM)
    sender = PQCKeyExchange(config)
    receiver = PQCKeyExchange(config)

    receiver_pub, _ = receiver.generate_keypair()

    encap_times = []
    decap_times = []

    for _ in range(iterations):
        start = time.perf_counter()
        ciphertext, shared_secret = sender.encapsulate(receiver_pub)
        encap_times.append(time.perf_counter() - start)

        start = time.perf_counter()
        _ = receiver.decapsulate(ciphertext, receiver_pub)
        decap_times.append(time.perf_counter() - start)

    return {
        "encap_avg_ms": statistics.mean(encap_times) * 1000,
        "encap_p95_ms": sorted(encap_times)[int(0.95 * len(encap_times))] * 1000,
        "decap_avg_ms": statistics.mean(decap_times) * 1000,
        "decap_p95_ms": sorted(decap_times)[int(0.95 * len(decap_times))] * 1000,
    }


def benchmark_handshake(
    iterations: int = 50,
) -> dict[str, float]:
    """Бенчмарк рукопожатия."""
    config = PQCConfig(
        mode=PQCMode.HYBRID_X25519_ML_KEM,
        enable_attestation=False,
        require_peer_attestation=False,
    )

    adapter1 = YDBPQCAdapter(config=config)
    adapter2 = YDBPQCAdapter(config=config)

    adapter1.initialize_node()
    adapter2.initialize_node()

    handshake_times = []

    for _ in range(iterations):
        start = time.perf_counter()

        result1 = adapter1.perform_handshake(
            peer_socket=None,
            peer_public_key=adapter2._node_keypair[0] if adapter2._node_keypair else None,
            peer_sign_public_key=adapter2._node_sign_keypair[0] if adapter2._node_sign_keypair else None,
            peer_id=f"peer-{secrets.token_hex(8)}",
        )

        handshake_times.append(time.perf_counter() - start)

    return {
        "handshake_avg_ms": statistics.mean(handshake_times) * 1000,
        "handshake_p95_ms": sorted(handshake_times)[int(0.95 * len(handshake_times))] * 1000,
        "handshake_p99_ms": sorted(handshake_times)[int(0.99 * len(handshake_times))] * 1000,
    }


def benchmark_cache_performance(
    iterations: int = 10000,
) -> dict[str, float]:
    """Бенчмарк производительности кэша."""
    cache = PQCSessionCache(max_size=1024, ttl=3600)

    for i in range(100):
        cache.put(f"peer-{i}", secrets.token_bytes(32))

    hit_times = []
    miss_times = []

    for _ in range(iterations):
        peer_id = f"peer-{secrets.randbelow(100)}"

        start = time.perf_counter()
        cache.get(peer_id)
        hit_times.append(time.perf_counter() - start)

        peer_id = f"unknown-{secrets.token_hex(8)}"
        start = time.perf_counter()
        cache.get(peer_id)
        miss_times.append(time.perf_counter() - start)

    return {
        "cache_hit_avg_us": statistics.mean(hit_times) * 1_000_000,
        "cache_miss_avg_us": statistics.mean(miss_times) * 1_000_000,
    }


def benchmark_key_sizes() -> dict[str, int]:
    """Замер размеров ключей."""
    config = PQCConfig(mode=PQCMode.HYBRID_X25519_ML_KEM)
    key_exchange = PQCKeyExchange(config)

    kem_pub, _ = key_exchange.generate_keypair()
    sign_pub, _ = key_exchange.generate_signature_keypair()

    receiver = PQCKeyExchange(config)
    receiver_pub, _ = receiver.generate_keypair()
    ciphertext, shared_secret = key_exchange.encapsulate(receiver_pub)

    message = b"benchmark message"
    signature = key_exchange.sign(message, key_exchange._signer.export_secret_key())

    return {
        "kem_public_key_bytes": len(kem_pub),
        "kem_secret_key_bytes": len(key_exchange._kem.export_secret_key()),
        "kem_ciphertext_bytes": len(ciphertext),
        "kem_shared_secret_bytes": len(shared_secret),
        "sign_public_key_bytes": len(sign_pub),
        "sign_signature_bytes": len(signature),
    }


def benchmark_signature(
    iterations: int = 100,
) -> dict[str, float]:
    """Бенчмарк подписи и верификации."""
    config = PQCConfig(mode=PQCMode.HYBRID_X25519_ML_KEM)
    key_exchange = PQCKeyExchange(config)

    public_key, secret_key = key_exchange.generate_signature_keypair()
    message = b"benchmark message for signing"

    sign_times = []
    verify_times = []

    for _ in range(iterations):
        start = time.perf_counter()
        signature = key_exchange.sign(message, secret_key)
        sign_times.append(time.perf_counter() - start)

        start = time.perf_counter()
        key_exchange.verify(message, signature, public_key)
        verify_times.append(time.perf_counter() - start)

    return {
        "sign_avg_ms": statistics.mean(sign_times) * 1000,
        "sign_p95_ms": sorted(sign_times)[int(0.95 * len(sign_times))] * 1000,
        "verify_avg_ms": statistics.mean(verify_times) * 1000,
        "verify_p95_ms": sorted(verify_times)[int(0.95 * len(verify_times))] * 1000,
    }


def run_all_benchmarks() -> None:
    """Запуск всех бенчмарков."""
    print("=" * 60)
    print("YDB PQC Adapter Benchmarks")
    print("=" * 60)

    print("\n1. Key Generation:")
    keygen_results = benchmark_key_generation()
    for key, value in keygen_results.items():
        print(f"   {key}: {value:.3f}ms")

    print("\n2. Encapsulation/Decapsulation:")
    encap_results = benchmark_encapsulation()
    for key, value in encap_results.items():
        print(f"   {key}: {value:.3f}ms")

    print("\n3. Signature:")
    sig_results = benchmark_signature()
    for key, value in sig_results.items():
        print(f"   {key}: {value:.3f}ms")

    print("\n4. Handshake:")
    handshake_results = benchmark_handshake()
    for key, value in handshake_results.items():
        print(f"   {key}: {value:.3f}ms")

    print("\n5. Cache Performance:")
    cache_results = benchmark_cache_performance()
    for key, value in cache_results.items():
        print(f"   {key}: {value:.3f}us")

    print("\n6. Key Sizes:")
    size_results = benchmark_key_sizes()
    for key, value in size_results.items():
        print(f"   {key}: {value} bytes")

    print("\n" + "=" * 60)
    print("Benchmarks completed")
    print("=" * 60)


if __name__ == "__main__":
    run_all_benchmarks()

