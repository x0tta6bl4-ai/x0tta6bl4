import asyncio
import sys
from types import SimpleNamespace

import pytest

import src.network.vpn_leak_protection as mod


class _CmdResult:
    def __init__(self, success=True, stdout="", stderr=""):
        self.success = success
        self.stdout = stdout
        self.stderr = stderr


class _DummyResolver:
    def __init__(self, mapping=None, errors=None):
        self.mapping = mapping or {}
        self.errors = set(errors or [])

    async def resolve_a(self, domain):
        if domain in self.errors:
            raise RuntimeError(f"resolver failed: {domain}")
        return self.mapping.get(domain, [])

    def get_stats(self):
        return {"resolver": "dummy"}


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
