import subprocess
from types import SimpleNamespace

import pytest

from libx0t.network import yggdrasil_client


class FakeCompleted:
    def __init__(self, stdout: str, stderr: str = "", returncode: int = 0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def fake_run_status(*args, **kwargs):
    return FakeCompleted(
        "Public key: TESTKEY\nIPv6 address: 200:dead:beef::1\nRouting table size: 3\n"
    )


def fake_run_peers(*args, **kwargs):
    return FakeCompleted(
        "Peer  Port  Protocol  Remote Address\n1  tcp  10.0.0.1\n2  tcp  10.0.0.2\n"
    )


def test_get_yggdrasil_status(monkeypatch):
    monkeypatch.setattr(subprocess, "run", fake_run_status)
    status = yggdrasil_client.get_yggdrasil_status()
    assert status["status"] == "online"
    assert status["node"]["public_key"] == "TESTKEY"
    assert status["node"]["ipv6_address"].startswith("200:dead:beef")


def test_get_yggdrasil_peers(monkeypatch):
    monkeypatch.setattr(subprocess, "run", fake_run_peers)
    peers = yggdrasil_client.get_yggdrasil_peers()
    assert peers["status"] == "ok"
    assert peers["count"] == 2
    assert all("remote" in p for p in peers["peers"])


def test_get_yggdrasil_routes(monkeypatch):
    monkeypatch.setattr(subprocess, "run", fake_run_status)
    routes = yggdrasil_client.get_yggdrasil_routes()
    assert routes["status"] == "ok"
    assert routes["routing_table_size"] == 3


def test_find_yggdrasilctl_paths(monkeypatch):
    monkeypatch.setattr(yggdrasil_client.shutil, "which", lambda x: x == "yggdrasilctl")
    monkeypatch.setattr(yggdrasil_client.os.path, "exists", lambda _x: False)
    assert yggdrasil_client._find_yggdrasilctl() == "yggdrasilctl"

    monkeypatch.setattr(yggdrasil_client.shutil, "which", lambda _x: None)
    monkeypatch.setattr(
        yggdrasil_client.os.path, "exists", lambda x: x == "/usr/local/bin/yggdrasilctl"
    )
    assert yggdrasil_client._find_yggdrasilctl() == "/usr/local/bin/yggdrasilctl"

    monkeypatch.setattr(yggdrasil_client.os.path, "exists", lambda _x: False)
    assert yggdrasil_client._find_yggdrasilctl() is None


def test_status_force_mock_and_missing_binary(monkeypatch):
    monkeypatch.setenv("YGGDRASIL_MOCK", "true")
    monkeypatch.setenv("NODE_ID", "node-b")
    status = yggdrasil_client.get_yggdrasil_status()
    assert status["status"] == "mock"
    assert status["address"] == "fd00::b"

    monkeypatch.delenv("YGGDRASIL_MOCK", raising=False)
    monkeypatch.setattr(yggdrasil_client, "_find_yggdrasilctl", lambda: None)
    status2 = yggdrasil_client.get_yggdrasil_status()
    assert status2["status"] == "mock"
    assert "subnet" in status2


def test_status_error_and_exception_paths(monkeypatch):
    monkeypatch.setattr(yggdrasil_client, "_find_yggdrasilctl", lambda: "/usr/bin/yggdrasilctl")

    monkeypatch.setattr(subprocess, "run", lambda *_a, **_k: (_ for _ in ()).throw(FileNotFoundError()))
    mock_status = yggdrasil_client.get_yggdrasil_status()
    assert mock_status["status"] == "mock"

    os_err_not_found = OSError("No such file or directory")
    os_err_not_found.errno = 2
    monkeypatch.setattr(subprocess, "run", lambda *_a, **_k: (_ for _ in ()).throw(os_err_not_found))
    mock_status2 = yggdrasil_client.get_yggdrasil_status()
    assert mock_status2["status"] == "mock"

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_a, **_k: (_ for _ in ()).throw(subprocess.CalledProcessError(1, "x", stderr="bad")),
    )
    err = yggdrasil_client.get_yggdrasil_status()
    assert err["status"] == "error"
    assert "bad" in err["error"]

    monkeypatch.setattr(
        subprocess, "run", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("offline"))
    )
    off = yggdrasil_client.get_yggdrasil_status()
    assert off["status"] == "offline"

    os_err_other = OSError("permission denied")
    os_err_other.errno = 13
    monkeypatch.setattr(subprocess, "run", lambda *_a, **_k: (_ for _ in ()).throw(os_err_other))
    with pytest.raises(OSError):
        yggdrasil_client.get_yggdrasil_status()


def test_peers_force_mock_missing_binary_and_error_paths(monkeypatch):
    monkeypatch.setenv("YGGDRASIL_MOCK", "1")
    monkeypatch.setattr(yggdrasil_client.random, "randint", lambda a, b: 2 if a == 2 else 10001)
    monkeypatch.setattr(yggdrasil_client.random, "choice", lambda seq: seq[0])
    peers = yggdrasil_client.get_yggdrasil_peers()
    assert peers["status"] == "ok"
    assert peers["count"] == 2

    monkeypatch.delenv("YGGDRASIL_MOCK", raising=False)
    monkeypatch.setattr(yggdrasil_client, "_find_yggdrasilctl", lambda: None)
    peers2 = yggdrasil_client.get_yggdrasil_peers()
    assert peers2["status"] == "ok"

    monkeypatch.setattr(yggdrasil_client, "_find_yggdrasilctl", lambda: "/usr/bin/yggdrasilctl")
    monkeypatch.setattr(subprocess, "run", lambda *_a, **_k: (_ for _ in ()).throw(FileNotFoundError()))
    peers3 = yggdrasil_client.get_yggdrasil_peers()
    assert peers3["status"] == "ok"

    os_err_not_found = OSError("No such file or directory")
    os_err_not_found.errno = 2
    monkeypatch.setattr(subprocess, "run", lambda *_a, **_k: (_ for _ in ()).throw(os_err_not_found))
    peers4 = yggdrasil_client.get_yggdrasil_peers()
    assert peers4["status"] == "ok"

    monkeypatch.setattr(
        subprocess, "run", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("peer fail"))
    )
    peers_err = yggdrasil_client.get_yggdrasil_peers()
    assert peers_err["status"] == "error"
    assert peers_err["count"] == 0

    os_err_other = OSError("permission denied")
    os_err_other.errno = 13
    monkeypatch.setattr(subprocess, "run", lambda *_a, **_k: (_ for _ in ()).throw(os_err_other))
    with pytest.raises(OSError):
        yggdrasil_client.get_yggdrasil_peers()


def test_peers_parser_ignores_bad_lines(monkeypatch):
    monkeypatch.setattr(yggdrasil_client, "_find_yggdrasilctl", lambda: "/usr/bin/yggdrasilctl")

    def _run(*_a, **_k):
        return FakeCompleted(
            "Peer Header\n"
            "badline\n"
            "12345 tcp node-a\n"
            "incomplete line\n"
            "23456 tcp node-b\n"
        )

    monkeypatch.setattr(subprocess, "run", _run)
    peers = yggdrasil_client.get_yggdrasil_peers()
    assert peers["status"] == "ok"
    assert peers["count"] == 2


def test_routes_force_mock_missing_binary_and_error_paths(monkeypatch):
    monkeypatch.setenv("YGGDRASIL_MOCK", "true")
    monkeypatch.setattr(yggdrasil_client, "get_yggdrasil_peers", lambda: {"count": 4})
    routes = yggdrasil_client.get_yggdrasil_routes()
    assert routes == {"status": "ok", "routing_table_size": 4}

    monkeypatch.delenv("YGGDRASIL_MOCK", raising=False)
    monkeypatch.setattr(yggdrasil_client, "_find_yggdrasilctl", lambda: None)
    routes2 = yggdrasil_client.get_yggdrasil_routes()
    assert routes2["status"] == "ok"

    monkeypatch.setattr(yggdrasil_client, "_find_yggdrasilctl", lambda: "/usr/bin/yggdrasilctl")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_a, **_k: (_ for _ in ()).throw(
            FileNotFoundError(2, "No such file or directory")
        ),
    )
    routes3 = yggdrasil_client.get_yggdrasil_routes()
    assert routes3["status"] == "ok"

    monkeypatch.setattr(
        subprocess, "run", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("route fail"))
    )
    routes_err = yggdrasil_client.get_yggdrasil_routes()
    assert routes_err["status"] == "error"
    assert routes_err["routing_table_size"] == 0

    os_err_other = OSError("permission denied")
    os_err_other.errno = 13
    monkeypatch.setattr(subprocess, "run", lambda *_a, **_k: (_ for _ in ()).throw(os_err_other))
    with pytest.raises(OSError):
        yggdrasil_client.get_yggdrasil_routes()
