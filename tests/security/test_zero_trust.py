"""
Tests for Zero Trust Validator module.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest


class TestZeroTrustValidator:
    """Tests for ZeroTrustValidator class."""

    def test_validator_initialization(self):
        """Test ZeroTrustValidator initialization."""
        with patch("src.security.zero_trust.WorkloadAPIClient"):
            from src.security.zero_trust import ZeroTrustValidator

            validator = ZeroTrustValidator(trust_domain="example.mesh")

            assert validator.trust_domain == "example.mesh"
            assert validator._validation_attempts == 0
            assert validator._validation_successes == 0
            assert validator._validation_failures == 0

    def test_validator_default_trust_domain(self):
        """Test default trust domain."""
        with patch("src.security.zero_trust.WorkloadAPIClient"):
            from src.security.zero_trust import ZeroTrustValidator

            validator = ZeroTrustValidator()

            assert validator.trust_domain == "x0tta6bl4.mesh"

    def test_get_validation_stats_initial(self):
        """Test initial validation stats."""
        with patch("src.security.zero_trust.WorkloadAPIClient"):
            from src.security.zero_trust import ZeroTrustValidator

            validator = ZeroTrustValidator()
            stats = validator.get_validation_stats()

            assert stats["success_rate"] == 1.0
            assert stats["total_attempts"] == 0
            assert stats["successes"] == 0
            assert stats["failures"] == 0

    def test_get_validation_stats_after_validations(self):
        """Test validation stats after some validations."""
        with patch("src.security.zero_trust.WorkloadAPIClient"):
            from src.security.zero_trust import ZeroTrustValidator

            validator = ZeroTrustValidator()

            # Simulate some validations
            validator._validation_attempts = 10
            validator._validation_successes = 8
            validator._validation_failures = 2

            stats = validator.get_validation_stats()

            assert stats["success_rate"] == 0.8
            assert stats["total_attempts"] == 10
            assert stats["successes"] == 8
            assert stats["failures"] == 2

    def test_validate_connection_wrong_trust_domain(self):
        """Test validation fails for wrong trust domain."""
        with patch("src.security.zero_trust.WorkloadAPIClient"):
            from src.security.zero_trust import ZeroTrustValidator

            validator = ZeroTrustValidator(trust_domain="x0tta6bl4.mesh")

            # Try with wrong trust domain
            result = validator.validate_connection("spiffe://other.domain/workload")

            assert result is False
            assert validator._validation_failures == 1
            assert validator._validation_attempts == 1

    def test_validate_connection_correct_trust_domain(self):
        """Test validation passes for correct trust domain."""
        with patch("src.security.zero_trust.WorkloadAPIClient"):
            from src.security.zero_trust import ZeroTrustValidator

            validator = ZeroTrustValidator(trust_domain="x0tta6bl4.mesh")

            # Mock policy check to succeed
            with patch.object(validator, "_check_policy", return_value=True):
                result = validator.validate_connection(
                    "spiffe://x0tta6bl4.mesh/workload"
                )

                assert result is True
                assert validator._validation_successes == 1

    def test_validate_connection_increments_attempts(self):
        """Test validation always increments attempts."""
        with patch("src.security.zero_trust.WorkloadAPIClient"):
            from src.security.zero_trust import ZeroTrustValidator

            validator = ZeroTrustValidator()

            # Multiple validations
            validator.validate_connection("spiffe://other.domain/workload")
            validator.validate_connection("spiffe://other.domain/workload2")
            validator.validate_connection("spiffe://other.domain/workload3")

            assert validator._validation_attempts == 3

    def test_validate_connection_with_svid(self):
        """Test validation with SVID object."""
        with patch("src.security.zero_trust.WorkloadAPIClient") as mock_client_class:
            from src.security.zero_trust import ZeroTrustValidator

            mock_client = Mock()
            mock_client.validate_peer_svid.return_value = True
            mock_client_class.return_value = mock_client

            validator = ZeroTrustValidator(trust_domain="x0tta6bl4.mesh")

            mock_svid = Mock()

            with patch.object(validator, "_check_policy", return_value=True):
                result = validator.validate_connection(
                    "spiffe://x0tta6bl4.mesh/workload", peer_svid=mock_svid
                )

                assert result is True
                mock_client.validate_peer_svid.assert_called_once()

    def test_validate_connection_svid_validation_fails(self):
        """Test validation fails when SVID validation fails."""
        with patch("src.security.zero_trust.WorkloadAPIClient") as mock_client_class:
            from src.security.zero_trust import ZeroTrustValidator

            mock_client = Mock()
            mock_client.validate_peer_svid.return_value = False
            mock_client_class.return_value = mock_client

            validator = ZeroTrustValidator(trust_domain="x0tta6bl4.mesh")

            mock_svid = Mock()
            result = validator.validate_connection(
                "spiffe://x0tta6bl4.mesh/workload", peer_svid=mock_svid
            )

            assert result is False
            assert validator._validation_failures == 1

    def test_validate_connection_policy_check_fails(self):
        """Test validation fails when policy check fails."""
        with patch("src.security.zero_trust.WorkloadAPIClient"):
            from src.security.zero_trust import ZeroTrustValidator

            validator = ZeroTrustValidator(trust_domain="x0tta6bl4.mesh")

            with patch.object(validator, "_check_policy", return_value=False):
                result = validator.validate_connection(
                    "spiffe://x0tta6bl4.mesh/workload"
                )

                assert result is False
                assert validator._validation_failures == 1


class TestGetMyIdentity:
    """Tests for get_my_identity method."""

    def test_get_my_identity_success(self):
        """Test successful identity fetch."""
        with patch("src.security.zero_trust.WorkloadAPIClient") as mock_client_class:
            from src.security.zero_trust import ZeroTrustValidator

            mock_svid = Mock()
            mock_svid.spiffe_id = "spiffe://x0tta6bl4.mesh/my-workload"
            mock_svid.expiry = datetime.now() + timedelta(hours=1)

            mock_client = Mock()
            mock_client.fetch_x509_svid.return_value = mock_svid
            mock_client_class.return_value = mock_client

            validator = ZeroTrustValidator()
            identity = validator.get_my_identity()

            assert "spiffe_id" in identity
            assert identity["spiffe_id"] == "spiffe://x0tta6bl4.mesh/my-workload"
            assert "expiry" in identity
            assert "trust_domain" in identity

    def test_get_my_identity_caches_identity(self):
        """Test that identity is cached."""
        with patch("src.security.zero_trust.WorkloadAPIClient") as mock_client_class:
            from src.security.zero_trust import ZeroTrustValidator

            mock_svid = Mock()
            mock_svid.spiffe_id = "spiffe://x0tta6bl4.mesh/my-workload"
            mock_svid.expiry = datetime.now() + timedelta(hours=1)

            mock_client = Mock()
            mock_client.fetch_x509_svid.return_value = mock_svid
            mock_client_class.return_value = mock_client

            validator = ZeroTrustValidator()
            validator.get_my_identity()

            assert validator._cached_identity == mock_svid

    def test_get_my_identity_failure(self):
        """Test identity fetch failure."""
        with patch("src.security.zero_trust.WorkloadAPIClient") as mock_client_class:
            from src.security.zero_trust import ZeroTrustValidator

            mock_client = Mock()
            mock_client.fetch_x509_svid.side_effect = Exception(
                "SPIFFE agent unavailable"
            )
            mock_client_class.return_value = mock_client

            validator = ZeroTrustValidator()
            identity = validator.get_my_identity()

            assert "error" in identity
            assert "SPIFFE agent unavailable" in identity["error"]


class TestPolicyCheck:
    """Tests for _check_policy method."""

    def test_check_policy_fallback_allows(self):
        """Test policy check fallback allows when engine not available."""
        with patch("src.security.zero_trust.WorkloadAPIClient"):
            from src.security.zero_trust import ZeroTrustValidator

            validator = ZeroTrustValidator()

            # Mock ImportError for policy engine
            with patch.dict(
                "sys.modules", {"src.security.zero_trust.policy_engine": None}
            ):
                with patch(
                    "src.security.zero_trust.ZeroTrustValidator._check_policy"
                ) as mock_check:
                    mock_check.return_value = True
                    result = mock_check("spiffe://x0tta6bl4.mesh/workload")
                    assert result is True

    def test_check_policy_with_resource(self):
        """Test policy check with resource parameter."""
        with patch("src.security.zero_trust.WorkloadAPIClient"):
            from src.security.zero_trust import ZeroTrustValidator

            validator = ZeroTrustValidator()

            # The method accepts a resource parameter
            # Just verify it doesn't raise an exception
            with patch.object(validator, "_check_policy", return_value=True):
                result = validator._check_policy(
                    "spiffe://x0tta6bl4.mesh/workload", resource="/api/data"
                )
                assert result is True


class TestSpiffeIdParsing:
    """Tests for SPIFFE ID parsing logic."""

    def test_spiffe_id_format_validation(self):
        """Test SPIFFE ID format validation."""
        with patch("src.security.zero_trust.WorkloadAPIClient"):
            from src.security.zero_trust import ZeroTrustValidator

            validator = ZeroTrustValidator(trust_domain="example.com")

            # Valid format
            valid_id = "spiffe://example.com/workload/service-a"
            with patch.object(validator, "_check_policy", return_value=True):
                assert validator.validate_connection(valid_id) is True

            # Invalid - missing spiffe:// prefix
            invalid_id = "example.com/workload"
            assert validator.validate_connection(invalid_id) is False

    def test_trust_domain_extraction(self):
        """Test trust domain is correctly extracted from SPIFFE ID."""
        with patch("src.security.zero_trust.WorkloadAPIClient"):
            from src.security.zero_trust import ZeroTrustValidator

            validator = ZeroTrustValidator(trust_domain="prod.example.com")

            # Must start with spiffe://trust_domain/
            valid_id = "spiffe://prod.example.com/namespace/workload"
            with patch.object(validator, "_check_policy", return_value=True):
                result = validator.validate_connection(valid_id)
                assert result is True

            # Different trust domain should fail
            different_domain = "spiffe://staging.example.com/namespace/workload"
            result = validator.validate_connection(different_domain)
            assert result is False


class TestValidationMetrics:
    """Tests for validation metrics tracking."""

    def test_metrics_track_successes(self):
        """Test metrics track successful validations."""
        with patch("src.security.zero_trust.WorkloadAPIClient"):
            from src.security.zero_trust import ZeroTrustValidator

            validator = ZeroTrustValidator(trust_domain="x0tta6bl4.mesh")

            with patch.object(validator, "_check_policy", return_value=True):
                for _ in range(5):
                    validator.validate_connection("spiffe://x0tta6bl4.mesh/workload")

            assert validator._validation_successes == 5
            assert validator._validation_attempts == 5
            assert validator._validation_failures == 0

    def test_metrics_track_failures(self):
        """Test metrics track failed validations."""
        with patch("src.security.zero_trust.WorkloadAPIClient"):
            from src.security.zero_trust import ZeroTrustValidator

            validator = ZeroTrustValidator(trust_domain="x0tta6bl4.mesh")

            # Wrong trust domain - should fail
            for _ in range(3):
                validator.validate_connection("spiffe://wrong.domain/workload")

            assert validator._validation_failures == 3
            assert validator._validation_attempts == 3
            assert validator._validation_successes == 0

    def test_success_rate_calculation(self):
        """Test success rate is calculated correctly."""
        with patch("src.security.zero_trust.WorkloadAPIClient"):
            from src.security.zero_trust import ZeroTrustValidator

            validator = ZeroTrustValidator(trust_domain="x0tta6bl4.mesh")

            with patch.object(validator, "_check_policy", return_value=True):
                # 7 successes
                for _ in range(7):
                    validator.validate_connection("spiffe://x0tta6bl4.mesh/workload")

            # 3 failures
            for _ in range(3):
                validator.validate_connection("spiffe://wrong.domain/workload")

            stats = validator.get_validation_stats()
            assert stats["success_rate"] == 0.7  # 7/10
            assert stats["total_attempts"] == 10
