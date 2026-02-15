import os
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

import src.api.vpn_experimental as vpn


def _raw(fn):
    return getattr(fn, "__wrapped__", fn)


@pytest.mark.asyncio
async def test_verify_admin_token_missing_env(monkeypatch) -> None:
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    with pytest.raises(HTTPException) as exc:
        await vpn.verify_admin_token("x")
    assert exc.value.status_code == 500


@pytest.mark.asyncio
async def test_verify_admin_token_forbidden(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_TOKEN", "good")
    with pytest.raises(HTTPException) as exc:
        await vpn.verify_admin_token("bad")
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_verify_admin_token_ok(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_TOKEN", "good")
    assert await vpn.verify_admin_token("good") is None


@pytest.mark.asyncio
async def test_get_vpn_config_uses_defaults_and_generators(monkeypatch) -> None:
    monkeypatch.setenv("VPN_SERVER", "vpn.example")
    monkeypatch.setenv("VPN_PORT_EXPERIMENTAL", "443")
    monkeypatch.setattr(
        vpn,
        "generate_config_text",
        lambda user_id, user_uuid, server, port: f"cfg:{user_id}:{server}:{port}:{user_uuid}",
    )
    monkeypatch.setattr(
        vpn,
        "generate_vless_link",
        lambda user_uuid, server, port: f"vless://{user_uuid}@{server}:{port}",
    )

    class _UUID:
        @staticmethod
        def uuid4():
            return "uuid-1"

    monkeypatch.setitem(__import__("sys").modules, "uuid", _UUID)
    resp = await _raw(vpn.get_vpn_config)(SimpleNamespace(), user_id=7)
    assert resp.user_id == 7
    assert "vpn.example:443" in resp.vless_link
    assert resp.config_text.startswith("cfg:7:vpn.example:443")


@pytest.mark.asyncio
async def test_create_vpn_config_forwards_request(monkeypatch) -> None:
    seen = {}

    async def fake_get_vpn_config(
        *, request, user_id, username=None, server=None, port=None
    ):
        seen["request"] = request
        return vpn.VPNConfigResponse(
            user_id=user_id,
            username=username,
            vless_link="vless://x",
            config_text="cfg",
        )

    monkeypatch.setattr(vpn, "get_vpn_config", fake_get_vpn_config)
    req_obj = SimpleNamespace(client="local")
    payload = vpn.VPNConfigRequest(user_id=9, username="u")
    resp = await _raw(vpn.create_vpn_config)(req_obj, payload)
    assert resp.user_id == 9
    assert seen["request"] is req_obj


@pytest.mark.asyncio
async def test_get_vpn_status_online_and_offline(monkeypatch) -> None:
    monkeypatch.setenv("VPN_SERVER", "127.0.0.1")
    monkeypatch.setenv("VPN_PORT_EXPERIMENTAL", "443")

    class GoodSock:
        def settimeout(self, _):
            return None

        def connect(self, _addr):
            return None

        def close(self):
            return None

    monkeypatch.setattr("socket.socket", lambda *_a, **_k: GoodSock())
    online = await _raw(vpn.get_vpn_status)(SimpleNamespace())
    assert online.status == "online"

    class BadSock:
        def settimeout(self, _):
            return None

        def connect(self, _addr):
            raise RuntimeError("down")

        def close(self):
            return None

    monkeypatch.setattr("socket.socket", lambda *_a, **_k: BadSock())
    offline = await _raw(vpn.get_vpn_status)(SimpleNamespace())
    assert offline.status == "offline"


@pytest.mark.asyncio
async def test_get_vpn_users_and_delete_user() -> None:
    users = await _raw(vpn.get_vpn_users)(SimpleNamespace(), admin=None)
    assert users["total"] == 2
    assert len(users["users"]) == 2

    deleted = await _raw(vpn.delete_vpn_user)(SimpleNamespace(), 1001, admin=None)
    assert deleted["success"] is True
