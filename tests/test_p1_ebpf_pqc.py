import os
import unittest
from unittest.mock import MagicMock, patch
import logging

# Set stub mode for EBPF validation without root
os.environ["BCC_STUB_MODE"] = "true"

# Add current directory to sys.path if not already there
import sys
if "." not in sys.path:
    sys.path.append(".")

# Force BCC_AVAILABLE to False before importing EBPFLoader
import src.network.ebpf.ebpf_loader
src.network.ebpf.ebpf_loader.BCC_AVAILABLE = False

from src.security.pqc_ebpf_integration import EnhancedPQCPerformanceOptimizer
from src.libx0t.security.post_quantum import LibOQSBackend

logging.basicConfig(level=logging.INFO)

class TestPQCeBPFIntegration(unittest.TestCase):
    def setUp(self):
        # Ensure we are in stub mode
        os.environ["BCC_STUB_MODE"] = "true"
        self.optimizer = EnhancedPQCPerformanceOptimizer(
            enable_cache=True,
            enable_ebpf=True
        )
        self.backend = LibOQSBackend(kem_algorithm="ML-KEM-768")

    def test_ebpf_accelerator_initialization(self):
        """Test that accelerator initializes in stub mode."""
        acc = self.optimizer.ebpf_accelerator
        self.assertTrue(acc.is_available(), "eBPF accelerator should be available in stub mode")
        self.assertIsNotNone(acc.program, "eBPF program should be loaded")
        
        print(f"DEBUG: program.bpf type: {type(acc.program.bpf)}")
        
        # Trigger map initialization by doing a lookup
        acc.lookup_session_key_ebpf("dummy", b"")
        
        print(f"DEBUG: maps keys: {list(acc.program.bpf._maps.keys())}")
        
        # In stub mode, bpf is a StubEBPFProgram object
        self.assertIn("pqc_keys", acc.program.bpf._maps)

    def test_optimized_handshake_with_ebpf_cache(self):
        """Test handshake with eBPF caching logic."""
        peer_id = "test-peer-123"
        acc = self.optimizer.ebpf_accelerator
        
        # Generate a VALID public key for ML-KEM-768
        keypair = self.backend.generate_kem_keypair()
        peer_public_key = keypair.public_key
        
        # First handshake: should be user_space (miss)
        shared_secret1, metrics1 = self.optimizer.optimized_handshake_with_ebpf(
            peer_id, peer_public_key
        )
        
        self.assertEqual(metrics1["source"], "user_space")
        
        # Check map content directly
        pqc_keys_map = acc.program.bpf["pqc_keys"]
        print(f"DEBUG: map size after cache: {len(pqc_keys_map._data)}")
        
        # Verify it was cached in eBPF via lookup
        cached_key = acc.lookup_session_key_ebpf(peer_id, b"")
        self.assertIsNotNone(cached_key, "Key should be found in eBPF cache")
        self.assertEqual(cached_key[:32], shared_secret1[:32])

        # Second handshake: should be ebpf (hit)
        shared_secret2, metrics2 = self.optimizer.optimized_handshake_with_ebpf(
            peer_id, peer_public_key
        )
        
        self.assertEqual(metrics2["source"], "ebpf")
        self.assertTrue(metrics2["cache_hit"])
        self.assertEqual(shared_secret1[:32], shared_secret2[:32])

if __name__ == "__main__":
    unittest.main()
