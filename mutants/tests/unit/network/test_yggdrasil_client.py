import subprocess
from types import SimpleNamespace
from src.network import yggdrasil_client

class FakeCompleted:
    def __init__(self, stdout: str, stderr: str = '', returncode: int = 0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def fake_run_status(*args, **kwargs):
    return FakeCompleted("Public key: TESTKEY\nIPv6 address: 200:dead:beef::1\nRouting table size: 3\n")


def fake_run_peers(*args, **kwargs):
    return FakeCompleted("Peer  Port  Protocol  Remote Address\n1  tcp  10.0.0.1\n2  tcp  10.0.0.2\n")


def test_get_yggdrasil_status(monkeypatch):
    monkeypatch.setattr(subprocess, 'run', fake_run_status)
    status = yggdrasil_client.get_yggdrasil_status()
    assert status['status'] == 'online'
    assert status['node']['public_key'] == 'TESTKEY'
    assert status['node']['ipv6_address'].startswith('200:dead:beef')


def test_get_yggdrasil_peers(monkeypatch):
    monkeypatch.setattr(subprocess, 'run', fake_run_peers)
    peers = yggdrasil_client.get_yggdrasil_peers()
    assert peers['status'] == 'ok'
    assert peers['count'] == 2
    assert all('remote' in p for p in peers['peers'])


def test_get_yggdrasil_routes(monkeypatch):
    monkeypatch.setattr(subprocess, 'run', fake_run_status)
    routes = yggdrasil_client.get_yggdrasil_routes()
    assert routes['status'] == 'ok'
    assert routes['routing_table_size'] == 3
