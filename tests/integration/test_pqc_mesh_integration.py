#!/usr/bin/env python3
"""
Phase 2: PQC Mesh Network Integration Tests
Tests PQC handshake, key distribution, and recovery in mesh networks.
"""

import asyncio
import json
import time

import pytest

try:
    from src.security.post_quantum_liboqs import PQMeshSecurityLibOQS

    PQC_AVAILABLE = True
except ImportError:
    PQC_AVAILABLE = False


@pytest.mark.skipif(not PQC_AVAILABLE, reason="PQC components not available")
@pytest.mark.asyncio
class TestPQCMeshIntegration:
    """Test PQC functionality within mesh network context"""

    @pytest.fixture
    def pqc_nodes(self):
        """Create 3 test nodes with PQC"""
        nodes = {}
        for i in range(3):
            node_id = f"node-pqc-{i}"
            pqc = PQMeshSecurityLibOQS(node_id=node_id)
            nodes[node_id] = {"pqc": pqc}
        return nodes

    async def test_pqc_handshake_between_nodes(self, pqc_nodes):
        """Test PQC handshake between two nodes"""
        node_a = pqc_nodes["node-pqc-0"]
        node_b = pqc_nodes["node-pqc-1"]

        kem_pk_a = node_a["pqc"].pq_backend.generate_kem_keypair()
        kem_pk_b = node_b["pqc"].pq_backend.generate_kem_keypair()

        assert kem_pk_a is not None
        assert kem_pk_b is not None

        shared_secret, ciphertext = node_a["pqc"].pq_backend.kem_encapsulate(
            kem_pk_b.public_key
        )
        assert shared_secret is not None
        assert ciphertext is not None

    async def test_pqc_key_distribution_protocol(self, pqc_nodes):
        """Test key distribution in mesh network"""
        nodes = list(pqc_nodes.values())
        public_keys = {}

        for i, node in enumerate(nodes):
            public_keys[f"node-{i}"] = node["pqc"].pq_backend.generate_kem_keypair()

        assert len(public_keys) == len(nodes)

    async def test_pqc_key_rotation_in_mesh(self, pqc_nodes):
        """Test key rotation during mesh operation"""
        node = pqc_nodes["node-pqc-0"]

        old_pk = node["pqc"].pq_backend.generate_kem_keypair()
        new_pk = node["pqc"].pq_backend.generate_kem_keypair()

        assert old_pk.public_key != new_pk.public_key

    async def test_pqc_signature_verification_in_mesh_messages(self, pqc_nodes):
        """Test signature verification in mesh message routing"""
        node = pqc_nodes["node-pqc-0"]
        message = b"Mesh network update from node-0"

        signature = node["pqc"].sign_beacon(message)
        assert signature is not None

        verified = node["pqc"].verify_beacon(
            message, signature, node["pqc"].sig_keypair.public_key
        )
        assert verified is True

    async def test_pqc_beacon_with_signature(self, pqc_nodes):
        """Test beacon messages signed with PQC"""
        node = pqc_nodes["node-pqc-0"]

        beacon_data = b"Beacon from node-pqc-0 at slot 1000"
        signature = node["pqc"].sign_beacon(beacon_data)

        assert signature is not None
        assert (
            node["pqc"].verify_beacon(
                beacon_data, signature, node["pqc"].sig_keypair.public_key
            )
            is True
        )

    async def test_pqc_concurrent_mesh_operations(self, pqc_nodes):
        """Test concurrent PQC operations across mesh"""

        async def perform_key_exchange(node):
            try:
                kem_pk = node["pqc"].pq_backend.generate_kem_keypair()
                return kem_pk is not None
            except Exception:
                return False

        results = await asyncio.gather(
            *[perform_key_exchange(node) for node in pqc_nodes.values()]
        )

        assert all(results)

    async def test_pqc_mesh_recovery_after_node_failure(self, pqc_nodes):
        """Test mesh recovery after node failure with PQC"""
        node_a = pqc_nodes["node-pqc-0"]
        node_c = pqc_nodes["node-pqc-2"]

        kem_pk_a = node_a["pqc"].pq_backend.generate_kem_keypair()
        kem_pk_c = node_c["pqc"].pq_backend.generate_kem_keypair()

        shared_secret, ciphertext = node_a["pqc"].pq_backend.kem_encapsulate(
            kem_pk_c.public_key
        )
        assert shared_secret is not None


@pytest.mark.skipif(not PQC_AVAILABLE, reason="PQC components not available")
class TestPQCBeaconIntegration:
    """Test PQC with slot synchronization beacons"""

    def test_pqc_protected_beacon(self):
        """Test beacon with PQC signature"""
        node_id = "beacon-test-node"
        pqc = PQMeshSecurityLibOQS(node_id=node_id)

        beacon_payload = {"node_id": node_id, "slot": 1000, "timestamp": time.time()}

        beacon_bytes = json.dumps(beacon_payload).encode()
        signature = pqc.sign_beacon(beacon_bytes)

        assert signature is not None
        assert (
            pqc.verify_beacon(beacon_bytes, signature, pqc.sig_keypair.public_key)
            is True
        )

    def test_pqc_beacon_tampering_detection(self):
        """Test tampering detection in PQC-signed beacons"""
        pqc = PQMeshSecurityLibOQS(node_id="tamper-test")

        original = b"Valid beacon data"
        signature = pqc.sign_beacon(original)

        tampered = b"Tampered beacon data"
        assert (
            pqc.verify_beacon(tampered, signature, pqc.sig_keypair.public_key) is False
        )

    def test_pqc_beacon_batch_verification(self):
        """Test batch verification of multiple beacons"""
        pqc = PQMeshSecurityLibOQS(node_id="batch-test")

        beacons = [f"beacon-{i}".encode() for i in range(10)]
        signatures = [pqc.sign_beacon(b) for b in beacons]

        for beacon, sig in zip(beacons, signatures):
            assert pqc.verify_beacon(beacon, sig, pqc.sig_keypair.public_key) is True
