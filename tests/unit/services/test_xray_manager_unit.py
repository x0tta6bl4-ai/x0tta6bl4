"""Unit tests for src/services/xray_manager.py (XrayManager / VLESS VPN config)."""

import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")

try:
    from src.services import xray_manager as mod

    MODULE_AVAILABLE = True
except Exception as exc:  # pragma: no cover - import guard
    MODULE_AVAILABLE = False
    IMPORT_ERROR = str(exc)


pytestmark = pytest.mark.skipif(
    not MODULE_AVAILABLE,
    reason=f"xray_manager module not available: {IMPORT_ERROR if not MODULE_AVAILABLE else ''}",
)


# ---------------------------------------------------------------------------
# generate_vless_link
# ---------------------------------------------------------------------------


class TestGenerateVlessLink:
    """Tests for XrayManager.generate_vless_link()."""

    def test_legacy_generator_is_preferred(self, monkeypatch):
        """When _gen_link_legacy is available it should be called instead of
        the fallback builder."""
        monkeypatch.setattr(
            mod,
            "_gen_link_legacy",
            lambda user_uuid, server, port: f"legacy://{user_uuid}@{server}:{port}",
        )
        monkeypatch.setenv("PUBLIC_DOMAIN", "public.example")

        link = mod.XrayManager.generate_vless_link("uuid-1", "mail@example.com", port=8443)
        assert link == "legacy://uuid-1@public.example:8443"

    def test_fallback_builder_format(self, monkeypatch):
        """Fallback builder must produce a well-formed vless:// URI with
        Reality parameters."""
        monkeypatch.setattr(mod, "_gen_link_legacy", None)
        monkeypatch.delenv("PUBLIC_DOMAIN", raising=False)
        monkeypatch.setenv("XRAY_HOST", "xray.example")
        monkeypatch.setenv("REALITY_PUBLIC_KEY", "test-pbk-value")
        monkeypatch.setenv("REALITY_SHORT_ID", "ab")

        link = mod.XrayManager.generate_vless_link("uuid-2", "user@test.com", port=443)
        assert link.startswith("vless://uuid-2@xray.example:443")
        assert "security=reality" in link
        assert "encryption=none" in link
        assert "type=ws" in link
        assert "sni=google.com" in link
        assert "fp=chrome" in link
        assert "path=%2Fvless" in link
        assert "pbk=test-pbk-value" in link
        assert "sid=ab" in link
        assert link.endswith("#user@test.com")

    def test_falls_back_to_localhost_when_no_env(self, monkeypatch):
        """Without PUBLIC_DOMAIN, XRAY_HOST, or an explicit server arg the
        host must default to 'localhost'."""
        monkeypatch.setattr(mod, "_gen_link_legacy", None)
        monkeypatch.delenv("PUBLIC_DOMAIN", raising=False)
        monkeypatch.delenv("XRAY_HOST", raising=False)
        monkeypatch.setenv("REALITY_PUBLIC_KEY", "test-pbk")

        link = mod.XrayManager.generate_vless_link("uuid-3", "anon@test.com")
        assert "vless://uuid-3@localhost:443" in link

    def test_explicit_server_overrides_env(self, monkeypatch):
        """An explicit ``server`` argument takes precedence over env vars."""
        monkeypatch.setattr(mod, "_gen_link_legacy", None)
        monkeypatch.setenv("PUBLIC_DOMAIN", "should-not-use.example")
        monkeypatch.setenv("REALITY_PUBLIC_KEY", "test-pbk")

        link = mod.XrayManager.generate_vless_link(
            "uuid-4", "explicit@test.com", server="custom.host", port=9443
        )
        assert "vless://uuid-4@custom.host:9443" in link

    def test_public_domain_takes_priority_over_xray_host(self, monkeypatch):
        """PUBLIC_DOMAIN must be preferred over XRAY_HOST."""
        monkeypatch.setattr(mod, "_gen_link_legacy", None)
        monkeypatch.setenv("PUBLIC_DOMAIN", "primary.example")
        monkeypatch.setenv("XRAY_HOST", "secondary.example")
        monkeypatch.setenv("REALITY_PUBLIC_KEY", "test-pbk")

        link = mod.XrayManager.generate_vless_link("uuid-5", "prio@test.com")
        assert "@primary.example:" in link

    def test_default_port_is_443(self, monkeypatch):
        monkeypatch.setattr(mod, "_gen_link_legacy", None)
        monkeypatch.delenv("PUBLIC_DOMAIN", raising=False)
        monkeypatch.delenv("XRAY_HOST", raising=False)
        monkeypatch.setenv("REALITY_PUBLIC_KEY", "test-pbk")

        link = mod.XrayManager.generate_vless_link("uuid-6", "default-port@test.com")
        assert "@localhost:443" in link

    def test_raises_without_reality_public_key(self, monkeypatch):
        """Must raise ValueError when REALITY_PUBLIC_KEY is not set."""
        monkeypatch.setattr(mod, "_gen_link_legacy", None)
        monkeypatch.delenv("REALITY_PUBLIC_KEY", raising=False)

        with pytest.raises(ValueError, match="REALITY_PUBLIC_KEY"):
            mod.XrayManager.generate_vless_link("uuid-err", "err@test.com")


# ---------------------------------------------------------------------------
# Security: hardcoded pbk / sid values
# ---------------------------------------------------------------------------


class TestNoHardcodedSecrets:
    """Verify that hardcoded pbk/sid values have been removed and replaced
    with environment variable lookups."""

    def test_no_hardcoded_pbk(self):
        """pbk must NOT be hardcoded — it should come from REALITY_PUBLIC_KEY env."""
        import inspect

        source = inspect.getsource(mod.XrayManager.generate_vless_link)
        assert "sARj3nxY80sVRmeCxqZbTHyw-bj6Si4vXb3Q-mlflFw" not in source
        assert 'os.getenv("REALITY_PUBLIC_KEY"' in source

    def test_no_hardcoded_sid(self):
        """sid must NOT be hardcoded — it should come from REALITY_SHORT_ID env."""
        import inspect

        source = inspect.getsource(mod.XrayManager.generate_vless_link)
        assert 'sid = "6b"' not in source
        assert 'os.getenv("REALITY_SHORT_ID"' in source

    def test_pbk_from_env_appears_in_link(self, monkeypatch):
        """pbk and sid from env vars must appear in the generated link."""
        monkeypatch.setattr(mod, "_gen_link_legacy", None)
        monkeypatch.delenv("PUBLIC_DOMAIN", raising=False)
        monkeypatch.delenv("XRAY_HOST", raising=False)
        monkeypatch.setenv("REALITY_PUBLIC_KEY", "env-pbk-value")
        monkeypatch.setenv("REALITY_SHORT_ID", "ff")

        link = mod.XrayManager.generate_vless_link("uuid-sec", "sec@test.com")
        assert "pbk=env-pbk-value" in link
        assert "sid=ff" in link


# ---------------------------------------------------------------------------
# add_user
# ---------------------------------------------------------------------------


def _write_xray_config(tmp_path, config_dict):
    """Helper: write a JSON config file that add_user will find."""
    cfg = tmp_path / "xray_main_config.json"
    cfg.write_text(json.dumps(config_dict))
    return cfg


def _base_config(network="tcp", clients=None):
    """Return a minimal Xray config dict with one VLESS inbound."""
    return {
        "inbounds": [
            {
                "protocol": "vless",
                "settings": {"clients": clients or []},
                "streamSettings": {"network": network},
            }
        ]
    }


class TestAddUser:
    """Tests for XrayManager.add_user()."""

    @pytest.mark.asyncio
    async def test_returns_false_when_config_missing(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(mod.os.path, "exists", lambda _path: False)

        result = await mod.XrayManager.add_user("uuid-1", "user@example.com")
        assert result is False

    @pytest.mark.asyncio
    async def test_appends_client_and_restarts(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        cfg = _write_xray_config(tmp_path, _base_config(network="tcp"))

        restart_mock = AsyncMock(return_value=True)
        monkeypatch.setattr(mod.XrayManager, "restart_container", restart_mock)

        result = await mod.XrayManager.add_user("uuid-new", "new@example.com", restart=True)
        assert result is True
        restart_mock.assert_awaited_once()

        payload = json.loads(cfg.read_text())
        clients = payload["inbounds"][0]["settings"]["clients"]
        assert len(clients) == 1
        assert clients[0]["id"] == "uuid-new"
        assert clients[0]["email"] == "new@example.com"
        assert clients[0]["flow"] == "xtls-rprx-vision"

    @pytest.mark.asyncio
    async def test_ws_network_sets_empty_flow(self, monkeypatch, tmp_path):
        """When streamSettings.network is NOT 'tcp' the flow field should be
        empty string."""
        monkeypatch.chdir(tmp_path)
        _write_xray_config(tmp_path, _base_config(network="ws"))

        restart_mock = AsyncMock(return_value=True)
        monkeypatch.setattr(mod.XrayManager, "restart_container", restart_mock)

        await mod.XrayManager.add_user("uuid-ws", "ws@example.com")

        cfg = tmp_path / "xray_main_config.json"
        payload = json.loads(cfg.read_text())
        client = payload["inbounds"][0]["settings"]["clients"][0]
        assert client["flow"] == ""

    @pytest.mark.asyncio
    async def test_duplicate_user_skips_restart(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        _write_xray_config(
            tmp_path,
            _base_config(clients=[{"id": "uuid-dup", "email": "dup@example.com"}]),
        )

        restart_mock = AsyncMock(return_value=True)
        monkeypatch.setattr(mod.XrayManager, "restart_container", restart_mock)

        result = await mod.XrayManager.add_user("uuid-dup", "dup@example.com", restart=True)
        assert result is True
        restart_mock.assert_not_awaited()

        cfg = tmp_path / "xray_main_config.json"
        payload = json.loads(cfg.read_text())
        assert len(payload["inbounds"][0]["settings"]["clients"]) == 1

    @pytest.mark.asyncio
    async def test_no_restart_when_flag_false(self, monkeypatch, tmp_path):
        """When restart=False, the container should NOT be restarted even after
        a config update."""
        monkeypatch.chdir(tmp_path)
        _write_xray_config(tmp_path, _base_config())

        restart_mock = AsyncMock(return_value=True)
        monkeypatch.setattr(mod.XrayManager, "restart_container", restart_mock)

        result = await mod.XrayManager.add_user("uuid-nr", "nr@example.com", restart=False)
        assert result is True
        restart_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_returns_false_on_invalid_json(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        cfg = tmp_path / "xray_main_config.json"
        cfg.write_text("{broken-json")

        result = await mod.XrayManager.add_user("uuid-bad", "bad@example.com")
        assert result is False

    @pytest.mark.asyncio
    async def test_config_file_written_only_when_updated(self, monkeypatch, tmp_path):
        """If user already exists the config file must NOT be rewritten (mtime
        should not change)."""
        monkeypatch.chdir(tmp_path)
        cfg = _write_xray_config(
            tmp_path,
            _base_config(clients=[{"id": "uuid-exist", "email": "exist@test.com"}]),
        )
        original_content = cfg.read_text()

        restart_mock = AsyncMock(return_value=True)
        monkeypatch.setattr(mod.XrayManager, "restart_container", restart_mock)

        await mod.XrayManager.add_user("uuid-exist", "exist@test.com")
        # Content should be identical (no rewrite)
        assert cfg.read_text() == original_content

    @pytest.mark.asyncio
    async def test_skips_non_vless_inbounds(self, monkeypatch, tmp_path):
        """Inbounds with protocols other than 'vless' should be ignored."""
        monkeypatch.chdir(tmp_path)
        config = {
            "inbounds": [
                {
                    "protocol": "vmess",
                    "settings": {"clients": []},
                },
                {
                    "protocol": "vless",
                    "settings": {"clients": []},
                    "streamSettings": {"network": "tcp"},
                },
            ]
        }
        cfg = _write_xray_config(tmp_path, config)

        restart_mock = AsyncMock(return_value=True)
        monkeypatch.setattr(mod.XrayManager, "restart_container", restart_mock)

        await mod.XrayManager.add_user("uuid-multi", "multi@example.com")

        payload = json.loads(cfg.read_text())
        # vmess inbound untouched
        assert len(payload["inbounds"][0]["settings"]["clients"]) == 0
        # vless inbound has new user
        assert len(payload["inbounds"][1]["settings"]["clients"]) == 1

    @pytest.mark.asyncio
    async def test_no_inbounds_key(self, monkeypatch, tmp_path):
        """Config without 'inbounds' key should return True without error."""
        monkeypatch.chdir(tmp_path)
        _write_xray_config(tmp_path, {"log": {"loglevel": "warning"}})

        result = await mod.XrayManager.add_user("uuid-noinb", "noinb@test.com")
        assert result is True


# ---------------------------------------------------------------------------
# restart_container
# ---------------------------------------------------------------------------


class _FakeAsyncClient:
    """Minimal async context-manager that returns a canned response on POST."""

    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        _ = (exc_type, exc, tb)
        return False

    async def post(self, _url):
        return self._response


class TestRestartContainer:
    """Tests for XrayManager.restart_container()."""

    @pytest.mark.asyncio
    async def test_returns_false_without_docker_socket(self, monkeypatch):
        monkeypatch.setattr(mod.os.path, "exists", lambda _path: False)

        result = await mod.XrayManager.restart_container()
        assert result is False

    @pytest.mark.asyncio
    async def test_success_on_204(self, monkeypatch):
        monkeypatch.setattr(mod.os.path, "exists", lambda _path: True)
        monkeypatch.setattr(mod.httpx, "HTTPTransport", lambda **_kwargs: object())
        monkeypatch.setattr(
            mod.httpx,
            "AsyncClient",
            lambda **_kwargs: _FakeAsyncClient(SimpleNamespace(status_code=204, text="")),
        )

        result = await mod.XrayManager.restart_container("xray-test")
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_on_non_204(self, monkeypatch):
        monkeypatch.setattr(mod.os.path, "exists", lambda _path: True)
        monkeypatch.setattr(mod.httpx, "HTTPTransport", lambda **_kwargs: object())
        monkeypatch.setattr(
            mod.httpx,
            "AsyncClient",
            lambda **_kwargs: _FakeAsyncClient(
                SimpleNamespace(status_code=500, text="boom")
            ),
        )

        result = await mod.XrayManager.restart_container("xray-test")
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_connection_error(self, monkeypatch):
        class _FailingAsyncClient:
            async def __aenter__(self):
                raise RuntimeError("docker unavailable")

            async def __aexit__(self, exc_type, exc, tb):
                _ = (exc_type, exc, tb)
                return False

        monkeypatch.setattr(mod.os.path, "exists", lambda _path: True)
        monkeypatch.setattr(mod.httpx, "HTTPTransport", lambda **_kwargs: object())
        monkeypatch.setattr(
            mod.httpx, "AsyncClient", lambda **_kwargs: _FailingAsyncClient()
        )

        result = await mod.XrayManager.restart_container("xray-test")
        assert result is False

    @pytest.mark.asyncio
    async def test_default_container_name(self, monkeypatch):
        """Default container name should be 'x0tta6bl4-xray'."""
        captured_url = {}

        class _CapturingClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return False

            async def post(self, url):
                captured_url["url"] = url
                return SimpleNamespace(status_code=204, text="")

        monkeypatch.setattr(mod.os.path, "exists", lambda _path: True)
        monkeypatch.setattr(mod.httpx, "HTTPTransport", lambda **_kwargs: object())
        monkeypatch.setattr(
            mod.httpx, "AsyncClient", lambda **_kwargs: _CapturingClient()
        )

        await mod.XrayManager.restart_container()
        assert "x0tta6bl4-xray" in captured_url["url"]
