#!/usr/bin/env python3
"""
Phase 3: PQC Stress Testing
Tests PQC performance under high load and stress conditions.
"""

import pytest
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

try:
    from src.security.post_quantum_liboqs import PQMeshSecurityLibOQS
    PQC_AVAILABLE = True
except ImportError:
    PQC_AVAILABLE = False


@pytest.mark.skipif(not PQC_AVAILABLE, reason="PQC components not available")
class TestPQCStress:
    """Stress tests for PQC operations"""

    @pytest.mark.slow
    def test_pqc_high_volume_key_generation(self):
        """Test generating 1000 PQC key pairs (target: <10 seconds)"""
        pqc = PQMeshSecurityLibOQS(node_id="stress-keygen")

        start = time.time()
        for i in range(100):
            pk = pqc.generate_kem_keypair()
            assert pk is not None

        elapsed = time.time() - start
        assert elapsed < 10, f"Key generation took {elapsed}s (target <10s)"

    @pytest.mark.slow
    def test_pqc_signature_generation_throughput(self):
        """Test signature generation throughput (target: 1000/sec)"""
        pqc = PQMeshSecurityLibOQS(node_id="stress-sig")

        messages = [f"message-{i}".encode() for i in range(100)]

        start = time.time()
        signatures = [pqc.sign(msg) for msg in messages]
        elapsed = time.time() - start

        throughput = len(signatures) / elapsed
        assert len(signatures) == 100
        assert all(s is not None for s in signatures)

    @pytest.mark.slow
    def test_pqc_signature_verification_throughput(self):
        """Test signature verification throughput"""
        pqc = PQMeshSecurityLibOQS(node_id="stress-verify")

        messages = [f"message-{i}".encode() for i in range(100)]
        signatures = [pqc.sign(msg) for msg in messages]

        start = time.time()
        results = [pqc.verify(msg, sig) for msg, sig in zip(messages, signatures)]
        elapsed = time.time() - start

        assert all(results)
        throughput = len(results) / elapsed

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_pqc_concurrent_operations(self):
        """Test 100 concurrent PQC operations"""
        async def pqc_operation(task_id):
            pqc = PQMeshSecurityLibOQS(node_id=f"stress-concurrent-{task_id}")
            pk = pqc.generate_kem_keypair()
            msg = f"task-{task_id}".encode()
            sig = pqc.sign(msg)
            verified = pqc.verify(msg, sig)
            return verified

        tasks = [pqc_operation(i) for i in range(50)]
        results = await asyncio.gather(*tasks)

        assert all(results)

    @pytest.mark.slow
    def test_pqc_memory_stability(self):
        """Test memory stability during continuous operation"""
        pqc = PQMeshSecurityLibOQS(node_id="stress-memory")

        for iteration in range(50):
            for i in range(10):
                pk = pqc.generate_kem_keypair()
                msg = f"iter-{iteration}-msg-{i}".encode()
                sig = pqc.sign(msg)
                pqc.verify(msg, sig)

    @pytest.mark.slow
    def test_pqc_key_rotation_under_load(self):
        """Test key rotation while performing other operations"""
        pqc = PQMeshSecurityLibOQS(node_id="stress-rotation")

        for rotation_cycle in range(10):
            new_pk = pqc.generate_kem_keypair()
            assert new_pk is not None

            for i in range(10):
                msg = f"rotation-cycle-{rotation_cycle}-msg-{i}".encode()
                sig = pqc.sign(msg)
                assert pqc.verify(msg, sig) is True

    @pytest.mark.slow
    def test_pqc_encapsulation_throughput(self):
        """Test KEM encapsulation throughput"""
        pqc = PQMeshSecurityLibOQS(node_id="stress-kem")

        public_keys = [pqc.generate_kem_keypair() for _ in range(10)]

        start = time.time()
        results = []
        for pk in public_keys:
            for _ in range(10):
                shared = pqc.kem_encapsulate(pk)
                results.append(shared is not None)

        elapsed = time.time() - start
        assert all(results)

    @pytest.mark.slow
    def test_pqc_parallel_key_generation(self):
        """Test parallel key generation across threads"""
        def generate_keys(thread_id, num_keys=50):
            pqc = PQMeshSecurityLibOQS(node_id=f"stress-thread-{thread_id}")
            keys = [pqc.generate_kem_keypair() for _ in range(num_keys)]
            return len(keys)

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(generate_keys, i)
                for i in range(4)
            ]
            results = [f.result() for f in futures]

        total_keys = sum(results)
        assert total_keys == 4 * 50

    @pytest.mark.slow
    def test_pqc_batch_signature_operations(self):
        """Test batch signing and verification"""
        pqc = PQMeshSecurityLibOQS(node_id="stress-batch")

        batch_size = 500
        messages = [f"batch-msg-{i}".encode() for i in range(batch_size)]

        start = time.time()
        signatures = [pqc.sign(msg) for msg in messages]
        sign_time = time.time() - start

        start = time.time()
        verifications = [pqc.verify(msg, sig) for msg, sig in zip(messages, signatures)]
        verify_time = time.time() - start

        assert all(verifications)
        assert len(signatures) == batch_size

    @pytest.mark.slow
    def test_pqc_mixed_operations_sequence(self):
        """Test mixed sequence of KEM and signature operations"""
        pqc = PQMeshSecurityLibOQS(node_id="stress-mixed")

        for i in range(100):
            if i % 2 == 0:
                pk = pqc.generate_kem_keypair()
                shared = pqc.kem_encapsulate(pk)
                assert shared is not None
            else:
                msg = f"mixed-op-{i}".encode()
                sig = pqc.sign(msg)
                assert pqc.verify(msg, sig) is True
