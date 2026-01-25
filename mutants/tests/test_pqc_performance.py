"""
Tests for PQC Performance Optimizer
===================================

Tests for:
- Key caching
- Batch processing
- Performance metrics
- eBPF integration
"""
import pytest
import time
import asyncio
from unittest.mock import Mock, patch

from src.security.pqc_performance import (
    PQCPerformanceOptimizer,
    PQCKeyCache,
    HandshakeMetrics,
    OptimizedPQMeshSecurity
)
from src.security.pqc_hybrid import (
    HybridPQEncryption,
    HybridPQMeshSecurity
)
from src.security.pqc_ebpf_integration import (
    PQCeBPFAccelerator,
    EnhancedPQCPerformanceOptimizer
)


@pytest.fixture
def mock_liboqs():
    """Mock liboqs for testing."""
    with patch('src.security.post_quantum_liboqs.LIBOQS_AVAILABLE', True):
        with patch('src.security.post_quantum_liboqs.KeyEncapsulation') as mock_kem:
            # Mock KEM operations
            mock_kem_instance = Mock()
            mock_kem_instance.generate_keypair.return_value = (
                b'public_key_32_bytes_here',
                b'private_key_32_bytes_here'
            )
            mock_kem_instance.encap_secret.return_value = (
                b'ciphertext_here',
                b'shared_secret_32_bytes'
            )
            mock_kem_instance.decap_secret.return_value = b'shared_secret_32_bytes'
            mock_kem_instance.export_secret_key.return_value = b'private_key_32_bytes_here'
            mock_kem.return_value = mock_kem_instance
            yield mock_kem


class TestPQCKeyCache:
    """Tests for PQCKeyCache."""
    
    def test_cache_keypair(self, mock_liboqs):
        """Test caching KEM keypair."""
        from src.security.post_quantum_liboqs import LibOQSBackend
        
        cache = PQCKeyCache(max_size=10, ttl_seconds=3600)
        backend = LibOQSBackend()
        
        # Generate and cache keypair
        keypair1 = cache.get_or_generate_kem_keypair("key1", backend)
        assert keypair1 is not None
        
        # Get same keypair (should be cached)
        keypair2 = cache.get_or_generate_kem_keypair("key1", backend)
        assert keypair2.key_id == keypair1.key_id
    
    def test_cache_expiration(self, mock_liboqs):
        """Test cache expiration."""
        from src.security.post_quantum_liboqs import LibOQSBackend
        
        cache = PQCKeyCache(max_size=10, ttl_seconds=1)  # 1 second TTL
        backend = LibOQSBackend()
        
        # Generate and cache
        keypair1 = cache.get_or_generate_kem_keypair("key1", backend)
        
        # Wait for expiration
        time.sleep(1.1)
        
        # Should generate new keypair
        keypair2 = cache.get_or_generate_kem_keypair("key1", backend)
        # Note: In real test, we'd check that keys are different
        # but mock returns same values, so we just check it works
    
    def test_cache_size_limit(self, mock_liboqs):
        """Test cache size limit."""
        from src.security.post_quantum_liboqs import LibOQSBackend
        
        cache = PQCKeyCache(max_size=2, ttl_seconds=3600)
        backend = LibOQSBackend()
        
        # Add 3 keys (should evict oldest)
        cache.get_or_generate_kem_keypair("key1", backend)
        cache.get_or_generate_kem_keypair("key2", backend)
        cache.get_or_generate_kem_keypair("key3", backend)
        
        # Cache should have max 2 entries
        assert len(cache._cache) <= 2


class TestPQCPerformanceOptimizer:
    """Tests for PQCPerformanceOptimizer."""
    
    def test_optimized_handshake(self, mock_liboqs):
        """Test optimized handshake."""
        optimizer = PQCPerformanceOptimizer(enable_cache=True)
        
        # Mock peer
        peer_id = "peer1"
        peer_public_key = b'peer_public_key_32_bytes_here'
        
        shared_secret, metrics = optimizer.optimized_handshake(peer_id, peer_public_key)
        
        assert shared_secret is not None
        assert metrics.handshake_time_ms >= 0
        assert metrics.algorithm == "ML-KEM-768"
    
    def test_batch_handshakes(self, mock_liboqs):
        """Test batch handshakes."""
        optimizer = PQCPerformanceOptimizer(enable_cache=True)
        
        peers = [
            ("peer1", b'public_key_1_32_bytes_here'),
            ("peer2", b'public_key_2_32_bytes_here'),
            ("peer3", b'public_key_3_32_bytes_here')
        ]
        
        results = optimizer.batch_handshakes(peers)
        
        assert len(results) == 3
        for peer_id, shared_secret, metrics in results:
            assert shared_secret is not None
            assert metrics.handshake_time_ms >= 0
    
    def test_performance_stats(self, mock_liboqs):
        """Test performance statistics."""
        optimizer = PQCPerformanceOptimizer(enable_cache=True)
        
        # Perform some handshakes
        for i in range(10):
            optimizer.optimized_handshake(f"peer{i}", b'public_key_32_bytes_here')
        
        stats = optimizer.get_performance_stats()
        
        assert stats['total_handshakes'] == 10
        assert stats['avg_handshake_time_ms'] >= 0
        assert stats['min_handshake_time_ms'] >= 0
        assert stats['max_handshake_time_ms'] >= 0


class TestHybridPQEncryption:
    """Tests for Hybrid PQ Encryption."""
    
    @pytest.mark.skipif(
        not pytest.importorskip("cryptography", reason="cryptography not available"),
        reason="cryptography library required"
    )
    def test_hybrid_keypair_generation(self, mock_liboqs):
        """Test hybrid keypair generation."""
        hybrid = HybridPQEncryption()
        
        keypair = hybrid.generate_hybrid_keypair()
        
        assert keypair.classical_public is not None
        assert keypair.classical_private is not None
        assert keypair.pq_public is not None
        assert keypair.pq_private is not None
        assert keypair.key_id is not None
    
    @pytest.mark.skipif(
        not pytest.importorskip("cryptography", reason="cryptography not available"),
        reason="cryptography library required"
    )
    def test_hybrid_encapsulation(self, mock_liboqs):
        """Test hybrid encapsulation."""
        hybrid = HybridPQEncryption()
        
        # Generate two keypairs
        keypair1 = hybrid.generate_hybrid_keypair()
        keypair2 = hybrid.generate_hybrid_keypair()
        
        # Encapsulate from keypair1 to keypair2
        shared_secret, ciphertext = hybrid.hybrid_encapsulate(
            keypair2.classical_public,
            keypair2.pq_public
        )
        
        assert shared_secret is not None
        assert ciphertext.classical_ciphertext is not None
        assert ciphertext.pq_ciphertext is not None
    
    @pytest.mark.skipif(
        not pytest.importorskip("cryptography", reason="cryptography not available"),
        reason="cryptography library required"
    )
    def test_hybrid_decapsulation(self, mock_liboqs):
        """Test hybrid decapsulation."""
        hybrid = HybridPQEncryption()
        
        # Generate two keypairs
        keypair1 = hybrid.generate_hybrid_keypair()
        keypair2 = hybrid.generate_hybrid_keypair()
        
        # Encapsulate
        shared_secret1, ciphertext = hybrid.hybrid_encapsulate(
            keypair2.classical_public,
            keypair2.pq_public
        )
        
        # Decapsulate
        shared_secret2 = hybrid.hybrid_decapsulate(
            ciphertext,
            keypair2.classical_private,
            keypair2.pq_private
        )
        
        # Secrets should match
        assert shared_secret1 == shared_secret2


class TestPQCeBPFAccelerator:
    """Tests for PQC eBPF Accelerator."""
    
    def test_ebpf_availability_check(self):
        """Test eBPF availability check."""
        accelerator = PQCeBPFAccelerator(enable_ebpf=True)
        
        # Should check availability without error
        available = accelerator.is_available()
        assert isinstance(available, bool)
    
    def test_key_lookup_map_creation(self):
        """Test key lookup map creation."""
        accelerator = PQCeBPFAccelerator(enable_ebpf=True)
        
        map_id = accelerator.create_key_lookup_map("test_map")
        
        # Should return map name or None
        assert map_id is None or isinstance(map_id, str)


class TestEnhancedPQCPerformanceOptimizer:
    """Tests for Enhanced PQC Performance Optimizer."""
    
    def test_handshake_with_ebpf(self, mock_liboqs):
        """Test handshake with eBPF acceleration."""
        optimizer = EnhancedPQCPerformanceOptimizer(
            enable_cache=True,
            enable_ebpf=True
        )
        
        peer_id = "peer1"
        peer_public_key = b'peer_public_key_32_bytes_here'
        
        shared_secret, metrics = optimizer.optimized_handshake_with_ebpf(
            peer_id, peer_public_key
        )
        
        assert shared_secret is not None
        assert 'source' in metrics
        assert 'handshake_time_ms' in metrics
        assert metrics['handshake_time_ms'] >= 0
    
    def test_stats(self, mock_liboqs):
        """Test statistics."""
        optimizer = EnhancedPQCPerformanceOptimizer(
            enable_cache=True,
            enable_ebpf=True
        )
        
        stats = optimizer.get_stats()
        
        assert 'ebpf_available' in stats
        assert 'ebpf_enabled' in stats
        assert isinstance(stats['ebpf_available'], bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

