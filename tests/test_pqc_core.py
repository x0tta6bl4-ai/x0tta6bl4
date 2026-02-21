"""
Tests for Post-Quantum Cryptography modules.

Run: python -m pytest tests/test_pqc_core.py -v
"""

import pytest


class TestLibx0tPQC:
    """Tests for libx0t/crypto/pqc.py"""

    def test_import_pqc_module(self):
        """Test that PQC module can be imported."""
        from libx0t.crypto.pqc import PQC

        assert PQC is not None

    def test_pqc_initialization(self):
        """Test PQC class initialization."""
        from libx0t.crypto.pqc import PQC

        pqc = PQC(algorithm="Kyber768")
        assert pqc.algorithm == "Kyber768"

    def test_pqc_keypair_generation(self):
        """Test keypair generation."""
        from libx0t.crypto.pqc import PQC

        pqc = PQC(algorithm="Kyber768")
        public_key, private_key = pqc.generate_keypair()

        assert len(public_key) == 1184  # Kyber768 public key size
        assert len(private_key) == 2400  # Kyber768 private key size

    def test_pqc_encapsulation(self):
        """Test KEM encapsulation."""
        from libx0t.crypto.pqc import PQC

        pqc = PQC(algorithm="Kyber768")
        public_key, private_key = pqc.generate_keypair()

        shared_secret, ciphertext = pqc.encapsulate(public_key)

        assert len(shared_secret) == 32  # 256-bit shared secret
        assert len(ciphertext) == 1088  # Kyber768 ciphertext size

    def test_pqc_decapsulation(self):
        """Test KEM decapsulation."""
        from libx0t.crypto.pqc import PQC

        pqc = PQC(algorithm="Kyber768")
        public_key, private_key = pqc.generate_keypair()

        shared_secret_enc, ciphertext = pqc.encapsulate(public_key)
        shared_secret_dec = pqc.decapsulate(ciphertext, private_key)

        assert shared_secret_enc == shared_secret_dec


class TestQuadraticVoting:
    """Tests for DAO Quadratic Voting."""

    def test_votes_to_cost(self):
        """Test quadratic cost calculation."""
        from src.dao.quadratic_voting import QuadraticVoting

        qv = QuadraticVoting()

        # 5 votes should cost 25 tokens (5²)
        assert qv.votes_to_cost(5) == 25
        assert qv.votes_to_cost(10) == 100
        assert qv.votes_to_cost(1) == 1

    def test_tokens_to_votes(self):
        """Test voting power calculation."""
        from src.dao.quadratic_voting import QuadraticVoting

        qv = QuadraticVoting()

        # 100 tokens → 10 votes (√100)
        assert qv.tokens_to_votes(100) == 10
        assert qv.tokens_to_votes(10000) == 100
        assert qv.tokens_to_votes(0) == 0

    def test_validate_vote(self):
        """Test vote validation."""
        from src.dao.quadratic_voting import QuadraticVoting

        qv = QuadraticVoting()

        # 100 tokens → max 10 votes, cost 100 tokens
        assert qv.validate_vote(100, 10) is True  # Valid: 10 votes, cost 100
        assert qv.validate_vote(100, 11) is False  # Invalid: 11 > 10 max votes


class TestMAPEK:
    """Tests for MAPE-K self-healing."""

    def test_mapek_monitor(self):
        """Test MAPE-K Monitor phase."""
        from src.self_healing.mape_k import MAPEKMonitor

        monitor = MAPEKMonitor()

        # Normal metrics should not trigger
        normal_metrics = {"cpu_percent": 50, "memory_percent": 60}
        assert monitor.check(normal_metrics) is False

        # Critical metrics should trigger
        critical_metrics = {"cpu_percent": 95, "memory_percent": 90}
        assert monitor.check(critical_metrics) is True

    def test_mapek_analyzer(self):
        """Test MAPE-K Analyzer phase."""
        from src.self_healing.mape_k import MAPEKAnalyzer

        analyzer = MAPEKAnalyzer()

        # High CPU should be detected
        result = analyzer.analyze({"cpu_percent": 95}, node_id="test")
        assert "High CPU" in result

        # Normal metrics should return Healthy
        result = analyzer.analyze({"cpu_percent": 50}, node_id="test")
        assert result == "Healthy"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
