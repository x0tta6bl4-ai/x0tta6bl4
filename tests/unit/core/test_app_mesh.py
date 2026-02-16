import httpx
import pytest
import pytest_asyncio

from src.core.app import app


class DummyMonkey:
    pass


@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as tc:
        yield tc


@pytest.mark.asyncio
async def test_mesh_endpoints(monkeypatch, client):
    import src.network.yggdrasil_client as yc

    monkeypatch.setattr(
        yc,
        "get_yggdrasil_status",
        lambda: {
            "status": "online",
            "node": {"public_key": "PK", "ipv6_address": "200::1"},
        },
    )
    monkeypatch.setattr(
        yc,
        "get_yggdrasil_peers",
        lambda: {"status": "ok", "peers": [{"remote": "10.0.0.1"}], "count": 1},
    )
    monkeypatch.setattr(
        yc, "get_yggdrasil_routes", lambda: {"status": "ok", "routing_table_size": 5}
    )

    r1 = await client.get("/mesh/status")
    assert r1.status_code == 200
    payload = r1.json()
    assert payload["status"] == "online"
    assert "node" in payload

    r2 = await client.get("/mesh/peers")
    assert r2.status_code == 200
    assert r2.json()["count"] == 1

    r3 = await client.get("/mesh/routes")
    assert r3.status_code == 200
    assert r3.json()["routing_table_size"] == 5


@pytest.mark.asyncio
async def test_health_endpoint_again(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
