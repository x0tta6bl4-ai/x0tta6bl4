"""Unit tests for SecretsManager (secrets_manager.py)."""
import os
import pytest
from unittest.mock import MagicMock, patch


class TestSecretsManagerInit:
    def test_disabled_when_no_vault_env(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("hvac.Client") as mock_hvac:
                from importlib import import_module
                import src.security.secrets_manager as sm_mod
                manager = sm_mod.SecretsManager()
                assert manager._enabled is False

    def test_enabled_when_vault_authenticated(self):
        env = {"VAULT_ADDR": "http://vault:8200", "VAULT_TOKEN": "tok"}
        with patch.dict(os.environ, env):
            mock_client = MagicMock()
            mock_client.is_authenticated.return_value = True
            with patch("hvac.Client", return_value=mock_client):
                import src.security.secrets_manager as sm_mod
                manager = sm_mod.SecretsManager()
                assert manager._enabled is True

    def test_disabled_when_vault_not_authenticated(self):
        env = {"VAULT_ADDR": "http://vault:8200", "VAULT_TOKEN": "bad"}
        with patch.dict(os.environ, env):
            mock_client = MagicMock()
            mock_client.is_authenticated.return_value = False
            with patch("hvac.Client", return_value=mock_client):
                import src.security.secrets_manager as sm_mod
                manager = sm_mod.SecretsManager()
                assert manager._enabled is False

    def test_disabled_when_vault_raises(self):
        env = {"VAULT_ADDR": "http://vault:8200", "VAULT_TOKEN": "tok"}
        with patch.dict(os.environ, env):
            with patch("hvac.Client", side_effect=Exception("conn refused")):
                import src.security.secrets_manager as sm_mod
                manager = sm_mod.SecretsManager()
                assert manager._enabled is False


class TestGetSecret:
    def _make_manager(self, enabled=False, vault_response=None):
        import src.security.secrets_manager as sm_mod
        manager = sm_mod.SecretsManager.__new__(sm_mod.SecretsManager)
        manager.vault_url = "http://vault:8200"
        manager.vault_token = "tok"
        manager.mount_point = "secret"
        manager._enabled = enabled
        if enabled:
            mock_client = MagicMock()
            if vault_response is not None:
                mock_client.secrets.kv.v2.read_secret_version.return_value = vault_response
            manager.client = mock_client
        else:
            manager.client = None
        return manager

    def test_fallback_to_env_when_disabled(self):
        with patch.dict(os.environ, {"MYPATH_VALUE": "env-secret"}):
            manager = self._make_manager(enabled=False)
            result = manager.get_secret("mypath", "value")
            assert result == "env-secret"

    def test_env_key_conversion(self):
        with patch.dict(os.environ, {"MY_PATH_KEY": "converted"}):
            manager = self._make_manager(enabled=False)
            result = manager.get_secret("my/path", "key")
            assert result == "converted"

    def test_returns_none_when_no_env(self):
        with patch.dict(os.environ, {}, clear=True):
            manager = self._make_manager(enabled=False)
            result = manager.get_secret("missing/path", "value")
            assert result is None

    def test_vault_hit_returns_value(self):
        vault_resp = {"data": {"data": {"value": "vault-secret"}}}
        manager = self._make_manager(enabled=True, vault_response=vault_resp)
        result = manager.get_secret("mypath", "value")
        assert result == "vault-secret"

    def test_vault_exception_falls_back_to_env(self):
        with patch.dict(os.environ, {"MYPATH_VALUE": "fallback"}):
            manager = self._make_manager(enabled=True)
            manager.client.secrets.kv.v2.read_secret_version.side_effect = Exception("oops")
            result = manager.get_secret("mypath", "value")
            assert result == "fallback"


class TestSetSecret:
    def _make_manager(self, enabled=False):
        import src.security.secrets_manager as sm_mod
        manager = sm_mod.SecretsManager.__new__(sm_mod.SecretsManager)
        manager.mount_point = "secret"
        manager._enabled = enabled
        if enabled:
            manager.client = MagicMock()
        else:
            manager.client = None
        return manager

    def test_returns_false_when_disabled(self):
        manager = self._make_manager(enabled=False)
        assert manager.set_secret("path", {"key": "val"}) is False

    def test_returns_true_on_success(self):
        manager = self._make_manager(enabled=True)
        result = manager.set_secret("path", {"key": "val"})
        assert result is True

    def test_returns_false_on_vault_error(self):
        manager = self._make_manager(enabled=True)
        manager.client.secrets.kv.v2.create_or_update_secret.side_effect = Exception("err")
        result = manager.set_secret("path", {"key": "val"})
        assert result is False


class TestPqcKeypair:
    def _make_manager(self, pub_hex=None, priv_hex=None):
        import src.security.secrets_manager as sm_mod
        manager = sm_mod.SecretsManager.__new__(sm_mod.SecretsManager)
        manager.mount_point = "secret"
        manager._enabled = False
        manager.client = None

        def fake_get_secret(path, key="value"):
            if key == "public_hex":
                return pub_hex
            if key == "private_hex":
                return priv_hex
            return None

        manager.get_secret = fake_get_secret
        return manager

    def test_returns_bytes_when_both_present(self):
        pub = b"\x01\x02\x03"
        priv = b"\x04\x05\x06"
        manager = self._make_manager(pub.hex(), priv.hex())
        p, k = manager.get_pqc_keypair("key-1")
        assert p == pub
        assert k == priv

    def test_returns_none_none_when_missing(self):
        manager = self._make_manager(None, None)
        p, k = manager.get_pqc_keypair("key-1")
        assert p is None
        assert k is None

    def test_store_calls_set_secret(self):
        import src.security.secrets_manager as sm_mod
        manager = sm_mod.SecretsManager.__new__(sm_mod.SecretsManager)
        manager.mount_point = "secret"
        manager._enabled = False
        manager.client = None
        calls = []
        manager.set_secret = lambda path, data: calls.append((path, data)) or True
        pub = b"\xaa\xbb"
        priv = b"\xcc\xdd"
        result = manager.store_pqc_keypair("k1", pub, priv)
        assert result is True
        assert calls[0][0] == "pqc/k1"
        assert calls[0][1]["public_hex"] == pub.hex()
        assert calls[0][1]["private_hex"] == priv.hex()
