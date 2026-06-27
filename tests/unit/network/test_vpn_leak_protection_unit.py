import sys
import json
from types import SimpleNamespace

import pytest

import src.network.vpn_leak_protection as mod


class _CmdResult:
    def __init__(self, success=True, stdout="", stderr=""):
        self.success = success
        self.stdout = stdout
        self.stderr = stderr


class _DummyResolver:
    def __init__(self, mapping=None, errors=None, evidence=None):
        self.mapping = mapping or {}
        self.errors = set(errors or [])
        self.evidence = evidence or {}
        self._last_resolution_evidence = None

    async def resolve_a(self, domain):
        self._last_resolution_evidence = self.evidence.get(domain)
        if domain in self.errors:
            raise RuntimeError(f"resolver failed: {domain}")
        return self.mapping.get(domain, [])

    def get_last_resolution_evidence(self):
        return self._last_resolution_evidence

    def get_stats(self):
        return {"resolver": "dummy"}


@pytest.fixture(autouse=True)
def _isolate_event_bus(monkeypatch, tmp_path):
    buses = {}

    def _get_event_bus(project_root="."):
        if project_root not in buses:
            buses[project_root] = mod.EventBus(str(tmp_path))
        return buses[project_root]

    monkeypatch.setattr(mod, "get_event_bus", _get_event_bus)


def _event_payloads(bus):
    return [
        event.to_dict()
        for event in bus.get_event_history(
            source_agent="vpn-leak-protector",
            limit=100,
        )
    ]


def _assert_event_log_redacted(tmp_path, bus, raw_values):
    serialized = json.dumps(_event_payloads(bus), sort_keys=True)
    log_path = tmp_path / mod.EventBus.EVENT_LOG
    log_text = log_path.read_text() if log_path.exists() else ""
    for raw_value in raw_values:
        assert raw_value not in serialized
        assert raw_value not in log_text


def test_leak_test_result_helpers():
    result = mod.LeakTestResult(mod.LeakType.DNS, True, {"k": "v"})
    text = str(result)
    assert "DNS:" in text
    assert "LEAK DETECTED" in text
    assert result.to_dict() == {
        "leak_type": "dns",
        "is_leaking": True,
        "details": {"k": "v"},
    }


def test_validate_interface_and_init():
    resolver = _DummyResolver()
    protector = mod.VPNLeakProtector(doh_resolver=resolver)
    assert protector.doh_resolver is resolver

    assert protector._validate_interface_name("tun0") is True
    assert protector._validate_interface_name("wg-1") is True
    assert protector._validate_interface_name(None) is False
    assert protector._validate_interface_name("") is False
    assert protector._validate_interface_name("bad iface") is False


def test_default_doh_resolver_reuses_injected_event_bus(tmp_path):
    event_bus = mod.EventBus(str(tmp_path))
    protector = mod.VPNLeakProtector(event_bus=event_bus)

    assert protector.doh_resolver.event_bus is event_bus


@pytest.mark.asyncio
async def test_iptables_command_event_redacts_args_outputs_and_identity(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv(
        "VPN_LEAK_PROTECTOR_SPIFFE_ID",
        "spiffe://secret/vpn-leak-protector",
    )
    monkeypatch.setenv("VPN_LEAK_PROTECTOR_DID", "did:mesh:secret-leak-protector")
    monkeypatch.setenv(
        "VPN_LEAK_PROTECTOR_WALLET_ADDRESS",
        "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    event_bus = mod.EventBus(str(tmp_path))
    protector = mod.VPNLeakProtector(
        doh_resolver=_DummyResolver(),
        event_bus=event_bus,
    )

    monkeypatch.setattr(
        mod.SafeSubprocess,
        "run",
        lambda *_a, **_k: _CmdResult(
            success=False,
            stdout="accepted 203.0.113.10 via tun-secret",
            stderr="blocked 203.0.113.10 on tun-secret",
        ),
    )

    result = await protector._run_iptables_command(
        ["-A", "OUTPUT", "-d", "203.0.113.10/32", "-o", "tun-secret", "-j", "DROP"]
    )

    assert result == (
        False,
        "accepted 203.0.113.10 via tun-secret",
        "blocked 203.0.113.10 on tun-secret",
    )
    event = _event_payloads(event_bus)[-1]
    data = event["data"]
    assert event["event_type"] == mod.EventType.TASK_BLOCKED.value
    assert data["operation"] == "iptables_command"
    assert data["control_action"] is True
    assert data["command"]["executable"] == "iptables"
    assert data["command"]["argv_count"] == 9
    assert data["command"]["raw_args_redacted"] is True
    assert data["output_metadata"]["success"] is False
    assert data["output_metadata"]["stdout"]["sha256_prefix"]
    assert data["output_metadata"]["stderr"]["sha256_prefix"]
    assert data["service_identity"]["spiffe_id_present"] is True
    assert data["service_identity"]["did_present"] is True
    assert data["service_identity"]["wallet_address_present"] is True
    assert "does not prove remote VPN provider health" in data["claim_boundary"]
    _assert_event_log_redacted(
        tmp_path,
        event_bus,
        [
            "203.0.113.10",
            "tun-secret",
            "spiffe://secret",
            "did:mesh:secret-leak-protector",
            "0xaaaaaaaa",
            "accepted 203.0.113.10",
            "blocked 203.0.113.10",
        ],
    )


@pytest.mark.asyncio
async def test_dns_leak_event_redacts_domains_and_resolved_ips(tmp_path):
    event_bus = mod.EventBus(str(tmp_path))
    protector = mod.VPNLeakProtector(
        doh_resolver=_DummyResolver(
            mapping={"secret.example": ["198.51.100.42"]},
            errors={"bad.secret"},
        ),
        event_bus=event_bus,
    )

    result = await protector.test_dns_leak(["secret.example", "bad.secret"])

    assert result.is_leaking is True
    event = _event_payloads(event_bus)[-1]
    data = event["data"]
    assert data["operation"] == "test_dns_leak"
    assert data["observed_state"] is True
    assert data["result_summary"]["tested_domain_count"] == 2
    assert data["result_summary"]["resolved_domain_count"] == 1
    assert data["result_summary"]["failed_domain_count"] == 1
    _assert_event_log_redacted(
        tmp_path,
        event_bus,
        ["secret.example", "bad.secret", "198.51.100.42"],
    )


class _FakeDoHResponse:
    def __init__(self, status, json_data):
        self.status = status
        self._json_data = json_data

    async def json(self):
        return self._json_data

    async def text(self):
        return json.dumps(self._json_data)


class _FakeDoHResponseCM:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, *_args):
        return False


class _FakeDoHSession:
    closed = False

    def __init__(self, response):
        self._response = response

    def get(self, *_args, **_kwargs):
        return _FakeDoHResponseCM(self._response)


@pytest.mark.asyncio
async def test_dns_leak_event_links_doh_evidence_without_raw_dns_payload(
    tmp_path,
):
    event_bus = mod.EventBus(str(tmp_path))
    resolver = mod.DoHResolver(
        servers=[
            {
                "name": "SecretResolver",
                "url": "https://secret-dns.example/query",
                "params": {"ct": "application/dns-json"},
            }
        ],
        event_bus=event_bus,
    )
    resolver.session = _FakeDoHSession(
        _FakeDoHResponse(
            200,
            {
                "Status": 0,
                "Answer": [
                    {
                        "name": "secret.example",
                        "type": 1,
                        "data": "203.0.113.77",
                    }
                ],
            },
        )
    )
    protector = mod.VPNLeakProtector(
        doh_resolver=resolver,
        event_bus=event_bus,
    )

    result = await protector.test_dns_leak(["secret.example"])

    assert result.is_leaking is False
    doh_event = event_bus.get_event_history(
        source_agent="doh-resolver",
        limit=10,
    )[-1].to_dict()
    vpn_event = _event_payloads(event_bus)[-1]
    evidence = vpn_event["data"]["result_summary"]["doh_resolution_evidence"]
    assert evidence["available_count"] == 1
    assert evidence["missing_count"] == 0
    assert evidence["event_ids"] == [doh_event["event_id"]]
    assert evidence["source_agents"] == ["doh-resolver"]
    assert evidence["layers"] == ["network_dns_over_https_observed_state"]
    assert evidence["resolver_modes"] == ["doh"]
    assert evidence["statuses"] == ["success"]
    _assert_event_log_redacted(
        tmp_path,
        event_bus,
        [
            "secret.example",
            "203.0.113.77",
            "SecretResolver",
            "https://secret-dns.example/query",
            "name=secret.example",
        ],
    )


@pytest.mark.asyncio
async def test_status_event_links_last_doh_evidence_without_raw_dns_payload(tmp_path):
    event_bus = mod.EventBus(str(tmp_path))
    resolver = _DummyResolver(
        mapping={"status.secret": ["198.51.100.77"]},
        evidence={
            "status.secret": {
                "event_id": "evt-status-doh",
                "source_agent": "doh-resolver",
                "layer": "network_dns_over_https_observed_state",
                "operation": "resolve",
                "stage": "doh_resolve",
                "status": "success",
                "record_type": "A",
                "domain_hash": mod._redacted_sha256_prefix("status.secret"),
                "resolver_mode": "doh",
                "answer_count": 1,
                "attempt_count": 1,
                "claim_boundary": "bounded test claim",
                "raw_identifiers_redacted": True,
                "payloads_redacted": True,
            }
        },
    )
    protector = mod.VPNLeakProtector(
        doh_resolver=resolver,
        event_bus=event_bus,
    )

    await protector.test_dns_leak(["status.secret"])
    status = await protector.get_status()

    assert status["resolver_info"]["resolver"] == "dummy"
    event = _event_payloads(event_bus)[-1]
    data = event["data"]
    assert data["operation"] == "get_status"
    evidence = data["result_summary"]["last_doh_resolution_evidence"]
    assert evidence["available"] is True
    assert evidence["event_id"] == "evt-status-doh"
    assert evidence["source_agent"] == "doh-resolver"
    assert evidence["layer"] == "network_dns_over_https_observed_state"
    assert evidence["resolver_mode"] == "doh"
    assert evidence["status"] == "success"
    _assert_event_log_redacted(
        tmp_path,
        event_bus,
        ["status.secret", "198.51.100.77"],
    )


@pytest.mark.asyncio
async def test_enable_disable_protection_flow_and_validation():
    protector = mod.VPNLeakProtector(doh_resolver=_DummyResolver())

    with pytest.raises(ValueError, match="Invalid VPN interface name"):
        await protector.enable_protection("bad iface")

    state = []

    async def _mark(name):
        state.append(name)

    protector._save_original_dns = lambda: _mark("save_dns")
    protector._configure_doh = lambda: _mark("configure_doh")
    protector._configure_firewall = lambda: _mark("configure_fw")
    protector._enable_kill_switch = lambda: _mark("enable_kill")

    await protector.enable_protection("tun0")
    assert protector.vpn_interface == "tun0"
    assert protector.protection_enabled is True
    assert state == ["save_dns", "configure_doh", "configure_fw", "enable_kill"]

    disable_state = []
    protector._disable_kill_switch = lambda: _mark_disable(disable_state, "disable_kill")
    protector._restore_original_dns = lambda: _mark_disable(disable_state, "restore_dns")
    protector._restore_firewall = lambda: _mark_disable(disable_state, "restore_fw")

    await protector.disable_protection()
    assert protector.protection_enabled is False
    assert disable_state == ["disable_kill", "restore_dns", "restore_fw"]

    # Already disabled path
    await protector.disable_protection()


async def _mark_disable(arr, name):
    arr.append(name)


@pytest.mark.asyncio
async def test_save_original_dns_platform_paths(monkeypatch):
    protector = mod.VPNLeakProtector(doh_resolver=_DummyResolver())

    # Linux parsing
    monkeypatch.setattr(mod.sys, "platform", "linux")
    monkeypatch.setattr(
        mod.SafeSubprocess,
        "run",
        lambda *_a, **_k: _CmdResult(
            success=True,
            stdout="nameserver 1.1.1.1\nnameserver 8.8.8.8\n",
        ),
    )
    await protector._save_original_dns()
    assert protector.original_dns_servers == ["1.1.1.1", "8.8.8.8"]

    # Windows parsing
    protector.original_dns_servers = []
    monkeypatch.setattr(mod.sys, "platform", "win32")
    monkeypatch.setattr(
        mod.SafeSubprocess,
        "run",
        lambda *_a, **_k: _CmdResult(
            success=True,
            stdout=(
                "DNS Servers . . . . . . . . . . . : 9.9.9.9\n"
                "                                      149.112.112.112\n"
                "Description . . . . . . . . . . . . : adapter\n"
            ),
        ),
    )
    await protector._save_original_dns()
    assert protector.original_dns_servers == ["149.112.112.112"]

    # macOS parsing
    protector.original_dns_servers = []
    monkeypatch.setattr(mod.sys, "platform", "darwin")
    monkeypatch.setattr(
        mod.SafeSubprocess,
        "run",
        lambda *_a, **_k: _CmdResult(
            success=True,
            stdout=(
                "resolver #0\n"
                "  nameserver[0] : 1.1.1.1\n"
                "  nameserver[1] : 8.8.8.8\n"
                "  flags    : Request A records\n"
            ),
        ),
    )
    await protector._save_original_dns()
    assert protector.original_dns_servers == ["1.1.1.1", "8.8.8.8"]


@pytest.mark.asyncio
async def test_save_original_dns_exception(monkeypatch):
    protector = mod.VPNLeakProtector(doh_resolver=_DummyResolver())
    monkeypatch.setattr(mod.sys, "platform", "linux")

    def _raise(*_a, **_k):
        raise RuntimeError("cat failed")

    monkeypatch.setattr(mod.SafeSubprocess, "run", _raise)
    await protector._save_original_dns()
    assert protector.original_dns_servers == []


@pytest.mark.asyncio
async def test_configure_doh_paths(monkeypatch):
    protector = mod.VPNLeakProtector(doh_resolver=_DummyResolver())
    protector.vpn_interface = "tun0"

    calls = []

    def _run(cmd, timeout=10):
        calls.append(cmd)
        if cmd[:2] == ["systemctl", "is-active"]:
            return _CmdResult(success=True, stdout="active")
        if cmd[:2] == ["resolvectl", "dns"]:
            return _CmdResult(success=False, stderr="dns fail")
        return _CmdResult(success=True)

    monkeypatch.setattr(mod.sys, "platform", "linux")
    monkeypatch.setattr(mod.os.path, "exists", lambda p: p == "/etc/systemd/resolved.conf")
    monkeypatch.setattr(mod.SafeSubprocess, "run", _run)
    await protector._configure_doh()
    assert calls[0][:2] == ["systemctl", "is-active"]
    assert calls[1][:2] == ["resolvectl", "dns"]
    assert calls[2][:2] == ["resolvectl", "domain"]

    monkeypatch.setattr(mod.sys, "platform", "win32")
    await protector._configure_doh()

    monkeypatch.setattr(mod.sys, "platform", "darwin")
    await protector._configure_doh()


@pytest.mark.asyncio
async def test_configure_doh_exception(monkeypatch):
    protector = mod.VPNLeakProtector(doh_resolver=_DummyResolver())
    protector.vpn_interface = "tun0"
    monkeypatch.setattr(mod.sys, "platform", "linux")
    monkeypatch.setattr(mod.os.path, "exists", lambda _p: True)

    def _raise(*_a, **_k):
        raise RuntimeError("systemctl failed")

    monkeypatch.setattr(mod.SafeSubprocess, "run", _raise)
    await protector._configure_doh()


@pytest.mark.asyncio
async def test_restore_original_dns_paths(monkeypatch):
    protector = mod.VPNLeakProtector(doh_resolver=_DummyResolver())
    protector.vpn_interface = "tun0"

    # no servers -> early return
    protector.original_dns_servers = []
    await protector._restore_original_dns()

    # linux success/failure
    protector.original_dns_servers = ["1.1.1.1"]
    monkeypatch.setattr(mod.sys, "platform", "linux")
    monkeypatch.setattr(mod.SafeSubprocess, "run", lambda *_a, **_k: _CmdResult(success=True))
    await protector._restore_original_dns()

    monkeypatch.setattr(
        mod.SafeSubprocess,
        "run",
        lambda *_a, **_k: _CmdResult(success=False, stderr="revert failed"),
    )
    await protector._restore_original_dns()

    # non-linux warning path
    monkeypatch.setattr(mod.sys, "platform", "win32")
    await protector._restore_original_dns()


@pytest.mark.asyncio
async def test_restore_original_dns_exception(monkeypatch):
    protector = mod.VPNLeakProtector(doh_resolver=_DummyResolver())
    protector.vpn_interface = "tun0"
    protector.original_dns_servers = ["1.1.1.1"]
    monkeypatch.setattr(mod.sys, "platform", "linux")

    def _raise(*_a, **_k):
        raise RuntimeError("revert boom")

    monkeypatch.setattr(mod.SafeSubprocess, "run", _raise)
    await protector._restore_original_dns()


@pytest.mark.asyncio
async def test_firewall_and_kill_switch_paths(monkeypatch):
    protector = mod.VPNLeakProtector(doh_resolver=_DummyResolver())
    protector.vpn_interface = "tun0"

    fw_calls = []

    async def _record_fw(args):
        fw_calls.append(args)
        return True, "", ""

    monkeypatch.setattr(mod.sys, "platform", "linux")
    monkeypatch.setattr(mod.os.path, "exists", lambda p: p == "/sbin/iptables")
    monkeypatch.setattr(protector, "_run_iptables_command", _record_fw)
    await protector._configure_firewall()
    assert fw_calls[0] == ["-A", "INPUT", "-i", "lo", "-j", "ACCEPT"]
    assert fw_calls[-1] == ["-P", "OUTPUT", "DROP"]

    restore_calls = []

    async def _record_restore(args):
        restore_calls.append(args)
        return True, "", ""

    monkeypatch.setattr(protector, "_run_iptables_command", _record_restore)
    await protector._restore_firewall()
    assert restore_calls == [
        ["-F"],
        ["-X"],
        ["-P", "INPUT", "ACCEPT"],
        ["-P", "OUTPUT", "ACCEPT"],
        ["-P", "FORWARD", "ACCEPT"],
    ]

    kill_calls = []

    async def _record_kill(args):
        kill_calls.append(args)
        return True, "", ""

    monkeypatch.setattr(protector, "_run_iptables_command", _record_kill)
    await protector._enable_kill_switch()
    assert protector.kill_switch_enabled is True
    assert kill_calls[0] == ["-N", "VPN_KILL_SWITCH"]

    await protector._disable_kill_switch()
    assert protector.kill_switch_enabled is False


@pytest.mark.asyncio
async def test_firewall_non_linux_and_exception_paths(monkeypatch):
    protector = mod.VPNLeakProtector(doh_resolver=_DummyResolver())

    monkeypatch.setattr(mod.sys, "platform", "darwin")
    await protector._configure_firewall()
    await protector._restore_firewall()

    monkeypatch.setattr(mod.sys, "platform", "linux")
    monkeypatch.setattr(mod.os.path, "exists", lambda _p: True)

    async def _raise_cmd(_args):
        raise RuntimeError("iptables failed")

    monkeypatch.setattr(protector, "_run_iptables_command", _raise_cmd)
    await protector._configure_firewall()
    await protector._restore_firewall()


@pytest.mark.asyncio
async def test_kill_switch_exception_and_non_linux(monkeypatch):
    protector = mod.VPNLeakProtector(doh_resolver=_DummyResolver())
    protector.vpn_interface = "tun0"

    monkeypatch.setattr(mod.sys, "platform", "darwin")
    await protector._enable_kill_switch()
    protector.kill_switch_enabled = True
    await protector._disable_kill_switch()
    assert protector.kill_switch_enabled is False

    monkeypatch.setattr(mod.sys, "platform", "linux")

    async def _raise_cmd(_args):
        raise RuntimeError("kill switch failed")

    monkeypatch.setattr(protector, "_run_iptables_command", _raise_cmd)
    await protector._enable_kill_switch()
    assert protector.kill_switch_enabled is False

    protector.kill_switch_enabled = True
    await protector._disable_kill_switch()
    assert protector.kill_switch_enabled is False


@pytest.mark.asyncio
async def test_run_iptables_command_paths(monkeypatch):
    protector = mod.VPNLeakProtector(doh_resolver=_DummyResolver())

    monkeypatch.setattr(
        mod.SafeSubprocess,
        "run",
        lambda *_a, **_k: _CmdResult(success=True, stdout="ok", stderr=""),
    )
    ok = await protector._run_iptables_command(["-L"])
    assert ok == (True, "ok", "")

    monkeypatch.setattr(
        mod.SafeSubprocess,
        "run",
        lambda *_a, **_k: _CmdResult(success=False, stdout="", stderr="bad"),
    )
    bad = await protector._run_iptables_command(["-L"])
    assert bad == (False, "", "bad")

    monkeypatch.setattr(mod.SafeSubprocess, "run", lambda *_a, **_k: (_ for _ in ()).throw(mod.ValidationError("v")))
    assert await protector._run_iptables_command(["-L"]) == (False, "", "v")

    monkeypatch.setattr(mod.SafeSubprocess, "run", lambda *_a, **_k: (_ for _ in ()).throw(mod.SecurityError("s")))
    assert await protector._run_iptables_command(["-L"]) == (False, "", "s")

    monkeypatch.setattr(mod.SafeSubprocess, "run", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("x")))
    assert await protector._run_iptables_command(["-L"]) == (False, "", "x")


@pytest.mark.asyncio
async def test_dns_leak_paths():
    resolver = _DummyResolver(
        mapping={"ok.com": ["1.1.1.1"], "empty.com": []},
        errors={"err.com"},
    )
    protector = mod.VPNLeakProtector(doh_resolver=resolver)

    result = await protector.test_dns_leak(["ok.com", "empty.com", "err.com"])
    assert result.leak_type == mod.LeakType.DNS
    assert result.is_leaking is True
    assert any(item["domain"] == "ok.com" for item in result.details["results"])


class _FakeIPResponse:
    def __init__(self, status, text):
        self.status = status
        self._text = text

    async def text(self):
        return self._text


class _FakeIPResponseCM:
    def __init__(self, status, text):
        self._resp = _FakeIPResponse(status, text)

    async def __aenter__(self):
        return self._resp

    async def __aexit__(self, *_args):
        return False


class _FakeIPSession:
    def get(self, service, **_kwargs):
        if "ipify" in service:
            return _FakeIPResponseCM(200, '{"ip": "9.9.9.9"}')
        if "httpbin" in service:
            return _FakeIPResponseCM(200, '{"origin": "9.9.9.9"}')
        return _FakeIPResponseCM(200, "9.9.9.9\n")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False


class _FakeIPSessionEmpty:
    def get(self, _service, **_kwargs):
        return _FakeIPResponseCM(500, "")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False


@pytest.mark.asyncio
async def test_ip_leak_paths(monkeypatch):
    fake_aiohttp = SimpleNamespace(
        ClientSession=lambda: _FakeIPSession(),
        ClientTimeout=lambda total: SimpleNamespace(total=total),
    )
    monkeypatch.setitem(sys.modules, "aiohttp", fake_aiohttp)

    protector = mod.VPNLeakProtector(doh_resolver=_DummyResolver())

    monkeypatch.setenv("VPN_SERVER", "9.9.9.9")
    ok = await protector.test_ip_leak()
    assert ok.is_leaking is False
    assert ok.details["consistent_ip"] is True

    monkeypatch.setenv("VPN_SERVER", "1.1.1.1")
    mismatch = await protector.test_ip_leak()
    assert mismatch.is_leaking is True

    monkeypatch.delenv("VPN_SERVER", raising=False)
    warn = await protector.test_ip_leak()
    assert warn.is_leaking is False
    assert "warning" in warn.details

    fake_aiohttp_empty = SimpleNamespace(
        ClientSession=lambda: _FakeIPSessionEmpty(),
        ClientTimeout=lambda total: SimpleNamespace(total=total),
    )
    monkeypatch.setitem(sys.modules, "aiohttp", fake_aiohttp_empty)
    empty = await protector.test_ip_leak()
    assert empty.is_leaking is True
    assert empty.details["error"] == "Could not detect public IP"


@pytest.mark.asyncio
async def test_webrtc_leak_paths(monkeypatch):
    class _FakeFix:
        def __init__(self):
            self._statuses = [
                {
                    "chrome_policy_exists": False,
                    "firefox_prefs_exists": False,
                    "system_rules_active": False,
                },
                {
                    "chrome_policy_exists": True,
                    "firefox_prefs_exists": False,
                    "system_rules_active": False,
                },
            ]

        def check_webrtc_status(self):
            if self._statuses:
                return self._statuses.pop(0)
            return {"chrome_policy_exists": True}

        def apply_browser_fixes(self):
            return {"chrome": True, "firefox": False, "system_wide": False}

    fake_module = SimpleNamespace(get_webrtc_fix=lambda: _FakeFix())
    monkeypatch.setitem(sys.modules, "src.network.webrtc_leak_fix", fake_module)

    protector = mod.VPNLeakProtector(doh_resolver=_DummyResolver())
    result = await protector.test_webrtc_leak()
    assert result.leak_type == mod.LeakType.WebRTC
    assert result.is_leaking is False
    assert "fix_results" in result.details

    def _raise_fix():
        raise RuntimeError("webrtc import fail")

    monkeypatch.setitem(
        sys.modules,
        "src.network.webrtc_leak_fix",
        SimpleNamespace(get_webrtc_fix=_raise_fix),
    )
    bad = await protector.test_webrtc_leak()
    assert bad.is_leaking is True
    assert "error" in bad.details


@pytest.mark.asyncio
async def test_run_all_status_and_singleton():
    protector = mod.VPNLeakProtector(doh_resolver=_DummyResolver())

    async def _dns():
        return mod.LeakTestResult(mod.LeakType.DNS, False, {})

    async def _ip():
        return mod.LeakTestResult(mod.LeakType.IP, False, {})

    async def _webrtc():
        return mod.LeakTestResult(mod.LeakType.WebRTC, True, {})

    protector.test_dns_leak = _dns
    protector.test_ip_leak = _ip
    protector.test_webrtc_leak = _webrtc

    all_tests = await protector.run_all_tests()
    assert [t.leak_type for t in all_tests] == [
        mod.LeakType.DNS,
        mod.LeakType.IP,
        mod.LeakType.WebRTC,
    ]

    status = await protector.get_status()
    assert status["resolver_info"]["resolver"] == "dummy"

    mod._global_protector = None
    first = await mod.get_vpn_protector()
    second = await mod.get_vpn_protector()
    assert first is second


@pytest.mark.asyncio
async def test_test_protection_happy_and_error_paths(monkeypatch):
    calls = {"get_status": 0, "run_all": 0, "enable": 0, "disable": 0}

    class _HappyProtector:
        async def get_status(self):
            calls["get_status"] += 1
            return {"protection_enabled": False, "kill_switch_enabled": False}

        async def run_all_tests(self):
            calls["run_all"] += 1
            return [mod.LeakTestResult(mod.LeakType.DNS, False, {})]

        async def enable_protection(self):
            calls["enable"] += 1

        async def disable_protection(self):
            calls["disable"] += 1

    monkeypatch.setattr(mod, "VPNLeakProtector", _HappyProtector)
    await mod.test_protection()
    assert calls == {"get_status": 2, "run_all": 2, "enable": 1, "disable": 1}

    class _ErrorProtector(_HappyProtector):
        async def enable_protection(self):
            raise RuntimeError("enable failed")

        async def disable_protection(self):
            raise RuntimeError("disable failed")

    monkeypatch.setattr(mod, "VPNLeakProtector", _ErrorProtector)
    await mod.test_protection()
