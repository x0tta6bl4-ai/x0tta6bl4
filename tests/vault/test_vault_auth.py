"""
Unit tests for K8sAuthHandler.
"""

from datetime import datetime, timedelta

import pytest

from src.security.vault_auth import K8sAuthConfig, K8sAuthHandler


class TestK8sAuthConfig:
    """Test K8sAuthConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = K8sAuthConfig(role="test-role")

        assert config.role == "test-role"
        assert config.jwt_path == "/var/run/secrets/kubernetes.io/serviceaccount/token"
        assert (
            config.ca_cert_path
            == "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
        )
        assert (
            config.namespace_path
            == "/var/run/secrets/kubernetes.io/serviceaccount/namespace"
        )
        assert config.token_expiry_days == 80

    def test_custom_config(self):
        """Test custom configuration values."""
        config = K8sAuthConfig(
            role="custom-role",
            jwt_path="/custom/jwt",
            ca_cert_path="/custom/ca.crt",
            namespace_path="/custom/namespace",
            token_expiry_days=30,
        )

        assert config.role == "custom-role"
        assert config.jwt_path == "/custom/jwt"
        assert config.ca_cert_path == "/custom/ca.crt"
        assert config.namespace_path == "/custom/namespace"
        assert config.token_expiry_days == 30


class TestK8sAuthHandlerJWT:
    """Test JWT token handling."""

    def test_get_jwt_success(self, k8s_auth_handler):
        """Test successful JWT retrieval."""
        jwt = k8s_auth_handler.get_jwt()

        assert jwt == "test-jwt-token"
        assert k8s_auth_handler._jwt_expiry is not None

    def test_get_jwt_caching(self, k8s_auth_handler):
        """Test JWT caching."""
        # First call
        jwt1 = k8s_auth_handler.get_jwt()

        # Second call should return cached value
        jwt2 = k8s_auth_handler.get_jwt()

        assert jwt1 == jwt2
        assert k8s_auth_handler._jwt == jwt1

    def test_get_jwt_cache_expiry(self, k8s_auth_handler):
        """Test JWT cache expiry."""
        # Get JWT and set expiry to past
        k8s_auth_handler.get_jwt()
        k8s_auth_handler._jwt_expiry = datetime.now() - timedelta(seconds=1)

        # Modify file content
        with open(k8s_auth_handler.config.jwt_path, "w") as f:
            f.write("new-jwt-token")

        # Should read new token
        jwt = k8s_auth_handler.get_jwt()
        assert jwt == "new-jwt-token"

    def test_get_jwt_file_not_found(self, tmp_path):
        """Test JWT file not found error."""
        config = K8sAuthConfig(
            role="test",
            jwt_path=str(tmp_path / "nonexistent"),
        )
        handler = K8sAuthHandler(config)

        with pytest.raises(FileNotFoundError):
            handler.get_jwt()

    def test_get_jwt_io_error(self, monkeypatch, k8s_auth_handler):
        """Test JWT read IOError path."""
        monkeypatch.setattr(
            "builtins.open",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(IOError("read failed")),
        )
        with pytest.raises(IOError):
            k8s_auth_handler.get_jwt()


class TestK8sAuthHandlerNamespace:
    """Test namespace handling."""

    def test_get_namespace_success(self, k8s_auth_handler):
        """Test successful namespace retrieval."""
        namespace = k8s_auth_handler.get_namespace()

        assert namespace == "test-namespace"
        assert k8s_auth_handler._namespace == "test-namespace"

    def test_get_namespace_caching(self, k8s_auth_handler):
        """Test namespace caching."""
        # First call
        ns1 = k8s_auth_handler.get_namespace()

        # Second call should return cached value
        ns2 = k8s_auth_handler.get_namespace()

        assert ns1 == ns2

    def test_get_namespace_file_not_found(self, tmp_path):
        """Test namespace file not found error."""
        config = K8sAuthConfig(
            role="test",
            namespace_path=str(tmp_path / "nonexistent"),
        )
        handler = K8sAuthHandler(config)

        with pytest.raises(FileNotFoundError):
            handler.get_namespace()


class TestK8sAuthHandlerCACert:
    """Test CA certificate handling."""

    def test_get_ca_cert_success(self, k8s_auth_handler):
        """Test successful CA cert retrieval."""
        ca_cert = k8s_auth_handler.get_ca_cert()

        assert ca_cert == "test-ca-cert"
        assert k8s_auth_handler._ca_cert == "test-ca-cert"

    def test_get_ca_cert_caching(self, k8s_auth_handler):
        """Test CA cert caching."""
        # First call
        cert1 = k8s_auth_handler.get_ca_cert()

        # Second call should return cached value
        cert2 = k8s_auth_handler.get_ca_cert()

        assert cert1 == cert2

    def test_get_ca_cert_file_not_found(self, tmp_path):
        """Test CA cert file not found error."""
        config = K8sAuthConfig(
            role="test",
            ca_cert_path=str(tmp_path / "nonexistent"),
        )
        handler = K8sAuthHandler(config)

        with pytest.raises(FileNotFoundError):
            handler.get_ca_cert()


class TestK8sAuthHandlerValidation:
    """Test K8s environment validation."""

    def test_validate_running_in_k8s_true(self, k8s_auth_handler):
        """Test validation when all files exist."""
        assert k8s_auth_handler.validate_running_in_k8s() is True

    def test_validate_running_in_k8s_missing_jwt(self, k8s_auth_handler):
        """Test validation when JWT file is missing."""
        import os

        os.remove(k8s_auth_handler.config.jwt_path)

        assert k8s_auth_handler.validate_running_in_k8s() is False

    def test_validate_running_in_k8s_missing_ca(self, k8s_auth_handler):
        """Test validation when CA cert file is missing."""
        import os

        os.remove(k8s_auth_handler.config.ca_cert_path)

        assert k8s_auth_handler.validate_running_in_k8s() is False

    def test_validate_running_in_k8s_missing_namespace(self, k8s_auth_handler):
        """Test validation when namespace file is missing."""
        import os

        os.remove(k8s_auth_handler.config.namespace_path)

        assert k8s_auth_handler.validate_running_in_k8s() is False

    def test_validate_running_in_k8s_no_files(self, tmp_path):
        """Test validation when no K8s files exist."""
        config = K8sAuthConfig(
            role="test",
            jwt_path=str(tmp_path / "jwt"),
            ca_cert_path=str(tmp_path / "ca"),
            namespace_path=str(tmp_path / "ns"),
        )
        handler = K8sAuthHandler(config)

        assert handler.validate_running_in_k8s() is False


class TestK8sAuthHandlerPodInfo:
    """Test pod info retrieval."""

    def test_get_pod_info_complete(self, k8s_auth_handler):
        """Test getting complete pod info."""
        info = k8s_auth_handler.get_pod_info()

        assert info["in_kubernetes"] is True
        assert info["namespace"] == "test-namespace"
        assert info["jwt_available"] is True
        assert info["ca_cert_available"] is True

    def test_get_pod_info_partial(self, tmp_path):
        """Test getting pod info with missing files."""
        # Create only namespace file
        ns_file = tmp_path / "namespace"
        ns_file.write_text("test-ns")

        config = K8sAuthConfig(
            role="test",
            jwt_path=str(tmp_path / "jwt"),
            ca_cert_path=str(tmp_path / "ca"),
            namespace_path=str(ns_file),
        )
        handler = K8sAuthHandler(config)

        info = handler.get_pod_info()

        assert info["in_kubernetes"] is False
        assert info["namespace"] == "test-ns"
        assert info["jwt_available"] is False
        assert info["ca_cert_available"] is False

    def test_get_pod_info_missing_namespace_only(self, tmp_path):
        """Namespace lookup failure is handled while other fields still resolve."""
        jwt_file = tmp_path / "token"
        ca_file = tmp_path / "ca.crt"
        jwt_file.write_text("jwt-token")
        ca_file.write_text("ca-cert")

        config = K8sAuthConfig(
            role="test",
            jwt_path=str(jwt_file),
            ca_cert_path=str(ca_file),
            namespace_path=str(tmp_path / "missing-namespace"),
        )
        handler = K8sAuthHandler(config)

        info = handler.get_pod_info()

        assert info["in_kubernetes"] is False
        assert info["namespace"] is None
        assert info["jwt_available"] is True
        assert info["ca_cert_available"] is True


class TestK8sAuthHandlerCacheClear:
    """Test cache clearing."""

    def test_clear_cache(self, k8s_auth_handler):
        """Test clearing all cached data."""
        # Populate cache
        k8s_auth_handler.get_jwt()
        k8s_auth_handler.get_namespace()
        k8s_auth_handler.get_ca_cert()

        # Clear cache
        k8s_auth_handler.clear_cache()

        assert k8s_auth_handler._jwt is None
        assert k8s_auth_handler._jwt_expiry is None
        assert k8s_auth_handler._namespace is None
        assert k8s_auth_handler._ca_cert is None
