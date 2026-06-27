"""
Integration tests for Global Formal Proof Registry and Inter-Plane Invariants.
"""

import unittest
from src.integration.formal_proof_registry import FormalProofRegistry

class TestGlobalFormalRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = FormalProofRegistry()

    def test_global_readiness_blocked_missing_planes(self):
        """Test that readiness is blocked if required planes are missing."""
        # Only register MAPE-K
        self.registry.register_proof("mape_k", {
            "schema": "x0tta6bl4.formal_proof.fragment.v1",
            "current_state": "IDLE",
            "safe_mode": False,
            "violations": []
        })

        proof = self.registry.get_global_readiness_proof()
        self.assertFalse(proof["ready"])
        self.assertEqual(proof["decision"], "GLOBAL_BLOCKED")
        self.assertIn("trust_pqc", proof["missing_planes"])
        self.assertIn("dataplane", proof["missing_planes"])

    def test_global_readiness_blocked_without_dataplane(self):
        """Test that readiness is blocked if dataplane proof is missing."""
        self.registry.register_proof("mape_k", {
            "schema": "x0tta6bl4.formal_proof.fragment.v1",
            "current_state": "IDLE",
            "safe_mode": False,
            "violations": []
        })
        self.registry.register_proof("trust_pqc", {
            "schema": "x0tta6bl4.trust_proof.fragment.v1",
            "current_trust_state": "STABLE",
            "violations": []
        })

        proof = self.registry.get_global_readiness_proof()
        self.assertFalse(proof["ready"])
        self.assertEqual(proof["decision"], "GLOBAL_BLOCKED")
        self.assertEqual(proof["missing_planes"], ["dataplane"])

    def test_global_readiness_ready(self):
        """Test successful global readiness consolidation."""
        self.registry.register_proof("mape_k", {
            "schema": "x0tta6bl4.formal_proof.fragment.v1",
            "current_state": "IDLE",
            "safe_mode": False,
            "violations": []
        })
        self.registry.register_proof("trust_pqc", {
            "schema": "x0tta6bl4.trust_proof.fragment.v1",
            "current_trust_state": "STABLE",
            "violations": []
        })
        self.registry.register_proof("dataplane", {
            "schema": "x0tta6bl4.dataplane_proof.fragment.v1",
            "current_state": "ATTACHED",
            "violations": []
        })

        proof = self.registry.get_global_readiness_proof()
        self.assertTrue(proof["ready"])
        self.assertEqual(proof["decision"], "GLOBAL_VERIFIED")

    def test_invariant_g1_violation(self):
        """Test G1: MAPE-K execution blocked if Trust Plane is unstable."""
        # 1. Register unstable Trust Plane (e.g. key generation in progress)
        self.registry.register_proof("trust_pqc", {
            "schema": "x0tta6bl4.trust_proof.fragment.v1",
            "current_trust_state": "GENERATING",
            "violations": []
        })

        # 2. Register MAPE-K in EXECUTING state
        self.registry.register_proof("mape_k", {
            "schema": "x0tta6bl4.formal_proof.fragment.v1",
            "current_state": "EXECUTING",
            "safe_mode": False,
            "violations": []
        })
        self.registry.register_proof("dataplane", {
            "schema": "x0tta6bl4.dataplane_proof.fragment.v1",
            "current_state": "ATTACHED",
            "violations": []
        })

        proof = self.registry.get_global_readiness_proof()
        self.assertFalse(proof["ready"])
        self.assertTrue(any("G1" in v for v in proof["global_violations"]))
        self.assertEqual(proof["shard_summaries"]["mape_k"]["state"], "EXECUTING")
        self.assertEqual(proof["shard_summaries"]["trust_pqc"]["state"], "GENERATING")

if __name__ == "__main__":
    unittest.main()
