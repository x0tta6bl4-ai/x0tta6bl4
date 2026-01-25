from fastapi.testclient import TestClient
from src.core.app import app

client = TestClient(app)

class DummyMonkey:
    pass


def test_mesh_endpoints(monkeypatch):
    monkeypatch.setattr('src.network.yggdrasil_client.get_yggdrasil_status', lambda: {"status":"online","node":{"public_key":"PK","ipv6_address":"200::1"}})
    monkeypatch.setattr('src.network.yggdrasil_client.get_yggdrasil_peers', lambda: {"status":"ok","peers":[{"remote":"10.0.0.1"}],"count":1})
    monkeypatch.setattr('src.network.yggdrasil_client.get_yggdrasil_routes', lambda: {"status":"ok","routing_table_size":5})

    r1 = client.get('/mesh/status')
    assert r1.status_code == 200
    assert r1.json()['node']['public_key'] == 'PK'

    r2 = client.get('/mesh/peers')
    assert r2.status_code == 200
    assert r2.json()['count'] == 1

    r3 = client.get('/mesh/routes')
    assert r3.status_code == 200
    assert r3.json()['routing_table_size'] == 5


def test_health_endpoint_again():
    r = client.get('/health')
    assert r.status_code == 200
    assert r.json()['status'] == 'ok'
