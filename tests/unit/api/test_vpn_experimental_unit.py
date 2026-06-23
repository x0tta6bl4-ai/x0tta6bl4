import json
import os
import sqlite3
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.coordination.events import EventBus, EventType

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

import src.api.vpn_experimental as vpn


def _raw(fn):
    return getattr(fn, "__wrapped__", fn)


def _request_with_bus(bus):
    return SimpleNamespace(state=SimpleNamespace(event_bus=bus))


def _latest_event_payload(bus, source_agent):
    events = bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent=source_agent,
        limit=10,
    )
    assert events
    return events[-1].data


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
async def test_get_vpn_config_publishes_redacted_evidence(monkeypatch, tmp_path) -> None:
    bus = EventBus(str(tmp_path))
    monkeypatch.setenv("VPN_SERVER", "secret.vpn.example")
    monkeypatch.setenv("VPN_PORT_EXPERIMENTAL", "443")
    monkeypatch.setenv(
        "VPN_EXPERIMENTAL_CONFIG_GENERATE_SPIFFE_ID",
        "spiffe://secret/vpn-experimental-config",
    )
    monkeypatch.setattr(
        vpn,
        "generate_config_text",
        lambda user_id, user_uuid, server, port: (
            f"cfg-private:{user_id}:{server}:{port}:{user_uuid}"
        ),
    )
    monkeypatch.setattr(
        vpn,
        "generate_vless_link",
        lambda user_uuid, server, port: f"vless://{user_uuid}@{server}:{port}",
    )

    class _UUID:
        @staticmethod
        def uuid4():
            return "uuid-private"

    monkeypatch.setitem(__import__("sys").modules, "uuid", _UUID)

    resp = await _raw(vpn.get_vpn_config)(
        _request_with_bus(bus),
        user_id=777,
        username="private-user",
    )
    payload = _latest_event_payload(bus, "vpn-experimental-config-generate")
    payload_text = str(payload)

    assert resp.user_id == 777
    assert payload["operation"] == "generate_experimental_vpn_config"
    assert payload["control_action"] is True
    assert payload["observed_state"] is False
    assert payload["source_quality"] == "local_config_generation_only"
    assert payload["vless_link_present"] is True
    assert payload["config_text_present"] is True
    assert payload["service_identity"]["spiffe_id_present"] is True
    assert payload["dataplane_confirmed"] is False
    assert payload["bypass_confirmed"] is False
    for raw_value in [
        "secret.vpn.example",
        "vless://uuid-private@secret.vpn.example:443",
        "cfg-private",
        "uuid-private",
        "private-user",
        "777",
        "spiffe://secret/vpn-experimental-config",
    ]:
        assert raw_value not in payload_text


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
    monkeypatch.setattr(vpn, "_get_active_users_count", lambda: 7)
    monkeypatch.setattr(vpn, "_read_system_uptime", lambda: 123.5)

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
    assert online.active_users == 7
    assert online.uptime == 123.5

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
    assert offline.active_users == 7
    assert offline.uptime == 123.5


@pytest.mark.asyncio
async def test_get_vpn_users_reads_configured_file(monkeypatch, tmp_path) -> None:
    users_file = tmp_path / "vpn-users.json"
    users_file.write_text(
        json.dumps(
            {
                "users": [
                    {
                        "user_id": 1001,
                        "username": "experimental_user1",
                        "vless_link": "vless://user1",
                        "last_connected": "2026-05-27T00:30:00Z",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("VPN_USERS_FILE", str(users_file))

    users = await _raw(vpn.get_vpn_users)(SimpleNamespace(), admin=None)
    assert users["total"] == 1
    assert users["users"][0]["username"] == "experimental_user1"


@pytest.mark.asyncio
async def test_get_vpn_users_returns_empty_without_sources(monkeypatch) -> None:
    monkeypatch.delenv("VPN_USERS_FILE", raising=False)
    monkeypatch.delenv("VPN_EXPERIMENTAL_USERS_FILE", raising=False)
    monkeypatch.setattr(vpn, "_fetch_users_from_xui_db", lambda: [])

    users = await _raw(vpn.get_vpn_users)(SimpleNamespace(), admin=None)
    assert users == {"total": 0, "users": []}


def test_active_users_count_prefers_env(monkeypatch) -> None:
    monkeypatch.setenv("VPN_ACTIVE_USERS", "11")
    assert vpn._get_active_users_count() == 11


def test_active_users_count_counts_xui_db_enabled_users(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "x-ui.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE client_traffics (
                email TEXT,
                up INTEGER,
                down INTEGER,
                total INTEGER,
                enable INTEGER,
                expiry_time INTEGER
            )
            """
        )
        conn.executemany(
            "INSERT INTO client_traffics VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("enabled@example.test", 1, 2, 10, 1, 0),
                ("disabled@example.test", 3, 4, 20, 0, 0),
            ],
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.delenv("VPN_ACTIVE_USERS", raising=False)
    monkeypatch.delenv("VPN_USERS_FILE", raising=False)
    monkeypatch.delenv("VPN_EXPERIMENTAL_USERS_FILE", raising=False)
    monkeypatch.setenv("XUI_DB_PATH", str(db_path))
    monkeypatch.setattr(vpn, "_get_xui_client", lambda: None)

    assert vpn._get_active_users_count() == 1
    users = vpn._fetch_users_from_xui_db()
    assert users[0]["email"] == "enabled@example.test"
    assert users[1]["enabled"] is False


@pytest.mark.asyncio
async def test_delete_vpn_user_returns_confirmation() -> None:
    deleted = await _raw(vpn.delete_vpn_user)(SimpleNamespace(), 1001, admin=None)
    assert deleted["success"] is True


@pytest.mark.asyncio
async def test_delete_vpn_user_evidence_marks_stub_without_raw_id(tmp_path) -> None:
    bus = EventBus(str(tmp_path))

    deleted = await _raw(vpn.delete_vpn_user)(
        _request_with_bus(bus),
        1001,
        admin=object(),
    )
    payload = _latest_event_payload(bus, "vpn-experimental-user-delete")
    payload_text = str(payload)

    assert deleted["success"] is True
    assert payload["operation"] == "delete_experimental_vpn_user"
    assert payload["control_action"] is True
    assert payload["delete_stub_response"] is True
    assert payload["persistent_delete_attempted"] is False
    assert payload["persistent_delete_confirmed"] is False
    assert payload["dataplane_confirmed"] is False
    assert "1001" not in payload_text
