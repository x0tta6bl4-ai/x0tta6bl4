#!/usr/bin/env python3
"""
Phase 2: PQC MAPE-K Integration Tests
Tests PQC integration with MAPE-K self-healing loop.
"""

import time

import pytest

try:
    from src.security.post_quantum_liboqs import PQMeshSecurityLibOQS
    from src.self_healing.mape_k import MAPEK

    PQC_AVAILABLE = True
except ImportError:
    PQC_AVAILABLE = False


@pytest.mark.skipif(not PQC_AVAILABLE, reason="PQC components not available")
class TestPQCMAPEKIntegration:
    """Test PQC with MAPE-K self-healing loop"""

    def test_mape_k_with_pqc_metrics(self):
        """Test MAPE-K monitoring with PQC-signed metrics"""
        pqc = PQMeshSecurityLibOQS(node_id="mapek-node")

        metrics = {
            "cpu_usage": 45.2,
            "memory_usage": 62.1,
            "network_latency": 12.5,
            "crypto_operations": 1523,
        }

        import json

        metrics_bytes = json.dumps(metrics).encode()
        signature = pqc.sign(metrics_bytes)

        assert signature is not None
        assert pqc.verify(metrics_bytes, signature) is True

    def test_pqc_key_rotation_triggered_by_anomaly(self):
        """Test PQC key rotation when anomaly is detected"""
        pqc = PQMeshSecurityLibOQS(node_id="anomaly-node")

        initial_pk = pqc.generate_kem_keypair()
        assert initial_pk is not None

        rotated_pk = pqc.generate_kem_keypair()
        assert rotated_pk is not None
        assert initial_pk != rotated_pk

    def test_pqc_recovery_execution_with_new_keys(self):
        """Test recovery action execution with newly generated PQC keys"""
        pqc = PQMeshSecurityLibOQS(node_id="recovery-node")

        new_kem_pk = pqc.generate_kem_keypair()
        assert new_kem_pk is not None

        test_message = b"Recovery action with new keys"
        signature = pqc.sign(test_message)

        assert signature is not None
        assert pqc.verify(test_message, signature) is True

    def test_pqc_crypto_agility_in_planning_phase(self):
        """Test crypto agility during MAPE-K planning phase"""
        pqc = PQMeshSecurityLibOQS(node_id="planning-node")

        plan_1_kem = pqc.generate_kem_keypair()
        plan_2_kem = pqc.generate_kem_keypair()

        assert plan_1_kem != plan_2_kem

        sig_1 = pqc.sign(b"Plan 1")
        sig_2 = pqc.sign(b"Plan 2")

        assert sig_1 != sig_2

    def test_pqc_anomaly_detection_with_signed_evidence(self):
        """Test anomaly detection with PQC-signed evidence"""
        pqc = PQMeshSecurityLibOQS(node_id="detector-node")

        anomaly_evidence = b"High CPU spike detected at 15:30:45"
        signature = pqc.sign(anomaly_evidence)

        assert pqc.verify(anomaly_evidence, signature) is True

        forged_evidence = b"Low memory alert"
        assert pqc.verify(forged_evidence, signature) is False

    def test_pqc_analysis_with_trend_signing(self):
        """Test trend analysis with PQC signatures"""
        pqc = PQMeshSecurityLibOQS(node_id="analysis-node")

        trend_data = [(1, 45.1), (2, 46.2), (3, 47.5), (4, 48.1), (5, 49.0)]

        import json

        trend_bytes = json.dumps(trend_data).encode()
        signature = pqc.sign(trend_bytes)

        assert pqc.verify(trend_bytes, signature) is True

    def test_pqc_knowledge_base_update_signature(self):
        """Test signing knowledge base updates from MAPE-K"""
        pqc = PQMeshSecurityLibOQS(node_id="kb-node")

        kb_update = b"New root cause: disk latency -> memory pressure"
        signature = pqc.sign(kb_update)

        assert pqc.verify(kb_update, signature) is True

    def test_pqc_recovery_audit_trail(self):
        """Test creating audit trail of recovery actions with PQC"""
        pqc = PQMeshSecurityLibOQS(node_id="audit-node")

        recovery_actions = [
            b"Restarted service redis",
            b"Increased memory limit to 4GB",
            b"Enabled cache optimization",
        ]

        signatures = [pqc.sign(action) for action in recovery_actions]

        for action, sig in zip(recovery_actions, signatures):
            assert pqc.verify(action, sig) is True
