from types import SimpleNamespace


def test_spire_server_client_health_check_success(monkeypatch):
    from src.security.spiffe.server.client import SPIREServerClient

    def _run(cmd, capture_output, text, timeout):
        assert cmd[1] == "healthcheck"
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("src.security.spiffe.server.client.subprocess.run", _run)

    c = SPIREServerClient(spire_server_bin="spire-server")
    assert c.health_check() is True


def test_spire_server_client_health_check_failure(monkeypatch):
    from src.security.spiffe.server.client import SPIREServerClient

    def _run(*args, **kwargs):
        raise FileNotFoundError("no")

    monkeypatch.setattr("src.security.spiffe.server.client.subprocess.run", _run)

    c = SPIREServerClient(spire_server_bin="spire-server")
    assert c.health_check() is False


def test_spire_server_client_create_entry_parses_id_and_admin_flag(monkeypatch):
    from src.security.spiffe.server.client import SPIREServerClient

    seen = {}

    def _run(cmd, capture_output, text, timeout):
        seen["cmd"] = cmd
        return SimpleNamespace(returncode=0, stdout="Entry created: eid\n", stderr="")

    monkeypatch.setattr("src.security.spiffe.server.client.subprocess.run", _run)

    c = SPIREServerClient(spire_server_bin="spire-server")
    eid = c.create_entry(
        "spiffe://a", "spiffe://p", {"unix:uid": "1000"}, ttl=10, admin=True
    )

    assert eid == "eid"
    assert "-admin" in seen["cmd"]
    assert "unix:uid:1000" in seen["cmd"]


def test_spire_server_client_list_entries_parses_blocks(monkeypatch):
    from src.security.spiffe.server.client import SPIREServerClient

    out = """Entry ID: e1
SPIFFE ID: spiffe://a
Parent ID: spiffe://p
Selectors: unix:uid:1000
TTL: 5
Admin: true

Entry ID: e2
SPIFFE ID: spiffe://b
Parent ID: spiffe://p
Selectors: 
TTL: 7
Admin: false
"""

    monkeypatch.setattr(
        "src.security.spiffe.server.client.subprocess.run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout=out, stderr=""),
    )

    c = SPIREServerClient(spire_server_bin="spire-server")
    entries = c.list_entries()

    assert len(entries) == 2
    assert entries[0].entry_id == "e1"
    assert entries[0].selectors["unix"] == "uid:1000"
    assert entries[0].admin is True


def test_spire_server_client_delete_entry_and_status(monkeypatch):
    from src.security.spiffe.server.client import SPIREServerClient

    def _run(cmd, capture_output, text, timeout):
        if cmd[1:3] == ["entry", "delete"]:
            return SimpleNamespace(returncode=0, stdout="ok", stderr="")
        return SimpleNamespace(returncode=1, stdout="", stderr="bad")

    monkeypatch.setattr("src.security.spiffe.server.client.subprocess.run", _run)

    c = SPIREServerClient(spire_server_bin="spire-server")
    assert c.delete_entry("e") is True

    st = c.get_server_status()
    assert st["healthy"] is False
    assert st["address"] == c.server_address
