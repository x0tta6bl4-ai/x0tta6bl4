"""
Unit test for high-concurrency PQC benchmark script.
"""
from unittest.mock import MagicMock, patch
import pytest

from scripts.ops.benchmark_pqc_high_concurrency import (
    benchmark_mldsa,
    benchmark_mlkem,
    calculate_percentiles,
)


@pytest.mark.asyncio
async def test_benchmark_mlkem():
    with patch("scripts.ops.benchmark_pqc_high_concurrency.PQCKeyExchange") as mock_kem_cls:
        instance = MagicMock()
        kp = MagicMock()
        kp.public_key = b"pubkey"
        kp.secret_key = b"privkey"
        instance.generate_keypair.return_value = kp
        instance.encapsulate.return_value = (b"ct", b"shared_secret")
        instance.decapsulate.return_value = b"shared_secret"
        mock_kem_cls.return_value = instance

        results = await benchmark_mlkem(iterations=30)
        assert results["iterations"] == 30
        assert results["total_ops_per_sec"] > 0
        assert "mean_ms" in results["encapsulation"]
        assert "p95_ms" in results["encapsulation"]


@pytest.mark.asyncio
async def test_benchmark_mldsa():
    with patch("scripts.ops.benchmark_pqc_high_concurrency.PQCDigitalSignature") as mock_dsa_cls:
        instance = MagicMock()
        kp = MagicMock()
        kp.public_key = b"pubkey"
        kp.secret_key = b"privkey"
        instance.generate_keypair.return_value = kp
        sig_obj = MagicMock()
        sig_obj.signature_bytes = b"sigbytes"
        instance.sign.return_value = sig_obj
        instance.verify.return_value = True
        mock_dsa_cls.return_value = instance

        results = await benchmark_mldsa(iterations=30)
        assert results["iterations"] == 30
        assert results["total_ops_per_sec"] > 0
        assert "mean_ms" in results["signing"]
        assert "p95_ms" in results["verification"]


def test_calculate_percentiles():
    lats = [1.0, 2.0, 3.0, 4.0, 5.0, 10.0]
    p = calculate_percentiles(lats)
    assert p["min_ms"] == 1.0
    assert p["max_ms"] == 10.0
    assert p["mean_ms"] > 0
